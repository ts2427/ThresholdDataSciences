r"""Demo B step 3b, final rule (Tim, 2026-11-19): name normalization with the
NARROWER suffix rule, chosen in place of the hand review of
review/b_suffix_sample.csv as that review's conservative outcome.

Each raw name -> (base, suffix type):
  base        = normalize_name() with spaces removed (name_key), i.e. the
                name with its legal suffix stripped;
  suffix type = the stripped suffix tokens mapped to canonical types, so
                spelling variants of one type are equal (corp = corporation,
                inc = incorporated, co = company, ltd = limited).
Merging:
  - same base, same suffix type            -> always one employer;
  - same base, different suffix type, or
    one name without a suffix              -> one employer only if the two
                                              forms share at least one state.
Merges are transitive (union-find over (base, suffix type) forms), so a
chain of shared states can link forms that share no state directly.

    .venv\Scripts\python -m osha_audit.src.entities3b            # preview
    .venv\Scripts\python -m osha_audit.src.entities3b --apply    # write data
"""
import sys
from pathlib import Path

import pandas as pd

from osha_audit.src.duplicates import clusters
from osha_audit.src.naive import save_results
from osha_audit.src.normalize import name_key, suffix_tail

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data/interim/osha_step3a.csv"
OUT = ROOT / "data/interim/osha_step3b.csv"

CANON = {"inc": "inc", "incorporated": "inc", "corp": "corp", "corporation": "corp",
         "co": "co", "company": "co", "ltd": "ltd", "limited": "ltd", "llc": "llc",
         "lp": "lp", "llp": "llp", "pllc": "pllc", "pc": "pc", "plc": "plc"}


def suffix_type(raw):
    return " ".join(CANON[t] for t in suffix_tail(raw))


def forms(df):
    """One row per (base, stype) form with its state set and report count."""
    d = df.assign(base=df.Employer.map(name_key), stype=df.Employer.map(suffix_type))
    f = d.groupby(["base", "stype"]).agg(states=("State", lambda s: frozenset(s)),
                                         reports=("State", "size")).reset_index()
    return d, f


def link_forms(f, narrow=True):
    """Return {(base, stype): entity_id}. narrow=False reproduces the
    original rule (every form with the same base merges)."""
    ids = {(b, t): i for i, (b, t) in enumerate(zip(f.base, f.stype))}
    edges, blocked = [], 0
    for base, g in f.groupby("base"):
        rows = list(g.itertuples(index=False))
        for a in range(len(rows)):
            for b in range(a + 1, len(rows)):
                ra, rb = rows[a], rows[b]
                if not narrow or (ra.states & rb.states):
                    edges.append((ids[(ra.base, ra.stype)], ids[(rb.base, rb.stype)]))
                else:
                    blocked += 1
    entity = {v: v for v in ids.values()}
    for c in clusters(edges):
        root = min(c)
        for v in c:
            entity[v] = root
    return {k: entity[v] for k, v in ids.items()}, blocked


def assign(df, narrow=True):
    d, f = forms(df)
    mapping, blocked = link_forms(f, narrow=narrow)
    d["entity"] = [mapping[(b, t)] for b, t in zip(d.base, d.stype)]
    # readable label: the entity's most common raw spelling
    lab = d.groupby("entity")["Employer"].agg(lambda s: s.value_counts().index[0])
    d["entity_label"] = d["entity"].map(lab)
    return d, blocked


def counts(d):
    fs0 = d[d.FederalState == "0"]
    return {"by_name": int(d.entity.nunique()),
            "by_name_and_state": int(d[["entity", "State"]].drop_duplicates().shape[0]),
            "federalstate0_by_name": int(fs0.entity.nunique()),
            "federalstate0_by_name_and_state": int(fs0[["entity", "State"]].drop_duplicates().shape[0]),
            "federalstate0_reports": int(len(fs0))}


def top_table(d, top=15):
    g = d.groupby("entity")
    t = pd.DataFrame({"label": g.entity_label.first(), "reports": g.size(),
                      "raw_variants": g.Employer.nunique(), "states": g.State.nunique(),
                      "federalstate0_reports": g.FederalState.agg(lambda s: int((s == "0").sum()))})
    t = t.reset_index().sort_values(["reports", "label"], ascending=[False, True]).head(top)
    t["share_pct"] = 100 * t.reports / len(d)
    t.insert(0, "rank", range(1, len(t) + 1))
    return t.drop(columns="entity").reset_index(drop=True)


def main(apply=False):
    df = pd.read_csv(IN, dtype=str, keep_default_na=False)
    narrow, blocked = assign(df, narrow=True)
    orig, _ = assign(df, narrow=False)
    raw = {"by_name": int(df.Employer.nunique()),
           "by_name_and_state": int(df[["Employer", "State"]].drop_duplicates().shape[0])}
    payload = {"rule": "narrower suffix rule (see module docstring)",
               "distinct_raw": raw, "original_rule": counts(orig), "narrow_rule": counts(narrow),
               "cross_type_form_pairs_blocked": blocked,
               "extra_employers_vs_original": counts(narrow)["by_name"] - counts(orig)["by_name"],
               "top15": top_table(narrow).to_dict(orient="records"),
               "applied": apply}
    save_results("step3b_final" if apply else "step3b_narrow_preview", payload)
    if apply:
        narrow.to_csv(OUT, index=False)
    return payload


if __name__ == "__main__":
    import json
    p = main(apply="--apply" in sys.argv)
    print(json.dumps({k: v for k, v in p.items() if k != "top15"}, indent=1))
    print(pd.DataFrame(p["top15"]).round(2).to_string(index=False))
