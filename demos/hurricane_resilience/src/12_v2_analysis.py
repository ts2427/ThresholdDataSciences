"""Step 12: version 2 analyses (exploratory; docs/analysis_plan_addendum_v2.md), written to results.json as v2_* keys.

Version 1's code (step 10) and its chapter_* keys are not changed; tests/test_v1_results_unchanged.py checks that.

    python src/12_v2_analysis.py [items]      items: v2_1, v2_2, v2_3, v2_5_groups, v2_5 (default: all built)

V2-5, network redundancy: per storm-county, the number of mobile providers covering at least half the county's area
(main measure) in the latest BDC release on or before the storm's day 0, grouped on whole values as close to thirds as
ties allow (no group under 20%), fixed from counts only before any recovery data is joined. Recovery: chapter 8's
waiting time to stay below 5% of sites out. Main analysis: storms from 2022 on; earlier storms (earliest release,
"network data from after the storm") only as a sensitivity display. Fixed broadband counts (near-universal providers
excluded) are sensitivity displays only. Providers are never named; IDs are used only for counting.

V2-3, power vs. cell timing: per storm-county at risk on both measures, the report time (days since day 0, rebound
rule) at which the share of electricity customers without power falls below its threshold and at which the share of
cell sites out falls below its threshold; the order (power first, same report, cell first, undetermined) and the
lag. Power values are v1 chapter 6's matched, plausible EAGLE-I rows at each report's as-of time. Association only.

V2-2, backup power: sites operating on backup power by report and storm, where the FCC collected it (a report
collects it when it prints the column; a blank county value is not collected, never zero), as a count and as a
share of sites served in the counties with a printed value. Never described as predicted failures.

V2-1, what the public record misses: for each storm, from its last used report, the sites still out (count and share
of the storm's v1 peak) and the counties still out; and the counties that left the reports earlier while still out.
Descriptive only. The time-flag rule applies (time-flagged reports are not on a storm's timeline), so "last report"
and "left the reports" are taken on the panel without them.
"""
import importlib
import json
import sys

import numpy as np
import pandas as pd

from config import OUTPUT, PROCESSED

step9 = importlib.import_module("09_build_panel")
step10 = importlib.import_module("10_analysis")
RESULTS = OUTPUT / "results.json"


def _county(r) -> dict:
    return {"county": str(r.county).title(), "state": r.state, "fips": r.fips, "sites_out": step10._plain(r.sites_out),
            "sites_served": step10._plain(r.sites_served)}


def last_report_misses(p: pd.DataFrame, peak_sites_out: float) -> dict:
    """One storm (panel rows without time-flagged reports): its last report's sites still out, and where."""
    last_doc = (p.drop_duplicates("doc_id").sort_values(["days_since_landfall", "doc_id"]).doc_id.iloc[-1])
    last = p[p.doc_id == last_doc]
    out = last[last.sites_out > 0].sort_values(["sites_out", "state", "county"], ascending=[False, True, True])
    n_out = float(last.sites_out.sum())
    spans = step9.county_spans(p)
    left = spans[spans.censoring == "left_reports_while_out"].merge(
        p[["fips", "report_date", "sites_out", "sites_served", "county", "state"]],
        left_on=["fips", "last_report_date"], right_on=["fips", "report_date"])
    left = left.sort_values(["sites_out", "state", "county"], ascending=[False, True, True])
    carried = n_out + float(left.sites_out.sum())
    return {
        "last_report": {"doc_id": last_doc, "report_date": str(last.report_date.iloc[0]),
                        "days_since_day0": step10._plain(last.days_since_landfall.iloc[0])},
        "sites_out_at_last_report": step10.num(n_out, n=int(last.fips.nunique()), unit="cell sites out",
                                               method="sum over the last report's counties"),
        "share_of_peak": step10.num(n_out / peak_sites_out if peak_sites_out else None, n=1,
                                    unit="share of the storm's peak sites out", method="last report / v1 peak"),
        "counties_still_out": [_county(r) for r in out.itertuples()],
        "n_counties_in_last_report": int(last.fips.nunique()),
        "counties_left_while_out": [{**_county(r), "last_report_date": str(r.last_report_date)} for r in left.itertuples()],
        "carried_forward": {
            "sites_out": step10.num(carried, n=int(len(out) + len(left)), unit="cell sites out",
                                    method="last report plus counties that left while out, at their last reported value"),
            "share_of_peak": step10.num(carried / peak_sites_out if peak_sites_out else None, n=1,
                                        unit="share of the storm's peak sites out")},
    }


NICOLE_NOTE = "{storm}: its last report is its peak, so the share still out is 100% by construction."
SHARED_NOTE = "{storm}: its {n} reports are shared with {other}, so its record is short."
UPPER_BOUND_WORDING = "if every county that left the reports while still out had stayed out"


def shared_only_note(storm_key: str, panel: pd.DataFrame) -> str | None:
    """A storm all of whose reports are shared with another storm (Nicholas, in the combined Ida reports)."""
    docs = set(panel[panel.storm_key == storm_key].doc_id)
    others = panel[panel.doc_id.isin(docs) & (panel.storm_key != storm_key)]
    if docs and set(others.doc_id) == docs:
        return SHARED_NOTE.format(storm=panel[panel.storm_key == storm_key].storm.iloc[0], n=len(docs),
                                  other=", ".join(sorted(others.storm.unique())))
    return None


def v2_1(panel: pd.DataFrame, storms: pd.DataFrame, results: dict) -> dict:
    tp = step10.timed(panel)
    c3 = {s["storm_key"]: s for s in results["chapter_3"]["storms"]}
    c4 = {s["storm_key"]: s for s in results["chapter_4"]["storms"]}
    per, sens = [], []
    unserious = step10.without_serious(tp)
    for st in storms[storms.in_panel].sort_values("landfall_utc").itertuples():
        p = tp[tp.storm_key == st.storm_key]
        peak = c3[st.storm_key]["peak_sites_out"]["value"]
        rec = {"storm_key": st.storm_key, "storm": st.storm, "rule_period": st.rule_period, "peak_sites_out": peak,
               **last_report_misses(p, peak)}
        notes = []
        rec["recovery_observed"] = c4[st.storm_key]["n_reports_after_peak"] > 0
        if not rec["recovery_observed"]:
            notes.append(NICOLE_NOTE.format(storm=st.storm))
        if (sn := shared_only_note(st.storm_key, tp)):
            notes.append(sn)
        if notes:
            rec["note"] = " ".join(notes)
        per.append(rec)
        q = unserious[unserious.storm_key == st.storm_key]
        if len(q):
            m = last_report_misses(q, peak)
            sens.append({"storm": st.storm, "last_report_date": m["last_report"]["report_date"],
                         "sites_out_at_last_report": m["sites_out_at_last_report"]["value"],
                         "share_of_peak": m["share_of_peak"]["value"]})
        else:
            sens.append({"storm": st.storm, "note": "every report carries a serious flag"})
    # Headline: every storm. Median and upper bound: storms with a report after the peak (Nicole, whose share is 100%
    # by construction, is left out, as in chapter 4); footnoted storms are kept unless that rule removes them.
    main = [r for r in per if r["recovery_observed"]]
    shares = [r["share_of_peak"]["value"] for r in main]
    total = sum(r["sites_out_at_last_report"]["value"] for r in per)
    upper = [r["carried_forward"]["share_of_peak"]["value"] for r in main]
    all_out = all(r["sites_out_at_last_report"]["value"] > 0 for r in per)
    page = {
        "headline": (f"In {'all ' if all_out else ''}{len(per)} storms, the FCC's last public report still showed cell "
                     f"sites out: {total:,.0f} in total."),
        "lead": (f"Still out in the FCC's last report: a median of {100 * float(pd.Series(shares).median()):.1f}% of the "
                 f"storm's peak sites out ({len(shares)} storms). Upper bound, {UPPER_BOUND_WORDING}: a median of "
                 f"{100 * float(pd.Series(upper).median()):.1f}%."),
        "footnotes": [r["note"] for r in per if "note" in r],
        "upper_bound_wording": UPPER_BOUND_WORDING,
        "upper_bound_rule": "shown only beside the last-report measure, never by itself",
    }
    return {
        "label": "Exploratory: added after the version 1 results were published (docs/analysis_plan_addendum_v2.md).",
        "headlines": {
            "n_storms": len(per),
            "n_storms_in_headline": len(per),
            "n_storms_in_median": len(main),
            "storms_footnoted": [r["storm"] for r in per if "note" in r],
            "sites_out_at_last_reports_headline": step10.num(total, n=len(per), unit="cell sites out, summed over "
                                                             "every storm"),
            "median_share_of_peak_upper_bound": step10.num(float(pd.Series(upper).median()), n=len(upper),
                                                           unit="share of peak", method=UPPER_BOUND_WORDING,
                                                           min=min(upper), max=max(upper)),
            "n_storms_with_sites_out_at_last_report": sum(r["sites_out_at_last_report"]["value"] > 0 for r in per),
            "sites_out_at_last_reports_all_storms": step10.num(sum(r["sites_out_at_last_report"]["value"] for r in per),
                                                               n=len(per), unit="cell sites out, summed over all storms"),
            "median_share_of_peak_still_out": step10.num(float(pd.Series(shares).median()), n=len(shares),
                                                         unit="share of peak", method="median across storms with a report "
                                                         "after the peak (Nicole left out)",
                                                         min=min(shares), max=max(shares)),
        },
        "page_text": page,
        "storms": per,
        "sensitivity": {"without_serious_flag_reports": sens,
                        "carried_forward": "per storm: carried_forward (counties that left while out kept at their "
                                           "last reported value)"},
        "wording": "Still out in the FCC's last report; never 'never restored' or 'abandoned'. Shares are of the "
                   "storm's peak sites out, not of sites served.",
    }


BACKUP_WORDING = ("Sites operating on backup power, as the FCC reports them; never 'about to fail', 'at risk' or "
                  "'predicted failures', and no claim about how long backup lasts or what follows.")


def backup_by_report(p: pd.DataFrame) -> list:
    """One storm (panel without time-flagged reports): per report, sites on backup power where printed."""
    out = []
    for doc, g in p.groupby("doc_id"):
        printed = g[g.on_backup_power.notna()]
        rec = {"doc_id": doc, "report_date": str(g.report_date.iloc[0]),
               "days_since_day0": step10._plain(g.days_since_landfall.iloc[0]),
               "collected": bool(len(printed)), "n_counties_listed": int(g.fips.nunique()),
               "n_counties_printed": int(printed.fips.nunique())}
        if len(printed):
            on, served = float(printed.on_backup_power.sum()), float(printed.sites_served.sum())
            rec.update(sites_on_backup=step10._plain(on), sites_served_printed=step10._plain(served),
                       share_of_sites_served=step10._plain(on / served) if served else None,
                       share_of_all_sites_served=step10._plain(on / float(g.sites_served.sum()))
                       if g.sites_served.sum() else None,
                       partial=bool(len(printed) < len(g)))
        out.append(rec)
    return sorted(out, key=lambda r: (r["days_since_day0"], r["doc_id"]))


def flagged_backup(panel: pd.DataFrame) -> list:
    """Time-flagged reports (off the timeline) that print the backup-power column, for a footnote."""
    if "time_flag" not in panel:
        return []
    f = panel[(panel.time_flag.fillna("") != "") & panel.on_backup_power.notna()]
    return [{"storm": g.storm.iloc[0], "report_date": str(g.report_date.iloc[0]), "doc_id": d,
             "n_counties_printed": int(g.fips.nunique()), "sites_on_backup": float(g.on_backup_power.sum())}
            for d, g in f.groupby("doc_id")]


def v2_2(panel: pd.DataFrame, storms: pd.DataFrame) -> dict:
    tp = step10.timed(panel)
    per, not_collected = [], []
    for st in storms[storms.in_panel].sort_values("landfall_utc").itertuples():
        rows = backup_by_report(tp[tp.storm_key == st.storm_key])
        got = [r for r in rows if r["collected"]]
        if not got:
            not_collected.append(st.storm)
            continue
        top = max(got, key=lambda r: (r["sites_on_backup"], -r["days_since_day0"]))
        per.append({"storm_key": st.storm_key, "storm": st.storm, "rule_period": st.rule_period,
                    "n_reports": len(rows), "n_reports_collected": len(got),
                    "all_reports_collected": len(got) == len(rows),
                    "any_partial_report": any(r["partial"] for r in got),
                    "most_sites_on_backup": {"value": top["sites_on_backup"], "report_date": top["report_date"],
                                             "days_since_day0": top["days_since_day0"],
                                             "share_of_sites_served": top["share_of_sites_served"]},
                    "by_report": rows})
    full = [r for r in per if r["all_reports_collected"]]
    few = [r for r in per if not r["all_reports_collected"]]
    laura = [r for r in few if r["any_partial_report"] and r["n_reports_collected"] == 1]  # Laura's rule, Delta too
    page = {
        "collected_sentence": (f"The FCC printed sites operating on backup power for {len(per)} of "
                               f"{len(per) + len(not_collected)} storms: in every report for "
                               f"{step10._and_list([r['storm'] for r in full])}, and in one report each for "
                               f"{step10._and_list([r['storm'] for r in few])}. It did not print them for "
                               f"{step10._and_list(not_collected)}."),
        "footnotes": [f"{r['storm']}: its one report with backup power prints it for "
                      f"{r['by_report'][[x['collected'] for x in r['by_report']].index(True)]['n_counties_printed']} of "
                      f"{r['by_report'][[x['collected'] for x in r['by_report']].index(True)]['n_counties_listed']} "
                      f"counties" + (", so it is left out of comparisons." if r in laura else ".") for r in few]
                     + [f"{x['storm']}'s report of {x['report_date']}, kept off {x['storm']}'s timeline (the combined "
                        f"Marco–Laura report), also prints backup power for {x['n_counties_printed']} counties, with "
                        f"{x['sites_on_backup']:.0f} sites on backup power." for x in flagged_backup(panel)],
        "left_out_of_comparisons": [r["storm"] for r in laura],
        "display_rules": ["counts first; any share is shown with its sites served beside it",
                          "no comparison across rule periods; only which storms the column was printed for"],
    }
    return {
        "label": "Exploratory: added after the version 1 results were published (docs/analysis_plan_addendum_v2.md).",
        "headlines": {
            "storms_collected": [r["storm"] for r in per], "storms_not_collected": not_collected,
            "storms_collected_in_every_report": [r["storm"] for r in full],
            "storms_collected_in_some_reports": [r["storm"] for r in per if not r["all_reports_collected"]],
            "largest_count_on_backup": max(({"storm": r["storm"], **r["most_sites_on_backup"]} for r in per),
                                           key=lambda x: x["value"]) if per else None,
        },
        "page_text": page,
        "storms": per,
        "sensitivity": {"share_of_all_sites_served": "per report: share_of_all_sites_served (denominator: every "
                                                     "county in the report, printed value or not)"},
        "wording": BACKUP_WORDING,
    }


TIMING_THRESHOLD_PCT = 5.0     # addendum V2-3 (approved 2026-11-23): both measures, below 5%
TIMING_SENS_THRESHOLD_PCT = 10.0
ORDERS = ["power_first", "same_report", "cell_first", "undetermined"]
TIMING_WORDING = ("Power outages fell below the threshold before / at the same report as / after cell outages did; "
                  "association only, never 'power restoration restores cell sites', 'drives' or 'explains'. 'Same "
                  "report' means within one report interval. EAGLE-I customers are meters.")


def crossing(days, pct, threshold: float, rule=step10.stay_index) -> dict | None:
    """One series (report times, % out): None if never at or above the threshold (not at risk); otherwise the time it
    falls below by the rule, or censored at its last observed time."""
    days, pct = np.asarray(days, float), np.asarray(pct, float)
    if not (pct >= threshold).any():
        return None
    start = int(np.flatnonzero(pct >= threshold)[0])
    i = rule(pct[start:], threshold, below=True)
    if i is None:
        return {"event": False, "time": float(days[-1])}
    return {"event": True, "time": float(days[start + i])}


def order(power: dict, cell: dict) -> str:
    if power["event"] and cell["event"]:
        return "same_report" if power["time"] == cell["time"] else ("power_first" if power["time"] < cell["time"]
                                                                     else "cell_first")
    if power["event"] and power["time"] < cell["time"]:
        return "power_first"           # cell still at or above it later (censored after power fell below)
    if cell["event"] and cell["time"] < power["time"]:
        return "cell_first"
    return "undetermined"


def timing_records(panel: pd.DataFrame, threshold: float = TIMING_THRESHOLD_PCT, rule=step10.stay_index,
                   coverage_ok=None) -> pd.DataFrame:
    """Storm-counties at risk on both measures, with each crossing, the order and the lag (cell minus power)."""
    pw = step10.power_frame(panel, lag=0)
    pw = pw.assign(days=panel.loc[pw.index, "days_since_landfall"].to_numpy())
    if coverage_ok is not None:
        pw = pw[pw.coverage.map(coverage_ok)]
    cells = panel[panel.sites_served > 0]
    out = []
    for (key, fips), g in pw.groupby(["storm_key", "fips"]):
        g = g.sort_values("days")
        c = cells[(cells.storm_key == key) & (cells.fips == fips)].sort_values("days_since_landfall")
        p_x = crossing(g.days, g.pct_customers_out, threshold, rule)
        c_x = crossing(c.days_since_landfall, 100 * c.sites_out / c.sites_served, threshold, rule)
        if p_x is None or c_x is None:
            continue
        o = order(p_x, c_x)
        out.append({"storm_key": key, "storm": g.storm.iloc[0], "fips": fips, "rule_period": c.rule_period.iloc[0],
                    "power_event": p_x["event"], "power_time": p_x["time"], "cell_event": c_x["event"],
                    "cell_time": c_x["time"], "order": o,
                    "lag_days": c_x["time"] - p_x["time"] if p_x["event"] and c_x["event"] else np.nan,
                    "coverage": g.coverage.iloc[0]})
    return pd.DataFrame(out)


def order_summary(t: pd.DataFrame, seed: int, draws: int = step10.BOOTSTRAP_DRAWS) -> dict:
    """Shares of each order with a storm bootstrap 95% interval; median and IQR of the lag where both occur."""
    if t.empty:
        return {"n": 0}
    keys = t.storm_key.unique()
    counts = t.groupby("storm_key").order.value_counts().unstack(fill_value=0).reindex(columns=ORDERS, fill_value=0)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(draws, len(keys)))
    tot = counts.to_numpy()[idx].sum(axis=1)
    share = tot / tot.sum(axis=1, keepdims=True)
    lo, hi = np.percentile(share, step10.CI, axis=0)
    point = counts.sum() / counts.to_numpy().sum()
    lag = t.lag_days.dropna()
    return {"n": int(len(t)), "n_storms": int(len(keys)),
            "orders": {o: {"count": int(counts[o].sum()), "share": step10._plain(point[o]),
                           "ci_low": step10._plain(lo[j]), "ci_high": step10._plain(hi[j])} for j, o in enumerate(ORDERS)},
            "lag_days_where_both": {"n": int(len(lag)), "median": step10._plain(lag.median()) if len(lag) else None,
                                    "q1": step10._plain(lag.quantile(0.25)) if len(lag) else None,
                                    "q3": step10._plain(lag.quantile(0.75)) if len(lag) else None},
            "method": f"storm bootstrap 95%, {draws} draws; lag = cell time minus power time, in days"}


TIMING_UNMEASURED = ["portable cell sites brought in after the storm", "generators placed at cell sites",
                     "service carried by other networks (roaming)", "the order in which crews restore lines",
                     "repairs to the network connections that link sites (backhaul)"]
SCALE_CAUTION = ("The two thresholds are on different scales: cell's 5% is of sites served, and power's 5% is of EAGLE-I "
                 "meters, so \"cell first\" doesn't mean phone service returned before household power.")


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def v2_3_page_text(h: dict, periods: dict) -> dict:
    o, lag = h["orders"], h["lag_days_where_both"]
    determined = h["n"] - o["undetermined"]["count"]
    more = "cell sites out" if o["cell_first"]["count"] > o["power_first"]["count"] else "customers without power"
    other = "customers without power" if more == "cell sites out" else "cell sites out"
    u = o["undetermined"]
    return {
        "finding": (f"Where the order could be determined ({determined} of {h['n']} counties, as defined), cell outages "
                    f"fell below 5% first in {o['cell_first']['count']} counties and power outages first in "
                    f"{o['power_first']['count']}; in {o['same_report']['count']} both fell below 5% in the same report. "
                    f"Where both fell below 5% ({lag['n']} counties), the median gap is {lag['median']:.0f} days."),
        "undetermined": (f"For the other {u['count']} counties ({pct(u['share'])}, 95% interval {pct(u['ci_low'])} to "
                         f"{pct(u['ci_high'])}), the order can't be determined because a county left the reports, or "
                         f"its power record ended, first."),
        "scale_caution": SCALE_CAUTION,
        "not_measured": ("Factors this data doesn't measure, any of which could bear on the order: "
                         + step10._and_list(TIMING_UNMEASURED) + "."),
        "rule_periods_shown_not_compared": [
            f"{code}: {v['n']} counties in {v['n_storms']} storms; power first {pct(v['orders']['power_first']['share'])}, "
            f"same report {pct(v['orders']['same_report']['share'])}, cell first {pct(v['orders']['cell_first']['share'])}, "
            f"undetermined {pct(v['orders']['undetermined']['share'])}" for code, v in periods.items()],
    }


def v2_3(panel: pd.DataFrame) -> dict:
    tp = step10.timed(panel)
    main = timing_records(tp)
    by_storm = {g.storm.iloc[0]: {"n": int(len(g)), **{o: int((g.order == o).sum()) for o in ORDERS},
                                  "median_lag_days": step10._plain(g.lag_days.median()) if g.lag_days.notna().any() else None}
                for _, g in main.groupby("storm_key", sort=False)}
    sens = {
        "threshold_10pct": order_summary(timing_records(tp, TIMING_SENS_THRESHOLD_PCT), step10.SEED + 610),
        "first_crossing": order_summary(timing_records(tp, rule=step10.first_index), step10.SEED + 620),
        "without_low_or_unknown_coverage": order_summary(
            timing_records(tp, coverage_ok=lambda c: c not in ("low_coverage", "coverage_unknown")), step10.SEED + 630),
        "without_serious_flag_reports": order_summary(timing_records(step10.without_serious(tp)), step10.SEED + 640),
        "by_rule_period_shown_not_compared": {code: order_summary(main[main.rule_period == code], step10.SEED + 650 + i)
                                              for i, code in enumerate(sorted(main.rule_period.unique()))},
    }
    return {
        "label": "Exploratory: added after the version 1 results were published (docs/analysis_plan_addendum_v2.md).",
        "thresholds": {"power_pct_customers": TIMING_THRESHOLD_PCT, "cell_pct_sites": TIMING_THRESHOLD_PCT,
                       "at_risk": "at or above the threshold on both measures in at least one report"},
        "headlines": (head := order_summary(main, step10.SEED + 600)),
        "page_text": v2_3_page_text(head, sens["by_rule_period_shown_not_compared"]),
        "storms_without_power_data": sorted(set(tp.storm) - set(step10.power_frame(tp).storm)),
        "storms_without_counties_at_risk": sorted(set(step10.power_frame(tp).storm) - set(main.storm)),
        "by_storm": by_storm,
        "sensitivity": sens,
        "wording": TIMING_WORDING,
    }


# ---- V2-5: network redundancy ----

BDC = None  # loaded on demand
NEAR_UNIVERSAL_SHARE = 0.95
NEAR_UNIVERSAL_LABEL = ("near-universal providers (likely satellite or national fixed-wireless; this file doesn't "
                        "identify technology)")
MIN_GROUP_SHARE = 0.20
MEASURES = {  # name: (data_type, threshold on the coverage share, exclude near-universal providers)
    "mobile_half": ("Mobile Broadband", 0.5, False),      # main measure (Tim's decision, 2026-11-23)
    "mobile_any": ("Mobile Broadband", 0.0, False),
    "fixed_any_excl_near_universal": ("Fixed Broadband", 0.0, True),
    "fixed_any": ("Fixed Broadband", 0.0, False),
    "fixed_half": ("Fixed Broadband", 0.5, False),
    "fixed_half_excl_near_universal": ("Fixed Broadband", 0.5, True),
}
MAIN_MEASURE = "mobile_half"


def near_universal(b: pd.DataFrame) -> set:
    """Fixed providers reporting service in at least 95% of the study-state counties of some release."""
    n_cty = b.groupby("release").geoid.nunique()
    fx = b[(b.data_type == "Fixed Broadband") & (b.res_st_pct > 0)].groupby(["release", "provider_id"]).geoid.nunique()
    return {p for (r, p), n in fx.items() if n >= NEAR_UNIVERSAL_SHARE * n_cty[r]}


def provider_counts(b: pd.DataFrame, measure: str, universal: set) -> pd.Series:
    data_type, thr, excl = MEASURES[measure]
    q = b[(b.data_type == data_type) & ((b.res_st_pct > 0) if thr == 0 else (b.res_st_pct >= thr))]
    if excl:
        q = q[~q.provider_id.isin(universal)]
    return q.groupby(["release", "geoid"]).provider_id.nunique()


def whole_value_groups(values: pd.Series, min_share: float = MIN_GROUP_SHARE) -> dict:
    """Three groups on whole values (<= a, a < x <= b, > b), as close to thirds as ties allow, none under min_share.
    Chosen from the counts alone."""
    v = values.astype(int)
    vals = sorted(v.unique())
    n = len(v)
    best = None
    for i, a in enumerate(vals):
        for b in vals[i + 1:]:
            sizes = [(v <= a).sum(), ((v > a) & (v <= b)).sum(), (v > b).sum()]
            if min(sizes) < min_share * n:
                continue
            score = sum((sz / n - 1 / 3) ** 2 for sz in sizes)
            if best is None or score < best[0]:
                best = (score, a, b, sizes)
    if best is None:
        return {"groups": None, "note": f"no three groups with each at least {min_share:.0%}"}
    _, a, b, sizes = best
    lo, mid, hi = (f"{a} or fewer", f"{a + 1}" if b == a + 1 else f"{a + 1} to {b}", f"{b + 1} or more")
    return {"cut_low": int(a), "cut_high": int(b), "labels": [lo, mid, hi],
            "sizes": {lo: int(sizes[0]), mid: int(sizes[1]), hi: int(sizes[2])}, "n": int(n),
            "rule": "whole values, as close to thirds as ties allow, no group under 20% of storm-counties"}


def assign_group(x: float, g: dict) -> str | None:
    if g.get("labels") is None:
        return None
    return g["labels"][0] if x <= g["cut_low"] else (g["labels"][1] if x <= g["cut_high"] else g["labels"][2])


def county_counts(b: pd.DataFrame) -> tuple:
    """Each measure's provider count by release and county, and the number of near-universal providers. Only counts
    leave this function: no provider ID is kept (step 6f writes the result)."""
    universal = near_universal(b)
    c = pd.concat([provider_counts(b, m, universal).rename(m) for m in MEASURES], axis=1).fillna(0).astype(int)
    c = c.rename_axis(["release", "fips"]).reset_index().sort_values(["release", "fips"], ignore_index=True)
    return c, len(universal)


def load_counts() -> tuple:
    from config import BDC_COUNTS, BDC_COUNTS_META
    c = pd.read_csv(BDC_COUNTS, dtype={"release": str, "fips": str})
    return c, int(json.loads(BDC_COUNTS_META.read_text(encoding="utf-8"))["n_near_universal_providers"])


def storm_county_counts(panel: pd.DataFrame, counts: pd.DataFrame, releases: dict, n_universal: int) -> pd.DataFrame:
    """Every storm-county in the panel with each measure's provider count in the storm's release (0 if none)."""
    sc = panel.drop_duplicates(["storm_key", "fips"])[["storm_key", "storm", "fips"]].copy()
    sc["release"] = sc.storm.map(lambda x: releases[x]["release"])
    sc["role"] = sc.storm.map(lambda x: releases[x]["role"].split(":")[0])
    sc = sc.merge(counts[["release", "fips", *MEASURES]], on=["release", "fips"], how="left", validate="many_to_one")
    for m in MEASURES:
        sc[m] = sc[m].fillna(0).astype(int)
    sc.attrs["n_near_universal"] = n_universal
    return sc


def v2_5_groups(panel: pd.DataFrame) -> dict:
    """Counts only: groups for every measure, from the main-analysis storm-counties (2022 on). No recovery data."""
    from config import RAW
    releases = json.loads((RAW / "bdc" / "listings" / "storm_releases.json").read_text(encoding="utf-8"))
    counts, n_universal = load_counts()
    sc = storm_county_counts(step10.timed(panel), counts, releases, n_universal)
    main = sc[sc.role == "main"]
    return {"label": "Exploratory: added after the version 1 results were published (docs/analysis_plan_addendum_v2.md).",
            "fixed_from_counts_only": True, "main_measure": MAIN_MEASURE,
            "near_universal_label": NEAR_UNIVERSAL_LABEL, "n_near_universal_providers": sc.attrs["n_near_universal"],
            "storm_releases": releases, "n_storm_counties_main": int(len(main)),
            "groups": {m: whole_value_groups(main[m]) for m in MEASURES},
            "distributions": {m: {str(k): int(v) for k, v in main[m].value_counts().sort_index().items()}
                              for m in MEASURES}}


REDUNDANCY_WORDING = ("Association only: counties served by more mobile providers fell below 5% of sites out sooner / "
                      "later / with no measurable difference; never that more providers produce faster recovery. "
                      "Provider counts describe reported coverage, not which networks were out. Providers are never "
                      "named.")


def km_by_group(recs: pd.DataFrame, col: str, labels: list, seed: int) -> dict:
    """Kaplan-Meier median wait (days since day 0) by group, county bootstrap 95%, as in chapter 8's raw table."""
    out, rng = {}, np.random.default_rng(seed)
    for lab in labels:
        g = recs[recs[col] == lab]
        if g.empty:
            out[lab] = {"n": 0}
            continue
        t, e = g.time.to_numpy(float), g.event.to_numpy(bool)
        boot = []
        for _ in range(step10.BOOTSTRAP_DRAWS):
            j = rng.integers(0, len(g), len(g))
            m = step10.km_median(step10.kaplan_meier(t[j], e[j]))
            boot.append(np.inf if m is None else m)
        lo, hi = step10._time_ci(np.array(boot))
        km = step10.kaplan_meier(t, e)
        out[lab] = {"median_days": step10.num(step10.km_median(km), lo, hi, n=len(g), unit="days since day 0",
                                              method="Kaplan-Meier median; county bootstrap 95%",
                                              n_censored=int((~e).sum())),
                    **{f"share_below_5pct_by_day_{d}": step10._plain(step10.km_share_by(km, d)) for d in (3, 7, 14)},
                    "n_storms": int(g.storm_key.nunique())}
    return out


def _pp_with(recs: pd.DataFrame, extra: list) -> pd.DataFrame:
    rows = []
    for r in recs.itertuples():
        w = r._asdict()
        for p in step10.person_periods(w):
            rows.append({"storm_key": r.storm_key, "fips": r.fips, "svi_q": r.svi_q, "zone": r.zone,
                         "min_dist_km": r.min_dist_km, "wind_kt_at_closest": r.wind_kt_at_closest,
                         **{c: w[c] for c in extra}, **p})
    return pd.DataFrame(rows)


def fit_hazard_with(pp: pd.DataFrame, group_col: str | None = None, levels: list | None = None,
                    numeric_col: str | None = None) -> tuple:
    """Chapter 8's discrete-time cloglog hazard (same design, storm fixed effects, county-clustered intervals, same
    convergence rule) with the redundancy group (reference: the first level) or a count added."""
    import statsmodels.api as sm
    ev = pp.groupby("storm_key").event.agg(["sum"])
    n_cty = pp.groupby("storm_key").fips.nunique()
    county_events = pp.groupby(["storm_key", "fips"]).event.max().groupby("storm_key").sum()
    keep = ev.index[(ev["sum"] > 0) & (county_events < n_cty)]
    q = pp[pp.storm_key.isin(keep)].copy()
    q["bin"] = q.t1.map(step10._baseline_bin)
    X = pd.DataFrame({"const": 1.0}, index=q.index)
    for col, prefix, lv in (("bin", "base", [b[2] for b in step10.BASELINE_BINS][1:]),
                            ("svi_q", "svi", step10.SVI_LABELS[1:]), ("zone", "zone", step10.ZONES[:-1])):
        for v in lv:
            X[f"{prefix}_{v}"] = (q[col] == v).astype(float)
    if group_col:
        for v in levels[1:]:
            X[f"group_{v}"] = (q[group_col] == v).astype(float)
    if numeric_col:
        X[f"per_provider_{numeric_col}"] = q[numeric_col].astype(float)
    X["log1p_dist_km"] = np.log1p(q.min_dist_km.astype(float))
    X["wind_per_10kt"] = q.wind_kt_at_closest.astype(float) / 10
    for k in sorted(keep)[1:]:
        X[f"storm_{k}"] = (q.storm_key == k).astype(float)
    X = X.loc[:, (X.std() > 0) | (X.columns == "const")]
    offset = np.log(np.clip((q.t1 - q.t0).astype(float), step10.MIN_INTERVAL_DAYS, None))
    model = sm.GLM(q.event.astype(float), X, family=sm.families.Binomial(link=sm.families.links.CLogLog()),
                   offset=offset)
    groups = {"groups": pd.factorize(q.fips)[0]}
    fit, optimizer = model.fit(cov_type="cluster", cov_kwds=groups), "IRLS"
    if not step10.irls_ok(fit):
        fit = model.fit(method="newton", start_params=np.zeros(X.shape[1]), maxiter=300, disp=0, cov_type="cluster",
                        cov_kwds=groups)
        grad = float(np.abs(model.score(fit.params)).max())
        if not (fit.mle_retvals.get("converged") and grad < step10.MAX_SCORE):
            raise step10.NotEstimable(f"no reachable finite maximum (gradient {grad:.1e})")
        optimizer = "Newton's method (IRLS did not converge)"
    ci = fit.conf_int()
    hr = {k: step10.num(float(np.exp(fit.params[k])), float(np.exp(ci.loc[k, 0])), float(np.exp(ci.loc[k, 1])),
                        n=int(fit.nobs), unit="hazard ratio (above 1 = reaches below 5% sooner)",
                        method="discrete-time cloglog; storm fixed effects; county-clustered 95%")
          for k in fit.params.index if k.startswith(("group_", "per_provider_", "svi_"))}
    return hr, {"storms_in_model": sorted(keep), "n_intervals": int(len(q)), "n_events": int(q.event.sum()),
                "n_counties": int(q.fips.nunique()), "optimizer": optimizer}


def _model(recs, extra, **kw) -> dict:
    try:
        hr, info = fit_hazard_with(_pp_with(recs, extra), **kw)
        return {"hazard_ratios": hr, **info}
    except Exception as err:  # reported, not hidden
        return {"error": f"{type(err).__name__}: {err}", "error_reason": str(err)}


def v2_5(panel: pd.DataFrame, results: dict) -> dict:
    gdef = results["v2_5_groups"]
    counts, n_universal = load_counts()
    tp = step10.timed(panel)
    sc = storm_county_counts(tp, counts, gdef["storm_releases"], n_universal)
    cuts = results["chapter_8"]["headlines"]["svi_quartile_cut_points"]  # v1's SVI quartiles, unchanged

    def prepared(p: pd.DataFrame) -> pd.DataFrame:
        r = step10.waiting_records(p)
        r["svi_q"] = pd.cut(r.svi, [-np.inf, *cuts, np.inf], labels=step10.SVI_LABELS, right=True).astype(str)
        r = r.merge(sc, on=["storm_key", "storm", "fips"], how="left", validate="many_to_one")
        for m, g in gdef["groups"].items():
            if g.get("labels"):
                r[f"grp_{m}"] = r[m].map(lambda x, g=g: assign_group(x, g))
        return r

    recs = prepared(tp)
    main = recs[recs.role == "main"]
    G = gdef["groups"][MAIN_MEASURE]
    col = f"grp_{MAIN_MEASURE}"
    out = {
        "label": gdef["label"], "main_measure": MAIN_MEASURE, "groups": G,
        "storms_main": sorted(main.storm.unique()),
        "n_at_risk_storm_counties_main": int(len(main)),
        "at_risk_by_group": {k: int((main[col] == k).sum()) for k in G["labels"]},
        "raw_by_group": km_by_group(main, col, G["labels"], step10.SEED + 700),
        "model": _model(main, [col], group_col=col, levels=G["labels"]),
    }
    sens = {"provider_count_as_number": _model(main, [MAIN_MEASURE], numeric_col=MAIN_MEASURE),
            "mobile_any_coverage_count_as_number": _model(main, ["mobile_any"], numeric_col="mobile_any")}
    allst = recs  # all storms: pre-2022 storms with the earliest release ("network data from after the storm")
    sens["including_storms_before_2022_network_data_from_after_the_storm"] = {
        "storms_added": sorted(recs[recs.role != "main"].storm.unique()),
        "raw_by_group": km_by_group(allst, col, G["labels"], step10.SEED + 710),
        "model": _model(allst, [col], group_col=col, levels=G["labels"])}
    uns = prepared(step10.without_serious(tp))
    uns = uns[uns.role == "main"]
    sens["without_serious_flag_reports"] = {"raw_by_group": km_by_group(uns, col, G["labels"], step10.SEED + 720),
                                            "model": _model(uns, [col], group_col=col, levels=G["labels"])}
    fixed = {}
    for i, m in enumerate(["fixed_any_excl_near_universal", "fixed_any", "fixed_half"]):
        g = gdef["groups"][m]
        fixed[m] = {"groups": g, "raw_by_group": km_by_group(main, f"grp_{m}", g["labels"], step10.SEED + 730 + i),
                    "model": _model(main, [f"grp_{m}"], group_col=f"grp_{m}", levels=g["labels"])}
    fixed["fixed_half_excl_near_universal_count_as_number"] = _model(
        main, ["fixed_half_excl_near_universal"], numeric_col="fixed_half_excl_near_universal")
    sens["fixed_broadband_secondary"] = {"note": "sensitivity displays only, never a headline; " + NEAR_UNIVERSAL_LABEL
                                                 + " excluded where marked", **fixed}
    from datetime import date
    gaps = {}
    for st in sorted(main.storm.unique()):
        d0 = pd.Timestamp(panel[panel.storm == st].landfall_utc.iloc[0]).tz_convert("America/New_York").date()
        gaps[st] = (d0 - date.fromisoformat(gdef["storm_releases"][st]["release"])).days
    sens["release_within_12_months"] = {
        "months_from_release_to_day0": {k: round(v / 30.44, 1) for k, v in gaps.items()},
        "identical_to_main": all(v <= 365 for v in gaps.values()),
        "note": "every main storm's release is within 12 months before its day 0, so the planned 'release within 12 months' display would equal the main analysis"}
    out["sensitivity"] = sens
    out["wording"] = REDUNDANCY_WORDING
    first_year = min(int(v["release"][:4]) for v in gdef["storm_releases"].values() if v["role"] == "main")
    top = G["labels"][-1]
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    top_n = int(top.split()[0])
    out["page_text"] = {
        "finding": (f"In storms from {first_year} on, counties served by more mobile providers did not show a consistent "
                    "difference in how long cell outages took to fall below 5% of sites. One grouping suggests a faster "
                    f"fall for counties with {words.get(top_n, top_n)} or more providers, but that association does not "
                    "hold when the count is used directly or when flagged reports are left out, and some other coverage "
                    "measures point the other way."),
        "limits": ("Provider counts describe reported coverage (mobile providers covering at least half the county's "
                   "area, in the FCC's Broadband Data Collection release before the storm), not which networks were "
                   "out. No provider is named."),
        "near_universal": NEAR_UNIVERSAL_LABEL,
    }
    return out


def main():
    panel = pd.read_parquet(PROCESSED / "panel.parquet")
    storms = pd.read_parquet(PROCESSED / "storms.parquet")
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    items = sys.argv[1:] or ["v2_1", "v2_2", "v2_3"]
    if "v2_1" in items:
        step10.write_chapter(RESULTS, "v2_1_public_record_misses", v2_1(panel, storms, results))
    if "v2_2" in items:
        step10.write_chapter(RESULTS, "v2_2_backup_power", v2_2(panel, storms))
    if "v2_3" in items:
        step10.write_chapter(RESULTS, "v2_3_power_cell_timing", v2_3(panel))
    if "v2_5_groups" in items:  # counts only; must run (and be logged) before "v2_5"
        step10.write_chapter(RESULTS, "v2_5_groups", v2_5_groups(panel))
    if "v2_5" in items:
        step10.write_chapter(RESULTS, "v2_5_network_redundancy",
                             v2_5(panel, json.loads(RESULTS.read_text(encoding="utf-8"))))
    print("written:", ", ".join(items))


if __name__ == "__main__":
    main()
