"""Step 6: EAGLE-I power outages matched to DIRS snapshot times.

Source: ORNL/DOE EAGLE-I (doi:10.1038/s41597-024-03095-5; figshare doi:10.6084/m9.figshare.24237376 v4;
2025 release doi:10.13139/ORNLNCCS/3012826). CC BY 4.0 / free reuse with attribution. Raw year files are in
EAGLEI_RAW_DIR (outside the project; see config.py), downloaded by step 6a.
* Each year's CSV is read in chunks; only the counties in each storm's reports (row_nhc_id, FIPS from step 5) and
  the window from 21 days before DIRS activation to 21 days after deactivation are kept. The extract is
  data/interim/eaglei_extract.parquet; whole years are never loaded.
* The 2023 file names the outage column "sum"; 2024 adds total_customers (not used: MCC is the
  denominator for every year). A blank customers_out stays blank.
* run_start_time is read as UTC (checked against landfall times; see docs/decisions.md).
* % of customers out uses MCC.csv (modeled customers per county; "customers" means meters). Coverage is published
  only by state and year (coverage_history.csv, 2018-2022): each row carries its state's min and max share of
  customers covered for the storm year, blank when not published. The low-coverage threshold is the author's
  decision: below 0.75 (the state's minimum covered share that year) is flagged low_coverage and kept; years with
  no published coverage (2017, 2023, 2024) are coverage_unknown, with no other year borrowed (2026-11-22).
* MCC is below EAGLE-I's own customers out in some counties (deviation logged 2026-11-22): each storm-county gets
  eaglei_mcc_flag = ok, mcc_below_observed_outages (its highest customers out in the window exceeds MCC: % of
  customers out is not used for it) or no_mcc, with eaglei_max_out_in_window.
* For each county row of each report: the EAGLE-I record nearest the report's as-of time within 30 minutes, and
  the same 6, 12 and 24 hours earlier. EAGLE-I has no row when it has no outage record, so an unmatched time is
  left blank, never set to zero; eaglei_match says why. For a sensitivity display only,
  eaglei_customers_out_zero_filled sets it to zero where the county has at least one EAGLE-I record in that
  storm's window.
* Isaias 2026 has no EAGLE-I data (the dataset ends in 2025): its rows are no_eaglei_release.
Output: data/interim/eaglei_matched.parquet. Do NOT use poweroutage.us.
"""
import numpy as np
import pandas as pd

from carried import require_carried
from config import EAGLEI_EXTRACT, EAGLEI_RAW_DIR, INTERIM, ROOT

STORMS = ROOT / "manifest" / "storms.csv"
WINDOW_DAYS = 21
TOLERANCE = pd.Timedelta(minutes=30)
LAGS = (6, 12, 24)
LAST_EAGLEI_YEAR = 2025
STATE_NAMES = {"AL": "Alabama", "AR": "Arkansas", "DC": "District of Columbia", "DE": "Delaware", "FL": "Florida",
               "GA": "Georgia", "IL": "Illinois", "IN": "Indiana", "KY": "Kentucky", "LA": "Louisiana",
               "MD": "Maryland", "MO": "Missouri", "MS": "Mississippi", "NC": "North Carolina", "NJ": "New Jersey",
               "NY": "New York", "OH": "Ohio", "OK": "Oklahoma", "PA": "Pennsylvania", "PR": "Puerto Rico",
               "SC": "South Carolina", "TN": "Tennessee", "TX": "Texas", "VA": "Virginia", "WV": "West Virginia"}


def extract_year(path, windows: pd.DataFrame, chunksize: int = 2_000_000) -> pd.DataFrame:
    """Rows of one year file for the windows' counties and times (a county in two storms keeps both)."""
    keep = []
    fips = set(windows.fips)
    with open(path, encoding="utf-8") as f:
        header = f.readline().strip().split(",")
    out_col = "sum" if "sum" in header else "customers_out"  # the 2023 file names it "sum"
    reader = pd.read_csv(path, usecols=["fips_code", out_col, "run_start_time"],
                         dtype={"fips_code": str, out_col: "float64", "run_start_time": str},
                         chunksize=chunksize)
    for chunk in reader:
        chunk = chunk.rename(columns={out_col: "customers_out"})
        chunk = chunk[chunk.fips_code.str.zfill(5).isin(fips)]
        if chunk.empty:
            continue
        c = pd.DataFrame({"fips": chunk.fips_code.str.zfill(5),
                          "time_utc": pd.to_datetime(chunk.run_start_time, utc=True),
                          "customers_out": chunk.customers_out})
        c = c.merge(windows[["fips", "start", "end"]], on="fips")
        keep.append(c[(c.time_utc >= c.start) & (c.time_utc <= c.end)].drop(columns=["start", "end"]))
    out = pd.concat(keep, ignore_index=True) if keep else pd.DataFrame(columns=["fips", "time_utc", "customers_out"])
    return out.drop_duplicates(["fips", "time_utc"]).reset_index(drop=True)


def _nearest(rows: pd.DataFrame, e: pd.DataFrame, offset: pd.Timedelta) -> pd.DataFrame:
    left = rows.assign(target=rows.as_of_utc - offset).dropna(subset=["target"]).sort_values("target")
    right = e.rename(columns={"time_utc": "eaglei_time"}).sort_values("eaglei_time")
    left["target"] = left.target.astype("datetime64[ns, UTC]")
    right["eaglei_time"] = right.eaglei_time.astype("datetime64[ns, UTC]")
    return pd.merge_asof(left, right, left_on="target", right_on="eaglei_time", by="fips",
                         direction="nearest", tolerance=TOLERANCE)


def match(rows: pd.DataFrame, e: pd.DataFrame, windows: pd.DataFrame | None = None) -> pd.DataFrame:
    """rows: doc_id, fips, as_of_utc (plus anything else, kept). e: fips, time_utc, customers_out.
    With windows (nhc_id, fips, start, end) and rows.row_nhc_id, "in the window" means a record of that county
    inside that storm's window; otherwise anywhere in e."""
    out = rows.reset_index(drop=True).copy()
    out["as_of_utc"] = pd.to_datetime(out.as_of_utc, utc=True)
    out["_i"] = np.arange(len(out))
    now = _nearest(out[["_i", "fips", "as_of_utc"]], e, pd.Timedelta(0)).set_index("_i")
    out["eaglei_time"] = out._i.map(now.eaglei_time)
    out["eaglei_customers_out"] = out._i.map(now.customers_out)
    out["eaglei_gap_min"] = ((out.eaglei_time - out.as_of_utc).abs().dt.total_seconds() / 60).round(1)
    for h in LAGS:
        lag = _nearest(out[["_i", "fips", "as_of_utc"]], e, pd.Timedelta(hours=h)).set_index("_i")
        out[f"eaglei_customers_out_{h}h"] = out._i.map(lag.customers_out)
    if windows is not None and "row_nhc_id" in out.columns:
        hits = e.merge(windows, on="fips")
        hits = hits[(hits.time_utc >= hits.start) & (hits.time_utc <= hits.end)]
        present = set(zip(hits.nhc_id, hits.fips))
        in_window = pd.Series([(s, f) in present for s, f in zip(out.row_nhc_id, out.fips)], index=out.index)
    else:
        in_window = out.fips.isin(set(e.fips))
    out["eaglei_match"] = np.select(
        [out.as_of_utc.isna(), ~in_window, out.eaglei_customers_out.notna()],
        ["no_as_of_time", "county_not_in_eaglei_window", "matched"], "no_record_within_30min")
    # Sensitivity only (author's decision): no record = zero, for counties with a record in that storm's window
    fill = out.eaglei_match == "no_record_within_30min"
    out["eaglei_customers_out_zero_filled"] = out.eaglei_customers_out.where(~fill, 0.0)
    return out.drop(columns="_i")


LOW_COVERAGE = 0.75  # author's decision 2026-11-22: state's minimum covered share for the year


def coverage_flag(df: pd.DataFrame) -> pd.Series:
    """ok, low_coverage (< 0.75), coverage_unknown (no coverage published for that year: 2017, 2023, 2024; no
    other year is borrowed) or no_eaglei_release (Isaias 2026)."""
    cov = df.eaglei_state_min_covered
    return pd.Series(np.select([~df.eaglei_release, cov.isna(), cov < LOW_COVERAGE],
                               ["no_eaglei_release", "coverage_unknown", "low_coverage"], "ok"), index=df.index)


def mcc_flags(e: pd.DataFrame, windows: pd.DataFrame, mcc: dict) -> pd.DataFrame:
    """Per storm and county: the highest customers out in the storm's window, and whether the modeled customer count
    (MCC) is at least that (ok), below it (mcc_below_observed_outages: % of customers out is not used) or missing."""
    hits = e.merge(windows, on="fips")
    hits = hits[(hits.time_utc >= hits.start) & (hits.time_utc <= hits.end)]
    mx = hits.groupby(["nhc_id", "fips"]).customers_out.max().rename("eaglei_max_out_in_window")
    out = windows[["nhc_id", "fips"]].drop_duplicates().merge(mx.reset_index(), on=["nhc_id", "fips"], how="left")
    m = out.fips.map(mcc)
    out["eaglei_mcc_flag"] = np.select([m.isna(), out.eaglei_max_out_in_window > m],
                                       ["no_mcc", "mcc_below_observed_outages"], "ok")
    return out


def state_coverage(cov: pd.DataFrame) -> pd.DataFrame:
    c = cov.assign(year=pd.to_datetime(cov.year, format="%m/%d/%y").dt.year, state=cov.state.map(STATE_NAMES))
    return c.dropna(subset=["state"])[["state", "year", "min_pct_covered", "max_pct_covered"]]


def windows_for(rows: pd.DataFrame, storms: pd.DataFrame) -> pd.DataFrame:
    s = storms.assign(start=pd.to_datetime(storms.dirs_activation_date, utc=True) - pd.Timedelta(days=WINDOW_DAYS),
                      end=pd.to_datetime(storms.dirs_deactivation_date, utc=True) + pd.Timedelta(days=WINDOW_DAYS + 1))
    w = rows[["row_nhc_id", "fips"]].drop_duplicates().merge(s[["nhc_id", "start", "end"]], left_on="row_nhc_id",
                                                              right_on="nhc_id")
    return w[["nhc_id", "fips", "start", "end"]]


def build_extract(rows, storms) -> pd.DataFrame:
    w = windows_for(rows, storms)
    w = w[w.start.dt.year <= LAST_EAGLEI_YEAR]
    parts = []
    for year in sorted(set(w.start.dt.year) | set(w.end.dt.year)):
        wy = w[(w.start.dt.year <= year) & (w.end.dt.year >= year)]
        path = EAGLEI_RAW_DIR / f"eaglei_outages_{year}.csv"
        if not path.exists():
            raise SystemExit(f"missing {path.name} in EAGLEI_RAW_DIR: run step 6a")
        part = extract_year(path, wy)
        print(f"{year}: {len(part):,} rows kept for {wy.fips.nunique()} counties", flush=True)
        parts.append(part)
    return pd.concat(parts, ignore_index=True).drop_duplicates(["fips", "time_utc"])


def main():
    rows = pd.read_parquet(INTERIM / "dirs_county_rows_fips.parquet")
    reports = pd.read_parquet(INTERIM / "dirs_reports.parquet", columns=["doc_id", "as_of_utc"])
    storms = pd.read_csv(STORMS)
    extract_path = EAGLEI_EXTRACT
    if extract_path.exists():
        e = pd.read_parquet(extract_path)
    else:
        e = build_extract(rows, storms)
        e.to_parquet(extract_path, index=False)
    rows = rows.merge(reports, on="doc_id", how="left", validate="many_to_one")
    rows["as_of_utc"] = pd.to_datetime(rows.as_of_utc, utc=True)
    out = match(rows, e, windows_for(rows, storms))
    out["storm_year"] = pd.to_datetime(out.report_date).dt.year
    out["eaglei_release"] = out.storm_year <= LAST_EAGLEI_YEAR
    out.loc[~out.eaglei_release, "eaglei_match"] = "no_eaglei_release"
    out.loc[~out.eaglei_release, ["eaglei_customers_out", "eaglei_customers_out_zero_filled"]
            + [f"eaglei_customers_out_{h}h" for h in LAGS]] = np.nan
    mcc = pd.read_csv(EAGLEI_RAW_DIR / "MCC.csv", encoding="utf-8-sig", dtype={"County_FIPS": str})
    mcc = dict(zip(mcc.County_FIPS.str.zfill(5), mcc.Customers))
    out["eaglei_modeled_customers"] = out.fips.map(mcc)
    out["eaglei_pct_out"] = 100 * out.eaglei_customers_out / out.eaglei_modeled_customers
    flags = mcc_flags(e, windows_for(rows, storms), mcc).rename(columns={"nhc_id": "row_nhc_id"})
    out = out.merge(flags, on=["row_nhc_id", "fips"], how="left", validate="many_to_one")
    cov = state_coverage(pd.read_csv(EAGLEI_RAW_DIR / "coverage_history.csv"))
    out = out.merge(cov.rename(columns={"year": "storm_year", "min_pct_covered": "eaglei_state_min_covered",
                                        "max_pct_covered": "eaglei_state_max_covered"}),
                    on=["state", "storm_year"], how="left", validate="many_to_one")
    out["eaglei_coverage_flag"] = coverage_flag(out)
    require_carried(out, "eaglei_matched")
    out.to_parquet(INTERIM / "eaglei_matched.parquet", index=False)
    print(f"{len(out):,} report-county rows; extract {len(e):,} rows")
    print(out.eaglei_match.value_counts().to_string())


if __name__ == "__main__":
    main()
