# Decisions

Dated log. Each entry: what was decided, and why.

## Setup

- **2026-11-19 — Folder and environment.** The working folder did not exist;
  created it with a Python 3.13 venv (Tim's go-ahead). The site repo
  location was confirmed by Tim (the path in the brief did not exist); this
  folder was later moved inside the site repo.
- **2026-11-19 — R.** R 4.6.0 is installed with `did` 2.5.1, `HonestDiD`
  0.2.8 and `fixest` 0.14.2 already in the user library, so nothing is
  installed system-wide. Python CS packages `differences` 0.3.0 and `csdid`
  0.4.5 are also installed for comparison.

## Demo A — Medicaid expansion

- **2026-11-19 — Outcome table: ACS `C27016`, low-income adults.** C27016
  ("Health Insurance Coverage Status by Ratio of Income to Poverty Level in
  the Past 12 Months by Age") splits adults 19–64 at exactly 138% of poverty
  ("Under 1.00" + "1.00 to 1.37"), the ACA expansion's income line. So the
  preferred population (low-income adults) is supported; the all-adults
  19–64 series is the robustness check. Universe: civilian
  noninstitutionalized people for whom poverty status is determined.
- **2026-11-19 — Years: 2009–2019 and 2021–2025.** The API returns C27016
  for 2009–2025 except 2020 (Census issued no standard 1-year release for
  2020, only experimental estimates). 2008 is not available for this table
  through the API. 16 years in all; the 2014 cohort has five pre-years.
  *Proposed — awaiting Tim's confirmation.*
- **2026-11-19 — Expansion dates: KFF State Health Facts, parsed in code.**
  The table on the KFF page is server-rendered HTML; it is saved unedited to
  `data/raw/kff_expansion_status_2026-11.html` (in the manifest) and parsed by
  `expansion.parse_kff_table`, which checks for exactly 51 jurisdictions and
  a date for every adopter. No date is typed by hand.
- **2026-11-19 — Treatment year: on or before July 1 → that year.** The ACS
  asks about coverage at the interview, spread across the year, so a state
  counts as treated in its effective date's year if coverage was in force
  for at least half of it, otherwise the next year. Effects: MI (Apr 2014)
  → 2014; LA (Jul 1 2016) → 2016; SD (Jul 1 2023) → 2023; NH (Aug 2014) →
  2015; AK (Sep 2015) → 2016; NE (Oct 2020) → 2021; MO (Oct 2021) → 2022;
  NC (Dec 2023) → 2024. *Proposed — awaiting confirmation.*
- **2026-11-19 — Early and partial expanders.** KFF lists every adopter's
  2014-or-later date with no note on earlier coverage. Kaestner et al. (NBER
  WP 21836, Table 1) classify DE, DC, MA, NY and VT as having had *full*
  prior expansions to parents and childless adults, and 13 2014-adopters
  (AZ, CA, CT, CO, HI, IL, IA, MD, MN, NJ, OR, RI, WA) plus 4 non-adopters
  in 2014 (IN, ME, TN, WI) as having had *limited* prior expansions; KFF
  (2012) documents the six ACA early-option states (CA, CT, DC, MN, NJ, WA).
  Proposed handling: the main analysis codes everyone as KFF does (the five
  prior-full states as 2014 adopters), which biases the estimate toward zero
  because those states already covered this group; a robustness check drops
  the five prior-full states, in addition to the brief's drop-DC check.
  Limited prior expansions stay coded as KFF has them; flagged as a
  limitation. Wisconsin stays never-treated (not adopted) although it covers
  some adults through a waiver. *Proposed — awaiting confirmation.*
- **2026-11-19 — Tim approved the table, the July 1 rule and the
  early-expander handling above, with the changes below.**
- **2026-11-19 — Main vs. secondary analysis (Tim).** *Main:* 2009–2019
  only, cohorts 2014, 2015, 2016 and 2019. States first treated after 2019
  (ID, UT, NE, OK, MO, SD, NC) are untreated throughout that window; they
  serve as not-yet-treated / never-treated-within-window comparisons, or are
  excluded, as each estimator requires (recorded in step 2). The headline
  result comes from the main analysis only. *Secondary:* 2009–2025, all
  cohorts, labeled as confounded by the 2020–2023 Medicaid
  continuous-enrollment requirement and the 2023–24 unwinding.
- **2026-11-19 — Added robustness checks (Tim).** (1) Utah coded as first
  treated in 2019 (partial expansion to 100% FPL in April 2019); (2) Utah
  dropped; (3) Wisconsin dropped (covers adults to 100% FPL without
  expanding); plus the existing drops of DE/DC/MA/NY/VT and of DC alone,
  and the all-adults outcome. Sources for the Utah and Wisconsin facts are
  added to docs/sources.md in step 3.
- **2026-11-19 — Georgia Pathways (Tim).** Georgia stays never-treated;
  Georgia Pathways (limited coverage with work requirements, from July
  2023) is listed as a limitation of the secondary analysis (it falls
  outside the main 2009–2019 window).
- **2026-11-19 — Missing 2020 in the secondary analysis (Tim).** No
  interpolation; 2019 and 2021 must not be treated as adjacent periods; the
  event-time axis must show the gap. How the estimator achieves this is
  recorded in step 2.
- **2026-11-19 — Outcome source switched from C27016 to PUMS (Tim).**
  Downloading C27016 showed its adult age band changes in 2017: 18–64 in
  2009–2016, 19–64 from 2017 (checked in every year's API metadata). That
  break sits inside the main window and need not be uniform across states
  (18-year-olds can qualify for children's Medicaid, whose upper age and
  income limits vary by state), so year fixed effects would not reliably
  absorb it. The outcome is now computed from ACS 1-year PUMS person
  records with one definition in every year: age 19–64; poverty status
  determined (POVPIP 0–501); not active-duty military (MIL ≠ 1); low-income
  = POVPIP ≤ 137 (under 138% FPL); uninsured = HICOV 2; weighted by PWGTP.
  The all-adults robustness series is the same universe without the income
  cut. *Validation:* published C27016 for 2017–2019 (19–64 in those years)
  is downloaded separately and compared state by state with the PUMS rates.
  *Consequence:* 2025 PUMS is not on the API yet, so the secondary analysis
  runs 2009–2024 (excluding 2020). The C27016 superseded plan above (years
  2009–2025) no longer applies.
- **2026-11-19 — Uncertainty in state-year rates.** The difference-in-
  differences inference uses standard errors clustered by state, which carry
  the sampling noise in the state-year rates; PUMS replicate weights are not
  used. State-year sample sizes (unweighted `_n`) are kept in the panel.
- **2026-11-19 — Analysis plan committed (`9302abe`) before any estimator
  was run.** Entries below record deviations from it and investigations.
- **2026-11-19 — Deviation: HonestDiD breakdown search.** The plan's
  breakdown value is the largest Mbar on the grid 0–3 (step 0.05) whose
  robust 95% interval excludes zero. Evaluating all 61 grid points took over
  20 minutes and was stopped; `r/demo_a_honestdid.R` finds the same grid
  point by bisection (robust intervals under relative magnitudes widen
  monotonically in Mbar). Same estimand, same grid, same answer.
- **2026-11-19 — Deviation: secondary-analysis inference.** The calendar-
  year Callaway–Sant'Anna implementation (`medicaid_did/src/cs.py`) uses a
  state-cluster nonparametric bootstrap (resample states, 2,000 draws, 95%
  percentile intervals), not `did`'s multiplier bootstrap. Point estimates
  reproduce `did` exactly on the main window (ATT(g,t) cells, overall ATT
  and event study agree to ~1e-14, both weightings). Cohort sizes follow
  `did`'s convention (unit weights in the first sample year), found while
  validating.
- **2026-11-19 — Mechanics: R output.** `jsonlite` is not installed in R; R
  writes CSVs to `results/demo_a/` and `step2_collect.py` assembles
  `results/medicaid_did.json`. Nothing installed.
- **2026-11-19 — Overall-ATT interval.** The plan names `did`'s uniform
  bands; those apply to the event study. The overall ATT is a single
  number, so its 95% interval is estimate ± 1.96 × bootstrap SE.
- **2026-11-19 — Investigation: the two pre-tests disagree.** The
  pre-specified test (event-study e = −5…−2, χ²(4)) is not significant
  (p = 0.24 population-weighted, 0.44 equal weights), so the plan's red flag
  is not triggered. `did`'s built-in pre-test (all 24 pre-period ATT(g,t)
  cells) returns p = 0 population-weighted and no value with equal weights
  (singular covariance). Investigation (`r/investigate_pretest.R`): the
  24-cell covariance matrix has condition number ≈ 4.7×10⁷ because the
  2015, 2016 and 2019 cohorts have 3, 3 and 2 states but 5–9 pre cells each,
  so that Wald statistic is numerically unreliable. By cohort, the 2014
  cohort (26 states) shows no pre-trend; the **2015 cohort (IN, NH, PA) does**
  (e = −6: −4.3 pp, z = −3.2; e = −5: −3.3 pp, z = −2.2), and the 2019
  cohort's e = −10 cell is −4.3 pp (z = −2.1). Its base year is 2014, the
  first marketplace year and a partly treated year for NH. Reported in the
  write-up as a weakness; the headline is unchanged; HonestDiD bounds are
  given prominence; cohort-specific ATTs are reported alongside.
- **2026-11-19 — Added explanation: TWFE implicit weights.** To explain how
  the naive estimate differs, `twfe_weights.py` computes the static TWFE
  estimator's implicit weights on treated state-years. None are negative;
  TWFE puts more weight on the first expansion year (where effects are
  smallest) and less on years 4–5 (largest) than the Callaway–Sant'Anna
  overall ATT, so it is smaller in magnitude.
- **2026-11-19 — Added after seeing results (Tim): naive vs careful =
  before-and-after.** The write-up's main contrast and second figure is now
  the 2014 cohort's 2013 rate vs its 2016–2019 average with no comparison
  group, against the same change net of the 17 states untreated through 2019
  (`medicaid_did/src/before_after.py`; state-cluster bootstrap, 2,000
  draws). Naive TWFE vs Callaway–Sant'Anna becomes a table, described as a
  check that agrees here because 26 of 34 treated states expanded together.
- **2026-11-19 — Robustness row added AFTER seeing results: drop the 2015
  cohort (IN, NH, PA)**, prompted by that cohort's pre-trend. Labeled as
  such in `results/medicaid_did.json` (`added` field), the write-up and here.
  Run by `r/demo_a_posthoc.R` with the same settings as the main script.
- **2026-11-19 — Robustness row added after seeing results: drop the 2014
  adopters.** The original brief's step 3 asked for it, but it was left out
  of the pre-registered plan; added now and labeled the same way.
- **2026-11-19 — Write-up requirements recorded** in
  `docs/writeup_requirements_demo_a.md` (both pre-tests with the condition-
  number explanation; the plain HonestDiD sentence; benchmarks are from
  abstracts with different populations, so the comparison is approximate).
- **2026-11-19 — Step 3 sources verified:** Utah's April 1, 2019 partial
  expansion, Wisconsin's 100% FPL waiver and Georgia Pathways (July 2023)
  are confirmed in `docs/sources.md`; Georgia's exact enrollment day is not
  stated in any source read, so the write-up says "July 2023".
- **2026-11-19 — Figures (step 4).** Preview PNGs are drawn only from the
  exported CSVs in `results/figures/`. The site's `figures.py` has no chart
  type for estimates with intervals; how the event study renders on the
  site is decided at the site step.
- **2026-11-19 — 2020 cohort (ID, UT).** Both expanded 1/1/2020, the year
  with no ACS 1-year data, so their event-time-0 year is unobserved and
  their first observed post year is 2021. How the estimators handle the
  missing year is decided in step 2.

## Demo B — OSHA Severe Injury Reports

- **2026-11-19 — Coverage.** Federal-OSHA jurisdictions only (OSHA's own
  wording, quoted in docs/sources.md). 50 states, DC and 5 territories
  appear; 2,492 rows carry `FederalState = 0`, mostly in state-plan states
  (CA, VA, WA, NC). The flag is undocumented on OSHA's page; reported, not
  interpreted.
- **2026-11-19 — `ID` is not a key.** Five `ID` values appear twice, each
  pair two different incidents. `UPA` is unique for all 105,996 rows and is
  used as the report identifier.
- **2026-11-19 — Step 3a evidence (before choosing a rule).** No row is an
  exact duplicate of another, with or without `ID`. 87 pairs share date and
  exact address; widening to the same normalized address or ZIP5 gives 542
  candidate pairs. Reading the strongest 72 by hand shows three kinds: (1)
  one injury filed twice by the same employer under spelling variants
  (VA, Red River, Orkin, Cross-Cut, Cabela's, JBS, Dentsply …); (2) one
  incident reported by two employers — a staffing agency and its host, or a
  contractor and the site owner; (3) different workers injured in one
  incident, each reported by their own employer. 645 rows record two or more
  hospitalized workers, so the file's convention is one report per incident
  with counts: a second same-employer row for the same incident is a repeat
  filing, not a second worker.
- **2026-11-19 — Step 3a rule (PROPOSED, not yet applied; awaiting Tim).**
  Same incident = same date and state, same normalized address or ZIP5, and
  (≥ 3 of 4 injury codes equal or narrative similarity ≥ 80). Same-employer
  duplicate = same incident + employer-name similarity ≥ 70 → keep the
  lowest UPA, remove the rest: **42 rows**. Cross-employer same-incident
  pairs (30) are kept — each is a different employer's report — and
  flagged. Sensitivity: a stricter rule (4 codes or narrative ≥ 90) finds 16
  same-employer pairs; a looser one (2 codes or narrative ≥ 70) finds 73.
  Known ambiguity: an employer filing one row per injured worker for the
  same incident would be merged (e.g. Darling Ingredients 10/20/2018: burns
  to "neck and back" vs "right arm and shoulder"); the file's one-report-
  per-incident convention makes this the less likely reading, but it is
  not certain.
- **2026-11-19 — Step 3a: Tim approved the proposed (middle) threshold.**
  All 42 same-employer pairs written in full to `review/b_dup_pairs.csv`
  (UPA kept/removed, employer names, date, state, injury titles, outcome
  counts, both narratives, empty `confirm` column) for hand confirmation;
  rows Tim marks N stay in. Sensitivity range recorded in
  `results/osha_audit.json` (`step3a_rule.sensitivity`). Write-up
  requirements in `docs/writeup_requirements_demo_b.md`.
- **2026-11-19 — Merge rule for duplicates (Tim).** When a duplicate
  cluster is collapsed, the kept row is the lowest UPA, but it takes the
  higher Hospitalized and Amputation counts from any row in the cluster
  (e.g. XPO 5/3/2019: one row records a hospitalization, the other does
  not). Implemented when the rule is applied, after hand confirmation.
- **2026-11-19 — Every table carries the 2,492 `FederalState = 0` rows as a
  separate line (Tim).**
- **2026-11-19 — Step 3a hand review (Tim).** Of the 42 same-employer
  pairs in `review/b_dup_pairs.csv`, 39 confirmed (Y) and 3 rejected (N):
  pairs 19 (American Railcar), 26 (Darling Ingredients) and 37 (KL
  Enterprises) describe different tasks or body parts, i.e. two workers;
  both rows stay. **Pairs 3 (XPO Logistics, 5/3/2019) and 17 (VA John D.
  Dingell Medical Center, 5/2/2019) are "Y — judgment call"**: same machine
  or door, same day, but a different finger recorded; merged, and listed in
  the write-up as the uncertain cases.
- **2026-11-19 — Step 3a applied.** `osha_audit/src/dedupe_apply.py` merges
  the 39 confirmed pairs: 39 rows removed (105,996 → 105,957), each kept row
  the lowest UPA with the higher Hospitalized, Amputation and Loss of Eye
  values from the pair (Tim). The confirmed count sits inside the
  strict / proposed / loose range of 16 / 42 / 73.
- **2026-11-19 — Step 3b normalization (PROPOSED, previewed, not applied;
  awaiting Tim).** `osha_audit/src/normalize.py`: lowercase; keep the part
  before "dba" (the legal entity that filed); drop parenthetical text; drop
  marked store/unit numbers ("#287", "store 517", "no. 1188" — bare numbers
  in names such as "Route 66" or "3M" are kept); "&" → "and"; delete
  periods and apostrophes; other punctuation → space; drop a leading "the";
  drop trailing legal suffixes (inc, llc, corp, co, company, ltd, lp, llp,
  pllc, pc, plc …) repeatedly; the grouping key also removes spaces
  ("Wal-Mart" = "Walmart"). Left to step 3c: aliases and abbreviations
  (USPS / U.S. Postal Service; UPS / United Parcel Service), store-format
  words ("Walmart Supercenter" vs "Walmart"), singular/plural ("Publix
  Supermarket" vs "Supermarkets"), and text after " - ". Preview:
  71,444 → 55,769 distinct names.
- **2026-11-19 — Step 3b approved as written (Tim), subject to a suffix
  check.** 100 random suffix-only merges ("abc co" + "abc inc"; seed
  20261119, from 2,319 such pairs) written to `review/b_suffix_sample.csv`.
  **Review scope (Tim): only the 71 pairs that share at least one state are
  marked**; they test the suffix rule. The 29 pairs with no shared state are
  left unmarked: whether identical names in different states are one
  company is a cross-state question, handled by the name + state count and
  by step 3c's state blocking, not by the suffix rule. Decision rule: 4 or
  fewer N among the marked pairs → apply 3b as written; more → propose
  merging across suffix types only within the same state.
- **2026-11-19 — Step 3b: narrower suffix rule adopted IN PLACE OF the
  hand review (Tim).** The sample in `review/b_suffix_sample.csv` was not
  marked; it is kept, unmarked, as a record. The narrower rule is the
  conservative outcome that review could have produced: names differing
  only in the spelling of one suffix type (Corp/Corporation,
  Inc/Incorporated, Co/Company, Ltd/Limited) always merge; names differing
  in suffix type (Inc vs LLC, Corp vs Inc), or where one has no suffix,
  merge only when they share a state (`osha_audit/src/entities3b.py`;
  merges are transitive through shared states). Preview: 57,132 employers by
  name (original rule 55,769; 1,674 cross-type form pairs blocked, +1,363
  employers); 67,199 by name + state under both rules, as expected, because
  the narrower rule only blocks merges between names that share no state.
  Top 15 unchanged. **Applied** to `data/interim/osha_step3b.csv`.
- **2026-11-19 — Step 3c design (PROPOSED, previewed, not applied; awaiting
  Tim).** `osha_audit/src/fuzzy3c.py`. Blocking: C1 within state; C2 across
  states only when one side is in >= 5 states (651 employers); C3 national
  aliases (acronyms, store-format names) only from a data-derived list for
  employers in >= 10 states, each link approved by hand
  (`review/b_3c_alias_candidates.csv`). Match: token_sort_ratio >= 92 AND
  the distinctive part (generic tokens removed; 141 tokens found in >= 150
  employer names) ratio >= 85, identical if shorter than 4 characters;
  "united states" read as "us". Evidence for the threshold: random pairs by
  score band — 95–98 almost all the same company; 92–95 mixed, the errors
  being short distinctive words beside generic ones (ifs/igs industries,
  bear/berg electric), which the distinctive-part check rejects; 85–92
  mostly different companies sharing a generic word. Preview: 57,132 →
  56,098 employers by name, 67,199 → 66,132 by name + state; 1,072 matched
  pairs (961 within state, 111 cross-state). Bug found in the preview and
  fixed before review: the acronym check read "us postal service" as
  "ups"; the candidate list now links UPS only to United Parcel Service.
- **2026-11-19 — Step 3c match rule and thresholds approved as proposed
  (Tim).**
- **2026-11-19 — Entity principle (Tim):** "Names that refer to the same
  operating employer merge (store formats and locations, acronyms);
  separate legal operating companies stay separate (FedEx Freight vs FedEx;
  subsidiaries vs parents)." Applied to the 23 national-alias candidates in
  `review/b_3c_alias_candidates.csv` (marked, with reasons, as the record):
  16 approved (USPS ×2, UPS ×2, Walmart ×3, Lowe's ×3, Home Depot, Hobby
  Lobby, Dollar Tree, Allied Universal, CVS ↔ CVS Pharmacy, FedEx Ground ↔
  FedEx Ground Package System), 7 rejected (FedEx ↔ Express / Freight /
  Ground / Ground Package System; XPO Logistics ↔ XPO Logistics Freight;
  Cargill ↔ Cargill Meat Solutions; CVS ↔ CVS Health). Two rows were not
  in the recommendation Tim approved and were decided under the principle:
  CVS ↔ CVS Pharmacy (Y: "CVS" as a store name is the CVS Pharmacy
  operating company) and FedEx Ground ↔ FedEx Ground Package System (Y:
  the same company's legal name).
- **2026-11-19 — Step 3d sample (Tim's design).** Candidate pool: all
  pairs of step-3b employers allowed by the approved blocking with overall
  score >= 80: 28,050 pairs — accepted 1,072; rejected 80–85: 21,015;
  rejected 85–92: 5,361; rejected 92+ by the distinctive-part check: 602.
  Sample (seed 20261119): 150 accepted + 50 from each rejected stratum, in
  `review/b_3d_pairs.csv` with an empty "same employer" column. Estimation
  plan, fixed before labeling: precision = share labeled Y among the
  accepted sample, 95% Wilson interval (a simple random sample from one
  stratum); recall = estimated true matches in the accepted stratum ÷
  estimated true matches in all strata, each stratum's Y share weighted by
  its pool size, 95% interval from a stratified bootstrap (resampling
  within strata, 10,000 draws). The national-alias links are hand-approved
  and outside this check.
- **2026-11-19 — Step 3d labels received (from Tim, `review/b_3d_pairs.csv`).**
  184 Y / 116 N; 22 items carry notes, 13 marked "Judgment call". **Label
  source:** the notes column is named `claude_note`, so the labels may have
  been drafted by Claude; the write-up calls this a hand check only once
  Tim confirms he reviewed them, and otherwise describes it as a
  model-labeled check reviewed by Tim.
- **2026-11-19 — Step 3d results (pre-specified methods).** Precision 145/150
  = 96.7% (Wilson 95% 92.4–98.6%). Recall 47.7% (stratified bootstrap 95%
  38.1–61.5%). Estimated missed matching pairs 1,136 (647–1,684): 751 in the
  85–92 band (from 7 of 50 labeled Y, so uncertain) and 385 in the 92+ band
  rejected by the distinctive-part check (32 of 50 Y, nearly all typos in
  common words); 0 of 50 in 80–85. Sensitivity, all 13 judgment calls
  flipped: precision unchanged (the flips in the accepted stratum cancel),
  recall 50.2% (40.2–64.3%). **Limitation:** the 80–85 stratum had 0 of 50
  matches, so the bootstrap cannot vary it; at its Wilson upper bound (7.1%)
  recall would be 28.2%. The matcher was not tuned on these labels.
- **2026-11-19 — Correction to a requested write-up sentence.** Tim asked
  the write-up to say "most misses are typos inside common words that the
  distinctive-part check rejects". The labels support that for the 92+
  band, but by the weighted estimate that band holds about a third of the
  misses (385 of 1,136); about two thirds (751) are pairs scoring 85–92,
  just under the overall threshold, of mixed kinds (typos, "+" vs "and",
  "1" vs "I", plant names). The requirement is recorded in corrected form
  and flagged to Tim.
- **2026-11-19 — Step 3c applied (final).** Approved rule plus 16 approved
  alias links; not adjusted using the 3d labels. Employers by name: 71,454
  raw → 71,444 (3a) → 57,132 (3b) → 56,098 (3c fuzzy) → 56,083 (aliases);
  by name + state: 80,196 → 80,185 → 67,199 → 66,132 → 65,923. Missed
  matches mean the final count is overstated by at most about 2.0%
  (1.2–3.0%); false merges (≈36) push slightly the other way. Outputs:
  `data/processed/osha_upa_employer.csv`, `results/figures/b_waterfall.*`,
  `results/figures/b_before_after.csv`.
- **2026-11-19 — Requirement 14 corrected wording accepted (Tim).**
- **2026-11-19 — Label review (Tim).** Tim reports reviewing the labels that
  drive the estimates and marking them in a `reviewed_by_tim` column. As of
  this entry the file has no such column and is unchanged since 14:12; no
  labels differ from commit 64ad87e, so precision and recall stand. The
  reviewed set is 21 distinct items (items 11, 24, 29, 43, 64, 69, 87, 103, 126, 129, 138, 166, 193, 194, 197, 258, 262, 267, 274, 290, 292),
  not 25 (four items fall in two groups). Requirement 16 is recorded with
  Tim's wording, corrected to 21, and marked pending until the review
  column is saved.
- **2026-11-19 — ITA feasibility (future research only).** 2023 ITA 300A
  data checked for the top 25 employers in federal-OSHA private-sector
  jurisdiction; findings in `docs/paper_idea_ita_linkage.md`. No rates are
  computed or published.
- **2026-11-19 — Step 3e (fallback, Tim): headcount illustration.** Report
  counts for the top 10 resolved employers next to fiscal-2024 headcounts
  from each company's Form 10-K (USPS: its own FY2024 10-K). Each figure is
  parsed from a verbatim quote that the code checks against the stored
  filing (`data/raw/filings/`, in the manifest). U.S. figures used where the
  filing gives them (Walmart, UPS, Tyson); otherwise totals (Lowe's: full-
  plus part-time sum; American Airlines: full-time equivalents). Disney has
  no parks headcount, so it is shown in the table but omitted from the
  chart. No rate ranking. **Finding stated honestly:** the association is
  loose — Tyson (120,000 U.S.) files more reports than Kroger (409,000) or
  Target (440,000) — so the caption says bigger employers *tend* to file
  more reports and that industry matters too; that is still the point:
  counts are not a safety ranking.
- **2026-11-19 — Label disclosure (Tim).** The pending sentence that
  depended on a `reviewed_by_tim` column is withdrawn, and so is that
  dependency. The OSHA page now says, visibly: "Accuracy figures are
  illustrative: they were estimated against match labels drafted by an AI
  model. In client work, labels are checked by hand."
- **2026-11-19 — Site review decisions (Tim).** Demonstration tag from the
  analysis template only (removed from page bodies); the distinct-employer
  figure is a waterfall (bridge) chart, a new tested chart type in the
  site's `figures.py`, with name + state counts in its data table; every
  figure CSV is verified value by value against `results/*.json` by
  `site_pages/verify_figures.py` before it is marked `verified: true` (all
  three matched); "Reproduce it" hidden until the code is published; pages
  published (`draft: false`) and both work items live.
