"""Reporting areas over time, the area check, per-state start dates and the Nicholas key."""
import importlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from notices import Op  # noqa: E402

areas = importlib.import_module("02b_reporting_areas")


def notice(date, doc, *ops):
    return {"date": pd.Timestamp(date), "doc_id": doc, "ops": list(ops)}


IDA = [
    notice("2021-08-29", "A1", Op("add", "Louisiana", ["Acadia", "Point Coupee", "Lafourche"]),
           Op("add", "Mississippi", ["Adams"])),
    notice("2021-09-03", "A2", Op("remove", "Mississippi", ["Adams"])),
    notice("2021-09-14", "N1", Op("add", "Louisiana", ["Acadia", "Pointe Coupee", "Cameron"]),
           Op("add", "Texas", ["Harris"])),
    notice("2021-09-16", "A3", Op("remain", "Louisiana", ["Lafourche"])),
    notice("2021-09-20", "A4", Op("end", "*", [])),
]


def test_intervals_from_add_remove_remain_and_end():
    got = areas.build_intervals(IDA)
    acadia = got[(got.state == "Louisiana") & (got.county == "Acadia")].iloc[0]
    assert (acadia.added_by, acadia.removed_by) == ("A1", "A3")
    adams = got[got.county == "Adams"].iloc[0]
    assert (adams.added_on, adams.removed_on) == (pd.Timestamp("2021-08-29"), pd.Timestamp("2021-09-03"))
    lafourche = got[got.county == "Lafourche"].iloc[0]
    assert lafourche.removed_by == "A4"


def test_fcc_misspelling_matches_the_same_county():
    got = areas.build_intervals(IDA)
    coupee = got[got.county.str.contains("Coupee")]
    assert len(coupee) == 1 and coupee.iloc[0].spellings == "Point Coupee; Pointe Coupee"


def test_area_on_a_date_counts_notices_released_that_day_both_ways():
    got = areas.build_intervals(IDA)
    before, through = areas.area_on(got, pd.Timestamp("2021-09-03"))
    assert ("Mississippi", "adams") in before and ("Mississippi", "adams") not in through


def test_area_status_of_report_counties():
    got = areas.build_intervals(IDA)
    rows = pd.DataFrame([
        {"doc_id": "R1", "report_date": "2021-09-01", "state": "Louisiana", "county": "ACADIA"},
        {"doc_id": "R1", "report_date": "2021-09-01", "state": "Louisiana", "county": "POINTE COUPEE"},
        {"doc_id": "R3", "report_date": "2021-09-15", "state": "Texas", "county": "HARRIS"},
        {"doc_id": "R3", "report_date": "2021-09-15", "state": "Texas", "county": "DALLAS"},
    ])
    lists = pd.DataFrame([{"doc_id": d, "state": s, "county": c} for d, s, c in
                          [("R1", "Louisiana", "Acadia"), ("R1", "Louisiana", "Pointe Coupee"), ("R3", "Texas", "Harris")]])
    got = areas.area_statuses(rows, got, lists)
    assert got.area_status.tolist() == ["inside", "inside_spelling_variant", "inside", "table_not_in_list"]


def test_same_day_notice_takes_effect_after_that_days_report():
    # Mississippi's Adams is removed by a notice released Sep 3; the Sep 3 report still lists it.
    # Texas's Harris is added by a notice released Sep 14; it is not in the area for the Sep 14 report.
    got = areas.build_intervals(IDA)
    rows = pd.DataFrame([{"doc_id": "R2", "report_date": "2021-09-03", "state": "Mississippi", "county": "ADAMS"},
                         {"doc_id": "R4", "report_date": "2021-09-14", "state": "Texas", "county": "HARRIS"}])
    lists = rows[["doc_id", "state", "county"]]
    assert areas.area_statuses(rows, got, lists).area_status.tolist() == ["inside", "outside_notice_area"]


def test_state_start_dates():
    got = areas.state_starts(areas.build_intervals(IDA))
    texas = got[got.state == "Texas"].iloc[0]
    assert (texas.reporting_began, texas.began_notice) == (pd.Timestamp("2021-09-14"), "N1")


def test_nicholas_gets_only_the_counties_its_notice_added():
    got = areas.shared_storm_counties(IDA, "N1")
    assigned = dict(zip(got.county, got.assigned_to))
    assert assigned == {"Acadia": "first storm", "Pointe Coupee": "first storm", "Cameron": "second storm",
                        "Harris": "second storm"}
    flagged = got[got.flag != ""].county.tolist()
    assert flagged == ["Acadia", "Pointe Coupee"]


def test_a_county_named_twice_in_one_list_is_handled_once():
    # A Mississippi removal list printed "Wilkinson" twice.
    got = areas.build_intervals([notice("2020-01-01", "A", Op("add", "Mississippi", ["Wilkinson"])),
                                 notice("2020-01-02", "B", Op("remove", "Mississippi", ["Wilkinson", "Wilkinson"]))])
    assert len(got) == 1 and got.iloc[0].removed_by == "B"


def test_within_one_notice_a_restated_area_does_not_undo_its_additions():
    # DA-24-1015A1 adds 35 South Carolina counties, then restates the 11 already active ("REMAIN ACTIVATED IN").
    got = areas.build_intervals([
        notice("2024-09-25", "A", Op("add", "South Carolina", ["Abbeville", "York"])),
        notice("2024-09-27", "B", Op("add", "South Carolina", ["Aiken"]), Op("remain", "South Carolina", ["Abbeville", "York"])),
    ])
    assert got.removed_on.isna().all() and set(got.county) == {"Abbeville", "York", "Aiken"}


def test_county_and_parish_words_do_not_matter():
    got = areas.build_intervals([notice("2024-09-27", "A", Op("add", "Tennessee", ["Washington"]))])
    rows = pd.DataFrame([{"doc_id": "R", "report_date": "2024-10-04", "state": "Tennessee",
                          "county": "Washington County"}])
    assert areas.area_statuses(rows, got, rows[["doc_id", "state", "county"]]).area_status.tolist() == ["inside"]
