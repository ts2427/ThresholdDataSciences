# Future research note: linking severe-injury reports to ITA Form 300A data

*Status: feasibility check only (2023, one year, top 25 employers).
Not part of the published demo; no rates are computed or published from it.
Figures below are generated from `results/osha_audit.json`
(`ita_feasibility_2023`) by `osha_audit/src/ita_feasibility.py`.*

## Why

Severe-injury report counts track employer size, so a count ranking is not a
safety ranking. OSHA's Injury Tracking Application (ITA) collects Form 300A
summaries by establishment — including `annual_average_employees` and
`total_hours_worked` — and is the natural denominator from the same agency.

## What was checked

- ITA 300A summary data for calendar 2023 (file
  `ITA_300A_Summary_Data_2023_through_12-31-2024.zip`, 394,234
  establishments; see manifest).
- Jurisdiction matched to the severe-injury data: OSHA's State Plans page
  lists 22 full State Plans
  (AK, AZ, CA, HI, IA, IN, KY, MD, MI, MN, NC, NM, NV, OR, PR, SC, TN, UT, VA, VT, WA, WY) and 7 public-sector-only plans
  (CT, IL, MA, ME, NJ, NY, VI). Dropping establishments in the full-plan
  states leaves 221,296 establishments under federal OSHA
  for the private sector.
- Link rule: exact match on the normalized company or establishment name
  (step-3b normalization), then every establishment sharing a linked EIN.

## What is linkable

19 of the top 25 resolved employers link to at least one 2023 ITA
establishment in federal-OSHA jurisdiction.

| Employer | Severe-injury reports (2015–2025) | ITA establishments linked | by name | added by EIN | EINs |
|---|---|---|---|---|---|
| U.S. Postal Service | 1,320 | 5,668 | 5,668 | 0 | 1 |
| Walmart | 866 | 783 | 783 | 0 | 1 |
| UPS | 637 | 773 | 773 | 0 | 1 |
| Lowe's Home Centers, LLC | 241 | 0 | 0 | 0 | 0 |
| Publix Super Markets, Inc. | 214 | 1,186 | 1,186 | 0 | 1 |
| Tyson Foods, Inc. | 201 | 0 | 0 | 0 | 0 |
| Kroger | 167 | 299 | 2 | 297 | 1 |
| Walt Disney Parks and Resorts U.S., Inc. | 131 | 3 | 3 | 0 | 1 |
| Target Corporation | 131 | 1,243 | 1,243 | 0 | 1 |
| American Airlines | 129 | 0 | 0 | 0 | 0 |
| FedEx Freight | 127 | 312 | 312 | 0 | 1 |
| Menard, Inc. | 115 | 293 | 293 | 0 | 1 |
| International Paper Company | 112 | 103 | 94 | 9 | 2 |
| Home Depot | 112 | 1,131 | 1,131 | 0 | 1 |
| AT&T | 110 | 0 | 0 | 0 | 0 |
| FedEx Ground | 109 | 833 | 414 | 419 | 3 |
| Pilgrim's Pride Corporation | 99 | 47 | 26 | 21 | 3 |
| Asplundh Tree Expert Company | 98 | 33 | 23 | 10 | 1 |
| Costco Wholesale | 86 | 301 | 301 | 0 | 1 |
| Walgreens | 85 | 0 | 0 | 0 | 0 |
| Capstone Logistics, LLC | 84 | 172 | 107 | 65 | 1 |
| Charter Communications | 83 | 67 | 67 | 0 | 1 |
| Frito Lay | 80 | 119 | 119 | 0 | 1 |
| Tyson Fresh Meats | 78 | 31 | 31 | 0 | 1 |
| XPO Logistics | 76 | 0 | 0 | 0 | 0 |

EIN expansion matters: Kroger links by name at only 2 establishments, and
the shared EIN adds 297.

## Coverage gaps found

1. **Not linked by name: Lowe's Home Centers, LLC, Tyson Foods, Inc., American Airlines, AT&T, Walgreens, XPO Logistics.** Causes seen in the ITA names:
   Tyson files under operating subsidiaries (Tyson Fresh Meats, Tyson
   Poultry, Tyson Farms); XPO under "XPO Logistics Freight Inc."; Walgreens
   under "Walgreen Co. …"; no establishment named for American Airlines or
   AT&T was found; Lowe's Home Centers was not found ("Lowes Foods" is a
   different company).
2. **Under-linking through legal subsidiaries.** Walmart's ITA records are
   mostly filed as "Wal-Mart Stores East, LP" and "Wal-Mart Stores Texas,
   LLC"; the name link caught only the "Walmart Inc." records. A
   company-level denominator needs a legal-entity map (parent → filing
   subsidiaries), which conflicts with the demo's entity principle
   (subsidiaries stay separate) and would have to be decided explicitly.
3. **USPS is present but miscoded**: 5,678 establishments in federal-OSHA
   jurisdiction mention "postal"; US Postal Service records carry
   `establishment_type` 2 ("State Government entity"). Usable, with a
   documented recode.
4. **EIN is blank** on 10% of establishments in scope, limiting
   EIN expansion.
5. **ITA covers only some establishments**: required from those with 250+
   employees outside exempt industries and 20–249 in designated industries;
   others may submit voluntarily. Missing establishments understate a
   company's hours and overstate any rate, unevenly across industries.

## What a full linkage would take

- ITA summary files for 2016–2024 (nine years), with the same jurisdiction
  filter each year.
- A parent → filing-entity map for each employer studied, built from ITA
  company names and EINs and checked by hand; a decision on how it squares
  with the subsidiaries-separate principle.
- Establishment-level matching of severe-injury reports to ITA
  establishments by address and name (not just company totals), with a
  hand-checked sample for link precision and recall.
- Year alignment (severe-injury reports by event date; ITA by calendar
  year) and an explicit treatment of establishments that never submit.
- Rates reported only with intervals and with the coverage caveats above.

Estimated effort: several weeks for a defensible version; a company-level
version for ~25 employers with hand-built entity maps is a few days.
