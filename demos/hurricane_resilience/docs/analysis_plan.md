# Analysis plan: "When the Network Goes Dark"

**Status: committed 2026-11-22, before any recovery outcome was computed. Not blind: see "Seen before registration". Open items are listed under "Before approval".**

Follows CLAUDE.md, docs/decisions.md and the step docstrings.

## Seen before registration
This plan was drafted, and revised, after outcome figures had been seen. **It is not blind to the reports below.** Claude Code, which drafted it, saw these while building and checking the parser, and showed some to the author:
- **Isaias, Oct 12, 2026:** every county row, all totals, the subscriber count, and the prior day's overall and state percents (so the one-day recovery).
- **Michael, Oct 20, 2018:** every county row, the total, the subscriber count, the prior day's percent, and the four-day fall from 12.7% to 5.5%.
- **Helene, Sep 30, Oct 1, 2 and 6, 2024:** every state total with causes and backup power, headlines, subscriber counts, prior-day percents (so the state recovery paths from Sep 29 to Oct 6), and some county rows.
- **Debby, Aug 5, 2024, and Ian, Sep 28, 2022:** totals with causes, headlines, subscriber counts, and some county rows.
- **Fiona, Sep 24 and 26, 2022 (out of scope):** totals, headlines, subscriber counts, and some county rows.
- **All reports with cause columns:** how many rows and sites had no cause, and the largest gaps.
- **Secondhand:** news and search summaries of Isaias outages (about 18% of sites out in Florida, 17% in Alabama, over 600 sites); a 3.6% Connecticut figure for Isaias 2020; the span of report dates for several 2017–2024 storms, which hints at recovery length; Helene's 4,562 sites out on Sep 28, 2024 and the pooled cause shares in Olukola et al. (both in the project docs).
- **Storm strength:** landfall category for Michael and Isaias, and wind speed for Isaias.
- **Not seen (at first registration):** EAGLE-I, SVI or county exposure data, any computed recovery time, and county tables from any other report.
- **Seen after registration, before chapter 3 was computed (added 2026-11-22):** while building steps 3-8, Claude Code saw every report's parsed county rows and totals, step 4's console output with each report's computed and stated overall % out (so each storm's day-by-day overall % out), the validation summaries shown to the author (status by storm; cause-gap counts), Helene's Sep 28 rows summing to 4,562 sites out, EAGLE-I match rates and state coverage by storm, the count of counties inside each storm's 34- and 64-kt radii and the median distance to track, FEMA declared-county counts by storm, and Michael's 261 sites served in Jefferson County, FL. Not seen: any computed peak by storm as defined in ch. 3, recovery times, site-days lost, cause shares by day, the power coupling, or any SVI breakdown.
- **The author, Timothy D. Spivey, in his own words:** "The author works in telecommunications operations on the Gulf Coast, has general professional familiarity with storm restoration from that work, and lived through several of these storms locally. No non-public or employer data was used in this project. Beyond the items listed above, the author has seen only what Claude Code reported during setup: the full Isaias Oct 12 county table, the cause-gap counts for the ten validation reports, and the report date range for each storm, which hints at how long recovery took."

## Questions
1. How much of the network goes dark, and how long until it is back?
2. Why do cell sites go dark: damage, power, transport, or no cause given?
3. How closely do telecom outages co-move with power outages?
4. Are exposure and social vulnerability associated with how long counties wait?
5. Did the 2022–2025 FCC rules (MDRI, mandatory DIRS) coincide with faster recovery? **Descriptive only.**

## Scope and keys
- Gulf and Southeast hurricanes, 2017–2026, in the ten states in `config.STUDY_STATES`, with public DIRS county tables.
- The storm list is fixed from activation notices before recovery is computed. Every exclusion is listed with a reason.
- Puerto Rico is out of scope. Both Fiona reports are marked `out_of_scope`.
- **Storm key:** NHC ID plus DIRS activation date (the first notice's release date), never the name.
- **Unit:** county (5-digit FIPS) × report, with each report's as-of time.

## Validation
- **Every report in scope must pass step 4 before use,** not a sample. A failure stops the build.
- `flagged` and `known_fcc_inconsistency` reports are used, with each reason from `validation_dirs.csv` stated in the page's methods.
- Exceptions come only from the three checked lists in `manifest/`.
- Excepted counties stay in sites served, as printed. The page uses the computed % out and records the stated one.

## Reporting rules
- Every outage figure is given as a count and a percent, with its sites-served denominator.
- Every headline number carries its uncertainty and comes from `results.json`.
- A gap of one day may be interpolated for display, and is marked. Longer gaps are never interpolated. Event times across any gap are interval-censored.
- A county that leaves the reports, or is still out at deactivation, is censored, not recovered.
- Every time chart marks the rule periods.
- Wording is "is associated with", "co-moves with" or "coincides with".

## Outcomes
- **Peak (ch. 3):** most sites out, as a count and a percent, by days since landfall, with cable and wireline subscribers out.
- **Recovery (ch. 4):** share of affected sites restored by day since peak, where affected means the number out at the peak. Report time to 50% and to 90% restored and site-days lost, with county-bootstrap bands. Where counties leave the reports, show bounds.
- **Waiting time (ch. 8):** time until a county is below 5% of sites out.
- **Rebound rule (decided 2026-11-22, before any chapter 4 result was seen):** a county (or a storm's total) counts as reaching 50% or 90% restored, or below 5% out, at the first report from which it stays past that threshold in every later report that includes it. If it leaves the reports before then, it is censored. Times are interval-censored between that report and the one before. The first crossing is a sensitivity display.

## Causes (ch. 5)
- Damage, power, transport and "unattributed" shares are reported together, by day and storm.
- **Every cause share is a share of sites out, not just of attributed sites.**
- `out_overattributed` is shown beside the shares and never netted against unattributed sites. It is described as consistent with sites out for more than one cause, not as an FCC error. Eleven reports (Idalia 2023, Beryl 2024) print the FCC's note that totals "may differ from the sum of numbers of cell sites out by cause" because of "sites being out due to multiple causes or because providers are still assessing the causes"; `validation_dirs.csv` records which (`fcc_multiple_causes_note`). Earlier reports carry no such note, so for them the reading is an inference, and the page says so.
- A report without cause columns (Michael, Oct 20, 2018) is "not collected", not zero, and is left out of the share denominators.
- Shares published on an attributed-only base, as in Olukola et al., are not directly comparable.

## Power (ch. 6)
- EAGLE-I value nearest each report's as-of time, within 30 minutes, plus 6, 12 and 24 hours earlier for lead and lag.
- Use the coverage and modeled-customer files, and flag low-coverage counties on every result. "Customers" means meters.
- EAGLE-I covers 2014–2025, so **Isaias 2026 has no power match or overlay** until a 2026 release exists. poweroutage.us is not a substitute.

## Exposure and waiting time (ch. 7–8)
- **Exposure:** distance to track, wind at the nearest track point, and 34/50/64-kt radii, from HURDAT2 through 2025 and the NHC GIS best track for 2026.
- **Chapter 7:** a simple calibrated model of peak % out on exposure.
- **Chapter 8:** time to below 5% out by SVI 2022 quartile. Discrete-time hazard (complementary log-log) with exposure, storm fixed effects, county-clustered standard errors, and interval and right censoring.
- **This model is not used for the rules:** storm fixed effects absorb the rule periods.

## Rule periods
| Period | Storm's DIRS activation date | Known storms (confirm from FCC activation notices) |
|---|---|---|
| P0: neither rule | Before 2024-05-01 | Michael and other earlier storms |
| P1: MDRI only | 2024-05-01 to 2025-02-19 | Beryl, Debby, Francine, Helene, Milton |
| P2: MDRI and mandatory DIRS | 2025-02-20 to 2026-06-29 | Possibly no hurricane |
| P3: both, DIRS modified | 2026-06-30 onward | Isaias (October 2026) |

The FCC's Third Report and Order (FCC 26-34) removed DIRS final reports and exempted non-facilities-based filers from 2026-06-30. Form and field changes follow at dates still to be announced. **The only post-mandate hurricane identified so far falls after that change.**

## Policy chapter (ch. 9): descriptive only
- Show each storm's peak, time to 50% and 90%, site-days lost and censoring, grouped by period, with its band and exposure.
- For each period, give the number of storms and the median and range across storms. A period with one storm is shown as that storm.
- No regression on period, hazard ratio, significance test, p-value or adjusted difference between periods.
- The strongest permitted wording is "recovery in storms after the rule coincided with shorter (or longer) times".

## Sensitivity displays (all reported, whatever they show)
1. Drop one storm at a time, and separately the Helene-Milton overlap counties.
2. Hold each county's sites served at its peak-day value.
3. Best and worst cases for censored counties.
4. With and without low-coverage EAGLE-I counties (state's minimum covered share below 0.75 that year; 2017, 2023 and 2024 are coverage_unknown and shown separately) (ch. 6).
5. With and without flagged reports.
5b. Without reports with a serious flag only (deviation, added 2026-11-22 after the chapter 3 result: see docs/decisions.md). Serious: headline_mismatch, state_total_missing, no_printed_totals, outside_notice_area, table_not_in_list (and the names check's "in table, not in the report's county list"). Benign: causes short of sites out, spelling variants, over-attribution confirmed by the second reading, a name the FCC lists twice, and entries on the checked exception lists.
6. With and without reports kept by the state_total_missing rule (Helene Sep 28, 2024), which was made after seeing that it would restore that report.
7. EAGLE-I with a missing record treated as zero customers out, only for counties with at least one EAGLE-I record in that storm's window (the main results leave it blank) (ch. 6).

## Red flags (any one means "coincided with faster recovery" is not written)
- Dropping any one storm reverses the ordering of periods.
- The ordering depends on 50% versus 90%, or on the treatment of censoring.
- Recovery was already shortening across P0 by a similar amount.
- The county site denominators jump at a rule date, or move more than 10% within a storm.
- Activations end systematically sooner, or with more counties still out, in one period.
- Wind exposure or peak outage has no overlap across periods.

## What this design can't rule out
**With few storms per period, this is association, not proof.**
- Anything else that changed over time: hardening, backup power, 5G build-out, satellite backhaul, utility practice, the voluntary framework that preceded MDRI.
- Differences between storms that wind, intensity and power data do not capture, such as flooding, road access and fiber cuts.
- A change in measurement rather than in restoration. Mandatory reporting changes who reports, so measured outages can move with no change on the ground.
- Mandatory DIRS, the June 2026 changes and Isaias itself coincide and can't be told apart.
- Anticipation, since MDRI was adopted in 2022 and some carriers may have complied early.
- Carrier-level behavior, since public tables combine all providers.
- Seeing no difference between periods does not show that there was none.

## Before approval
- [ ] Add the daily reports to the manifest and pass step 4 on all of them.
- [x] Set the low-coverage threshold for EAGLE-I (0.75, 2026-11-22).
- [x] Decide how a rebound after crossing 50%, 90% or 5% is timed: the first report from which the threshold holds in every later report (2026-11-22); first crossing is a sensitivity display.
- [x] Resolve Virginia's "Franklin, Franklin" (county or city) for FIPS: a plain name is the county; the tables write cities as "X CITY".
- [x] Check Michael's 261 sites served in Jefferson County, FL (Isaias reports 40): printed in all 16 Michael reports with 0 out, confirmed by the second reading. Kept as printed and flagged as an apparent FCC denominator error; Michael's peak is also given without it (2026-11-22).
- [ ] Complete "Seen before registration", then commit before computing any outcome.

## When it publishes
- Follow the threshold-site demos convention: the public snapshot (code, tests, manifests, docs, results) goes in `demos/hurricane_resilience/`, and the page goes on the Work page with the demonstration tag.
- The publish step copies `output/validation_summary.csv` into the snapshot.
- Each chapter uses the retention playbook's layout: claim, exhibit, what it means. Then methods, data, licenses and sources.
- The cleaned county-day panel is published under CC BY 4.0 with the parser, keeping `out_unattributed` and `out_overattributed`.
- Show the OpenFEMA disclaimer, cite the EAGLE-I DOIs, and don't redistribute the Olukola et al. dataset.
- An independent check of every number and claim against `results.json` comes before publishing.

## Sources
Only entries marked VERIFIED in `docs/literature.md` are cited. For the rules: FCC 21-34, FCC 22-50 (MDRI), FCC 24-5 and DA 25-74 (mandatory DIRS), FCC 26-34. Rule identifiers and dates checked 2026-11-22: DA 25-74 is the PSHSB notice (adopted Jan 21, 2025) setting February 20, 2025 as the compliance date for mandatory DIRS (Federal Register 2025-00495); FCC 26-34 (adopted May 20, released May 21, 2026) was published in the Federal Register on June 30, 2026 (2026-13155), and the FCC says its final-report removal and non-facilities-based exemption take effect on publication. The MDRI date (May 1, 2024) is from the November 16 research. FCC 21-34 is not used.

## Future covariates (not in this version)
- FCC Broadband Map county summaries (cable, fiber, fixed wireless availability): dropped from this version on 2026-11-22 after broadbandmap.fcc.gov/robots.txt returned 403.
