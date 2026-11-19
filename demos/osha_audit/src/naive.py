r"""Demo B step 2: the naive answer — reports filed, counted by the raw
`Employer` field exactly as it appears in the file (no trimming, no case
folding), and the number of distinct raw employer names.

    .venv\Scripts\python -m osha_audit.src.naive
"""
import json
from pathlib import Path

import pandas as pd

from osha_audit.src.download import RAW, read_member

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results/osha_audit.json"
MEMBER = "January2015toNovember2025.csv"


def naive_counts(df, col="Employer", top=15):
    """Return (top-N table with rank, employer, reports, share), distinct
    raw names). Ties are broken alphabetically so the ranking is stable."""
    counts = df[col].value_counts()
    t = (counts.rename("reports").rename_axis("employer").reset_index()
         .sort_values(["reports", "employer"], ascending=[False, True]))
    t["share_pct"] = 100 * t["reports"] / len(df)
    t = t.head(top).reset_index(drop=True)
    t.insert(0, "rank", range(1, len(t) + 1))
    return t, int(counts.size)


def save_results(section, payload):
    r = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    r[section] = payload
    RESULTS.write_text(json.dumps(r, indent=2), encoding="utf-8")


def main():
    df = read_member(RAW, MEMBER)
    top, distinct = naive_counts(df)
    payload = {"reports": int(len(df)), "distinct_raw_employer_names": distinct,
               "top15": top.to_dict(orient="records"),
               "top15_share_of_reports_pct": float(top["share_pct"].sum()),
               "names_with_one_report": int((df["Employer"].value_counts() == 1).sum())}
    save_results("step2_naive", payload)
    top.to_csv(ROOT / "results/osha_naive_top15.csv", index=False)
    return payload, top


if __name__ == "__main__":
    payload, top = main()
    print(top.round(2).to_string(index=False))
    print({k: v for k, v in payload.items() if k != "top15"})
