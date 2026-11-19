r"""Validation download: published ACS 1-year table C27016 for every state +
DC in 2017–2019, the years in which it uses the same 19–64 age band as the
PUMS-based panel (it used 18–64 through 2016; see docs/decisions.md). Saves
the raw API responses unedited, logs them in the manifest, and writes the
published state-year rates used to check the PUMS aggregation.

    .venv\Scripts\python -m medicaid_did.src.download_acs

The API key is read from .env (CENSUS_API_KEY) and never printed, logged or
written to disk; manifest URLs are recorded without it.
"""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from common import manifest
from medicaid_did.src.acs import select_vars, state_year_rates

VALIDATION_YEARS = [2017, 2018, 2019]

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/acs"
OUT = ROOT / "data/processed/c27016_published_2017_2019.csv"
API = "https://api.census.gov/data/{year}/acs/acs1"
EXCLUDE_FIPS = {"72"}  # Puerto Rico: not a state; no Medicaid expansion decision


def _get(url, params):
    r = requests.get(url, params=params, timeout=120)
    if r.status_code != 200:
        # never echo the request URL: it carries the key
        raise RuntimeError(f"HTTP {r.status_code} from {url}")
    return r


def main():
    load_dotenv(ROOT / ".env")
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise SystemExit("CENSUS_API_KEY not found in .env")
    RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    for year in VALIDATION_YEARS:
        meta_url = f"{API.format(year=year)}/groups/C27016.json"
        meta_path = RAW / f"c27016_{year}_variables.json"
        meta_path.write_bytes(_get(meta_url, {}).content)
        varmap = select_vars(json.loads(meta_path.read_text(encoding="utf-8"))["variables"])
        manifest.record(meta_path, meta_url, rows=len(varmap) * 2, accessed=date.today())

        codes = [c for b in varmap.values() for c in (b["total"], b["uninsured"])]
        get = ",".join(["NAME"] + codes + [c[:-1] + "M" for c in codes])
        data_path = RAW / f"c27016_{year}_state.json"
        data_path.write_bytes(_get(API.format(year=year),
                                   {"get": get, "for": "state:*", "key": key}).content)
        rows = json.loads(data_path.read_text(encoding="utf-8"))
        header, body = rows[0], rows[1:]
        recs = [dict(zip(header, r)) for r in body]
        public_url = f"{API.format(year=year)}?get={get}&for=state:*"
        manifest.record(data_path, public_url, rows=len(recs), accessed=date.today())

        recs = [r for r in recs if r["state"] not in EXCLUDE_FIPS]
        df = pd.DataFrame(state_year_rates(recs, varmap))
        df.insert(0, "year", year)
        if len(df) != 51:
            raise SystemExit(f"{year}: expected 51 jurisdictions, got {len(df)}")
        frames.append(df)
        print(f"{year}: 51 jurisdictions; low-income 19-64 uninsured "
              f"{df.lowinc_uninsured.sum() / df.lowinc_pop.sum():.3f}")
    panel = pd.concat(frames, ignore_index=True)
    panel.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(panel)} rows")


if __name__ == "__main__":
    main()
