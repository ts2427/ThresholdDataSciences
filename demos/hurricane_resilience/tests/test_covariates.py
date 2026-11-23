"""Step 8: county covariates (ACS part)."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step8 = importlib.import_module("08_fema_svi_bdc")


def test_acs_response_to_county_table():
    header = ["NAME", *step8.ACS_VARS, "state", "county"]
    vals = {v: "0" for v in step8.ACS_VARS}
    vals.update(B11001_001E="1000", B01001_001E="2500", B01001_020E="100", B01001_049E="150",
                B28002_001E="1000", B28002_004E="800")
    data = [header, ["Bay County, Florida", *[vals[v] for v in step8.ACS_VARS], "12", "005"]]
    got = step8.acs_table(data).iloc[0]
    assert got.fips == "12005" and got.acs_households == 1000
    assert got.acs_pct_65plus == pytest.approx(10.0) and got.acs_pct_broadband == pytest.approx(80.0)


def test_acs_missing_value_codes_are_blank():
    header = ["NAME", *step8.ACS_VARS, "state", "county"]
    row = ["X", *(["-666666666"] * len(step8.ACS_VARS)), "12", "005"]
    got = step8.acs_table([header, row]).iloc[0]
    assert pd.isna(got.acs_households) and pd.isna(got.acs_pct_broadband)


def test_key_is_not_in_the_logged_url():
    job = step8.acs_job("abc123")
    assert "abc123" in job["url"] and "abc123" not in job["logged_url"] and "key=REDACTED" in job["logged_url"]


# --- OpenFEMA (author's decision 2026-11-22) and SVI ---

def decl(**kw):
    base = {"disasterNumber": 4834, "state": "FL", "declarationType": "DR", "declarationDate": "2024-09-28T00:00:00.000Z",
            "incidentType": "Hurricane", "declarationTitle": "HURRICANE HELENE", "incidentBeginDate": "2024-09-23T00:00:00.000Z",
            "incidentEndDate": "2024-10-07T00:00:00.000Z", "fipsStateCode": "12", "fipsCountyCode": "123",
            "designatedArea": "Taylor (County)", "ihProgramDeclared": True, "iaProgramDeclared": False,
            "paProgramDeclared": True, "hmProgramDeclared": True, "id": "x"}
    return {**base, **kw}


STORMS = pd.DataFrame([{"storm_name": "Helene", "nhc_id": "AL092024", "dirs_activation_date": "2024-09-25",
                        "dirs_deactivation_date": "2024-10-19"},
                       {"storm_name": "Isaias", "nhc_id": "AL092026", "dirs_activation_date": "2026-10-08",
                        "dirs_deactivation_date": "2026-10-12"}])


def test_declarations_match_storm_by_name_and_date():
    d = pd.DataFrame([decl(), decl(declarationTitle="HURRICANE ISAIAS", incidentBeginDate="2020-07-30T00:00:00.000Z",
                               fipsStateCode="37", fipsCountyCode="019"),  # Isaias 2020: not the 2026 storm
                      decl(declarationTitle="SEVERE STORMS", fipsCountyCode="005")])
    got = step8.fema_by_county(d, STORMS)
    assert got[["nhc_id", "fips"]].values.tolist() == [["AL092024", "12123"]]
    r = got.iloc[0]
    assert r.fema_dr and not r.fema_em and r.fema_ih and r.fema_pa and not r.fema_ia


def test_statewide_and_tribal_rows_are_not_county_rows():
    d = pd.DataFrame([decl(fipsCountyCode="000", designatedArea="Statewide"), decl()])
    assert step8.fema_by_county(d, STORMS).fips.tolist() == ["12123"]


def test_em_then_dr_for_one_county_is_one_row():
    d = pd.DataFrame([decl(declarationType="EM", declarationDate="2024-09-24T00:00:00.000Z", disasterNumber=3622), decl()])
    r = step8.fema_by_county(d, STORMS).iloc[0]
    assert r.fema_em and r.fema_dr and str(r.fema_first_declared.date()) == "2024-09-24"


def test_fema_page_urls_are_paced_and_ordered():
    jobs = step8.fema_jobs(2500)
    assert len(jobs) == 3 and all(j["url"].startswith(step8.FEMA_BASE) for j in jobs)
    assert "%24skip=2000" in jobs[2]["url"] and "%24orderby=id" in jobs[0]["url"]


def test_svi_table_uses_us_ranks_and_blanks_missing():
    raw = pd.DataFrame({"FIPS": ["12005", "12123"], "RPL_THEMES": [0.4, -999], "RPL_THEME1": [0.1, 0.2],
                        "RPL_THEME2": [0.2, 0.3], "RPL_THEME3": [0.3, 0.4], "RPL_THEME4": [0.5, 0.6]})
    got = step8.svi_table(raw).set_index("fips")
    assert got.loc["12005", "svi_overall"] == 0.4 and pd.isna(got.loc["12123", "svi_overall"])
