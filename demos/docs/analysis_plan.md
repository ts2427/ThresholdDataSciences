# Demo A analysis plan — Medicaid expansion and the low-income adult uninsured rate

Written 2026-11-19, **before any estimator was run on the real data** (only
the descriptive step-1 summary had been seen). Committed on its own. Any
change after this commit is recorded as a deviation in `docs/decisions.md`
with the date and reason; this file is not edited after the fact.

## Data (from step 1)

- Unit: state (50 + DC) × year. Outcome: percent of adults 19–64 with income
  under 138% of the federal poverty line who are uninsured (ACS 1-year PUMS,
  person-weighted; definition in `docs/decisions.md`). Reported in
  **percentage points**.
- Treatment: first treated year per `data/processed/expansion_dates.csv`
  (KFF dates; effective on or before July 1 → that year, else next year).

## 1. Headline estimand

**The overall ATT from the Callaway–Sant'Anna estimator**, defined as R
`did` 2.5.1 `aggte(type = "group")$overall.att` — the average of
cohort-specific ATTs weighted by cohort size — with:

- **Window:** 2009–2019 (the main analysis).
- **Treated cohorts:** 2014, 2015, 2016, 2019. States first treated after
  2019 (ID, UT, NE, OK, MO, SD, NC) are untreated throughout the window and
  enter only as comparisons; never-treated states likewise.
- **Comparison group:** not-yet-treated plus never-treated
  (`control_group = "notyettreated"`, which includes never-treated units).
- **Estimation:** doubly robust (`est_method = "dr"`). There are no
  covariates, so the doubly robust estimator reduces to the unconditional
  difference in mean changes; it is specified anyway, as asked.
- **Inference:** multiplier bootstrap (`bstrap = TRUE`, `biters = 2000`,
  fixed seed 20261119), standard errors clustered by state
  (`clustervars = "fips"`); 95% intervals are the bootstrap simultaneous
  (uniform) bands that `did` reports, with pointwise intervals also shown.
- **Weighting — headline:** population-weighted by the state-year
  low-income adult population (`lowinc_pop`). `did` uses, in each 2×2
  comparison, the weight from the earlier of the two years (the base period
  for post-treatment cells), so a state's weight is never taken from a year
  its expansion could have affected. **Reported alongside:** equal state
  weights (`weightsname = NULL`).
- **Base period:** universal (`base_period = "universal"`): every effect is
  measured relative to the year before the cohort's first treated year
  (e = −1, normalised to zero).

## 2. Event study

- `aggte(type = "dynamic")` on the same estimates, reported for event times
  **e = −5 … +5** (e = −1 is the reference and is zero by construction).
  The panel is not balanced in event time: e = +5 comes only from the 2014
  cohort, e = +4 from 2014–2015, e = +3 from 2014–2016; e = 0 includes the
  2019 cohort. This is stated next to the table and figure.
- **Pre-period tests:** (a) a joint Wald test that the event-study
  coefficients for e = −5 … −2 are all zero, using the covariance matrix
  from `did`'s influence functions (χ², 4 df); (b) `did`'s own pre-test
  p-value (`Wpval`). Each pre-period coefficient is also shown with its
  95% interval.
- **2020 gap (secondary analysis only):** the main window ends in 2019, so it
  has no gap. A probe on synthetic data (`r/probe_did_gap.R`) showed that
  `did` renumbers observed years consecutively, which would treat 2019 and
  2021 as adjacent and shift every event time after the gap by one. So the
  secondary analysis uses event time **in calendar years, e = t − g**,
  computed from the cohort's true first treated year, never from period
  indices: there is **no interpolation**, no row for 2020, **e values that
  fall on 2020 are absent** from the table and appear as a visible gap on
  the plot axis, and each cohort's base period is its last *observed*
  pre-treatment year (2019 for cohorts 2020 and 2021). Implementation:
  ATT(g,t) cells computed by a small, tested Python implementation of the
  unconditional Callaway–Sant'Anna estimator using calendar years, checked
  to reproduce `did`'s ATT(g,t) estimates on the main window (agreement to
  1e-6) before being used on the full period.

## 3. Secondary analysis

The full **2009–2024** period (2020 absent; 2025 PUMS not yet available),
all cohorts (2014, 2015, 2016, 2019, 2020, 2021, 2022, 2023, 2024), same
comparison group, weights and base-period rule. **Labeled throughout as
confounded** by the 2020–2023 Medicaid continuous-enrollment requirement
(which kept people enrolled in every state) and the 2023–24 unwinding. It is
descriptive context, not a second headline. Georgia Pathways (limited
coverage with work requirements from July 2023) is a listed limitation;
Georgia stays never-treated.

## 4. Naive comparison

Two-way fixed-effects regression on the main window: uninsured rate (pp) on
a treated-and-post indicator, state and year fixed effects, weighted by the
state-year low-income adult population, standard errors clustered by state
(R `fixest`). Also run unweighted. The write-up explains how and why it
differs from Callaway–Sant'Anna (already-treated states used as controls for
later cohorts; implicit weights that are not cohort shares).

## 5. Robustness (each re-estimates the headline overall ATT)

1. Drop DE, DC, MA, NY, VT (prior full expansions).
2. Drop DC only.
3. Utah coded first treated in 2019 (partial expansion to 100% FPL, April
   2019).
4. Utah dropped.
5. Wisconsin dropped (covers adults to 100% FPL without expanding).
6. New Hampshire dropped (expanded August 2014, so 2014 is partly treated).
7. All adults 19–64 instead of low-income adults (weights: all-adult
   population).
8. Equal vs. population weights (the headline is reported both ways; this
   row restates the equal-weight figure).

Each row reports the overall ATT, its 95% interval and the change from the
headline. No row replaces the headline, whatever it shows.

## 6. Sensitivity to pre-trend violations

HonestDiD 0.2.8, relative-magnitudes restriction
(`createSensitivityResults_relativeMagnitudes`) on the main-window event
study (headline weighting), using the e = −5 … −2 and e = 0 … +5
coefficients and their influence-function covariance matrix:

- **Mbar = 0.5, 1, 1.5, 2**, with robust 95% intervals, plus the original
  interval.
- **Targets:** (a) the average of the post-period effects e = 0 … +5
  (equal weights on each), the primary target; (b) the e = 0 effect.
- **Breakdown value:** the largest Mbar on a grid of 0 to 3 in steps of
  0.05 at which the robust 95% interval still excludes zero, reported for
  each target.

## 7. Benchmarks (named before seeing any estimate)

Both verified against the abstracts indexed in PubMed (NCBI E-utilities,
2026-11-19); full texts were not accessible (publisher HTTP 403 / not open
access), so their confidence intervals are not available here.

1. **Miller & Wherry (2017)**, *NEJM* 376(10):947–956,
   doi:10.1056/NEJMsa1612890 (PMID 28273021). National Health Interview
   Survey; **U.S. citizens aged 19–64 with incomes below 138% FPL**; 2014–15
   vs. 2010–13, expansion vs. non-expansion states. Uninsurance in year 2
   after implementation: **−8.2 percentage points** (P < 0.001).
2. **Wehby & Lyu (2018)**, *Health Services Research* 53(2):1248–1271,
   doi:10.1111/1475-6773.12711 (PMID 28517042, PMC5867173). ACS 2011–2015;
   **low-educated adults aged 19–64** (an education-based, not income-based,
   population); difference-in-differences. Uninsured rate in 2015: a
   **"6 percentage-point decline"** (abstract wording).

**Published range: −8.2 to −6.0 pp**, both for the *second year* of
expansion (2015 for 2014 adopters). Like for like, the comparison is made
twice: with the event-study **e = +1** estimate (the second year), and with
the headline overall ATT, which averages over up to six years of exposure.
Differences in population (citizens only; education vs. income), survey
(NHIS vs. ACS) and design are stated alongside.

## 8. Red flags

Either of these **triggers an investigation, not a reframing** — the
headline stays as pre-specified and the investigation is reported next to
it:

- The pre-period event-study coefficients (e = −5 … −2) are **jointly
  significant** at the 5% level (test 2a).
- The **headline overall ATT's point estimate lies outside −8.2 to −6.0
  pp**, or the e = +1 point estimate does.

Investigation means: checking the data and coding for the cohorts driving
the result, reporting cohort-specific ATTs, and reporting the HonestDiD
bounds prominently. Its findings are logged in `docs/decisions.md`.

## 9. What is reported

Every number above is written by code to `results/medicaid_did.json`;
event-study and comparison values are exported as CSVs for the figures.
