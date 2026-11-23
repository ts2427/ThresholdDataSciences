"""Step 6a: download the approved EAGLE-I files to EAGLEI_RAW_DIR (outside the project folder, which is cloud-synced).

Approved by the author 2026-11-22: the year files 2017-2024 (2025 is not needed by any in-scope storm) and the
coverage files coverage_history.csv, MCC.csv and DQI.csv. The list, sizes and MD5s are in manifest/eaglei_files.csv,
from the figshare API record of doi:10.6084/m9.figshare.24237376 (version 4). Each file is checked against its
size and MD5 and its SHA-256 is logged in manifest/downloads.csv, with the path written as $EAGLEI_RAW_DIR/<file>.
Refuses to start with less than 3x the download size free on the target drive.
"""
import shutil

import pandas as pd

import download_util
from config import DOWNLOADS_LOG, EAGLEI_RAW_DIR, ROOT

FILES = ROOT / "manifest" / "eaglei_files.csv"
ALLOWED = ("https://ndownloader.figshare.com/files/",)


def main():
    files = pd.read_csv(FILES, dtype={"md5": str})
    EAGLEI_RAW_DIR.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(EAGLEI_RAW_DIR).free
    need = files.bytes.sum()
    print(f"need {need / 1e9:.2f} GB; free {free / 1e9:.0f} GB")
    if free < 3 * need:
        raise SystemExit("not enough free disk space: stopped before downloading")
    small_first = files.sort_values("bytes")
    jobs = [{"url": f.url, "dest": EAGLEI_RAW_DIR / f.file, "logged_path": f"$EAGLEI_RAW_DIR/{f.file}",
             "doc_id": f.file, "kind": "eaglei", "bytes": int(f.bytes), "md5": f.md5} for f in small_first.itertuples()]
    download_util.run(jobs, DOWNLOADS_LOG, allowed=ALLOWED)


if __name__ == "__main__":
    main()
