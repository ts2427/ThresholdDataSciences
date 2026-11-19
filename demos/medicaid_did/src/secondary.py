r"""Secondary analysis (docs/analysis_plan.md §3): 2009–2024, 2020 absent,
all cohorts, calendar-year event time. CONFOUNDED by the 2020–2023
continuous-enrollment requirement and the 2023–24 unwinding.

    .venv\Scripts\python -m medicaid_did.src.secondary

Inference: state-cluster bootstrap (resample states), 2000 draws, 95%
percentile intervals (a deviation from the multiplier bootstrap used in the
main analysis; see docs/decisions.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from medicaid_did.src.cs import (att_gt, cluster_bootstrap, cohort_sizes, dynamic,
                                 overall_group)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/demo_a"
E_RANGE = (-5, 10)


def prepare(panel):
    d = panel.copy()
    d["g"] = d["cohort"].astype(int)
    d["y"] = 100 * d["lowinc_rate"]
    d["w"] = d["lowinc_pop"]
    d["id"] = d["fips"].astype(int)
    return d[["id", "year", "g", "y", "w"]]


def estimates(d):
    cells = att_gt(d)
    dyn = dynamic(cells, d, e_range=E_RANGE).set_index("e")["att"]
    s = pd.Series({f"e{int(e)}": v for e, v in dyn.items()})
    s["overall"] = overall_group(cells, cohort_sizes(d))
    return s


def main(reps=2000):
    panel = pd.read_csv(ROOT / "data/processed/analysis_panel.csv", dtype={"fips": str})
    d = prepare(panel)
    point = estimates(d)
    cells = att_gt(d)
    dyn = dynamic(cells, d, e_range=E_RANGE)
    draws = cluster_bootstrap(d, estimates, reps=reps)
    lo, hi = draws.quantile(0.025), draws.quantile(0.975)
    ev = dyn.assign(lo=[lo.get(f"e{int(e)}", np.nan) for e in dyn.e],
                    hi=[hi.get(f"e{int(e)}", np.nan) for e in dyn.e],
                    se_boot=[draws[f"e{int(e)}"].std() for e in dyn.e])
    # calendar event times with no observation are listed explicitly as gaps
    full = pd.DataFrame({"e": range(E_RANGE[0], E_RANGE[1] + 1)})
    ev = full.merge(ev, on="e", how="left")
    ev.to_csv(OUT / "secondary_event.csv", index=False)
    cells.to_csv(OUT / "secondary_attgt.csv", index=False)
    pd.DataFrame([{"att": point["overall"], "lo": lo["overall"], "hi": hi["overall"],
                   "se_boot": draws["overall"].std(), "reps": reps}]).to_csv(
        OUT / "secondary_overall.csv", index=False)
    return ev, point


if __name__ == "__main__":
    ev, point = main()
    print(ev.round(2).to_string(index=False))
    print("overall", round(point["overall"], 2))
