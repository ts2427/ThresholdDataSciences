"""Step 5: DIRS county names to FIPS, with the names found in real reports."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step5 = importlib.import_module("05_fips")

CENSUS = pd.DataFrame([
    ("LA", "22", "093", "St. James Parish"), ("LA", "22", "095", "St. John the Baptist Parish"),
    ("FL", "12", "086", "Miami-Dade County"), ("GA", "13", "089", "DeKalb County"),
    ("VA", "51", "036", "Charles City County"), ("VA", "51", "059", "Fairfax County"), ("VA", "51", "600", "Fairfax city"),
    ("VA", "51", "750", "Radford city"), ("PR", "72", "005", "Aguadilla Municipio"), ("PR", "72", "007", "Aguas Buenas Municipio"),
    ("TX", "48", "123", "DeWitt County"), ("NM", "35", "013", "Doña Ana County"), ("FL", "12", "027", "DeSoto County"),
], columns=["STATE", "STATEFP", "COUNTYFP", "COUNTYNAME"])
EXCEPTIONS = pd.DataFrame([{"state": "Virginia", "dirs_county_name": "RADFORD", "census_county_name": "Radford city",
                            "fips": "51750", "note": "independent city; no Radford County"}])


def match(state, county, exceptions=EXCEPTIONS):
    rows = pd.DataFrame({"state": [state], "county": [county]})
    exceptions = exceptions[exceptions.dirs_county_name == county]  # the rest would be unused
    return step5.crosswalk(rows, CENSUS, exceptions).fips.iloc[0]


@pytest.mark.parametrize("state, county, fips", [
    ("Louisiana", "ST. JAMES", "22093"),  # "St." for Saint in the reports, "St." in Census
    ("Louisiana", "ST. JOHN THE BAPTIST", "22095"),
    ("Florida", "MIAMI-DADE", "12086"),
    ("Florida", "DE SOTO", "12027"),  # spaced in some reports
    ("Georgia", "De Kalb", "13089"),
    ("Texas", "DE WITT", "48123"),
    ("Virginia", "CHARLES CITY", "51036"),  # a county whose name ends in City
    ("Virginia", "FAIRFAX", "51059"),  # a plain name is the county; the reports write cities as "X CITY"
    ("Virginia", "FAIRFAX CITY", "51600"),
    ("Puerto Rico", "AGUAS BUENAS", "72007"),
    ("Virginia", "RADFORD", "51750"),  # from the exception table
])
def test_real_names_match(state, county, fips):
    assert match(state, county) == fips


def test_unmatched_name_not_in_the_exception_table_fails():
    with pytest.raises(SystemExit, match="no FIPS for Virginia/SALEM"):
        match("Virginia", "SALEM")


def test_unused_exception_fails():
    rows = pd.DataFrame({"state": ["Florida"], "county": ["MIAMI-DADE"]})
    with pytest.raises(SystemExit, match="exception not used: Virginia/RADFORD"):
        step5.crosswalk(rows, CENSUS, EXCEPTIONS)


def test_exception_fips_must_be_a_census_county():
    bad = EXCEPTIONS.assign(fips="51999")
    with pytest.raises(SystemExit, match="51999 is not in the Census county file"):
        match("Virginia", "RADFORD", bad)


@pytest.mark.skipif(not (step5.INTERIM / "dirs_county_rows.parquet").exists(), reason="needs step 3 output (data, not committed)")
def test_the_exception_table_covers_every_real_name():
    rows = pd.read_parquet(step5.INTERIM / "dirs_county_rows.parquet", columns=["row_nhc_id", "state", "county"])
    rows, _ = step5.apply_scope(rows, pd.read_csv(step5.SCOPE))  # as step 5 does
    got = step5.crosswalk(rows.drop_duplicates(), step5.read_census(), pd.read_csv(step5.EXCEPTIONS, dtype=str))
    assert got.fips.str.fullmatch(r"\d{5}").all()


def test_out_of_scope_areas_are_dropped_and_counted():
    rows = pd.DataFrame({"row_nhc_id": ["AL112017", "AL112017", "AL092024"], "state": ["Puerto Rico", "Florida", "Puerto Rico"],
                         "county": ["AGUADILLA", "BAY", "AGUADILLA"]})
    scope = pd.DataFrame([{"nhc_id": "AL112017", "state": "Puerto Rico"}])
    kept, dropped = step5.apply_scope(rows, scope)
    assert kept.state.tolist() == ["Florida", "Puerto Rico"] and len(dropped) == 1  # only that storm's rows


def test_every_scope_entry_must_drop_something():
    rows = pd.DataFrame({"row_nhc_id": ["AL112017"], "state": ["Florida"], "county": ["BAY"]})
    with pytest.raises(SystemExit, match="drops no rows"):
        step5.apply_scope(rows, pd.DataFrame([{"nhc_id": "AL112017", "state": "Puerto Rico"}]))


def test_scope_table_is_generated_from_study_states():
    rows = pd.DataFrame({"row_nhc_id": ["L", "L", "L", "I"], "row_storm": ["Laura", "Laura", "Laura", "Irma"],
                         "state": ["Louisiana", "Arkansas", "Arkansas", "Puerto Rico"], "county": ["A", "B", "C", "D"]})
    got = step5.scope_table(rows, ["Louisiana"])
    assert got[["nhc_id", "state", "rows"]].values.tolist() == [["I", "Puerto Rico", 1], ["L", "Arkansas", 2]]
    assert set(got.reason) == {"outside config.STUDY_STATES"}
    kept, dropped = step5.apply_scope(rows, got)
    assert kept.state.tolist() == ["Louisiana"] and len(dropped) == 3
