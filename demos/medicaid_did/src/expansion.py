"""Medicaid expansion dates: parse KFF's State Health Facts table and code
each state's first treated year for annual ACS data.

Treatment-year rule (see docs/decisions.md): the ACS interviews people
throughout the calendar year and asks about coverage at the time of the
interview. A state is coded as first treated in the calendar year of its
expansion's effective date if that date is on or before July 1 (coverage in
force for at least half the year), otherwise in the following year.
"""
import html
import re
from datetime import date, datetime

import pandas as pd

KFF_URL = ("https://www.kff.org/health-reform/state-indicator/"
           "state-activity-around-expanding-medicaid-under-the-affordable-care-act/")
KAESTNER_SRC = ("Kaestner, Garrett, Gangopadhyaya & Fleming (2016), NBER WP 21836 "
                "(rev. Sept 2016), Table 1, p. 32")

# Kaestner et al. Table 1: states that covered low-income adults before
# 2014. Categorical labels only — copied from the table, cited in `source`.
PRIOR_FULL = {"Delaware", "District of Columbia", "Massachusetts", "New York", "Vermont"}
PRIOR_LIMITED_NONEXP_2014 = {"Indiana", "Maine", "Tennessee", "Wisconsin"}
PRIOR_PARTIAL_EXP_2014 = {"Arizona", "California", "Connecticut", "Colorado", "Hawaii",
                          "Illinois", "Iowa", "Maryland", "Minnesota", "New Jersey",
                          "Oregon", "Rhode Island", "Washington"}

_ROW = re.compile(r"<tr><td>(.*?)</td><td>(.*?)</td><td>(.*?)</td>", re.S)


def parse_kff_table(page_html):
    """Return one row per state + DC: state, status, effective_date (date or
    NaT). Skips the 'United States' summary row. Raises if the table does
    not hold exactly 51 jurisdictions."""
    start = page_html.find("Expansion Implementation Date")
    if start < 0:
        raise ValueError("KFF table header not found")
    body = page_html[start:page_html.find("</tbody>", start)]
    rows = []
    for name, status, eff in _ROW.findall(body):
        name, status, eff = (html.unescape(x).strip() for x in (name, status, eff))
        if name == "United States":
            continue
        d = datetime.strptime(eff, "%m/%d/%Y").date() if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", eff) else None
        if status == "Adopted" and d is None:
            raise ValueError(f"{name}: adopted but no parsable date ({eff!r})")
        rows.append({"state": name, "status": status, "effective_date": d})
    df = pd.DataFrame(rows)
    if len(df) != 51 or df["state"].duplicated().any():
        raise ValueError(f"expected 51 unique jurisdictions, got {len(df)}")
    return df


def treatment_year(effective, cutoff=(7, 1)):
    """First treated ACS year: the effective date's year if the date is on
    or before July 1, else the next year. None for never-treated."""
    if effective is None or pd.isna(effective):
        return None
    if isinstance(effective, str):
        effective = date.fromisoformat(effective)
    return effective.year if (effective.month, effective.day) <= cutoff else effective.year + 1


def prior_coverage(state):
    """Pre-2014 coverage of low-income adults per Kaestner et al. Table 1."""
    if state in PRIOR_FULL:
        return "prior_full"
    if state in PRIOR_LIMITED_NONEXP_2014 or state in PRIOR_PARTIAL_EXP_2014:
        return "prior_limited"
    return "none"


def build_expansion_table(page_html, accessed):
    df = parse_kff_table(page_html)
    df["first_treated_year"] = [treatment_year(d) for d in df["effective_date"]]
    df["first_treated_year"] = df["first_treated_year"].astype("Int64")
    df["prior_coverage_kaestner"] = df["state"].map(prior_coverage)
    df["source"] = (f"KFF State Health Facts, 'Status of State Action on the Medicaid "
                    f"Expansion Decision' (November 2026), {KFF_URL}, accessed {accessed}")
    df.loc[df["prior_coverage_kaestner"] != "none", "source"] += f"; prior coverage: {KAESTNER_SRC}"
    return df
