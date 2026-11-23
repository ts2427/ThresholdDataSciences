"""Step 10, chapter 9 (rule periods, descriptive): helpers and red-flag checks."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")


def storms(*rows):
    """rows: (storm, period, t50, t50_cens, t90, t90_cens, t90_best, t90_best_cens, activation)"""
    return pd.DataFrame([{"storm": s, "rule_period": p, "t50": a, "t50_censored": ac, "t90": b, "t90_censored": bc,
                          "t90_best": c, "t90_best_censored": cc, "dirs_activation_date": d, "censored_at": 30.0}
                         for s, p, a, ac, b, bc, c, cc, d in rows])


S = storms(("A", "P0", 3.0, False, 10.0, False, 8.0, False, "2017-08-25"),
           ("B", "P0", 4.0, False, 12.0, False, 9.0, False, "2018-10-09"),
           ("C", "P0", 2.0, False, 9.0, False, 7.0, False, "2020-08-24"),
           ("D", "P1", 2.0, False, 6.0, False, 5.0, False, "2024-07-08"),
           ("E", "P1", 1.0, False, 5.0, False, 4.0, False, "2024-09-25"),
           ("F", "P3", 1.0, False, 4.0, False, 3.0, False, "2026-10-08"))


def test_period_medians_and_ranges():
    got = step10.period_summary(S, "t50", "t50_censored")
    assert got["P0"]["median"] == 3.0 and got["P0"]["min"] == 2.0 and got["P0"]["max"] == 4.0 and got["P0"]["n_storms"] == 3
    assert got["P3"]["n_storms"] == 1 and got["P3"]["storm"] == "F"
    assert got["P2"] == {"n_storms": 0, "note": "no storm in this period"}


def test_order_of_periods():
    assert step10.period_order(step10.period_summary(S, "t50", "t50_censored")) == ["P1", "P3", "P0"] or \
        step10.period_order(step10.period_summary(S, "t50", "t50_censored")) == ["P3", "P1", "P0"]


def test_red_flag_1_one_storm_period_is_triggered():
    rf = step10.red_flag_drop_one(S)
    assert rf["triggered"] and "P3" in rf["reason"]


def test_red_flag_1_not_triggered_when_order_is_robust():
    s = S[S.rule_period != "P3"]
    assert not step10.red_flag_drop_one(s)["triggered"]


def test_red_flag_2_triggered_when_50_and_90_disagree():
    s = S[S.rule_period != "P3"].copy()
    s.loc[s.storm == "D", "t90"] = 40.0  # P1's 90% median now above P0's
    s.loc[s.storm == "E", "t90"] = 40.0
    assert step10.red_flag_measure_dependence(s)["triggered"]
    assert not step10.red_flag_measure_dependence(S[S.rule_period != "P3"])["triggered"]


def test_red_flag_2_triggered_when_a_median_is_not_estimable_under_one_treatment():
    s = S[S.rule_period != "P3"].copy()
    s.loc[s.storm.isin(["D", "E"]), "t90_censored"] = True
    assert step10.red_flag_measure_dependence(s)["triggered"]


def test_red_flag_3_prior_trend_within_p0():
    s = storms(("A", "P0", 6.0, False, 1, False, 1, False, "2017-01-01"), ("B", "P0", 6.0, False, 1, False, 1, False, "2018-01-01"),
               ("C", "P0", 3.0, False, 1, False, 1, False, "2021-01-01"), ("D", "P0", 3.0, False, 1, False, 1, False, "2022-01-01"),
               ("E", "P1", 2.0, False, 1, False, 1, False, "2024-07-01"))
    assert step10.red_flag_prior_trend(s)["triggered"]  # P0 fell 3 days; P0 to P1 fell 2.5
    flat = s.assign(t50=[4.0, 4.0, 4.0, 4.0, 2.0])
    assert not step10.red_flag_prior_trend(flat)["triggered"]


def test_red_flag_4_within_storm_denominator_moves():
    p = pd.DataFrame({"storm_key": "K", "storm": "K", "fips": ["a", "a", "b", "b"], "doc_id": ["D1", "D2", "D1", "D2"],
                      "sites_served": [100, 100, 100, 125], "dirs_activation_date": "2024-07-08", "rule_period": "P1"})
    rf = step10.red_flag_denominators(p)
    assert rf["within_storm"]["K"] == pytest.approx(225 / 200) and rf["triggered"]


def test_red_flag_5_activation_ends_by_period():
    s = pd.DataFrame({"storm": list("ABCDEF"), "rule_period": ["P0", "P0", "P0", "P1", "P1", "P3"],
                      "days_peak_to_last": [10.0, 12.0, 9.0, 3.0, 2.0, 2.0], "still_out_share_at_last": [0.1] * 6})
    rf = step10.red_flag_activation_ends(s)
    assert rf["triggered"] and "days from peak to last report" in rf["reason"]


def test_red_flag_6_no_overlap():
    s = pd.DataFrame({"storm": list("ABC"), "rule_period": ["P0", "P0", "P1"], "max_wind_kt": [100.0, 120.0, 60.0],
                      "peak_pct_out": [10.0, 20.0, 15.0]})
    rf = step10.red_flag_overlap(s)
    assert rf["triggered"] and "strongest wind" in rf["reason"] and "peak % out" not in rf["reason"]


def test_wording_rule():
    assert step10.ch9_wording({"a": {"triggered": True}, "b": {"triggered": False}})["coincided_wording_allowed"] is False
    assert step10.ch9_wording({"a": {"triggered": False}})["coincided_wording_allowed"] is True



def test_page_headline_is_generated_from_the_period_counts_and_the_largest_move():
    by_period = {"P0": {"n_storms": 15}, "P1": {"n_storms": 5}, "P2": {"n_storms": 0}, "P3": {"n_storms": 1, "storm": "Isaias"}}
    flag4 = {"within_storm": {"a": 1.12, "b": 1.31, "c": None}}
    s = step10.ch9_headline(by_period, flag4)
    assert s == ("The public reports can't yet show whether the FCC's 2024–2025 rules coincided with any change in recovery: "
                 "one rule period has no storm, another has only Isaias, and the sites-served counts shift within storms "
                 "by as much as 31%.")



def test_period_ranges_cover_observed_times_only():
    s = S.copy()
    s.loc[s.storm == "B", ["t50_censored"]] = True  # B censored at 30: out of the range, counted apart
    got = step10.period_summary(s, "t50", "t50_censored")["P0"]
    assert (got["min"], got["max"], got["n_observed"], got["n_censored"]) == (2.0, 3.0, 2, 1)
    assert got["median"] == 3.0  # 3, 2 and B censored at 30: the median is 3 either way, so it is identified
    s.loc[s.storm == "B", "censored_at"] = 1.0  # censored at day 1: the median now depends on B's unknown time
    assert step10.period_summary(s, "t50", "t50_censored")["P0"]["median"] is None


def test_red_flag_1_reason_reads_as_text():
    rf = step10.red_flag_drop_one(S)
    assert "['" not in rf["reason"] and "None" not in rf["reason"] and "t50" not in rf["reason"]
    s = S[S.rule_period != "P3"].copy()
    s.loc[s.storm == "C", "t50"] = 6.0  # P0 now 3, 4, 6 -> median 4; drop B -> 3 and 6 ...
    s.loc[s.storm == "D", "t50"] = 3.5
    got = step10.red_flag_drop_one(s)["reason"]
    assert "the order of period medians changes from" in got or got == ""
