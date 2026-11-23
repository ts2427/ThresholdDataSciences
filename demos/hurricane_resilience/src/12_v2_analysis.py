"""Step 12: version 2 analyses (exploratory; docs/analysis_plan_addendum_v2.md), written to results.json as v2_* keys.

Version 1's code (step 10) and its chapter_* keys are not changed; tests/test_v1_results_unchanged.py checks that.

    python src/12_v2_analysis.py [items]      items: v2_1, v2_2, v2_3 (default: all built so far)

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
    laura = [r for r in few if r["storm"] == "Laura"]
    page = {
        "collected_sentence": (f"The FCC printed sites operating on backup power for {len(per)} of "
                               f"{len(per) + len(not_collected)} storms: in every report for "
                               f"{step10._and_list([r['storm'] for r in full])}, and in one report each for "
                               f"{step10._and_list([r['storm'] for r in few])}. It did not print them for "
                               f"{step10._and_list(not_collected)}."),
        "footnotes": [f"{r['storm']}: its one report with backup power prints it for "
                      f"{r['by_report'][[x['collected'] for x in r['by_report']].index(True)]['n_counties_printed']} of "
                      f"{r['by_report'][[x['collected'] for x in r['by_report']].index(True)]['n_counties_listed']} "
                      f"counties, so it is left out of comparisons." for r in laura],
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
        "finding": (f"Where the order could be determined ({determined} of {h['n']} counties, as defined), the share of "
                    f"{more} more often fell below 5% before, or in the same report as, the share of {other}: "
                    f"cell first in {o['cell_first']['count']}, the same report in {o['same_report']['count']}, and "
                    f"power first in {o['power_first']['count']}. "
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
        "by_storm": by_storm,
        "sensitivity": sens,
        "wording": TIMING_WORDING,
    }


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
    print("written:", ", ".join(items))


if __name__ == "__main__":
    main()
