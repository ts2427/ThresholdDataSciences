---
draft: false
title: "Did Medicaid expansion reduce uninsurance among low-income adults?"
date: 2026-11-19
updated: 2026-11-19
summary: "A worked example of a staggered difference-in-differences analysis on public Census data: Medicaid expansion lowered the uninsured rate among adults under 138% of the poverty line by about 7.2 percentage points (95% interval 4.6 to 9.7)."
method: >-
  Callaway–Sant'Anna difference-in-differences (R did 2.5.1), states that
  expanded in 2014, 2015, 2016 or 2019 compared with states not yet treated
  and never treated, 2009–2019, doubly robust, weighted by each state's
  low-income adult population, standard errors clustered by state with a
  multiplier bootstrap. The analysis plan, including the headline estimand,
  robustness checks and benchmarks, was written and committed before any
  estimator was run. Sensitivity to pre-trend violations: HonestDiD
  relative-magnitudes bounds.
data_sources:
  - name: "U.S. Census Bureau, American Community Survey 1-year Public Use Microdata Sample, 2009–2019 and 2021–2024 (Census Data API)"
    url: "https://api.census.gov/data/2019/acs/acs1/pums"
  - name: "KFF State Health Facts, Status of State Action on the Medicaid Expansion Decision (November 2026)"
    url: "https://www.kff.org/health-reform/state-indicator/state-activity-around-expanding-medicaid-under-the-affordable-care-act/"
  - name: "U.S. Census Bureau, ACS table C27016 (used to check the microdata, 2017–2019)"
    url: "https://api.census.gov/data/2019/acs/acs1/groups/C27016.html"
download: "/static/data/medicaid-event-study.csv"
figures:
  - id: fig-1
    type: interval
    data: medicaid-event-study.csv
    x: year_relative_to_expansion
    y: estimate_pp
    lo: ci95_low
    hi: ci95_high
    signal_before: 0
    x_label: "Years relative to expansion (−1 = reference year)"
    title: "Uninsurance fell after expansion and kept falling"
    caption: "Change in the uninsured rate among adults 19–64 under 138% of the poverty line, expansion states vs. comparison states, percentage points, with 95% intervals. Year −1 is the reference. Later years rest on fewer states: year 5 is the 2014 states only."
    source: "ACS 1-year PUMS via the Census Data API; expansion dates from KFF."
    source_url: ""
    data_public: true
    verified: true    # every value checked against results/*.json
  - id: fig-2
    type: column
    data: medicaid-naive-vs-careful.csv
    x: comparison
    y: decline_pp
    title: "Without a comparison group, the effect looks 2.3 times larger"
    caption: "Fall in the uninsured rate, 2013 to the 2016–2019 average, percentage points: the 26 states that expanded in 2014; the 17 states that had not expanded by 2019; and the first net of the second. 95% intervals in the data table."
    source: "ACS 1-year PUMS via the Census Data API."
    source_url: ""
    data_public: true
    verified: true    # every value checked against results/*.json
---

## Question

When a state expanded Medicaid to adults with incomes under 138% of the
poverty line, did fewer of those adults go without health insurance — and
by how much, compared with what would have happened anyway?

## Data

The uninsured rate among adults aged 19–64 with incomes under 138% of the
poverty line, for every state and DC, from the Census Bureau's American
Community Survey microdata, 2009–2019 (with 2021–2024 for a secondary
look; 2020 had no standard 1-year release). I built the rate from person
records rather than the published table because the table changes its age
band in 2017; the two agree closely where they overlap. Expansion dates
come from KFF; a state counts as treated in the year its expansion took
effect if that was on or before July 1.

## Design

I compared how the uninsured rate changed in states that expanded with how
it changed, over the same years, in states that had not yet expanded.

## Result

**Expansion lowered the uninsured rate among low-income adults by
7.2 percentage points (95% interval 4.6 to 9.7).**

[figure:fig-1]

The comparison group matters more than the method. Between 2013 and the
2016–2019 average, the uninsured rate in the 26 states that expanded in 2014
fell by 18.8 points (95% interval 15.3 to 21.3).
But it fell by 10.6 points in states that did not expand, because
the rest of the Affordable Care Act arrived everywhere at once. Net of
that, the change is −8.2 points (−11.2 to −4.3).

[figure:fig-2]

The simple comparison gives −8.2 points because it looks only at the
2014 states two to five years in, when the effect had grown; averaged over
every expanding state and every year after expansion, including the first,
smaller year (−4.1 points), the effect is −7.2 points — the headline.

A simpler regression (two-way fixed effects) gives almost the same answer,
which is expected here: 26 of the 34 states that expanded by 2019 did so
together in 2014, so there are few staggered comparisons for it to get wrong.

| Estimate (percentage points) | Population-weighted | Equal state weights |
|---|---|---|
| Callaway–Sant'Anna | −7.2 (−9.7 to −4.6) | −6.4 (−8.6 to −4.2) |
| Two-way fixed effects | −6.9 (−9.7 to −4.1) | −6.7 (−8.9 to −4.6) |

**Checks.** The result holds when I change the sample:

| Check | Estimate | 95% interval |
|---|---|---|
| Drop DE, DC, MA, NY, VT | −8.5 | −10.6 to −6.3 |
| Drop DC only | −7.2 | −9.9 to −4.6 |
| Utah coded first treated 2019 | −7.1 | −9.8 to −4.3 |
| Utah dropped | −7.2 | −9.9 to −4.4 |
| Wisconsin dropped | −7.2 | −10.0 to −4.4 |
| New Hampshire dropped | −7.2 | −9.8 to −4.5 |
| All adults 19-64 | −2.3 | −4.4 to −0.2 |
| Equal state weights | −6.4 | −8.6 to −4.2 |
| Drop the 2015 cohort (IN, NH, PA) (added after seeing results) | −7.2 | −10.3 to −4.1 |
| Drop the 2014 adopters (added after seeing results) | −7.4 | −9.4 to −5.3 |

Dropping the five states that already covered this group before 2014
makes the effect larger; using all adults 19–64, most of whom were never
eligible, makes it much smaller. Two rows were added after I saw the
results, and are labeled so.

**Before expansion.** The pre-specified test that the four pre-expansion
estimates are jointly zero does not reject (p = 0.24). The estimator's
built-in test, which stacks every pre-period cell, returns p = 0, but it is
unusable here: its covariance matrix has a condition number of about
4.7 × 10⁷ because the 2015, 2016 and 2019 groups have two or three states
each. Looked at one group at a time, the 2014 states are flat before
expansion, but the 2015 states (Indiana, New Hampshire, Pennsylvania) were
already drifting (e = -6: −4.3 points (z = −3.2); e = -5: −3.3 points (z = −2.2)). Dropping them leaves the
result unchanged.

**How much a pre-trend could matter.** Moderate robustness — the average
effect stays clear of zero unless the post-expansion violation exceeds
1.5 times the largest pre-period deviation.

**Against published estimates.** Two published studies of the second year
of expansion found −8.2 points (Miller & Wherry (2017), NEJM 376(10):947-956; National Health Interview
Survey, U.S. citizens 19–64 under 138% of poverty) and about
−6.0 points (Wehby & Lyu (2018), Health Services Research 53(2):1248-1271; ACS, low-educated adults 19–64). My
second-year estimate is −6.9 points. Both figures come from the studies'
abstracts and use different populations, so the comparison is approximate.

Over the full 2009–2024 period the estimate is −6.2 points, but those later
years are confounded by the 2020–2023 rule that kept Medicaid enrollees
covered in every state and by the 2023–24 unwinding, so I treat them as
context, not as the result.

## What this does not show

- **Who gained coverage.** This is a state-level rate; it does not say
  which people gained coverage or whether their health changed.
- **Clean timing everywhere.** Several states covered some low-income adults
  before 2014, and some expanded partway through a year; the robustness
  rows bound these choices but cannot remove them.
- **Recent years.** After 2019 the comparison is confounded by pandemic-era
  continuous enrollment, its unwinding, and Georgia's limited Pathways
  program (from July 2023).

## Reproduce it

The code, the analysis plan (committed before any estimate was run), the
decision log and the results files are at
[https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/medicaid_did](https://github.com/ts2427/ThresholdDataSciences/tree/main/demos/medicaid_did); the run instructions are in the
[demos README](https://github.com/ts2427/ThresholdDataSciences/tree/main/demos).

## If this were your data

The same design answers "did our change work?" for a price, a policy or a
program rolled out to some places or groups before others: it separates
the change you made from everything else that moved at the same time, and
says how sure you can be.
