r"""Step B1: download OSHA Severe Injury Reports (federal OSHA jurisdiction
only) into data/raw/ and log it in the manifest.

    .venv\Scripts\python -m osha_audit.src.download
"""
import io
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from common import manifest

ROOT = Path(__file__).resolve().parents[2]
URL = "https://www.osha.gov/sites/default/files/January2015toNovember2025.zip"
RAW = ROOT / "data/raw/osha_sir_January2015toNovember2025.zip"
# osha.gov rejects requests without ordinary browser headers (HTTP 403).
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/142.0 Safari/537.36"),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def zip_members(path):
    with zipfile.ZipFile(path) as z:
        return [i.filename for i in z.infolist() if not i.is_dir()]


def read_member(path, member):
    """Read a CSV or Excel member of the zip as all-string columns (raw
    values untouched)."""
    with zipfile.ZipFile(path) as z:
        data = z.read(member)
    if member.lower().endswith(".csv"):
        for enc in ("utf-8-sig", "cp1252"):
            try:
                return pd.read_csv(io.BytesIO(data), dtype=str, encoding=enc,
                                   keep_default_na=False)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"{member}: could not decode")
    return pd.read_excel(io.BytesIO(data), dtype=str, keep_default_na=False)


if __name__ == "__main__":
    RAW.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(URL, headers=HEADERS, timeout=600, stream=True) as r:
        r.raise_for_status()
        with open(RAW, "wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
    members = zip_members(RAW)
    print("zip members:", members)
    data_members = [m for m in members if m.lower().endswith((".csv", ".xlsx", ".xls"))]
    if len(data_members) != 1:
        raise SystemExit(f"expected one data file in the zip, found {data_members}")
    df = read_member(RAW, data_members[0])
    manifest.record(RAW, URL, rows=len(df), accessed=date.today())
    print(f"{RAW.name}: {RAW.stat().st_size:,} bytes; {data_members[0]}: "
          f"{len(df):,} rows x {df.shape[1]} columns")
    print("columns:", list(df.columns))
