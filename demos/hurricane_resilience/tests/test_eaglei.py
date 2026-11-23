"""Step 6: EAGLE-I filtered on read, matched to each report's as-of time."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step6 = importlib.import_module("06_eaglei")

CSV = """fips_code,county,state,customers_out,run_start_time
12005,Bay,Florida,10,2018-10-10 12:00:00
12005,Bay,Florida,50,2018-10-10 12:15:00
01003,Baldwin,Alabama,7,2018-10-10 12:15:00
12005,Bay,Florida,90,2018-12-31 00:00:00
48201,Harris,Texas,3,2018-10-10 12:15:00
"""


def test_extract_keeps_only_study_counties_inside_the_window(tmp_path):
    p = tmp_path / "y.csv"
    p.write_text(CSV, encoding="utf-8")
    windows = pd.DataFrame([{"nhc_id": "AL142018", "fips": f, "start": pd.Timestamp("2018-09-18", tz="UTC"),
                             "end": pd.Timestamp("2018-11-16", tz="UTC")} for f in ("12005", "01003")])
    got = step6.extract_year(p, windows, chunksize=2)
    assert sorted(zip(got.fips, got.customers_out)) == [("01003", 7), ("12005", 10), ("12005", 50)]
    assert str(got.time_utc.dt.tz) == "UTC"


def series(*pairs):
    return pd.DataFrame({"fips": "12005", "time_utc": [pd.Timestamp(t, tz="UTC") for t, _ in pairs],
                         "customers_out": [v for _, v in pairs]})


def test_nearest_value_within_30_minutes_and_earlier_lags():
    e = series(("2018-10-11 12:45", 100), ("2018-10-11 13:10", 120), ("2018-10-11 07:00", 40),
               ("2018-10-10 13:00", 5))
    rows = pd.DataFrame({"doc_id": ["D"], "fips": ["12005"], "as_of_utc": [pd.Timestamp("2018-10-11 13:00", tz="UTC")]})
    m = step6.match(rows, e).iloc[0]
    assert m.eaglei_customers_out == 120 and m.eaglei_gap_min == 10 and m.eaglei_match == "matched"
    assert m.eaglei_customers_out_6h == 40 and m.eaglei_customers_out_24h == 5
    assert pd.isna(m.eaglei_customers_out_12h)


def test_nothing_within_30_minutes_is_not_matched():
    e = series(("2018-10-11 12:00", 100))
    rows = pd.DataFrame({"doc_id": ["D"], "fips": ["12005"], "as_of_utc": [pd.Timestamp("2018-10-11 13:00", tz="UTC")]})
    m = step6.match(rows, e).iloc[0]
    assert m.eaglei_match == "no_record_within_30min" and pd.isna(m.eaglei_customers_out)


def test_county_never_in_the_extract_is_flagged():
    rows = pd.DataFrame({"doc_id": ["D"], "fips": ["99999"], "as_of_utc": [pd.Timestamp("2018-10-11 13:00", tz="UTC")]})
    assert step6.match(rows, series(("2018-10-11 13:00", 1))).iloc[0].eaglei_match == "county_not_in_eaglei_window"


def test_no_as_of_time_is_flagged():
    rows = pd.DataFrame({"doc_id": ["D"], "fips": ["12005"], "as_of_utc": [pd.NaT]})
    assert step6.match(rows, series(("2018-10-11 13:00", 1))).iloc[0].eaglei_match == "no_as_of_time"


def test_state_coverage_for_the_storm_year():
    cov = pd.DataFrame({"year": ["1/1/18", "1/1/19"], "state": ["FL", "FL"], "min_pct_covered": [0.8, 0.9],
                        "max_pct_covered": [0.85, 0.95], "total_customers": [1, 1], "min_covered": [1, 1],
                        "max_covered": [1, 1]})
    got = step6.state_coverage(cov)
    assert got.set_index(["state", "year"]).loc[("Florida", 2019), "min_pct_covered"] == 0.9


@pytest.mark.parametrize("header", ["fips_code,county,state,sum,run_start_time",  # 2023 file
                                    "fips_code,county,state,customers_out,run_start_time,total_customers"])  # 2024
def test_year_files_with_other_headers(tmp_path, header):
    extra = ",500" if header.endswith("total_customers") else ""
    p = tmp_path / "y.csv"
    p.write_text(f"{header}\n12005,Bay,Florida,10,2023-08-30 12:00:00{extra}\n"
                 f"12005,Bay,Florida,,2023-08-30 12:15:00{extra}\n", encoding="utf-8")
    w = pd.DataFrame([{"nhc_id": "X", "fips": "12005", "start": pd.Timestamp("2023-08-01", tz="UTC"),
                       "end": pd.Timestamp("2023-09-30", tz="UTC")}])
    got = step6.extract_year(p, w)
    assert got.customers_out.iloc[0] == 10 and pd.isna(got.customers_out.iloc[1])  # blank stays blank


# --- coverage flag and zero-filled sensitivity (author's decisions, 2026-11-22) ---

@pytest.mark.parametrize("year, cov, release, flag", [
    (2018, 0.74, True, "low_coverage"), (2018, 0.75, True, "ok"), (2017, None, True, "coverage_unknown"),
    (2024, None, True, "coverage_unknown"), (2026, None, False, "no_eaglei_release")])
def test_coverage_flag(year, cov, release, flag):
    df = pd.DataFrame({"storm_year": [year], "eaglei_state_min_covered": [cov], "eaglei_release": [release]})
    assert step6.coverage_flag(df).tolist() == [flag]


def test_presence_is_per_storm_window():
    # Bay County has records in Michael's window only; a Sally row for Bay is "not in window", not "no record"
    e = series(("2018-10-11 13:00", 5))
    w = pd.DataFrame([{"nhc_id": "M", "fips": "12005", "start": pd.Timestamp("2018-09-18", tz="UTC"),
                       "end": pd.Timestamp("2018-11-16", tz="UTC")},
                      {"nhc_id": "S", "fips": "12005", "start": pd.Timestamp("2020-08-24", tz="UTC"),
                       "end": pd.Timestamp("2020-10-13", tz="UTC")}])
    rows = pd.DataFrame({"doc_id": ["D1", "D2"], "row_nhc_id": ["M", "S"], "fips": ["12005", "12005"],
                         "as_of_utc": [pd.Timestamp("2018-10-12 13:00", tz="UTC"), pd.Timestamp("2020-09-17 13:00", tz="UTC")]})
    m = step6.match(rows, e, w)
    assert m.eaglei_match.tolist() == ["no_record_within_30min", "county_not_in_eaglei_window"]
    assert m.eaglei_customers_out_zero_filled.tolist()[0] == 0 and pd.isna(m.eaglei_customers_out_zero_filled.iloc[1])


def test_zero_fill_keeps_matched_values_and_blank_outages():
    e = series(("2018-10-11 13:00", 7))
    rows = pd.DataFrame({"doc_id": ["D"], "fips": ["12005"], "as_of_utc": [pd.Timestamp("2018-10-11 13:00", tz="UTC")]})
    m = step6.match(rows, e).iloc[0]
    assert m.eaglei_customers_out == 7 and m.eaglei_customers_out_zero_filled == 7



def test_mcc_flag_when_window_outages_exceed_modeled_customers():
    # Henderson County, NC in Helene: 24 modeled customers, 71,171 out
    e = pd.DataFrame({"fips": ["37089", "37089", "12005"], "customers_out": [71171.0, 10.0, 500.0],
                      "time_utc": pd.to_datetime(["2024-09-28", "2024-09-29", "2024-09-28"], utc=True)})
    w = pd.DataFrame([{"nhc_id": "H", "fips": f, "start": pd.Timestamp("2024-09-01", tz="UTC"),
                       "end": pd.Timestamp("2024-10-30", tz="UTC")} for f in ("37089", "12005", "13001")])
    got = step6.mcc_flags(e, w, {"37089": 24, "12005": 88692}).set_index("fips")
    assert got.loc["37089", "eaglei_mcc_flag"] == "mcc_below_observed_outages"
    assert got.loc["37089", "eaglei_max_out_in_window"] == 71171
    assert got.loc["12005", "eaglei_mcc_flag"] == "ok"
    assert got.loc["13001", "eaglei_mcc_flag"] == "no_mcc"
