r"""Future-research feasibility check (Tim, 2026-11-19): can the top 25
resolved employers be linked to OSHA ITA Form 300A establishment data for
2023, within federal-OSHA private-sector jurisdictions? One year only. No
rates are computed or published from this.

Jurisdiction: OSHA's State Plans page marks states with a full (private +
public sector) State Plan with one asterisk and public-sector-only plans with
two. Federal OSHA covers the private sector everywhere except the
one-asterisk states, so ITA establishments in one-asterisk states are
dropped (private-sector establishments in two-asterisk states stay).

Linking: an ITA row is linked to an employer if the normalized company_name
or establishment_name equals the normalized form of any of that employer's
raw names in the severe-injury data; then every ITA row sharing a linked
non-blank EIN is added ("EIN expansion").

    .venv\Scripts\python -m osha_audit.src.ita_feasibility
"""
import re
import zipfile
from pathlib import Path

import pandas as pd
import requests

from common import manifest
from osha_audit.src.naive import save_results
from osha_audit.src.normalize import name_key

ROOT = Path(__file__).resolve().parents[2]
ITA_ZIP = ROOT / "data/raw/ita_300a_2023_through_12-31-2024.zip"
PLANS_URL = "https://www.osha.gov/stateplans"
PLANS_RAW = ROOT / "data/raw/osha_stateplans_page.html"
HEADERS = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "Chrome/142.0 Safari/537.36"), "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
ABBR = {"Alabama": "AL", "Alaska": "AK", "American Samoa": "AS", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Guam": "GU", "Hawaii": "HI",
        "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
        "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
        "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
        "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Northern Mariana Islands": "MP", "Ohio": "OH",
        "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Puerto Rico": "PR",
        "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN",
        "Texas": "TX", "U.S. Virgin Islands": "VI", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
        "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"}


def parse_state_plans(text):
    """From the page text 'Select a State Alabama Alaska* ... Wyoming*',
    return (full_plan_states, public_only_states) as postal codes."""
    full, public = set(), set()
    for name, code in ABBR.items():
        m = re.search(re.escape(name) + r"(\*{1,2})(?!\w)", text)
        if m:
            (public if m.group(1) == "**" else full).add(code)
    return full, public


def link_employer(ita, raw_names):
    """Rows of `ita` linked to an employer by normalized name, then by EIN.
    Returns (linked rows, n by name, n added by EIN)."""
    keys = {name_key(n) for n in raw_names}
    by_name = ita[ita.company_key.isin(keys) | ita.establishment_key.isin(keys)]
    eins = {e for e in by_name.ein if e.strip()}
    linked = ita[ita.index.isin(by_name.index) | ita.ein.isin(eins)]
    return linked, len(by_name), len(linked) - len(by_name)


def main(top=25):
    r = requests.get(PLANS_URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    PLANS_RAW.write_bytes(r.content)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r.text))
    full, public = parse_state_plans(text)
    manifest.record(PLANS_RAW, PLANS_URL, rows=len(full) + len(public))
    if len(full) != 22 or len(public) != 7:
        raise SystemExit(f"state-plan parse gave {len(full)} full / {len(public)} public-only, expected 22 / 7")

    with zipfile.ZipFile(ITA_ZIP) as z:
        member = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        ita = pd.read_csv(z.open(member), dtype=str, keep_default_na=False, encoding_errors="replace")
    ita = ita[~ita.state.isin(full)].copy()
    ita["company_key"] = ita.company_name.map(name_key)
    ita["establishment_key"] = ita.establishment_name.map(name_key)

    res = pd.read_csv(ROOT / "data/interim/osha_resolved.csv", dtype=str, keep_default_na=False)
    top_ids = res.groupby("employer_id").size().sort_values(ascending=False).head(top).index
    rows = []
    for eid in top_ids:
        sub = res[res.employer_id == eid]
        linked, n_name, n_ein = link_employer(ita, sub.Employer.unique())
        rows.append({"employer": sub.employer_label.iloc[0], "sir_reports_2015_2025": int(len(sub)),
                     "ita_establishments_linked": int(len(linked)), "linked_by_name": n_name,
                     "added_by_ein": n_ein, "distinct_eins": int(linked.ein[linked.ein.str.strip() != ""].nunique()),
                     "ita_states": int(linked.state.nunique()),
                     "linked": bool(len(linked))})
    t = pd.DataFrame(rows)
    postal = ita[ita.company_name.str.contains("postal", case=False) |
                 ita.establishment_name.str.contains("postal", case=False)]
    payload = {"year": 2023, "ita_rows_total": None, "full_plan_states": sorted(full),
               "public_only_plan_states": sorted(public),
               "ita_rows_federal_private_jurisdiction": int(len(ita)),
               "ein_blank_share": float((ita.ein.str.strip() == "").mean()),
               "top_employers": t.to_dict(orient="records"),
               "top_linked": int(t.linked.sum()), "top_n": top,
               "postal_rows": int(len(postal)),
               "postal_examples": postal[["company_name", "establishment_name", "state", "establishment_type"]]
                                  .head(8).to_dict(orient="records")}
    save_results("ita_feasibility_2023", payload)
    return payload, t


if __name__ == "__main__":
    import json
    p, t = main()
    print(json.dumps({k: v for k, v in p.items() if k not in ("top_employers",)}, indent=1))
    print(t.to_string(index=False))
