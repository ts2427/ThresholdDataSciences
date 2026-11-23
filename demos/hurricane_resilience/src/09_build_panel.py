"""Step 9: county x report-day panel.

Joins the in-scope DIRS county rows with FIPS and EAGLE-I values (data/interim/eaglei_matched.parquet), the
report fields and validation status, exposure (step 7), covariates (step 8: ACS and SVI by county) and FEMA
declarations (per storm and county).
* Only reports in use: the 7 in manifest/excluded_reports.csv are left out (deviation logged 2026-11-22) and
  listed, with reasons, in the storm table.
* Storm key: NHC ID plus DIRS activation date (row_nhc_id, row_dirs_activation_date), never the name.
* Rule period (P0-P3) from config.REGIMES by the storm's DIRS activation date.
* Day 0 ("landfall_utc", second correction 2026-11-23): step 7's time origin, the first time 34-kt winds reach a
  study-state county (fallback: first study-state landfall). Two earlier rules are kept for chapter 8's comparison:
  the original (earliest HURDAT2 landfall nearest to at least one county; closest approach without a landfall marker),
  as previous_landfall_utc and days_since_landfall_previous_rule, and the first 2026-11-23 rule (earlier of first
  study-state landfall and closest approach), as interim_landfall_utc and days_since_landfall_interim_rule.
* time_flag (decision 2026-11-23): config.TIME_FLAGS marks reports kept in the panel but left out of every time-based
  result (Laura's Aug 25, 2020 combined Marco/Laura report: "pre_onset_likely_marco"). The build stops if any other
  report falls before day 0.
* days_since_landfall from each report's as-of time; a report with none is placed at 12:00 Eastern on its
  report date and flagged as_of_imputed (deviation).
* Per storm and county: first and last report, number of reports, and censoring: "left_reports_while_out" (its
  last report is before the storm's last report and it still had sites out), "out_at_last_report" (still out in
  the storm's last report), or "none". Censored counties are not recovered.
* Cable and wireline subscribers out are printed for the report's whole area: flagged when that area included
  states now out of scope, or when the report is shared by two storms (Ida and Nicholas).
Outputs: data/processed/panel.parquet, data/processed/storms.parquet, and data/processed/dirs_county_day.csv
(the public CC BY 4.0 dataset: DIRS fields, plus fema_declared as context for reuse; no result uses it). Both
keep out_unattributed and out_overattributed.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from carried import require_carried
from config import INTERIM, OUTPUT, PROCESSED, REGIMES, ROOT, STUDY_STATES, TIME_FLAGS

EXCLUDED = ROOT / "manifest" / "excluded_reports.csv"
STORMS = ROOT / "manifest" / "storms.csv"
EASTERN = ZoneInfo("America/New_York")
PERIOD_CODES = ["P0", "P1", "P2", "P3"]
PUBLIC_COLUMNS = ["storm_key", "nhc_id", "storm", "dirs_activation_date", "rule_period", "doc_id", "report_date",
                  "as_of_utc", "as_of_imputed", "report_status", "state", "county", "fips", "sites_served", "sites_out",
                  "pct_out", "pct_printed", "out_damage", "out_transport", "out_power", "on_backup_power",
                  "out_unattributed", "out_overattributed", "area_status", "fema_declared", "time_flag"]


def rule_period(activation_date: str) -> tuple[str, str]:
    for code, (label, start, end) in zip(PERIOD_CODES, REGIMES):
        if start <= activation_date <= end:
            return code, label
    raise ValueError(f"no rule period for {activation_date}")


def storm_landfall(ex: pd.DataFrame) -> pd.DataFrame:
    """The previous day-0 rule (before the 2026-11-23 correction), kept for comparison."""
    out = []
    for nhc_id, g in ex.groupby("nhc_id"):
        if g.nearest_landfall_utc.notna().any():
            out.append((nhc_id, g.nearest_landfall_utc.min(), "HURDAT2"))
        else:
            out.append((nhc_id, g.loc[g.min_dist_km.idxmin(), "closest_utc"], "closest approach (no landfall marker)"))
    return pd.DataFrame(out, columns=["nhc_id", "landfall_utc", "landfall_source"])


def check_time_flags(p: pd.DataFrame) -> None:
    """Every report before day 0 must carry a time flag, and every flagged report must be in the panel."""
    early = set(p.loc[p.days_since_landfall < 0, "doc_id"])
    flagged = set(p.loc[p.time_flag != "", "doc_id"])
    if early - flagged:
        raise SystemExit(f"reports before day 0 without a time flag: {sorted(early - flagged)}")
    if missing := set(TIME_FLAGS) - set(p.doc_id):
        raise SystemExit(f"time-flagged reports not in the panel: {sorted(missing)}")


def fill_as_of(reports: pd.DataFrame) -> pd.DataFrame:
    r = reports.copy()
    r["as_of_utc"] = pd.to_datetime(r.as_of_utc, utc=True)
    r["as_of_imputed"] = r.as_of_utc.isna()
    noon = [pd.Timestamp(datetime.fromisoformat(f"{d}T12:00").replace(tzinfo=EASTERN)).tz_convert("UTC")
            for d in r.report_date]
    r.loc[r.as_of_imputed, "as_of_utc"] = pd.Series(noon, index=r.index)[r.as_of_imputed]
    return r


def county_spans(panel: pd.DataFrame) -> pd.DataFrame:
    """First/last report and censoring per storm and county (rows: storm_key, fips, report_date, sites_out)."""
    last_storm = panel.groupby("storm_key").report_date.max()
    p = panel.sort_values("report_date")
    g = p.groupby(["storm_key", "fips"])
    out = g.agg(first_report_date=("report_date", "first"), last_report_date=("report_date", "last"),
                n_reports=("report_date", "size"), out_at_last=("sites_out", "last")).reset_index()
    still_out = out.out_at_last > 0
    left_early = out.last_report_date < out.storm_key.map(last_storm)
    out["censoring"] = "none"
    out.loc[still_out & left_early, "censoring"] = "left_reports_while_out"
    out.loc[still_out & ~left_early, "censoring"] = "out_at_last_report"
    return out.drop(columns="out_at_last")


def report_area_flags(all_rows: pd.DataFrame, study_states) -> pd.DataFrame:
    f = all_rows.assign(out=~all_rows.state.isin(study_states)).groupby("doc_id").out.any()
    return f.rename("area_includes_out_of_scope").reset_index()


def main():
    rows = pd.read_parquet(INTERIM / "eaglei_matched.parquet")
    reports = fill_as_of(pd.read_parquet(INTERIM / "dirs_reports.parquet"))
    validation = pd.read_csv(OUTPUT / "validation_dirs.csv", keep_default_na=False)
    excluded = pd.read_csv(EXCLUDED, dtype=str, keep_default_na=False)
    storms = pd.read_csv(STORMS)
    exposure = pd.read_parquet(INTERIM / "county_storm_exposure.parquet")
    covariates = pd.read_parquet(INTERIM / "county_covariates.parquet")
    fema = pd.read_parquet(INTERIM / "fema_declarations.parquet")
    all_rows = pd.read_parquet(INTERIM / "dirs_county_rows.parquet", columns=["doc_id", "state", "row_nhc_id"])

    rows = rows[~rows.doc_id.isin(set(excluded.doc_id))].drop(columns=["as_of_utc"])
    rows = rows.rename(columns={"storm_name": "report_storm_name", "nhc_id": "report_nhc_id"})
    rows = rows.assign(storm_key=rows.row_nhc_id + "_" + rows.row_dirs_activation_date.astype(str),
                       nhc_id=rows.row_nhc_id, storm=rows.row_storm, dirs_activation_date=rows.row_dirs_activation_date)
    rep = reports[["doc_id", "as_of_utc", "as_of_imputed", "as_of_note", "cable_wireline_subs_out",
                   "pct_sites_out_stated"]].merge(report_area_flags(all_rows, STUDY_STATES), on="doc_id", how="left")
    shared = all_rows.groupby("doc_id").row_nhc_id.nunique().gt(1).rename("report_shared_by_storms").reset_index()
    rep = rep.merge(shared, on="doc_id", how="left")
    val = validation[["doc_id", "status", "flag_reasons", "fcc_multiple_causes_note"]].rename(
        columns={"status": "report_status", "flag_reasons": "report_flags"})
    p = rows.merge(rep, on="doc_id", how="left", validate="many_to_one").merge(val, on="doc_id", how="left",
                                                                                validate="many_to_one")
    periods = {d: rule_period(str(d)) for d in p.dirs_activation_date.astype(str).unique()}
    p["rule_period"] = p.dirs_activation_date.astype(str).map(lambda d: periods[d][0])
    p["rule_period_label"] = p.dirs_activation_date.astype(str).map(lambda d: periods[d][1])
    prev = storm_landfall(exposure).rename(columns={"landfall_utc": "previous_landfall_utc",
                                                    "landfall_source": "previous_landfall_source"})
    origin = pd.read_parquet(INTERIM / "storm_time_origin.parquet")[["nhc_id", "time_origin_utc", "time_origin_source",
                                                                     "interim_origin_utc"]]
    lf = origin.rename(columns={"time_origin_utc": "landfall_utc", "time_origin_source": "landfall_source",
                                "interim_origin_utc": "interim_landfall_utc"}).merge(prev, on="nhc_id",
                                                                                      validate="one_to_one")
    p = p.merge(lf, on="nhc_id", how="left", validate="many_to_one")
    p["days_since_landfall"] = (p.as_of_utc - p.landfall_utc).dt.total_seconds() / 86400
    p["days_since_landfall_previous_rule"] = (p.as_of_utc - p.previous_landfall_utc).dt.total_seconds() / 86400
    p["days_since_landfall_interim_rule"] = (p.as_of_utc - p.interim_landfall_utc).dt.total_seconds() / 86400
    p["time_flag"] = p.doc_id.map(TIME_FLAGS).fillna("")
    check_time_flags(p)
    ex_cols = ["nhc_id", "fips", "min_dist_km", "wind_kt_at_closest", "in_34kt", "in_50kt", "in_64kt",
               "first_34kt_utc", "nearest_landfall_utc", "nearest_landfall_km", "track_source"]
    p = p.merge(exposure[ex_cols], on=["nhc_id", "fips"], how="left", validate="many_to_one")
    p = p.merge(covariates.drop(columns=["acs_name"]), on="fips", how="left", validate="many_to_one")
    p = p.merge(fema, on=["nhc_id", "fips"], how="left", validate="many_to_one")
    p["fema_declared"] = p.fema_dr.notna()
    p = p.merge(county_spans(p), on=["storm_key", "fips"], how="left", validate="many_to_one")
    if p.report_status.isna().any() or (p.report_status == "excluded").any():
        raise SystemExit("panel has a report with no validation status, or an excluded report")
    require_carried(p, "panel")
    PROCESSED.mkdir(parents=True, exist_ok=True)
    p.to_parquet(PROCESSED / "panel.parquet", index=False)

    s = p.groupby("storm_key").agg(nhc_id=("nhc_id", "first"), storm=("storm", "first"),
                                   dirs_activation_date=("dirs_activation_date", "first"),
                                   rule_period=("rule_period", "first"), landfall_utc=("landfall_utc", "first"),
                                   landfall_source=("landfall_source", "first"),
                                   previous_landfall_utc=("previous_landfall_utc", "first"),
                                   interim_landfall_utc=("interim_landfall_utc", "first"), n_reports=("doc_id", "nunique"),
                                   n_counties=("fips", "nunique"), first_report=("report_date", "min"),
                                   last_report=("report_date", "max")).reset_index()
    ex_by_storm = excluded.merge(all_rows.drop_duplicates(["doc_id", "row_nhc_id"]), on="doc_id")
    ex_by_storm = ex_by_storm.groupby("row_nhc_id").apply(
        lambda g: "; ".join(f"{d.doc_id} ({d.report_date}): {d.reason}" for d in g.itertuples()), include_groups=False)
    all_storms = storms[["nhc_id", "storm_name", "dirs_activation_date"]].assign(
        storm_key=lambda x: x.nhc_id + "_" + x.dirs_activation_date.astype(str))
    s = all_storms.merge(s.drop(columns=["nhc_id", "dirs_activation_date"]), on="storm_key", how="left")
    s["storm"] = s.storm.fillna(s.storm_name)
    s["excluded_reports"] = s.nhc_id.map(ex_by_storm).fillna("")
    s["in_panel"] = s.n_reports.notna()
    s.drop(columns="storm_name").to_parquet(PROCESSED / "storms.parquet", index=False)

    pub = p[PUBLIC_COLUMNS].sort_values(["storm_key", "report_date", "state", "county"])
    require_carried(pub, "dirs_county_day.csv")
    pub.to_csv(PROCESSED / "dirs_county_day.csv", index=False, lineterminator="\n")
    print(f"panel {len(p):,} rows, {p.doc_id.nunique()} reports, {p.storm_key.nunique()} storms, {p.fips.nunique()} counties")
    print("storms not in the panel:", s[~s.in_panel][["storm", "excluded_reports"]].values.tolist())
    print("censoring (storm-counties):", p.drop_duplicates(["storm_key", "fips"]).censoring.value_counts().to_dict())


if __name__ == "__main__":
    main()
