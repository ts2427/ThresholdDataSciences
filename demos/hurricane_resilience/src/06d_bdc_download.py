"""Step 6d (v2-5): download the four approved BDC "Provider Summary by Geography Type" files (2026-11-23).

Files: one national CSV (zipped) per release used by a storm (latest release on or before its day 0): 2022-06-30,
2023-06-30, 2024-06-30, 2026-06-30, by the file_ids in data/raw/bdc/listings/provider_summary_files.csv.
Conduct: credentials only from .env (never printed, logged or saved); at least 6.5 s between calls; generic User-Agent;
any non-200 stops; a file over 1 GB (by Content-Length, or while streaming) stops the run and is not kept. Files go
to data/raw/bdc/ (git-ignored; append-only: an existing file is not downloaded again) and are logged in
manifest/downloads.csv with SHA-256. They contain provider names; nothing downstream keeps or shows them.
"""
import hashlib
import importlib
import time

import pandas as pd
import requests

from config import RAW, USER_AGENT

lister = importlib.import_module("06c_bdc_list")
RELEASES = ["2022-06-30", "2023-06-30", "2024-06-30", "2026-06-30"]
MAX_BYTES = 1 << 30
DEST = RAW / "bdc"


def main():
    auth = lister.credentials()
    files = pd.read_csv(lister.OUT / "provider_summary_files.csv", dtype={"release": str})
    files = files[files.release.isin(RELEASES)]
    if sorted(files.release) != RELEASES:
        raise SystemExit(f"expected one file per release {RELEASES}, got {sorted(files.release)}")
    s = requests.Session()
    for f in files.itertuples():
        dest = DEST / f"{f.file_name}.zip"
        if dest.exists():
            print("exists, kept:", dest.name)
            continue
        url = f"{lister.HOST}/api/public/map/downloads/downloadFile/availability/{f.file_id}"
        with s.get(url, headers={**auth, "User-Agent": USER_AGENT}, stream=True, timeout=300) as r:
            if r.status_code != 200:
                lister.log(url, dest, f"http_{r.status_code}", "", "bdc_provider_summary")
                raise SystemExit(f"STOP: HTTP {r.status_code} for {url} (no retry)")
            size = int(r.headers.get("Content-Length") or 0)
            if size > MAX_BYTES:
                lister.log(url, dest, f"stopped_over_1GB_{size}", "", "bdc_provider_summary")
                raise SystemExit(f"STOP: {url} is {size:,} bytes (over 1 GB); not downloaded")
            part, h, n = dest.with_suffix(".zip.part"), hashlib.sha256(), 0
            with open(part, "wb") as out:
                for chunk in r.iter_content(1 << 20):
                    n += len(chunk)
                    if n > MAX_BYTES:
                        out.close()
                        part.unlink()
                        lister.log(url, dest, "stopped_over_1GB_streaming", "", "bdc_provider_summary")
                        raise SystemExit(f"STOP: {url} passed 1 GB while streaming; removed")
                    h.update(chunk)
                    out.write(chunk)
            part.rename(dest)
        lister.log(url, dest, "downloaded", h.hexdigest(), "bdc_provider_summary")
        print(f"{f.release}: {dest.name} {n:,} bytes")
        time.sleep(lister.SECONDS_BETWEEN_CALLS)


if __name__ == "__main__":
    main()
