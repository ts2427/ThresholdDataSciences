"""Give every county row its storm key: NHC ID plus DIRS activation date.

Normally a row takes the key of the report's storm. In reports shared by two storms (Ida and Nicholas, from
Sep 15, 2021), a county that the second storm's notice added takes the second storm's key. A county that was
already in the first storm's area stays with it and is flagged. Values are never split between storms.
The county lists come from manifest/shared_report_counties.csv (step 2b).
"""
from __future__ import annotations

import difflib
import re

import pandas as pd

SPELLING_CUTOFF = 0.9


def _key(name) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+(county|parish)\s*$", "", str(name).lower().strip()))


def assign_storm_keys(rows: pd.DataFrame, shared: pd.DataFrame, storms: pd.DataFrame) -> pd.DataFrame:
    by_name = storms.set_index("storm_name")
    rows = rows.copy()
    rows["row_storm"] = rows.storm_name
    rows["row_nhc_id"] = rows.nhc_id
    rows["row_dirs_activation_date"] = rows.storm_name.map(by_name.dirs_activation_date)
    rows["storm_key_flag"] = ""
    for notice, g in shared.groupby("notice"):
        page = g.storm_page.iloc[0]
        first_storms = set(storms[storms.storm_page == page].storm_name) - set(g[g.flag == ""].assigned_storm)
        lookup = {(s, _key(c)): r for s, c, r in zip(g.state, g.county, g.to_dict("records"))}
        applies = rows.storm_name.isin(first_storms) & (rows.report_date >= g.applies_from.iloc[0])
        for i in rows.index[applies]:
            state, key = rows.at[i, "state"], _key(rows.at[i, "county"])
            keys = [k for s, k in lookup if s == state]
            near = key if key in keys else next(iter(difflib.get_close_matches(key, keys, 1, SPELLING_CUTOFF)), None)
            if near is None:
                continue
            hit = lookup[(state, near)]
            if hit["flag"]:
                rows.at[i, "storm_key_flag"] = hit["flag"]
            else:
                rows.at[i, "row_storm"] = hit["assigned_storm"]
                rows.at[i, "row_nhc_id"] = hit["assigned_nhc_id"]
                rows.at[i, "row_dirs_activation_date"] = by_name.loc[hit["assigned_storm"], "dirs_activation_date"]
    return rows
