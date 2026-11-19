r"""Step A1 summary: build the analysis panel, validate PUMS against the
published table, and write the step-1 numbers to results/medicaid_did.json.

    .venv\Scripts\python -m medicaid_did.src.step1_summary
"""
import json
from pathlib import Path

import pandas as pd

from medicaid_did.src.panel import build_panel, main_window_group, weighted_group_rates
from medicaid_did.src.validate import compare_rates

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data/processed"
RESULTS = ROOT / "results/medicaid_did.json"


def load_results():
    return json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}


def save_results(section, payload):
    r = load_results()
    r[section] = payload
    RESULTS.write_text(json.dumps(r, indent=2), encoding="utf-8")


def main():
    rates = pd.read_csv(PROC / "pums_state_year.csv", dtype={"fips": str})
    pub = pd.read_csv(PROC / "c27016_published_2017_2019.csv", dtype={"fips": str})
    exp = pd.read_csv(PROC / "expansion_dates.csv")
    names = pub[["fips", "state"]].drop_duplicates()
    panel = build_panel(rates, exp, names)
    panel.to_csv(PROC / "analysis_panel.csv", index=False)

    val = {}
    for col in ("lowinc_rate", "all_rate"):
        s, _ = compare_rates(rates[["year", "fips", col]],
                             pub[["year", "fips", col, col + "_moe90"]], col)
        val[col] = s

    main = panel[panel.year <= 2019].copy()
    main["group"] = main["cohort"].map(main_window_group)
    trends = weighted_group_rates(main, "group")
    trends_all = weighted_group_rates(main, "group", "all_rate", "all_pop")

    payload = {
        "panel": {"state_years": int(len(panel)), "states": int(panel.fips.nunique()),
                  "years": sorted(int(y) for y in panel.year.unique()),
                  "lowinc_n_min": int(panel.lowinc_n.min()),
                  "lowinc_n_median": float(panel.lowinc_n.median()),
                  "lowinc_n_min_where": panel.loc[panel.lowinc_n.idxmin(), ["state", "year"]].astype(str).tolist()},
        "validation_vs_c27016_2017_2019": val,
        "main_window_groups": main.groupby("group")["state"].apply(lambda s: sorted(set(s))).to_dict(),
        "lowinc_rate_pct_by_group_year": trends.to_dict(orient="records"),
        "all_rate_pct_by_group_year": trends_all.to_dict(orient="records"),
    }
    save_results("step1_data", payload)
    return panel, payload


if __name__ == "__main__":
    panel, payload = main()
    t = pd.DataFrame(payload["lowinc_rate_pct_by_group_year"])
    print(t.pivot(index="year", columns="group", values="rate_pct").round(1).to_string())
    print({g: len(s) for g, s in payload["main_window_groups"].items()})
