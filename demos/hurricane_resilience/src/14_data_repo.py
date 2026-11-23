"""Step 14 (Phase C): assemble the public data repository, when-the-network-goes-dark-data.

Usage: python src/14_data_repo.py [TARGET]   (default: ../../when-the-network-goes-dark-data next to threshold-site)

Copies only what may be published:
  data/input/     FCC DIRS reports (PDF and text), FCC notices, the two FCC orders cited, Census, ACS, CDC/ATSDR SVI,
                  OpenFEMA pages, NHC files, EAGLE-I's filtered extract plus MCC.csv and coverage_history.csv (never a
                  year file), and the BDC county provider counts (counts only; never a raw BDC file or provider ID).
                  INPUTS.csv gives each file's source, URL, retrieval time and SHA-256.
  data/analysis/  the published panel, the storm table and results.json (what the page shows).
  code/           the pipeline (src/), its hand-made tables (manifest/) and tests, with a config.py that reads
                  data/input and writes build/.
  docs/           the analysis plan as committed (with its SHA-256), the addendum, the decision log, sources notes.
Writes README.md, SOURCES.md, CITATION.cff, CHANGELOG.md, DEVIATIONS.md, AI_ASSISTANCE.md, LICENSE, LICENSE-DATA.md,
datapackage.json and CODEBOOK.md (generated from datapackage.json), run_all.py and requirements.txt.
Never copies .env, .venv, data/interim, data/raw/bdc, the EAGLE-I year files or anything else not listed here.
"""
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

from config import (BDC_COUNTS, BDC_COUNTS_META, DOWNLOADS_LOG, EAGLEI_EXTRACT, EAGLEI_RAW_DIR, OUTPUT, PROCESSED,
                    RAW, REGIMES, ROOT)

VERSION = "2.0.0"
RELEASE_DATE = "2026-11-23"
REPO_NAME = "when-the-network-goes-dark-data"
TITLE = "When the Network Goes Dark: Gulf Coast cell-site outages in hurricanes, 2017-2026 (data and code)"
AUTHOR = {"family": "Spivey", "given": "Timothy D.", "orcid": "0009-0009-8990-4308"}
PAGE_URL = "https://thresholddatasciences.com/analysis/when-the-network-goes-dark/"
PLAN_COMMIT = "9fc17a4"
PLAN_FILE = "docs/analysis_plan.md"
STUDY_FIPS = {"48", "22", "28", "01", "12", "13", "45", "37", "47", "51"}

# data/input subfolder -> (source label, files): every published input, by name
INPUT_DIRS = {
    "dirs": "FCC DIRS Communications Status Reports",
    "notices": "FCC DIRS activation and area-change notices",
    "census": "U.S. Census Bureau",
    "acs": "U.S. Census Bureau, ACS 5-year 2022 (Census Data API)",
    "svi": "CDC/ATSDR Social Vulnerability Index 2022",
    "fema": "OpenFEMA Disaster Declarations Summaries v2",
}
NHC_FILES = ["hurdat2-1851-2025-092326.txt", "al092026_best_track.zip"]
RULE_FILES = ["FCC-22-50A1_Rcd.pdf", "FCC-26-34A1.txt"]
EAGLEI_FILES = ["MCC.csv", "coverage_history.csv"]  # unmodified EAGLE-I files; the year files are never copied
BDC_LISTINGS = ["storm_releases.json", "provider_summary_files.csv"]
STORM_PAGE_FILES = ["fcc_storm_documents.csv", "fcc_storm_documents_supplement.csv", "README_fcc_storm_documents.md"]

NEVER = (".env", ".venv", "__pycache__", "bdc_provider_county", "eaglei_outages_", "bdc_us_provider_summary",
         "listAvailabilityData", ".pytest_cache")
MAX_BYTES = 50 * 1024 * 1024

# --------------------------------------------------------------------------------------------------- codebook --
PERIODS = "; ".join(f"P{i}: {name} ({start} to {end if end < '2099' else 'present'})"
                    for i, (name, start, end) in enumerate(REGIMES))
SITE_LIMIT = ("Cell sites as reported by providers to the FCC; a site out is not a count of people without service "
              "(the FCC's caveat).")
PANEL_FIELDS = [
    # name, type, description, unit, limitation
    ("storm_key", "string", "Storm key: NHC ID and DIRS activation date, joined by an underscore.", "",
     "Names repeat across years (Isaias 2020 and 2026); always join on this key, not the name."),
    ("nhc_id", "string", "National Hurricane Center storm ID (basin, number, year).", "", ""),
    ("storm", "string", "Storm name.", "", "Not unique across years."),
    ("dirs_activation_date", "date", "Date the FCC activated DIRS for the storm.", "", ""),
    ("rule_period", "string", f"FCC rule period by activation date. {PERIODS}.", "",
     "Descriptive grouping only; periods differ in storms, hazards and filers."),
    ("doc_id", "string", "FCC EDOCS document number of the report.", "", ""),
    ("report_date", "date", "Date of the report.", "", ""),
    ("as_of_utc", "datetime", "The report's stated as-of time, in UTC.", "UTC",
     "Where the report prints none, set to 12:00 Eastern on the report date (as_of_imputed)."),
    ("as_of_imputed", "boolean", "True when as_of_utc was set to 12:00 Eastern because the report prints no time.", "",
     ""),
    ("report_status", "string", "Validation status of the report (step 4): ok, flagged (a check raised a note) or "
     "known_fcc_inconsistency (a stated total the FCC's own rows do not sum to, listed in "
     "code/manifest/known_fcc_inconsistencies.csv).", "", "Excluded reports are not in the file."),
    ("state", "string", "State, as printed.", "", "Ten study states only."),
    ("county", "string", "County as printed by the FCC (upper case).", "",
     "Spellings vary between reports; use fips."),
    ("fips", "string", "Five-digit county FIPS code (with leading zero).", "",
     "Mapped from the printed name with code/manifest/fips_exceptions.csv."),
    ("sites_served", "number", "Cell sites served in the county, as reported.", "sites",
     "The denominator differs by storm and report; compare percentages with care. " + SITE_LIMIT),
    ("sites_out", "number", "Cell sites out of service in the county, as reported.", "sites", SITE_LIMIT),
    ("pct_out", "number", "Percent of sites out, as printed (computed from the two counts where not printed).",
     "percent", "Where pct_printed is false the value is computed, not printed."),
    ("pct_printed", "boolean", "True when the report printed the percent column.", "", ""),
    ("out_damage", "number", "Sites out due to damage, as reported.", "sites",
     "Blank where the report has no cause columns. Causes can overlap (see out_overattributed)."),
    ("out_transport", "number", "Sites out due to transport (backhaul), as reported.", "sites",
     "Blank where the report has no cause columns."),
    ("out_power", "number", "Sites out due to power, as reported.", "sites",
     "Blank where the report has no cause columns."),
    ("on_backup_power", "number", "Sites operating on backup power, as reported.", "sites",
     "Blank where the report has no such column. Not a measure of sites about to fail."),
    ("out_unattributed", "number", "Sites out with no cause given: sites_out minus the three causes, never below 0.",
     "sites", "Blank where the report has no cause columns. Kept apart from out_overattributed; never net them."),
    ("out_overattributed", "number", "Causes in excess of sites out (sites counted under more than one cause).",
     "sites", "Blank where the report has no cause columns. May print as -0.0, which equals 0."),
    ("area_status", "string", "Whether the county is in the FCC's notice area on the report date: inside, "
     "inside_spelling_variant, outside_notice_area or table_not_in_list.", "",
     "From the FCC's notices (code/manifest/reporting_areas.csv)."),
    ("fema_declared", "boolean", "True if OpenFEMA lists a declaration for the storm covering the county.", "",
     "Context for reuse only; no result uses it. This product uses the Federal Emergency Management Agency's "
     "OpenFEMA API, but is not endorsed by FEMA."),
    ("time_flag", "string", "Blank, or pre_onset_likely_marco for Laura's Aug 25, 2020 report (the FCC's combined "
     "Marco and Laura report), which is kept but left out of every time-based result.", "", ""),
]
STORM_FIELDS = [
    ("nhc_id", "string", "National Hurricane Center storm ID.", "", ""),
    ("dirs_activation_date", "date", "Date the FCC activated DIRS.", "", ""),
    ("storm_key", "string", "NHC ID and DIRS activation date.", "", ""),
    ("storm", "string", "Storm name.", "", "Not unique across years."),
    ("rule_period", "string", f"FCC rule period by activation date. {PERIODS}.", "", "Blank for storms not in the panel."),
    ("landfall_utc", "datetime", "Day 0: the first time the storm's 34-kt wind radii reach a study-state county "
     "(fallback: first study-state landfall at tropical-storm strength or above).", "UTC",
     "Defined from NHC best-track radii; see docs/decisions.md (2026-11-23)."),
    ("landfall_source", "string", "Which rule set day 0.", "", ""),
    ("previous_landfall_utc", "datetime", "Day 0 under the original rule (kept for chapter 8's comparison).", "UTC",
     "Superseded; not used for the main results."),
    ("interim_landfall_utc", "datetime", "Day 0 under the first 2026-11-23 rule (kept for comparison).", "UTC",
     "Superseded; not used for the main results."),
    ("n_reports", "integer", "Reports in the panel.", "reports", "Blank for storms not in the panel."),
    ("n_counties", "integer", "Counties in the panel.", "counties", "Blank for storms not in the panel."),
    ("first_report", "date", "First report date in the panel.", "", ""),
    ("last_report", "date", "Last report date in the panel.", "", "The FCC's last public report, not the end of outages."),
    ("excluded_reports", "string", "Reports left out, with date and reason.", "", ""),
    ("in_panel", "boolean", "True if the storm has at least one report in the panel.", "", ""),
]
BDC_FIELDS = [
    ("release", "date", "FCC Broadband Data Collection release (as-of date).", "", ""),
    ("fips", "string", "Five-digit county FIPS code.", "", "Study-state counties only."),
    ("mobile_half", "integer", "Mobile broadband providers reporting coverage of at least half of the county.",
     "providers", "Reported coverage, not which networks were out; providers are never named."),
    ("mobile_any", "integer", "Mobile broadband providers reporting any coverage in the county.", "providers",
     "Reported coverage, not which networks were out."),
    ("fixed_any_excl_near_universal", "integer", "Fixed providers with any residential service, near-universal "
     "providers excluded.", "providers", "Near-universal: service in at least 95% of study-state counties."),
    ("fixed_any", "integer", "Fixed providers with any residential service.", "providers",
     "Includes near-universal (likely satellite or national fixed-wireless) providers."),
    ("fixed_half", "integer", "Fixed providers serving at least half of residential locations.", "providers", ""),
    ("fixed_half_excl_near_universal", "integer", "As fixed_half, near-universal providers excluded.", "providers", ""),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)


# -------------------------------------------------------------------------------------------------- inputs --
def copy_inputs(T: Path) -> pd.DataFrame:
    log = pd.read_csv(DOWNLOADS_LOG, dtype=str, keep_default_na=False)
    log = log[log.status != "exists"].drop_duplicates("path", keep="last").set_index("path")
    rows, inp = [], T / "data" / "input"

    def add(src: Path, rel: str, source: str, logged: str, note: str = ""):
        copy(src, inp / rel)
        hit = log.loc[logged] if logged in log.index else None
        status = "" if hit is None else hit.status
        if status.startswith("not found"):
            note = ("The FCC served a 'not found' page for this .txt URL; the saved page is kept because step 3 reads "
                    "the .txt first and then falls back to the PDF, which holds the report.")
        rows.append({"path": f"data/input/{rel}", "source": source,
                     "doc_id": src.stem if rel.startswith(("dirs/", "notices/", "rules/")) else "",
                     "url": "" if hit is None else hit.url, "retrieved_utc": "" if hit is None else hit["when"],
                     "download_status": status, "sha256": sha256(inp / rel), "bytes": (inp / rel).stat().st_size,
                     "note": note})

    for sub, source in INPUT_DIRS.items():
        for p in sorted((RAW / sub).iterdir()):
            if p.is_file() and not p.name.startswith("."):
                add(p, f"{sub}/{p.name}", source, f"data/raw/{sub}/{p.name}")
    for name in NHC_FILES:
        add(RAW / "nhc" / name, f"nhc/{name}", "NOAA National Hurricane Center", f"data/raw/nhc/{name}")
    for name in RULE_FILES:
        add(RAW / "rules" / name, f"rules/{name}", "FCC orders (cited for rule dates)", f"data/raw/rules/{name}")
    for name in STORM_PAGE_FILES:
        add(RAW / "storm_pages" / name, f"storm_pages/{name}", "FCC storm pages (document lists)",
            f"data/raw/storm_pages/{name}", "Compiled by reading the FCC storm pages (www.fcc.gov/<storm>) on "
            "2026-11-22; see README_fcc_storm_documents.md. No single URL.")
    for name in EAGLEI_FILES:
        add(EAGLEI_RAW_DIR / name, f"eaglei/{name}", "ORNL/DOE EAGLE-I (unmodified)", f"$EAGLEI_RAW_DIR/{name}")
    add(EAGLEI_EXTRACT, "eaglei/eaglei_extract.parquet", "ORNL/DOE EAGLE-I (modified)", "",
        "Derived by code/src/06_eaglei.py from the 2017-2024 year files: study counties and storm windows only "
        "(21 days before activation to 21 days after deactivation). Modified: aggregated to county at report times.")
    for name in BDC_LISTINGS:
        add(RAW / "bdc" / "listings" / name, f"bdc/listings/{name}", "FCC Broadband Data Collection (file list)",
            f"data/raw/bdc/listings/{name}", "Written by code/src/06c_bdc_list.py from the FCC's file listings: "
            "the files used and each storm's release (the latest on or before its day 0).")
    add(BDC_COUNTS, "bdc/bdc_county_provider_counts.csv", "FCC Broadband Data Collection (derived counts)", "",
        "Derived by code/src/06e_bdc_counties.py and 06f_bdc_counts.py: provider counts by county and release; "
        "no provider ID or name.")
    add(BDC_COUNTS_META, "bdc/bdc_county_provider_counts_meta.json", "FCC Broadband Data Collection (derived)", "",
        "The number of near-universal fixed providers and the measure definitions.")
    idx = pd.DataFrame(rows)
    idx.to_csv(inp / "INPUTS.csv", index=False, lineterminator="\n")
    return idx


# ------------------------------------------------------------------------------------------------ analysis --
def copy_analysis(T: Path) -> None:
    a = T / "data" / "analysis"
    copy(PROCESSED / "dirs_county_day.csv", a / "dirs_county_day.csv")
    pd.read_parquet(PROCESSED / "storms.parquet").to_csv(a / "storms.csv", index=False, lineterminator="\n")
    copy(OUTPUT / "results.json", a / "results.json")
    for f in ("validation_dirs.csv", "validation_summary.csv", "excluded_reports.csv", "area_status_counts.csv"):
        copy(OUTPUT / f, a / "validation" / f)


# -------------------------------------------------------------------------------------------------- code --
PUBLIC_CONFIG_PATHS = '''"""Paths and constants shared by all scripts (public data repository).

The constants below the path block are the private project's, unchanged. Only the paths differ: inputs are read from
data/input and every output goes to build/ (set WTNGD_BUILD to use another folder). tests/test_reproduction.py
compares build/ with the published files in data/analysis.
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / "code"
RAW = REPO / "data" / "input"
BUILD = Path(os.environ.get("WTNGD_BUILD", str(REPO / "build")))
INTERIM = BUILD / "interim"
PROCESSED = BUILD / "processed"
OUTPUT = BUILD / "output"
DOCS = REPO / "docs"
MANIFEST = ROOT / "manifest" / "dirs_reports.csv"
DOWNLOADS_LOG = ROOT / "manifest" / "downloads.csv"  # every download; a rerun adds nothing (files exist)
# MCC.csv and coverage_history.csv only (the year files are not redistributed); EAGLEI_RAW_DIR overrides it
EAGLEI_RAW_DIR = Path(os.environ.get("EAGLEI_RAW_DIR", str(RAW / "eaglei")))
EAGLEI_EXTRACT = RAW / "eaglei" / "eaglei_extract.parquet"
BDC_COUNTS = RAW / "bdc" / "bdc_county_provider_counts.csv"
BDC_COUNTS_META = RAW / "bdc" / "bdc_county_provider_counts_meta.json"
for _d in (INTERIM, PROCESSED, OUTPUT):
    _d.mkdir(parents=True, exist_ok=True)
'''


def public_config() -> str:
    s = (ROOT / "src" / "config.py").read_text(encoding="utf-8")
    start = s.index("\n\ndef census_api_key")
    return PUBLIC_CONFIG_PATHS + s[start:]


def copy_code(T: Path) -> None:
    c = T / "code"
    for p in sorted((ROOT / "src").glob("*.py")):
        if p.name == "config.py":
            write(c / "src" / "config.py", public_config())
        else:
            copy(p, c / "src" / p.name)
    hashes = []
    for p in sorted((ROOT / "manifest").iterdir()):
        if p.is_file():
            copy(p, c / "manifest" / p.name)
            hashes.append(f"{sha256(p)}  {p.name}")
    # step 2b rewrites some of these tables; the reproduction test checks they come out unchanged
    write(c / "manifest.sha256", "\n".join(hashes) + "\n")
    for p in sorted((ROOT / "tests").rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            copy(p, c / "tests" / p.relative_to(ROOT / "tests"))


# -------------------------------------------------------------------------------------------------- docs --
def plan_as_committed(T: Path) -> dict:
    blob = subprocess.run(["git", "-C", str(ROOT), "show", f"{PLAN_COMMIT}:{PLAN_FILE}"], capture_output=True,
                          check=True).stdout
    when = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%ad", "--date=iso-strict", PLAN_COMMIT],
                          capture_output=True, text=True, check=True).stdout.strip()
    blob_id = subprocess.run(["git", "-C", str(ROOT), "rev-parse", f"{PLAN_COMMIT}:{PLAN_FILE}"], capture_output=True,
                             text=True, check=True).stdout.strip()
    dest = T / "docs" / f"analysis_plan_as_committed_{PLAN_COMMIT}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
    info = {"file": dest.name, "commit": PLAN_COMMIT, "committed": when, "git_blob": blob_id,
            "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}
    write(T / "docs" / "analysis_plan_as_committed.sha256",
          f"{info['sha256']}  {dest.name}\n")
    return info


def copy_docs(T: Path) -> None:
    for name in ("analysis_plan.md", "analysis_plan_addendum_v2.md", "decisions.md", "data_sources.md",
                 "literature.md"):
        copy(ROOT / "docs" / name, T / "docs" / name)


def deviations_md(T: Path) -> None:
    step11 = importlib.import_module("11_build_page")
    text = (ROOT / "docs" / "decisions.md").read_text(encoding="utf-8")
    lines = ["# Deviations from the analysis plan", "",
             "Generated by `code/src/14_data_repo.py` from `docs/decisions.md`: every entry marked DEVIATION, then every "
             "entry marked CORRECTION, in the log's order and wording. The full log is `docs/decisions.md`.", "",
             "## Deviations", "", "| Date | Deviation | Reason |", "|---|---|---|"]
    lines += [f"| {d} | {w} | {y} |" for d, w, y in step11.deviations(text)]
    lines += ["", "## Corrections", "", "| Date | Correction | Reason |", "|---|---|---|"]
    lines += [f"| {d} | {w} | {y} |" for d, w, y in step11.corrections(text)]
    write(T / "DEVIATIONS.md", "\n".join(lines) + "\n")


# --------------------------------------------------------------------------------------------- data package --
def schema(fields, primary_key, missing=("",)) -> dict:
    out = []
    for name, typ, desc, unit, limit in fields:
        f = {"name": name, "type": typ, "description": desc}
        if unit:
            f["unit"] = unit
        if limit:
            f["limitations"] = limit
        if typ == "string" and name == "fips":
            f["constraints"] = {"pattern": "^[0-9]{5}$", "required": True}
        if typ == "boolean":
            f["trueValues"], f["falseValues"] = ["True"], ["False"]
        if typ == "datetime":
            f["format"] = "any"
        out.append(f)
    return {"fields": out, "primaryKey": primary_key, "missingValues": list(missing)}


def datapackage(T: Path, plan: dict) -> dict:
    a = T / "data" / "analysis"
    panel_cols = list(pd.read_csv(a / "dirs_county_day.csv", nrows=0).columns)
    storm_cols = list(pd.read_csv(a / "storms.csv", nrows=0).columns)
    bdc_cols = list(pd.read_csv(T / "data" / "input" / "bdc" / "bdc_county_provider_counts.csv", nrows=0).columns)
    dates = pd.read_csv(a / "dirs_county_day.csv", usecols=["report_date"]).report_date
    for cols, fields, name in ((panel_cols, PANEL_FIELDS, "panel"), (storm_cols, STORM_FIELDS, "storms"),
                               (bdc_cols, BDC_FIELDS, "bdc")):
        if cols != [f[0] for f in fields]:
            raise SystemExit(f"{name}: documented fields {[f[0] for f in fields]} differ from the file's {cols}")
    pkg = {
        "profile": "tabular-data-package", "name": REPO_NAME, "title": TITLE, "version": VERSION,
        "created": RELEASE_DATE, "homepage": PAGE_URL,
        "description": ("County-by-report panel of FCC Disaster Information Reporting System (DIRS) cell-site outages "
                        "for 21 Atlantic hurricanes and tropical storms in ten Gulf and Southeast states, 2017-2026, "
                        "checked against each report's printed totals, with the inputs and code that rebuild it."),
        "keywords": ["hurricanes", "cell sites", "telecommunications outages", "FCC DIRS", "disaster resilience",
                     "power outages", "EAGLE-I", "Gulf Coast"],
        "contributors": [{"title": "Timothy D. Spivey", "role": "author",
                          "path": f"https://orcid.org/{AUTHOR['orcid']}"}],
        "licenses": [{"name": "CC-BY-4.0", "title": "Creative Commons Attribution 4.0 International (data)",
                      "path": "https://creativecommons.org/licenses/by/4.0/"},
                     {"name": "MIT", "title": "MIT License (code)", "path": "https://opensource.org/license/mit"}],
        "temporalCoverage": f"{dates.min()}/{dates.max()}", "spatialCoverage": "Texas, Louisiana, Mississippi, Alabama, "
        "Florida, Georgia, South Carolina, North Carolina, Tennessee, Virginia (United States), county level",
        "resources": [
            {"name": "dirs_county_day", "path": "data/analysis/dirs_county_day.csv", "profile": "tabular-data-resource",
             "format": "csv", "mediatype": "text/csv", "encoding": "utf-8",
             "title": "FCC DIRS cell-site outages by county and report",
             "description": "One row per county per FCC DIRS report in use (167 reports, 21 storms).",
             "schema": schema(PANEL_FIELDS, ["storm_key", "doc_id", "fips"])},
            {"name": "storms", "path": "data/analysis/storms.csv", "profile": "tabular-data-resource",
             "format": "csv", "mediatype": "text/csv", "encoding": "utf-8", "title": "Storm table",
             "description": "One row per storm with a DIRS activation in scope, including storms with no usable report.",
             "schema": schema(STORM_FIELDS, ["storm_key"])},
            {"name": "bdc_county_provider_counts", "path": "data/input/bdc/bdc_county_provider_counts.csv",
             "profile": "tabular-data-resource", "format": "csv", "mediatype": "text/csv", "encoding": "utf-8",
             "title": "Broadband provider counts by county and BDC release (counts only)",
             "description": "Derived from FCC Broadband Data Collection public data; no provider is named or identified.",
             "schema": schema(BDC_FIELDS, ["release", "fips"])},
            {"name": "results", "path": "data/analysis/results.json", "format": "json", "mediatype": "application/json",
             "title": "Every number on the page",
             "description": "Chapter results with intervals, n and method, written by code/src/10_analysis.py "
                            "(chapters 1-9) and 12_v2_analysis.py (chapters 10-13)."},
            {"name": "analysis_plan_as_committed", "path": f"docs/{plan['file']}", "format": "md",
             "mediatype": "text/markdown", "title": "Analysis plan as committed",
             "description": f"Committed {plan['committed']} (commit {plan['commit']}); SHA-256 {plan['sha256']}.",
             "hash": f"sha256:{plan['sha256']}"},
        ],
    }
    for r in pkg["resources"]:
        if "hash" not in r:
            r["hash"] = "sha256:" + sha256(T / r["path"])
        r["bytes"] = (T / r["path"]).stat().st_size
    write(T / "datapackage.json", json.dumps(pkg, indent=2, ensure_ascii=False) + "\n")
    return pkg


def codebook_md(T: Path, pkg: dict) -> None:
    L = ["# Codebook", "", "Generated from `datapackage.json` by `code/src/14_data_repo.py`; edit the package, not this "
         "file. Missing values are empty cells. Every variable's limitation is in the last column.", ""]
    for r in pkg["resources"]:
        if "schema" not in r:
            continue
        s = r["schema"]
        L += [f"## `{r['path']}`", "", r["description"], "",
              f"Primary key: {', '.join('`' + k + '`' for k in s['primaryKey'])}. Missing value code: empty cell.", "",
              "| Variable | Type | Unit | Description | Limitations |", "|---|---|---|---|---|"]
        for f in s["fields"]:
            L.append(f"| `{f['name']}` | {f['type']} | {f.get('unit', '')} | {f['description']} | "
                     f"{f.get('limitations', '')} |")
        L.append("")
    L += ["## `data/analysis/results.json`", "",
          "Nested JSON, one key per chapter (`chapter_1` to `chapter_9`, then `v2_1_public_record_misses`, "
          "`v2_2_backup_power`, `v2_3_power_cell_timing`, `v2_5_groups`, `v2_5_network_redundancy`). Each number is "
          "stored with its interval (`lo`, `hi`), `n`, `unit` and `method` where it has them. The README maps each "
          "page section and figure to its key and script.", ""]
    write(T / "CODEBOOK.md", "\n".join(L))


# ------------------------------------------------------------------------------------------- text files --
def citation_cff(T: Path) -> None:
    write(T / "CITATION.cff", f"""cff-version: 1.2.0
message: "If you use these data or code, please cite them as below."
type: dataset
title: "{TITLE}"
version: {VERSION}
date-released: {RELEASE_DATE}
license: CC-BY-4.0
authors:
  - family-names: "{AUTHOR['family']}"
    given-names: "{AUTHOR['given']}"
    orcid: "https://orcid.org/{AUTHOR['orcid']}"
url: "{PAGE_URL}"
repository-code: "https://github.com/ts2427/{REPO_NAME}"
keywords:
  - hurricanes
  - cell sites
  - telecommunications outages
  - FCC DIRS
  - disaster resilience
abstract: >-
  A county-by-report panel of FCC Disaster Information Reporting System (DIRS) cell-site outages for 21 Atlantic
  storms in ten Gulf and Southeast states, 2017-2026, checked against each report's printed totals, with the public
  inputs and the code that rebuild the panel and every number on the page "When the Network Goes Dark".
  Data are CC BY 4.0; code is MIT.
""")


def changelog(T: Path) -> None:
    write(T / "CHANGELOG.md", f"""# Changelog

This project follows [Semantic Versioning](https://semver.org/): a major version changes a published number or a
variable's meaning, a minor version adds data or variables, a patch fixes documentation or code without changing
any output.

## [{VERSION}] - {RELEASE_DATE}

First release of this repository. The analysis is version 2 of the page.

### Added
- Version 2 analyses (chapters 10-13): sites still out in the FCC's last report, sites on backup power, power vs. cell
  timing, network redundancy from FCC Broadband Data Collection provider counts; the county lookup and the map.
- Inputs with provenance (`data/input/INPUTS.csv`), `datapackage.json`, `CODEBOOK.md`, `SOURCES.md`,
  `DEVIATIONS.md`, `CITATION.cff`, and `run_all.py`, which rebuilds the panel and `results.json` from `data/input`.
- The analysis plan as committed, with its SHA-256.

### Unchanged
- Every version 1 result (chapters 1-9); a test fails if one changes.

## [1.0.0] - 2026-11-22

Version 1 of the page (chapters 1-9) and the panel, published with the page's code snapshot.
""")


def licenses(T: Path) -> None:
    write(T / "LICENSE", """MIT License

Copyright (c) 2026 Timothy D. Spivey

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit
persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
""")
    write(T / "LICENSE-DATA.md", """# Data license

The author's data in this repository (everything in `data/analysis/`, the derived files in `data/input/` marked
"derived" or "modified" in `data/input/INPUTS.csv`, `datapackage.json` and `CODEBOOK.md`) are licensed under the
Creative Commons Attribution 4.0 International license (CC BY 4.0):
https://creativecommons.org/licenses/by/4.0/ (legal code: https://creativecommons.org/licenses/by/4.0/legalcode).

Attribute: Timothy D. Spivey, "When the Network Goes Dark" data, version 2.0.0 (2026). See `CITATION.cff`.

The third-party inputs in `data/input/` keep their own terms, listed with the exact attribution for each in
`SOURCES.md`. U.S. federal government works (FCC, Census, NOAA/NHC, CDC/ATSDR, FEMA) are in the public domain in the
United States; EAGLE-I files are CC BY 4.0 from ORNL/DOE.

The code (`code/`, `run_all.py`) is under the MIT License in `LICENSE`.

---

The full legal code follows, unmodified, as published by Creative Commons at
https://creativecommons.org/licenses/by/4.0/legalcode.txt (retrieved 2026-11-23; SHA-256 in
`code/manifest/downloads.csv`).

```text
""" + (RAW / "licenses" / "cc-by-4.0-legalcode.txt").read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
          + "\n```\n")


def ai_statement(T: Path) -> None:
    write(T / "AI_ASSISTANCE.md", """# AI assistance

The code and documentation in this repository were written with the help of an AI coding assistant (Claude Code,
by Anthropic) working under the author's direction. The author set the questions, the ground rules and the analysis
plan, and made every analytical decision; who proposed and who chose each one is recorded in `docs/decisions.md`.
Every number in `data/analysis/` is generated by the code here from the public inputs in `data/input/`, and
`tests/test_reproduction.py` checks that the code reproduces the published files. The assistant had no access to
any non-public data.
""")


def sources_md(T: Path, idx: pd.DataFrame) -> None:
    def when(prefix):
        w = idx[idx.path.str.startswith(prefix) & (idx.retrieved_utc != "")].retrieved_utc
        if not len(w):
            return ""
        return (f"{w.min()[:10]}" + ("" if w.min()[:10] == w.max()[:10] else f" to {w.max()[:10]}")
                + f" (UTC; first file {w.min()[11:16]} UTC)")

    def span(prefix):
        w = idx[idx.path.str.startswith(prefix) & (idx.retrieved_utc != "")].retrieved_utc.sort_values()
        return f"{w.iloc[0]} to {w.iloc[-1]}" if len(w) else ""

    dirs = idx[idx.path.str.startswith("data/input/dirs/")]
    n_docs = dirs.doc_id.nunique()
    nhc = idx.set_index("path").loc["data/input/nhc/hurdat2-1851-2025-092326.txt"]
    eag = ", ".join(EAGLEI_FILES)
    text = f"""# Sources and attribution

Every input file, with its URL, retrieval time (UTC) and SHA-256, is listed in `data/input/INPUTS.csv`. Downloads
followed one rule: approved sources only, one request at a time at least 3 seconds apart, a generic User-Agent, and
no retry after a refusal.

## FCC Disaster Information Reporting System (DIRS)

Federal Communications Commission, Public Safety and Homeland Security Bureau. *Communications Status Report for
Areas Impacted by* [storm], {n_docs} reports, 2017-2026, each cited by its EDOCS DOC number and date in
`data/input/INPUTS.csv` and `code/manifest/dirs_reports.csv` (https://docs.fcc.gov/public/attachments/DOC-<number>.pdf
and .txt). Retrieved {when('data/input/dirs/')}. U.S. government work; public domain in the United States.
The FCC's DIRS notices (activation, area changes, deactivation) are in `data/input/notices/`.

Each report carries this caveat: "The number of cell site outages in a specific area does not necessarily correspond
to the availability of wireless service to consumers in that area."

Rules cited for dates: FCC 22-50 (Mandatory Disaster Response Initiative, adopted June 27, 2022;
`data/input/rules/FCC-22-50A1_Rcd.pdf`), compliance from May 1, 2024 per the FCC's MDRI page
(https://www.fcc.gov/node/254876, accessed November 23, 2026; the formal compliance notice was not retrieved);
FCC 24-5 and DA 25-74 (mandatory DIRS from February 20, 2025; Federal Register 2025-00495); FCC 26-34 (adopted
May 20, 2026; Federal Register 2026-13155, 91 FR 39516, June 30, 2026; `data/input/rules/FCC-26-34A1.txt`).

## FCC Broadband Data Collection (counts only)

FCC Broadband Data Collection public data (National Broadband Map, https://broadbandmap.fcc.gov/data-download) were
obtained through the FCC's Public Data API under the FCC API terms of service accepted for the account, and are used
for provider counts only; no provider is named and the files are not redistributed. What is published here is
`data/input/bdc/bdc_county_provider_counts.csv` (counts by county and release, derived by `code/src/06e_bdc_counties.py`
and `06f_bdc_counts.py`) and the list of files used (`provider_summary_files.csv`, `storm_releases.json`).

## ORNL/DOE EAGLE-I

Brelsford, C., et al. (2024). A dataset of recorded electricity outages by United States county 2014-2022.
*Scientific Data*, 11, 271. https://doi.org/10.1038/s41597-024-03095-5.
Data: figshare, https://doi.org/10.6084/m9.figshare.24237376 (version 4, published 2026-02-25), files
eaglei_outages_2017.csv to eaglei_outages_2024.csv, {eag}; licence CC BY 4.0, read from the figshare record of
version 4 on 2026-11-22 (the record that holds these file IDs; `code/manifest/eaglei_files.csv`). The 2025 release
(https://doi.org/10.13139/ORNLNCCS/3012826) was not used.
Modified: aggregated to county at report times. `data/input/eaglei/eaglei_extract.parquet` keeps only the study
counties and storm windows; `MCC.csv` and `coverage_history.csv` are unmodified. The year files are not
redistributed. Retrieved {when('data/input/eaglei/')}.

## CDC/ATSDR Social Vulnerability Index

Centers for Disease Control and Prevention/ Agency for Toxic Substances and Disease Registry/ Geospatial Research,
Analysis, and Services Program. CDC/ATSDR Social Vulnerability Index 2022 Database United States.
https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html Accessed on {when('data/input/svi/')}.

## OpenFEMA

This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not endorsed by FEMA. The Federal
Government or FEMA cannot vouch for the data or analyses derived from these data after the data have been retrieved
from the Agency's website(s).
Dataset: Disaster Declarations Summaries v2, https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries, accessed
{span('data/input/fema/')} (UTC). Used as context only (`fema_declared`); no result uses it.

## NOAA National Hurricane Center

Landsea, C. W., & Franklin, J. L. (2013). Atlantic hurricane database uncertainty and presentation of a new database
format. *Monthly Weather Review*, 141(10), 3576-3592. https://doi.org/10.1175/MWR-D-12-00254.1.
File: HURDAT2 Atlantic, `hurdat2-1851-2025-092326.txt` (1851-2025, NHC file version dated 2026-09-23 in its name),
{nhc.url}, retrieved {nhc.retrieved_utc[:10]}. Isaias 2026 (AL092026) best track from the NHC GIS archive,
`al092026_best_track.zip`. U.S. government work; public domain.

## U.S. Census Bureau

This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.
American Community Survey 5-year estimates, 2018-2022 (households, population 65 and over, broadband subscription),
county level, from api.census.gov (the key is not stored; the logged URL has it redacted). 2020 county list
(`national_county2020.txt`), 2020 Gazetteer counties and the 2022 cartographic boundary file (1:500,000) from
www2.census.gov. Retrieved {when('data/input/census/')}.

## Software on the page

D3 7.9.0 and topojson-client 3.1.0 (ISC License), used by the page's map; not part of this repository.

## Related work cited on the page

Olukola et al. (2026), arXiv:2609.10944, is used on the page only as a check on Helene; its dataset is not
redistributed here.
"""
    write(T / "SOURCES.md", text)


# ---------------------------------------------------------------------------------------------- README --
PAGE_MAP = [  # page section, figures (figure id: published CSV), results.json key, script
    ("Opening, How to read it", "", "chapter_3, chapter_4, v2_1_public_record_misses", "10_analysis.py, 12_v2_analysis.py"),
    ("Map: where cell sites were out", "storm map (hurricane-map.json)", "panel (dirs_county_day.csv)",
     "09_build_panel.py; map data written by 11_build_page.py"),
    ("1. The question and the data", "fig-coverage: hurricane-coverage-heatmap.csv", "chapter_1", "10_analysis.py"),
    ("2. Anatomy of a storm: Isaias", "fig-isaias-map: hurricane-isaias-map.csv; fig-isaias: hurricane-isaias-counties.csv",
     "chapter_2", "10_analysis.py (track: 07_nhc.py)"),
    ("3. How much goes dark", "fig-peaks: hurricane-peaks.csv", "chapter_3", "10_analysis.py"),
    ("4. How fast it comes back", "fig-curves: hurricane-recovery-curves.csv; fig-restored: hurricane-restored.csv",
     "chapter_4", "10_analysis.py"),
    ("5. Why sites go dark", "fig-causes: hurricane-causes.csv", "chapter_5", "10_analysis.py"),
    ("6. The power coupling", "fig-power-overlay: hurricane-power-overlay.csv; fig-power: hurricane-power-lags.csv",
     "chapter_6", "10_analysis.py (EAGLE-I match: 06_eaglei.py)"),
    ("7. Exposure", "fig-zone: hurricane-wind-zone.csv; fig-distance: hurricane-distance.csv; "
     "fig-calibration (methods): hurricane-calibration.csv", "chapter_7", "10_analysis.py (exposure: 07_nhc.py)"),
    ("8. Who waits longest", "fig-svi: hurricane-svi-wait.csv", "chapter_8", "10_analysis.py (SVI: 08_fema_svi_bdc.py)"),
    ("9. Did the rules help?", "", "chapter_9", "10_analysis.py"),
    ("10. What the public record misses", "", "v2_1_public_record_misses", "12_v2_analysis.py v2_1"),
    ("11. Sites on backup power", "", "v2_2_backup_power", "12_v2_analysis.py v2_2"),
    ("12. Which comes back first: power or cell service?", "", "v2_3_power_cell_timing", "12_v2_analysis.py v2_3"),
    ("13. Do counties with more mobile providers recover differently?", "",
     "v2_5_groups, v2_5_network_redundancy", "12_v2_analysis.py v2_5_groups v2_5 (counts: 06e, 06f)"),
    ("Look up a county", "county lookup (hurricane-county-lookup.json)", "panel", "11_build_page.py"),
    ("Methods, data and licenses", "validation tables", "chapter_1, validation/*.csv", "04_validate_dirs.py, 10_analysis.py"),
]
RUN_ORDER = [
    ("02b_reporting_areas.py", "", "each storm's reporting area from the FCC notices (rewrites code/manifest tables; "
                                   "the test checks they are unchanged)"),
    ("03_parse_dirs.py", "", "parse every DIRS report (text first, PDF fallback) into county rows and totals"),
    ("04_validate_dirs.py", "", "reconcile county rows with each report's printed totals; validation tables"),
    ("05_fips.py", "", "county names to FIPS"),
    ("06_eaglei.py", "", "match EAGLE-I (from the published extract) to each report's as-of time"),
    ("07_nhc.py", "", "tracks, wind radii, distance to track, day 0"),
    ("08_fema_svi_bdc.py", "", "ACS, SVI and OpenFEMA declarations (from the stored files; no request is made)"),
    ("09_build_panel.py", "", "the panel, the storm table and dirs_county_day.csv"),
    ("10_analysis.py", "3 4 5 6 7 8 9", "chapters 3-9 to results.json"),
    ("10_analysis.py", "1 2", "chapters 1 and 2 (run second so results.json keeps the published key order)"),
    ("12_v2_analysis.py", "v2_1 v2_2 v2_3 v2_5_groups v2_5", "chapters 10-13 to results.json"),
]


def readme(T: Path, idx: pd.DataFrame, plan: dict) -> None:
    def size(prefix):
        b = idx[idx.path.str.startswith(prefix)].bytes.sum()
        return f"{b / 1e6:,.1f} MB"

    avail = [
        ("FCC DIRS reports (PDF and text)", "data/input/dirs/", "FCC", "Public domain (U.S. government)", "yes",
         size("data/input/dirs/")),
        ("FCC DIRS notices", "data/input/notices/", "FCC", "Public domain", "yes", size("data/input/notices/")),
        ("FCC orders cited for dates", "data/input/rules/", "FCC", "Public domain", "yes", size("data/input/rules/")),
        ("FCC storm-page document lists", "data/input/storm_pages/", "FCC (compiled list)", "Public domain", "yes",
         size("data/input/storm_pages/")),
        ("EAGLE-I extract, MCC, coverage", "data/input/eaglei/", "ORNL/DOE", "CC BY 4.0", "yes (extract modified)",
         size("data/input/eaglei/")),
        ("EAGLE-I year files 2017-2024", "not included (8.9 GB)", "ORNL/DOE via figshare", "CC BY 4.0",
         "no: download with code/src/06a_download_eaglei.py", "8.9 GB"),
        ("BDC provider counts", "data/input/bdc/", "FCC BDC (derived)", "CC BY 4.0 (counts)", "yes (counts only)",
         size("data/input/bdc/")),
        ("BDC provider-by-geography files", "not included", "FCC BDC", "FCC API terms", "no: provider-level files are "
         "not redistributed", ""),
        ("ACS 5-year 2022", "data/input/acs/", "Census Data API", "Public domain; API notice in SOURCES.md", "yes",
         size("data/input/acs/")),
        ("County lists, gazetteer, boundaries", "data/input/census/", "Census", "Public domain", "yes",
         size("data/input/census/")),
        ("SVI 2022", "data/input/svi/", "CDC/ATSDR", "Public domain; credit line in SOURCES.md", "yes",
         size("data/input/svi/")),
        ("OpenFEMA declarations", "data/input/fema/", "FEMA", "Public domain; disclaimer in SOURCES.md", "yes",
         size("data/input/fema/")),
        ("NHC HURDAT2 and Isaias best track", "data/input/nhc/", "NOAA/NHC", "Public domain", "yes",
         size("data/input/nhc/")),
    ]
    L = [f"# {TITLE}", "",
         f"Version {VERSION} ({RELEASE_DATE}). Data: CC BY 4.0 (`LICENSE-DATA.md`). Code: MIT (`LICENSE`).", "",
         f"The data and code behind the page *When the Network Goes Dark* ({PAGE_URL}): a county-by-report panel of "
         "FCC DIRS cell-site outages for 21 storms in ten Gulf and Southeast states, 2017-2026, each report checked "
         "against its printed totals, joined to power outages (EAGLE-I), storm tracks (NHC), social vulnerability "
         "(CDC/ATSDR SVI) and broadband provider counts (FCC BDC). Every number on the page is in "
         "`data/analysis/results.json`, and `run_all.py` rebuilds it and the panel from `data/input/`.", "",
         "Associations, not causes. A site out is a site out: the FCC's counts describe the network, not how many "
         "people lost service.", "",
         "## Which licence covers what", "",
         "| Part | Licence |", "|---|---|",
         "| `data/analysis/`, derived files in `data/input/` (marked in `INPUTS.csv`), `datapackage.json`, "
         "`CODEBOOK.md` | CC BY 4.0 |",
         "| `code/`, `run_all.py` | MIT |",
         "| Third-party inputs in `data/input/` | their own terms; see `SOURCES.md` |", "",
         "## Contents", "", "```",
         "data/input/      every input, with INPUTS.csv (source, URL, retrieval time, SHA-256)",
         "data/analysis/   dirs_county_day.csv (the panel), storms.csv, results.json, validation/",
         "code/src/        numbered pipeline steps; code/manifest/ hand-made tables; code/tests/",
         "docs/            analysis plan (as committed, with SHA-256), addendum, decision log, sources notes",
         "run_all.py       one command: rebuild the panel and results.json into build/",
         "```", "",
         "## Analysis plan", "",
         f"The analysis plan was committed on November 22, 2026, in the project's private version-controlled "
         f"repository (commit {plan['commit']}, {plan['committed']}), before any recovery outcome was computed. The "
         f"plan file as committed is `docs/{plan['file']}`, SHA-256 `{plan['sha256']}` (git blob "
         f"`{plan['git_blob']}`), so it can be checked against later changes. It is not blind to some figures, which "
         "the plan lists. Deviations are in `DEVIATIONS.md`.", "",
         "## Data availability and provenance", "",
         "| Data | Location | Provider | Terms | Included | Size |", "|---|---|---|---|---|---|"]
    L += [f"| {a} | `{b}` | {c} | {d} | {e} | {f} |" if b.startswith("data/") else f"| {a} | {b} | {c} | {d} | {e} | {f} |"
          for a, b, c, d, e, f in avail]
    L += ["", "Exact attribution for each source: `SOURCES.md`. Variables: `CODEBOOK.md` and `datapackage.json`.", "",
          "## Computational requirements", "",
          "- Python 3.13 (tested with 3.13.2) on Windows 11; the code uses no platform-specific calls.",
          "- Packages: `requirements.txt` (exact versions used).",
          "- Memory: about 4 GB. Disk: about 200 MB for the repository and `build/`.",
          "- Run time: 12.4 minutes for `run_all.py`, measured on the author's Windows 11 laptop on 2026-11-23 "
          "(most of it is parsing the reports in step 3 and the bootstrap in step 10).",
          "- No network access is needed: every step reads `data/input/`. Steps 02, 06a, 06c, 06d and 06e (downloads "
          "and raw BDC reading) are included for transparency but are not run; they need the original sources and, "
          "for BDC, an FCC account.",
          "- Random numbers: fixed seed 20261122 (bootstrap, 2,000 draws).", "",
          "## Run order", "",
          "```", "python -m pip install -r requirements.txt", "python run_all.py        # rebuild into build/",
          "python -m pytest code/tests/test_reproduction.py   # compare build/ with data/analysis/", "```", "",
          "`run_all.py` runs these steps in this order (all in `code/src/`):", "",
          "| # | Script | Arguments | Does |", "|---|---|---|---|"]
    L += [f"| {i} | `{s}` | {a} | {d} |" for i, (s, a, d) in enumerate(RUN_ORDER, 1)]
    L += ["", "Then it writes `build/processed/storms.csv` and the test compares `build/processed/dirs_county_day.csv`, "
          "`storms.csv` and `build/output/results.json` with `data/analysis/` (byte for byte).", "",
          "## Page sections and figures", "",
          "Each section of the page, its figures (the figure CSVs are published with the page), the key in "
          "`results.json` and the script that produces it. The page itself is built by `code/src/11_build_page.py`, "
          "which needs the website and is not run here.", "",
          "| Page section | Figures | results.json key | Script |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in PAGE_MAP]
    L += ["", "## How to cite", "",
          "See `CITATION.cff`. A DOI will be added when the repository is archived.", "",
          "## Disclosure", "",
          "The author works in the telecommunications industry. This analysis was done independently, on personal "
          "time, using only publicly available government data. It uses no employer data or confidential "
          "information, and the views are the author's alone. The author has no financial interest in any FCC "
          "proceeding. AI assistance: `AI_ASSISTANCE.md`.", ""]
    write(T / "README.md", "\n".join(L))


RUN_ALL = '''"""Rebuild the panel and results.json from data/input, into build/ (one command: python run_all.py).

Runs the steps listed in README.md, in order, each in its own process, and stops at the first failure. Nothing is
downloaded. Then writes build/processed/storms.csv. Compare with: python -m pytest code/tests/test_reproduction.py
"""
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
SRC = REPO / "code" / "src"
STEPS = STEPS_LITERAL


def main():
    t0 = time.time()
    for script, args in STEPS:
        print(f"== {script} {' '.join(args)}", flush=True)
        r = subprocess.run([sys.executable, script, *args], cwd=SRC)
        if r.returncode:
            raise SystemExit(f"{script} failed (exit {r.returncode})")
    sys.path.insert(0, str(SRC))
    import pandas as pd
    from config import PROCESSED
    pd.read_parquet(PROCESSED / "storms.parquet").to_csv(PROCESSED / "storms.csv", index=False, lineterminator="\\n")
    print(f"done in {(time.time() - t0) / 60:.1f} min; outputs in build/")


if __name__ == "__main__":
    main()
'''

TEST_REPRO = '''"""The code reproduces the published files: run python run_all.py first."""
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BUILD = REPO / "build"
PAIRS = [("processed/dirs_county_day.csv", "dirs_county_day.csv"), ("processed/storms.csv", "storms.csv"),
         ("output/results.json", "results.json")]


@pytest.mark.skipif(not (BUILD / "output" / "results.json").exists(), reason="run python run_all.py first")
@pytest.mark.parametrize("built, published", PAIRS)
def test_build_matches_published(built, published):
    assert (BUILD / built).read_bytes() == (REPO / "data" / "analysis" / published).read_bytes(), built


@pytest.mark.skipif(not (BUILD / "output" / "results.json").exists(), reason="run python run_all.py first")
@pytest.mark.parametrize("name", ["validation_dirs.csv", "validation_summary.csv", "excluded_reports.csv",
                                  "area_status_counts.csv"])
def test_validation_tables_match(name):
    assert (BUILD / "output" / name).read_bytes() == (REPO / "data" / "analysis" / "validation" / name).read_bytes()


def test_inputs_match_their_hashes():
    import csv
    import hashlib
    with open(REPO / "data" / "input" / "INPUTS.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            assert hashlib.sha256((REPO / row["path"]).read_bytes()).hexdigest() == row["sha256"], row["path"]


def test_manifest_tables_unchanged():
    """Step 2b rewrites some of code/manifest; after a run they must equal the published tables."""
    import hashlib
    for line in (REPO / "code" / "manifest.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256((REPO / "code" / "manifest" / name).read_bytes()).hexdigest() == digest, name


def test_plan_as_committed_matches_its_hash():
    import hashlib
    line = (REPO / "docs" / "analysis_plan_as_committed.sha256").read_text(encoding="utf-8").split()
    assert hashlib.sha256((REPO / "docs" / line[1]).read_bytes()).hexdigest() == line[0]
'''


def scripts(T: Path) -> None:
    write(T / "run_all.py", RUN_ALL.replace("STEPS_LITERAL", "[\n" + "".join(
        f"    ({s!r}, {a.split()!r}),\n" for s, a, _ in RUN_ORDER) + "]"))
    write(T / "code" / "tests" / "test_reproduction.py", TEST_REPRO)
    write(T / "requirements.txt", "\n".join([
        "pandas==2.3.3", "numpy==2.5.5", "scipy==1.18.1", "statsmodels==0.15.0", "scikit-learn==1.9.1",
        "lifelines==0.30.3", "pdfplumber==0.11.11", "pdfminer.six==20260107", "geopandas==1.2.0", "shapely==2.2.0",
        "pyogrio==0.13.0", "pyproj==3.8.0", "pyarrow==26.0.1", "requests==2.34.2", "pytest==9.2.0"]) + "\n")
    write(T / ".gitignore", "build/\n__pycache__/\n.pytest_cache/\n.env\n.venv/\n")


# ------------------------------------------------------------------------------------------------ checks --
def scan(T: Path) -> dict:
    """Secrets (.env values, never printed), provider names and IDs, forbidden files, files over 50 MB."""
    files = [p for p in T.rglob("*") if p.is_file() and ".git" not in p.relative_to(T).parts
             and "build" not in p.relative_to(T).parts[:1]]
    env = ROOT / ".env"
    secrets = []
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            value = value.strip().strip('"')
            if name.strip() and len(value) >= 8:
                secrets.append((name.strip(), value.encode()))
    names, ids = set(), set()
    for z in sorted((RAW / "bdc").glob("bdc_us_provider_summary_by_geography_*.zip")):
        import zipfile
        zf = zipfile.ZipFile(z)
        for ch in pd.read_csv(zf.open(zf.namelist()[0]), dtype=str, chunksize=500_000,
                              usecols=lambda c: c in ("provider_id", "holding_company", "provider_name", "brand_name")):
            for col in ch.columns:
                vals = set(ch[col].dropna())
                (ids if col == "provider_id" else names).update(vals)
    names = {n for n in names if len(n) >= 6}
    out = {"files": len(files), "bytes": sum(p.stat().st_size for p in files),
           "over_50MB": [str(p.relative_to(T)) for p in files if p.stat().st_size > MAX_BYTES],
           "forbidden_names": [str(p.relative_to(T)) for p in files if any(n in str(p) for n in NEVER)],
           "secret_hits": {}, "provider_name_hits": {}, "provider_id_column_hits": [],
           "provider_names_checked": len(names), "provider_ids_known": len(ids)}
    name_pat = None
    if names:
        import re
        name_pat = re.compile("|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)), re.I)
    for p in files:
        b = p.read_bytes()
        for label, v in secrets:
            if v in b:
                out["secret_hits"].setdefault(label, []).append(str(p.relative_to(T)))
        if p.suffix.lower() in (".csv", ".json", ".md", ".txt", ".cff", ".py", ".yaml", ".html"):
            t = b.decode("utf-8", errors="replace")
            if name_pat:
                hits = sorted({m.group(0) for m in name_pat.finditer(t)})
                if hits:
                    out["provider_name_hits"][str(p.relative_to(T))] = hits[:12]
            if p.suffix.lower() in (".csv", ".json") and "provider_id" in t:
                out["provider_id_column_hits"].append(str(p.relative_to(T)))
        if p.suffix == ".parquet":
            cols = list(pd.read_parquet(p).columns)
            if any("provider" in c for c in cols):
                out["provider_id_column_hits"].append(str(p.relative_to(T)))
        # any table column whose values are mostly BDC provider IDs, whatever it is called
        if ids and p.suffix in (".csv", ".parquet"):
            try:
                df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p, dtype=str, keep_default_na=False)
            except Exception as err:  # reported, not hidden
                out.setdefault("unreadable_tables", []).append(f"{p.relative_to(T)}: {type(err).__name__}")
                continue
            for col in df.columns:
                vals = {str(v) for v in df[col].dropna().unique() if str(v) != ""}
                if len(vals) >= 5 and len(vals & ids) >= 0.5 * len(vals):
                    out.setdefault("provider_id_value_hits", []).append(f"{p.relative_to(T)}:{col}")
    out.setdefault("provider_id_value_hits", [])
    out["provider_names_note"] = ("The BDC summary files and listings used carry no provider names (0 found), so names "
                                  "are checked by column: no file has a provider_name, brand_name or holding_company "
                                  "column, and the FCC DIRS reports are county aggregates that name no provider.")
    return out


def main():
    T = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parents[1] / REPO_NAME
    keep_git = (T / ".git").exists()
    if T.exists():
        for p in T.iterdir():
            if p.name not in (".git", "build"):  # build/ is git-ignored; kept so a finished run can be retested
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    T.mkdir(parents=True, exist_ok=True)
    idx = copy_inputs(T)
    copy_analysis(T)
    copy_code(T)
    copy_docs(T)
    plan = plan_as_committed(T)
    deviations_md(T)
    pkg = datapackage(T, plan)
    codebook_md(T, pkg)
    citation_cff(T)
    changelog(T)
    licenses(T)
    ai_statement(T)
    sources_md(T, idx)
    readme(T, idx, plan)
    scripts(T)
    report = scan(T)
    write(ROOT / "output" / "data_repo_scan.json", json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: v for k, v in report.items()}, indent=1)[:4000])
    print("target:", T, "| kept .git:", keep_git, "| inputs:", len(idx), "| missing URL:",
          int((idx.url == "").sum()), "(derived files have none)")


if __name__ == "__main__":
    main()
