---
draft: false
title: "Who files the most severe-injury reports? It depends on how you count employers"
date: 2026-11-19
updated: 2026-11-19
summary: "A worked data audit of OSHA's Severe Injury Reports: the raw file lists 71,454 employer names; after removing duplicates, normalizing names and matching variants, it is about 56,083 employers, and the top of the ranking changes completely. Counts of reports filed are not a safety ranking."
method: >-
  Step by step, each step's effect reported: same-incident duplicates
  removed by a stated rule and confirmed by hand; employer names normalized
  (case, punctuation, legal suffixes, "dba", store numbers); fuzzy entity
  resolution (rapidfuzz) blocked by state, with cross-state matching only
  for employers present in five or more states and a hand-approved list of
  national aliases; matcher precision and recall estimated from a
  stratified sample of 300 labeled candidate pairs.
data_sources:
  - name: "U.S. Department of Labor, OSHA, Severe Injury Reports, January 2015 to November 2025"
    url: "https://www.osha.gov/severe-injury-reports"
  - name: "OSHA State Plans (jurisdiction)"
    url: "https://www.osha.gov/stateplans"
  - name: "Company Form 10-K filings (SEC EDGAR) and the U.S. Postal Service FY2024 Form 10-K (headcounts)"
    url: "https://www.sec.gov/edgar/search/"
download: "/static/data/osha-employer-waterfall.csv"
figures:
  - id: fig-1
    type: waterfall
    data: osha-employer-waterfall.csv
    x: step
    y: value
    title: "Most of the distortion is in the names, not the duplicates"
    caption: "Distinct employers in OSHA's Severe Injury Reports, counted by name: the raw count, the change at each audit step, and the final count. The data table also gives the count by name and state after each step."
    source: "OSHA Severe Injury Reports, January 2015 – November 2025."
    source_url: "https://www.osha.gov/severe-injury-reports"
    data_public: true
    verified: true    # every value checked against results/*.json
---

## Question

Which employers file the most severe-injury reports with OSHA — and can
you trust the obvious way of counting them?

## Data

OSHA's Severe Injury Reports: 105,996 reports of amputations, in-patient
hospitalizations and losses of an eye, January 2015 to November 2025.
**They cover federal-OSHA jurisdictions only; states with their own
OSHA-approved State Plans are not included.** 2,492 reports carry the file's
undocumented `FederalState = 0` flag, mostly in State Plan states; they
appear as a separate line wherever they matter. Reports dipped from
11,065 in 2019 to 8,908 in 2020, which reflects the pandemic, not a safety trend.
Everything below counts **reports filed**.

## Design

I counted reports by employer the obvious way, then repeated the count after
each cleaning step, measuring what each step changed.

## Result

**Counted by the raw employer field, the file lists 71,454 employers; after
cleaning it is 56,083 by name, or 65,923 if identical names in different states
count separately.** How many employers filed reports depends on the
definition — identical names in different states are usually different
small firms, but the same company for national employers.

[figure:fig-1]

**Duplicates are a minor issue here.** No row is an exact copy of another. A
stated rule found same-incident pairs filed twice by the same employer;
depending on how strict the rule is, 16 to 73 pairs qualify (42
under the rule I used), because the count depends on the matching rule.
After checking each one by hand, 39 of 105,996 reports were merged. Two
merges were judgment calls (XPO Logistics, 5/3/2019; VA John D. Dingell
Medical Center, 5/2/2019: same machine or door and day, a different finger
recorded), and three pairs were kept apart as two workers. A merged report
keeps the lowest report number and the higher injury counts of the two.

**The larger distortion is in employer names.** Normalizing case,
punctuation, legal suffixes, "dba" and store numbers removes
14,312 names; fuzzy matching removes 1,034 more; a short, hand-approved list of
national aliases (USPS for U.S. Postal Service, store formats such as
Walmart Supercenter) removes 15. Names that refer to the same operating
employer merge (store formats and locations, acronyms); separate legal
operating companies stay separate (FedEx Freight vs FedEx; subsidiaries vs
parents).

| Rank | Raw employer field | Reports | Resolved employer | Reports | % of reports | Name variants | States |
|---|---|---|---|---|---|---|---|
| 1 | U.S. Postal Service | 548 | U.S. Postal Service | 1,320 | 1.25 | 35 | 50 |
| 2 | United States Postal Service | 290 | Walmart | 866 | 0.82 | 296 | 29 |
| 3 | UPS | 245 | UPS | 637 | 0.60 | 36 | 28 |
| 4 | U.S. POSTAL SERVICE | 148 | Lowe's Home Centers, LLC | 241 | 0.23 | 74 | 25 |
| 5 | United Parcel Service | 134 | Publix Super Markets, Inc. | 214 | 0.20 | 33 | 3 |
| 6 | Walmart | 126 | Tyson Foods, Inc. | 201 | 0.19 | 17 | 13 |
| 7 | USPS | 112 | Kroger | 167 | 0.16 | 48 | 10 |
| 8 | United Parcel Service, Inc. | 109 | Target Corporation | 131 | 0.12 | 22 | 26 |
| 9 | Walmart, Inc. | 109 | Walt Disney Parks and Resorts U.S., Inc. | 131 | 0.12 | 24 | 1 |
| 10 | US Postal Service | 87 | American Airlines | 129 | 0.12 | 11 | 11 |
| 11 | Walmart Supercenter | 83 | FedEx Freight | 127 | 0.12 | 27 | 25 |
| 12 | Publix Super Markets, Inc. | 82 | Menard, Inc. | 115 | 0.11 | 14 | 8 |
| 13 | Tyson Foods, Inc. | 70 | Home Depot | 112 | 0.11 | 32 | 20 |
| 14 | Lowe's Home Centers, LLC | 69 | International Paper Company | 112 | 0.11 | 8 | 16 |
| 15 | DHL Supply Chain | 65 | AT&T | 110 | 0.10 | 16 | 15 |
| — | `FederalState = 0` reports | 2,492 | `FederalState = 0` reports | 2,491 | — | — | — |

The raw top 15 is really six organizations: the Postal Service alone fills
five places under five spellings.

**How good is the matching?** The matcher is precise but conservative.
Of 150 merges it made, 145 were right: precision 96.7% (95% Wilson
interval 92.4% to 98.6%). It finds an estimated 47.7% of true
matches (95% stratified-bootstrap interval 38.1% to 61.5%). In the band just
above the threshold, nearly all misses are typos inside common words that
the distinctive-part check rejects ("Manufacturin", "Distibution",
"Serive"); but the larger estimated share is pairs scoring just under the
threshold, a mix of typos and variants such as "+" vs "and" — and that
share rests on few labeled matches, so it is uncertain. The missed matches
mean the employer count above is overstated by at most about
2.0% (1.2–3.0%). If every judgment-call label flipped, recall would be
50.2%. In the lowest score band none of 50 sampled pairs matched; if
the true rate there were at its upper 95% bound, recall would be
28.2%. The rule was not tuned on these labels.
Accuracy figures are illustrative: they were estimated against match
labels drafted by an AI model. In client work, labels are checked by hand.

**A count ranking is not a safety ranking.** Report counts track how big an
employer is, among other things. As an illustration only, here are the
ten largest filers next to their own reported headcounts. Headcounts are
national (or company-wide) and for one fiscal year; the reports cover
federal-OSHA states only and span 2015–2025. So this is not a rate
comparison and not a safety ranking. The association is loose: industry,
and how much of a workforce sits in federal-OSHA states, matter too.

| Employer | Reports, 2015–2025 | Headcount | What the headcount covers | Source |
|---|---|---|---|---|
| U.S. Postal Service | 1,320 | 639,000 | Total (substantially all U.S.) | U.S. Postal Service, FY2024 Form 10-K (Sept 30, 2024) |
| Walmart | 866 | 1,600,000 | U.S. associates | Walmart Inc., Form 10-K, fiscal 2025 (Jan 31, 2025) |
| UPS | 637 | 406,000 | U.S. employees (excl. temporary seasonal) | United Parcel Service, Inc., Form 10-K, 2024 (FY2024) |
| Lowe's Home Centers, LLC | 241 | 270,000 | Total full- + part-time (mainly U.S.; no U.S. split) | Lowe's Companies, Inc., Form 10-K, fiscal 2024 (Jan 31, 2025) |
| Publix Super Markets, Inc. | 214 | 255,000 | Total (stated as 'more than') | Publix Super Markets, Inc., Form 10-K, 2024 (Dec 28, 2024) |
| Tyson Foods, Inc. | 201 | 120,000 | U.S. team members (all Tyson entities) | Tyson Foods, Inc., Form 10-K, fiscal 2024 (Sept 28, 2024) |
| Kroger | 167 | 409,000 | Total (stated as 'over') | The Kroger Co., Form 10-K, fiscal 2024 (Feb 1, 2025) |
| Target Corporation | 131 | 440,000 | Total incl. seasonal | Target Corporation, Form 10-K, fiscal 2024 (Feb 1, 2025) |
| Walt Disney Parks and Resorts U.S., Inc. | 131 | 171,000 | Disney company-wide U.S. — NO parks figure is published; not comparable | The Walt Disney Company, Form 10-K, fiscal 2024 (Sept 28, 2024) |
| American Airlines | 129 | 133,300 | Group total, full-time equivalents | American Airlines Group Inc., Form 10-K, 2024 (Dec 31, 2024) |

## What this does not show

- **Which employers are safer.** Counts reflect size, industry and
  federal-OSHA coverage; State Plan states are missing entirely, and state
  totals reflect coverage and workforce size, not relative safety.
- **A complete entity map.** The matcher misses some true matches and keeps
  subsidiaries apart from parents by design; other definitions would give
  other counts.
- **Unreported injuries.** The file holds what employers reported.

## If this were your data

Before a number like "reports per employer" drives a decision, I would find
out what it is actually counting: the duplicates, the spellings, the
definitions and the coverage — and say how much each one moves the answer.
