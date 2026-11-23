"""Step 10, chapter 4 (recovery): helpers."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")


# --- the rebound rule ---

def test_stays_past_threshold_from_that_report_on():
    # crosses 50% at index 1, falls back at 2, then stays from 3
    assert step10.stay_index([0.0, 0.6, 0.4, 0.55, 0.7], 0.5) == 3


def test_first_crossing_for_the_sensitivity_display():
    assert step10.first_index([0.0, 0.6, 0.4, 0.55, 0.7], 0.5) == 1


def test_never_staying_is_censored():
    assert step10.stay_index([0.0, 0.6, 0.4], 0.5) is None
    assert step10.first_index([0.0, 0.2], 0.5) is None


def test_below_threshold_direction_for_percent_out():
    # waiting time: below 5% out and staying below
    assert step10.stay_index([20.0, 4.0, 6.0, 3.0, 2.0], 5.0, below=True) == 3


def test_stay_index_matrix_matches_the_scalar_version():
    m = np.array([[0.0, 0.6, 0.4, 0.55, 0.7], [0.0, 0.2, 0.3, 0.4, 0.45], [0.0, 0.9, 0.95, 0.99, 1.0]])
    assert step10.stay_index_rows(m, 0.5).tolist() == [3, -1, 1]


# --- the storm curve ---

def panel(rows):
    """rows: (doc_id, days_since_landfall, fips, served, out)"""
    return pd.DataFrame([{"storm_key": "K", "storm": "K", "doc_id": d, "report_date": f"2024-09-{20 + int(t):02d}",
                          "days_since_landfall": t, "fips": f, "sites_served": s, "sites_out": o,
                          "cable_wireline_subs_out": None, "area_includes_out_of_scope": False,
                          "report_shared_by_storms": False, "report_status": "ok", "report_flags": ""}
                         for d, t, f, s, o in rows])


P = panel([("D0", 0.0, "a", 100, 10), ("D0", 0.0, "b", 100, 10),
           ("D1", 1.0, "a", 100, 60), ("D1", 1.0, "b", 100, 40),     # peak: 100 out
           ("D2", 2.0, "a", 100, 30), ("D2", 2.0, "b", 100, 30),     # 40% restored
           ("D3", 3.0, "a", 100, 10),                                 # b missing: carried at 30 -> 60% (best 90%)
           ("D4", 5.0, "a", 100, 0), ("D4", 5.0, "b", 100, 5)])      # 95% restored


def test_curve_starts_at_the_peak_and_carries_absent_counties():
    c = step10.recovery_curve(P)
    assert c.days_since_peak.tolist() == [0.0, 1.0, 2.0, 4.0]
    assert c.sites_out.tolist() == [100, 60, 40, 5]
    assert c.restored_share.tolist() == pytest.approx([0.0, 0.4, 0.6, 0.95])
    assert c.restored_share_best.tolist() == pytest.approx([0.0, 0.4, 0.9, 0.95])
    assert c.n_carried.tolist() == [0, 0, 1, 0]


def test_counties_first_listed_after_the_peak_are_left_out():
    extra = panel([("D2", 2.0, "z", 50, 5)])  # small enough that D1 stays the peak
    c = step10.recovery_curve(pd.concat([P, extra], ignore_index=True))
    assert c.sites_out.tolist() == [100, 60, 40, 5]


def test_time_to_threshold_with_its_interval():
    c = step10.recovery_curve(P)
    t = step10.time_to(c, 0.5, "restored_share")
    assert (t["value"], t["interval_low"], t["censored"]) == (2.0, 1.0, False)
    t90 = step10.time_to(c, 0.9, "restored_share")
    assert (t90["value"], t90["interval_low"]) == (4.0, 2.0)
    assert step10.time_to(c, 0.9, "restored_share_best")["value"] == 2.0


def test_not_reached_is_right_censored_at_the_last_report():
    c = step10.recovery_curve(P[P.doc_id != "D4"])
    t = step10.time_to(c, 0.9, "restored_share")
    assert t["value"] is None and t["censored"] and t["censored_at"] == 2.0


def test_site_days_lost_trapezoid_and_bounds():
    c = step10.recovery_curve(P)
    s = step10.site_days_lost(c)
    # out: 100, 60, 40, 5 at days 0, 1, 2, 4
    assert s["value"] == pytest.approx(80 + 50 + 45)
    assert s["upper"] == pytest.approx(100 + 60 + 80) and s["lower"] == pytest.approx(60 + 40 + 10)
    assert s["gaps_over_one_day"] == 1


def test_bootstrap_times_bracket_and_reproduce():
    a = step10.bootstrap_recovery(P, draws=300, seed=3)
    b = step10.bootstrap_recovery(P, draws=300, seed=3)
    assert np.array_equal(a["t50"], b["t50"], equal_nan=True)
    assert set(np.unique(a["t50"][np.isfinite(a["t50"])])) <= {1.0, 2.0, 4.0}
    assert a["share"].shape == (300, 4)


def test_censored_aware_median_across_storms():
    assert step10.median_with_censoring([1.0, 2.0, 3.0], [False, False, False]) == 2.0
    assert step10.median_with_censoring([1.0, 2.0, 9.0], [False, False, True]) == 2.0
    assert step10.median_with_censoring([1.0, 9.0, 9.0], [False, True, True]) is None



def test_storms_reaching_a_threshold_under_both_bounds():
    storms = [{"storm": "A", "time_to_90pct_restored": {"censored": False, "best_case_censored": False}},
              {"storm": "B", "time_to_90pct_restored": {"censored": True, "best_case_censored": False}},
              {"storm": "C", "time_to_90pct_restored": {"censored": True, "best_case_censored": True}}]
    got = step10.storms_reaching(storms, "90")
    assert (got["value"], got["min"], got["max"], got["n"]) == ("1 to 2", 1, 2, 3)
    assert got["counties_leaving_stay_out"] == ["A"] and got["counties_leaving_restored"] == ["A", "B"]



def test_median_is_given_only_when_censoring_cannot_move_it():
    # Barry-like storm censored at day 1 must not count as slower than Michael's 12 days
    assert step10.median_with_censoring([1.0, 1.0, 12.0], [False, True, False]) is None
    assert step10.median_with_censoring([2.0, 3.0, 9.0], [False, False, True]) == 3.0


def test_storms_without_a_report_after_the_peak_are_left_out_of_time_summaries():
    per = [{"storm": "A", "n_reports_after_peak": 3}, {"storm": "Nicole", "n_reports_after_peak": 0}]
    assert [r["storm"] for r in step10.recovery_observed(per)] == ["A"]
    assert step10.NO_RECOVERY_NOTE.format(storm="Nicole") == "Nicole: no report after its peak, so no recovery could be observed."


def test_time_flagged_reports_are_left_out_of_time_based_results():
    p = pd.DataFrame({"doc_id": ["A", "B"], "time_flag": ["pre_onset_likely_marco", ""], "storm": ["Laura"] * 2,
                      "report_date": ["2020-08-25", "2020-08-26"], "days_since_landfall": [-0.9, 0.1]})
    assert list(step10.timed(p).doc_id) == ["B"]
    assert step10.time_flagged_reports(p)[0]["flag"] == "pre_onset_likely_marco"
