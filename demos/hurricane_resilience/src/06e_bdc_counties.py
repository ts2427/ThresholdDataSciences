"""Step 6e (v2-5): read the four BDC provider-by-geography files, keeping only county rows in the ten study states.

Reads each zipped CSV in chunks (never the whole file at once) and keeps rows with geography_type "County" and a
geography_id whose state FIPS is a study state. Columns kept: release, geoid, data_type (Fixed / Mobile Broadband),
provider_id, res_st_pct, bus_iv_pct. Provider IDs stay in data/interim (git-ignored) and are used only for counting;
the files carry no provider names, and nothing downstream keeps an ID.
Output: data/interim/bdc_provider_county.parquet.
"""
import zipfile

import pandas as pd

from config import INTERIM, RAW

STUDY_FIPS = {"48", "22", "28", "01", "12", "13", "45", "37", "47", "51"}
FILES = {"2022-06-30": "J22", "2023-06-30": "J23", "2024-06-30": "J24", "2026-06-30": "J26"}


def county_rows(path, release: str, chunksize: int = 200_000) -> pd.DataFrame:
    z = zipfile.ZipFile(path)
    out, seen_types = [], set()
    for ch in pd.read_csv(z.open(z.namelist()[0]), dtype=str, chunksize=chunksize):
        seen_types |= set(ch.geography_type.dropna())
        c = ch[(ch.geography_type == "County") & ch.geography_id.str[:2].isin(STUDY_FIPS)]
        out.append(c[["geography_id", "data_type", "provider_id", "res_st_pct", "bus_iv_pct"]])
    df = pd.concat(out, ignore_index=True).rename(columns={"geography_id": "geoid"})
    df["release"] = release
    for col in ("res_st_pct", "bus_iv_pct"):
        df[col] = df[col].astype(float)
    df.attrs["geography_types"] = sorted(seen_types)
    return df


def main():
    parts = []
    for rel, tag in FILES.items():
        path = next((RAW / "bdc").glob(f"bdc_us_provider_summary_by_geography_{tag}_*.zip"))
        df = county_rows(path, rel)
        print(rel, "geography types in file:", df.attrs["geography_types"], "| study-state county rows:", len(df),
              "| counties:", df.geoid.nunique())
        parts.append(df)
    pd.concat(parts, ignore_index=True).to_parquet(INTERIM / "bdc_provider_county.parquet", index=False)


if __name__ == "__main__":
    main()
