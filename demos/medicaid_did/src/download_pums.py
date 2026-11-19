r"""Step A1a (revised): download ACS 1-year PUMS person records for adults
19–64, one file per state-year, save unedited to data/raw/pums/, log each
in the manifest, and build the state-year panel.

    .venv\Scripts\python -m medicaid_did.src.download_pums

Key from .env (CENSUS_API_KEY); never printed, logged or written; manifest
URLs omit it. Re-running skips state-years already on disk.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from common import manifest
from medicaid_did.src.pums import STATE_FIPS, VARS, YEARS, aggregate, records_to_frame

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/pums"
OUT = ROOT / "data/processed/pums_state_year.csv"
API = "https://api.census.gov/data/{year}/acs/acs1/pums"


def public_url(year, fips):
    return f"{API.format(year=year)}?get={','.join(VARS)}&AGEP=19:64&for=state:{fips}"


def fetch(year, fips, key):
    path = RAW / f"pums_{year}_{fips}.json"
    if not path.exists():
        for attempt in range(4):
            r = requests.get(API.format(year=year),
                             params={"get": ",".join(VARS), "AGEP": "19:64",
                                     "for": f"state:{fips}", "key": key},
                             timeout=600)
            if r.status_code == 200:
                break
        else:
            raise RuntimeError(f"{year} state {fips}: HTTP {r.status_code}")
        tmp = path.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
    return path


def main():
    load_dotenv(ROOT / ".env")
    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        raise SystemExit("CENSUS_API_KEY not found in .env")
    RAW.mkdir(parents=True, exist_ok=True)
    jobs = [(y, f) for y in YEARS for f in STATE_FIPS]
    with ThreadPoolExecutor(max_workers=4) as ex:
        paths = list(ex.map(lambda yf: (yf, fetch(yf[0], yf[1], key)), jobs))
    recs = []
    for (year, fips), path in paths:
        api_json = json.loads(path.read_text(encoding="utf-8"))
        manifest.record(path, public_url(year, fips), rows=len(api_json) - 1,
                        accessed=date.today())
        agg = aggregate(records_to_frame(api_json))
        recs.append({"year": year, "fips": fips, **agg})
    panel = pd.DataFrame(recs).sort_values(["fips", "year"])
    panel.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(panel)} state-years")


if __name__ == "__main__":
    main()
