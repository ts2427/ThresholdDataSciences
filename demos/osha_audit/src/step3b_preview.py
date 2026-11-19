r"""Demo B step 3b PREVIEW: what name normalization would do to the top 15
and the distinct-employer count, on the step-3a data. Writes
results/osha_audit.json["step3b_preview"]; does not create the normalized
dataset (that happens only after Tim's review).

    .venv\Scripts\python -m osha_audit.src.step3b_preview
"""
from pathlib import Path

import pandas as pd

from osha_audit.src.naive import save_results
from osha_audit.src.normalize import name_key, normalize_name

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data/interim/osha_step3a.csv"


def grouped_top(df, key_col="key", top=15):
    """Reports per key with the most common raw spelling as the label and
    the number of distinct raw variants; ties broken by key."""
    g = df.groupby(key_col)
    t = pd.DataFrame({
        "reports": g.size(),
        "raw_variants": g["Employer"].nunique(),
        "label": g["Employer"].agg(lambda s: s.value_counts().index[0]),
        "federalstate0_reports": g["FederalState"].agg(lambda s: int((s == "0").sum())),
    }).reset_index().sort_values(["reports", key_col], ascending=[False, True])
    t["share_pct"] = 100 * t["reports"] / len(df)
    t = t.head(top).reset_index(drop=True)
    t.insert(0, "rank", range(1, len(t) + 1))
    return t


def main():
    df = pd.read_csv(IN, dtype=str, keep_default_na=False)
    df["norm"] = df["Employer"].map(normalize_name)
    df["key"] = df["Employer"].map(name_key)
    top = grouped_top(df)
    v = df.groupby("key")["Employer"].nunique().sort_values(ascending=False)
    biggest = [{"key": k, "raw_variants": int(n), "reports": int((df.key == k).sum()),
                "examples": df.loc[df.key == k, "Employer"].value_counts().head(6).index.tolist()}
               for k, n in v.head(10).items()]
    fs0 = df[df.FederalState == "0"]
    payload = {
        "distinct_raw_before": int(df["Employer"].nunique()),
        "distinct_after_normalization": int(df["key"].nunique()),
        "distinct_normalized_with_spaces": int(df["norm"].nunique()),
        "top15": top.to_dict(orient="records"),
        "largest_merges": biggest,
        "federalstate0": {"reports": int(len(fs0)), "distinct_raw": int(fs0.Employer.nunique()),
                          "distinct_after": int(fs0.key.nunique())},
        "status": "preview only; not applied",
    }
    save_results("step3b_preview", payload)
    return payload, top


if __name__ == "__main__":
    p, top = main()
    print({k: p[k] for k in ("distinct_raw_before", "distinct_after_normalization",
                             "distinct_normalized_with_spaces", "federalstate0")})
    print(top[["rank", "label", "key", "reports", "raw_variants", "share_pct"]].round(2).to_string(index=False))
    for b in p["largest_merges"]:
        print(f"{b['key']}: {b['raw_variants']} variants, {b['reports']} reports, e.g. {b['examples'][:4]}")
