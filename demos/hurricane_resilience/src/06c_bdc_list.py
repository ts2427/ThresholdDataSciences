"""Step 6c (v2-5): list the FCC Broadband Data Collection releases and the provider-summary files, without downloading data.

Calls (https://bdc.fcc.gov, Public Data API spec rev. 1.7):
  1. GET /api/public/map/listAsOfDates
  2. for each chosen availability release, and for Fixed Broadband and Mobile Broadband:
     GET /api/public/map/downloads/listAvailabilityData/{as_of_date}
         ?category=Summary&subcategory=Provider Summary by Geography Type&technology_type=...
Releases: for each storm from 2022 on, the latest availability release on or before its day 0 (main analysis); the
earliest release for storms before 2022 (sensitivity display only; addendum changes 2026-11-23).

Conduct: credentials only from .env (FCC_BDC_USERNAME, FCC_BDC_TOKEN), never printed, logged or saved; at least 6.5
seconds between calls (the API allows 10 per minute); the generic User-Agent; any status other than 200 stops the run
with no retry. Each response is saved to data/raw/bdc/listings/ and logged in manifest/downloads.csv with its SHA-256.
"""
import hashlib
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from config import DOWNLOADS_LOG, PROCESSED, RAW, ROOT, USER_AGENT

HOST = "https://bdc.fcc.gov"
SECONDS_BETWEEN_CALLS = 6.5
OUT = RAW / "bdc" / "listings"
TECHS = ["Fixed Broadband", "Mobile Broadband"]
SUBCATEGORY = "Provider Summary by Geography Type"


def credentials(env_file: Path = ROOT / ".env") -> dict:
    vals = {}
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        name, _, value = line.partition("=")
        vals[name.strip()] = value.strip().strip('"').strip("'")
    user, token = vals.get("FCC_BDC_USERNAME"), vals.get("FCC_BDC_TOKEN")
    if not user or not token:
        raise SystemExit("FCC_BDC_USERNAME / FCC_BDC_TOKEN not set in .env")
    return {"username": user, "hash_value": token}


def release_before(day: date, releases: list) -> str:
    """The latest release on or before the storm's day 0 (addendum change, 2026-11-23): the network the storm met."""
    before = [r for r in releases if date.fromisoformat(r) <= day]
    return max(before) if before else min(releases)


def choose_releases(storms: pd.DataFrame, releases: list) -> dict:
    """storm -> (release, role); 2022+ storms: latest release on or before day 0 (main); earlier storms: the earliest
    release (sensitivity display, "network data from after the storm")."""
    out = {}
    for s in storms.itertuples():
        d = pd.Timestamp(s.landfall_utc).tz_convert("America/New_York").date()  # day 0
        if d.year >= 2022:
            out[s.storm] = (release_before(d, releases), "main")
        else:
            out[s.storm] = (min(releases), "sensitivity: network data from after the storm")
    return out


def log(url: str, path: Path, status: str, sha: str, kind: str) -> None:
    row = pd.DataFrame([{"url": url, "path": path.relative_to(ROOT).as_posix(), "status": status, "sha256": sha,
                         "doc_id": path.name, "kind": kind,
                         "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}])
    row.to_csv(DOWNLOADS_LOG, mode="a", header=False, index=False, lineterminator="\n")


def call(session, path: str, params: dict | None, dest: Path, auth: dict) -> dict:
    url = HOST + path
    r = session.get(url, params=params, headers={**auth, "User-Agent": USER_AGENT}, timeout=60)
    shown = r.url  # the URL carries no credential (they travel in headers)
    if r.status_code != 200:
        log(shown, dest, f"http_{r.status_code}", "", "bdc_listing")
        raise SystemExit(f"STOP: HTTP {r.status_code} for {shown} (no retry)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    log(shown, dest, "downloaded", hashlib.sha256(r.content).hexdigest(), "bdc_listing")
    time.sleep(SECONDS_BETWEEN_CALLS)
    return r.json()


def main():
    auth = credentials()
    storms = pd.read_parquet(PROCESSED / "storms.parquet")
    storms = storms[storms.in_panel]
    s = requests.Session()
    dates = call(s, "/api/public/map/listAsOfDates", None, OUT / "listAsOfDates.json", auth)
    releases = sorted(x["as_of_date"] for x in dates["data"] if x["data_type"] == "availability")
    chosen = choose_releases(storms, releases)
    needed = sorted({r for r, _ in chosen.values()})
    rows = []
    for rel in needed:
        for tech in TECHS:
            dest = OUT / f"listAvailabilityData_{rel}_{tech.split()[0].lower()}.json"
            got = call(s, f"/api/public/map/downloads/listAvailabilityData/{rel}",
                       {"category": "Summary", "subcategory": SUBCATEGORY, "technology_type": tech}, dest, auth)
            for f in got["data"]:
                rows.append({"release": rel, "technology_type": f.get("technology_type"), "file_id": f.get("file_id"),
                             "subcategory": f.get("subcategory"), "file_type": f.get("file_type"),
                             "file_name": f.get("file_name"), "record_count": f.get("record_count"),
                             "state": f.get("state_name"), "provider_named": f.get("provider_name") is not None})
    pd.DataFrame(rows).to_csv(OUT / "provider_summary_files.csv", index=False, lineterminator="\n")
    json.dump({k: {"release": v[0], "role": v[1]} for k, v in chosen.items()},
              open(OUT / "storm_releases.json", "w", encoding="utf-8"), indent=1)
    print("availability releases:", releases)
    print("storm -> release:", {k: v[0] for k, v in chosen.items()})
    print(pd.DataFrame(rows).to_string(index=False) if rows else "no files matched the filters")


if __name__ == "__main__":
    main()
