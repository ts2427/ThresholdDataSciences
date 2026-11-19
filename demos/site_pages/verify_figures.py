r"""Verify every site figure CSV against results/*.json, value by value
(Tim, 2026-11-19). A figure is marked verified: true only if every value
matches; mismatches are returned for reporting.

Rounded estimates must match the JSON within half a unit of the rounding
(0.005 for two decimals, 0.05 for one); counts must match exactly.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT.parent / "content/data"


def _close(a, b, tol):
    return abs(float(a) - float(b)) <= tol + 1e-12


def check_event_study(csv, res):
    ev = pd.DataFrame(res["step2_main"]["event_study"]["pop"]).set_index("e")
    bad = []
    for r in csv.itertuples():
        e = int(r.year_relative_to_expansion)
        exp = ev.loc[e]
        exp_att = 0.0 if pd.isna(exp.att) else exp.att
        exp_lo = 0.0 if e == -1 else exp.lo
        exp_hi = 0.0 if e == -1 else exp.hi
        for col, want in (("estimate_pp", exp_att), ("ci95_low", exp_lo), ("ci95_high", exp_hi)):
            if not _close(getattr(r, col), want, 0.005):
                bad.append(f"event study e={e} {col}: csv {getattr(r, col)} vs json {want}")
    if sorted(csv.year_relative_to_expansion) != sorted(ev.index):
        bad.append("event study: event times differ from the JSON")
    return bad


def check_naive_vs_careful(csv, res):
    p, c = res["naive_vs_careful"]["point"], res["naive_vs_careful"]["ci95"]
    keys = ["naive_change", "comparison_change", "adjusted_change"]
    bad = []
    if len(csv) != 3:
        return ["naive vs careful: expected 3 rows"]
    for r, k in zip(csv.itertuples(), keys):
        checks = (("change_pp", p[k], 0.005), ("decline_pp", -p[k], 0.05),
                  ("ci95_low", c[k][0], 0.005), ("ci95_high", c[k][1], 0.005))
        for col, want, tol in checks:
            if not _close(getattr(r, col), want, tol):
                bad.append(f"naive vs careful {k} {col}: csv {getattr(r, col)} vs json {want}")
    return bad


def check_waterfall(csv, res):
    w = pd.DataFrame(res["final_tables"]["waterfall"])
    levels = w.employers_by_name.tolist()
    bad = []
    rows = csv.to_dict(orient="records")
    if [r["kind"] for r in rows] != ["start"] + ["step"] * (len(levels) - 1) + ["end"]:
        return ["waterfall: unexpected row kinds"]
    if int(rows[0]["value"]) != levels[0]:
        bad.append(f"waterfall start: csv {rows[0]['value']} vs json {levels[0]}")
    for i, r in enumerate(rows[1:-1], start=1):
        want = levels[i] - levels[i - 1]
        if int(r["value"]) != want:
            bad.append(f"waterfall step {r['step']}: csv {r['value']} vs json {want}")
        if int(r["employers_by_name_after"]) != levels[i]:
            bad.append(f"waterfall step {r['step']} level: csv {r['employers_by_name_after']} vs json {levels[i]}")
        if int(r["employers_by_name_and_state_after"]) != int(w.employers_by_name_and_state[i]):
            bad.append(f"waterfall step {r['step']} name+state: mismatch")
    if int(rows[-1]["value"]) != levels[-1]:
        bad.append(f"waterfall end: csv {rows[-1]['value']} vs json {levels[-1]}")
    return bad


CHECKS = {
    "medicaid-event-study.csv": ("medicaid_did.json", check_event_study),
    "medicaid-naive-vs-careful.csv": ("medicaid_did.json", check_naive_vs_careful),
    "osha-employer-waterfall.csv": ("osha_audit.json", check_waterfall),
}


def verify_all(data_dir=SITE_DATA, results_dir=ROOT / "results"):
    """{csv name: list of mismatches} for every site figure CSV."""
    out = {}
    for name, (jf, fn) in CHECKS.items():
        res = json.loads((Path(results_dir) / jf).read_text(encoding="utf-8"))
        out[name] = fn(pd.read_csv(Path(data_dir) / name), res)
    return out
