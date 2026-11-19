# Demo A step 2: main-window estimates, exactly as docs/analysis_plan.md.
#   Rscript r/demo_a_main.R
# Reads data/processed/analysis_panel.csv; writes CSVs to results/demo_a/
# (assembled into results/medicaid_did.json by medicaid_did/src/step2_collect.py).
suppressPackageStartupMessages({
  library(did); library(fixest); library(HonestDiD); library(data.table)
})
SEED <- 20261119; BITERS <- 2000
MAIN_COHORTS <- c(2014, 2015, 2016, 2019)
out_dir <- "results/demo_a"; dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

panel <- fread("data/processed/analysis_panel.csv", colClasses = list(character = "fips"))
panel[, id := as.integer(fips)]

main_data <- function(p, utah_2019 = FALSE, drop = character(0), outcome = "lowinc") {
  d <- copy(p)[year <= 2019 & !(state %in% drop)]
  if (utah_2019) d[state == "Utah", cohort := 2019L]
  d[, g := fifelse(cohort %in% MAIN_COHORTS, cohort, 0L)]
  d[, y := 100 * get(paste0(outcome, "_rate"))]
  d[, w := get(paste0(outcome, "_pop"))]
  d[]
}

run_cs <- function(d, weighted = TRUE) {
  set.seed(SEED)
  att_gt(yname = "y", tname = "year", idname = "id", gname = "g", data = as.data.frame(d),
         control_group = "notyettreated", est_method = "dr", base_period = "universal",
         bstrap = TRUE, biters = BITERS, clustervars = "id",
         weightsname = if (weighted) "w" else NULL, print_details = FALSE)
}

overall <- function(r) {
  set.seed(SEED)
  a <- aggte(r, type = "group", bstrap = TRUE, biters = BITERS, clustervars = "id")
  list(agg = a, row = data.frame(att = a$overall.att, se = a$overall.se,
                                 lo = a$overall.att - 1.96 * a$overall.se,
                                 hi = a$overall.att + 1.96 * a$overall.se))
}

event <- function(r) {
  set.seed(SEED)
  aggte(r, type = "dynamic", min_e = -5, max_e = 5, bstrap = TRUE, biters = BITERS,
        clustervars = "id")
}

# ---------------------------------------------------------------- headline --
d0 <- main_data(panel)
fwrite(d0[, .N, by = .(g)][order(g)], file.path(out_dir, "main_cohort_sizes.csv"))
specs <- list(pop = TRUE, equal = FALSE)
res <- list()
for (nm in names(specs)) {
  r <- run_cs(d0, specs[[nm]])
  o <- overall(r); es <- event(r)
  res[[nm]] <- list(r = r, o = o, es = es)
  fwrite(cbind(spec = nm, o$row), file.path(out_dir, paste0("overall_", nm, ".csv")))
  fwrite(data.frame(spec = nm, group = o$agg$egt, att = o$agg$att.egt, se = o$agg$se.egt),
         file.path(out_dir, paste0("cohort_att_", nm, ".csv")))
  fwrite(data.frame(spec = nm, group = r$group, t = r$t, att = r$att, se = r$se),
         file.path(out_dir, paste0("attgt_", nm, ".csv")))
  # event study: pointwise and uniform bands
  inf <- es$inf.function$dynamic.inf.func.e
  n <- nrow(inf)
  V <- crossprod(inf) / n^2
  ev <- data.frame(spec = nm, e = es$egt, att = es$att.egt, se = es$se.egt,
                   lo = es$att.egt - 1.96 * es$se.egt, hi = es$att.egt + 1.96 * es$se.egt,
                   lo_uniform = es$att.egt - es$crit.val.egt * es$se.egt,
                   hi_uniform = es$att.egt + es$crit.val.egt * es$se.egt,
                   crit_uniform = es$crit.val.egt)
  fwrite(ev, file.path(out_dir, paste0("event_", nm, ".csv")))
  # pre-trend joint Wald test, e = -5..-2, influence-function covariance
  pre <- which(es$egt %in% -5:-2)
  b <- es$att.egt[pre]; Vp <- V[pre, pre]
  W <- as.numeric(t(b) %*% solve(Vp) %*% b)
  fwrite(data.frame(spec = nm, wald = W, df = length(pre), p = pchisq(W, length(pre), lower.tail = FALSE),
                    did_Wpval = ifelse(is.null(r$Wpval), NA, r$Wpval)),
         file.path(out_dir, paste0("pretest_", nm, ".csv")))
  if (nm == "pop") {
    keep <- which(es$egt != -1)
    saveRDS(list(beta = es$att.egt[keep], V = V[keep, keep], e = es$egt[keep]),
            file.path(out_dir, "es_pop_for_honestdid.rds"))
  }
}

# ------------------------------------------------------------------- TWFE --
d0[, treat := as.integer(g > 0 & year >= g)]
tw_w <- feols(y ~ treat | id + year, data = d0, weights = ~w, cluster = ~id)
tw_u <- feols(y ~ treat | id + year, data = d0, cluster = ~id)
tw <- rbind(data.frame(spec = "pop", att = coef(tw_w)[["treat"]], se = se(tw_w)[["treat"]]),
            data.frame(spec = "equal", att = coef(tw_u)[["treat"]], se = se(tw_u)[["treat"]]))
tw$lo <- tw$att - 1.96 * tw$se; tw$hi <- tw$att + 1.96 * tw$se
fwrite(tw, file.path(out_dir, "twfe.csv"))

# ------------------------------------------------------------- robustness --
rob <- list(
  "Drop DE, DC, MA, NY, VT" = list(drop = c("Delaware", "District of Columbia", "Massachusetts", "New York", "Vermont")),
  "Drop DC only" = list(drop = "District of Columbia"),
  "Utah coded first treated 2019" = list(utah_2019 = TRUE),
  "Utah dropped" = list(drop = "Utah"),
  "Wisconsin dropped" = list(drop = "Wisconsin"),
  "New Hampshire dropped" = list(drop = "New Hampshire"),
  "All adults 19-64" = list(outcome = "all")
)
rows <- list()
for (nm in names(rob)) {
  a <- rob[[nm]]
  d <- main_data(panel, utah_2019 = isTRUE(a$utah_2019), drop = if (is.null(a$drop)) character(0) else a$drop,
                 outcome = if (is.null(a$outcome)) "lowinc" else a$outcome)
  o <- overall(run_cs(d, TRUE))
  rows[[nm]] <- cbind(check = nm, o$row, states = uniqueN(d$id), treated_states = uniqueN(d[g > 0]$id))
}
rows[["Equal state weights"]] <- cbind(check = "Equal state weights", res$equal$o$row,
                                       states = uniqueN(d0$id), treated_states = uniqueN(d0[g > 0]$id))
fwrite(rbindlist(rows), file.path(out_dir, "robustness.csv"))

# HonestDiD: see r/demo_a_honestdid.R (reads es_pop_for_honestdid.rds).
cat("done
")
