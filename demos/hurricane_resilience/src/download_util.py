"""Streaming downloads for the large and non-FCC sources (EAGLE-I, Census, NHC).

Same conduct as step 2: only URLs that start with an approved prefix are requested; one request at a time, at
least 3 seconds apart; the generic User-Agent from config; a 403 or 429 (or any error) stops the run with no retry.
Each file streams to <name>.part and is renamed only after its size and MD5 match the publisher's (when given).
Every attempt is appended to manifest/downloads.csv with its SHA-256. A job whose URL holds a secret (the Census
API key) gives a logged_url with it redacted; only that is logged or shown. Paths outside the project are logged with a
placeholder (e.g. $EAGLEI_RAW_DIR/...) so no personal path reaches a committed file.
"""
import hashlib
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from config import USER_AGENT

SECONDS_BETWEEN_REQUESTS = 3.0
LOG_COLUMNS = ["url", "path", "status", "sha256", "doc_id", "kind", "when"]


def _hash(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(job: dict, session) -> dict:
    dest = job["dest"]
    rec = {"url": job.get("logged_url", job["url"]), "path": job["logged_path"], "sha256": ""}  # no secrets in logs
    if dest.exists():
        return {**rec, "status": "exists", "sha256": _hash(dest, "sha256")}
    time.sleep(SECONDS_BETWEEN_REQUESTS)
    part = dest.with_name(dest.name + ".part")
    try:
        with session.get(job["url"], stream=True, timeout=(30, 300), allow_redirects=True) as r:
            if r.status_code != 200:
                return {**rec, "status": f"http {r.status_code}"}
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 22):
                    f.write(chunk)
    except requests.exceptions.RequestException as err:
        part.unlink(missing_ok=True)
        return {**rec, "status": f"error {type(err).__name__}"}
    if job.get("bytes") is not None and part.stat().st_size != int(job["bytes"]):
        part.unlink()
        return {**rec, "status": "size mismatch"}
    if job.get("md5") and _hash(part, "md5") != job["md5"]:
        part.unlink()
        return {**rec, "status": "md5 mismatch"}
    part.replace(dest)
    return {**rec, "status": "downloaded", "sha256": _hash(dest, "sha256")}


def run(jobs: list[dict], log_path, session=None, allowed: tuple[str, ...] = ()) -> None:
    for job in jobs:
        if not job["url"].startswith(allowed):
            raise SystemExit(f"URL not approved, not requested: {job['url']}")
    s = session or requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    log, stop = [], None
    try:
        for job in jobs:
            job["dest"].parent.mkdir(parents=True, exist_ok=True)
            rec = fetch(job, s)
            rec.update(doc_id=job["doc_id"], kind=job["kind"],
                       when=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            log.append(rec)
            print(job["doc_id"], rec["status"], flush=True)
            if rec["status"] not in ("downloaded", "exists"):
                stop = rec
                break
    finally:
        new = pd.DataFrame(log, columns=LOG_COLUMNS)
        if log_path.exists():
            old = pd.read_csv(log_path, dtype=str, keep_default_na=False)
            new = pd.concat([old, new]).drop_duplicates(["path", "sha256"], keep="first")
        new.to_csv(log_path, index=False, lineterminator="\n")
    if stop:
        raise SystemExit(f"stopped on {stop['status']} at {stop['url']}: not retried")
