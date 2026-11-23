"""Step 3: parse every downloaded DIRS report into county rows and report-level figures.

Prefers the .txt file unless the PDF (read with pdfplumber) recovers more table rows, then more numbers.
Reports marked out_of_scope in the manifest are skipped.
Writes data/interim/dirs_county_rows.parquet (with out_unattributed and out_overattributed, see carried.py,
each row's storm key, see storm_keys.py, and its area_status, see 02b_reporting_areas.py),
dirs_state_totals.parquet, dirs_county_lists.parquet, dirs_reports.parquet, and dirs_pdf_lines.parquet
(the PDF read as plain lines, not by table cell: step 4's second reading).
"""
import importlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from carried import add_unattributed
from config import INTERIM, MANIFEST, RAW, ROOT
from storm_keys import assign_storm_keys
from dirs_parser import ROW_RE, TOTAL_ROW_RE, parse_text


def cell_text(page) -> str:
    """Page text with tables read cell by cell, so a name wrapped inside a cell stays on its row."""
    tables = page.find_tables()
    outside = page
    for table in tables:
        outside = outside.outside_bbox(table.bbox)
    lines = [outside.extract_text() or ""]
    for table in tables:
        for cells in table.extract():
            lines.append(" ".join(" ".join((c or "").replace("-\n", "-").split()) for c in cells))
    return "\n".join(lines)


def completeness(text: str) -> tuple[int, int]:
    """(table rows, numbers in them): how much of the page's tables a reading recovered."""
    rows = [m for line in text.splitlines() for m in [ROW_RE.match(line) or TOTAL_ROW_RE.match(line)] if m]
    return len(rows), sum(len(m.group("nums").split()) for m in rows)


def page_text(page) -> str:
    """The cell-by-cell reading keeps wrapped names whole (Isaias 2026), but pdfplumber's table cells sometimes
    drop columns or merge rows (Zeta and Barry 2019-2020, Florence 2018). Use whichever reading recovers more
    rows, then more numbers; on a tie, the cell reading."""
    cells = cell_text(page)
    plain = page.extract_text() or ""
    return cells if completeness(cells) >= completeness(plain) else plain


def pdf_text(path) -> str:
    import pdfplumber
    with pdfplumber.open(path) as p:
        return "\n".join(page_text(page) for page in p.pages)


def pdf_lines(path) -> list[str]:
    """A second, independent reading: plain lines, with no use of table cells or of the parser."""
    if not path.exists():
        return []
    import pdfplumber
    with pdfplumber.open(path) as p:
        return [line for page in p.pages for line in (page.extract_text() or "").splitlines()]


EASTERN = ZoneInfo("America/New_York")


def as_of_utc(date: str, clock: str, tz: str) -> datetime:
    """The snapshot time in UTC: the printed clock read as Eastern local time on that date. The FCC prints EDT or
    EST; with no zone printed, Eastern is assumed. A printed zone that disagrees with the calendar (Zeta, Nov 1,
    2020: "12:00 p.m. EDT" after daylight time ended) is a misprint, reported by as_of_zone_note."""
    return datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=EASTERN).astimezone(timezone.utc)


def as_of_zone_note(date: str, clock: str, tz: str) -> str:
    zone = datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=EASTERN).tzname()
    if not tz:
        return "no zone printed; Eastern assumed"
    return "" if tz == zone else f"{tz} printed, but Eastern time then was {zone}; read as {zone}"


def as_of_fields(rep, report_date: str) -> dict:
    if not rep or not rep.as_of_time:
        return {"as_of_date": None, "as_of_time": None, "as_of_tz": None, "as_of_utc": None, "as_of_note": None}
    date = rep.as_of_date or report_date
    return {"as_of_date": date, "as_of_time": rep.as_of_time, "as_of_tz": rep.as_of_tz,
            "as_of_utc": as_of_utc(date, rep.as_of_time, rep.as_of_tz).isoformat(),
            "as_of_note": as_of_zone_note(date, rep.as_of_time, rep.as_of_tz)}


def report_text(doc_id: str) -> tuple[str, str]:
    """The .txt unless the PDF recovers more table rows, then more numbers (Harvey 2017 .txt files break rows across
    lines; some .txt files run cells together or space out letters)."""
    txt = RAW / "dirs" / f"{doc_id}.txt"
    pdf = RAW / "dirs" / f"{doc_id}.pdf"
    text = txt.read_text(encoding="utf-8", errors="replace") if txt.exists() else ""
    if pdf.exists():
        from_pdf = pdf_text(pdf)
        if not text or completeness(from_pdf) > completeness(text):
            return from_pdf, "pdf"
    return (text, "txt") if text else ("", "missing")


def add_area_status(rows: pd.DataFrame, lists: pd.DataFrame) -> pd.DataFrame:
    """Each row's area_status against its report's storm area (manifest/reporting_areas.csv, step 2b)."""
    areas = importlib.import_module("02b_reporting_areas")
    iv = pd.read_csv(ROOT / "manifest" / "reporting_areas.csv", dtype=str, keep_default_na=False)
    for col in ("added_on", "removed_on"):
        iv[col] = pd.to_datetime(iv[col].replace("", None))
    iv["key"] = iv.county.map(areas.name_key)
    page = pd.read_csv(ROOT / "manifest" / "storms.csv", dtype=str).set_index("storm_name").storm_page
    parts = []
    for storm, g in rows.groupby("storm_name", sort=False):
        parts.append(areas.area_statuses(g, iv[iv.storm_page == page.get(storm, "")], lists))
    return pd.concat(parts).loc[rows.index]


def main():
    man = pd.read_csv(MANIFEST)
    rows, totals, lists, reports, printed, overall = [], [], [], [], [], []
    for _, m in man.iterrows():
        if m.get("status") == "out_of_scope":
            print(f"{m.doc_id}: out of scope, skipped")
            continue
        text, src = report_text(m.doc_id)
        rep = parse_text(text) if text else None
        meta = {"doc_id": m.doc_id, "storm_name": m.storm_name, "nhc_id": m.nhc_id, "report_date": m.report_date}
        reports.append({**meta, "source": src,
                        "n_county_rows": len(rep.rows) if rep else 0,
                        "pct_sites_out_stated": rep.pct_sites_out if rep else None,
                        "cable_wireline_subs_out": rep.cable_wireline_subs_out if rep else None,
                        **as_of_fields(rep, m.report_date),
                        "warnings": " | ".join(rep.warnings) if rep else "no file"})
        if rep:
            rows += [{**meta, **r} for r in rep.rows]
            totals += [{**meta, **t} for t in rep.state_totals]
            lists += [{**meta, **c} for c in rep.county_list]
            overall += [{**meta, **t} for t in rep.overall_totals]
        printed += [{"doc_id": m.doc_id, "line": line} for line in pdf_lines(RAW / "dirs" / f"{m.doc_id}.pdf")]
        print(f"{m.doc_id}: {src}, {reports[-1]['n_county_rows']} county rows")
    INTERIM.mkdir(parents=True, exist_ok=True)
    county_rows = add_unattributed(pd.DataFrame(rows)) if rows else pd.DataFrame()
    if rows:  # each row's storm key (Nicholas counties in the shared Ida reports get Nicholas's)
        county_rows = assign_storm_keys(
            county_rows, pd.read_csv(ROOT / "manifest" / "shared_report_counties.csv", dtype=str, keep_default_na=False),
            pd.read_csv(ROOT / "manifest" / "storms.csv", dtype=str, keep_default_na=False))
        county_rows = add_area_status(county_rows, pd.DataFrame(lists, columns=["doc_id", "state", "county"]))
    county_rows.to_parquet(INTERIM / "dirs_county_rows.parquet", index=False)
    pd.DataFrame(lists).to_parquet(INTERIM / "dirs_county_lists.parquet", index=False)
    pd.DataFrame(totals).to_parquet(INTERIM / "dirs_state_totals.parquet", index=False)
    pd.DataFrame(overall, columns=["doc_id", "states", "sites_served", "sites_out"] if not overall else None
                 ).to_parquet(INTERIM / "dirs_overall_totals.parquet", index=False)
    pd.DataFrame(printed, columns=["doc_id", "line"]).to_parquet(INTERIM / "dirs_pdf_lines.parquet", index=False)
    pd.DataFrame(reports).to_parquet(INTERIM / "dirs_reports.parquet", index=False)


if __name__ == "__main__":
    main()
