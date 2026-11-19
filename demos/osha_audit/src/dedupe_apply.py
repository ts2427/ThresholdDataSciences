r"""Demo B step 3a (final): apply the hand-confirmed same-employer duplicate
pairs from review/b_dup_pairs.csv.

- Pairs whose `confirm` starts with "Y" are merged; "N" pairs keep both rows.
- Confirmed pairs are clustered (union-find); each cluster keeps its lowest
  UPA row, which takes the HIGHER Hospitalized, Amputation and Loss of Eye
  values from any row in the cluster (Tim, 2026-11-19).
- Writes data/interim/osha_step3a.csv and results to results/osha_audit.json.

    .venv\Scripts\python -m osha_audit.src.dedupe_apply
"""
from pathlib import Path

import pandas as pd

from osha_audit.src.download import RAW, read_member
from osha_audit.src.duplicates import clusters
from osha_audit.src.naive import MEMBER, naive_counts, save_results

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "review/b_dup_pairs.csv"
OUT = ROOT / "data/interim/osha_step3a.csv"
COUNT_COLS = ["Hospitalized", "Amputation", "Loss of Eye"]


def confirmed_pairs(review):
    c = review["confirm"].fillna("").str.strip().str.upper()
    bad = review.loc[~(c.str.startswith("Y") | c.str.startswith("N")), "pair"]
    if len(bad):
        raise ValueError(f"pairs without a Y/N decision: {bad.tolist()}")
    keep = review[c.str.startswith("Y")]
    return list(zip(keep["upa_kept"].astype(str), keep["upa_removed"].astype(str)))


def apply_merges(df, pairs, count_cols=COUNT_COLS):
    """df indexed by anything, with a string UPA column. Returns (new df,
    list of removed UPAs). The kept row of each cluster is the lowest UPA
    and carries the max of count_cols across the cluster."""
    out = df.copy()
    pos = {u: i for i, u in zip(out.index, out["UPA"].astype(str))}
    missing = [u for p in pairs for u in p if u not in pos]
    if missing:
        raise ValueError(f"UPAs not in data: {missing}")
    removed = []
    for c in clusters(pairs):
        keep = min(c, key=int)
        for col in count_cols:
            vals = pd.to_numeric(out.loc[[pos[u] for u in c], col], errors="coerce")
            if vals.notna().any():
                out.loc[pos[keep], col] = f"{vals.max():.2f}"
        removed += sorted(c - {keep}, key=int)
    out = out.drop(index=[pos[u] for u in removed])
    return out, removed


def main():
    df = read_member(RAW, MEMBER)
    review = pd.read_csv(REVIEW, dtype=str, keep_default_na=False)
    pairs = confirmed_pairs(review)
    after, removed = apply_merges(df, pairs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    after.to_csv(OUT, index=False)

    top_before, distinct_before = naive_counts(df)
    top_after, distinct_after = naive_counts(after)
    fs0 = lambda d: int((d["FederalState"] == "0").sum())
    judgment = review[review["confirm"].str.contains("judgment", case=False)]
    payload = {
        "pairs_reviewed": int(len(review)),
        "pairs_confirmed": int(len(pairs)),
        "pairs_rejected": int(len(review) - len(pairs)),
        "rejected_pairs": review.loc[review["confirm"].str.upper().str.startswith("N"), "pair"].astype(int).tolist(),
        "judgment_call_pairs": judgment["pair"].astype(int).tolist(),
        "rows_removed": len(removed), "removed_upas": removed,
        "reports_before": int(len(df)), "reports_after": int(len(after)),
        "removed_pct_of_reports": 100 * len(removed) / len(df),
        "distinct_raw_employers_before": distinct_before,
        "distinct_raw_employers_after": distinct_after,
        "federalstate0_before": fs0(df), "federalstate0_after": fs0(after),
        "top15_after": top_after.to_dict(orient="records"),
        "merge_rule": "keep lowest UPA; take max Hospitalized, Amputation, Loss of Eye in the cluster",
    }
    save_results("step3a_final", payload)
    return payload, top_before, top_after


if __name__ == "__main__":
    import json
    p, tb, ta = main()
    print(json.dumps({k: v for k, v in p.items() if k not in ("top15_after", "removed_upas")}, indent=1))
    m = tb[["rank", "employer", "reports"]].merge(ta[["employer", "reports"]], on="employer", how="outer",
                                                 suffixes=("_before", "_after"))
    print(m.sort_values("reports_before", ascending=False).to_string(index=False))
