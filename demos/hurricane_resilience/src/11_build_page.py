"""Step 11: build the web page from output/results.json, in the threshold-site demos convention.

Writes (into the threshold-site repo that contains this project):
* content/analysis/when-the-network-goes-dark.md (published: draft: false, 2026-11-23), laid out like the
  retention playbook: numbered chapters, each claim -> exhibit -> what it means; then methods, data and licenses;
  sources. The demonstration tag comes from the site's analysis template.
* content/data/hurricane-*.csv: one CSV per figure. Each is re-read and checked value by value against
  results.json; a figure is marked verified: true only if every value matches (the site build refuses an
  unverified figure on a published page).
* static/data/hurricane-dirs-county-day.csv: the cleaned county-report panel (CC BY 4.0), DIRS fields only.
* demos/hurricane_resilience/: the public snapshot (code, tests, manifests, docs, results), via
  copy_snapshot(), which calls copy_validation_summary() to copy output/validation_summary.csv into the snapshot
  (it refuses to run if any report failed validation).
Every number on the page is generated here from results.json and the project's CSVs; none is typed in.
"""
import json
import re
import shutil
from pathlib import Path

import pandas as pd

from config import DOWNLOADS_LOG, OPENFEMA_DISCLAIMER, OUTPUT, PROCESSED, RAW, ROOT

SITE = ROOT.parent
SNAPSHOT = SITE / "demos" / "hurricane_resilience"
SLUG = "when-the-network-goes-dark"
PAGE = SITE / "content" / "analysis" / f"{SLUG}.md"
FIG_DIR = SITE / "content" / "data"
PANEL_PUBLIC = SITE / "static" / "data" / "hurricane-dirs-county-day.csv"
LOOKUP_JSON = SITE / "static" / "data" / "hurricane-county-lookup.json"  # v2-4: generated from the published panel
MAP_TOPO = SITE / "static" / "data" / "hurricane-counties.topo.json"     # v2-6: county shapes (TopoJSON)
MAP_JSON = SITE / "static" / "data" / "hurricane-map.json"               # v2-6: generated from the published panel
STUDY_FIPS = ("48", "22", "28", "01", "12", "13", "45", "37", "47", "51")
MAP_TOLERANCE_DEG = 0.02
TOPO_QUANT = 10_000
MAP_SCALE = "steps"  # Tim's choice, 2026-11-23 (option B), from the panel's overall distribution
MAP_SCALE_TEXT = {"cap50": "the same fixed scale for every storm, from 0% to 50% and above",
                  "steps": "fixed steps for every storm: 0%, under 5%, 5–15%, 15–30%, 30–50% and 50% or more"}
DATE = "2026-11-22"
UPDATED = "2026-11-23"
DRAFT = False  # published 2026-11-23 (Tim's decision); the site build's guards apply to a published page
WORK_YAML = SITE / "content" / "work.yaml"
WORK_URL = f"/analysis/{SLUG}/"
REPO_URL = "https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/hurricane_resilience"
TOLERANCE = 0.051  # figure values are rounded to one decimal
EAGLEI_DOIS = ["10.1038/s41597-024-03095-5", "10.6084/m9.figshare.24237376", "10.13139/ORNLNCCS/3012826"]
VIEWS_LINE = "Independent analysis using public data. Views are my own and not those of any employer."
SNAPSHOT_DIRS = ["src", "tests", "manifest"]
SNAPSHOT_DOCS = ["analysis_plan.md", "analysis_plan_addendum_v2.md", "decisions.md", "data_sources.md", "literature.md"]
SNAPSHOT_RESULTS = ["results.json", "validation_dirs.csv", "validation_summary.csv", "excluded_reports.csv",
                    "area_status_counts.csv"]


# ---------------------------------------------------------------- formatting --

def f1(x, d=1):
    return "–" if x is None else f"{x:,.{d}f}".replace("-", "−")


def n0(x):
    """Whole number, rounding halves up (1,474.5 -> 1,475)."""
    import math
    return "–" if x is None else f"{int(math.floor(x + 0.5)):,}"


PERIOD_LABELS = {"P0": "neither rule (DIRS activated before May 1, 2024)",
                 "P1": "MDRI in force, DIRS voluntary (May 1, 2024 to February 19, 2025)",
                 "P2": "MDRI and mandatory DIRS (February 20, 2025 to June 29, 2026)",
                 "P3": "MDRI and mandatory DIRS as modified by FCC 26-34 (from June 30, 2026)"}
READABLE = [("t90_best", "time to 90% (leaving counties restored)"), ("t90", "time to 90% (leaving counties still out)"),
            ("t50", "time to 50%"), ("days_peak_to_last", "days from peak to last report"),
            ("still_out_share_at_last", "share still out at the last report"), ("max_wind_kt", "strongest wind"),
            ("peak_pct_out", "peak % out")]


def readable(text: str) -> str:
    for a, b in READABLE:
        text = text.replace(a, b)
    return text


def fema_access() -> str:
    d = pd.read_csv(DOWNLOADS_LOG, dtype=str, keep_default_na=False)
    w = pd.to_datetime(d[d.kind == "openfema"].when, utc=True)
    e = w.min().tz_convert("America/New_York")
    hour = e.hour % 12 or 12
    return (f"{w.min():%Y-%m-%d %H:%M:%S}–{w.max():%H:%M:%S} UTC ({e:%B} {e.day}, {e.year}, {hour}:{e.minute:02d} "
            f"{'a.m.' if e.hour < 12 else 'p.m.'} Eastern)")


def boundary_download() -> dict:
    d = pd.read_csv(DOWNLOADS_LOG, dtype=str, keep_default_na=False)
    row = d[d.kind == "census_cartographic_boundary"].iloc[0]
    return {"url": row.url, "when": row.when[:10]}


def ci(rec, d=1, unit=""):
    lo, hi = rec.get("ci_low"), rec.get("ci_high")
    u = f" {unit}" if unit else ""
    if hi is None and lo is not None:  # a time whose upper limit censoring leaves open
        return f"from {f1(lo, d)}{u}, with no upper limit identified because of censoring"
    return f"{f1(lo, d)} to {f1(hi, d)}{u}"


def fdays(x):
    """Days at their stated precision, one decimal, dropping a trailing .0 (7.000000000000001 -> 7, 2.5 -> 2.5,
    1.958 -> 2)."""
    if x is None:
        return "–"
    v = round(float(x), 1)
    return f1(v, 0) if v == round(v) else f1(v, 1)


STATUS_LABELS = {"pass": "passed", "known_fcc_inconsistency": "known FCC inconsistency", "flagged": "flagged",
                 "excluded": "excluded", "fail": "failed"}


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def doi(x):
    return f"[doi:{x}](https://doi.org/{x})"


def days(t, cens, at):
    return f"not reached by day {f1(at, 0)}" if cens else f1(t, 0)


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ---------------------------------------------------------------- validation --

def copy_validation_summary(snapshot: Path = SNAPSHOT) -> Path:
    """Copy the validation summary into the public snapshot."""
    summary = OUTPUT / "validation_summary.csv"
    if not summary.exists():
        raise FileNotFoundError(f"{summary.name} is missing: run step 4 first")
    if (pd.read_csv(OUTPUT / "validation_dirs.csv").status == "fail").any():
        raise ValueError("a report failed validation: not publishing")
    snapshot.mkdir(parents=True, exist_ok=True)
    dest = snapshot / summary.name
    shutil.copyfile(summary, dest)
    return dest


# ---------------------------------------------------------------- figures --

def figure_rows(r: dict) -> dict:
    """Each figure's rows, taken straight from results.json."""
    c2, c3, c4, c5, c6, c7, c8 = (r[f"chapter_{i}"] for i in (2, 3, 4, 5, 6, 7, 8))
    isaias = [{"county": f"{x['county']}, {abbr(x['state'])}", "peak_pct_out": round(x["peak_pct_out"], 1)}
              for x in c2["county_peaks"][:15]]
    peaks = [{"storm": s["storm"], "peak_pct_out": round(s["peak_pct_out"]["value"], 1),
              "ci95_low": round(s["peak_pct_out"]["ci_low"], 1), "ci95_high": round(s["peak_pct_out"]["ci_high"], 1)}
             for s in c3["storms"]]
    restored = [{"storm": s["storm"], "restored_pct_counties_stay_out": round(100 * s["curve"][-1]["restored_share"], 1),
                 "low": round(100 * s["curve"][-1]["restored_share"], 1),
                 "restored_pct_counties_restored": round(100 * s["curve"][-1]["restored_share_best"], 1)}
                for s in c4["storms"] if s["n_reports_after_peak"] > 0]
    pooled = c5["headlines"]["pooled_all_storms"]
    causes = [{"cause": k.capitalize() if k != "overattributed" else "Over-attributed (beside, not netted)",
               "pct_of_sites_out": round(pooled[k]["value"], 1)}
              for k in ("power", "transport", "damage", "unattributed", "overattributed")]
    lags = [{"hours_before_report": lag.split("_")[1], "median_rank_correlation": round(v["pct_sites_out"]["value"], 2)}
            for lag, v in c6["headlines"]["median_by_lag"].items()]
    zone = [{"wind_zone": k, "peak_pct_out": round(v["value"], 1)} for k, v in c7["by_wind_zone"].items()]
    dist = [{"distance_to_track": k, "peak_pct_out": round(v["value"], 1)} for k, v in c7["by_distance_band"].items()]
    wait = [{"svi_quartile": q, "median_days": round(v["median_days_since_landfall"]["value"], 1),
             "ci95_low": round(v["median_days_since_landfall"]["ci_low"], 1),
             "ci95_high": round(v["median_days_since_landfall"]["ci_high"], 1)}
            for q, v in c8["headlines"]["raw_by_quartile"].items()]
    period = {s["storm"]: s["rule_period"] for s in c3["storms"]}
    curves = []
    for s in c4["storms"]:
        if s["n_reports_after_peak"] == 0:
            continue
        for pt in s["curve"]:
            curves.append({"storm": s["storm"], "period": period[s["storm"]], "day": round(pt["days_since_peak"], 2),
                           "series": "stay_out", "pct": round(100 * pt["restored_share"], 1),
                           "lo": round(100 * pt["ci_low"], 1), "hi": round(100 * pt["ci_high"], 1)})
        for pt in s["curve"]:
            curves.append({"storm": s["storm"], "period": period[s["storm"]], "day": round(pt["days_since_peak"], 2),
                           "series": "restored", "pct": round(100 * pt["restored_share_best"], 1), "lo": "", "hi": ""})
    flags = time_flags(r)
    heat = []
    for s in c3["storms"]:
        seen = set()
        for t in r["chapter_1"]["coverage_by_report"][s["storm"]]:
            day = calendar_day(s, t["report_date"])
            if day in seen:
                raise ValueError(f"{s['storm']}: two reports fall on day {day}")
            seen.add(day)
            heat.append({"storm": s["storm"], "period": period[s["storm"]], "day": day, "pct_out": round(t["pct_out"], 1),
                         "flag": flags.get(t["doc_id"], "")})
        for x in excluded_days(r)[s["storm"]]:  # an FCC report exists but is excluded: drawn crossed, value blank
            if x["day"] in seen:
                raise ValueError(f"{s['storm']}: an excluded report falls on a used report's day {x['day']}")
            seen.add(x["day"])
            heat.append({"storm": s["storm"], "period": period[s["storm"]], "day": x["day"], "pct_out": "", "flag": ""})
    overlay = []
    for s in c3["storms"]:
        for t in c6["overlay"].get(s["storm"], []):
            if t["doc_id"] in flags:  # time-flagged: kept off the storm's timeline
                continue
            overlay.append({"storm": s["storm"], "period": period[s["storm"]], "day": round(t["days_since_landfall"], 2),
                            "series": "sites", "pct": round(t["pct_sites_out"], 1), "counties": t["n_counties"]})
            overlay.append({"storm": s["storm"], "period": period[s["storm"]], "day": round(t["days_since_landfall"], 2),
                            "series": "power", "pct": round(t["pct_customers_out"], 1), "counties": t["n_counties"]})
    calib = [{"decile": d["bin"], "mean_predicted_pct": round(d["mean_predicted_pct"], 1),
              "observed_pct": round(d["observed_pct"], 1), "storm_counties": d["n"]}
             for d in c7["headlines"]["calibration_held_out"]["deciles"]]
    return {"hurricane-isaias-counties.csv": isaias, "hurricane-peaks.csv": peaks, "hurricane-restored.csv": restored,
            "hurricane-recovery-curves.csv": curves, "hurricane-coverage-heatmap.csv": heat,
            "hurricane-power-overlay.csv": overlay, "hurricane-calibration.csv": calib,
            "hurricane-isaias-map.csv": isaias_map_rows(c2),
            "hurricane-causes.csv": causes, "hurricane-power-lags.csv": lags, "hurricane-wind-zone.csv": zone,
            "hurricane-distance.csv": dist, "hurricane-svi-wait.csv": wait}


def outlined_cell_text(r: dict, short: bool = False) -> str:
    """Caption / description text for time-flagged cells (the coverage chart's one exception to the timeline rule)."""
    xs = r["chapter_1"].get("time_flagged_reports", [])
    if not xs:
        return ""
    if short:
        return " ".join(f"the outlined cell, {x['storm']} day {calendar_day_of(r, x)}, is the combined Marco–Laura "
                        f"report, before Laura's winds arrived; " for x in xs)
    return " ".join(f"Outlined cell: {x['storm']}'s report of {x['report_date']}, the combined Marco–Laura report, "
                    f"before Laura's winds arrived (shown here as the one exception to keeping it off Laura's timeline; "
                    f"see Laura's note in chapter 3). " for x in xs)


def calendar_day_of(r: dict, x: dict) -> int:
    st = next(s for s in r["chapter_3"]["storms"] if s["storm"] == x["storm"])
    return calendar_day(st, x["report_date"])


def time_flags(r: dict) -> dict:
    """doc_id -> time flag, for reports kept out of anything that places them on the storm's timeline."""
    return {x["doc_id"]: x["flag"] for x in r["chapter_1"].get("time_flagged_reports", [])}


def calendar_day(storm: dict, report_date: str) -> int:
    """A report's calendar day since day 0: report date minus day 0's date in Eastern time."""
    origin = pd.Timestamp(storm["landfall_utc"]).tz_convert("America/New_York").date()
    return (pd.Timestamp(report_date).date() - origin).days


def excluded_days(r: dict) -> dict:
    """Per storm, the calendar days of its excluded FCC reports."""
    out = {s["storm"]: [] for s in r["chapter_3"]["storms"]}
    by_name = {s["storm"]: s for s in r["chapter_3"]["storms"]}
    for e in r["chapter_1"]["excluded_reports"]:
        if e["storm_name"] in by_name:
            out[e["storm_name"]].append({"doc_id": e["doc_id"], "report_date": e["report_date"],
                                         "day": calendar_day(by_name[e["storm_name"]], e["report_date"])})
    return out


def excluded_days_text(r: dict) -> str:
    parts = []
    for storm, xs in excluded_days(r).items():
        if xs:
            d = sorted(x["day"] for x in xs)
            span = f"day {d[0]}" if len(d) == 1 else (f"days {d[0]}–{d[-1]}" if d == list(range(d[0], d[-1] + 1))
                                                      else "days " + _and([str(v) for v in d]))
            parts.append(f"{storm} {span}")
    return _and(parts)


def _and(items: list) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def overlay_notes(r: dict) -> dict:
    """Which storms' matched county set narrows by more than half, and which reports have no power match."""
    narrow, missing = [], []
    flags = time_flags(r)
    for s in r["chapter_3"]["storms"]:
        o = [t for t in r["chapter_6"]["overlay"].get(s["storm"], []) if t["doc_id"] not in flags]
        if not o:
            continue
        first, last = o[0]["n_counties"], o[-1]["n_counties"]
        if last < first / 2:
            narrow.append(f"{s['storm']} {first} to {last}")
        gap = len([t for t in r["chapter_1"]["coverage_by_report"][s["storm"]] if t["doc_id"] not in flags]) - len(o)
        if gap:
            missing.append(f"{'one' if gap == 1 else gap} of {s['storm']}'s reports")
    return {"narrow": narrow, "missing": missing}


BOUNDARIES = RAW / "census" / "cb_2022_us_county_500k.zip"  # Census cartographic boundary, 2022
MAP_STATES = ("01", "12", "13", "28")  # AL, FL, GA, MS
MAP_MARGIN_DEG = 0.4
MAP_WIDTH = 720
MAP_SIMPLIFY_DEG = 0.004


def isaias_map_rows(c2: dict) -> list:
    """Counties around Isaias's reporting area as projected SVG paths, with each reporting county's peak share from
    results.json (blank where it was not in a report), and the best-track points from results.json."""
    import geopandas as gpd
    import numpy as np
    g = gpd.read_file(f"zip://{BOUNDARIES.as_posix()}")
    g = g[g.STATEFP.isin(MAP_STATES)]
    peaks = {x["fips"]: x for x in c2["county_peaks"]}
    area = g[g.GEOID.isin(peaks)]
    minx, miny, maxx, maxy = area.total_bounds
    minx, miny, maxx, maxy = minx - MAP_MARGIN_DEG, miny - MAP_MARGIN_DEG, maxx + MAP_MARGIN_DEG, maxy + MAP_MARGIN_DEG
    g = g.cx[minx:maxx, miny:maxy]
    k = np.cos(np.radians((miny + maxy) / 2))
    scale = MAP_WIDTH / ((maxx - minx) * k)

    def xy(lon, lat):
        return (lon - minx) * k * scale, (maxy - lat) * scale

    def ring(coords):
        pts = [xy(lon, lat) for lon, lat in coords]
        return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"
    rows = []
    for r in g.sort_values("GEOID").itertuples():
        geom = r.geometry.simplify(MAP_SIMPLIFY_DEG, preserve_topology=True)
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        d = " ".join(ring(pl.exterior.coords) + "".join(" " + ring(h.coords) for h in pl.interiors) for pl in polys)
        hit = peaks.get(r.GEOID)
        rows.append({"kind": "area", "fips": r.GEOID, "county": f"{r.NAME}, {r.STUSPS}",
                     "peak_pct_out": round(hit["peak_pct_out"], 1) if hit else "", "d": d,
                     "lat": "", "lon": "", "x": "", "y": ""})
    for t in c2["track"]:  # every best-track point; the chart clips the line to the map frame
        x, y = xy(t["lon"], t["lat"])
        rows.append({"kind": "track", "fips": "", "county": "", "peak_pct_out": "", "d": "",
                     "lat": t["lat"], "lon": t["lon"], "x": round(x, 1), "y": round(y, 1)})
    return rows


def map_height(rows: list) -> int:
    ys = [float(n) for r in rows if r["kind"] == "area" for n in re.findall(r"-?\d+\.\d", r["d"])[1::2]]
    return int(max(ys)) + 10


STATE_ABBR = {"Alabama": "AL", "Florida": "FL", "Georgia": "GA", "Louisiana": "LA", "Mississippi": "MS",
              "North Carolina": "NC", "South Carolina": "SC", "Tennessee": "TN", "Texas": "TX", "Virginia": "VA"}


def abbr(state):
    return STATE_ABBR.get(state, state)


def write_figure_csvs(rows: dict, folder: Path = FIG_DIR) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in rows.items():
        pd.DataFrame(data).to_csv(folder / name, index=False, lineterminator="\n")


def verify_figure_csvs(rows: dict, folder: Path = FIG_DIR) -> dict:
    """Re-read each written CSV and compare every value with the rows taken from results.json."""
    out = {}
    for name, expected in rows.items():
        got = pd.read_csv(folder / name, dtype=str, keep_default_na=False).to_dict("records")
        ok = len(got) == len(expected)
        for g, e in zip(got, expected):
            for k, v in e.items():
                if k == "d":
                    ok &= g[k] == v  # projected shape from the Census boundary file, not a value
                elif isinstance(v, (int, float)):
                    ok &= abs(float(g[k]) - float(v)) <= TOLERANCE
                else:
                    ok &= g[k] == str(v)
        out[name] = bool(ok)
    return out


def figures_front_matter(verified: dict, r: dict) -> list:
    rows_all = figure_rows(r)
    rows_map = rows_all["hurricane-isaias-map.csv"]
    overlay_max = 10 * -(-max(x["pct"] for x in rows_all["hurricane-power-overlay.csv"]) // 10)  # next 10 above the data
    n_isaias = len(figure_rows(r)["hurricane-isaias-counties.csv"])
    n_causes = r["chapter_5"]["headlines"]["pooled_all_storms"]["power"]["n"]
    n_power = r["chapter_6"]["headlines"]["comovement_at_as_of_time"]["n"]
    left_out = r["chapter_4"]["headlines"]["storms_left_out_of_time_summaries"]
    not_shown = " ".join(f"{x['note']} Not shown." for x in left_out)
    neg = sorted({x["storm"] for x in rows_all["hurricane-recovery-curves.csv"] if x["lo"] != "" and x["lo"] < 0})
    neg_note = (f" Where the band's lower end falls below 0% ({_and(neg)}: resampled counties with more sites out than "
                f"at the peak), it is drawn from 0; the data table gives the values." if neg else "")
    ov = overlay_notes(r)
    ov_note = (f" The matched counties narrow as the FCC's reporting area shrinks ({'; '.join(ov['narrow'])} counties, "
               f"first to last report), so late values describe only the counties still reported." if ov["narrow"] else "")
    ov_missing = (f" Reports with no power match are left out: {_and(ov['missing'])} (its Sep 1, 2020 report, which "
                  f"prints no as-of time)." if ov["missing"] else "")
    bd = boundary_download()
    def fig(fid, ftype, data, x, y, title, caption, source, **extra):
        return {"id": fid, "type": ftype, "data": data, "x": x, "y": y, "title": title, "caption": caption,
                "source": source, "source_url": "", "data_public": True, "verified": verified[data], **extra}
    dirs = "FCC DIRS Communications Status Reports."
    return [
        fig("fig-isaias", "bar", "hurricane-isaias-counties.csv", "county", "peak_pct_out",
            f"Isaias: the {n_isaias} counties with the highest peak share of sites out",
            f"Each county's highest share of cell sites out across Isaias's reports, percent; the {n_isaias} highest.", dirs),
        fig("fig-peaks", "interval", "hurricane-peaks.csv", "storm", "peak_pct_out",
            "Peak share of cell sites out, by storm",
            "Share of sites served that were out in each storm's report with the most sites out, percent, with 95% "
            "county-bootstrap intervals. Storms in date order.", dirs, lo="ci95_low", hi="ci95_high",
            vertical_labels=True),
        fig("fig-restored", "interval", "hurricane-restored.csv", "storm", "restored_pct_counties_stay_out",
            "How much was back by each storm's last report, under both bounds",
            "Share of the sites out at the peak that were back by the storm's last report, percent. The dot and lower "
            "end: counties that leave the reports keep their last reported outages. Upper end: they are counted as "
            f"restored. {not_shown}", dirs, lo="low",
            hi="restored_pct_counties_restored", vertical_labels=True),
        fig("fig-causes", "bar", "hurricane-causes.csv", "cause", "pct_of_sites_out",
            "Loss of commercial power is the largest cause the FCC records",
            f"Shares of cell sites out, pooled over {n_causes} storms with cause columns, percent. Over-attribution is shown "
            "beside the others and never netted against unattributed sites.", dirs),
        fig("fig-power", "column", "hurricane-power-lags.csv", "hours_before_report", "median_rank_correlation",
            "Cell outages line up with power outages up to about 12 hours earlier",
            f"Median across {n_power} storms of the within-storm rank correlation between % of customers (meters) without "
            "power and % of cell sites out, by how many hours before the report the power value is taken.",
            "FCC DIRS; ORNL/DOE EAGLE-I."),
        fig("fig-zone", "bar", "hurricane-wind-zone.csv", "wind_zone", "peak_pct_out",
            "Peak share of cell sites out, by wind zone",
            "Sum of county peak sites out over sum of sites served, percent, by the strongest wind radius the county "
            "fell inside.", "FCC DIRS; NHC HURDAT2 and GIS best track."),
        fig("fig-distance", "bar", "hurricane-distance.csv", "distance_to_track", "peak_pct_out",
            "Peak share of cell sites out, by distance to the track",
            "Sum of county peak sites out over sum of sites served, percent, by distance from the county's internal "
            "point to the storm track.", "FCC DIRS; NHC HURDAT2 and GIS best track; Census Gazetteer."),
        fig("fig-coverage", "heatmap", "hurricane-coverage-heatmap.csv", "day", "pct_out",
            "Every storm's reports, day by day",
            "Each row is a storm, in date order; each cell is one FCC report, by calendar days since the storm's 34-knot "
            "winds first reached a study-state county (day 0; see the methods), shaded by the share of sites served that were out. Blank cells: no FCC report that day. "
            f"Crossed cells: an FCC report that exists but is excluded ({excluded_days_text(r)}; listed in the methods). "
            f"{outlined_cell_text(r)}"
            "Rule periods are marked at the right. Late dark cells can reflect a reporting area narrowed to a few "
            "hard-hit counties (Laura).",
            dirs, row="storm", col="day", value="pct_out", group="period", legend_label="% of sites out",
            flag="flag", flag_label="combined Marco–Laura report, before Laura's winds arrived",
            x_label="Days since 34-kt winds arrived", blank_label="no report", excluded_label="report excluded",
            description="A grid of storms by days since their 34-knot winds arrived. Darker cells mean a larger share of cell sites out in "
                        f"that day's report; crossed cells are excluded reports; {outlined_cell_text(r, short=True)}"
                        "rows end where the FCC's reports for that storm end."),
        fig("fig-isaias-map", "map", "hurricane-isaias-map.csv", "county", "peak_pct_out",
            "Isaias: peak share of cell sites out by county, with the storm's track",
            "Each county's highest share of sites out across Isaias's reports, percent. White counties were not in its "
            "reports; the lightest grey ones were, with no sites out. The orange line is the NHC best track.",
            "FCC DIRS; NHC GIS best track; U.S. Census Bureau cartographic boundary file (2022, 1:500,000).",
            value="peak_pct_out", path="d", tx="x", ty="y", width=MAP_WIDTH, height=map_height(rows_map),
            legend_label="peak % of sites out", track_label="Isaias track", no_data_label="not in the reports",
            table_where=["kind", "area"], table_columns=["county", "fips", "peak_pct_out"],
            description="A map of the Florida Panhandle, southern Alabama and nearby counties. Counties are shaded by "
                        "their peak share of cell sites out; the darkest lie near the track, on the coast and inland."),
        fig("fig-curves", "multiples", "hurricane-recovery-curves.csv", "day", "pct",
            "Recovery curves for every storm, under both bounds",
            "Share of the sites out at the peak that were back, percent, by days since the peak. Solid: counties that "
            "leave the reports keep their last reported outages, with the 95% county-bootstrap band. Dashed: they are "
            f"counted as restored. Panels in date order; rule periods marked in orange. {not_shown}{neg_note}", dirs,
            panel="storm", series="series", series_order=["stay_out", "restored"],
            series_labels={"stay_out": "leaving counties still out", "restored": "leaving counties restored"},
            lo="lo", hi="hi", group="period", y_max=100, x_label="Days since the peak",
            description="Small panels, one per storm, each with two rising lines from 0% at the peak; where the dashed "
                        "line sits above the solid one, counties left the reports while still out."),
        fig("fig-power-overlay", "multiples", "hurricane-power-overlay.csv", "day", "pct",
            "Power outages and cell outages, storm by storm",
            "Share of electricity customers (meters) without power and share of cell sites out, percent, in each "
            "report over the counties matched to EAGLE-I in that report, by days since the storm's 34-knot winds arrived. "
            "EAGLE-I ends in 2025, "
            f"so Isaias is not shown.{ov_note}{ov_missing}",
            "FCC DIRS; ORNL/DOE EAGLE-I.", panel="storm", series="series", series_order=["sites", "power"],
            series_labels={"sites": "% of cell sites out", "power": "% of customers without power"},
            group="period", y_max=overlay_max, x_label="Days since 34-kt winds arrived",
            table_columns=["storm", "period", "day", "series", "pct", "counties"],
            description="Small panels, one per storm, each with a line for cell sites out and one for customers without "
                        "power. The two lines often move together, but not in every storm: in some the power share rises "
                        "late as the reporting area narrows to a few hard-hit counties, and in others sites stay out "
                        "after power is back."),
        fig("fig-calibration", "calibration", "hurricane-calibration.csv", "mean_predicted_pct", "observed_pct",
            "Exposure model: predicted against observed, on held-out storms",
            "Each dot is a tenth of the storm-counties, ordered by predicted peak share: mean predicted against observed "
            "peak share of sites out, percent, with each storm held out of the fit. Dots on the dashed line would be "
            "perfectly calibrated.", "FCC DIRS; NHC; model in the methods.",
            x_label="Mean predicted peak % out", y_label="Observed peak % out",
            description="Ten dots near the diagonal at both ends, with the middle deciles scattered on either side."),
        fig("fig-svi", "interval", "hurricane-svi-wait.csv", "svi_quartile", "median_days",
            "Days until a county stayed below 5% of sites out, by SVI quartile",
            "Kaplan-Meier median days since the storm's 34-knot winds arrived, with 95% county-bootstrap intervals. Quartiles of the at-risk "
            "counties' SVI 2022 national percentiles.", "FCC DIRS; CDC/ATSDR SVI 2022.", lo="ci95_low", hi="ci95_high"),
    ]


# ---------------------------------------------------------------- page text --

def deviations(decisions: str) -> list:
    rows = [ln for ln in decisions.splitlines() if ln.startswith("| 2026") and "DEVIATION" in ln]
    out = []
    for ln in rows:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        out.append((cells[0], cells[1], cells[2] if len(cells) > 2 else ""))
    return out


def corrections(decisions: str) -> list:
    rows = [ln for ln in decisions.splitlines() if ln.startswith("| 2026") and "CORRECTION" in ln]
    return [tuple([c.strip() for c in ln.strip("|").split("|")] + [""])[:3] for ln in rows]


SUPERSEDED = {  # deviations replaced by a later decision: the page names them without the outdated text
    "DEVIATION (page exhibits)": "superseded the same day by the new exhibits (next list): the heatmap, map and "
                                 "small-multiple charts on this page replace the tables this deviation planned"}
EXHIBIT_DECISIONS = ("New exhibits", "The Isaias map draws")


def optimizer_note(c8: dict) -> str:
    w = c8["sensitivity"]["censored_worst_case"]
    if w.get("optimizer", "IRLS") == "IRLS":
        return ""
    return ("The worst-case sensitivity display is fitted by Newton's method because the default fitter (IRLS) did not "
            "converge; the model and its likelihood are the same. ")


SUPERSEDED_NOTES = [  # (condition on an entry, note appended on the page)
    (lambda d, w: w.startswith("CORRECTION (time origin; made after seeing results)"),
     "Superseded by the second time-origin correction below."),
    (lambda d, w: d < "2026-11-23" and "landfall" in w,
     "Superseded: day 0 is now the first time 34-knot winds reach a study-state county (2026-11-23 corrections).")]


def superseded_note(date: str, what: str) -> str:
    return next((f" *{n}*" for c, n in SUPERSEDED_NOTES if c(date, what)), "")


# The page says what changed and why, without naming who proposed or chose it; docs/decisions.md keeps that record.
NEUTRAL_SUBS = [
    (r"The ambiguous rule was proposed by Claude Code as option \(a\) and adopted, in generalized form, in Tim's "
     r"instruction: ", ""),
    (r";? ?the base rule was proposed by Claude Code as option \(a\) and adopted, in generalized form, in Tim's "
     r"instruction; its two refinements \(([^)]*)\) were chosen by Tim from options proposed by Claude Code"
     r"(, \d{4}-\d\d-\d\d)?", lambda m: "; the rule's two refinements: " + m.group(1).replace("; ", ", and ")),
    (r"Exhibits chosen by Tim from options proposed by Claude Code; the chart rules are Tim's instruction"
     r"(, \d{4}-\d\d-\d\d)?", ""),
    (r"\b[Cc]hosen by Tim from options proposed by Claude Code(, \d{4}-\d\d-\d\d)?", ""),
    (r"Assigned by Claude Code, not named by Tim:", "Also classified:"),
    (r"\b(Serious|Benign) \(Tim\):", r"\1:"),
    (r"Tim's decision after seeing", "Decided after seeing"),
    (r"Tim's stopping rule", "the stopping rule"),
    (r"\bTim's (instruction|decisions?|request|approval|confirmation|check)( \(Prompt 5\))?(,? \d{4}-\d\d-\d\d)?",
     ""),
]
ATTRIBUTION = re.compile(r"\bTim\b|\bTim's\b|Claude")


PAGE_REWORDS = {  # rows whose neutral page wording is written out (the substitutions would cut them mid-sentence)
    "CORRECTION (V2-1 page text; correction of an ambiguous instruction)": (
        "CORRECTION (V2-1 page text; made after seeing results): the headline covers every storm (21 storms and 1,883 "
        "sites still out; it had covered 19 storms and 1,679 sites, leaving out Nicholas and Nicole), and the median "
        "(9.0%) and the upper bound (16.9%) leave out only Nicole, whose share is 100% by construction (the chapter 4 "
        "rule), keeping Nicholas with its footnote: 20 storms", "correction of an ambiguous instruction")}


def neutral(text: str) -> str:
    """Remove who proposed or chose a decision; keep what changed and why."""
    for a, b in NEUTRAL_SUBS:
        text = re.sub(a, b, text)
    # inside parentheticals, ;-parts that only attribute (e.g. "the footnote wording is Tim's") go; the rest stay
    def keep_parts(m):
        kept = [p for p in re.split(r";\s*", m.group(1)) if p.strip() and not ATTRIBUTION.search(p)]
        return f" ({'; '.join(kept)})" if kept else ""
    text = re.sub(r"\s*\(([^()]*(?:\bTim\b|Tim's|Claude)[^()]*)\)", keep_parts, text)
    parts = [p.strip() for p in re.split(r";\s*", text)]
    parts = [p for p in parts if p and not ATTRIBUTION.search(p)]
    text = "; ".join(parts)
    text = re.sub(r"\(\s*[,;]?\s*\)", "", text)
    text = re.sub(r"\(\s*[,;]\s*", "(", text)
    text = re.sub(r"\s+:", ":", re.sub(r"\s{2,}", " ", text)).strip(" ;,")
    if text.startswith("(") and text.endswith(")") and text.count("(") == 1:  # a reason left wrapped in parentheses
        text = text[1:-1]
    return text[:1].upper() + text[1:] if text else text


def entry(date: str, what: str, why: str, note: str = "") -> str:
    hit = next((v for k, v in PAGE_REWORDS.items() if what.startswith(k)), None)
    what, why = hit if hit else (neutral(what), neutral(why))
    return f"- *{date}.* {what}" + (f" ({why})" if why else "") + note


PLAN_SUBS = [
    ("**Not seen (at first registration):**", "**Not seen (when the plan was first committed):**"),
    ("**Seen after registration, before chapter 3 was computed", "**Seen after the plan was committed, before chapter 3 was computed"),
    ("Claude Code, which drafted it, saw these while building and checking the parser, and showed some to the author:",
     "These were seen during data preparation and validation:"),
    ("while building steps 3-8, Claude Code saw every report's",
     "during data preparation and validation (steps 3-8), these were seen: every report's"),
    ("the validation summaries shown to the author (", "the validation summaries ("),
    ("the author has seen only what Claude Code reported during setup:",
     "the author has seen only what was reported during data preparation and validation:"),
]


def neutral_plan(text: str) -> str:
    for a, b in PLAN_SUBS:
        if a not in text:
            raise ValueError(f"plan wording changed; update PLAN_SUBS: {a[:60]}")
        text = text.replace(a, b)
    if "Claude" in text:
        raise ValueError("the plan excerpt still names the coding assistant")
    return text


def bdc_methods_line() -> str:
    """The FCC Broadband Data Collection files used in chapter 13, from the logged file list."""
    files = pd.read_csv(RAW / "bdc" / "listings" / "provider_summary_files.csv", dtype=str)
    rel = json.loads((RAW / "bdc" / "listings" / "storm_releases.json").read_text(encoding="utf-8"))
    used = sorted({v["release"] for v in rel.values()})
    files = files[files.release.isin(used)].sort_values("release")
    from datetime import datetime as _dt

    def when(code):
        d = _dt.strptime(code, "%d%b%Y")
        return f"{d:%B} {d.day}, {d.year}"
    revs = "; ".join(f"the {r.release} release revised {when(r.file_name.rsplit('_', 1)[-1])}" for r in files.itertuples())
    return ("Provider counts come from the FCC's Broadband Data Collection public data (National Broadband Map, "
            "\"Provider Summary by Geography Type\"), downloaded through the FCC's Public Data API with an account "
            "and token, at most one call every 6.5 seconds (the API allows 10 per minute). Each storm uses the "
            "latest release on or before its day 0. The files are the FCC's current revisions of those releases ("
            + revs + "), so the counts include the FCC's later corrections. Only counts are kept: no provider is named "
            "or identified.")


PLAN_COMMIT = {"hash": "9fc17a4", "date": "November 22, 2026"}  # test: tests/test_build_page.py checks it in git
PLAN_SENTENCE = ("The analysis plan was committed on November 22, 2026, in the project's private version-controlled repository ("
                 "commit 9fc17a4), before any recovery outcome was computed. The plan file as committed is published in the data repo"
                 "sitory with its SHA-256, so it can be checked against later changes.")
FINAL_REPORT_SENTENCE = ("The FCC's order FCC 26-34 (adopted May 20, 2026; in effect from its Federal Register publication on "
                         "June 30, 2026) ended the requirement for providers to file a DIRS final report within 24 hours "
                         "of deactivation.")
FCC_CAVEAT = ("The number of cell site outages in a specific area does not necessarily correspond to the availability of "
              "wireless service to consumers in that area.")
DISCLOSURE = ("The author works in the telecommunications industry. This analysis was done independently, on personal time, "
              "using only publicly available government data. It uses no employer data or confidential information, and "
              "the views are the author's alone. The author has no financial interest in any FCC proceeding.")
RELATED_WORK = [
    "Olukola, O., Addeh, O. D., Konan, E. A., & Rahimi, N. (2026). The towers were standing: A cause decomposition of "
    "cellular outages during Hurricane Helene. arXiv:2609.10944. A cause decomposition of Helene's cell-site outages from "
    "the same FCC reports; this page uses it as a check on chapter 5.",
    "U.S. Government Accountability Office (2017). Telecommunications: FCC should improve monitoring of industry efforts to "
    "strengthen wireless network resiliency (GAO-18-198).",
    "U.S. Government Accountability Office (2021). Telecommunications: FCC assisted in Hurricane Maria network restoration, "
    "but a clarified disaster response role and enhanced communication are needed (GAO-21-297).",
    "Federal Communications Commission, Public Safety and Homeland Security Bureau (2018). 2017 Atlantic Hurricane Season "
    "Impact on Communications: Report and Recommendations (DOC-353805A1).",
    "Peskin, A. H. (2025). Cellular network outage reporting and restoration during disasters (CRS Report R48776). "
    "Congressional Research Service.",
    "Gallagher, J. C., & Peskin, A. H. (2024). Restoration of cell phone services: Hurricane Helene (CRS In Focus "
    "IF12779). Congressional Research Service.",
]
AI_LINE = ("Code was written with the help of an AI coding assistant; every number on this page is generated by that "
           "code from public data and was checked independently against its sources.")


def exhibit_decisions(decisions: str) -> list:
    rows = [ln for ln in decisions.splitlines() if ln.startswith("| 2026")]
    cells = [[c.strip() for c in ln.strip("|").split("|")] for ln in rows]
    return [(c[0], c[1], c[2] if len(c) > 2 else "") for c in cells if c[1].startswith(EXHIBIT_DECISIONS)]


def origin_sentence(r: dict) -> str:
    """How day 0 is set, with any storm that uses the fallback, generated from chapter 3."""
    fb = [x["storm"] for x in r["chapter_3"]["storms"] if x["landfall_source"].startswith("fallback")]
    tail = (f"For {_and(fb)}, whose 34-knot radii reach no county, day 0 is the first landfall in the study states."
            if fb else "Every storm has 34-knot radii at that time, so none uses the fallback (its first landfall in "
                       "the study states).")
    return ("Days count from day 0: the first time the storm's 34-knot (tropical-storm-force) winds reach any study-state "
            "county in its reports, from the NHC best-track wind radii. " + tail)


def before_day0_sentence(r: dict) -> str:
    """Nothing to say when every report before day 0 carries a time flag (each is explained in its storm's note);
    otherwise name the unflagged ones."""
    flagged = {x["doc_id"] for x in r["chapter_1"].get("time_flagged_reports", [])}
    cov = r["chapter_1"]["coverage_by_report"]
    hits = [(k, [t for t in v if t["days_since_landfall"] < 0 and t["doc_id"] not in flagged]) for k, v in cov.items()]
    hits = [(k, v) for k, v in hits if v]
    if not hits:
        return ""
    parts = [f"{k}'s report of {_and([t['report_date'] for t in v])}" for k, v in hits]
    return f"Reports before day 0 have negative days: {_and(parts)}."


TIME_FLAG_TEXT = {"pre_onset_likely_marco": (
    "{storm}'s report of {date} is the FCC's combined report for Marco and Laura, keyed to Laura; it falls {days} days "
    "before Laura's 34-knot winds reached a study-state county, so its outages are likely Marco's. It stays in the "
    "published panel, flagged pre_onset_likely_marco. It is left out of anything that places it on Laura's timeline "
    "(peak timing, recovery, waiting times, rule periods, the power overlay chart), with one exception: the coverage "
    "heatmap shows it as a marked (outlined) cell. It is kept where only same-time comparisons are made (the power-cell "
    "correlations).")}
CORRELATION_FLAG_TEXT = {"pre_onset_likely_marco": (
    "Note. {storm}'s correlation includes its report of {date}, the combined Marco–Laura report: same-time co-movement "
    "of power and cell outages doesn't depend on which storm caused the outage.")}


def time_flag_notes(r: dict) -> dict:
    """Per storm, the note on its time-flagged reports (the page's one mention of each)."""
    out = {}
    for x in r["chapter_1"].get("time_flagged_reports", []):
        out.setdefault(x["storm"], []).append(TIME_FLAG_TEXT[x["flag"]].format(
            storm=x["storm"], date=x["report_date"], days=f1(-x["days_since_landfall"])))
    return {k: " ".join(v) for k, v in out.items()}


def earlier_origins_line(c8: dict) -> str:
    """One line on chapter 8 under the earlier day-0 rules (both corrected after results were seen)."""
    e = c8["sensitivity"].get("earlier_time_origins") or {}
    if not e:
        return ""

    def hrs(x):
        h = x["hazard_ratios"]
        return ", ".join(f"{f1(h[k]['value'], 2)} ({ci(h[k], 2)})" for k in ("svi_Q2", "svi_Q3", "svi_Q4 (most)"))
    names = {"original": "the original rule (earliest landfall nearest a county)",
             "landfall_or_closest_approach": "the first correction (first study-state landfall or closest approach)"}
    same = not any(x["headline_changes"] for x in e.values())

    def bound(headline):
        return re.search(r"more than (\d+)% slower", headline).group(1) + "%"
    now = bound(c8["page_text"]["headline"])
    short = {"original": "the original rule", "landfall_or_closest_approach": "the first correction"}
    then = _and([f"\"more than {bound(x['headline'])} slower\" under {short[k]}" for k, x in e.items()])
    head = (" The headline is the same under all three rules." if same else
            f" The headline's wording is the same under all three rules; only its bound moves: {then}, and "
            f"\"more than {now} slower\" now.")
    return ("Day 0 was redefined twice after results were seen (methods). The second- to fourth-quartile hazard ratios "
            "were " + "; ".join(f"{hrs(x)} under {names[k]}" for k, x in e.items()) + "." + head)


def seen_before_registration(plan: str) -> str:
    m = re.search(r"## Seen before registration\n(.*?)\n## ", plan, re.S)
    return m.group(1).strip()


RED_FLAG_LABELS = {
    "1_drop_one_storm_reverses_order": "Dropping any one storm reverses the order of the periods",
    "2_order_depends_on_threshold_or_censoring": "The order depends on 50% versus 90%, or on the treatment of censoring",
    "3_recovery_already_shortening_in_P0": "Recovery was already shortening across P0",
    "4_denominators_jump_or_move_over_10pct": "Sites-served counts jump at a rule date, or move more than 10% within a storm",
    "5_activations_end_differently_by_period": "Activations end sooner, or with more sites still out, in one period",
    "6_no_overlap_in_wind_or_peak": "Wind or peak outage has no overlap across periods"}


def opening_numbers(r: dict) -> dict:
    """Every number in the opening, from results.json."""
    h1, h4 = r["chapter_1"]["headlines"], r["chapter_4"]["headlines"]
    t90 = h4["n_storms_reaching_90pct_restored"]
    return {"n_reports": h1["n_reports_used"]["value"], "n_storms": h1["n_storms"]["value"],
            "first_year": h1["first_report"][:4], "last_year": h1["last_report"][:4],
            "median_t50": f1(h4["median_time_to_50pct_restored"]["value"], 0),
            "n90_low": t90["min"], "n90_high": t90["max"], "n_storms_recovery": t90["n"]}


def pct1(x) -> str:
    return f"{100 * x:.1f}%"


V2_LABEL = "Exploratory: added after version 1 of this page was published."


def v2_opening(r: dict) -> list:
    """The opening's version 2 findings (V2-7), every number from results.json."""
    if "v2_1_public_record_misses" not in r:
        return []
    a, b = r["v2_1_public_record_misses"], r["v2_2_backup_power"]
    t, n = r["v2_3_power_cell_timing"], r["v2_5_network_redundancy"]
    h = a["headlines"]
    left = set(b["page_text"]["left_out_of_comparisons"])
    top = max(({"storm": x["storm"], **x["most_sites_on_backup"]} for x in b["storms"] if x["storm"] not in left),
              key=lambda x: x["value"])
    o = t["headlines"]
    det = o["n"] - o["orders"]["undetermined"]["count"]
    return [
        "### What version 2 adds\n",
        f"{V2_LABEL} Chapters 10 to 13, the map and the county lookup are new.\n",
        f"- {a['page_text']['headline']} The median share of a storm's peak still out at its last report is "
        f"{pct1(h['median_share_of_peak_still_out']['value'])} ({h['n_storms_in_median']} storms).",
        f"- The FCC printed sites operating on backup power for {len(b['headlines']['storms_collected'])} of "
        f"{len(b['headlines']['storms_collected']) + len(b['headlines']['storms_not_collected'])} storms; the most in one "
        f"report was {n0(top['value'])} sites, in {top['storm']}.",
        f"- Where the order could be determined ({det} of {o['n']} counties), cell outages fell below 5% of sites first "
        f"in {o['orders']['cell_first']['count']} counties and power outages fell below 5% of customers first in "
        f"{o['orders']['power_first']['count']}; in {o['orders']['same_report']['count']} both fell below 5% in the same "
        f"report. The two are measured on different scales (cell sites served, electricity meters), so this is not the "
        f"order in which people got service back.",
        f"- {n['page_text']['finding'].split('. ')[0]}.\n",
    ]


def opening_section(r: dict) -> list:
    """'Why this page exists' (Tim's text, 2026-11-23), with every number generated."""
    n = opening_numbers(r)
    return [
        "## Why this page exists\n",
        "When a hurricane reaches the Gulf Coast, a working phone is often what people need most, and one of the "
        "first things they lose.\n{: .page-lede}\n",
        "During major storms the FCC tracks cell-site outages and publishes a daily report. But it publishes them one "
        "PDF at a time, storm by storm, in formats that change from year to year, so nobody can easily see the whole "
        "picture.\n",
        f"I put them side by side: {n['n_reports']} FCC reports from {n['n_storms']} hurricanes, "
        f"{n['first_year']}–{n['last_year']}, checked line by line against the originals and linked to power-outage, "
        "storm-track and social-vulnerability data. The page asks four questions: How much of the network goes dark? "
        "How fast does it come back? What takes it down? Who waits longest?\n",
        "### What I found\n",
        f"- Half of the sites that go dark are typically back within about {n['median_t50']} days.",
        "- Lost power and lost network connections, not damage to the sites themselves, account for most outages, and "
        "cell outages tend to rise and fall with power outages.",
        "- Counties with higher social vulnerability did not take measurably longer for cell outages to fall below 5% of "
        "sites.",
        f"- The FCC's reporting often ended before recovery could be confirmed: only {n['n90_low']} to {n['n90_high']} "
        f"of {n['n_storms_recovery']} storms reached 90% restored within the reports.",
        "\nEach finding's uncertainty and limits are given in its chapter.\n",
        *v2_opening(r),
        "### How to read it\n",
        "Everything here is descriptive: it shows what happened together, not what caused what. The analysis plan was "
        "committed on November 22, 2026, in the project's private version-controlled repository (commit 9fc17a4), "
        "before any recovery outcome was computed. The plan file as committed is published in the data repository with "
        "its SHA-256, so it can be checked against later changes. It is not blind to some figures, which are listed in "
        "the methods. Every number is generated by code, and each chapter states its limits. The data and code are public. It's written for emergency managers, utilities, carriers, regulators, "
        "and anyone who has lost signal in a storm.\n",
    ]


def build_page(r: dict, after_opening: str = "") -> str:
    c1, c2, c3, c4, c5, c6, c7, c8, c9 = (r[f"chapter_{i}"] for i in range(1, 10))
    h1, h3, h4 = c1["headlines"], c3["headlines"], c4["headlines"]
    L = []
    add = L.append

    for x in opening_section(r):  # replaces "In brief" (2026-11-23); every number it held is in the chapters
        add(x)
    if after_opening:  # the map, the page's first exhibit (Tim's instruction, 2026-11-23)
        add(after_opening)

    # 1
    add("## 1. The question and the data\n")
    none = c1["reports_without_study_state_rows"]
    shared = c1["reports_shared_by_two_storms"]
    add(f"**Claim.** The FCC's Disaster Information Reporting System (DIRS) publishes, for each activated storm, a "
        f"daily county table of cell sites served and out. Of {h1['n_reports_in_scope']['value']} reports in scope, "
        f"{h1['n_reports_excluded']['value']} are excluded (they fail validation; listed in the methods) and "
        f"{len(none)} have county rows only outside the ten study states ({', '.join(sorted({x['storm'] for x in none}))}, "
        f"{none[0]['report_date']} to {none[-1]['report_date']}: Puerto Rico and the U.S. Virgin Islands), leaving "
        f"{h1['n_reports_used']['value']} reports for {h1['n_storms']['value']} storms: "
        f"{n0(h1['n_county_days']['value'])} county-report rows in {n0(h1['n_counties']['value'])} counties of ten Gulf "
        f"and Southeast states.\n")
    rows = [(s["storm"], s.get("rule_period") or "–", s["dirs_activation_date"], s.get("n_reports", 0),
             s.get("n_counties", 0), f"{s.get('first_report', '–')} to {s.get('last_report', '–')}" if s.get("in_panel") else "–",
             len(re.findall(r"\(\d{4}-\d\d-\d\d\)", s["excluded_reports"])))
            for s in c1["storms"]]
    add("**Exhibit.**\n\n[figure:fig-coverage]\n")
    add(table(["Storm", "Rule period", "DIRS activation", "Reports used", "Counties", "Report dates", "Reports excluded"], rows))
    add(f"\n{', '.join(shared['storms'])} share {shared['n']} reports, so the \"Reports used\" column counts those "
        f"reports for both storms.\n")
    add("**What it means.** The tables combine all providers, so no single company's network is visible. Coverage "
        "changes during a storm: counties join and leave the reporting area, and the FCC narrows the area as outages "
        "fall. Reporting was voluntary before February 20, 2025 and mandatory after; from June 30, 2026, FCC 26-34 "
        "exempts non-facilities-based providers and drops DIRS final reports. So who reports can change between storms. "
        "The page groups storms by these rule periods, using each storm's DIRS activation date:\n")
    for code, label in PERIOD_LABELS.items():
        add(f"- **{code}:** {label}")
    add("")

    # 2
    a = c2["area_by_report"]
    e = c2["exposure"]
    add("## 2. Anatomy of a storm: Isaias, October 2026\n")
    add(f"**Claim.** Isaias's first report counted {n0(a[0]['sites_out'])} of {n0(a[0]['sites_served'])} cell sites out "
        f"({f1(a[0]['pct_out'])}%) across its reporting area; by its last report, {n0(a[-1]['sites_out'])} "
        f"({f1(a[-1]['pct_out'])}%) were out.\n")
    add("**Exhibit.**\n\n[figure:fig-isaias-map]\n\n[figure:fig-isaias]\n")
    srows = [(x["state"], x["report_date"], n0(x["sites_out"]), n0(x["sites_served"]), f1(x["pct_out"]))
             for x in c2["state_by_report"]]
    add(table(["State", "Report", "Sites out", "Sites served", "% out"], srows))
    top5 = c2["county_peaks"][:5]
    where = "in the Florida Panhandle" if all(x["state"] == "Florida" for x in top5) else "near the track"
    add(f"\n**What it means.** The five worst-hit counties ({_and([x['county'] for x in top5])}) are all {where}, "
        f"near the track, on the coast and inland. "
        f"{e['counties_inside_34kt']} of Isaias's {e['n_counties']} counties fell inside its 34-knot winds and "
        f"{e['counties_inside_64kt']} inside its 64-knot winds; its strongest wind at the point of the track nearest a "
        f"county was {f1(e['max_wind_kt_at_nearest_track_point'], 0)} knots. {c2['notes'][1]} {c2['notes'][0]}\n")

    # 3
    lp, lc, mp = h3["largest_peak_pct_out"], h3["largest_peak_sites_out"], h3["median_peak_pct_out"]
    add("## 3. How much goes dark\n")
    add(f"**Claim.** At their peaks, between {f1(mp['min'])}% and {f1(mp['max'])}% of the cell sites in storms' "
        f"reporting areas were out; the median across {mp['n']} storms is {f1(mp['value'])}% (95% interval {ci(mp)}). "
        f"Helene had the most sites out, {n0(lc['value'])} (95% interval {n0(lc['ci_low'])} to {n0(lc['ci_high'])}).\n")
    add("**Exhibit.**\n\n[figure:fig-peaks]\n")
    prow = []
    for s in c3["storms"]:
        c = s["cable_wireline_subs_out_at_peak"]
        prow.append((s["storm"], s["rule_period"], s["peak_report_date"], f1(s["peak_days_since_landfall"]["value"]),
                     f"{n0(s['peak_sites_out']['value'])} ({n0(s['peak_sites_out']['ci_low'])} to {n0(s['peak_sites_out']['ci_high'])})",
                     f"{f1(s['peak_pct_out']['value'])}", n0(s["sites_served_at_peak"]["value"]),
                     n0(c["value"]) if c["value"] is not None else "not printed"))
    add(table(["Storm", "Period", "Peak report", "Days since 34-kt winds arrived", "Sites out (95% interval)", "% out", "Sites served",
               "Cable and wireline subscribers out (report area)"], prow))
    add(f"\n{origin_sentence(r)}")
    tf = time_flag_notes(r)
    notes = [v + (" " + tf[k] if k in tf else "") for k, v in c3["page_notes"].items()]
    notes += [v for k, v in tf.items() if k not in c3["page_notes"]]
    mich = next(s for s in c3["storms"] if s["storm"] == "Michael")
    jf = mich["jefferson_fl_flag"]
    notes.append(f"Michael's reports print {n0(jf['sites_served_this_storm']['value'])} sites served in Jefferson County, "
                 f"Florida, against a median of {n0(jf['sites_served_other_storms']['value'])} in later storms' reports: an "
                 f"apparent FCC denominator error, kept as printed. Without it, Michael's peak is "
                 f"{f1(mich['without_jefferson_fl']['peak_pct_out']['value'])}%.")
    add("\n**What it means.** Peaks are shares of each storm's own reporting area, which ranges from a few counties to "
        "hundreds, so a small share can hide a large count and the reverse. " + " ".join(notes) +
        " Cable and wireline subscribers out are printed for the whole report area, with no county detail.\n")

    # 4
    t50, t90 = h4["median_time_to_50pct_restored"], h4["n_storms_reaching_90pct_restored"]
    sd = h4["median_site_days_lost"]
    add("## 4. How fast it comes back\n")
    add(f"**Claim.** Half of the sites out at a storm's peak were back within a median of {f1(t50['value'], 0)} days "
        f"(95% interval {ci(t50, 0)}; {t50['n_censored']} of {t50['n']} storms never reached half while their reports "
        f"ran). Only {t90['value']} of {t90['n']} storms reached 90% restored before their reports ended: {t90['min']} if "
        f"counties that leave the reports are counted as still out, {t90['max']} if they are counted as restored. "
        f"{t90['note']}\n")
    add("**Exhibit.**\n\n[figure:fig-curves]\n\n[figure:fig-restored]\n")
    rrow = []
    left = c4["headlines"]["storms_left_out_of_time_summaries"]
    for s in c4["storms"]:
        a5, a9 = s["time_to_50pct_restored"], s["time_to_90pct_restored"]
        if s["n_reports_after_peak"] == 0:
            rrow.append((f"{s['storm']} (note)", n0(s["affected_sites"]["value"]), "–", "–", "–", "–"))
            continue
        rrow.append((s["storm"], n0(s["affected_sites"]["value"]), days(a5["value"], a5["censored"], a5["censored_at"]),
                     days(a9["value"], a9["censored"], a9["censored_at"]),
                     days(a9["best_case"], a9["best_case_censored"], a9["censored_at"]),
                     n0(s["site_days_lost"]["value"])))
    add(table(["Storm", "Sites out at peak", "Days to 50%", "Days to 90% (leaving counties still out)",
               "Days to 90% (leaving counties restored)", "Site-days lost, peak to last report"], rrow))
    for x in left:
        add(f"\nNote. {x['note']}")
    seen50 = [s["time_to_50pct_restored"]["value"] for s in c4["storms"] if not s["time_to_50pct_restored"]["censored"]]
    add(f"\n**What it means.** Where it is seen, recovery to half takes from {f1(min(seen50), 0)} to "
        f"{f1(max(seen50), 0)} days. The last stretch to 90% is "
        f"not observed in {t90['n'] - t90['min']} of {t90['n']} storms if leaving counties are counted as still out, or "
        f"{t90['n'] - t90['max']} if they are counted as restored, because the reports stop. {FINAL_REPORT_SENTENCE} "
        f"A time is the first report "
        f"from which the share restored stays "
        f"past the threshold in every later report; the true time falls after the report before. Site-days lost "
        f"(median {n0(sd['value'])}, range {n0(sd['min'])} to {n0(sd['max'])}, {sd['n']} storms) count only to each "
        f"storm's last report. These medians, ranges and counts leave out {_and([x['storm'] for x in left])} (note "
        f"above).\n")

    # 5
    p = c5["headlines"]["pooled_all_storms"]
    nc = [x["storm"] for x in c5["headlines"]["not_collected"]]
    ext = c5["external_check"]
    add("## 5. Why sites go dark\n")
    add(f"**Claim.** In the FCC's cause columns, loss of commercial power accounts for {f1(p['power']['value'])}% of "
        f"cell sites out (95% interval {ci(p['power'])}), loss of transport (backhaul) {f1(p['transport']['value'])}%, "
        f"and damage to the site {f1(p['damage']['value'])}%, pooled over {p['power']['n']} storms' reports (each site "
        f"counts once for every report in which it is out). {f1(p['unattributed']['value'])}% have no cause given, and "
        f"causes exceed sites out by {f1(p['overattributed']['value'])}%, consistent with some sites counted under more "
        f"than one cause.\n")
    add("**Exhibit.**\n\n[figure:fig-causes]\n")
    crow = [(s["storm"], *(f1(s["pooled_over_reports"][k]["value"]) for k in ("power", "transport", "damage", "unattributed",
                                                                            "overattributed")))
            for s in c5["storms"]]
    add(table(["Storm", "Power %", "Transport %", "Damage %", "No cause given %", "Over-attributed %"], crow))
    add(f"\n**What it means.** Every share is a share of all sites out, not only of those with a cause. "
        f"{c5['notes'][2]} Reports for Idalia (2023) and Beryl (2024) say so: \"{c5['fcc_multiple_causes_note_text']}\" "
        f"For other reports that reading is an inference. {', '.join(nc[:-1])} and {nc[-1]} print no cause columns; "
        f"they are left out, not counted as zero. As a check, converted to the attributed-only base of Olukola et al. "
        f"(2026), who use 23 days of cause data from 24 reports where this page uses {ext['n_reports_ours']}, this "
        f"page's Helene shares are damage {f1(ext['ours_converted']['damage'])}%, power "
        f"{f1(ext['ours_converted']['power'])}% and transport {f1(ext['ours_converted']['transport'])}%, against their "
        f"{f1(ext['paper']['damage'])}%, {f1(ext['paper']['power'])}% and {f1(ext['paper']['transport'])}%.\n")

    # 6
    rho = c6["headlines"]["comovement_at_as_of_time"]
    add("## 6. The power coupling\n")
    add(f"**Claim.** Within a storm, county-reports with a higher share of electricity customers without power tend to "
        f"have a higher share of cell sites out: the median rank correlation across {rho['n']} storms is "
        f"{f1(rho['value'], 2)} (95% interval "
        f"{ci(rho, 2)}). {c6['page_text']['lag_pattern']}\n")
    add(f"{c6['page_text']['main_text_caveat']}\n")
    add("**Exhibit.**\n\n[figure:fig-power-overlay]\n\n[figure:fig-power]\n")
    by = c6["by_lag"]["lag_0h"]["pct_sites_out"]["by_storm"]
    order = [s["storm"] for s in c3["storms"] if s["storm"] in by]  # date order
    orow = [(k, f"{f1(by[k]['value'], 2)} ({ci(by[k], 2)})" if by[k]["value"] is not None else "–", n0(by[k]["n"]),
             ", ".join(f"{kk.replace('_', ' ')} {n0(vv)}" for kk, vv in by[k]["coverage_counts"].items()))
            for k in order]
    add(table(["Storm", "Rank correlation (95% interval)", "County-reports", "EAGLE-I coverage flags"], orow))
    in_corr = {t["doc_id"] for v in c6["overlay"].values() for t in v}  # reports matched to EAGLE-I
    for x in r["chapter_1"].get("time_flagged_reports", []):
        if x["doc_id"] in in_corr and x["storm"] in by:
            add("\n" + CORRELATION_FLAG_TEXT[x["flag"]].format(storm=x["storm"], date=x["report_date"]))
    add(f"\n**What it means.** {c6['notes'][0]} {c6['notes'][1]} Coverage is flagged on every result: \"low coverage\" "
        f"means the state's EAGLE-I covered share was below 0.75 that year, and 2017, 2023 and 2024 have no published "
        f"coverage.\n")

    # 7
    z, dd = c7["by_wind_zone"], c7["by_distance_band"]
    add("## 7. Exposure\n")
    add(f"**Claim.** Counties inside a storm's 64-knot winds had a peak of {f1(z['inside 64 kt']['value'])}% of cell sites "
        f"out (95% interval {ci(z['inside 64 kt'])}); outside its 34-knot winds, {f1(z['outside 34 kt']['value'])}% "
        f"(95% interval {ci(z['outside 34 kt'])}).\n")
    add("**Exhibit.**\n\n[figure:fig-zone]\n\n[figure:fig-distance]\n")
    add(f"**What it means.** With wind zone in the model, the intervals for distance and for the storm's intensity "
        f"include no association (model in the methods). {c7['page_text']['storm_misses']}\n")

    # 8
    pt = c8["page_text"]
    add("## 8. Who waits longest\n")
    add(f"**Claim.** {pt['headline']} {pt['headline_bound']}\n")
    add("**Exhibit.**\n\n[figure:fig-svi]\n")
    raw = c8["headlines"]["raw_by_quartile"]
    wrow = [(q, n0(v["median_days_since_landfall"]["n"]), f"{f1(v['svi_range'][0], 3)} to {f1(v['svi_range'][1], 3)}",
             f"{f1(v['median_days_since_landfall']['value'])} ({ci(v['median_days_since_landfall'])})",
             n0(v["median_days_since_landfall"]["n_censored"]),
             " / ".join(f"{100 * v[f'share_below_5pct_by_day_{d}']['value']:.0f}%" for d in (3, 7, 14)))
            for q, v in raw.items()]
    add(table(["SVI quartile", "Storm-counties", "SVI range", "Median days (95% interval)", "Censored",
               "Below 5% by day 3 / 7 / 14"], wrow))
    hr = c8["headlines"]["hazard_ratios"]
    add(f"\nHolding wind zone, distance, track intensity and the storm fixed, the hazard ratios for reaching below 5% "
        f"(above 1 is sooner) are {f1(hr['svi_Q2']['value'], 2)} ({ci(hr['svi_Q2'], 2)}) for the second quartile, "
        f"{f1(hr['svi_Q3']['value'], 2)} ({ci(hr['svi_Q3'], 2)}) for the third and {f1(hr['svi_Q4 (most)']['value'], 2)} "
        f"({ci(hr['svi_Q4 (most)'], 2)}) for the most vulnerable.\n")
    line = earlier_origins_line(c8)
    if line:
        add(line + "\n")
    add(f"**What it means.** {pt['wording']} What the data can't rule out:\n")
    for x in pt["cannot_rule_out"]:
        add(f"- {x}")
    add(f"\n{pt['best_case_sensitivity']}\n")

    # 9
    add("## 9. Did the rules help?\n")
    add(f"**Claim.** {c9['page_text']['headline']}\n")
    add("**Exhibit.**\n")
    st9 = [(s["storm"], s["rule_period"], f1(s["peak_pct_out"]), days(s["t50"], s["t50_censored"], s["censored_at"]),
            days(s["t90"], s["t90_censored"], s["censored_at"]), days(s["t90_best"], s["t90_best_censored"], s["censored_at"]),
            n0(s["site_days_lost"]), f1(s["max_wind_kt"], 0), s["counties_inside_64kt"]) if s["recovery_observed"] else
           (f"{s['storm']} (note)", s["rule_period"], f1(s["peak_pct_out"]), "–", "–", "–", "–", f1(s["max_wind_kt"], 0),
            s["counties_inside_64kt"]) for s in c9["storms"]]
    add(table(["Storm", "Period", "Peak % out", "Days to 50%", "Days to 90% (still out)", "Days to 90% (restored)",
               "Site-days lost", "Strongest wind at nearest track point (kt)", "Counties inside 64 kt"], st9))
    per = c9["periods"]
    bp = c9["by_period"]

    fmt = {"peak_pct_out": f1, "site_days_lost": n0, "max_wind_kt": lambda x: f1(x, 0)}

    def cell(m, code):
        v = bp[m][code]
        g = fmt.get(m, fdays)
        if not v["n_storms"]:
            return "no storm"
        if v["n_storms"] == 1:
            return f"{g(v['median'])} ({v['storm']})" if v["median"] is not None else f"not reached ({v['storm']})"
        med = g(v["median"]) if v["median"] is not None else "no median (censored)"
        rng = f"{g(v['min'])} to {g(v['max'])}" if v["min"] is not None else "none observed"
        cens = f"; {v['n_censored']} censored" if v.get("n_censored") else ""
        return f"{med} ({rng}{cens})"
    prow = [(f"{code}: {PERIOD_LABELS[code]}", bp["peak_pct_out"][code]["n_storms"],
             *(cell(m, code) for m in ("peak_pct_out", "time_to_50pct_restored",
                                       "time_to_90pct_restored_counties_leaving_stay_out",
                                       "time_to_90pct_restored_counties_leaving_restored", "site_days_lost", "max_wind_kt")))
            for code in per]
    add("\n" + table(["Rule period", "Storms", "Peak % out", "Days to 50%", "Days to 90% (still out)",
                      "Days to 90% (restored)", "Site-days lost", "Strongest wind (kt)"], prow))
    for x in c9["storms_left_out_of_time_summaries"]:
        add(f"\nNote. {x['note']} It is counted in the peak and wind columns only.")
    add("\nMedians, with the range of observed values in parentheses; censored storms are counted separately, and a "
        "median is given only when censoring cannot change it.\n\nThe plan's red flags (any one rules out the plan's \"coincided with\" "
        "wording for the rule periods):\n")
    for k, v in c9["red_flags"].items():
        label = RED_FLAG_LABELS[k]
        add(f"- **{label}: {'triggered' if v['triggered'] else 'not triggered'}.**"
            + (f" {cap(readable(v['reason']))}." if v["reason"] else ""))
    add(f"\n**What it means.** {c9['wording']['note']} {c9['notes'][1]} {c9['notes'][3]}\n")
    return "\n".join(L)


# ---------------------------------------------------------------- v2-4: county lookup --

def lookup_data(r: dict, panel: pd.DataFrame) -> dict:
    """The county lookup's data, from the published panel (dirs_county_day.csv) and each storm's day 0 in results.json.
    Time-flagged reports are left off the storm's timeline (decision 2026-11-23)."""
    st = {s["storm_key"]: s for s in r["chapter_3"]["storms"]}
    p = panel[(panel.time_flag.fillna("") == "") & panel.storm_key.isin(st) & (panel.sites_served > 0)].copy()
    day0 = p.storm_key.map({k: pd.Timestamp(v["landfall_utc"]) for k, v in st.items()})
    p["day"] = ((pd.to_datetime(p.as_of_utc, utc=True) - day0).dt.total_seconds() / 86400).round(2)
    p["pct"] = (100 * p.sites_out / p.sites_served).round(1)
    storms = [{"key": k, "name": v["storm"], "period": v["rule_period"],
               "report_days": sorted(p[p.storm_key == k].drop_duplicates("doc_id").day.tolist())}
              for k, v in st.items()]
    counties = []
    for fips, g in p.sort_values(["state", "county", "day"]).groupby("fips", sort=False):
        series = {k: [[float(x.day), float(x.pct), int(x.sites_out), int(x.sites_served), str(x.report_date)]
                      for x in h.sort_values("day").itertuples()] for k, h in g.groupby("storm_key", sort=False)}
        counties.append({"fips": fips, "county": str(g.county.iloc[0]).title(), "state": g.state.iloc[0],
                         "abbr": abbr(g.state.iloc[0]), "series": series})
    flagged = [x for x in r["chapter_1"].get("time_flagged_reports", [])]
    return {"storms": storms, "counties": counties,
            "note": " ".join(f"{x['storm']}'s report of {x['report_date']} (the combined Marco–Laura report) is left "
                             f"off {x['storm']}'s line." for x in flagged),
            "source": f"/static/data/{PANEL_PUBLIC.name}"}


def write_lookup(data: dict, path: Path = LOOKUP_JSON) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")


def verify_lookup(r: dict, panel: pd.DataFrame, path: Path = LOOKUP_JSON) -> bool:
    """Re-read the written file and compare every value with a fresh derivation from the panel."""
    return json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(lookup_data(r, panel), ensure_ascii=False))


# ---------------------------------------------------------------- v2-6: interactive map --

def _encode_ring(coords, x0, y0, kx, ky) -> list:
    q = [(int(round((x - x0) / kx)), int(round((y - y0) / ky))) for x, y in coords]
    out, px, py = [], 0, 0
    for i, (x, y) in enumerate(q):
        if i and (x, y) == (px, py):
            continue
        out.append([x - px, y - py])
        px, py = x, y
    return out


def map_topology() -> dict:
    """TopoJSON (one arc per ring, quantized, delta-encoded) of the study states' counties and their state outlines,
    from the Census 2022 cartographic boundary file, simplified as a coverage so shared borders stay identical."""
    import geopandas as gpd
    import shapely
    g = gpd.read_file(f"zip://{BOUNDARIES.as_posix()}")
    g = g[g.STATEFP.isin(STUDY_FIPS)].sort_values("GEOID").reset_index(drop=True)
    simp = shapely.coverage_simplify(g.geometry.values, MAP_TOLERANCE_DEG)
    states = gpd.GeoDataFrame({"STATEFP": g.STATEFP}, geometry=simp, crs=g.crs).dissolve("STATEFP")
    # d3-geo reads polygons on the sphere: exterior rings clockwise, holes counter-clockwise (the reverse of GeoJSON's
    # right-hand rule), or a county becomes "the whole globe minus the county"
    simp = shapely.orient_polygons(simp, exterior_cw=True)
    states = states.assign(geometry=shapely.orient_polygons(states.geometry.values, exterior_cw=True))
    x0, y0, x1, y1 = g.total_bounds
    kx, ky = (x1 - x0) / (TOPO_QUANT - 1), (y1 - y0) / (TOPO_QUANT - 1)
    arcs = []

    def polys(geom):
        return [geom] if geom.geom_type == "Polygon" else list(geom.geoms)

    def encode(geom):
        out = []
        for pl in polys(geom):
            rings = []
            for ring in [pl.exterior, *pl.interiors]:
                arcs.append(_encode_ring(ring.coords, x0, y0, kx, ky))
                rings.append([len(arcs) - 1])
            out.append(rings)
        return {"type": "MultiPolygon", "arcs": out}
    counties = [{**encode(geom), "id": r.GEOID, "properties": {"name": r.NAME, "state": r.STUSPS}}
                for r, geom in zip(g.itertuples(), simp)]
    st = [{**encode(geom), "id": fp} for fp, geom in zip(states.index, states.geometry)]
    return {"type": "Topology", "transform": {"scale": [kx, ky], "translate": [x0, y0]}, "arcs": arcs,
            "objects": {"counties": {"type": "GeometryCollection", "geometries": counties},
                        "states": {"type": "GeometryCollection", "geometries": st}}}


def decode_arc(arc, transform) -> list:
    """Inverse of _encode_ring (for the round-trip test)."""
    (kx, ky), (x0, y0) = transform["scale"], transform["translate"]
    x = y = 0
    out = []
    for dx, dy in arc:
        x, y = x + dx, y + dy
        out.append((x0 + x * kx, y0 + y * ky))
    return out


def map_data(r: dict, panel: pd.DataFrame) -> dict:
    """Every storm's used reports (time-flagged reports left off the timeline) with each listed county's % of sites
    out, sites out and served, and cause shares of sites out where the report prints causes."""
    st = {s["storm_key"]: s for s in r["chapter_3"]["storms"]}
    p = panel[(panel.time_flag.fillna("") == "") & panel.storm_key.isin(st) & (panel.sites_served > 0)].copy()
    day0 = p.storm_key.map({k: pd.Timestamp(v["landfall_utc"]) for k, v in st.items()})
    p["day"] = ((pd.to_datetime(p.as_of_utc, utc=True) - day0).dt.total_seconds() / 86400).round(2)
    storms = []
    for k, v in st.items():
        q = p[p.storm_key == k]
        reports = []
        for doc, h in sorted(q.groupby("doc_id"), key=lambda kv: (kv[1].day.iloc[0], kv[0])):
            cty = {}
            for x in h.itertuples():
                causes = None
                if x.sites_out > 0 and not any(pd.isna(getattr(x, c)) for c in ("out_damage", "out_transport", "out_power")):
                    causes = [round(100 * float(getattr(x, c)) / float(x.sites_out), 1)
                              for c in ("out_damage", "out_transport", "out_power")]
                cty[x.fips] = [round(100 * float(x.sites_out) / float(x.sites_served), 1), int(x.sites_out),
                               int(x.sites_served), causes]
            reports.append({"doc_id": doc, "date": str(h.report_date.iloc[0]), "day": float(h.day.iloc[0]),
                            "counties": cty})
        storms.append({"key": k, "name": v["storm"], "period": v["rule_period"], "reports": reports})
    vals = [c[0] for s in storms for rep in s["reports"] for c in rep["counties"].values()]
    vmax = max(vals)
    dist = {"n_county_reports": len(vals), "share_zero": sum(v == 0 for v in vals) / len(vals),
            "share_50_or_more": sum(v >= 50 for v in vals) / len(vals)}
    flagged = r["chapter_1"].get("time_flagged_reports", [])
    return {"storms": storms, "value_max": vmax, "distribution": dist,
            "note": " ".join(f"{x['storm']}'s report of {x['report_date']} (the combined Marco–Laura report) is not a "
                             f"step on {x['storm']}'s slider." for x in flagged)}


def write_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")


def verify_map(r: dict, panel: pd.DataFrame, path: Path = MAP_JSON) -> bool:
    return json.loads(path.read_text(encoding="utf-8")) == json.loads(json.dumps(map_data(r, panel), ensure_ascii=False))


def map_section(data: dict) -> str:
    n_s = len(data["storms"])
    return f"""## Map: where cell sites were out, report by report

Choose a storm and move through its FCC reports to see each county's share of cell sites out. Counties shaded darker had
a larger share out ({MAP_SCALE_TEXT[MAP_SCALE]}); hatched light-grey counties were not in that day's report (not
reported, not zero), and counties in the report with no sites out have a faint tint. Hover over or tap a county
for its numbers, and the cause shares where the report gives them. The table under the map lists the same numbers for
the chosen report. Drawn in your browser from the published data for all {n_s} storms, with county shapes from the
Census Bureau; nothing is loaded from any other site. {data['note']}

Across all {n0(data['distribution']['n_county_reports'])} county-reports, {100 * data['distribution']['share_zero']:.1f}%
show 0% of sites out and {100 * data['distribution']['share_50_or_more']:.1f}% show 50% or more.

<div class="storm-map" data-src="/static/data/{MAP_JSON.name}" data-topo="/static/data/{MAP_TOPO.name}" data-scale="{MAP_SCALE}">
<div class="storm-map-controls">
<div><label for="storm-map-storm">Storm</label>
<select id="storm-map-storm" disabled><option>Loading…</option></select></div>
<div class="storm-map-slider"><label for="storm-map-day">Report</label>
<input id="storm-map-day" type="range" min="0" max="0" step="1" value="0" disabled></div>
<button type="button" class="storm-map-play" aria-pressed="false" disabled>Play</button>
</div>
<p class="storm-map-status" role="status" aria-live="polite"></p>
<figure class="storm-map-figure"><div class="storm-map-svg"></div>
<div class="storm-map-tip" aria-hidden="true" hidden></div></figure>
<details class="fig-data"><summary>View data table for this report</summary><div class="table-scroll storm-map-table"></div></details>
<noscript><p>The map needs JavaScript. The same data is in the <a href="/static/data/{PANEL_PUBLIC.name}">county-report
panel (CSV)</a>.</p></noscript>
</div>
<script src="/static/js/vendor/d3-7.9.0.min.js" defer></script>
<script src="/static/js/vendor/topojson-client-3.1.0.min.js" defer></script>
<script src="/static/js/hurricane-map.js" defer></script>
"""


def v2_sections(r: dict) -> str:
    """Chapters 10 to 13 (V2-1, V2-2, V2-3, V2-5), from results.json and the approved page text."""
    if "v2_1_public_record_misses" not in r:
        return ""
    L = []
    add = L.append
    # 10. V2-1
    a = r["v2_1_public_record_misses"]
    pt = a["page_text"]
    add("## 10. What the public record misses\n")
    add(f"*{V2_LABEL}*\n")
    add(f"**Claim.** {pt['headline']}\n")
    add(f"{pt['lead']}\n")
    add("**Exhibit.**\n")
    rows = [(x["storm"], x["last_report"]["report_date"], n0(x["sites_out_at_last_report"]["value"]),
             n0(x["peak_sites_out"]), pct1(x["share_of_peak"]["value"]),
             f"{len(x['counties_still_out'])} of {x['n_counties_in_last_report']}",
             f"{n0(x['carried_forward']['sites_out']['value'])} ({pct1(x['carried_forward']['share_of_peak']['value'])})")
            for x in a["storms"]]
    add(table(["Storm", "Last report", "Sites still out", "Peak sites out", "Share of peak still out",
               "Counties still out, of those listed",
               "Upper bound: if every county that left the reports while still out had stayed out (share of peak)"], rows))
    for fn in pt["footnotes"]:
        add(f"\nNote. {fn}")
    sens = a["sensitivity"]["without_serious_flag_reports"]
    base = {x["storm"]: x["last_report"]["report_date"] for x in a["storms"]}
    moved = [x for x in sens if "note" not in x and x["last_report_date"] != base[x["storm"]]]
    none = [x["storm"] for x in sens if "note" in x]
    parts = [f"{x['storm']}'s last report without a serious flag is {x['last_report_date']}, with "
             f"{n0(x['sites_out_at_last_report'])} sites out ({pct1(x['share_of_peak'])} of its peak)" for x in moved]
    add("\n**Sensitivity.** Without reports carrying a serious validation flag: " + "; ".join(parts) +
        (f". {_and(none)} cannot be shown, because every one of their reports carries a serious flag." if none else ".") +
        " Every other storm is unchanged.\n")
    add("**What it means.** \"Still out in the FCC's last report\" counts sites at the moment the public reporting "
        f"stopped; it does not say how long they stayed out afterwards. {FINAL_REPORT_SENTENCE} The upper bound assumes every county that left the "
        "reports while still out stayed out, which the reports cannot confirm.\n")

    # 11. V2-2
    b = r["v2_2_backup_power"]
    pb = b["page_text"]
    add("## 11. Sites on backup power\n")
    add(f"*{V2_LABEL}*\n")
    add(f"**Claim.** {pb['collected_sentence']}\n")
    add("**Exhibit.**\n")
    left = set(pb["left_out_of_comparisons"])
    rows = [(x["storm"], f"{x['n_reports_collected']} of {x['n_reports']}", n0(x["most_sites_on_backup"]["value"]),
             f"{x['most_sites_on_backup']['report_date']} (day {f1(x['most_sites_on_backup']['days_since_day0'])})",
             n0(next(rr["sites_served_printed"] for rr in x["by_report"]
                     if rr.get("report_date") == x["most_sites_on_backup"]["report_date"] and rr["collected"])),
             pct1(x["most_sites_on_backup"]["share_of_sites_served"]))
            for x in b["storms"] if x["storm"] not in left]
    add(table(["Storm", "Reports with backup power", "Most sites on backup power in one report", "Report (days since "
               "34-kt winds arrived)", "Sites served in the counties reporting it", "Share of those sites served"], rows))
    for fn in pb["footnotes"]:
        add(f"\nNote. {fn}")
    partial = [x for x in b["storms"] if x["any_partial_report"]]
    if partial:
        add("\n**Sensitivity.** With every county in the report as the denominator (printed value or not): " + "; ".join(
            f"{x['storm']} {pct1(next(rr['share_of_all_sites_served'] for rr in x['by_report'] if rr['collected']))}"
            for x in partial) + ". Every other storm prints the column for all its counties, so its share is unchanged.")
    add("\n**What it means.** These are sites operating on backup power as the FCC reports them; they say nothing about "
        "how long backup lasts or what followed. Counts come first: a share can rise when the reporting area narrows "
        "even as the count falls. The column was printed only for the storms named above, so the storms are not "
        "compared across rule periods.\n")

    # 12. V2-3
    t = r["v2_3_power_cell_timing"]
    p3 = t["page_text"]
    o = t["headlines"]
    add("## 12. Which comes back first: power or cell service?\n")
    add(f"*{V2_LABEL}*\n")
    add(f"**Claim.** {p3['finding']} {p3['undetermined']}\n")
    add(f"{p3['scale_caution']}\n")
    add("**Exhibit.**\n")
    lab = {"power_first": "Power fell below 5% first", "same_report": "Same report",
           "cell_first": "Cell fell below 5% first", "undetermined": "Undetermined (censoring)"}
    add(table(["Order", "Counties", "Share (95% storm-bootstrap interval)"],
              [(lab[k], v["count"], f"{pct1(v['share'])} ({pct1(v['ci_low'])} to {pct1(v['ci_high'])})")
               for k, v in o["orders"].items()]))
    sens = t["sensitivity"]
    names = {"threshold_10pct": "Both thresholds at 10%", "first_crossing": "First crossing instead of staying below",
             "without_low_or_unknown_coverage": "Without low- and unknown-coverage EAGLE-I counties",
             "without_serious_flag_reports": "Without reports with a serious flag"}
    add("\n" + table(["Sensitivity display", "Counties (storms)", "Power first", "Same report", "Cell first",
                       "Undetermined"],
                      [(names[k], f"{v['n']} ({v['n_storms']})", *(pct1(v["orders"][x]["share"]) for x in lab))
                       for k, v in sens.items() if k in names]))
    add("\nBy rule period, shown and not compared: " + "; ".join(p3["rule_periods_shown_not_compared"]) + ".\n")
    add(f"**What it means.** {p3['not_measured']} Storms without EAGLE-I data "
        f"({_and(t['storms_without_power_data'])}) are not included"
        + (f", and {_and(t['storms_without_counties_at_risk'])} has no county at or above 5% of sites out"
           if t.get("storms_without_counties_at_risk") else "") + ". \"Same report\" means within one report "
        "interval, not at the same moment.\n")

    # 13. V2-5
    n = r["v2_5_network_redundancy"]
    p5 = n["page_text"]
    G = n["groups"]
    add("## 13. Do counties with more mobile providers recover differently?\n")
    add(f"*{V2_LABEL}*\n")
    add(f"**Claim.** {p5['finding']}\n")
    add(f"{p5['limits']}\n")
    add("**Exhibit.**\n")
    hr = n["model"].get("hazard_ratios", {})
    rows = []
    for i, lab5 in enumerate(G["labels"]):
        v = n["raw_by_group"][lab5]["median_days"]
        h = hr.get(f"group_{lab5}")
        rows.append((lab5, n0(G["sizes"][lab5]), n0(n["at_risk_by_group"][lab5]),
                     f"{fdays(v['value'])} ({ci(v, 1, 'days')})", n0(v["n_censored"]),
                     "reference" if i == 0 else (f"{f1(h['value'], 2)} ({ci(h, 2)})" if h else "–")))
    add(table(["Mobile providers covering at least half the county's area", "Storm-counties (all)",
               "Storm-counties at risk", "Median days to stay below 5% (95% interval)", "Censored",
               "Hazard ratio (95% interval; above 1 = sooner)"], rows))
    se = n["sensitivity"]

    def model_txt(m, key_prefix):
        if "error" in m:
            return "not estimable"
        def name(k):
            return "per provider" if k.startswith("per_provider_") else f"{k[len('group_'):]} providers"
        return "; ".join(f"{name(k)}: {f1(v['value'], 2)} ({ci(v, 2)})" for k, v in m["hazard_ratios"].items()
                         if k.startswith(("group_", "per_provider_")))
    sens_rows = [
        ("Provider count as a number", model_txt(se["provider_count_as_number"], "")),
        ("Mobile, any coverage, count as a number", model_txt(se["mobile_any_coverage_count_as_number"], "")),
        ("Including storms before 2022 (network data from after the storm)",
         model_txt(se["including_storms_before_2022_network_data_from_after_the_storm"]["model"], "group_")),
        ("Without reports with a serious flag", model_txt(se["without_serious_flag_reports"]["model"], "group_")),
    ]
    fx = se["fixed_broadband_secondary"]
    for k, lab_ in (("fixed_any_excl_near_universal", "Fixed, any service, near-universal providers excluded"),
                    ("fixed_any", "Fixed, any service"), ("fixed_half", "Fixed, at least half of locations")):
        sens_rows.append((lab_, model_txt(fx[k]["model"], "group_")))
    sens_rows.append(("Fixed, at least half of locations, near-universal providers excluded, count as a number",
                      model_txt(fx["fixed_half_excl_near_universal_count_as_number"], "")))
    add("\n" + table(["Sensitivity display", "Hazard ratios (95% interval)"], sens_rows))
    m = n["model"]
    left_out = sorted(set(n["storms_main"]) - {k.split("_")[0] for k in []})
    add(f"\nGroups were fixed from the counts alone, before any recovery data was joined: whole values as close to "
        f"thirds as ties allow, no group under 20% of storm-counties. Fixed broadband is shown only as sensitivity "
        f"displays; rows marked \"near-universal providers excluded\" leave out {p5['near_universal']}. The hazard "
        f"model covers {len(m['storms_in_model'])} of the {len(n['storms_main'])} storms ({n0(m['n_counties'])} "
        f"counties); a storm whose effect cannot be estimated stays in the raw table. "
        f"{n['sensitivity']['release_within_12_months']['note'].capitalize()}.\n")
    add("**What it means.** Association only: these counts describe reported coverage before the storm, not which "
        "networks were out or how they were restored.\n")
    return "\n".join(L)


def lookup_section(data: dict) -> str:
    n_c = len(data["counties"])
    return f"""## Look up a county

Choose any of the {n_c} counties in the FCC's reports to see each storm's share of the county's cell sites out, report
by report, by days since the storm's 34-knot winds first reached a study-state county. Points are the FCC's reports;
lines join only consecutive reports of that storm at most 1.5 days apart, so a missing or excluded report leaves a gap. Built in the browser from the published data, with nothing loaded
from any other site. {data['note']}

<div class="county-lookup" data-src="/static/data/{LOOKUP_JSON.name}">
<label for="county-lookup-select">County</label>
<select id="county-lookup-select" disabled><option value="">Loading counties…</option></select>
<p class="county-lookup-status" role="status" aria-live="polite"></p>
<div class="county-lookup-panels"></div>
<details class="fig-data"><summary>View data table</summary><div class="table-scroll county-lookup-table"></div></details>
<noscript><p>The lookup needs JavaScript. The same data is in the <a href="{data['source']}">county-report panel
(CSV)</a>.</p></noscript>
</div>
<script src="/static/js/hurricane-county-lookup.js" defer></script>
"""


def methods_section(r: dict, decisions: str, plan: str, validation: pd.DataFrame, excluded: pd.DataFrame) -> str:
    c7, c8 = r["chapter_7"], r["chapter_8"]
    bd = boundary_download()
    L = []
    add = L.append
    add("## Methods, data and licenses\n")
    add("**Reading the reports.** Each FCC report is read from its text file or, when that is incomplete, its PDF, and "
        "every county row is checked against a second reading of the PDF. County rows must sum to the report's printed "
        "totals; a report that fails after one round of parser fixes is excluded with its reason. Counties are mapped to "
        "FIPS codes with a checked exception list. The storm key is the NHC ID plus the DIRS activation date.\n")
    add("**Times and censoring.** A county or storm reaches a threshold at the first report from which it stays past it "
        "in every later report that includes it; the true time lies after the report before. A county that leaves the "
        f"reports while still out is censored, not recovered. {origin_sentence(r)}"
        + (f" {before_day0_sentence(r)}" if before_day0_sentence(r) else "") + "\n")
    o = c7["headlines"]["odds_ratios"]
    cal = c7["headlines"]["calibration_held_out"]
    add(f"**Exposure model (chapter 7), checked for calibration.** A binomial model of each county's peak share of "
        f"sites out on wind zone, "
        f"distance to the track and the storm's intensity at the nearest track point, with storm-clustered intervals. "
        f"Odds ratios: inside 64-knot winds {f1(o['zone_inside 64 kt']['value'])} ({ci(o['zone_inside 64 kt'])}), "
        f"50-64 knots {f1(o['zone_50-64 kt']['value'])} ({ci(o['zone_50-64 kt'])}), 34-50 knots "
        f"{f1(o['zone_34-50 kt']['value'])} ({ci(o['zone_34-50 kt'])}), log distance {f1(o['log1p_dist_km']['value'], 2)} "
        f"({ci(o['log1p_dist_km'], 2)}), per 10 knots {f1(o['wind_per_10kt']['value'], 2)} ({ci(o['wind_per_10kt'], 2)}). "
        f"Calibration on storms held out of the fit one at a time: slope {f1(cal['slope']['value'], 2)} "
        f"({ci(cal['slope'], 2)}; 1 is ideal), calibration-in-the-large {f1(cal['in_the_large']['value'], 2)} "
        f"({ci(cal['in_the_large'], 2)}; 0 is ideal), mean absolute error {f1(cal['mean_absolute_error_pct_points']['value'])} "
        f"percentage points.\n")
    add(table(["Decile of predicted share", "Storm-counties", "Mean predicted %", "Observed %"],
              [(d["bin"], d["n"], f1(d["mean_predicted_pct"]), f1(d["observed_pct"])) for d in cal["deciles"]]))
    add("\n[figure:fig-calibration]\n")
    m = c8["headlines"]["model"]
    add(f"\n**Waiting-time model (chapter 8).** A discrete-time hazard with a complementary log-log link over the "
        f"intervals between a county's reports (interval censoring), with exposure, storm fixed effects and "
        f"county-clustered intervals: {n0(m['n_intervals'])} intervals, {n0(m['n_events'])} events, "
        f"{n0(m['n_counties'])} counties, {len(m['storms_in_model'])} storms (two storms whose fixed effect cannot be "
        f"estimated stay in the raw tables). {optimizer_note(c8)}SVI quartiles are of the at-risk storm-counties' "
        f"national percentiles; on "
        f"the national cut points only "
        f"{c8['sensitivity']['national_svi_cut_points']['counts']['Q1 (least)']} storm-counties fall in the lowest "
        f"quartile.\n")
    add("**Sensitivity displays.** Each chapter's results in `results.json` include the plan's sensitivity displays: "
        "dropping one storm at a time; holding each county's sites served at its peak value; best and worst cases for "
        "censored counties; with and without low-coverage EAGLE-I counties; with and without flagged reports, and "
        "without reports with a serious flag; without the report kept by the state_total_missing rule; and EAGLE-I with "
        "a missing record treated as zero.\n")
    add(f"**What the FCC's numbers measure.** Each FCC report carries this caveat: \"{FCC_CAVEAT}\" So the counts here "
        f"describe the network, not how many people lost service.\n")
    add(f"**EAGLE-I denominators.** {r['chapter_6']['page_text']['methods_denominator_note']}\n")
    add(f"**Mobile and fixed providers (chapter 13).** {bdc_methods_line()}\n")

    val = r["chapter_1"]["validation"]
    add("**Validation.** Every in-scope report was checked against its own printed totals: " +
        ", ".join(f"{n0(v)} {STATUS_LABELS.get(k, k.replace('_', ' '))}" for k, v in val["status_counts"].items()) +
        ". Flags on the reports used, by type (a report can carry several):\n")
    add(table(["Flag", "Kind", "Reports"], [(f["flag"], f["class"], f["n_reports"]) for f in val["flag_types_in_reports_used"]]))
    for k in val["known_fcc_inconsistencies"]:
        m = re.search(r"headline ([\d.]+)% vs ([\d.]+)%", k["detail"])
        add(f"\nThe known FCC inconsistency: {k['storm']}, {k['report_date']} ({k['doc_id']}), whose headline states "
            f"{m.group(1)}% of sites out against {m.group(2)}% computed from its own totals; the computed share is used.")
    add(f"\nEach report's flags and reasons are in the snapshot's "
        f"[`output/validation_dirs.csv`]({REPO_URL}/output/validation_dirs.csv). Excluded reports:\n")
    add(table(["Report", "Storm", "Date", "Reason"],
              [(e.doc_id, e.storm_name, e.report_date, e.reason) for e in excluded.itertuples()]))
    add("\n**Deviations from the analysis plan**, each logged in `docs/decisions.md` before it was run:\n")
    for date, what, why in deviations(decisions):
        sup = next((v for k, v in SUPERSEDED.items() if what.startswith(k)), None)
        add(f"- *{date}.* {what.split(':')[0]}: {sup}" if sup else entry(date, what, why, superseded_note(date, what)))
    add("\n**Decisions on the exhibits**, logged before the charts were built:\n")
    for date, what, why in exhibit_decisions(decisions):
        add(entry(date, what, why, superseded_note(date, what)))
    add("\n**Corrections**, made after results or an independent check were seen, also logged:\n")
    for date, what, why in corrections(decisions):
        add(entry(date, what, why, superseded_note(date, what)))
    add(f"\n**Seen before the plan was committed.** {PLAN_SENTENCE} It is not blind to some figures, as listed below. "
        f"From the plan:\n")
    for ln in neutral_plan(seen_before_registration(plan)).splitlines():
        add("> " + ln if ln.strip() else ">")
    add(f"\n**Data and licenses.** The cleaned county-report panel (DIRS fields only, with `out_unattributed` and "
        f"`out_overattributed` kept apart) is published under CC BY 4.0: "
        f"[download the CSV](/static/data/{PANEL_PUBLIC.name}). The code is MIT-licensed. FCC DIRS reports and NHC "
        f"tracks are public. EAGLE-I is CC BY 4.0 ({doi(EAGLEI_DOIS[0])}; dataset {doi(EAGLEI_DOIS[1])}; 2025 release "
        f"{doi(EAGLEI_DOIS[2])}); its \"customers\" are electricity meters. CDC/ATSDR SVI 2022, Census ACS 2022 and the "
        f"Census 2022 cartographic boundary file (map only; [{bd['url']}]({bd['url']}), downloaded {bd['when']}) are "
        f"public with attribution. FEMA OpenFEMA Disaster Declarations Summaries v2 "
        f"(https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries), accessed {fema_access()}: {OPENFEMA_DISCLAIMER} "
        f"The published panel keeps a column for whether a county had a FEMA declaration for that storm, as context for "
        f"reuse; no result on this page uses it. poweroutage.us is not used. The Olukola et al. (2026) dataset is used "
        f"only as a check and is not redistributed. FCC Broadband Data Collection public data (National Broadband Map, "
        f"[https://broadbandmap.fcc.gov/data-download](https://broadbandmap.fcc.gov/data-download)) were obtained through "
        f"the FCC's Public Data API under the FCC API terms of service accepted for the account, and are used for "
        f"provider counts only; no provider is named and the files are not redistributed. The map is drawn with D3 and topojson-client (ISC licence), served from this site. {AI_LINE} "
        f"{VIEWS_LINE}\n")
    add(f"**Disclosure.** {DISCLOSURE}\n")
    add("## Related work\n")
    for item in RELATED_WORK:
        add(f"- {item}")
    add("")
    add("## Sources\n")
    add("- Brelsford, C., et al. (2024). A dataset of recorded electricity outages by United States county 2014–2022. "
        f"*Scientific Data*, 11, 271. [https://doi.org/{EAGLEI_DOIS[0]}](https://doi.org/{EAGLEI_DOIS[0]})")
    add("- Olukola, O., Addeh, O. D., Konan, E. A., & Rahimi, N. (2026). The towers were standing: A cause "
        "decomposition of cellular outages during Hurricane Helene. arXiv:2609.10944. "
        "[https://doi.org/10.48550/arXiv.2609.10944](https://doi.org/10.48550/arXiv.2609.10944)")
    add("- Federal Communications Commission. Disaster Information Reporting System, Communications Status Reports, "
        "2017–2026; FCC 22-50 (Mandatory Disaster Response Initiative, adopted June 27, 2022; compliance from May 1, "
        "2024, per the FCC's MDRI page, https://www.fcc.gov/node/254876, accessed November 23, 2026); FCC 24-5 and DA 25-74 (mandatory DIRS from February 20, 2025; Federal Register 2025-00495); FCC 26-34 "
        "(adopted May 20, 2026; Federal Register 2026-13155, 91 FR 39516, June 30, 2026).")
    add("- National Hurricane Center. HURDAT2 (1851–2025) and GIS best track for AL092026.")
    add("- Federal Communications Commission. Broadband Data Collection, National Broadband Map public data, Provider "
        "Summary by Geography Type (releases of June 30, 2022, 2023, 2024 and 2026); Public Data API specification, "
        "revision 1.7 (June 8, 2026).")
    add("- CDC/ATSDR Social Vulnerability Index 2022; U.S. Census Bureau, ACS 5-year 2022, 2020 Gazetteer and 2022 "
        "cartographic boundary file (counties, 1:500,000); FEMA OpenFEMA Disaster Declarations Summaries v2.")
    add("## If this were your data\n\nThe same approach turns scattered public status reports into a checked panel and "
        "answers how much went dark, how fast it came back, and what moved with it, with the uncertainty and the limits "
        "stated next to each number.\n")
    return "\n".join(L)


def work_summary(r: dict) -> str:
    h4 = r["chapter_4"]["headlines"]
    t50, t90 = h4["median_time_to_50pct_restored"], h4["n_storms_reaching_90pct_restored"]
    return (f"Cell-site outages and recovery in {r['chapter_1']['headlines']['n_storms']['value']} Gulf and Southeast "
            f"hurricanes, 2017–2026: half the sites out at the peak were back within a median of {f1(t50['value'], 0)} "
            f"days, only {t90['value']} of {t90['n']} storms with a report after their peak reach 90% before the FCC's "
            f"reports end, and cell outages tend to rise and fall with power outages." + v2_work_line(r))


def v2_work_line(r: dict) -> str:
    """The Work page's version 2 line, generated from results.json."""
    if "v2_1_public_record_misses" not in r:
        return ""
    h = r["v2_1_public_record_misses"]["headlines"]
    return (f" Version 2 adds that in all {h['n_storms']} storms the FCC's last public report still showed cell sites "
            f"out: {h['sites_out_at_last_reports_headline']['value']:,.0f} in total.")


def update_work_entry(r: dict, path: Path = WORK_YAML) -> None:
    """Regenerate this page's summary line in the site's Work list (numbers from results.json, never typed)."""
    lines = path.read_text(encoding="utf-8").split("\n")
    at = [i for i, ln in enumerate(lines) if ln.strip() == f'url: "{WORK_URL}"']
    if len(at) != 1:
        raise SystemExit(f"work.yaml: expected one entry with url {WORK_URL}, found {len(at)}")
    j = next(i for i in range(at[0], min(at[0] + 6, len(lines))) if lines[i].lstrip().startswith("summary:"))
    indent = lines[j][:len(lines[j]) - len(lines[j].lstrip())]
    lines[j] = f"{indent}summary: {json.dumps(work_summary(r), ensure_ascii=False)}"
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _yaml(meta: dict) -> str:
    """Front matter as YAML with JSON-quoted scalars (YAML reads JSON strings); no YAML library needed."""
    def scalar(v):
        return json.dumps(v, ensure_ascii=False)
    out = []
    for k, v in meta.items():
        if isinstance(v, list):
            out.append(f"{k}:")
            for item in v:
                for i, (kk, vv) in enumerate(item.items()):
                    out.append(f"  {'- ' if i == 0 else '  '}{kk}: {scalar(vv)}")  # lists and dicts as JSON flow
        else:
            out.append(f"{k}: {scalar(v)}")
    return "\n".join(out) + "\n"


def front_matter(r: dict, figs: list) -> str:
    t50 = r["chapter_4"]["headlines"]["median_time_to_50pct_restored"]
    meta = {
        "draft": DRAFT, "title": "When the Network Goes Dark", "date": DATE, "updated": UPDATED,
        "summary": (f"Cell-site outages and recovery in {r['chapter_1']['headlines']['n_storms']['value']} Gulf and Southeast "
                    f"hurricanes, 2017–2026, from FCC reports: half the sites out at the peak were back within a median "
                    f"of {f1(t50['value'], 0)} days, the reports often end before 90% is back, and cell outages tend to rise and fall "
                    f"with power outages."),
        "method": ("County-level FCC DIRS cell-site tables, parsed, checked against their printed totals and a second "
                   "reading of each PDF, and joined to EAGLE-I power outages, NHC tracks and CDC/ATSDR SVI (OpenFEMA "
                   "declarations are kept in the published panel as context; no result uses them). Descriptive storm "
                   "comparisons with county-bootstrap intervals; an exposure model checked for calibration on held-out "
                   "storms; a discrete-time hazard for waiting time. The analysis plan was committed on November 22, "
                   "2026, in the project's private version-controlled repository (commit 9fc17a4), before any recovery "
                   "outcome was computed; the plan file as committed is published in the data repository with its "
                   "SHA-256. It is not blind to some figures, which are listed below with every deviation. "
                   "Associations, not causes."),
        "data_sources": [
            {"name": "FCC Broadband Data Collection, National Broadband Map public data (provider counts, chapter 13)",
             "url": "https://broadbandmap.fcc.gov/data-download"},
            {"name": "FCC Disaster Information Reporting System, Communications Status Reports (2017–2026)",
             "url": "https://www.fcc.gov/disaster-information-reporting-system-dirs-0"},
            {"name": "ORNL/DOE EAGLE-I recorded electricity outages, 2014–2025 (figshare v4)",
             "url": f"https://doi.org/{EAGLEI_DOIS[1]}"},
            {"name": "NOAA National Hurricane Center, HURDAT2 and GIS best track", "url": "https://www.nhc.noaa.gov/data/"},
            {"name": "CDC/ATSDR Social Vulnerability Index 2022",
             "url": "https://www.atsdr.cdc.gov/place-health/php/svi/svi-data-documentation-download.html"},
            {"name": "FEMA OpenFEMA Disaster Declarations Summaries v2",
             "url": "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"},
            {"name": "U.S. Census Bureau, ACS 5-year 2022 and 2020 county Gazetteer", "url": "https://api.census.gov"},
            {"name": "U.S. Census Bureau, 2022 cartographic boundary file, counties 1:500,000 (Isaias map)",
             "url": boundary_download()["url"]},
        ],
        "download": f"/static/data/{PANEL_PUBLIC.name}",
        "figures": figs,
    }
    return "---\n" + _yaml(meta) + "---\n"


# ---------------------------------------------------------------- snapshot --

def copy_snapshot(snapshot: Path = SNAPSHOT) -> list:
    """Code, tests, manifests, docs and results; never raw data, interim files, .env or the prompts."""
    copied = []
    snapshot.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    for d in SNAPSHOT_DIRS:
        if (snapshot / d).exists():
            shutil.rmtree(snapshot / d)
        shutil.copytree(ROOT / d, snapshot / d, ignore=ignore)
        copied.append(d)
    (snapshot / "docs").mkdir(exist_ok=True)
    for f in SNAPSHOT_DOCS:
        shutil.copyfile(ROOT / "docs" / f, snapshot / "docs" / f)
    (snapshot / "output").mkdir(exist_ok=True)
    for f in SNAPSHOT_RESULTS:
        shutil.copyfile(OUTPUT / f, snapshot / "output" / f)
    (snapshot / "data" / "processed").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROCESSED / "dirs_county_day.csv", snapshot / "data" / "processed" / "dirs_county_day.csv")
    shutil.copyfile(ROOT / "requirements.txt", snapshot / "requirements.txt")
    copy_validation_summary(snapshot)
    (snapshot / "README.md").write_text(SNAPSHOT_README, encoding="utf-8", newline="\n")
    (snapshot / "DATA_LICENSE.md").write_text(DATA_LICENSE, encoding="utf-8", newline="\n")
    return copied


SNAPSHOT_README = """# When the Network Goes Dark (code)

Gulf and Southeast hurricanes, 2017–2026: how much of the cell network goes dark, how fast it comes back, and
what moves with it, from FCC DIRS county reports and other public data. Demonstration on public data. Not client
work. Write-up: thresholddatasciences.com/analysis/when-the-network-goes-dark/

Every number on the page is in `output/results.json`, produced by `src/10_analysis.py`. Read
`docs/analysis_plan.md` first (committed before any outcome was computed) and `docs/decisions.md` (every decision
and deviation, dated).

```
src/            numbered steps 01-11 and their helpers
tests/          pytest -q (two tests skip without the raw data)
manifest/       report list, exception lists, downloads.csv (URL and SHA-256 of every download)
docs/           analysis plan, decision log, data sources, literature
output/         results.json, validation_dirs.csv, validation_summary.csv, excluded_reports.csv
data/processed/ dirs_county_day.csv: the cleaned county-report panel (CC BY 4.0; see DATA_LICENSE.md)
```

Raw downloads are not included. Run order: `src/01_check_manifest.py` to `src/10_analysis.py` (see each
docstring). EAGLE-I's year files (about 9 GB) are read from the folder in the `EAGLEI_RAW_DIR` environment
variable. The Census key goes in a git-ignored `.env` as `CENSUS_API_KEY=...`.
"""

DATA_LICENSE = """# Data license

`data/processed/dirs_county_day.csv` (the cleaned FCC DIRS county-report panel) is released under the Creative
Commons Attribution 4.0 International license (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/.
Attribute: Timothy D. Spivey, Threshold Data Sciences, "When the Network Goes Dark" (2026). The source reports are
public FCC documents. The code in this folder is MIT-licensed (see the LICENSE file of the demos folder).
"""


def main():
    r = json.loads((OUTPUT / "results.json").read_text(encoding="utf-8"))
    for i in range(1, 10):
        if f"chapter_{i}" not in r:
            raise SystemExit(f"results.json has no chapter_{i}: run step 10 first")
    rows = figure_rows(r)
    write_figure_csvs(rows)
    verified = verify_figure_csvs(rows)
    figs = figures_front_matter(verified, r)
    decisions = (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "analysis_plan.md").read_text(encoding="utf-8")
    panel_public = pd.read_csv(PROCESSED / "dirs_county_day.csv", dtype={"fips": str}, keep_default_na=False,
                               na_values=[""])
    panel_public["time_flag"] = panel_public.time_flag.fillna("")
    lookup = lookup_data(r, panel_public)
    write_lookup(lookup)
    if not verify_lookup(r, panel_public):
        raise SystemExit("county lookup data does not match the published panel")
    mdata = map_data(r, panel_public)
    write_json(mdata, MAP_JSON)
    if not verify_map(r, panel_public):
        raise SystemExit("map data does not match the published panel")
    if not MAP_TOPO.exists():  # geometry depends only on the boundary file; rebuilt when removed
        write_json(map_topology(), MAP_TOPO)
    body = (build_page(r, after_opening=map_section(mdata)) + "\n" + v2_sections(r) + "\n" + lookup_section(lookup)
            + "\n"
            + methods_section(r, decisions, plan, pd.read_csv(OUTPUT / "validation_dirs.csv"),
                                                  pd.read_csv(OUTPUT / "excluded_reports.csv", keep_default_na=False)))
    page = front_matter(r, figs) + "\n" + body + "\n"
    if "claude" in page.lower():
        raise SystemExit("the page names the coding assistant; reword it (see neutral())")
    PAGE.write_text(page, encoding="utf-8", newline="\n")
    PANEL_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROCESSED / "dirs_county_day.csv", PANEL_PUBLIC)
    copied = copy_snapshot()
    update_work_entry(r)
    print(f"page: {PAGE.relative_to(SITE)} (draft: {str(DRAFT).lower()}); work.yaml summary regenerated")
    print("figures verified:", verified)
    print("snapshot:", SNAPSHOT.relative_to(SITE), copied)


if __name__ == "__main__":
    main()
