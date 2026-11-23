"""Step 5: map DIRS (state, county) names to 5-digit county FIPS.

Built from the Census county reference file (data/raw/census/national_county2020.txt) plus
manifest/fips_exceptions.csv for names that don't match. Names are compared within a state, ignoring case,
accents, spaces and punctuation, a trailing "County", "Parish" or "Municipio", and "St."/"Saint". Virginia's
independent cities appear in the reports as "<NAME> CITY"; a plain name is the county (Fairfax, Franklin, Richmond,
Roanoke have both). A city with no county of that name (Radford, Salem) is in the exception table.
Scope (2026-11-22): every county-day in a state outside config.STUDY_STATES is dropped first, for every storm.
manifest/out_of_scope_areas.csv is generated here from the config and the parsed rows, never typed. Step 4
validated the full tables, so this changes no reconciliation.
Every unmatched name must appear in the exception table, every exception must be used and must be a Census
county, or the script fails. Output: data/interim/dirs_county_rows_fips.parquet, with out_unattributed and
out_overattributed carried through (checked by carried.require_carried).
"""
import re
import unicodedata

import pandas as pd

from carried import require_carried
from config import INTERIM, RAW, ROOT, STUDY_STATES

CENSUS_FILE = RAW / "census" / "national_county2020.txt"
EXCEPTIONS = ROOT / "manifest" / "fips_exceptions.csv"
SCOPE = ROOT / "manifest" / "out_of_scope_areas.csv"
STATE_CODES = {"AL": "Alabama", "AR": "Arkansas", "DC": "District of Columbia", "DE": "Delaware", "FL": "Florida",
               "GA": "Georgia", "IL": "Illinois", "IN": "Indiana", "KY": "Kentucky", "LA": "Louisiana",
               "MD": "Maryland", "MO": "Missouri", "MS": "Mississippi", "NC": "North Carolina", "NJ": "New Jersey",
               "NM": "New Mexico", "NY": "New York", "OH": "Ohio", "OK": "Oklahoma", "PA": "Pennsylvania",
               "PR": "Puerto Rico", "SC": "South Carolina", "TN": "Tennessee", "TX": "Texas", "VA": "Virginia",
               "VI": "U.S. Virgin Islands", "WV": "West Virginia"}


def key(name) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"\s+(county|parish|municipio)$", "", s)
    s = re.sub(r"\bste\.?\s", "sainte ", s)
    s = re.sub(r"\bst\.?\s", "saint ", s)
    return re.sub(r"[^a-z]", "", s)


def read_census() -> pd.DataFrame:
    return pd.read_csv(CENSUS_FILE, sep="|", dtype=str)


def crosswalk(names: pd.DataFrame, census: pd.DataFrame, exceptions: pd.DataFrame) -> pd.DataFrame:
    """One row per distinct (state, county) in names, with fips and how it was matched."""
    c = census.assign(state=census.STATE.map(STATE_CODES), k=census.COUNTYNAME.map(key),
                      fips=census.STATEFP + census.COUNTYFP)
    c = c.dropna(subset=["state"])
    known = set(census.STATEFP + census.COUNTYFP)
    for e in exceptions.itertuples():
        if e.fips not in known:
            raise SystemExit(f"exception {e.state}/{e.dirs_county_name}: {e.fips} is not in the Census county file")
    ex = {(e.state, key(e.dirs_county_name)): e.fips for e in exceptions.itertuples()}
    lookup = {}
    for r in c.itertuples():
        lookup.setdefault((r.state, r.k), set()).add(r.fips)
    out, used, missing = [], set(), []
    for state, county in names[["state", "county"]].drop_duplicates().itertuples(index=False):
        k = (state, key(county))
        if k in ex:
            out.append((state, county, ex[k], "exception"))
            used.add(k)
        elif len(lookup.get(k, ())) == 1:
            out.append((state, county, next(iter(lookup[k])), "name"))
        else:
            missing.append(f"{state}/{county}")
    if missing:
        raise SystemExit(f"no FIPS for {', '.join(missing)}: add to manifest/fips_exceptions.csv")
    unused = [f"{s}/{e.dirs_county_name}" for e in exceptions.itertuples() for s in [e.state]
              if (s, key(e.dirs_county_name)) not in used]
    if unused:
        raise SystemExit(f"exception not used: {', '.join(unused)}")
    return pd.DataFrame(out, columns=["state", "county", "fips", "fips_match"])


def apply_scope(rows: pd.DataFrame, scope: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop the (storm, state) pairs in manifest/out_of_scope_areas.csv. Each entry must drop at least one row."""
    drop = pd.Series(False, index=rows.index)
    for e in scope.itertuples():
        hit = (rows.row_nhc_id == e.nhc_id) & (rows.state == e.state)
        if not hit.any():
            raise SystemExit(f"scope entry {e.nhc_id}/{e.state} drops no rows")
        drop |= hit
    return rows[~drop], rows[drop]


def scope_table(rows: pd.DataFrame, study_states) -> pd.DataFrame:
    """Every (storm, state) with county rows in a state outside the study states. Generated, never typed."""
    out = rows[~rows.state.isin(study_states)].groupby(["row_nhc_id", "row_storm", "state"]).size()
    out = out.reset_index(name="rows").rename(columns={"row_nhc_id": "nhc_id", "row_storm": "storm_name"})
    return out.assign(reason="outside config.STUDY_STATES").sort_values(["nhc_id", "state"], ignore_index=True)


def main():
    all_rows = pd.read_parquet(INTERIM / "dirs_county_rows.parquet")
    scope = scope_table(all_rows, STUDY_STATES)
    scope.to_csv(SCOPE, index=False, lineterminator="\n")  # generated record of what is dropped
    rows, dropped = apply_scope(all_rows, scope)
    print(f"out of scope: {len(dropped)} rows dropped ({dropped.groupby(['row_storm', 'state']).size().to_dict()})")
    xw = crosswalk(rows, read_census(), pd.read_csv(EXCEPTIONS, dtype=str))
    out = rows.merge(xw, on=["state", "county"], how="left", validate="many_to_one")
    assert out.fips.notna().all() and len(out) == len(rows)
    require_carried(out, "dirs_county_rows_fips")
    out.to_parquet(INTERIM / "dirs_county_rows_fips.parquet", index=False)
    xw.to_csv(INTERIM / "fips_crosswalk.csv", index=False, lineterminator="\n")
    dup = out.groupby(["doc_id", "fips"]).size()
    print(f"{len(rows)} rows, {len(xw)} distinct names -> {xw.fips.nunique()} counties; "
          f"{(xw.fips_match == 'exception').sum()} by exception; {int((dup > 1).sum())} report-county pairs on one FIPS twice")


if __name__ == "__main__":
    main()
