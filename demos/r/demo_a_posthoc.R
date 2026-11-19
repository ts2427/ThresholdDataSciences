# Robustness rows NOT in the pre-registered plan (docs/analysis_plan.md):
#  - "Drop the 2015 cohort (IN, NH, PA)": added AFTER seeing results,
#    prompted by that cohort's pre-trend (docs/decisions.md).
#  - "Drop the 2014 adopters": required by the original brief's step 3 but
#    omitted from the plan; added after seeing results.
# Same estimator settings as r/demo_a_main.R.
suppressPackageStartupMessages({library(did); library(data.table)})
SEED <- 20261119; BITERS <- 2000; MAIN_COHORTS <- c(2014, 2015, 2016, 2019)
p <- fread("data/processed/analysis_panel.csv", colClasses = list(character = "fips"))
p[, id := as.integer(fips)]
d0 <- p[year <= 2019]
d0[, g := fifelse(cohort %in% MAIN_COHORTS, cohort, 0L)]
d0[, y := 100 * lowinc_rate]; d0[, w := lowinc_pop]
run <- function(d) {
  set.seed(SEED)
  r <- att_gt("y", "year", "id", "g", data = as.data.frame(d), control_group = "notyettreated",
              est_method = "dr", base_period = "universal", bstrap = TRUE, biters = BITERS,
              clustervars = "id", weightsname = "w", print_details = FALSE)
  set.seed(SEED)
  a <- aggte(r, type = "group", bstrap = TRUE, biters = BITERS, clustervars = "id")
  data.table(att = a$overall.att, se = a$overall.se, lo = a$overall.att - 1.96 * a$overall.se,
             hi = a$overall.att + 1.96 * a$overall.se, states = uniqueN(d$id),
             treated_states = uniqueN(d[g > 0]$id))
}
rows <- rbind(
  cbind(check = "Drop the 2015 cohort (IN, NH, PA)", added = "after seeing results (2015 pre-trend)",
        run(d0[g != 2015])),
  cbind(check = "Drop the 2014 adopters", added = "after seeing results (from the brief, omitted from the plan)",
        run(d0[g != 2014])))
fwrite(rows, "results/demo_a/robustness_posthoc.csv")
print(rows)
