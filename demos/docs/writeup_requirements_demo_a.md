# Demo A write-up requirements (Tim, 2026-11-19)

Carried into the site page `content/analysis/` when Tim says go. Numbers are
pulled from `results/medicaid_did.json`, never typed.

1. **Naive vs careful = before-and-after vs comparison-group-adjusted.**
   The main contrast and the second figure: the 2014 cohort's 2013 rate vs
   its 2016–2019 average with no comparison group (`naive_vs_careful.point.naive_change`),
   against the same change net of the comparison states'
   (`naive_vs_careful.point.adjusted_change`), each with its 95% interval.
   **Required sentence (Tim, 2026-11-19), numbers from the JSON:** state that
   the headline is −7.2 (`step2_main.headline.att`), and explain that the
   simple comparison-adjusted figure, −8.2
   (`naive_vs_careful.point.adjusted_change`), is larger because it covers
   only the 2014 cohort and only 2016–2019 — years 2 to 5 after expansion,
   when the effect had grown — against a single 2013 base year and only the
   states untreated through 2019, whereas the headline averages every
   cohort (2014, 2015, 2016, 2019) over every post-expansion year,
   including the first year, when the effect was smallest
   (`step2_main.event_study.pop`, e = 0), with not-yet-treated states also
   in the comparison group. Suggested wording: "The simple comparison gives
   −8.2 points because it looks only at the 2014 states two to five years
   in, when the effect had grown; averaged over every expanding state and
   every year after expansion, including the first, smaller year, the
   effect is −7.2 points — the headline."
2. **Naive TWFE vs Callaway–Sant'Anna stays as a table**, described as a
   check that agrees here because 26 of 34 treated states expanded together
   in 2014 (few staggered comparisons for TWFE to get wrong).
3. **Robustness table** includes "Drop the 2015 cohort (IN, NH, PA)",
   labeled as added after seeing results, prompted by that cohort's
   pre-trend; and "Drop the 2014 adopters", labeled as from the brief but
   added to the analysis after seeing results.
4. **Methods note reports both pre-trend tests:** the pre-specified joint
   test (event-study e = −5…−2; `step2_main.pretest.pop.p`) and `did`'s
   built-in test (`pretest.pop.did_Wpval`), which is unusable here because
   its 24-cell covariance matrix has condition number
   `pretest_investigation.all_cells_test.condition_number` (the 2015, 2016
   and 2019 cohorts have 2–3 states but 5–9 pre-period cells each). Also
   state the 2015 cohort's individually significant pre-period cells.
5. **HonestDiD, stated plainly:** "moderate robustness — the average effect
   stays clear of zero unless the post-expansion violation exceeds 1.5 times
   the largest pre-period deviation" (1.5 = `honestdid_breakdown` avg_post).
6. **Benchmarks:** both figures come from the studies' abstracts and use
   different populations (NHIS citizens; low-educated adults), so the
   comparison is approximate.
