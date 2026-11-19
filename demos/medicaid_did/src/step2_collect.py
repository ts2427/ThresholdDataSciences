r"""Step A2: collect the R and Python outputs into results/medicaid_did.json,
evaluate the pre-specified red flags, and export figure CSVs.

    .venv\Scripts\python -m medicaid_did.src.step2_collect
"""
from pathlib import Path

import numpy as np
import pandas as pd

from medicaid_did.src.cs import att_gt, cohort_sizes
from medicaid_did.src.step1_summary import save_results
from medicaid_did.src.twfe_weights import twfe_cell_weights

ROOT = Path(__file__).resolve().parents[2]
RA = ROOT / "results/demo_a"

# Benchmarks, fixed in docs/analysis_plan.md §7 before any estimate was seen.
BENCHMARKS = [
    {"study": "Miller & Wherry (2017), NEJM 376(10):947-956", "estimate_pp": -8.2,
     "population": "U.S. citizens 19-64, income <138% FPL", "survey": "NHIS",
     "timing": "year 2 after implementation (2015)", "interval": "not accessible (P<0.001)"},
    {"study": "Wehby & Lyu (2018), Health Services Research 53(2):1248-1271", "estimate_pp": -6.0,
     "population": "low-educated adults 19-64", "survey": "ACS",
     "timing": "2015", "interval": "not accessible"},
]
RANGE = (min(b["estimate_pp"] for b in BENCHMARKS), max(b["estimate_pp"] for b in BENCHMARKS))


def in_range(x, rng=RANGE):
    return rng[0] <= x <= rng[1]


def red_flags(pretest_p, headline, e1, rng=RANGE, alpha=0.05):
    """The two pre-specified triggers (analysis plan §8)."""
    return {
        "pre_period_jointly_significant": bool(pretest_p < alpha),
        "headline_outside_published_range": not in_range(headline, rng),
        "e1_outside_published_range": not in_range(e1, rng),
    }


def _csv(name):
    return pd.read_csv(RA / name)


def main_window_frame():
    p = pd.read_csv(ROOT / "data/processed/analysis_panel.csv", dtype={"fips": str})
    d = p[p.year <= 2019].copy()
    d["g"] = np.where(d.cohort.isin([2014, 2015, 2016, 2019]), d.cohort, 0)
    d["y"] = 100 * d.lowinc_rate
    d["id"] = d.fips.astype(int)
    d["w"] = d.lowinc_pop
    d["treat"] = ((d.g > 0) & (d.year >= d.g)).astype(int)
    return d


def twfe_vs_cs_weights(d):
    cw = twfe_cell_weights(d)
    cw["e"] = cw.year - cw.g
    sizes = cohort_sizes(d)
    tot = sum(sizes.values())
    cells = att_gt(d)
    post = cells[cells.t >= cells.g].copy()
    post["cs_weight"] = post.g.map(sizes) / tot / post.groupby("g").t.transform("count")
    by_e = pd.DataFrame({"twfe_weight": cw.groupby("e").twfe_weight.sum(),
                         "cs_weight": post.groupby("e").cs_weight.sum()}).reset_index()
    m = cw.merge(cells, left_on=["g", "year"], right_on=["g", "t"])
    return by_e, int((cw.twfe_weight < 0).sum()), int(len(cw)), float((m.twfe_weight * m.att).sum())


def main():
    ov = {s: _csv(f"overall_{s}.csv").iloc[0].to_dict() for s in ("pop", "equal")}
    ev = {s: _csv(f"event_{s}.csv") for s in ("pop", "equal")}
    pre = {s: _csv(f"pretest_{s}.csv").iloc[0].to_dict() for s in ("pop", "equal")}
    tw = _csv("twfe.csv").set_index("spec")
    e1 = float(ev["pop"].set_index("e").loc[1, "att"])
    flags = red_flags(pre["pop"]["p"], ov["pop"]["att"], e1)

    d = main_window_frame()
    by_e, n_neg, n_cells, recon = twfe_vs_cs_weights(d)
    by_e.to_csv(RA / "twfe_vs_cs_weights.csv", index=False)

    cells = _csv("pretest_cells_pop.csv")
    honest = _csv("honestdid.csv") if (RA / "honestdid.csv").exists() else None
    breakdown = _csv("honestdid_breakdown.csv") if (RA / "honestdid_breakdown.csv").exists() else None
    sec_ov = _csv("secondary_overall.csv").iloc[0].to_dict() if (RA / "secondary_overall.csv").exists() else None

    payload = {
        "headline": {**ov["pop"], "label": "Overall ATT, CS, main window, population-weighted (pp)"},
        "equal_weights": ov["equal"],
        "twfe": tw.to_dict(orient="index"),
        "twfe_explained": {"weights_by_event_time": by_e.to_dict(orient="records"),
                           "negative_weights": n_neg, "treated_cells": n_cells,
                           "sum_w_times_attgt": recon},
        "cohort_att": {s: _csv(f"cohort_att_{s}.csv").to_dict(orient="records") for s in ("pop", "equal")},
        "cohort_sizes_state_years": _csv("main_cohort_sizes.csv").to_dict(orient="records"),
        "event_study": {s: ev[s].to_dict(orient="records") for s in ("pop", "equal")},
        "pretest": pre,
        "pretest_investigation": {
            "all_cells_test": _csv("pretest_allcells_pop.csv").iloc[0].to_dict(),
            "by_cohort": _csv("pretest_by_cohort_pop.csv").to_dict(orient="records"),
            "cells": cells.to_dict(orient="records"),
            "individually_significant": int((cells.z.abs() > 1.96).sum()),
            "n_cells": int(len(cells)),
        },
        "robustness": _csv("robustness.csv").assign(added="pre-specified").to_dict(orient="records")
                      + _csv("robustness_posthoc.csv").to_dict(orient="records"),
        "honestdid": None if honest is None else honest.to_dict(orient="records"),
        "honestdid_breakdown": None if breakdown is None else breakdown.to_dict(orient="records"),
        "benchmarks": BENCHMARKS, "benchmark_range_pp": list(RANGE),
        "e1": e1, "red_flags": flags,
        "secondary_overall": sec_ov,
    }
    save_results("step2_main", payload)
    return payload


if __name__ == "__main__":
    import json
    p = main()
    print(json.dumps({k: p[k] for k in ("headline", "red_flags", "e1")}, indent=1))
