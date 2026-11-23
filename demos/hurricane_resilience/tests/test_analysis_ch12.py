"""Step 10, chapters 1 (the data) and 2 (Isaias anatomy): helpers."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")


def panel():
    return pd.DataFrame([
        {"storm_key": "I", "storm": "Isaias", "doc_id": "D1", "report_date": "2026-10-10", "days_since_landfall": 0.5,
         "state": "Florida", "fips": "12091", "county": "OKALOOSA", "sites_served": 200, "sites_out": 50},
        {"storm_key": "I", "storm": "Isaias", "doc_id": "D1", "report_date": "2026-10-10", "days_since_landfall": 0.5,
         "state": "Alabama", "fips": "01003", "county": "BALDWIN", "sites_served": 100, "sites_out": 10},
        {"storm_key": "I", "storm": "Isaias", "doc_id": "D2", "report_date": "2026-10-11", "days_since_landfall": 1.5,
         "state": "Florida", "fips": "12091", "county": "OKALOOSA", "sites_served": 200, "sites_out": 20},
    ])


def test_state_shares_by_report():
    got = step10.state_by_report(panel())
    fl = [r for r in got if r["state"] == "Florida"]
    assert [(r["report_date"], r["sites_out"], r["pct_out"]) for r in fl] == [("2026-10-10", 50, 25.0), ("2026-10-11", 20, 10.0)]


def test_county_peaks_are_ranked_by_share():
    got = step10.county_peak_table(panel())
    assert [r["county"] for r in got] == ["Okaloosa", "Baldwin"] and got[0]["peak_pct_out"] == 25.0


def test_coverage_table_counts_reports_and_counties():
    storms = pd.DataFrame([{"storm_key": "I", "storm": "Isaias", "nhc_id": "AL092026", "rule_period": "P3",
                            "dirs_activation_date": "2026-10-08", "in_panel": True, "excluded_reports": "",
                            "landfall_utc": pd.Timestamp("2026-10-10", tz="UTC"), "landfall_source": "closest approach"}])
    got = step10.coverage_table(panel(), storms)[0]
    assert (got["n_reports"], got["n_counties"], got["county_days"], got["first_report"], got["last_report"]) == \
        (2, 2, 3, "2026-10-10", "2026-10-11")



def test_flag_type_table_counts_reports_and_stops_on_unknown():
    v = pd.DataFrame({"doc_id": ["A", "B", "C"], "flag_reasons": [
        "3 rows outside_notice_area; FCC spelling: x", "FCC spelling: y; 2 rows inside_spelling_variant", ""]})
    got = {r["flag"]: (r["class"], r["n_reports"]) for r in step10.flag_type_table(v, ["A", "B", "C"])}
    assert got["County name spelling variant"] == ("benign", 2)  # counted once per report
    assert got["County rows outside the FCC notice's area"] == ("serious", 1)
    with pytest.raises(ValueError, match="unknown flag"):
        step10.flag_type_table(pd.DataFrame({"doc_id": ["Z"], "flag_reasons": ["new thing"]}), ["Z"])
