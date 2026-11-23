"""Step 2: download DIRS reports listed in the manifest (txt preferred, pdf as backup), and the FCC's
reporting-area notices for in-scope storms (text only).

Out-of-scope reports are not fetched. Reports go to data/raw/dirs/, notices to data/raw/notices/. Every file is written once and logged with its
SHA-256 in manifest/downloads.csv. Logged paths are relative to the project root, and a rerun with nothing new
leaves the log unchanged. Existing files are never overwritten.

Notices: every activation, area-change or deactivation notice in manifest/fcc_storm_documents.csv for a storm
page in manifest/storms.csv whose title is about DIRS reporting (MDRI-only notices are skipped).

FCC terms (docs/decisions.md, 2026-11-22): only document URLs listed in the manifest, only on docs.fcc.gov,
no probing or crawling, at most one request every 3 seconds, and stop on the first 403 or 429 with no retry
and no change of headers. Any other request error (such as a timeout) is logged and also stops the run.
Other sources (EAGLE-I, NHC, FEMA, SVI, BDC) get their own functions here as they are added; keep each one
append-only and logged the same way.
"""
import hashlib
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from config import DOWNLOADS_LOG, MANIFEST, RAW, ROOT, USER_AGENT

DOCUMENT_LIST = ROOT / "manifest" / "fcc_storm_documents.csv"
STORMS = ROOT / "manifest" / "storms.csv"
NOTICE_KINDS = ("activation", "area_change", "deactivation")
DIRS_TITLE = r"DIRS|Disaster"

SECONDS_BETWEEN_REQUESTS = 3.0
REFUSALS = ("http 403", "http 429")


def sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_html_404(content: bytes) -> bool:
    head = content[:600].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html")) and b"404" in head


def fetch(url: str, dest, session: requests.Session) -> dict:
    path = dest.relative_to(ROOT).as_posix()
    if dest.exists():
        return {"url": url, "path": path, "status": "exists", "sha256": sha256(dest)}
    if not url.startswith("https://docs.fcc.gov/public/attachments/"):
        raise SystemExit(f"not a docs.fcc.gov attachment, not requested: {url}")
    time.sleep(SECONDS_BETWEEN_REQUESTS)  # before every request, so a rerun can't shorten the gap
    try:
        r = session.get(url, timeout=60, allow_redirects=False)
    except requests.exceptions.RequestException as err:
        return {"url": url, "path": path, "status": f"error {type(err).__name__}", "sha256": ""}
    if r.status_code != 200 or len(r.content) < 200:
        return {"url": url, "path": path, "status": f"http {r.status_code}", "sha256": ""}
    if is_html_404(r.content):  # docs.fcc.gov answers some missing .txt files with status 200 and this page
        return {"url": url, "path": path, "status": "not found (html 404 page)", "sha256": ""}
    dest.write_bytes(r.content)
    return {"url": url, "path": path, "status": "downloaded", "sha256": sha256(dest)}


def run(jobs: list[dict]) -> None:
    """Fetch each job in order, log every result, and stop at the first refusal or error."""
    for job in jobs:
        job["dest"].parent.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    log = []
    refused = None
    for job in jobs:
        rec = fetch(job["url"], job["dest"], s)
        rec.update(doc_id=job["doc_id"], kind=job["kind"], when=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        log.append(rec)
        print(rec["doc_id"], job["kind"], rec["status"])
        if rec["status"] in REFUSALS or rec["status"].startswith("error "):
            refused = rec
            break
    new = pd.DataFrame(log)
    if DOWNLOADS_LOG.exists():
        # Read as text: otherwise a failed download's empty sha256 becomes NaN and is logged again on each run.
        old = pd.read_csv(DOWNLOADS_LOG, dtype=str, keep_default_na=False)
        new = pd.concat([old, new]).drop_duplicates(["path", "sha256"], keep="first")
    new.to_csv(DOWNLOADS_LOG, index=False, lineterminator="\n")
    if refused:
        raise SystemExit(f"stopped on {refused['status']} at {refused['url']}: not retried")


def download_dirs():
    man = pd.read_csv(MANIFEST)
    jobs = []
    for _, row in man.iterrows():
        if row.get("status") == "out_of_scope":
            continue  # kept in the manifest, never fetched
        for kind in ("txt", "pdf"):
            url = row.get(f"{kind}_url")
            if isinstance(url, str) and url:
                jobs.append({"url": url, "dest": RAW / "dirs" / f"{row.doc_id}.{kind}", "doc_id": row.doc_id,
                             "kind": kind})
    run(jobs)


def notice_jobs(documents: pd.DataFrame, pages: set[str]) -> list[dict]:
    keep = documents[documents.storm_page.isin(pages) & documents.kind.isin(NOTICE_KINDS)
                     & documents.title.str.contains(DIRS_TITLE, regex=True)]
    return [{"url": r.txt_url, "dest": RAW / "notices" / f"{r.doc_id}.txt", "doc_id": r.doc_id, "kind": "txt"}
            for r in keep.itertuples()]


def download_notices():
    documents = pd.read_csv(DOCUMENT_LIST, dtype=str, keep_default_na=False)
    pages = set(pd.read_csv(STORMS, dtype=str).storm_page)
    run(notice_jobs(documents, pages))


if __name__ == "__main__":
    download_dirs()
    download_notices()
