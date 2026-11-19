"""Analysis panel: PUMS state-year rates joined to expansion cohorts."""
import pandas as pd

MAIN_YEARS = (2009, 2019)
MAIN_COHORTS = (2014, 2015, 2016, 2019)


def build_panel(rates, expansion, fips_names):
    """rates: year, fips, *_rate, *_pop ... ; expansion: state,
    first_treated_year, prior_coverage_kaestner; fips_names: fips, state.
    Returns the joined panel with `cohort` (first treated year; 0 = never
    treated by the end of the data)."""
    e = expansion.merge(fips_names, on="state", how="left", validate="one_to_one")
    if e["fips"].isna().any():
        raise ValueError(f"no FIPS for: {e.loc[e.fips.isna(), 'state'].tolist()}")
    p = rates.merge(e[["fips", "state", "first_treated_year", "prior_coverage_kaestner"]],
                    on="fips", how="left", validate="many_to_one")
    if p["state"].isna().any():
        raise ValueError("rates contain FIPS codes with no expansion record")
    p["cohort"] = p["first_treated_year"].fillna(0).astype(int)
    return p


def main_window_group(cohort, main_cohorts=MAIN_COHORTS, last_year=MAIN_YEARS[1]):
    """Label used in the main 2009–2019 analysis: the cohort year if it is a
    main cohort, else 'untreated through 2019' (later adopters and never)."""
    if cohort in main_cohorts:
        return str(cohort)
    if cohort == 0 or cohort > last_year:
        return "untreated through 2019"
    raise ValueError(f"cohort {cohort} is neither a main cohort nor after {last_year}")


def weighted_group_rates(panel, group_col, rate="lowinc_rate", pop="lowinc_pop"):
    """Population-weighted mean rate by group and year (percent)."""
    g = panel.assign(_num=panel[rate] * panel[pop])
    out = g.groupby([group_col, "year"]).agg(num=("_num", "sum"), den=(pop, "sum"),
                                              states=("fips", "nunique"))
    out["rate_pct"] = 100 * out["num"] / out["den"]
    return out[["rate_pct", "states"]].reset_index()
