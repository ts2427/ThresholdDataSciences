"""Step 8: county covariates.

* OpenFEMA Disaster Declarations Summaries v2, from the documented API (no key). Display on the page:
  "This product uses the FEMA OpenFEMA API, but is not endorsed by FEMA." The 403 on www.fema.gov/robots.txt
  (2026-11-22) was not retried; the author decided the API, FEMA's interface for programmatic access, may be used,
  paced at least 3 s per call and stopping on any 403, 429 or other non-200 (docs/decisions.md).
  Pages of 1,000 declarations since 2017-08-01 of type Hurricane, Tropical Storm, Coastal Storm, Severe Storm or
  Flood, ordered by id, saved as data/raw/fema/declarations_<n>.json. A declaration belongs to a storm when the
  storm's name is a word of its title and the incident began within 10 days before DIRS activation and no later
  than deactivation. Statewide and tribal rows (county code 000) are not county rows.
* CDC/ATSDR SVI 2022 county file, US-ranked (data/raw/svi/SVI_2022_US_county.csv): overall percentile and the
  four themes; -999 is missing.
* FCC Broadband Map: dropped from this version (robots.txt 403, 2026-11-22); a future covariate in the plan.
* Census ACS 5-year 2022 (key from .env via config.census_api_key; never printed or logged): households,
  population 65+, households with a broadband subscription of any type. One request for all counties; the raw
  response is data/raw/acs/acs5_2022_county.json and the logged URL has key=REDACTED.
Outputs: data/interim/county_covariates.parquet (one row per county FIPS: ACS and SVI) and
data/interim/fema_declarations.parquet (one row per storm and declared county).
"""
import json
import re
from urllib.parse import quote

import pandas as pd

import download_util
from config import DOWNLOADS_LOG, INTERIM, RAW, ROOT, census_api_key

ACS_YEAR = 2022
AGE_65 = [f"B01001_{i:03d}E" for i in [*range(20, 26), *range(44, 50)]]  # male and female 65+
ACS_VARS = ["B11001_001E", "B01001_001E", *AGE_65, "B28002_001E", "B28002_004E"]
ACS_RAW = RAW / "acs" / f"acs5_{ACS_YEAR}_county.json"
ACS_BASE = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"

SVI_RAW = RAW / "svi" / "SVI_2022_US_county.csv"
SVI_THEMES = {"RPL_THEMES": "svi_overall", "RPL_THEME1": "svi_socioeconomic", "RPL_THEME2": "svi_household",
              "RPL_THEME3": "svi_minority_language", "RPL_THEME4": "svi_housing_transport"}

FEMA_BASE = "https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries"
FEMA_DIR = RAW / "fema"
FEMA_PAGE = 1000
FEMA_FIELDS = ["id", "disasterNumber", "state", "declarationType", "declarationDate", "incidentType",
               "declarationTitle", "incidentBeginDate", "incidentEndDate", "fipsStateCode", "fipsCountyCode",
               "designatedArea", "ihProgramDeclared", "iaProgramDeclared", "paProgramDeclared", "hmProgramDeclared"]
FEMA_TYPES = ["Hurricane", "Tropical Storm", "Coastal Storm", "Severe Storm", "Flood"]
FEMA_FILTER = ("declarationDate ge '2017-08-01T00:00:00.000Z' and ("
               + " or ".join(f"incidentType eq '{t}'" for t in FEMA_TYPES) + ")")
DAYS_BEFORE_ACTIVATION = 10
STORMS = ROOT / "manifest" / "storms.csv"


def acs_job(key: str) -> dict:
    query = f"?get=NAME,{','.join(ACS_VARS)}&for=county:*"
    return {"url": f"{ACS_BASE}{query}&key={key}", "logged_url": f"{ACS_BASE}{query}&key=REDACTED",
            "dest": ACS_RAW, "logged_path": f"data/raw/acs/{ACS_RAW.name}", "doc_id": ACS_RAW.name, "kind": "acs"}


def acs_table(data: list[list[str]]) -> pd.DataFrame:
    df = pd.DataFrame(data[1:], columns=data[0])
    for v in ACS_VARS:
        df[v] = pd.to_numeric(df[v], errors="coerce")
        df.loc[df[v] < 0, v] = float("nan")  # Census codes such as -666666666 mean not available
    return pd.DataFrame({
        "fips": df.state + df.county, "acs_name": df.NAME,
        "acs_households": df.B11001_001E, "acs_population": df.B01001_001E,
        "acs_pct_65plus": 100 * df[AGE_65].sum(axis=1, min_count=len(AGE_65)) / df.B01001_001E,
        "acs_pct_broadband": 100 * df.B28002_004E / df.B28002_001E,
    })


def svi_table(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw[["FIPS", *SVI_THEMES]].rename(columns={"FIPS": "fips", **SVI_THEMES})
    out["fips"] = out.fips.astype(str).str.zfill(5)
    for col in SVI_THEMES.values():
        out[col] = pd.to_numeric(out[col], errors="coerce").where(lambda s: s >= 0)
    return out


def _fema_url(skip: int, count: bool = False) -> str:
    params = {"$filter": FEMA_FILTER, "$select": ",".join(FEMA_FIELDS), "$orderby": "id", "$top": str(FEMA_PAGE),
              "$skip": str(skip)}
    if count:
        params["$inlinecount"] = "allpages"
    return FEMA_BASE + "?" + "&".join(f"{quote(k)}={quote(v, safe=',')}" for k, v in params.items())


def _fema_job(n: int, skip: int, count: bool = False) -> dict:
    dest = FEMA_DIR / f"declarations_{n:03d}.json"
    return {"url": _fema_url(skip, count), "dest": dest, "logged_path": f"data/raw/fema/{dest.name}",
            "doc_id": dest.name, "kind": "openfema"}


def fema_jobs(total: int) -> list[dict]:
    return [_fema_job(n, n * FEMA_PAGE, count=(n == 0)) for n in range(-(-total // FEMA_PAGE))]


def download_fema() -> pd.DataFrame:
    """First page (with the total count), then the rest; each call paced and stopped on refusal."""
    first = _fema_job(0, 0, count=True)
    download_util.run([first], DOWNLOADS_LOG, allowed=(FEMA_BASE + "?",))
    total = int(json.loads(first["dest"].read_text(encoding="utf-8"))["metadata"]["count"])
    download_util.run(fema_jobs(total)[1:], DOWNLOADS_LOG, allowed=(FEMA_BASE + "?",))
    rows = []
    for job in fema_jobs(total):
        rows += json.loads(job["dest"].read_text(encoding="utf-8"))["DisasterDeclarationsSummaries"]
    got = pd.DataFrame(rows)
    if len(got) != total or got.id.duplicated().any():
        raise SystemExit(f"OpenFEMA pages hold {len(got)} rows ({got.id.duplicated().sum()} repeated), count says {total}")
    return got


def fema_by_county(d: pd.DataFrame, storms: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    for col in ("declarationDate", "incidentBeginDate"):
        d[col] = pd.to_datetime(d[col], utc=True)
    out = []
    for s in storms.itertuples():
        start = pd.Timestamp(s.dirs_activation_date, tz="UTC") - pd.Timedelta(days=DAYS_BEFORE_ACTIVATION)
        end = pd.Timestamp(s.dirs_deactivation_date, tz="UTC")
        named = d.declarationTitle.str.upper().str.contains(rf"\b{re.escape(s.storm_name.upper())}\b")
        hit = d[named & d.incidentBeginDate.between(start, end) & (d.fipsCountyCode != "000")]
        if hit.empty:
            continue
        hit = hit.assign(fips=hit.fipsStateCode.str.zfill(2) + hit.fipsCountyCode.str.zfill(3))
        g = hit.groupby("fips")
        out.append(pd.DataFrame({
            "nhc_id": s.nhc_id, "fema_dr": g.declarationType.apply(lambda x: (x == "DR").any()),
            "fema_em": g.declarationType.apply(lambda x: (x == "EM").any()),
            "fema_ia": g.iaProgramDeclared.any(), "fema_ih": g.ihProgramDeclared.any(),
            "fema_pa": g.paProgramDeclared.any(), "fema_hm": g.hmProgramDeclared.any(),
            "fema_first_declared": g.declarationDate.min(),
            "fema_disasters": g.disasterNumber.apply(lambda x: "; ".join(str(n) for n in sorted(set(x)))),
        }).reset_index())
    cols = ["nhc_id", "fips", "fema_dr", "fema_em", "fema_ia", "fema_ih", "fema_pa", "fema_hm",
            "fema_first_declared", "fema_disasters"]
    return pd.concat(out, ignore_index=True)[cols] if out else pd.DataFrame(columns=cols)


def main():
    if not ACS_RAW.exists():
        download_util.run([acs_job(census_api_key())], DOWNLOADS_LOG, allowed=(ACS_BASE,))
    acs = acs_table(json.loads(ACS_RAW.read_text(encoding="utf-8")))
    svi = svi_table(pd.read_csv(SVI_RAW, dtype={"FIPS": str}, encoding="utf-8-sig"))
    cov = acs.merge(svi, on="fips", how="outer", validate="one_to_one")
    cov.to_parquet(INTERIM / "county_covariates.parquet", index=False)
    fema = fema_by_county(download_fema(), pd.read_csv(STORMS))
    fema.to_parquet(INTERIM / "fema_declarations.parquet", index=False)
    print(f"ACS {ACS_YEAR}: {len(acs)} counties; SVI 2022: {svi.svi_overall.notna().sum()} with an overall percentile")
    print("FEMA declared counties by storm:", fema.groupby("nhc_id").size().to_dict())


if __name__ == "__main__":
    main()
