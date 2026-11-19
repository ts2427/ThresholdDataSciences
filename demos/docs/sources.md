# Sources

Data sources, policy sources and published estimates used for comparison.
Every citation listed here was checked to exist (link resolved, details
matched) before being added.

## Demo A — Medicaid expansion

### Data

- U.S. Census Bureau, American Community Survey 1-year Public Use Microdata
  Sample (PUMS), person records for ages 19–64 (variables PWGTP, AGEP,
  POVPIP, HICOV, MIL), via the Census Data API
  (`https://api.census.gov/data/<year>/acs/acs1/pums`), 2009–2019 and
  2021–2024; one raw file per state-year in `data/raw/pums/` (see manifest).
  2020 has no standard 1-year release; 2025 PUMS was not on the API as of
  2026-11-19.
- U.S. Census Bureau, ACS 1-year table C27016, via the Census Data API
  (`https://api.census.gov/data/<year>/acs/acs1`), 2017–2019 — used only to
  validate the PUMS aggregation. The table's adult age band is 18–64 in
  2009–2016 and 19–64 from 2017 (API group metadata, checked 2026-11-19).

### Expansion dates

- KFF, State Health Facts, "Status of State Action on the Medicaid Expansion
  Decision" (November 2026).
  https://www.kff.org/health-reform/state-indicator/state-activity-around-expanding-medicaid-under-the-affordable-care-act/
  — accessed 2026-11-19; saved to `data/raw/` (see manifest).
- KFF, "Status of State Medicaid Expansion Decisions" issue brief (published
  Nov 6, 2026), which points to the State Health Facts table above for
  adoption and implementation dates.
  https://www.kff.org/affordable-care-act/issue-brief/status-of-state-medicaid-expansion-decisions-interactive-map/
- KFF, "States Getting a Jump Start on Health Reform's Medicaid Expansion"
  (Apr 2, 2012): six states (CA, CT, DC, MN, NJ, WA) expanded to low-income
  adults from April 2010 through the ACA early option and/or 1115 waivers.
  https://www.kff.org/medicaid/states-getting-a-jump-start-on-health/
- Kaestner, R., Garrett, B., Gangopadhyaya, A., & Fleming, C. "Effects of ACA
  Medicaid Expansions on Health Insurance Coverage and Labor Supply." NBER
  Working Paper 21836, December 2015, revised September 2016. Table 1 (p. 32)
  classifies states by prior expansions (used for `prior_coverage_kaestner`).
  https://www.nber.org/papers/w21836 — text checked 2026-11-19. Published
  version: *Journal of Policy Analysis and Management* 36(3), 608–642 (2017),
  doi:10.1002/pam.21993 (with J. Chen added as author; publication details
  confirmed via RePEc listing).

### Published estimates for comparison

Named in `docs/analysis_plan.md` before any estimate was seen. Both checked
against the PubMed record via NCBI E-utilities (2026-11-19); full texts were
not accessible (NEJM and Wiley return HTTP 403; the HSR article is in PMC
but not open access), so the figures are the abstracts' and no confidence
intervals are available.

- Miller, S., & Wherry, L. R. (2017). Health and access to care during the
  first 2 years of the ACA Medicaid expansions. *New England Journal of
  Medicine*, 376(10), 947–956. https://doi.org/10.1056/NEJMsa1612890
  (PMID 28273021). NHIS; 60,766 U.S. citizens aged 19–64 with incomes below
  138% FPL; 2014–15 vs. 2010–13. Abstract: in year 2, uninsurance
  "difference-in-differences estimate, −8.2 percentage points; P<0.001".
- Wehby, G. L., & Lyu, W. (2018). The impact of the ACA Medicaid expansions
  on health insurance coverage through 2015 and coverage disparities by age,
  race/ethnicity, and gender. *Health Services Research*, 53(2),
  1248–1271. https://doi.org/10.1111/1475-6773.12711 (PMID 28517042,
  PMC5867173). ACS 2011–2015; 3,137,989 low-educated adults aged 19–64.
  Abstract: in 2015, "a nearly 8 percentage-point increase in Medicaid
  take-up and 6 percentage-point decline in uninsured rate".
- Considered and not used (population or estimand differs): Kaestner et
  al. (2017) — parents/childless adults in low-education or <300% FPL
  samples (−2.7 pp for parents, NBER WP 21836 p. 17); Courtemanche et al.
  (2017, *JPAM* 36(1):178–210, NBER WP 22182) — effects on all residents
  scaled by pre-ACA local uninsured rates; Frean, Gruber & Sommers (2017,
  NBER WP 22213) — effect among the newly eligible.

### Policy facts used in robustness checks (supplied by Tim; verified 2026-11-19)

- **Utah — partial expansion to 100% FPL from April 1, 2019: confirmed.**
  KFF, "From Ballot Initiative to Waivers: What is the Status of Medicaid
  Expansion in Utah?" (Nov 15, 2019): "to implement a coverage expansion to
  100% FPL beginning April 1, 2019"; Utah calls it the "Bridge Plan".
  https://www.kff.org/medicaid/issue-brief/from-ballot-initiative-to-waivers-what-is-the-status-of-medicaid-expansion-in-utah/
  Utah DHHS, https://medicaid.utah.gov/expansion : "This smaller-scale
  expansion opened enrollment on April 1, 2019". KSL (Mar 29, 2019) reports
  CMS approval that Friday for the Monday launch. (KFF and Utah DHHS differ
  on the bridge's match rate, 68% vs 70%; not used here.) Full expansion
  date (1/1/2020) is from the KFF State Health Facts table above.
- **Wisconsin — childless adults to 100% FPL through a waiver, not the ACA
  expansion: confirmed.** KFF fact sheet, "Wisconsin's BadgerCare Program and
  the ACA" (Feb 25, 2014): "Wisconsin received approval of a new waiver to
  provide coverage to childless adults up to 100% FPL"; the coverage "is not
  eligible for enhanced ACA matching funds"; intended effective January 1,
  2014, with coverage above 100% FPL continued "until April 1, 2014".
  https://www.kff.org/medicaid/fact-sheet/wisconsins-badgercare-program-and-the-aca/
- **Georgia Pathways — limited coverage to 100% FPL with work or
  qualifying-activity requirements, from July 2023: confirmed to the
  month.** Manatt Health (Oct 2, 2025): "Georgia's first 1115 demonstration
  period (from July 1, 2023 through September 30, 2025)", "household incomes
  up to 100 percent of the federal poverty level", "a minimum of 80 hours of
  qualifying activities".
  https://www.manatt.com/insights/insight/cms-approves-temporary-extension-of-georgia-pathways-section-1115-work-requirements-demonstration
  Georgetown CCF (June 27, 2023): "In July 2023, Georgia will begin
  enrollment", "with coverage expected to begin in September 2023".
  https://ccf.georgetown.edu/2023/06/27/an-analysis-of-georgias-section-1115-medicaid-pathways-to-coverage-program/
  No source read gives an exact enrollment day; the write-up says "July 2023".

## Demo B — OSHA Severe Injury Reports

### Data

- U.S. Department of Labor, OSHA, Severe Injury Reports,
  `January2015toNovember2025.zip` (one CSV, 105,996 rows × 28 columns),
  linked from the Severe Injury Dashboard page
  https://www.osha.gov/severe-injury-reports ; file URL
  https://www.osha.gov/sites/default/files/January2015toNovember2025.zip —
  accessed 2026-11-19; saved to `data/raw/` (see manifest). osha.gov returns
  HTTP 403 to requests without ordinary browser headers, so the download
  script sends them.
- Coverage, quoted from https://www.osha.gov/severeinjury (accessed
  2026-11-19): "The reports will be updated periodically and represent
  incidents under federal OSHA jurisdiction only. They do not include
  incidents in states covered by OSHA-approved State Plans."
- Reporting rule: 29 CFR 1904.39 (employers report in-patient
  hospitalizations, amputations and losses of an eye within 24 hours; the
  requirement began January 1, 2015).
