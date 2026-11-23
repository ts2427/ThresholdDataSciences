"""Step 10: every number on the page, written to output/results.json.

Chapters (see CLAUDE.md and docs/analysis_plan.md):
 2 Isaias anatomy: county % out by day; track; no power overlay (EAGLE-I ends in 2025): the page says so
 3 Storm comparison (storm list and count come from manifest/dirs_reports.csv, never hard-coded):
   peak sites out (abs, %), cable/wireline subscribers out, normalized to landfall
 4 Recovery curves: share of affected sites restored by day since peak; county bootstrap bands;
   time to 50%/90%; site-days lost ("resilience triangle")
 5 Causes: damage / transport / power / unattributed shares by day and storm, each a share of sites out
   (not of attributed sites); out_overattributed share shown beside them, never netted; reports without
   cause columns are 'not collected' and left out of the denominators; backup-power line
 6 Power coupling (power overlay for storms through 2025; the page says Isaias 2026 has none):
   % customers without power vs % sites out due to power at matched times; lead/lag
 7 Exposure: peak % out vs distance to track and wind; simple calibrated model
 8 Equity: time to restoration (< 5% out) by SVI quartile; discrete-time hazard (cloglog) with
   exposure and storm fixed effects, county-clustered SEs; interval- and right-censoring handled
 9 Regimes: descriptive pre/post comparison; explicit caveats
Rules: associations only; report uncertainty; all thresholds set in the config block below.

Chapter 3 (built 2026-11-22). For each storm in the panel, the peak is the report with the most sites out in the
study states (ties: the earlier report); its % out uses that report's sites served. Uncertainty: 95% county
bootstrap (counties resampled with replacement within the storm, peak recomputed in each draw); the peak's
timing lies between the neighbouring snapshots. Cable and wireline subscribers out are the report's printed area
total, with no interval, flagged where that area included out-of-scope states or the report was shared by two
storms. Across storms: median with a storm-bootstrap interval and the range.
"""
import json
import math
import re
import sys

import numpy as np
import pandas as pd

from config import INTERIM, MANIFEST, OUTPUT, PROCESSED, REGIMES, STUDY_STATES

# ---- config block: every threshold and setting ----
SEED = 20261122
BOOTSTRAP_DRAWS = 2000
CI = (2.5, 97.5)
STATE_TOTAL_MISSING_DOCS = ("DOC-405893A1",)  # kept by the state_total_missing rule (Helene Sep 28, 2024)
UNFLAGGED_STATUSES = ("ok", "known_fcc_inconsistency")
# Flag types (deviation 5b, 2026-11-22). Fragments of the two longer messages count with them.
SERIOUS_FLAGS = [r"^headline_mismatch", r"^state_total_missing", r"^no_printed_totals", r"rows outside_notice_area$",
                 r"rows table_not_in_list$", r"^in table, not in the report's county list"]
BENIGN_FLAGS = [r"rows short of sites out", r"^FCC spelling", r"rows inside_spelling_variant$",
                r"^causes exceed sites out, confirmed by second reading", r"^causes exceed sites out, listed exception",
                r"^listed more than once by the FCC", r"^in table, not in the report's list, listed exception",
                r"^headline [\d.]+% vs [\d.]+% from the report's own totals",
                r"^every row confirmed by second reading$", r"^other states reconcile\)$"]
PAGE_NOTE_UNDERSTATED = ("Laura",)  # author's instruction 2026-11-22: excluded reports right after the peak
PAGE_NOTE_FEW_COUNTIES = ("Beryl",)  # author's instruction 2026-11-22
MICHAEL_JEFFERSON_FIPS = "12065"  # 261 sites served as printed (open plan item); shown with and without
RESULTS = OUTPUT / "results.json"
PERIOD_CODES = ["P0", "P1", "P2", "P3"]  # in the order of config.REGIMES, as in step 9


def num(value, ci_low=None, ci_high=None, n=None, unit="", method="", **extra) -> dict:
    """One headline number: value, its uncertainty, its count, unit and how the interval was made."""
    rec = {"value": _plain(value), "ci_low": _plain(ci_low), "ci_high": _plain(ci_high), "n": _plain(n),
           "unit": unit, "method": method}
    rec.update({k: _plain(v) for k, v in extra.items()})
    return rec


def _plain(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def write_chapter(path, key: str, content: dict) -> None:
    results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    results[key] = content
    path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---- chapter 3: peak outages ----

def report_totals(p: pd.DataFrame) -> pd.DataFrame:
    """One row per storm and report: summed sites out and served over the counties it lists."""
    g = p.groupby(["storm_key", "doc_id"])
    t = g.agg(storm=("storm", "first"), report_date=("report_date", "first"),
              days_since_landfall=("days_since_landfall", "first"), sites_out=("sites_out", "sum"),
              sites_served=("sites_served", "sum"), n_counties=("fips", "nunique"),
              cable_wireline_subs_out=("cable_wireline_subs_out", "first"),
              area_includes_out_of_scope=("area_includes_out_of_scope", "first"),
              report_shared_by_storms=("report_shared_by_storms", "first"),
              report_status=("report_status", "first")).reset_index()
    t["pct_out"] = 100 * t.sites_out / t.sites_served
    return t.sort_values(["storm_key", "days_since_landfall", "doc_id"], ignore_index=True)


def peak_report(t: pd.DataFrame) -> pd.Series:
    """The report with the most sites out (ties: the earliest)."""
    t = t.sort_values(["days_since_landfall", "doc_id"])
    return t.loc[t.sites_out.idxmax()]


def peak_timing_interval(t: pd.DataFrame, peak: pd.Series) -> tuple:
    """Days since landfall of the snapshots before and after the peak (None at either end)."""
    s = t[t.storm_key == peak.storm_key].sort_values("days_since_landfall").reset_index(drop=True)
    i = s.index[s.doc_id == peak.doc_id][0]
    lo = s.days_since_landfall[i - 1] if i > 0 else None
    hi = s.days_since_landfall[i + 1] if i + 1 < len(s) else None
    return (_plain(lo), _plain(hi))


def bootstrap_peak(p: pd.DataFrame, draws: int = BOOTSTRAP_DRAWS, seed: int = SEED) -> dict:
    """County bootstrap of one storm's peak: resample counties, recompute report totals, take the peak."""
    rng = np.random.default_rng(seed)
    out = p.pivot_table(index="fips", columns="doc_id", values="sites_out", aggfunc="sum", fill_value=0)
    served = p.pivot_table(index="fips", columns="doc_id", values="sites_served", aggfunc="sum", fill_value=0)
    served = served.reindex(index=out.index, columns=out.columns, fill_value=0)
    n = len(out)
    w = rng.multinomial(n, np.full(n, 1 / n), size=draws)  # draws x counties
    tot_out, tot_served = w @ out.to_numpy(float), w @ served.to_numpy(float)
    order =np.argsort(p.drop_duplicates("doc_id").set_index("doc_id").days_since_landfall.reindex(out.columns).to_numpy())
    tot_out, tot_served = tot_out[:, order], tot_served[:, order]
    j = tot_out.argmax(axis=1)  # ties go to the earliest report, as in peak_report
    rows = np.arange(draws)
    with np.errstate(invalid="ignore", divide="ignore"):
        pct = 100 * tot_out[rows, j] / tot_served[rows, j]
    return {"sites_out": tot_out[rows, j], "pct_out": pct}


def median_across(values, draws: int = BOOTSTRAP_DRAWS, seed: int = SEED, unit: str = "") -> dict:
    v = np.asarray(values, float)
    rng = np.random.default_rng(seed)
    boot = np.median(rng.choice(v, size=(draws, len(v)), replace=True), axis=1)
    lo, hi = np.percentile(boot, CI)
    return num(np.median(v), lo, hi, n=len(v), unit=unit, method="median across storms; storm bootstrap 95%",
               min=v.min(), max=v.max())


def storm_peak(p: pd.DataFrame, seed: int) -> dict:
    t = report_totals(p)
    pk = peak_report(t)
    b = bootstrap_peak(p, seed=seed)
    lo_c, hi_c = np.percentile(b["sites_out"], CI)
    lo_p, hi_p = np.nanpercentile(b["pct_out"], CI)
    lo_t, hi_t = peak_timing_interval(t, pk)
    method = f"county bootstrap 95%, {BOOTSTRAP_DRAWS} draws"
    return {
        "peak_doc_id": pk.doc_id, "peak_report_date": pk.report_date, "peak_report_status": pk.report_status,
        "peak_sites_out": num(pk.sites_out, lo_c, hi_c, n=pk.n_counties, unit="cell sites out", method=method),
        "peak_pct_out": num(pk.pct_out, lo_p, hi_p, n=pk.n_counties, unit="% of sites served", method=method),
        "sites_served_at_peak": num(pk.sites_served, n=pk.n_counties, unit="cell sites served", method="as printed"),
        "peak_days_since_landfall": num(pk.days_since_landfall, lo_t, hi_t, n=len(t), unit="days",
                                        method="snapshot time; true peak lies between the neighbouring snapshots"),
        "cable_wireline_subs_out_at_peak": num(pk.cable_wireline_subs_out, n=1, unit="subscribers out (report area)",
                                               method="as printed; no interval",
                                               area_includes_out_of_scope=bool(pk.area_includes_out_of_scope),
                                               report_shared_by_storms=bool(pk.report_shared_by_storms)),
        "max_pct_report_differs": bool(t.loc[t.pct_out.idxmax(), "doc_id"] != pk.doc_id),
        "n_reports": len(t),
    }


def drop_one_medians(by_storm: dict) -> dict:
    """Median across storms with each storm left out in turn (sensitivity display 1)."""
    return {k: float(np.median([v for kk, v in by_storm.items() if kk != k])) for k in by_storm}


def without_flagged(p: pd.DataFrame) -> pd.DataFrame:
    """Only reports with status ok or known_fcc_inconsistency (sensitivity display 5)."""
    return p[p.report_status.isin(UNFLAGGED_STATUSES)]


def has_serious_flag(flags: str) -> bool:
    serious = False
    for part in filter(None, (flags or "").split("; ")):
        if any(re.search(p, part) for p in SERIOUS_FLAGS):
            serious = True
        elif not any(re.search(p, part) for p in BENIGN_FLAGS):
            raise ValueError(f"unknown flag type, not classified: {part}")
    return serious


def without_serious(p: pd.DataFrame) -> pd.DataFrame:
    """Drop only reports with a serious flag (sensitivity display 5b)."""
    serious = {d: has_serious_flag(f) for d, f in p.drop_duplicates("doc_id")[["doc_id", "report_flags"]].values}
    return p[~p.doc_id.map(serious)]


def _and_list(items: list) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def chapter_3_page_notes(per_storm: list, small_county_storms=PAGE_NOTE_FEW_COUNTIES,
                         understated_storms=PAGE_NOTE_UNDERSTATED) -> dict:
    notes = {}
    for r in per_storm:
        if r["storm"] in understated_storms and r["excluded_reports"]:
            dates = [d for d in re.findall(r"\((\d{4}-\d\d-\d\d)\)", r["excluded_reports"]) if d > r["peak_report_date"]]
            if dates:
                notes[r["storm"]] = (f"{r['storm']}'s peak may be understated: its reports of {_and_list(dates)}, "
                                     f"after the peak report of {r['peak_report_date']}, are excluded.")
        if r["storm"] in small_county_storms:
            notes[r["storm"]] = f"{r['storm']}'s peak share comes from {r['n_counties']} counties."
    return notes


def _peak_points(panel: pd.DataFrame) -> dict:
    out = {}
    for key, p in panel.groupby("storm_key"):
        pk = peak_report(report_totals(p))
        out[key] = {"storm": pk.storm, "peak_report_date": pk.report_date, "peak_sites_out": _plain(pk.sites_out),
                    "peak_pct_out": _plain(pk.pct_out), "n_reports": int(p.doc_id.nunique())}
    return out


def chapter_3_sensitivity(panel: pd.DataFrame, per_storm: list) -> dict:
    pct = {r["storm"]: r["peak_pct_out"]["value"] for r in per_storm}
    drop = drop_one_medians(pct)
    unflagged = _peak_points(without_flagged(panel))
    unserious = _peak_points(without_serious(panel))
    no_stm = panel[~panel.doc_id.isin(STATE_TOTAL_MISSING_DOCS)]
    helene = [k for k in panel.storm_key.unique() if panel[panel.storm_key == k].doc_id.isin(STATE_TOTAL_MISSING_DOCS).any()]
    return {
        "drop_one_storm_median_peak_pct_out": {"by_storm_left_out": drop, "min": min(drop.values()), "max": max(drop.values()),
                                               "n": len(drop)},
        "without_flagged_reports": {"n_storms_with_an_unflagged_report": len(unflagged), "storms": unflagged,
                                    "median_peak_pct_out": float(np.median([v["peak_pct_out"] for v in unflagged.values()]))
                                    if unflagged else None},
        "without_serious_flag_reports": {
            "n_storms": len(unserious), "storms": unserious,
            "median_peak_pct_out": float(np.median([v["peak_pct_out"] for v in unserious.values()])) if unserious else None,
            "note": "deviation 5b, added after the chapter 3 result was seen"},
        "without_state_total_missing_reports": {"docs": list(STATE_TOTAL_MISSING_DOCS),
                                                "storms": _peak_points(no_stm[no_stm.storm_key.isin(helene)])},
    }


def chapter_3(panel: pd.DataFrame, storms: pd.DataFrame, manifest: pd.DataFrame) -> dict:
    in_scope = manifest[manifest.status != "out_of_scope"]
    per_storm, order = [], storms[storms.in_panel].sort_values("landfall_utc")
    for i, s in enumerate(order.itertuples()):
        p = panel[panel.storm_key == s.storm_key]
        rec = {"storm_key": s.storm_key, "storm": s.storm, "nhc_id": s.nhc_id, "rule_period": s.rule_period,
               "landfall_utc": str(s.landfall_utc), "landfall_source": s.landfall_source,
               "excluded_reports": s.excluded_reports, "n_counties": int(p.fips.nunique()),
               **storm_peak(p, SEED + i)}
        if s.storm == "Michael":
            alt = storm_peak(p[p.fips != MICHAEL_JEFFERSON_FIPS], SEED + i)
            j = panel[panel.fips == MICHAEL_JEFFERSON_FIPS]
            here, other = j[j.storm_key == s.storm_key].sites_served, j[j.storm_key != s.storm_key].sites_served
            rec["jefferson_fl_flag"] = {
                "flag": "apparent FCC denominator error", "fips": MICHAEL_JEFFERSON_FIPS,
                "sites_served_this_storm": num(here.median(), n=len(here), unit="sites served", min=here.min(), max=here.max(),
                                               method="as printed; median and range across this storm's reports"),
                "sites_served_other_storms": num(other.median(), n=len(other), min=other.min(), max=other.max(),
                                                 unit="sites served", method="median and range across later storms' reports")}
            rec["without_jefferson_fl"] = {"peak_sites_out": alt["peak_sites_out"], "peak_pct_out": alt["peak_pct_out"]}
        per_storm.append(rec)
    pct = [r["peak_pct_out"]["value"] for r in per_storm]
    cnt = [r["peak_sites_out"]["value"] for r in per_storm]
    big_n = max(per_storm, key=lambda r: r["peak_sites_out"]["value"])
    big_p = max(per_storm, key=lambda r: r["peak_pct_out"]["value"])
    headlines = {
        "n_storms_in_manifest": num(in_scope.nhc_id.nunique(), n=len(in_scope), unit="storms (in-scope reports)",
                                    method="count from manifest/dirs_reports.csv"),
        "n_storms_with_peak": num(len(per_storm), n=int(order.n_reports.sum()), unit="storms",
                                  method="storms with at least one report in use"),
        "storms_without_peak": storms[~storms.in_panel][["storm", "excluded_reports"]].to_dict("records"),
        "largest_peak_sites_out": {"storm": big_n["storm"], **big_n["peak_sites_out"]},
        "largest_peak_pct_out": {"storm": big_p["storm"], **big_p["peak_pct_out"]},
        "median_peak_pct_out": median_across(pct, unit="% of sites served"),
        "median_peak_sites_out": median_across(cnt, unit="cell sites out"),
    }
    return {"headlines": headlines, "storms": per_storm, "sensitivity": chapter_3_sensitivity(panel, per_storm),
            "page_notes": chapter_3_page_notes(per_storm),
            "notes": ["Peak = the report with the most cell sites out in the study states; % uses that report's sites served.",
                      "Each storm's counties are those its reports list; the county set changes during a storm.",
                      "Cable and wireline subscribers out are printed for the report's whole area."]}


# ---- chapter 4: recovery ----

def stay_index(values, threshold: float, below: bool = False):
    """Rebound rule: the first index from which every later value is past the threshold (None if none)."""
    v = np.asarray(values, float)
    past = v < threshold if below else v >= threshold
    ok = np.logical_and.accumulate(past[::-1])[::-1]  # past from here to the end
    idx = np.flatnonzero(ok)
    return int(idx[0]) if len(idx) else None


def first_index(values, threshold: float, below: bool = False):
    """First crossing (sensitivity display): the first index past the threshold."""
    v = np.asarray(values, float)
    idx = np.flatnonzero(v < threshold if below else v >= threshold)
    return int(idx[0]) if len(idx) else None


def stay_index_rows(m: np.ndarray, threshold: float) -> np.ndarray:
    """stay_index for each row of a matrix (draws x reports); -1 where never; NaN counts as not past."""
    past = np.nan_to_num(m, nan=-np.inf) >= threshold
    ok = np.logical_and.accumulate(past[:, ::-1], axis=1)[:, ::-1]
    return np.where(ok.any(axis=1), ok.argmax(axis=1), -1)


def _recovery_matrix(p: pd.DataFrame):
    """Peak-report counties x reports from the peak on: main (absent = last reported) and best (absent = 0)."""
    pk = peak_report(report_totals(p))
    reports = (p.drop_duplicates("doc_id")[["doc_id", "days_since_landfall"]]
               .sort_values(["days_since_landfall", "doc_id"]))
    reports = reports[reports.days_since_landfall >= pk.days_since_landfall].reset_index(drop=True)
    counties = sorted(p[p.doc_id == pk.doc_id].fips.unique())
    raw = (p[p.fips.isin(counties)].pivot_table(index="fips", columns="doc_id", values="sites_out", aggfunc="sum")
           .reindex(index=counties, columns=reports.doc_id))
    main = raw.ffill(axis=1).to_numpy(float)
    best = raw.fillna(0).to_numpy(float)
    days = (reports.days_since_landfall - pk.days_since_landfall).to_numpy(float)
    return pk, reports, days, main, best, raw.isna().to_numpy()


def recovery_curve(p: pd.DataFrame) -> pd.DataFrame:
    pk, reports, days, main, best, absent = _recovery_matrix(p)
    affected = main[:, 0].sum()
    return pd.DataFrame({"doc_id": reports.doc_id, "days_since_peak": days, "sites_out": main.sum(axis=0),
                         "sites_out_best": best.sum(axis=0),
                         "restored_share": 1 - main.sum(axis=0) / affected,
                         "restored_share_best": 1 - best.sum(axis=0) / affected,
                         "n_counties": main.shape[0], "n_carried": absent.sum(axis=0),
                         "affected_sites": affected})


def time_to(curve: pd.DataFrame, threshold: float, column: str, rule=stay_index) -> dict:
    i = rule(curve[column].to_numpy(), threshold)
    d = curve.days_since_peak.to_numpy()
    if i is None:
        return {"value": None, "interval_low": None, "censored": True, "censored_at": _plain(d[-1])}
    return {"value": _plain(d[i]), "interval_low": _plain(d[i - 1]) if i > 0 else None, "censored": False,
            "censored_at": None}


def site_days_lost(curve: pd.DataFrame) -> dict:
    d, y = curve.days_since_peak.to_numpy(), curve.sites_out.to_numpy(float)
    gap = np.diff(d)
    return {"value": _plain(float(np.sum(gap * (y[:-1] + y[1:]) / 2))), "lower": _plain(float(np.sum(gap * y[1:]))),
            "upper": _plain(float(np.sum(gap * y[:-1]))), "gaps_over_one_day": int((gap > 1.0 + 1e-9).sum()),
            "days_covered": _plain(float(d[-1]))}


def bootstrap_recovery(p: pd.DataFrame, draws: int = BOOTSTRAP_DRAWS, seed: int = SEED) -> dict:
    """County bootstrap of the peak-report counties: restored share by report, time to 50%/90%, site-days lost."""
    _, _, days, main, _, _ = _recovery_matrix(p)
    rng = np.random.default_rng(seed)
    n = main.shape[0]
    w = rng.multinomial(n, np.full(n, 1 / n), size=draws)
    out = w @ main
    with np.errstate(invalid="ignore", divide="ignore"):
        share = 1 - out / out[:, [0]]
    res = {"share": share, "days": days}
    for label, thr in (("t50", 0.5), ("t90", 0.9)):
        i = stay_index_rows(share, thr)
        res[label] = np.where(i >= 0, days[np.clip(i, 0, None)], np.inf)
    gap = np.diff(days)
    res["site_days"] = (out[:, :-1] + out[:, 1:]) / 2 @ gap if len(gap) else np.zeros(draws)
    return res


def _time_ci(draws: np.ndarray) -> tuple:
    lo, hi = np.percentile(draws, CI)
    return (_plain(lo) if np.isfinite(lo) else None, _plain(hi) if np.isfinite(hi) else None)


def median_with_censoring(values, censored) -> float | None:
    """Median across storms, given only when censoring cannot move it (correction, 2026-11-22): the median with
    each censored storm at its censoring time must equal the median with it above every time. Otherwise None
    ("no median (censored)"). values hold each censored storm's censoring time."""
    v, c = np.asarray(values, float), np.asarray(censored, bool)
    low = float(np.median(v))
    high = float(np.median(np.where(c, np.inf, v)))
    return low if np.isfinite(high) and low == high else None


def storm_recovery(p: pd.DataFrame, seed: int) -> dict:
    c = recovery_curve(p)
    b = bootstrap_recovery(p, seed=seed)
    band = np.nanpercentile(b["share"], CI, axis=0)
    method = f"county bootstrap 95% of the peak-report counties, {BOOTSTRAP_DRAWS} draws"
    rec = {"affected_sites": num(c.affected_sites.iloc[0], n=int(c.n_counties.iloc[0]), unit="sites out at the peak",
                                 method="as printed"),
           "n_reports_after_peak": len(c) - 1,
           "curve": [{"days_since_peak": _plain(r.days_since_peak), "sites_out": _plain(r.sites_out),
                      "restored_share": _plain(r.restored_share), "ci_low": _plain(band[0][i]),
                      "ci_high": _plain(band[1][i]), "restored_share_best": _plain(r.restored_share_best),
                      "n_counties_carried": int(r.n_carried)} for i, r in enumerate(c.itertuples())]}
    for label, thr in (("t50", 0.5), ("t90", 0.9)):
        main, best, first = (time_to(c, thr, "restored_share"), time_to(c, thr, "restored_share_best"),
                             time_to(c, thr, "restored_share", rule=first_index))
        lo, hi = _time_ci(b[label])
        rec[f"time_to_{label[1:]}pct_restored"] = num(
            main["value"], lo, hi, n=int(c.n_counties.iloc[0]), unit="days since peak", method=method,
            interval_low=main["interval_low"], censored=main["censored"], censored_at=main["censored_at"],
            share_of_draws_not_reached=_plain(float(np.mean(~np.isfinite(b[label])))),
            best_case=best["value"], best_case_censored=best["censored"],
            first_crossing=first["value"], first_crossing_censored=first["censored"])
    sd = site_days_lost(c)
    lo, hi = np.percentile(b["site_days"], CI)
    rec["site_days_lost"] = num(sd["value"], lo, hi, n=int(c.n_counties.iloc[0]), unit="site-days, peak to last report",
                                method=method, lower_bound=sd["lower"], upper_bound=sd["upper"],
                                gaps_over_one_day=sd["gaps_over_one_day"], days_covered=sd["days_covered"])
    return rec


def _recovery_points(panel: pd.DataFrame) -> dict:
    out = {}
    for key, p in panel.groupby("storm_key"):
        c = recovery_curve(p)
        out[key] = {"storm": p.storm.iloc[0], "n_reports": int(p.doc_id.nunique()),
                    "t50": time_to(c, 0.5, "restored_share")["value"], "t90": time_to(c, 0.9, "restored_share")["value"],
                    "t90_censored": time_to(c, 0.9, "restored_share")["censored"],
                    "site_days_lost": site_days_lost(c)["value"]}
    return out


NO_RECOVERY_NOTE = "{storm}: no report after its peak, so no recovery could be observed."


def recovery_observed(per_storm: list) -> list:
    """Storms with at least one report after the peak (correction, 2026-11-23: the others, Nicole, are left out of every
    time and site-days summary and footnoted)."""
    return [r for r in per_storm if r["n_reports_after_peak"] > 0]


LEAVING_NOTE = ("The FCC's reporting area narrows as outages fall, so a county leaving the reports is consistent with "
                "recovery but does not prove it.")


def storms_reaching(per_storm: list, label: str) -> dict:
    """Storms reaching the threshold with leaving counties kept out (main) and counted restored (best case)."""
    k = f"time_to_{label}pct_restored"
    out = [r["storm"] for r in per_storm if not r[k]["censored"]]
    best = [r["storm"] for r in per_storm if not r[k]["best_case_censored"]]
    lo, hi = sorted((len(out), len(best)))
    return {"value": f"{lo} to {hi}" if lo != hi else str(lo), "min": lo, "max": hi, "n": len(per_storm),
            "unit": "storms", "method": "range over the two treatments of counties that leave the reports",
            "counties_leaving_stay_out": out, "counties_leaving_restored": best, "note": LEAVING_NOTE}


def chapter_4(panel: pd.DataFrame, storms: pd.DataFrame) -> dict:
    per_storm = []
    order = storms[storms.in_panel].sort_values("landfall_utc")
    for i, s in enumerate(order.itertuples()):
        p = panel[panel.storm_key == s.storm_key]
        per_storm.append({"storm_key": s.storm_key, "storm": s.storm, "rule_period": s.rule_period,
                          "excluded_reports": s.excluded_reports, **storm_recovery(p, SEED + 100 + i)})
    heads = {}
    seen = recovery_observed(per_storm)
    heads["storms_left_out_of_time_summaries"] = [{"storm": r["storm"], "note": NO_RECOVERY_NOTE.format(storm=r["storm"])}
                                                  for r in per_storm if r not in seen]
    for label in ("50", "90"):
        k = f"time_to_{label}pct_restored"
        vals = [r[k]["value"] if r[k]["value"] is not None else r[k]["censored_at"] for r in seen]
        cens = [r[k]["censored"] for r in seen]
        rng = np.random.default_rng(SEED + int(label))
        idx = rng.integers(0, len(vals), size=(BOOTSTRAP_DRAWS, len(vals)))
        boot = [median_with_censoring(np.array(vals)[j], np.array(cens)[j]) for j in idx]
        boot = np.array([np.inf if b is None else b for b in boot])
        lo, hi = _time_ci(boot)
        heads[f"median_{k}"] = num(median_with_censoring(vals, cens), lo, hi, n=len(vals), unit="days since peak",
                                   method="median across storms, censored storms above every observed time; storm bootstrap 95%",
                                   n_censored=int(sum(cens)))
        drop = {}
        for r in seen:
            keep = [(v, c) for v, c, rr in zip(vals, cens, seen) if rr["storm"] != r["storm"]]
            drop[r["storm"]] = median_with_censoring([v for v, _ in keep], [c for _, c in keep])
        heads[f"drop_one_storm_median_{k}"] = drop
    heads["n_storms_reaching_50pct_restored"] = storms_reaching(seen, "50")
    heads["n_storms_reaching_90pct_restored"] = storms_reaching(seen, "90")
    sd = [r["site_days_lost"]["value"] for r in seen]
    heads["median_site_days_lost"] = median_across(sd, unit="site-days, peak to last report")
    no_stm = panel[~panel.doc_id.isin(STATE_TOTAL_MISSING_DOCS)]
    affected_keys = panel[panel.doc_id.isin(STATE_TOTAL_MISSING_DOCS)].storm_key.unique()
    sensitivity = {
        "first_crossing": "per storm: time_to_*pct_restored.first_crossing",
        "best_and_worst_case_for_counties_leaving_the_reports": "per storm: main (absent counties keep their last value) and best_case (absent counties restored)",
        "hold_sites_served_at_peak": "not applicable: restored shares use counts, not sites served",
        "without_flagged_reports": _recovery_points(without_flagged(panel)),
        "without_serious_flag_reports": _recovery_points(without_serious(panel)),
        "without_state_total_missing_reports": _recovery_points(no_stm[no_stm.storm_key.isin(affected_keys)]),
    }
    exhibit = {"type": "restored share by day since peak, one panel per storm",
               "series": [{"field": "restored_share", "label": "counties leaving the reports stay out (main)",
                           "band": ["ci_low", "ci_high"]},
                          {"field": "restored_share_best", "label": "counties leaving the reports counted restored"}],
               "both_bounds_for_every_storm": True, "mark_rule_periods": True, "caption_note": LEAVING_NOTE}
    return {"headlines": heads, "storms": per_storm, "sensitivity": sensitivity, "exhibit": exhibit,
            "notes": ["Affected = sites out at the peak in the counties of the peak report; restored share = 1 - sites out / affected.",
                      "A county absent from a later report keeps its last reported value (censored, not recovered); best case counts it restored.",
                      "Time to 50% / 90%: the first report from which the share stays past the threshold in every later report; the true time lies after the report before.",
                      "Site-days lost run from the peak to the storm's last report only.",
                      LEAVING_NOTE]}


# ---- chapter 5: causes ----

CAUSE_COLS = ["out_damage", "out_transport", "out_power"]
SHARE_COLS = {"damage": "out_damage", "transport": "out_transport", "power": "out_power",
              "unattributed": "out_unattributed", "overattributed": "out_overattributed"}
FCC_MULTIPLE_CAUSES_NOTE = ("The number of total cell sites out may differ from the sum of numbers of cell sites out by "
                            "cause. This is due to sites being out due to multiple causes or because providers are still "
                            "assessing the causes of some sites being out of service.")
OVERATTRIBUTION_WORDING = ("Causes exceeding sites out are read as consistent with sites out for more than one cause, "
                           "and are not treated as an FCC error.")
# External check (chapter 5 methods note): Olukola, Addeh, Konan & Rahimi (2026), arXiv:2609.10944 v1, VERIFIED in
# docs/literature.md: pooled shares of attributed cell-site-days for Helene (damage: abstract; power and transport:
# section 1 "Scope").
OLUKOLA_HELENE_ATTRIBUTED = {"damage": 1.1, "power": 63.2, "transport": 35.7}
OLUKOLA_CITATION = "Olukola, Addeh, Konan & Rahimi (2026), arXiv:2609.10944"
CH5_STORM_FIELDS = ("storm_key", "storm")  # no rule period: cause shares are compared across periods only in ch. 9
OVERATTRIBUTION_INFERENCE = ("This report does not print the FCC's multiple-causes note, so for it that reading is an "
                             "inference.")


def has_causes(p: pd.DataFrame) -> bool:
    return bool(p[CAUSE_COLS].notna().all(axis=1).any())


def cause_by_report(p: pd.DataFrame) -> pd.DataFrame:
    """Per report: cause counts over rows with all three causes; rows without are counted apart (not collected)."""
    q = p.assign(_has=p[CAUSE_COLS].notna().all(axis=1), _bk=p.on_backup_power.notna())
    rows = []
    for (_, doc), g in q.groupby(["storm_key", "doc_id"], sort=False):  # Ida and Nicholas share reports
        c, b = g[g._has], g[g._bk]
        rows.append({"storm_key": g.storm_key.iloc[0], "storm": g.storm.iloc[0], "doc_id": doc,
                     "report_date": g.report_date.iloc[0], "days_since_landfall": g.days_since_landfall.iloc[0],
                     "sites_out": c.sites_out.sum(), "sites_out_not_collected": g[~g._has].sites_out.sum(),
                     **{col: c[col].sum() for col in SHARE_COLS.values()},
                     "on_backup_power": b.on_backup_power.sum(), "served_with_backup_column": b.sites_served.sum(),
                     "fcc_multiple_causes_note": bool(g.fcc_multiple_causes_note.fillna(False).astype(bool).any())})
    r = pd.DataFrame(rows)
    with np.errstate(invalid="ignore", divide="ignore"):
        r["backup_pct_of_served"] = np.where(r.served_with_backup_column > 0,
                                             100 * r.on_backup_power / r.served_with_backup_column, np.nan)
    return r.sort_values(["days_since_landfall", "doc_id"], ignore_index=True)


def attributed_only(shares: dict) -> dict:
    """Damage, transport and power as shares of the three together (for the external check only)."""
    base = sum(shares[k] for k in ("damage", "transport", "power"))
    return {k: 100 * shares[k] / base for k in ("damage", "transport", "power")}


def cause_shares(counts) -> dict:
    out = float(counts["sites_out"])
    return {k: (100 * float(counts[col]) / out if out else None) for k, col in SHARE_COLS.items()}


def pooled_shares(by_report: pd.DataFrame) -> dict:
    tot = by_report[["sites_out", *SHARE_COLS.values()]].sum()
    return {**cause_shares(tot), "sites_out": _plain(tot.sites_out)}


def bootstrap_cause_shares(p: pd.DataFrame, draws: int = BOOTSTRAP_DRAWS, seed: int = SEED) -> dict:
    """County bootstrap: each county's counts summed over the storm's reports, counties resampled."""
    c = p[p[CAUSE_COLS].notna().all(axis=1)].groupby("fips")[["sites_out", *SHARE_COLS.values()]].sum()
    rng = np.random.default_rng(seed)
    n = len(c)
    w = rng.multinomial(n, np.full(n, 1 / n), size=draws)
    tot = w @ c.to_numpy(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return {k: 100 * tot[:, 1 + i] / tot[:, 0] for i, k in enumerate(SHARE_COLS)}


def _share_nums(point: dict, boot: dict, n: int, method: str) -> dict:
    out = {}
    for k in SHARE_COLS:
        lo, hi = np.nanpercentile(boot[k], CI)
        out[k] = num(point[k], lo, hi, n=n, unit="% of sites out", method=method)
    return out


def storm_causes(p: pd.DataFrame, seed: int) -> dict:
    r = cause_by_report(p)
    with_c = r[r.sites_out > 0]
    boot = bootstrap_cause_shares(p, seed=seed)
    n_cty = int(p[p[CAUSE_COLS].notna().all(axis=1)].fips.nunique())
    method = f"county bootstrap 95%, {BOOTSTRAP_DRAWS} draws"
    pk = peak_report(report_totals(p))
    pk_row = r[r.doc_id == pk.doc_id].iloc[0]
    note_docs = r[r.fcc_multiple_causes_note].doc_id.tolist()
    return {
        "pooled_over_reports": {**_share_nums(pooled_shares(with_c), boot, n_cty, method),
                                "sites_out_report_sum": num(with_c.sites_out.sum(), n=len(with_c),
                                                            unit="sites out, summed over reports", method="as printed")},
        "at_peak_report": {"doc_id": pk.doc_id, "report_date": pk.report_date,
                           **{k: num(v, n=int(pk.n_counties), unit="% of sites out", method="as printed")
                              for k, v in cause_shares(pk_row).items()}},
        "by_report": [{"doc_id": x.doc_id, "report_date": x.report_date,
                       "days_since_landfall": _plain(x.days_since_landfall), "sites_out": _plain(x.sites_out),
                       **{k: _plain(v) for k, v in cause_shares(x._asdict()).items()},
                       "on_backup_power": _plain(x.on_backup_power) if x.served_with_backup_column > 0 else None,
                       "backup_pct_of_served": _plain(x.backup_pct_of_served),
                       "fcc_multiple_causes_note": bool(x.fcc_multiple_causes_note)} for x in with_c.itertuples()],
        "n_reports_with_causes": len(with_c), "n_reports": int(p.doc_id.nunique()),
        "fcc_multiple_causes_note_reports": note_docs,
        "overattribution_wording": OVERATTRIBUTION_WORDING + ("" if len(note_docs) == len(with_c) else " " + OVERATTRIBUTION_INFERENCE
                                                              if not note_docs else
                                                              " The FCC's note is printed in some of this storm's reports; for the others the reading is an inference."),
        "backup_power_collected": bool((r.served_with_backup_column > 0).any()),
    }


def chapter_5(panel: pd.DataFrame, storms: pd.DataFrame) -> dict:
    order = storms[storms.in_panel].sort_values("landfall_utc")
    per_storm, not_collected = [], []
    for i, s in enumerate(order.itertuples()):
        p = panel[panel.storm_key == s.storm_key]
        if not has_causes(p):
            not_collected.append({"storm": s.storm, "storm_key": s.storm_key, "n_reports": int(p.doc_id.nunique())})
            continue
        per_storm.append({"storm_key": s.storm_key, "storm": s.storm, **storm_causes(p, SEED + 200 + i)})
    keys = [r["storm_key"] for r in per_storm]
    reps = cause_by_report(panel[panel.storm_key.isin(keys)])
    reps = reps[reps.sites_out > 0]
    point = pooled_shares(reps)
    # storm bootstrap of the all-storm pooled shares
    by_storm = reps.groupby("storm_key")[["sites_out", *SHARE_COLS.values()]].sum()
    rng = np.random.default_rng(SEED + 5)
    w = rng.multinomial(len(by_storm), np.full(len(by_storm), 1 / len(by_storm)), size=BOOTSTRAP_DRAWS)
    tot = w @ by_storm.to_numpy(float)
    boot = {k: 100 * tot[:, 1 + i] / tot[:, 0] for i, k in enumerate(SHARE_COLS)}
    heads = {"pooled_all_storms": _share_nums(point, boot, len(by_storm), "all storms pooled; storm bootstrap 95%"),
             "median_of_storm_shares": {k: median_across([r["pooled_over_reports"][k]["value"] for r in per_storm],
                                                         unit="% of sites out") for k in SHARE_COLS},
             "n_storms_with_causes": num(len(per_storm), n=len(per_storm) + len(not_collected), unit="storms",
                                         method="storms whose reports print cause columns"),
             "not_collected": not_collected,
             "drop_one_storm_pooled": {r["storm"]: {k: _plain(v) for k, v in pooled_shares(reps[reps.storm_key != r["storm_key"]]).items()}
                                       for r in per_storm}}
    sens = {"without_flagged_reports": {}, "without_serious_flag_reports": {}, "without_state_total_missing_reports": {}}
    for name, sub in (("without_flagged_reports", without_flagged(panel)), ("without_serious_flag_reports", without_serious(panel)),
                      ("without_state_total_missing_reports", panel[~panel.doc_id.isin(STATE_TOTAL_MISSING_DOCS)])):
        sr = cause_by_report(sub[sub.storm_key.isin(keys)])
        sr = sr[sr.sites_out > 0]
        sens[name] = {"pooled_all_storms": {k: _plain(v) for k, v in pooled_shares(sr).items()},
                      "n_storms": int(sr.storm_key.nunique()), "n_reports": len(sr)}
    helene = [r for r in per_storm if r["storm"] == "Helene"]
    external = None
    if helene:
        ours = attributed_only({k: helene[0]["pooled_over_reports"][k]["value"] for k in ("damage", "transport", "power")})
        external = {"source": OLUKOLA_CITATION, "storm": "Helene", "base": "attributed causes (damage + transport + power)",
                    "ours_converted": {k: _plain(v) for k, v in ours.items()}, "paper": OLUKOLA_HELENE_ATTRIBUTED,
                    "n_reports_ours": helene[0]["n_reports_with_causes"],
                    "note": ("External check only: converted to an attributed-only base, our Helene shares are set beside "
                             "the paper's pooled figures. The bases differ from this chapter's shares of sites out, and the "
                             "report sets differ (the paper uses 23 days of cause data from 24 reports).")}
    return {"headlines": heads, "storms": per_storm, "sensitivity": sens, "external_check": external,
            "fcc_multiple_causes_note_text": FCC_MULTIPLE_CAUSES_NOTE,
            "notes": ["Every share is a share of sites out, not of attributed sites; damage + transport + power + unattributed - overattributed = 100%.",
                      "Over-attribution is shown beside the other shares and never netted against unattributed sites.",
                      OVERATTRIBUTION_WORDING,
                      "Storms whose reports have no cause columns are 'not collected' and are left out of every denominator.",
                      "Shares on an attributed-only base (as in Olukola et al. 2026) are not directly comparable; see external_check.",
                      "Cause shares are not compared across rule periods in this chapter; that is done only in chapter 9, descriptively."]}


# ---- chapter 6: power co-movement ----

LAGS_H = (0, 6, 12, 24)
MIN_ROWS_FOR_CORRELATION = 10
CUSTOMERS_ARE_METERS = "EAGLE-I 'customers' are electricity meters, not people or households."
NO_POWER_STORMS_NOTE = ("EAGLE-I covers 2014-2025, so storms in 2026 (Isaias) have no power match or overlay until a "
                        "2026 release exists.")


def spearman(a, b) -> float:
    from scipy.stats import rankdata
    return float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])


def power_frame(p: pd.DataFrame, lag: int = 0, denominator: str = "eaglei_modeled_customers",
                customers_col: str | None = None) -> pd.DataFrame:
    """County-reports with an EAGLE-I value (at the as-of time, or lag hours earlier) and a usable denominator."""
    col = customers_col or ("eaglei_customers_out" if lag == 0 else f"eaglei_customers_out_{lag}h")
    q = p[(p.eaglei_match == "matched") | (col == "eaglei_customers_out_zero_filled")]
    if denominator == "eaglei_modeled_customers":
        q = q[q.eaglei_mcc_flag == "ok"]
    q = q[q[col].notna() & q[denominator].gt(0) & q.sites_served.gt(0)]
    has_c = q[["out_damage", "out_transport", "out_power"]].notna().all(axis=1)
    return pd.DataFrame({"storm_key": q.storm_key, "storm": q.storm, "fips": q.fips, "doc_id": q.doc_id,
                         "pct_customers_out": 100 * q[col] / q[denominator],
                         "pct_sites_out": 100 * q.sites_out / q.sites_served,
                         "pct_sites_out_power": (100 * q.out_power / q.sites_served).where(has_c),
                         "coverage": q.eaglei_coverage_flag})


def storm_comovement(f: pd.DataFrame, y: str, draws: int = BOOTSTRAP_DRAWS, seed: int = SEED) -> dict:
    f = f.dropna(subset=[y])
    cov = {k: int(v) for k, v in f.coverage.value_counts().items()}
    base = dict(n=len(f), unit="Spearman rank correlation", method=f"county bootstrap 95%, {draws} draws",
                n_counties=int(f.fips.nunique()), coverage_counts=cov)
    if len(f) < MIN_ROWS_FOR_CORRELATION or f[y].nunique() < 2 or f.pct_customers_out.nunique() < 2:
        return num(None, **base)
    rng = np.random.default_rng(seed)
    groups = [g.index.to_numpy() for _, g in f.groupby("fips")]
    x, yy = f.pct_customers_out.to_numpy(), f[y].to_numpy()
    pos = {ix: i for i, ix in enumerate(f.index)}
    groups = [np.array([pos[i] for i in g]) for g in groups]
    boot = []
    for _ in range(draws):
        pick = np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))])
        if np.unique(x[pick]).size > 1 and np.unique(yy[pick]).size > 1:
            boot.append(spearman(x[pick], yy[pick]))
    lo, hi = np.percentile(boot, CI) if boot else (None, None)
    return num(spearman(x, yy), lo, hi, **base)


def _summary_across(per_storm: dict, seed: int) -> dict:
    vals = [v["value"] for v in per_storm.values() if v["value"] is not None]
    return median_across(vals, seed=seed, unit="Spearman rank correlation") if vals else num(None)


def _pooled(f: pd.DataFrame, y: str, seed: int) -> dict:
    """One correlation over all county-reports; cluster bootstrap of storm-counties."""
    g = f.dropna(subset=[y]).assign(fips=lambda d: d.storm_key + "|" + d.fips)
    r = storm_comovement(g, y, seed=seed)
    r["method"] = "all storms pooled; storm-county cluster bootstrap 95%"
    return r


def comovement_block(panel: pd.DataFrame, storms_keys: list, seed: int, denominator="eaglei_modeled_customers",
                     zero_filled=False, coverage_filter=None, lags=LAGS_H) -> dict:
    out = {}
    for lag in lags:
        col = None
        if zero_filled:
            if lag != 0:
                continue
            col = "eaglei_customers_out_zero_filled"
        f = power_frame(panel[panel.storm_key.isin(storms_keys)], lag=lag, denominator=denominator, customers_col=col)
        if coverage_filter is not None:
            f = f[coverage_filter(f.coverage)]
        block = {}
        for y in ("pct_sites_out", "pct_sites_out_power"):
            per = {}
            for i, (key, g) in enumerate(f.groupby("storm_key")):
                per[g.storm.iloc[0]] = storm_comovement(g, y, seed=seed + 10 * lag + i)
            block[y] = {"by_storm": per, "median_across_storms": _summary_across(per, seed + lag),
                        "pooled": _pooled(f, y, seed + 1000 + lag)}
        out[f"lag_{lag}h"] = block
    return out


def power_overlay(panel: pd.DataFrame, keys: list) -> dict:
    """Per storm and report: % customers out and % sites out over the same matched, MCC-plausible counties."""
    f = power_frame(panel[panel.storm_key.isin(keys)], lag=0)
    q = panel.loc[f.index]
    out = {}
    for key, g in q.groupby("storm_key"):
        rows = []
        for doc, h in g.groupby("doc_id"):
            rows.append({"doc_id": doc, "days_since_landfall": _plain(h.days_since_landfall.iloc[0]),
                         "pct_customers_out": _plain(100 * h.eaglei_customers_out.sum() / h.eaglei_modeled_customers.sum()),
                         "pct_sites_out": _plain(100 * h.sites_out.sum() / h.sites_served.sum()),
                         "n_counties": int(h.fips.nunique()),
                         "n_low_coverage": int((h.eaglei_coverage_flag == "low_coverage").sum()),
                         "coverage_unknown": bool((h.eaglei_coverage_flag == "coverage_unknown").any())})
        out[g.storm.iloc[0]] = sorted(rows, key=lambda r: r["days_since_landfall"])
    return out


COMOVEMENT_CAVEAT = ("These correlations describe how the share of electricity customers without power and the share of "
                     "cell sites out move together across county-reports within a storm. Both may follow the storm's path "
                     "and strength, so the correlation does not show how much one drives the other.")


def lag_sentence(median_by_lag: dict) -> str:
    """When the two series line up, stated from the numbers; no mechanism is given."""
    v = {lag: median_by_lag[lag]["pct_sites_out"]["value"] for lag in median_by_lag}
    return (f"Cell outages line up about as closely with power outages 6 hours earlier (median correlation "
            f"{v['lag_6h']:.2f}) as with power outages at the same time ({v['lag_0h']:.2f}), and less closely with "
            f"power outages 24 hours earlier ({v['lag_24h']:.2f}).")


def mcc_methods_note(n_flagged: int, n_total: int, ex: dict) -> str:
    return (f"EAGLE-I's modeled customer count is below EAGLE-I's own recorded outages in {n_flagged:,} of {n_total:,} "
            f"storm-counties (for example, {ex['county']} County, {ex['state']}: {ex['modeled']:,} modeled customers, "
            f"{ex['max_out']:,.0f} customers out, {ex['households']:,.0f} households). Those storm-counties are left out of "
            f"every % of customers result; using households as the denominator instead is shown as a sensitivity.")


def _mcc_example(panel: pd.DataFrame) -> dict:
    """The flagged storm-county with the largest ratio of customers out to modeled customers."""
    f = panel[panel.eaglei_mcc_flag == "mcc_below_observed_outages"].drop_duplicates(["storm_key", "fips"])
    f = f.assign(ratio=f.eaglei_max_out_in_window / f.eaglei_modeled_customers).sort_values("ratio", ascending=False)
    r = f.iloc[0]
    return {"county": str(r.county).title(), "state": r.state, "fips": r.fips, "storm": r.storm,
            "modeled": int(r.eaglei_modeled_customers), "max_out": float(r.eaglei_max_out_in_window),
            "households": float(r.acs_households)}


def chapter_6(panel: pd.DataFrame, storms: pd.DataFrame) -> dict:
    s = storms[storms.in_panel]
    with_power = panel[panel.eaglei_release.fillna(False).astype(bool)]
    keys = sorted(with_power.storm_key.unique())
    no_power = s[~s.storm_key.isin(keys)].storm.tolist()
    rows = panel[panel.storm_key.isin(keys)]
    m = rows[rows.eaglei_match == "matched"]
    flagged_mcc = rows.drop_duplicates(["storm_key", "fips"])
    main = comovement_block(panel, keys, SEED + 300)
    heads = {
        "n_storms_with_power": num(len(keys), n=len(s), unit="storms", method="storms with an EAGLE-I release"),
        "storms_without_power": no_power,
        "county_reports_matched": num(len(m), n=len(rows), unit="county-reports", method="EAGLE-I record within 30 minutes"),
        "county_reports_used": num(len(power_frame(rows, lag=0)), n=len(m), unit="county-reports",
                                   method="matched, with a plausible modeled-customer count"),
        "storm_counties_mcc_below_observed_outages": num(int((flagged_mcc.eaglei_mcc_flag == "mcc_below_observed_outages").sum()),
                                                         n=len(flagged_mcc), unit="storm-counties",
                                                         method="highest customers out in the window exceeds MCC"),
        "matched_by_coverage": {k: int(v) for k, v in m.eaglei_coverage_flag.value_counts().items()},
        "comovement_at_as_of_time": main["lag_0h"]["pct_sites_out"]["median_across_storms"],
        "comovement_power_cause_at_as_of_time": main["lag_0h"]["pct_sites_out_power"]["median_across_storms"],
        "median_by_lag": {lag: {y: main[lag][y]["median_across_storms"] for y in ("pct_sites_out", "pct_sites_out_power")}
                          for lag in main},
    }
    def lag0_medians(block):
        return {y: block["lag_0h"][y]["median_across_storms"] for y in ("pct_sites_out", "pct_sites_out_power")}
    sens = {
        "without_low_coverage": lag0_medians(comovement_block(panel, keys, SEED + 310, lags=(0,),
                                                              coverage_filter=lambda c: c != "low_coverage")),
        "coverage_unknown_only": lag0_medians(comovement_block(panel, keys, SEED + 320, lags=(0,),
                                                               coverage_filter=lambda c: c == "coverage_unknown")),
        "coverage_ok_only": lag0_medians(comovement_block(panel, keys, SEED + 330, lags=(0,), coverage_filter=lambda c: c == "ok")),
        "missing_record_as_zero": lag0_medians(comovement_block(panel, keys, SEED + 340, lags=(0,), zero_filled=True)),
        "households_denominator": lag0_medians(comovement_block(panel, keys, SEED + 350, lags=(0,), denominator="acs_households")),
        "without_flagged_reports": lag0_medians(comovement_block(without_flagged(panel), keys, SEED + 360, lags=(0,))),
        "without_serious_flag_reports": lag0_medians(comovement_block(without_serious(panel), keys, SEED + 370, lags=(0,))),
        "without_state_total_missing_reports": lag0_medians(comovement_block(
            panel[~panel.doc_id.isin(STATE_TOTAL_MISSING_DOCS)], keys, SEED + 380, lags=(0,))),
    }
    per = main["lag_0h"]["pct_sites_out"]["by_storm"]
    vals = {k: v["value"] for k, v in per.items() if v["value"] is not None}
    sens["drop_one_storm_median_lag_0h"] = drop_one_medians(vals)
    ex = _mcc_example(rows)
    page_text = {"main_text_caveat": COMOVEMENT_CAVEAT, "lag_pattern": lag_sentence(heads["median_by_lag"]),
                 "methods_denominator_note": mcc_methods_note(heads["storm_counties_mcc_below_observed_outages"]["value"],
                                                              heads["storm_counties_mcc_below_observed_outages"]["n"], ex),
                 "methods_denominator_example": ex,
                 "no_exposure_model": "Chapter 6 fits no model that controls for exposure; the plan does not include one."}
    return {"headlines": heads, "by_lag": main, "sensitivity": sens, "overlay": power_overlay(panel, keys),
            "page_text": page_text,
            "notes": [CUSTOMERS_ARE_METERS, NO_POWER_STORMS_NOTE,
                      "Co-movement is a Spearman rank correlation across county-reports within a storm; it describes how the two move together, not why.",
                      "Counties whose EAGLE-I modeled customer count is below EAGLE-I's own recorded outages are left out of % of customers.",
                      "Every result carries its count by EAGLE-I coverage flag; low_coverage = the state's minimum covered share below 0.75 that year."]}


# ---- chapter 7: exposure ----

ZONES = ["inside 64 kt", "50-64 kt", "34-50 kt", "outside 34 kt"]  # outside 34 kt is the reference
DIST_BANDS = [(0, 50, "0-50 km"), (50, 100, "50-100 km"), (100, 200, "100-200 km"), (200, np.inf, "over 200 km")]
CALIBRATION_BINS = 10
PRED_CLIP = 1e-6


def wind_zone(r34, r50, r64) -> str:
    return "inside 64 kt" if r64 else "50-64 kt" if r50 else "34-50 kt" if r34 else "outside 34 kt"


def county_peaks(p: pd.DataFrame) -> pd.DataFrame:
    """One row per storm and county, at the county's own peak report (highest share of sites out)."""
    q = p[p.sites_served > 0].assign(_share=lambda d: d.sites_out / d.sites_served)
    q = q.sort_values(["storm_key", "fips", "_share", "doc_id"], ascending=[True, True, False, True])
    top = q.drop_duplicates(["storm_key", "fips"])
    return pd.DataFrame({"storm_key": top.storm_key, "storm": top.storm, "fips": top.fips, "peak_doc_id": top.doc_id,
                         "peak_out": top.sites_out, "peak_served": top.sites_served,
                         "min_dist_km": top.min_dist_km, "wind_kt_at_closest": top.wind_kt_at_closest,
                         "zone": [wind_zone(a, b, c) for a, b, c in zip(top.in_34kt, top.in_50kt, top.in_64kt)]}
                        ).reset_index(drop=True)


def _design(c: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame({"const": 1.0, "log1p_dist_km": np.log1p(c.min_dist_km.to_numpy(float)),
                      "wind_per_10kt": c.wind_kt_at_closest.to_numpy(float) / 10}, index=c.index)
    for z in ZONES[:-1]:
        X[f"zone_{z}"] = (c.zone == z).astype(float).to_numpy()
    return X


def fit_exposure_model(c: pd.DataFrame, clustered: bool = True):
    import statsmodels.api as sm
    y = np.column_stack([c.peak_out.to_numpy(float), (c.peak_served - c.peak_out).to_numpy(float)])
    model = sm.GLM(y, _design(c), family=sm.families.Binomial())
    if clustered and c.storm_key.nunique() > 1:
        groups = pd.factorize(c.storm_key)[0]
        return model.fit(cov_type="cluster", cov_kwds={"groups": groups}, scale="X2")
    return model.fit(scale="X2")


def predict_share(fit, c: pd.DataFrame) -> np.ndarray:
    X = _design(c)[fit.params.index]
    return np.clip(fit.predict(X), PRED_CLIP, 1 - PRED_CLIP)


def leave_one_storm_out(c: pd.DataFrame) -> pd.Series:
    pred = pd.Series(np.nan, index=c.index)
    for key in c.storm_key.unique():
        held = c.storm_key == key
        fit = fit_exposure_model(c[~held], clustered=False)
        pred[held] = predict_share(fit, c[held])
    return pred


def calibration(c: pd.DataFrame, pred) -> dict:
    import statsmodels.api as sm
    pred = pd.Series(np.clip(np.asarray(pred, float), PRED_CLIP, 1 - PRED_CLIP), index=c.index)
    lp = np.log(pred / (1 - pred))
    y = np.column_stack([c.peak_out.to_numpy(float), (c.peak_served - c.peak_out).to_numpy(float)])
    groups = pd.factorize(c.storm_key)[0]
    fam = sm.families.Binomial()
    kw = dict(cov_type="cluster", cov_kwds={"groups": groups}, scale="X2") if c.storm_key.nunique() > 1 else dict(scale="X2")
    slope_fit = sm.GLM(y, sm.add_constant(lp.to_numpy()), family=fam).fit(**kw)
    large_fit = sm.GLM(y, np.ones((len(c), 1)), family=fam, offset=lp.to_numpy()).fit(**kw)
    sl, (sl_lo, sl_hi) = slope_fit.params[1], slope_fit.conf_int()[1]
    il, (il_lo, il_hi) = large_fit.params[0], large_fit.conf_int()[0]
    bins = pd.qcut(pred.rank(method="first"), CALIBRATION_BINS, labels=False)
    deciles = []
    for b in range(CALIBRATION_BINS):
        m = bins == b
        deciles.append({"bin": b + 1, "n": int(m.sum()),
                        "mean_predicted_pct": _plain(100 * float((pred[m] * c.peak_served[m]).sum() / c.peak_served[m].sum())),
                        "observed_pct": _plain(100 * float(c.peak_out[m].sum() / c.peak_served[m].sum()))})
    obs = c.peak_out / c.peak_served
    unit = "storm-counties"
    return {"slope": num(sl, sl_lo, sl_hi, n=len(c), unit="calibration slope (1 is ideal)",
                         method="GLM of observed counts on logit(prediction); storm-clustered 95%"),
            "in_the_large": num(il, il_lo, il_hi, n=len(c), unit="log-odds (0 is ideal)",
                                method="intercept with logit(prediction) as offset; storm-clustered 95%"),
            "mean_absolute_error_pct_points": num(100 * float(np.mean(np.abs(obs - pred))), n=len(c), unit="percentage points",
                                                  method="county peak share; unweighted"),
            "spearman_predicted_observed": num(spearman(pred, obs), n=len(c), unit="Spearman rank correlation",
                                               method="county peaks"),
            "deciles": deciles, "n": len(c), "unit": unit}


def band_shares(c: pd.DataFrame, by: str, draws: int = BOOTSTRAP_DRAWS, seed: int = SEED) -> dict:
    c = c.copy()
    if by == "dist_band":
        c["dist_band"] = None
        for lo, hi, label in DIST_BANDS:
            c.loc[(c.min_dist_km >= lo) & (c.min_dist_km < hi), "dist_band"] = label
        order = [b[2] for b in DIST_BANDS]
    else:
        order = ZONES
    rng = np.random.default_rng(seed)
    keys = c.storm_key.unique()
    tab = c.groupby(["storm_key", by])[["peak_out", "peak_served"]].sum()
    out = {}
    for label in order:
        sub = c[c[by] == label]
        if sub.empty:
            out[label] = num(None, n=0, unit="% of sites served")
            continue
        boot = []
        for _ in range(draws):
            pick = rng.choice(keys, size=len(keys), replace=True)
            t = tab.reindex([(k, label) for k in pick]).dropna()
            if t.peak_served.sum() > 0:
                boot.append(100 * t.peak_out.sum() / t.peak_served.sum())
        lo, hi = np.percentile(boot, CI)
        out[label] = num(100 * sub.peak_out.sum() / sub.peak_served.sum(), lo, hi, n=len(sub), unit="% of sites served",
                         method="sum of county peak sites out / sum of sites served; storm bootstrap 95%",
                         n_storms=int(sub.storm_key.nunique()))
    return out


def _model_summary(fit) -> dict:
    ci = fit.conf_int()
    return {k: num(float(np.exp(fit.params[k])), float(np.exp(ci.loc[k, 0])), float(np.exp(ci.loc[k, 1])),
                   n=int(fit.nobs), unit="odds ratio", method="binomial GLM; storm-clustered 95%")
            for k in fit.params.index if k != "const"}


CH7_PAGE_LAYOUT = {"lead_exhibit": "by_wind_zone", "second_exhibit": "by_distance_band",
                   "methods": ["headlines.odds_ratios", "headlines.calibration_held_out", "headlines.calibration_in_sample",
                               "storms", "sensitivity"]}
STORM_MISS_GAP_PCT_POINTS = 5.0  # a storm's held-out prediction this far from observed is named in the misses note


def storm_misses_note(per_storm: list, min_gap: float = STORM_MISS_GAP_PCT_POINTS) -> str:
    def one(r):
        return f"{r['storm']} ({r['observed_pct']:.1f}% observed, {r['predicted_pct_held_out']:.1f}% predicted)"
    under = [r for r in per_storm if r["observed_pct"] - r["predicted_pct_held_out"] >= min_gap]
    over = [r for r in per_storm if r["predicted_pct_held_out"] - r["observed_pct"] >= min_gap]
    parts = []
    if under:
        parts.append("higher than predicted for " + _and_list([one(r) for r in under]))
    if over:
        parts.append("lower than predicted for " + _and_list([one(r) for r in over]))
    return ("Here a storm's peak share pools each county's own peak report, so it can differ from the single-report "
            f"peak in chapter 3. Held out of the fit, with misses of {min_gap:.0f} percentage points or more listed, "
            "storms' pooled peak shares were " + "; and ".join(parts) + ". Flooding, road access and fiber cuts are "
            "possible unmeasured factors; this design cannot tell whether they, or something else, account for the "
            "gaps.") if parts else ""


def chapter_7(panel: pd.DataFrame, storms: pd.DataFrame) -> dict:
    c = county_peaks(panel)
    fit = fit_exposure_model(c)
    held = leave_one_storm_out(c)
    cal_out = calibration(c, held)
    cal_in = calibration(c, predict_share(fit, c))
    per_storm = []
    for key, g in c.assign(pred=held).groupby("storm_key"):
        per_storm.append({"storm": g.storm.iloc[0], "storm_key": key, "n_counties": len(g),
                          "observed_pct": _plain(100 * g.peak_out.sum() / g.peak_served.sum()),
                          "predicted_pct_held_out": _plain(100 * (g.pred * g.peak_served).sum() / g.peak_served.sum())})
    drop = {}
    for key in c.storm_key.unique():
        f = fit_exposure_model(c[c.storm_key != key])
        drop[c[c.storm_key == key].storm.iloc[0]] = {k: _plain(float(np.exp(v))) for k, v in f.params.items() if k != "const"}
    sens = {"drop_one_storm_odds_ratios": drop}
    for name, sub in (("without_flagged_reports", without_flagged(panel)), ("without_serious_flag_reports", without_serious(panel)),
                      ("without_state_total_missing_reports", panel[~panel.doc_id.isin(STATE_TOTAL_MISSING_DOCS)])):
        cs = county_peaks(sub)
        if cs.storm_key.nunique() < 3:
            sens[name] = {"n_storms": int(cs.storm_key.nunique()), "note": "too few storms to fit"}
            continue
        fs = fit_exposure_model(cs)
        sens[name] = {"n_storms": int(cs.storm_key.nunique()), "n": len(cs), "odds_ratios": _model_summary(fs),
                      "held_out_calibration_slope": calibration(cs, leave_one_storm_out(cs))["slope"]}
    return {"headlines": {"n_storm_counties": num(len(c), n=int(c.storm_key.nunique()), unit="storm-counties",
                                                  method="county peak report per storm"),
                          "odds_ratios": _model_summary(fit),
                          "calibration_held_out": cal_out, "calibration_in_sample": cal_in},
            "by_distance_band": band_shares(c, "dist_band", seed=SEED + 400),
            "by_wind_zone": band_shares(c, "zone", seed=SEED + 410),
            "storms": per_storm, "sensitivity": sens, "page_layout": CH7_PAGE_LAYOUT,
            "page_text": {"storm_misses": storm_misses_note(per_storm)},
            "notes": ["Peak share = a county's highest share of sites out across the storm's reports, at its own peak report.",
                      "Odds ratios describe associations between exposure and peak share; they are not effects of wind or distance.",
                      "Wind at the nearest track point is the storm's intensity there, not the wind measured in the county.",
                      "Calibration is judged on storms held out of the fit, one at a time."]}


# ---- chapter 8: waiting time by SVI quartile ----

WAIT_THRESHOLD = 0.05  # share of sites out
BASELINE_BINS = [(-np.inf, 2, "0-2 d"), (2, 4, "2-4 d"), (4, 7, "4-7 d"), (7, 14, "7-14 d"), (14, np.inf, "14+ d")]
SVI_LABELS = ["Q1 (least)", "Q2", "Q3", "Q4 (most)"]
SHARE_BY_DAYS = (3, 7, 14)
MIN_INTERVAL_DAYS = 1 / 24
CH8_NOT_RULED_OUT = [
    "SVI is correlated with rurality, terrain and network density; any of these, or other differences between counties, "
    "may be associated with both SVI and restoration times.",
    "Public DIRS tables combine all providers, so differences between providers' networks in different counties cannot be seen.",
    "Counties that leave the reports while still out are censored; if leaving the reports differs by SVI quartile, the "
    "comparison can shift (see the best and worst cases).",
    "Wind zone, distance and track-point wind do not capture flooding, road access or fiber cuts.",
]
CH8_WORDING = ("Associations only: these results describe how long counties in each SVI quartile took to fall below 5% of "
               "sites out. They do not show why, and say nothing about anyone's intent.")


def waiting_record(days, shares, storm_days) -> dict | None:
    """A storm-county's wait to stay below 5% of sites out, from its first report at or above 5%."""
    days, shares = list(map(float, days)), list(map(float, shares))
    at_or_above = [i for i, v in enumerate(shares) if v >= WAIT_THRESHOLD]
    if not at_or_above:
        return None
    s = at_or_above[0]
    rest = shares[s:]
    i = stay_index(rest, WAIT_THRESHOLD, below=True)
    j = first_index(rest, WAIT_THRESHOLD, below=True)
    storm_days = sorted(map(float, storm_days))
    last, storm_last = days[-1], storm_days[-1]
    rec = {"days": days, "start_index": s, "start": days[s], "storm_last": storm_last,
           "first_crossing_time": days[s + j] if j is not None else None}
    if i is not None:
        rec.update(event=True, time=days[s + i], interval_low=days[s + i - 1], end_index=s + i, censoring="none",
                   best_event=True, best_time=days[s + i], worst_event=True, worst_time=days[s + i])
        return rec
    left = last < storm_last
    later = [d for d in storm_days if d > last]
    rec.update(event=False, time=last, interval_low=None, end_index=len(days) - 1,
               censoring="left_reports_while_out" if left else "out_at_last_report",
               best_event=bool(left), best_time=later[0] if left else last,
               worst_event=False, worst_time=storm_last)
    return rec


def person_periods(w: dict, case: str = "main") -> list[dict]:
    d = w["days"]
    out = [{"t0": d[k - 1], "t1": d[k], "event": int(w["event"] and k == w["end_index"])}
           for k in range(w["start_index"] + 1, w["end_index"] + 1)]
    if not w["event"] and w["censoring"] == "left_reports_while_out":
        if case == "best":
            out.append({"t0": d[-1], "t1": w["best_time"], "event": 1})
        elif case == "worst":
            out.append({"t0": d[-1], "t1": w["storm_last"], "event": 0})
    return out


def svi_quartiles(svi: pd.Series, scale: str = "sample"):
    if scale == "national":
        cuts = [0.25, 0.5, 0.75]
    else:
        cuts = [float(x) for x in np.quantile(svi.dropna(), [0.25, 0.5, 0.75])]
    q = pd.cut(svi, [-np.inf, *cuts, np.inf], labels=SVI_LABELS, right=True)
    return q.astype(str).where(svi.notna()), cuts


def kaplan_meier(times, events) -> pd.DataFrame:
    t, e = np.asarray(times, float), np.asarray(events, bool)
    rows, s = [], 1.0
    for u in np.unique(t[e]):
        at_risk = (t >= u).sum()
        d = ((t == u) & e).sum()
        s *= 1 - d / at_risk
        rows.append((u, s))
    return pd.DataFrame(rows, columns=["time", "survival"])


def km_median(km: pd.DataFrame):
    hit = km[km.survival <= 0.5]
    return _plain(hit.time.iloc[0]) if len(hit) else None


def km_share_by(km: pd.DataFrame, day: float) -> float:
    before = km[km.time <= day]
    return float(1 - before.survival.iloc[-1]) if len(before) else 0.0


def waiting_records(panel: pd.DataFrame, hold_served: bool = False) -> pd.DataFrame:
    recs = []
    storm_days = panel.groupby("storm_key").days_since_landfall.apply(lambda s: sorted(s.unique()))
    for (key, fips), g in panel.groupby(["storm_key", "fips"]):
        g = g.sort_values("days_since_landfall")
        g = g[g.sites_served > 0]
        if g.empty:
            continue
        if hold_served:
            served = g.loc[(g.sites_out / g.sites_served).idxmax(), "sites_served"]
            share = g.sites_out / served
        else:
            share = g.sites_out / g.sites_served
        w = waiting_record(g.days_since_landfall, share, storm_days[key])
        if w is None:
            continue
        first = g.iloc[0]
        recs.append({"storm_key": key, "storm": first.storm, "fips": fips, "svi": first.svi_overall,
                     "zone": wind_zone(first.in_34kt, first.in_50kt, first.in_64kt), "min_dist_km": first.min_dist_km,
                     "wind_kt_at_closest": first.wind_kt_at_closest, **{k: v for k, v in w.items()}})
    return pd.DataFrame(recs)


def _baseline_bin(t1):
    for lo, hi, label in BASELINE_BINS:
        if lo <= t1 < hi:
            return label


MAX_SCORE = 1e-6       # gradient at an accepted Newton maximum
MAX_ABS_COEF = 30.0    # an IRLS fit with a larger coefficient (a hazard ratio beyond e^30) is treated as diverged


class NotEstimable(RuntimeError):
    """The worst-case (or other) hazard model has no reachable finite maximum."""


def irls_ok(fit) -> bool:
    p = np.asarray(fit.params, float)
    return bool(getattr(fit, "converged", False)) and np.all(np.isfinite(p)) and float(np.abs(p).max()) <= MAX_ABS_COEF


def fit_waiting_hazard(pp: pd.DataFrame):
    """Discrete-time cloglog hazard over report intervals with log(interval length) offset; storm fixed effects;
    county-clustered SEs. Returns (fit, info)."""
    import statsmodels.api as sm
    ev = pp.groupby("storm_key").event.agg(["sum", "size"])
    n_cty = pp.groupby("storm_key").fips.nunique()
    county_events = pp.groupby(["storm_key", "fips"]).event.max().groupby("storm_key").sum()
    keep = ev.index[(ev["sum"] > 0) & (county_events < n_cty)]
    dropped = sorted(set(ev.index) - set(keep))
    q = pp[pp.storm_key.isin(keep)].copy()
    q["bin"] = q.t1.map(_baseline_bin)
    X = pd.DataFrame({"const": 1.0}, index=q.index)
    for col, prefix, levels in (("bin", "base", [b[2] for b in BASELINE_BINS][1:]), ("svi_q", "svi", SVI_LABELS[1:]),
                                ("zone", "zone", ZONES[:-1])):
        for lv in levels:
            X[f"{prefix}_{lv}"] = (q[col] == lv).astype(float)
    X["log1p_dist_km"] = np.log1p(q.min_dist_km.astype(float))
    X["wind_per_10kt"] = q.wind_kt_at_closest.astype(float) / 10
    for k in sorted(keep)[1:]:
        X[f"storm_{k}"] = (q.storm_key == k).astype(float)
    X = X.loc[:, (X.std() > 0) | (X.columns == "const")]
    offset = np.log(np.clip((q.t1 - q.t0).astype(float), MIN_INTERVAL_DAYS, None))
    fam = sm.families.Binomial(link=sm.families.links.CLogLog())
    model = sm.GLM(q.event.astype(float), X, family=fam, offset=offset)
    groups = {"groups": pd.factorize(q.fips)[0]}
    fit, optimizer = model.fit(cov_type="cluster", cov_kwds=groups), "IRLS"
    if not irls_ok(fit):  # same model and likelihood; only the maximiser changes (decision 2026-11-23)
        fit = model.fit(method="newton", start_params=np.zeros(X.shape[1]), maxiter=300, disp=0,
                        cov_type="cluster", cov_kwds=groups)
        grad = float(np.abs(model.score(fit.params)).max())
        if not (fit.mle_retvals.get("converged") and grad < MAX_SCORE and np.all(np.isfinite(fit.params))):
            raise NotEstimable(f"the likelihood has no finite maximum the fitter can reach (IRLS diverged; Newton's "
                               f"method stopped with gradient {grad:.1e})")
        optimizer = "Newton's method (IRLS did not converge)"
    return fit, {"storms_in_model": sorted(keep), "storms_left_out": dropped, "n_intervals": len(q),
                 "n_events": int(q.event.sum()), "n_counties": int(q.fips.nunique()), "optimizer": optimizer}


def _hazard_ratios(fit) -> dict:
    ci = fit.conf_int()
    return {k: num(float(np.exp(fit.params[k])), float(np.exp(ci.loc[k, 0])), float(np.exp(ci.loc[k, 1])),
                   n=int(fit.nobs), unit="hazard ratio (above 1 = reaches below 5% sooner)",
                   method="discrete-time cloglog; storm fixed effects; county-clustered 95%")
            for k in fit.params.index if k.startswith(("svi_", "zone_")) or k in ("log1p_dist_km", "wind_per_10kt")}


def _pp_frame(recs: pd.DataFrame, case: str = "main", first_crossing: bool = False) -> pd.DataFrame:
    rows = []
    for r in recs.itertuples():
        w = r._asdict()
        if first_crossing and pd.notna(w["first_crossing_time"]):
            k = w["days"].index(w["first_crossing_time"])
            w = {**w, "event": True, "end_index": k}
        for p in person_periods(w, case=case):
            rows.append({"storm_key": r.storm_key, "fips": r.fips, "svi_q": r.svi_q, "zone": r.zone,
                         "min_dist_km": r.min_dist_km, "wind_kt_at_closest": r.wind_kt_at_closest, **p})
    return pd.DataFrame(rows)


def raw_by_quartile(recs: pd.DataFrame, seed: int, time_col="time", event_col="event") -> dict:
    out = {}
    rng = np.random.default_rng(seed)
    for i, q in enumerate(SVI_LABELS):
        g = recs[recs.svi_q == q]
        if g.empty:
            out[q] = {"n": 0}
            continue
        t, e = g[time_col].to_numpy(float), g[event_col].to_numpy(bool)
        km = kaplan_meier(t, e)
        boot = []
        for _ in range(BOOTSTRAP_DRAWS):
            j = rng.integers(0, len(g), len(g))
            m = km_median(kaplan_meier(t[j], e[j]))
            boot.append(np.inf if m is None else m)
        lo, hi = _time_ci(np.array(boot))
        out[q] = {"median_days_since_landfall": num(km_median(km), lo, hi, n=len(g), unit="days since landfall",
                                                    method="Kaplan-Meier median; county bootstrap 95%",
                                                    n_censored=int((~e).sum())),
                  **{f"share_below_5pct_by_day_{d}": num(km_share_by(km, d), n=len(g), unit="share of storm-counties",
                                                          method="1 - Kaplan-Meier survival") for d in SHARE_BY_DAYS},
                  "svi_range": [_plain(g.svi.min()), _plain(g.svi.max())]}
    return out


def ch8_headline(hr_q4: dict) -> str:
    """Chapter 8 headline (2026-11-22; chosen by Tim from options proposed by Claude Code), with the bound taken from the Q4 hazard ratio's interval."""
    return ("In this data, counties with higher social vulnerability did not take measurably longer for cell outages to "
            "fall below 5% of sites. The estimates rule out a large delay for the most vulnerable quartile (a rate of "
            f"recovery more than {ruled_out_pct(hr_q4['ci_low'])}% slower), though they can't rule out a smaller one.")


def ruled_out_pct(lo: float) -> int:
    """The slowdown stated as ruled out, rounded up so the claim is never stronger than the interval."""
    return int(math.ceil(round(100 * (1 - lo), 9)))


def not_ruled_out_pct(hi: float) -> int:
    """The speed-up stated as not ruled out, rounded down for the same reason."""
    return int(math.floor(round(100 * (hi - 1), 9)))


def ch8_bound_sentence(hr_q4: dict) -> str:
    lo, hi = hr_q4["ci_low"], hr_q4["ci_high"]
    return (f"For the most vulnerable quartile, the 95% interval for the hazard ratio runs from {lo:.2f} to {hi:.2f}: a rate "
            f"of falling below 5% more than {ruled_out_pct(lo)}% lower than the least vulnerable quartile's is outside it; "
            f"a smaller shortfall, or a rate up to {not_ruled_out_pct(hi)}% higher, is not.")


def ch8_best_case_sentence(best: dict, worst: dict) -> str:
    """best and worst: model_svi results (hazard_ratios, or error)."""
    def hr(d, k):
        h = d["hazard_ratios"][k]
        return f"{h['value']:.2f} [{h['ci_low']:.2f}, {h['ci_high']:.2f}]"
    if "error" in worst:
        return ("Sensitivity display, not a finding: if counties that leave the reports while still out are counted as having "
                f"fallen below 5% at their next unreported report, the third and fourth quartiles reach it sooner (hazard "
                f"ratios {hr(best, 'svi_Q3')} and {hr(best, 'svi_Q4 (most)')}). Keeping those counties at risk to the "
                f"storm's last report instead is not estimable under the worst-case assumption: {worst['error_reason']}.")
    return ("Sensitivity display, not a finding: if counties that leave the reports while still out are counted as having "
            f"fallen below 5% at their next unreported report, the third and fourth quartiles reach it sooner (hazard ratios "
            f"{hr(best, 'svi_Q3')} and {hr(best, 'svi_Q4 (most)')}). The difference disappears if those counties are instead "
            f"kept at risk to the storm's last report ({hr(worst, 'svi_Q3')} and {hr(worst, 'svi_Q4 (most)')}).")


EARLIER_ORIGINS = {
    "original": ("days_since_landfall_previous_rule",
                 "the earliest HURDAT2 landfall nearest to at least one of the storm's counties"),
    "landfall_or_closest_approach": ("days_since_landfall_interim_rule",
                                     "the earlier of the first study-state landfall and the closest approach to the "
                                     "study-state counties (first 2026-11-23 rule)")}


def earlier_origin_comparisons(panel: pd.DataFrame, hr_now: dict, headline_now: str) -> dict:
    """Chapter 8 under each earlier day-0 rule (see EARLIER_ORIGINS)."""
    return {k: previous_origin_comparison(panel, hr_now, headline_now, col, note)
            for k, (col, note) in EARLIER_ORIGINS.items() if col in panel}


def previous_origin_comparison(panel: pd.DataFrame, hr_now: dict, headline_now: str,
                               col: str = "days_since_landfall_previous_rule", note: str = "") -> dict | None:
    """Chapter 8 under an earlier day-0 rule, and whether anything shown changes."""
    if col not in panel:
        return None
    prev = panel.assign(days_since_landfall=panel[col])
    recs = waiting_records(prev)
    recs["svi_q"], _ = svi_quartiles(recs.svi, "sample")
    fit, info = fit_waiting_hazard(_pp_frame(recs))
    hr = _hazard_ratios(fit)
    shown = [k for k in hr_now if k.startswith("svi_")]
    moved = {k: [round(hr_now[k][f], 2) for f in ("value", "ci_low", "ci_high")] !=
             [round(hr[k][f], 2) for f in ("value", "ci_low", "ci_high")] for k in shown}
    headline = ch8_headline(hr["svi_Q4 (most)"])
    return {"hazard_ratios": hr, "model": info, "raw_by_quartile": raw_by_quartile(recs, SEED + 550),
            "headline": headline, "headline_bound": ch8_bound_sentence(hr["svi_Q4 (most)"]),
            "svi_hazard_ratios_change_at_two_decimals": moved,
            "any_svi_hazard_ratio_changes": any(moved.values()), "headline_changes": headline != headline_now,
            "note": f"day 0: {note}"}


def chapter_8(panel: pd.DataFrame, storms: pd.DataFrame) -> dict:
    recs = waiting_records(panel)
    recs["svi_q"], cuts = svi_quartiles(recs.svi, "sample")
    fit, info = fit_waiting_hazard(_pp_frame(recs))
    raw = raw_by_quartile(recs, SEED + 500)
    per_storm = {k: {"storm": g.storm.iloc[0], "n": len(g), "n_events": int(g.event.sum()),
                     "censoring": {c: int(v) for c, v in g.censoring.value_counts().items()}}
                 for k, g in recs.groupby("storm_key")}

    def model_svi(r, case="main", first_crossing=False):
        try:
            f, inf = fit_waiting_hazard(_pp_frame(r, case=case, first_crossing=first_crossing))
        except Exception as err:  # reported, not hidden
            return {"error": f"{type(err).__name__}: {err}", "error_reason": str(err)}
        return {"hazard_ratios": {k: v for k, v in _hazard_ratios(f).items() if k.startswith("svi_")}, **inf}

    nat = recs.copy()
    nat["svi_q"], nat_cuts = svi_quartiles(nat.svi, "national")
    held = waiting_records(panel, hold_served=True)
    held["svi_q"], _ = svi_quartiles(held.svi, "sample")
    drop = {}
    for key in recs.storm_key.unique():
        r = recs[recs.storm_key != key]
        m = model_svi(r)
        drop[recs[recs.storm_key == key].storm.iloc[0]] = {k: v["value"] for k, v in m.get("hazard_ratios", {}).items()}
    def requartile(r):
        r = r.copy()
        r["svi_q"], _ = svi_quartiles(r.svi, "sample")
        return r
    sens = {
        "national_svi_cut_points": {"cuts": nat_cuts, "counts": {q: int((nat.svi_q == q).sum()) for q in SVI_LABELS},
                                    **model_svi(nat), "raw": raw_by_quartile(nat, SEED + 510)},
        "hold_sites_served_at_peak": {**model_svi(held), "raw": raw_by_quartile(held, SEED + 520)},
        "censored_best_case": {**model_svi(recs, case="best"),
                               "raw": raw_by_quartile(recs, SEED + 530, time_col="best_time", event_col="best_event")},
        "censored_worst_case": {**model_svi(recs, case="worst"),
                                "raw": raw_by_quartile(recs, SEED + 540, time_col="worst_time", event_col="worst_event")},
        "first_crossing": model_svi(recs, first_crossing=True),
        "drop_one_storm_svi_hazard_ratios": drop,
        "without_flagged_reports": model_svi(requartile(waiting_records(without_flagged(panel)))),
        "without_serious_flag_reports": model_svi(requartile(waiting_records(without_serious(panel)))),
        "without_state_total_missing_reports": model_svi(requartile(waiting_records(
            panel[~panel.doc_id.isin(STATE_TOTAL_MISSING_DOCS)]))),
        "earlier_time_origins": earlier_origin_comparisons(panel, _hazard_ratios(fit),
                                                           ch8_headline(_hazard_ratios(fit)["svi_Q4 (most)"])),
    }
    return {"headlines": {"n_storm_counties_at_risk": num(len(recs), n=int(recs.storm_key.nunique()), unit="storm-counties",
                                                          method="share of sites out at or above 5% in some report"),
                          "n_events": num(int(recs.event.sum()), n=len(recs), unit="storm-counties below 5% by the rebound rule",
                                          method="the rest are right-censored"),
                          "censoring": {c: int(v) for c, v in recs.censoring.value_counts().items()},
                          "svi_quartile_cut_points": cuts,
                          "raw_by_quartile": raw,
                          "hazard_ratios": _hazard_ratios(fit), "model": info},
            "storms": per_storm, "sensitivity": sens,
            "page_text": {"headline": ch8_headline(_hazard_ratios(fit)["svi_Q4 (most)"]),
                          "headline_bound": ch8_bound_sentence(_hazard_ratios(fit)["svi_Q4 (most)"]),
                          "best_case_sensitivity": ch8_best_case_sentence(sens["censored_best_case"],
                                                                          sens["censored_worst_case"]),
                          "wording": CH8_WORDING, "cannot_rule_out": CH8_NOT_RULED_OUT,
                          "cannot_rule_out_placement": "main text"},
            "notes": ["Quartiles are of the at-risk storm-counties' SVI 2022 national percentiles; national cut points are a sensitivity display.",
                      "Hazard ratios above 1 mean a county reaches below 5% of sites out sooner than the lowest-SVI quartile, holding exposure and storm fixed.",
                      "The event is the first report from which a county stays below 5% in every later report that includes it."]}


# ---- chapter 9: rule periods (descriptive only) ----

TIME_MEASURES = [("t50", "t50_censored"), ("t90", "t90_censored"), ("t90_best", "t90_best_censored")]
MEASURE_LABELS = {"t50": "time to 50%", "t90": "time to 90% (leaving counties still out)",
                  "t90_best": "time to 90% (leaving counties restored)", "days_peak_to_last": "days from peak to last report",
                  "still_out_share_at_last": "share still out at the last report", "max_wind_kt": "strongest wind",
                  "peak_pct_out": "peak % out"}


def _order_text(o) -> str:
    return "no median for every period" if o is None else " < ".join(o)
DENOMINATOR_MOVE_LIMIT = 1.10
CH9_ALLOWED = "recovery in storms after the rule coincided with shorter (or longer) times"
CH9_NOT_ALLOWED_NOTE = ("At least one of the plan's red flags is triggered, so this chapter makes no statement about "
                        "whether recovery changed after the rules. It shows each storm and each period's median and "
                        "range, and lists the flags.")


def period_summary(s: pd.DataFrame, col: str, cens_col: str | None = None) -> dict:
    out = {}
    for code in PERIOD_CODES:
        g = s[s.rule_period == code]
        if g.empty:
            out[code] = {"n_storms": 0, "note": "no storm in this period"}
            continue
        vals = g[col].where(~g[cens_col].astype(bool), g.censored_at) if cens_col else g[col]
        cens = g[cens_col].astype(bool).tolist() if cens_col else [False] * len(g)
        observed = vals[~np.asarray(cens, bool)]
        rec = {"n_storms": len(g), "median": median_with_censoring(vals, cens) if cens_col else _plain(float(np.median(vals))),
               "min": _plain(float(observed.min())) if len(observed) else None,
               "max": _plain(float(observed.max())) if len(observed) else None,
               "n_observed": int(len(observed)), "n_censored": int(sum(cens)),
               "range_note": "range of observed times only; censored storms counted separately" if cens_col else "",
               "storms": g.storm.tolist()}
        if len(g) == 1:
            rec["storm"] = g.storm.iloc[0]
        out[code] = rec
    return out


def period_order(summary: dict) -> list:
    have = {k: v for k, v in summary.items() if v.get("n_storms")}
    if any(v["median"] is None for v in have.values()):
        return None
    return sorted(have, key=lambda k: (have[k]["median"], k))


def red_flag_drop_one(s: pd.DataFrame) -> dict:
    reasons = []
    for col, cens in TIME_MEASURES:
        base = period_order(period_summary(s, col, cens))
        for storm in s.storm:
            rest = s[s.storm != storm]
            if set(rest.rule_period) != set(s.rule_period):
                lost = sorted(set(s.rule_period) - set(rest.rule_period))
                reasons.append(f"dropping {storm} leaves {', '.join(lost)} with no storm")
                continue
            o = period_order(period_summary(rest, col, cens))
            if o != base:
                what = ("a median can no longer be given for every period" if o is None else
                        f"the period medians can now be ordered ({_order_text(o)})" if base is None else
                        f"the order of period medians changes from {_order_text(base)} to {_order_text(o)}")
                reasons.append(f"{MEASURE_LABELS[col]}: without {storm}, {what}")
    reasons = sorted(set(reasons))
    return {"triggered": bool(reasons), "reason": "; ".join(reasons)}


def red_flag_measure_dependence(s: pd.DataFrame) -> dict:
    orders = {col: period_order(period_summary(s, col, cens)) for col, cens in TIME_MEASURES}
    reasons = []
    if any(o is None for o in orders.values()):
        reasons.append("a median cannot be given for every period for " +
                       _and_list([MEASURE_LABELS[k] for k, o in orders.items() if o is None]))
    known = {k: o for k, o in orders.items() if o is not None}
    if len({tuple(o) for o in known.values()}) > 1:
        reasons.append("the order of period medians differs: " +
                       "; ".join(f"{MEASURE_LABELS[k]} {_order_text(o)}" for k, o in known.items()))
    return {"triggered": bool(reasons), "reason": "; ".join(reasons), "orders": orders}


def red_flag_prior_trend(s: pd.DataFrame) -> dict:
    p0 = s[s.rule_period == "P0"].sort_values("dirs_activation_date")
    p1 = s[s.rule_period == "P1"]
    if len(p0) < 2 or p1.empty:
        return {"triggered": False, "reason": "not enough storms to check"}
    half = len(p0) // 2
    early, late = p0.iloc[:half], p0.iloc[half:]

    def med(g):
        return median_with_censoring(g.t50.where(~g.t50_censored.astype(bool), g.censored_at), g.t50_censored.astype(bool))
    e, l, a, b = med(early), med(late), med(p0), med(p1)
    if None in (e, l, a, b):
        return {"triggered": True, "reason": "a median cannot be given, so a prior trend cannot be ruled out"}
    within, across = l - e, b - a
    hit = across != 0 and np.sign(within) == np.sign(across) and abs(within) >= 0.5 * abs(across)
    return {"triggered": bool(hit), "within_p0_change": _plain(within), "p0_to_p1_change": _plain(across),
            "reason": (f"median time to 50% changed by {within:+.1f} days within P0 and {across:+.1f} days from P0 to P1"
                       if hit else "")}


def red_flag_denominators(p: pd.DataFrame) -> dict:
    within, reasons = {}, []
    for key, g in p.groupby("storm_key"):
        n_rep = g.doc_id.nunique()
        full = g.groupby("fips").doc_id.nunique().pipe(lambda x: x[x == n_rep].index)
        tot = g[g.fips.isin(full)].groupby("doc_id").sites_served.sum()
        ratio = float(tot.max() / tot.min()) if len(tot) and tot.min() > 0 else None
        within[key] = ratio
        if ratio is not None and ratio > DENOMINATOR_MOVE_LIMIT:
            reasons.append(f"{g.storm.iloc[0]}: sites served over its always-listed counties moves by {100 * (ratio - 1):.0f}%")
    across = {}
    med = p.groupby(["rule_period", "fips"]).sites_served.median().unstack(0)
    periods = [c for c in PERIOD_CODES if c in med.columns]
    for a, b in zip(periods, periods[1:]):
        both = med[[a, b]].dropna()
        both = both[both[a] > 0]
        if len(both):
            r = float((both[b] / both[a]).median())
            across[f"{a}->{b}"] = {"median_ratio": r, "n_counties": len(both)}
            if not (1 / DENOMINATOR_MOVE_LIMIT <= r <= DENOMINATOR_MOVE_LIMIT):
                reasons.append(f"{a} to {b}: median county sites served changes by {100 * (r - 1):+.0f}%")
    return {"triggered": bool(reasons), "reason": "; ".join(reasons), "within_storm": within, "across_rule_dates": across}


def red_flag_activation_ends(s: pd.DataFrame) -> dict:
    reasons = []
    for col in ("days_peak_to_last", "still_out_share_at_last"):
        for code in s.rule_period.unique():
            g, other = s[s.rule_period == code][col], s[s.rule_period != code][col]
            if other.empty:
                continue
            if len(g) >= 2 and ((g > other.median()).all() or (g < other.median()).all()):
                reasons.append(f"{MEASURE_LABELS[col]}: every {code} storm is on one side of the other storms' median")
            if len(g) == 1 and not (other.min() <= g.iloc[0] <= other.max()):
                reasons.append(f"{MEASURE_LABELS[col]}: the one {code} storm lies outside the other storms' range")
    return {"triggered": bool(reasons), "reason": "; ".join(reasons)}


def red_flag_overlap(s: pd.DataFrame) -> dict:
    reasons = []
    for col in ("max_wind_kt", "peak_pct_out"):
        rng = s.groupby("rule_period")[col].agg(["min", "max"])
        for a in rng.index:
            for b in rng.index:
                if a < b and (rng.loc[a, "max"] < rng.loc[b, "min"] or rng.loc[b, "max"] < rng.loc[a, "min"]):
                    reasons.append(f"{MEASURE_LABELS[col]}: {a} and {b} do not overlap")
    return {"triggered": bool(reasons), "reason": "; ".join(reasons)}


def ch9_headline(by_period: dict, flag4: dict) -> str:
    """The author's chapter 9 sentence, with its facts taken from the results."""
    empty = [k for k, v in by_period.items() if v["n_storms"] == 0]
    single = [v["storm"] for v in by_period.values() if v["n_storms"] == 1]
    move = max(v for v in flag4["within_storm"].values() if v is not None)
    if len(empty) != 1 or len(single) != 1:
        raise ValueError("the chapter 9 sentence assumes one empty period and one single-storm period")
    return ("The public reports can't yet show whether the FCC's 2024–2025 rules coincided with any change in recovery: "
            f"one rule period has no storm, another has only {single[0]}, and the sites-served counts shift within storms "
            f"by as much as {100 * (move - 1):.0f}%.")


def ch9_wording(flags: dict) -> dict:
    hit = [k for k, v in flags.items() if v["triggered"]]
    return {"coincided_wording_allowed": not hit, "triggered_flags": hit,
            "allowed_wording": CH9_ALLOWED if not hit else None, "note": CH9_NOT_ALLOWED_NOTE if hit else ""}


def ch9_storm_table(panel: pd.DataFrame, storms: pd.DataFrame, results: dict) -> pd.DataFrame:
    c3 = {r["storm_key"]: r for r in results["chapter_3"]["storms"]}
    c4 = {r["storm_key"]: r for r in results["chapter_4"]["storms"]}
    rows = []
    for st in storms[storms.in_panel].sort_values("landfall_utc").itertuples():
        a, b = c3[st.storm_key], c4[st.storm_key]
        p = panel[panel.storm_key == st.storm_key]
        cty = p.drop_duplicates("fips")
        t50, t90 = b["time_to_50pct_restored"], b["time_to_90pct_restored"]
        curve = b["curve"]
        rows.append({"storm_key": st.storm_key, "storm": st.storm, "rule_period": st.rule_period,
                     "dirs_activation_date": str(st.dirs_activation_date),
                     "peak_sites_out": a["peak_sites_out"]["value"], "peak_pct_out": a["peak_pct_out"]["value"],
                     "t50": t50["value"], "t50_censored": t50["censored"],
                     "t90": t90["value"], "t90_censored": t90["censored"],
                     "t90_best": t90["best_case"], "t90_best_censored": t90["best_case_censored"],
                     "censored_at": curve[-1]["days_since_peak"],
                     "site_days_lost": b["site_days_lost"]["value"],
                     "max_wind_kt": _plain(float(cty.wind_kt_at_closest.max())),
                     "median_distance_km": _plain(float(cty.min_dist_km.median())),
                     "counties_inside_64kt": int(cty.in_64kt.astype(bool).sum()), "n_counties": int(len(cty)),
                     "days_peak_to_last": curve[-1]["days_since_peak"],
                     "still_out_share_at_last": _plain(1 - curve[-1]["restored_share"]),
                     "recovery_observed": b["n_reports_after_peak"] > 0})
    return pd.DataFrame(rows)


def chapter_9(panel: pd.DataFrame, storms: pd.DataFrame, results: dict) -> dict:
    s = ch9_storm_table(panel, storms, results)
    seen = s[s.recovery_observed]  # times and site-days: storms with a report after the peak (Nicole is footnoted)
    summary = {
        "peak_pct_out": period_summary(s, "peak_pct_out"), "peak_sites_out": period_summary(s, "peak_sites_out"),
        "time_to_50pct_restored": period_summary(seen, "t50", "t50_censored"),
        "time_to_90pct_restored_counties_leaving_stay_out": period_summary(seen, "t90", "t90_censored"),
        "time_to_90pct_restored_counties_leaving_restored": period_summary(seen, "t90_best", "t90_best_censored"),
        "site_days_lost": period_summary(seen, "site_days_lost"),
        "max_wind_kt": period_summary(s, "max_wind_kt"), "median_distance_km": period_summary(s, "median_distance_km"),
        "counties_inside_64kt": period_summary(s, "counties_inside_64kt"),
    }
    flags = {"1_drop_one_storm_reverses_order": red_flag_drop_one(seen),
             "2_order_depends_on_threshold_or_censoring": red_flag_measure_dependence(seen),
             "3_recovery_already_shortening_in_P0": red_flag_prior_trend(seen),
             "4_denominators_jump_or_move_over_10pct": red_flag_denominators(panel),
             "5_activations_end_differently_by_period": red_flag_activation_ends(seen),
             "6_no_overlap_in_wind_or_peak": red_flag_overlap(s)}
    periods = {code: {"label": label, "from": start, "to": end} for code, (label, start, end) in zip(PERIOD_CODES, REGIMES)}
    return {"periods": periods, "storms": s.to_dict("records"), "by_period": summary, "red_flags": flags,
            "storms_left_out_of_time_summaries": [{"storm": x, "note": NO_RECOVERY_NOTE.format(storm=x)}
                                                  for x in s[~s.recovery_observed].storm],
            "wording": ch9_wording(flags),
            "page_text": {"headline": ch9_headline(summary["peak_pct_out"], flags["4_denominators_jump_or_move_over_10pct"])},
            "notes": ["Descriptive only: no regression, test, p-value, hazard ratio or adjusted difference between periods.",
                      "With few storms per period, this is association, not proof.",
                      "Times to 90% are given under both treatments of counties that leave the reports.",
                      "Rule periods: MDRI from May 1, 2024; mandatory DIRS from February 20, 2025 (DA 25-74); FCC 26-34's changes from June 30, 2026 (Federal Register publication). Checked 2026-11-22."]}


# ---- chapters 1 and 2: the data, and Isaias ----

def coverage_table(panel: pd.DataFrame, storms: pd.DataFrame) -> list:
    out = []
    for st in storms.sort_values("dirs_activation_date").itertuples():
        p = panel[panel.storm_key == st.storm_key]
        rec = {"storm": st.storm, "nhc_id": st.nhc_id, "storm_key": st.storm_key,
               "rule_period": st.rule_period if isinstance(st.rule_period, str) else None,
               "dirs_activation_date": str(st.dirs_activation_date), "in_panel": bool(st.in_panel),
               "excluded_reports": st.excluded_reports}
        if len(p):
            rec.update(n_reports=int(p.doc_id.nunique()), n_counties=int(p.fips.nunique()), county_days=len(p),
                       first_report=str(p.report_date.min()), last_report=str(p.report_date.max()),
                       states=sorted(p.state.unique()), landfall_source=st.landfall_source)
        out.append(rec)
    return out


FLAG_TYPES = [  # (pattern, label, class) for the validation table by flag type (deviation, 2026-11-22)
    (r"^headline_mismatch", "Stated headline differs from the computed share (computed used)", "serious"),
    (r"^state_total_missing", "One state printed no total (its rows all confirmed)", "serious"),
    (r"^no_printed_totals", "No totals printed (every row confirmed)", "serious"),
    (r"rows outside_notice_area$", "County rows outside the FCC notice's area", "serious"),
    (r"rows table_not_in_list$", "County rows in the table but not in the report's list", "serious"),
    (r"^in table, not in the report's county list", "County rows in the table but not in the report's list", "serious"),
    (r"rows short of sites out", "Causes short of sites out (some sites with no cause)", "benign"),
    (r"^FCC spelling|rows inside_spelling_variant$", "County name spelling variant", "benign"),
    (r"^causes exceed sites out, confirmed by second reading", "Causes exceed sites out (confirmed in the PDF)", "benign"),
    (r"^causes exceed sites out, listed exception", "Causes exceed sites out (checked exception)", "benign"),
    (r"^listed more than once by the FCC", "County listed twice in the report's list", "benign"),
    (r"^in table, not in the report's list, listed exception", "County not in the list (checked exception)", "benign"),
    (r"^headline [\d.]+% vs [\d.]+% from the report's own totals", "Known FCC inconsistency in the headline", "benign"),
    (r"^every row confirmed by second reading$|^other states reconcile\)$", None, None),  # parts of longer flags
]


def flag_type_table(validation: pd.DataFrame, docs_in_use) -> list:
    v = validation[validation.doc_id.isin(set(docs_in_use))]
    counts = {}
    for doc, flags in zip(v.doc_id, v.flag_reasons.fillna("")):
        seen = set()
        for part in filter(None, flags.split("; ")):
            hit = next(((label, cls) for pat, label, cls in FLAG_TYPES if re.search(pat, part)), "unknown")
            if hit == "unknown":
                raise ValueError(f"unknown flag type, not classified: {part}")
            if hit[0]:
                seen.add(hit)
        for key in seen:
            counts[key] = counts.get(key, 0) + 1
    return [{"flag": label, "class": cls, "n_reports": n} for (label, cls), n in
            sorted(counts.items(), key=lambda kv: (kv[0][1] != "serious", -kv[1]))]


def chapter_1(panel: pd.DataFrame, storms: pd.DataFrame, manifest: pd.DataFrame) -> dict:
    excluded = pd.read_csv(MANIFEST.parent / "excluded_reports.csv", dtype=str, keep_default_na=False)
    in_scope = manifest[manifest.status != "out_of_scope"]
    validation = pd.read_csv(OUTPUT / "validation_dirs.csv", keep_default_na=False)
    all_rows = pd.read_parquet(INTERIM / "dirs_county_rows.parquet", columns=["doc_id", "state", "row_nhc_id"])
    used = set(panel.doc_id)
    no_rows = in_scope[~in_scope.doc_id.isin(used) & ~in_scope.doc_id.isin(set(excluded.doc_id))]
    for d in no_rows.doc_id:
        if all_rows[all_rows.doc_id == d].state.isin(STUDY_STATES).any():
            raise ValueError(f"{d} has study-state rows but is not in the panel")
    shared = panel.groupby("doc_id").storm_key.nunique()
    shared = sorted(shared[shared > 1].index)
    known = validation[validation.status == "known_fcc_inconsistency"].merge(
        manifest[["doc_id", "storm_name", "report_date"]], on="doc_id")
    status = {k: int(n) for k, n in validation.status.value_counts().items()}
    return {"headlines": {
                "n_storms": num(int(storms.in_panel.sum()), n=len(storms), unit="storms with reports in use",
                                method="storm key = NHC ID + DIRS activation date"),
                "n_reports_in_scope": num(len(in_scope), unit="FCC DIRS reports in scope", method="manifest/dirs_reports.csv"),
                "n_reports_used": num(int(panel.doc_id.nunique()), unit="reports used", method="passed step 4 or flagged"),
                "n_reports_excluded": num(len(excluded), unit="reports excluded", method="manifest/excluded_reports.csv"),
                "n_county_days": num(len(panel), unit="county-report rows", method="study states only"),
                "n_counties": num(int(panel.fips.nunique()), unit="counties"),
                "first_report": str(panel.report_date.min()), "last_report": str(panel.report_date.max())},
            "storms": coverage_table(panel, storms),
            "excluded_reports": excluded.to_dict("records"),
            "coverage_by_report": {s["storm"]: [
                {"doc_id": t.doc_id, "report_date": str(t.report_date), "days_since_landfall": _plain(t.days_since_landfall),
                 "sites_out": _plain(t.sites_out), "sites_served": _plain(t.sites_served), "pct_out": _plain(t.pct_out)}
                for t in report_totals(panel[panel.storm_key == s["storm_key"]]).itertuples()]
                for s in coverage_table(panel, storms) if s["in_panel"]},
            "reports_without_study_state_rows": [
                {"doc_id": r.doc_id, "storm": r.storm_name, "report_date": str(r.report_date),
                 "reason": "every county row is in a state outside the study states"} for r in no_rows.itertuples()],
            "time_flagged_reports": time_flagged_reports(panel),
            "reports_shared_by_two_storms": {"n": len(shared), "doc_ids": shared,
                                             "storms": sorted(panel[panel.doc_id.isin(shared)].storm.unique())},
            "validation": {"status_counts": status,
                           "flag_types_in_reports_used": flag_type_table(validation, used),
                           "known_fcc_inconsistencies": [
                               {"doc_id": k.doc_id, "storm": k.storm_name, "report_date": str(k.report_date),
                                "detail": k.flag_reasons} for k in known.itertuples()]}}


def state_by_report(p: pd.DataFrame) -> list:
    g = p.groupby(["report_date", "state"])[["sites_out", "sites_served"]].sum().reset_index()
    return [{"report_date": str(r.report_date), "state": r.state, "sites_out": _plain(r.sites_out),
             "sites_served": _plain(r.sites_served), "pct_out": _plain(100 * r.sites_out / r.sites_served)}
            for r in g.sort_values(["state", "report_date"]).itertuples()]


def county_peak_table(p: pd.DataFrame) -> list:
    q = p.assign(share=p.sites_out / p.sites_served).sort_values(["share", "sites_out"], ascending=False)
    top = q.drop_duplicates("fips")
    return [{"county": str(r.county).title(), "state": r.state, "fips": r.fips, "peak_report_date": str(r.report_date),
             "peak_sites_out": _plain(r.sites_out), "sites_served": _plain(r.sites_served),
             "peak_pct_out": _plain(100 * r.share)} for r in top.itertuples()]


def isaias_track() -> list:
    """Isaias 2026 best-track points (NHC GIS), for the chapter 2 map."""
    import importlib
    t = importlib.import_module("07_nhc").read_isaias_gis()
    return [{"time_utc": str(r.time_utc), "lat": _plain(r.lat), "lon": _plain(r.lon), "wind_kt": _plain(r.wind_kt)}
            for r in t.sort_values("time_utc").itertuples()]


def chapter_2(panel: pd.DataFrame, storms: pd.DataFrame) -> dict:
    st = storms[(storms.storm == "Isaias") & storms.in_panel].iloc[0]
    p = panel[panel.storm_key == st.storm_key]
    cty = p.drop_duplicates("fips")
    tot = p.groupby("report_date")[["sites_out", "sites_served"]].sum().reset_index()
    return {"storm_key": st.storm_key, "nhc_id": st.nhc_id, "rule_period": st.rule_period,
            "landfall_reference_utc": str(st.landfall_utc), "landfall_source": st.landfall_source,
            "area_by_report": [{"report_date": str(r.report_date), "sites_out": _plain(r.sites_out),
                                "sites_served": _plain(r.sites_served), "pct_out": _plain(100 * r.sites_out / r.sites_served)}
                               for r in tot.itertuples()],
            "state_by_report": state_by_report(p), "county_peaks": county_peak_table(p),
            "track": isaias_track(),
            "exposure": {"max_wind_kt_at_nearest_track_point": _plain(float(cty.wind_kt_at_closest.max())),
                         "counties_inside_34kt": int(cty.in_34kt.astype(bool).sum()),
                         "counties_inside_64kt": int(cty.in_64kt.astype(bool).sum()), "n_counties": len(cty),
                         "nearest_county_distance_km": _plain(float(cty.min_dist_km.min())),
                         "track_source": "NHC GIS best track (al092026_best_track.zip)"},
            "notes": [NO_POWER_STORMS_NOTE,
                      "Days are counted from the first time Isaias's 34-kt winds reach a study-state county in its reports."]}


def timed(panel: pd.DataFrame) -> pd.DataFrame:
    """The panel for time-based results: without reports carrying a time flag (decision 2026-11-23)."""
    return panel[panel.time_flag.fillna("") == ""] if "time_flag" in panel else panel


def time_flagged_reports(panel: pd.DataFrame) -> list:
    if "time_flag" not in panel:
        return []
    f = panel[panel.time_flag.fillna("") != ""].drop_duplicates("doc_id")
    return [{"doc_id": r.doc_id, "storm": r.storm, "report_date": str(r.report_date), "flag": r.time_flag,
             "days_since_landfall": _plain(r.days_since_landfall)} for r in f.itertuples()]


def main():
    panel = pd.read_parquet(PROCESSED / "panel.parquet")
    tp = timed(panel)  # chapters 3, 4, 8 and 9
    storms = pd.read_parquet(PROCESSED / "storms.parquet")
    manifest = pd.read_csv(MANIFEST)
    chapters = sys.argv[1:] or ["1", "2", "3", "4", "5", "6", "7", "8", "9"]
    if "1" in chapters:
        write_chapter(RESULTS, "chapter_1", chapter_1(panel, storms, manifest))
    if "2" in chapters:
        write_chapter(RESULTS, "chapter_2", chapter_2(panel, storms))
    if "3" in chapters:
        write_chapter(RESULTS, "chapter_3", chapter_3(tp, storms, manifest))
    if "4" in chapters:
        write_chapter(RESULTS, "chapter_4", chapter_4(tp, storms))
    if "5" in chapters:
        write_chapter(RESULTS, "chapter_5", chapter_5(panel, storms))
    if "6" in chapters:
        write_chapter(RESULTS, "chapter_6", chapter_6(panel, storms))
    if "7" in chapters:
        write_chapter(RESULTS, "chapter_7", chapter_7(panel, storms))
    if "8" in chapters:
        write_chapter(RESULTS, "chapter_8", chapter_8(tp, storms))
    if "9" in chapters:  # built from chapters 3 and 4 in results.json
        write_chapter(RESULTS, "chapter_9", chapter_9(tp, storms, json.loads(RESULTS.read_text(encoding="utf-8"))))
    print(f"chapters {', '.join(chapters)} written to {RESULTS.name}")


if __name__ == "__main__":
    main()
