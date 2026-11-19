r"""Demo B step 3c PREVIEW: run the proposed fuzzy rule (osha_audit/src/
fuzzy3c.py) on the step-3b employers without writing a resolved dataset.
Also derives the C3 national-alias candidates (employers in >= 10 states)
for Tim's review: acronym links and name-containment links.

    .venv\Scripts\python -m osha_audit.src.step3c_preview
"""
from pathlib import Path

import pandas as pd

from osha_audit.src.duplicates import clusters
from osha_audit.src.entities3b import counts
from osha_audit.src.fuzzy3c import (DISTINCT, GENERIC_MIN, MULTI_STATES, OVERALL, candidate_pairs,
                                    canon, generic_tokens, is_match)
from osha_audit.src.naive import save_results
from osha_audit.src.normalize import normalize_name

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data/interim/osha_step3b.csv"
NATIONAL_STATES = 10


def entity_table(d):
    g = d.groupby("entity")
    E = pd.DataFrame({"label": g.entity_label.first(), "reports": g.size(),
                      "nstates": g.State.nunique(),
                      "states": g.State.agg(lambda s: frozenset(s))}).reset_index()
    E["name"] = E.label.map(normalize_name)
    return E


def initials(name):
    """Initials of a multi-word name with a leading "us" read as "united
    states" (so "us postal service" -> "usps", never "ups"). Single-word
    names have no initials."""
    toks = name.split()
    if toks[:1] == ["us"]:
        toks = ["united", "states"] + toks[1:]
    return "".join(t[0] for t in toks) if len(toks) > 1 else ""


def alias_candidates(E, min_states=NATIONAL_STATES):
    """Acronym links (a short name equals another's initials, after reading
    'us' as 'united states') and containment links (one name's tokens are a
    subset of the other's) among employers in >= min_states states."""
    N = E[E.nstates >= min_states].copy()
    N["toks"] = N.name.map(lambda n: frozenset(n.split()))
    N["init"] = N.name.map(initials)
    rows = []
    for a in N.itertuples():
        for b in N.itertuples():
            if a.entity >= b.entity:
                continue
            kind = None
            if a.name.replace(" ", "") in (b.init,) or b.name.replace(" ", "") in (a.init,):
                kind = "acronym"
            elif a.toks < b.toks or b.toks < a.toks:
                kind = "containment"
            if kind:
                rows.append({"kind": kind, "name_a": a.label, "reports_a": a.reports, "states_a": a.nstates,
                             "name_b": b.label, "reports_b": b.reports, "states_b": b.nstates,
                             "approve": ""})
    return pd.DataFrame(rows)


def resolve(d, E, generic, cutoff=OVERALL):
    cand = candidate_pairs(E[["entity", "name", "states", "nstates"]], cutoff=cutoff)
    nm = E.set_index("entity").name
    st = E.set_index("entity").states
    matched, c1, c2 = [], 0, 0
    for a, b in cand:
        if is_match(nm[a], nm[b], generic):
            matched.append((a, b))
            if st[a] & st[b]:
                c1 += 1
            else:
                c2 += 1
    root = {}
    for c in clusters(matched):
        r = min(c)
        for v in c:
            root[v] = r
    r = d.copy()
    r["entity3c"] = r.entity.map(lambda e: root.get(e, e))
    lab = r.groupby("entity3c").Employer.agg(lambda s: s.value_counts().index[0])
    r["label3c"] = r.entity3c.map(lab)
    return r, {"candidate_pairs": len(cand), "matched_pairs": len(matched),
               "matched_within_state": c1, "matched_cross_state": c2}, matched


def top_table(r, top=15):
    g = r.groupby("entity3c")
    t = pd.DataFrame({"label": g.label3c.first(), "reports": g.size(), "raw_variants": g.Employer.nunique(),
                      "states": g.State.nunique(),
                      "federalstate0_reports": g.FederalState.agg(lambda s: int((s == "0").sum()))})
    t = t.reset_index(drop=True).sort_values(["reports", "label"], ascending=[False, True]).head(top)
    t["share_pct"] = 100 * t.reports / len(r)
    t.insert(0, "rank", range(1, len(t) + 1))
    return t.reset_index(drop=True)


def main():
    d = pd.read_csv(IN, dtype=str, keep_default_na=False)
    E = entity_table(d)
    generic = generic_tokens(E.name.map(canon))
    r, stats, matched = resolve(d, E, generic)
    after = counts(r.assign(entity=r.entity3c))
    before = counts(d.assign(entity=d.entity.astype(int)))
    nm = E.set_index("entity").name
    ex = pd.DataFrame([{"a": nm[a], "b": nm[b]} for a, b in matched]).sample(25, random_state=7)
    alias = alias_candidates(E)
    (ROOT / "review").mkdir(exist_ok=True)
    alias.to_csv(ROOT / "review/b_3c_alias_candidates.csv", index=False, encoding="utf-8-sig")
    payload = {"parameters": {"overall_min": OVERALL, "distinctive_min": DISTINCT,
                              "generic_token_min_names": GENERIC_MIN, "multi_state_min": MULTI_STATES,
                              "national_alias_min_states": NATIONAL_STATES},
               "generic_tokens": sorted(generic), "n_generic_tokens": len(generic),
               "multi_state_employers": int((E.nstates >= MULTI_STATES).sum()),
               "before": before, "after": after, **stats,
               "top15": top_table(r).to_dict(orient="records"),
               "alias_candidates": int(len(alias)),
               "status": "preview only; not applied"}
    save_results("step3c_preview", payload)
    return payload, ex, alias


if __name__ == "__main__":
    import json
    p, ex, alias = main()
    print(json.dumps({k: v for k, v in p.items() if k not in ("top15", "generic_tokens")}, indent=1))
    print("generic tokens (sample):", p["generic_tokens"][:60])
    print(pd.DataFrame(p["top15"]).round(2).to_string(index=False))
    print("\nrandom accepted matches:\n", ex.to_string(index=False))
    print("\nalias candidates:\n", alias.drop(columns="approve").to_string(index=False))
