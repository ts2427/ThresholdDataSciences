"""ACS 1-year PUMS: person records -> state-year uninsured rates for adults
19–64, with one definition in every year (the published table C27016
changes its age band from 18–64 to 19–64 in 2017; see docs/decisions.md).

Universe, matching C27016 as closely as PUMS allows: people for whom
poverty status is determined (POVPIP present, 0–501), excluding active-duty
military (MIL == 1), who are outside the civilian population.

  low-income: POVPIP <= 137  (income under 138% of the poverty line)
  uninsured:  HICOV == 2
  weights:    PWGTP (person weight); rates are weighted shares.
"""
import pandas as pd

VARS = ["PWGTP", "AGEP", "POVPIP", "HICOV", "MIL"]
YEARS = [y for y in range(2009, 2025) if y != 2020]   # 2025 PUMS not on the API yet
STATE_FIPS = ["01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15",
              "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27",
              "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39",
              "40", "41", "42", "44", "45", "46", "47", "48", "49", "50", "51", "53",
              "54", "55", "56"]


def records_to_frame(api_json):
    """Census API JSON (header row + rows of strings) -> numeric DataFrame.
    Blank or non-numeric values become NaN (e.g. POVPIP for people without
    a poverty status)."""
    header, rows = api_json[0], api_json[1:]
    df = pd.DataFrame(rows, columns=header)
    # A variable used both in get= and as a predicate (AGEP) comes back
    # twice. Keep one copy, after checking the copies agree.
    for name in set(c for c in header if header.count(c) > 1):
        copies = df.loc[:, df.columns == name]
        if not copies.nunique(axis=1).le(1).all():
            raise ValueError(f"duplicate column {name} with differing values")
    df = df.loc[:, ~df.columns.duplicated()]
    for c in VARS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def in_universe(df):
    """Boolean mask: age 19–64, poverty status determined, not active duty."""
    return (df["AGEP"].between(19, 64)
            & df["POVPIP"].between(0, 501)
            & (df["MIL"] != 1))


def aggregate(df):
    """Weighted population, uninsured and rate for the low-income and
    all-adult groups within the universe."""
    u = df[in_universe(df)]
    if (u["HICOV"].isin([1, 2]) == False).any():  # noqa: E712
        raise ValueError("HICOV has values other than 1/2 inside the universe")
    out = {}
    for group, mask in (("lowinc", u["POVPIP"] <= 137), ("all", pd.Series(True, index=u.index))):
        g = u[mask]
        pop = float(g["PWGTP"].sum())
        un = float(g.loc[g["HICOV"] == 2, "PWGTP"].sum())
        out[f"{group}_pop"] = pop
        out[f"{group}_uninsured"] = un
        out[f"{group}_rate"] = un / pop if pop else float("nan")
        out[f"{group}_n"] = int(len(g))
    return out
