"""Step 9: panel helpers."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step9 = importlib.import_module("09_build_panel")
UTC = "UTC"


@pytest.mark.parametrize("date, code", [("2018-10-09", "P0"), ("2024-04-30", "P0"), ("2024-05-01", "P1"),
                                        ("2025-02-19", "P1"), ("2025-02-20", "P2"), ("2026-06-30", "P3"),
                                        ("2026-10-08", "P3")])
def test_rule_period_from_activation_date(date, code):
    assert step9.rule_period(date)[0] == code


def test_storm_landfall_is_the_earliest_nearest_landfall():
    # Harvey: Texas counties' nearest landfall is Aug 26, not the Barbados landfall of Aug 18
    ex = pd.DataFrame({"nhc_id": ["H"] * 3, "fips": ["a", "b", "c"], "min_dist_km": [5.0, 50.0, 90.0],
                       "closest_utc": pd.to_datetime(["2017-08-26 02:00"] * 3, utc=True),
                       "nearest_landfall_utc": pd.to_datetime(["2017-08-26 03:00", "2017-08-26 06:00",
                                                               "2017-08-26 03:00"], utc=True)})
    got = step9.storm_landfall(ex).iloc[0]
    assert got.landfall_utc == pd.Timestamp("2017-08-26 03:00", tz=UTC) and got.landfall_source == "HURDAT2"


def test_no_landfall_marker_uses_closest_approach_to_the_nearest_county():
    ex = pd.DataFrame({"nhc_id": ["I"] * 2, "fips": ["a", "b"], "min_dist_km": [30.0, 4.0],
                       "closest_utc": pd.to_datetime(["2026-10-09 22:00", "2026-10-10 00:15"], utc=True),
                       "nearest_landfall_utc": pd.NaT})
    got = step9.storm_landfall(ex).iloc[0]
    assert got.landfall_utc == pd.Timestamp("2026-10-10 00:15", tz=UTC)
    assert got.landfall_source == "closest approach (no landfall marker)"


def test_missing_as_of_is_noon_eastern_and_flagged():
    r = pd.DataFrame({"report_date": ["2020-09-01", "2020-08-31"],
                      "as_of_utc": [None, "2020-08-31T15:00:00+00:00"]})
    got = step9.fill_as_of(r)
    assert got.as_of_utc.tolist() == [pd.Timestamp("2020-09-01 16:00", tz=UTC), pd.Timestamp("2020-08-31 15:00", tz=UTC)]
    assert got.as_of_imputed.tolist() == [True, False]


def panel_rows(*rows):
    return pd.DataFrame([{"storm_key": "K", "fips": f, "report_date": d, "sites_out": o} for f, d, o in rows])


def test_censoring_left_reports_while_out_and_out_at_last_report():
    p = panel_rows(("a", "2024-09-27", 5), ("a", "2024-09-28", 2),           # leaves the reports while out
                   ("b", "2024-09-27", 5), ("b", "2024-09-28", 0), ("b", "2024-09-29", 0),  # recovered
                   ("c", "2024-09-27", 1), ("c", "2024-09-29", 3))           # still out at the last report
    got = step9.county_spans(p).set_index("fips")
    assert got.loc["a", "censoring"] == "left_reports_while_out"
    assert got.loc["b", "censoring"] == "none"
    assert got.loc["c", "censoring"] == "out_at_last_report"
    assert got.loc["c", "n_reports"] == 2 and got.loc["c", "first_report_date"] == "2024-09-27"


def test_cable_figure_flagged_when_the_report_area_had_out_of_scope_states():
    allrows = pd.DataFrame({"doc_id": ["D1", "D1", "D2"], "state": ["Louisiana", "Arkansas", "Louisiana"]})
    got = step9.report_area_flags(allrows, ["Louisiana"])
    assert got.set_index("doc_id").area_includes_out_of_scope.to_dict() == {"D1": True, "D2": False}


def test_public_csv_has_dirs_fields_and_carried_columns_only():
    assert {"out_unattributed", "out_overattributed", "sites_served", "fips"} <= set(step9.PUBLIC_COLUMNS)
    assert not any(c.startswith(("eaglei", "svi", "acs", "min_dist")) for c in step9.PUBLIC_COLUMNS)
    assert [c for c in step9.PUBLIC_COLUMNS if c.startswith("fema")] == ["fema_declared"]  # context only (2026-11-22)


def test_every_report_before_day0_must_carry_a_time_flag():
    p = pd.DataFrame({"doc_id": ["A", "B"], "days_since_landfall": [-0.9, 1.0], "time_flag": ["", ""]})
    with pytest.raises(SystemExit):
        step9.check_time_flags(p)
    p.loc[0, "time_flag"] = "pre_onset_likely_marco"
    p.loc[0, "doc_id"] = "DOC-366394A1"
    step9.check_time_flags(p)  # flagged: passes
