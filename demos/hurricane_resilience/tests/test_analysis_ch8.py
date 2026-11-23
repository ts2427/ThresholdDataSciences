"""Step 10, chapter 8 (waiting time by SVI quartile): helpers."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")

STORM_DAYS = [0.5, 1.5, 2.5, 3.5, 4.5]


def test_waiting_event_by_the_rebound_rule():
    # at or above 5% from 0.5; dips below at 2.5, back up at 3.5, stays below from 4.5
    w = step10.waiting_record([0.5, 1.5, 2.5, 3.5, 4.5], [0.30, 0.10, 0.04, 0.06, 0.01], STORM_DAYS)
    assert (w["start"], w["event"], w["time"], w["interval_low"]) == (0.5, True, 4.5, 3.5)
    assert w["first_crossing_time"] == 2.5


def test_county_never_at_5_percent_is_not_at_risk():
    assert step10.waiting_record([0.5, 1.5], [0.02, 0.0], STORM_DAYS) is None


def test_leaving_the_reports_while_out_is_censored_with_best_and_worst_cases():
    w = step10.waiting_record([0.5, 1.5], [0.30, 0.20], STORM_DAYS)
    assert (w["event"], w["time"], w["censoring"]) == (False, 1.5, "left_reports_while_out")
    assert (w["best_event"], w["best_time"]) == (True, 2.5)    # reaches below 5% at the next unreported report
    assert (w["worst_event"], w["worst_time"]) == (False, 4.5)  # stays at risk to the storm's last report


def test_still_out_at_the_storms_last_report():
    w = step10.waiting_record([0.5, 4.5], [0.30, 0.20], STORM_DAYS)
    assert w["censoring"] == "out_at_last_report" and w["best_event"] is False and w["worst_time"] == 4.5


def test_person_periods_cover_report_intervals_with_the_event_in_the_last():
    w = step10.waiting_record([0.5, 1.5, 2.5, 3.5, 4.5], [0.30, 0.10, 0.04, 0.06, 0.01], STORM_DAYS)
    pp = step10.person_periods(w)
    assert [(r["t0"], r["t1"], r["event"]) for r in pp] == [(0.5, 1.5, 0), (1.5, 2.5, 0), (2.5, 3.5, 0), (3.5, 4.5, 1)]


def test_person_periods_for_the_best_case_add_the_unreported_interval():
    w = step10.waiting_record([0.5, 1.5], [0.30, 0.20], STORM_DAYS)
    assert [(r["t0"], r["t1"], r["event"]) for r in step10.person_periods(w, case="best")] == [(0.5, 1.5, 0), (1.5, 2.5, 1)]
    assert [(r["t0"], r["t1"], r["event"]) for r in step10.person_periods(w, case="worst")][-1] == (1.5, 4.5, 0)


def test_sample_quartiles_split_evenly_and_national_cuts_are_fixed():
    svi = pd.Series(np.linspace(0.6, 1.0, 40))
    q, cuts = step10.svi_quartiles(svi, scale="sample")
    assert q.value_counts().tolist() == [10, 10, 10, 10] and len(cuts) == 3
    qn, cn = step10.svi_quartiles(svi, scale="national")
    assert cn == [0.25, 0.5, 0.75] and set(qn) == {"Q3", "Q4 (most)"}


def test_kaplan_meier_median_and_share_by_day():
    times = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    events = np.array([True, True, False, True, True])
    km = step10.kaplan_meier(times, events)
    assert step10.km_median(km) == 4.0  # S drops 0.8, 0.6, (censor), 0.3 at t=4
    assert step10.km_share_by(km, 2.0) == pytest.approx(0.4)


def test_cloglog_hazard_recovers_a_known_hazard_ratio():
    rng = np.random.default_rng(0)
    rows = []
    for c in range(1500):
        storm = f"S{c % 5}"
        q = ["Q1 (least)", "Q2", "Q3", "Q4 (most)"][c % 4]
        log_hr = {"Q1 (least)": 0.0, "Q2": 0.0, "Q3": 0.0, "Q4 (most)": np.log(0.5)}[q]
        t = 0.0
        while t < 30:
            dt = 1.0
            p = 1 - np.exp(-np.exp(-1.5 + log_hr + (0.2 if storm == "S1" else 0.0)) * dt)
            ev = rng.random() < p
            rows.append({"fips": f"{c:05d}", "storm_key": storm, "t0": t, "t1": t + dt, "event": int(ev), "svi_q": q,
                         "zone": "34-50 kt", "min_dist_km": 50.0 + c % 7, "wind_kt_at_closest": 80.0 + c % 3})
            t += dt
            if ev:
                break
    fit, names = step10.fit_waiting_hazard(pd.DataFrame(rows))
    assert np.exp(fit.params["svi_Q4 (most)"]) == pytest.approx(0.5, abs=0.1)
    assert np.exp(fit.params["svi_Q2"]) == pytest.approx(1.0, abs=0.2)


def test_first_crossing_frame_skips_counties_that_never_cross():
    # in a DataFrame a missing crossing time is NaN, not None (Isaias-like county still out at the end)
    recs = pd.DataFrame([{**step10.waiting_record([0.5, 1.5], [0.3, 0.2], STORM_DAYS), "storm_key": "K", "fips": "a",
                          "svi_q": "Q1 (least)", "zone": "34-50 kt", "min_dist_km": 10.0, "wind_kt_at_closest": 80.0},
                         {**step10.waiting_record([0.5, 1.5, 2.5], [0.3, 0.01, 0.0], STORM_DAYS), "storm_key": "K",
                          "fips": "b", "svi_q": "Q2", "zone": "34-50 kt", "min_dist_km": 10.0, "wind_kt_at_closest": 80.0}])
    pp = step10._pp_frame(recs, first_crossing=True)
    assert pp.groupby("fips").event.sum().to_dict() == {"a": 0, "b": 1}



def test_headline_bound_is_generated_from_the_q4_interval():
    hr = {"value": 1.16, "ci_low": 0.91, "ci_high": 1.47}
    s = step10.ch8_bound_sentence(hr)
    assert "0.91" in s and "1.47" in s and "9%" in s and "47% higher" in s
    for word in ("because", "neglect", "priorit"):
        assert word not in s.lower()


def test_best_case_is_labelled_a_sensitivity_and_its_disappearance_stated():
    best = {"svi_Q3": {"value": 1.38, "ci_low": 1.09, "ci_high": 1.76}, "svi_Q4 (most)": {"value": 1.36, "ci_low": 1.08, "ci_high": 1.71}}
    worst = {"svi_Q3": {"value": 1.04, "ci_low": 0.84, "ci_high": 1.28}, "svi_Q4 (most)": {"value": 1.05, "ci_low": 0.84, "ci_high": 1.32}}
    s = step10.ch8_best_case_sentence({"hazard_ratios": best}, {"hazard_ratios": worst})
    assert s.startswith("Sensitivity display") and "1.38" in s and "1.05" in s and "disappears" in s



def test_chapter_8_headline_carries_the_generated_bound():
    s = step10.ch8_headline({"value": 1.16, "ci_low": 0.91, "ci_high": 1.47})
    assert s.startswith("In this data, counties with higher social vulnerability did not take measurably longer")
    assert "(a rate of recovery more than 9% slower)" in s



def test_bound_rounding_is_never_stronger_than_the_interval():
    assert step10.ruled_out_pct(0.8953) == 11      # 10.47% slower is the edge: "more than 11%" is outside it
    assert step10.ruled_out_pct(0.91) == 9         # exact edge stays
    assert step10.not_ruled_out_pct(1.455) == 45   # 45.5% faster is the edge: "up to 45%" is inside it


def test_irls_divergence_is_detected():
    class F:
        converged, params = True, np.array([0.1, 2e14])
    assert not step10.irls_ok(F())
    F.params = np.array([0.1, -1.2])
    assert step10.irls_ok(F())


def test_worst_case_sentence_when_not_estimable():
    hr = {"value": 1.2, "ci_low": 1.0, "ci_high": 1.4}
    best = {"hazard_ratios": {"svi_Q3": hr, "svi_Q4 (most)": hr}}
    s = step10.ch8_best_case_sentence(best, {"error": "NotEstimable: x", "error_reason": "no finite maximum"})
    assert "not estimable under the worst-case assumption: no finite maximum" in s and "inf" not in s
