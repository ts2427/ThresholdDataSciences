r"""Demo B step 3b check (Tim): a random sample of merges in which ONLY the
legal suffix differs, for hand review before normalization is applied.

A "suffix form" is a name's normalized base plus its stripped legal-suffix
tail, e.g. ("abc", ("co",)). Within one grouping key, two forms with
different non-empty tails are a suffix-only merge ("abc co" + "abc inc").
Forms with an empty tail ("abc" + "abc inc") are counted separately as
suffix-omission merges.

    .venv\Scripts\python -m osha_audit.src.suffix_sample
"""
import itertools
from pathlib import Path

import pandas as pd

from osha_audit.src.naive import save_results
from osha_audit.src.normalize import name_key, suffix_tail

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data/interim/osha_step3a.csv"
OUT = ROOT / "review/b_suffix_sample.csv"
SEED, N = 20261119, 100


def suffix_forms(df):
    """One row per (key, tail): representative raw name, reports, states."""
    d = df.assign(key=df.Employer.map(name_key), tail=df.Employer.map(lambda s: " ".join(suffix_tail(s))))
    g = d.groupby(["key", "tail"])
    return pd.DataFrame({
        "raw_example": g["Employer"].agg(lambda s: s.value_counts().index[0]),
        "raw_variants": g["Employer"].nunique(),
        "reports": g.size(),
        "states": g["State"].agg(lambda s: "; ".join(sorted(set(s)))),
        "federalstate0_reports": g["FederalState"].agg(lambda s: int((s == "0").sum())),
    }).reset_index()


def suffix_pairs(forms):
    """All pairs of forms sharing a key; returns (suffix_only, omission)
    DataFrames with columns from both sides (_a, _b)."""
    rows_only, rows_omit = [], []
    for key, g in forms.groupby("key"):
        if len(g) < 2:
            continue
        for (_, a), (_, b) in itertools.combinations(g.iterrows(), 2):
            rec = {"key": key, **{f"{c}_a": a[c] for c in g.columns if c != "key"},
                   **{f"{c}_b": b[c] for c in g.columns if c != "key"}}
            (rows_only if a["tail"] and b["tail"] else rows_omit).append(rec)
    return pd.DataFrame(rows_only), pd.DataFrame(rows_omit)


def main():
    df = pd.read_csv(IN, dtype=str, keep_default_na=False)
    forms = suffix_forms(df)
    only, omit = suffix_pairs(forms)
    sample = only.sample(n=min(N, len(only)), random_state=SEED).reset_index(drop=True)
    out = pd.DataFrame({
        "item": range(1, len(sample) + 1),
        "raw_name_a": sample.raw_example_a, "suffix_a": sample.tail_a,
        "reports_a": sample.reports_a, "states_a": sample.states_a,
        "raw_name_b": sample.raw_example_b, "suffix_b": sample.tail_b,
        "reports_b": sample.reports_b, "states_b": sample.states_b,
        "shared_states": [len(set(a.split("; ")) & set(b.split("; "))) for a, b in zip(sample.states_a, sample.states_b)],
        "same company": "",
    })
    OUT.parent.mkdir(exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    payload = {"suffix_only_pairs": int(len(only)), "suffix_omission_pairs": int(len(omit)),
               "keys_with_suffix_only_merge": int(only.key.nunique()) if len(only) else 0,
               "sample_size": int(len(out)), "seed": SEED,
               "sample_pairs_sharing_a_state": int((out.shared_states > 0).sum()),
               "status": "awaiting Tim's Y/N in review/b_suffix_sample.csv"}
    save_results("step3b_suffix_check", payload)
    return payload, out


if __name__ == "__main__":
    import json
    p, out = main()
    print(json.dumps(p, indent=1))
    print(out.drop(columns=["same company"]).head(25).to_string(index=False))
