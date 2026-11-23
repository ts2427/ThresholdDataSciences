"""Step 1: validate manifest/dirs_reports.csv before downloading anything.

The manifest has one row per FCC DIRS Communications Status Report.
status is "ok" once confirmed, or "out_of_scope" (kept and logged, but not parsed or validated).
Build it by hand from the FCC storm pages (https://www.fcc.gov/past-response-efforts),
because the FCC site may block automated browsing. Direct docs.fcc.gov file URLs usually download fine.
"""
import re
import sys

import pandas as pd

from config import MANIFEST

REQUIRED = ["storm_name", "nhc_id", "dirs_activation_date", "report_date", "doc_id", "pdf_url", "txt_url", "status"]


def check(df: pd.DataFrame) -> list[str]:
    problems = []
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        return [f"missing columns: {missing}"]
    if df.doc_id.duplicated().any():
        problems.append(f"duplicate doc_id: {df.doc_id[df.doc_id.duplicated()].tolist()}")
    bad_doc = df[~df.doc_id.astype(str).str.match(r"^DOC-\d+A\d$")]
    if len(bad_doc):
        problems.append(f"malformed doc_id: {bad_doc.doc_id.tolist()}")
    for col in ["pdf_url", "txt_url"]:
        bad = df[df[col].notna() & ~df[col].astype(str).str.startswith("https://docs.fcc.gov/")]
        if len(bad):
            problems.append(f"{col} not on docs.fcc.gov: {bad.doc_id.tolist()}")
    nhc = df.nhc_id.dropna().astype(str)
    bad_nhc = nhc[~nhc.str.match(r"^AL\d{6}$")]
    if len(bad_nhc):
        problems.append(f"malformed nhc_id (want ALnnYYYY): {bad_nhc.tolist()}")
    todo = df[~df.status.isin(["ok", "out_of_scope"]) | df.storm_name.eq("TBD") | df.report_date.isna()]
    if len(todo):
        problems.append(f"{len(todo)} rows still need storm/date confirmation (status != ok)")
    return problems


if __name__ == "__main__":
    df = pd.read_csv(MANIFEST)
    print(f"{len(df)} reports in manifest, {df.storm_name.nunique()} storms")
    print(df.groupby("storm_name").size().to_string())
    probs = check(df)
    for p in probs:
        print("PROBLEM:", p)
    sys.exit(1 if any(not p.endswith("(status != ok)") for p in probs) else 0)
