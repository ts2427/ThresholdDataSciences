"""Step 10, chapter 3 (peak outages): helpers."""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")


def panel(*rows):
    """rows: (storm_key, doc_id, days, fips, served, out)"""
    return pd.DataFrame([{"storm_key": k, "storm": k, "doc_id": d, "report_date": f"2024-09-{20 + int(t):02d}",
                          "days_since_landfall": t, "fips": f, "sites_served": s, "sites_out": o,
                          "cable_wireline_subs_out": 100.0, "area_includes_out_of_scope": False,
                          "report_shared_by_storms": False, "report_status": "flagged", "report_flags": "",
                          "landfall_source": "HURDAT2", "rule_period": "P1"} for k, d, t, f, s, o in rows])


P = panel(("H", "D1", 0.4, "a", 100, 10), ("H", "D1", 0.4, "b", 100, 30),
          ("H", "D2", 1.4, "a", 100, 40), ("H", "D2", 1.4, "b", 100, 20),
          ("H", "D3", 2.4, "a", 100, 5), ("H", "D3", 2.4, "b", 100, 5))


def test_report_totals_sum_counties():
    t = step10.report_totals(P)
    assert t.sites_out.tolist() == [40, 60, 10] and t.sites_served.tolist() == [200, 200, 200]
    assert t.n_counties.tolist() == [2, 2, 2]


def test_peak_is_the_report_with_most_sites_out_and_its_percent():
    pk = step10.peak_report(step10.report_totals(P))
    assert pk.doc_id == "D2" and pk.sites_out == 60 and pk.pct_out == pytest.approx(30.0)


def test_peak_tie_goes_to_the_earlier_report():
    t = step10.report_totals(panel(("H", "D1", 0.4, "a", 10, 5), ("H", "D2", 1.4, "a", 10, 5)))
    assert step10.peak_report(t).doc_id == "D1"


def test_peak_timing_is_bounded_by_neighbouring_snapshots():
    t = step10.report_totals(P)
    assert step10.peak_timing_interval(t, step10.peak_report(t)) == (0.4, 2.4)


def test_peak_timing_at_the_first_report_has_no_lower_bound():
    t = step10.report_totals(P[P.doc_id != "D1"].assign(sites_out=lambda x: np.where(x.doc_id == "D2", 50, 1)))
    lo, hi = step10.peak_timing_interval(t, step10.peak_report(t))
    assert lo is None and hi == 2.4


def test_county_bootstrap_brackets_the_estimate_and_is_reproducible():
    a = step10.bootstrap_peak(P, draws=500, seed=1)
    b = step10.bootstrap_peak(P, draws=500, seed=1)
    assert np.array_equal(a["sites_out"], b["sites_out"])
    lo, hi = np.percentile(a["pct_out"], [2.5, 97.5])
    assert lo <= 30.0 <= hi
    # resampling two counties: peak count lies between 2x the smallest and 2x the largest county peak
    assert a["sites_out"].min() >= 40 and a["sites_out"].max() <= 80


def test_county_missing_from_a_report_adds_nothing_to_it():
    p = panel(("H", "D1", 0.4, "a", 100, 10), ("H", "D2", 1.4, "a", 100, 20), ("H", "D2", 1.4, "b", 50, 50))
    t = step10.report_totals(p)
    assert t.sites_served.tolist() == [100, 150]
    draws = step10.bootstrap_peak(p, draws=50, seed=0)
    assert np.isfinite(draws["pct_out"]).all()


def test_number_record_keeps_value_interval_count_and_method():
    n = step10.num(12.3456, 10.0, 15.0, n=42, unit="% of sites served", method="county bootstrap")
    assert n == {"value": 12.3456, "ci_low": 10.0, "ci_high": 15.0, "n": 42, "unit": "% of sites served",
                 "method": "county bootstrap"}
    json.dumps(n)


def test_median_across_storms_has_a_storm_bootstrap_interval_and_range():
    m = step10.median_across([1.0, 2.0, 3.0, 10.0], draws=500, seed=0, unit="%")
    assert m["value"] == 2.5 and m["min"] == 1.0 and m["max"] == 10.0 and m["n"] == 4
    assert m["ci_low"] <= 2.5 <= m["ci_high"]


def test_results_file_keeps_other_chapters(tmp_path):
    f = tmp_path / "results.json"
    f.write_text(json.dumps({"chapter_2": {"x": 1}}), encoding="utf-8")
    step10.write_chapter(f, "chapter_3", {"y": 2})
    assert json.loads(f.read_text(encoding="utf-8")) == {"chapter_2": {"x": 1}, "chapter_3": {"y": 2}}


def test_drop_one_storm_medians():
    got = step10.drop_one_medians({"A": 1.0, "B": 2.0, "C": 3.0, "D": 10.0})
    assert got == {"A": 3.0, "B": 3.0, "C": 2.0, "D": 2.0}


def test_reports_used_without_flagged_keep_ok_and_known_only():
    p = P.assign(report_status=lambda x: x.doc_id.map({"D1": "ok", "D2": "flagged", "D3": "known_fcc_inconsistency"}))
    assert sorted(step10.without_flagged(p).doc_id.unique()) == ["D1", "D3"]


# --- serious vs benign flags (deviation 5b, 2026-11-22) ---

@pytest.mark.parametrize("flags, serious", [
    ("84 rows short of sites out (12 sites unattributed); FCC spelling: Tennessee/Unicoi listed as Unicorn", False),
    ("causes exceed sites out, confirmed by second reading: Louisiana/ASCENSION by 3; 2 rows inside_spelling_variant", False),
    ("listed more than once by the FCC: Virginia/Franklin; causes exceed sites out, listed exception: X by 1", False),
    ("headline 21.7% vs 14.49% from the report's own totals", False),
    ("headline_mismatch: stated 5.60, computed 12.10 (computed used)", True),
    ("state_total_missing: Georgia (its rows all confirmed; other states reconcile)", True),
    ("no_printed_totals: the report prints no totals; every row confirmed by second reading", True),
    ("3 rows outside_notice_area", True),
    ("2 rows table_not_in_list; in table, not in the report's county list: Florida/Broward", True),
    ("", False),
])
def test_serious_flags(flags, serious):
    assert step10.has_serious_flag(flags) is serious


def test_unknown_flag_type_stops():
    with pytest.raises(ValueError, match="unknown flag"):
        step10.has_serious_flag("something new happened")


def test_without_serious_drops_only_serious_reports():
    p = P.assign(report_flags=lambda x: x.doc_id.map({"D1": "3 rows outside_notice_area", "D2": "FCC spelling: a", "D3": ""}))
    assert sorted(step10.without_serious(p).doc_id.unique()) == ["D2", "D3"]


def test_page_notes_are_generated_from_the_data():
    storms = [{"storm": "Laura", "excluded_reports": "DOC-1 (2020-08-28): x; DOC-2 (2020-08-29): y; D3 (2020-08-30): z",
               "n_counties": 325,
               "peak_report_date": "2020-08-27"},
              {"storm": "Beryl", "excluded_reports": "", "n_counties": 6, "peak_report_date": "2024-07-09"}]
    notes = step10.chapter_3_page_notes(storms, small_county_storms=("Beryl",), understated_storms=("Laura",))
    assert notes["Laura"] == ("Laura's peak may be understated: its reports of 2020-08-28, 2020-08-29 and 2020-08-30, "
                              "after the peak report of 2020-08-27, are excluded.")
    assert notes["Beryl"] == "Beryl's peak share comes from 6 counties."
