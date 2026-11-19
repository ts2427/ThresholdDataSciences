r"""Naive vs careful, the write-up's main contrast (Tim, 2026-11-19):

- naive before-and-after: the 2014 cohort's population-weighted uninsured
  rate, 2013 vs the 2016–2019 average, with no comparison group;
- comparison-group-adjusted: the same change minus the change over the same
  years in states untreated through 2019 (never-treated and later
  adopters) — a 2×2 difference-in-differences.

Both from state-year rates weighted by the low-income adult population;
95% intervals from a state-cluster bootstrap (2,000 draws).

    .venv\Scripts\python -m medicaid_did.src.before_after
"""
from pathlib import Path

import numpy as np
import pandas as pd

from medicaid_did.src.cs import cluster_bootstrap
from medicaid_did.src.step1_summary import save_results

ROOT = Path(__file__).resolve().parents[2]
PRE, POST = [2013], [2016, 2017, 2018, 2019]


def group_rate(d, years):
    s = d[d.year.isin(years)]
    return float(np.average(s.y, weights=s.w))


def before_after(d, pre=PRE, post=POST):
    """d: id, year, group ('treated'/'comparison'), y (pp), w. Returns the
    levels, the naive change and the comparison-adjusted change."""
    t, c = d[d.group == "treated"], d[d.group == "comparison"]
    out = {"treated_pre": group_rate(t, pre), "treated_post": group_rate(t, post),
           "comparison_pre": group_rate(c, pre), "comparison_post": group_rate(c, post)}
    out["naive_change"] = out["treated_post"] - out["treated_pre"]
    out["comparison_change"] = out["comparison_post"] - out["comparison_pre"]
    out["adjusted_change"] = out["naive_change"] - out["comparison_change"]
    return pd.Series(out)


def frame(panel):
    d = panel[panel.year <= 2019].copy()
    d["group"] = np.select([d.cohort == 2014, (d.cohort == 0) | (d.cohort > 2019)],
                           ["treated", "comparison"], default="other")
    d = d[d.group != "other"]
    return pd.DataFrame({"id": d.fips.astype(int), "year": d.year, "group": d.group,
                         "y": 100 * d.lowinc_rate, "w": d.lowinc_pop})


def main(reps=2000):
    panel = pd.read_csv(ROOT / "data/processed/analysis_panel.csv", dtype={"fips": str})
    d = frame(panel)
    point = before_after(d)
    draws = cluster_bootstrap(d, before_after, reps=reps)
    ci = {k: [float(draws[k].quantile(0.025)), float(draws[k].quantile(0.975))] for k in point.index}
    payload = {"point": point.to_dict(), "ci95": ci, "reps": reps,
               "pre_years": PRE, "post_years": POST,
               "treated_states": int(d[d.group == "treated"].id.nunique()),
               "comparison_states": int(d[d.group == "comparison"].id.nunique())}
    save_results("naive_vs_careful", payload)
    # figure data: yearly rates of both groups, plus the two summary bars
    yearly = (d.assign(num=d.y * d.w).groupby(["group", "year"])
                .agg(num=("num", "sum"), den=("w", "sum")).reset_index())
    yearly["rate_pct"] = yearly.num / yearly.den
    yearly[["group", "year", "rate_pct"]].to_csv(ROOT / "results/figures/a_before_after_yearly.csv", index=False)
    pd.DataFrame([
        {"estimate": "Before and after (2014 cohort, no comparison)", "pp": point.naive_change,
         "lo": ci["naive_change"][0], "hi": ci["naive_change"][1]},
        {"estimate": "Change in comparison states", "pp": point.comparison_change,
         "lo": ci["comparison_change"][0], "hi": ci["comparison_change"][1]},
        {"estimate": "Comparison-adjusted (2x2 DiD)", "pp": point.adjusted_change,
         "lo": ci["adjusted_change"][0], "hi": ci["adjusted_change"][1]},
    ]).to_csv(ROOT / "results/figures/a_naive_vs_careful.csv", index=False)
    return payload


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=1))
