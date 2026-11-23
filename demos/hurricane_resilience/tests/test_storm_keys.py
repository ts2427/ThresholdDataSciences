"""Each county row gets its storm key; Nicholas counties in the shared Ida reports get Nicholas's."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from storm_keys import assign_storm_keys  # noqa: E402

SHARED = pd.DataFrame([
    {"notice": "DA-21-1152A1", "storm_page": "ida", "applies_from": "2021-09-15", "state": "Texas", "county": "Harris",
     "assigned_storm": "Nicholas", "assigned_nhc_id": "AL142021", "flag": ""},
    {"notice": "DA-21-1152A1", "storm_page": "ida", "applies_from": "2021-09-15", "state": "Louisiana",
     "county": "Pointe Coupee", "assigned_storm": "Ida", "assigned_nhc_id": "AL092021",
     "flag": "also named by the second storm's notice; kept with the first storm"},
])
STORMS = pd.DataFrame([
    {"storm_name": "Ida", "nhc_id": "AL092021", "storm_page": "ida", "dirs_activation_date": "2021-08-29"},
    {"storm_name": "Nicholas", "nhc_id": "AL142021", "storm_page": "ida", "dirs_activation_date": "2021-09-14"},
])


def row(date, state, county):
    return {"doc_id": "D", "storm_name": "Ida", "nhc_id": "AL092021", "report_date": date, "state": state,
            "county": county}


def test_rows_from_the_applies_from_date_take_the_second_storms_key():
    got = assign_storm_keys(pd.DataFrame([row("2021-09-15", "Texas", "HARRIS")]), SHARED, STORMS).iloc[0]
    assert (got.row_storm, got.row_nhc_id, got.row_dirs_activation_date, got.storm_key_flag) == (
        "Nicholas", "AL142021", "2021-09-14", "")


def test_rows_before_that_date_keep_the_reports_storm():
    got = assign_storm_keys(pd.DataFrame([row("2021-09-14", "Texas", "HARRIS")]), SHARED, STORMS).iloc[0]
    assert (got.row_storm, got.row_nhc_id) == ("Ida", "AL092021")


def test_county_in_both_stays_with_the_first_storm_and_is_flagged():
    got = assign_storm_keys(pd.DataFrame([row("2021-09-16", "Louisiana", "POINTE COUPEE")]), SHARED, STORMS).iloc[0]
    assert (got.row_storm, got.row_dirs_activation_date) == ("Ida", "2021-08-29")
    assert got.storm_key_flag.startswith("also named")


def test_other_storms_and_states_are_untouched():
    rows = pd.DataFrame([row("2021-09-16", "Louisiana", "ACADIA"),
                         {**row("2024-09-30", "Florida", "Bay"), "storm_name": "Helene", "nhc_id": "AL092024"}])
    storms = pd.concat([STORMS, pd.DataFrame([{"storm_name": "Helene", "nhc_id": "AL092024", "storm_page": "helene",
                                               "dirs_activation_date": "2024-09-25"}])])
    got = assign_storm_keys(rows, SHARED, storms)
    assert got.row_storm.tolist() == ["Ida", "Helene"] and got.row_dirs_activation_date.tolist() == ["2021-08-29",
                                                                                                    "2024-09-25"]
    assert (got.storm_key_flag == "").all()


def test_the_values_are_not_split():
    rows = pd.DataFrame([{**row("2021-09-16", "Texas", "HARRIS"), "sites_out": 7.0}])
    got = assign_storm_keys(rows, SHARED, STORMS)
    assert len(got) == 1 and got.sites_out.iloc[0] == 7.0
