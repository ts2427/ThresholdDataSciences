# Investigation (red-flag protocol, analysis plan §8): why did's built-in
# pre-test (Wpval) is 0 under population weights while the pre-specified
# event-study joint test is not significant.
suppressPackageStartupMessages({library(did); library(data.table)})
SEED <- 20261119
p <- fread("data/processed/analysis_panel.csv", colClasses = list(character = "fips"))
p[, id := as.integer(fips)]
d <- p[year <= 2019]; d[, g := fifelse(cohort %in% c(2014, 2015, 2016, 2019), cohort, 0L)]
d[, y := 100 * lowinc_rate]; d[, w := lowinc_pop]
set.seed(SEED)
r <- att_gt("y", "year", "id", "g", data = as.data.frame(d), control_group = "notyettreated",
            est_method = "dr", base_period = "universal", bstrap = FALSE,
            weightsname = "w", print_details = FALSE)
n <- nrow(r$inffunc); pre <- which(r$t < r$group - 1)   # excludes the base cells
IF <- as.matrix(r$inffunc[, pre]); V <- crossprod(IF) / n
b <- r$att[pre]
ev <- eigen(V, symmetric = TRUE, only.values = TRUE)$values
cat("pre-period cells:", length(pre), " rank(V):", qr(V)$rank, "\n")
cat("eigenvalues (smallest 5):", signif(tail(ev, 5), 3), "\n")
cat("condition number:", signif(max(ev) / min(ev), 3), "\n")
W <- tryCatch(n * as.numeric(t(b) %*% solve(V) %*% b), error = function(e) NA)
cat("Wald with solve():", W, "\n")
Vinv <- MASS::ginv(V); k <- qr(V)$rank
Wg <- n * as.numeric(t(b) %*% Vinv %*% b)
cat("Wald with generalized inverse:", round(Wg, 2), " df:", k, " p:", signif(pchisq(Wg, k, lower.tail = FALSE), 3), "\n")
se <- sqrt(diag(V) / n)
tab <- data.table(group = r$group[pre], t = r$t[pre], e = r$t[pre] - r$group[pre], att = b, se = se, z = b / se)
cat("\nindividually |z|>1.96:", tab[abs(z) > 1.96, .N], "of", nrow(tab), "\n")
print(tab[order(group, t)][, lapply(.SD, function(x) if (is.numeric(x)) round(x, 2) else x)])
for (gg in sort(unique(tab$group))) {
  ix <- which(r$group[pre] == gg); Vg <- V[ix, ix, drop = FALSE]
  kg <- qr(Vg)$rank; Wgg <- n * as.numeric(t(b[ix]) %*% MASS::ginv(Vg) %*% b[ix])
  cat(sprintf("cohort %d: %d pre cells, rank %d, Wald %.2f, p %.3g\n", gg, length(ix), kg, Wgg,
              pchisq(Wgg, kg, lower.tail = FALSE)))
}
fwrite(tab, "results/demo_a/pretest_cells_pop.csv")
coh <- rbindlist(lapply(sort(unique(tab$group)), function(gg) {
  ix <- which(r$group[pre] == gg); Vg <- V[ix, ix, drop = FALSE]; kg <- qr(Vg)$rank
  Wgg <- n * as.numeric(t(b[ix]) %*% MASS::ginv(Vg) %*% b[ix])
  data.table(group = gg, cells = length(ix), wald = Wgg, df = kg, p = pchisq(Wgg, kg, lower.tail = FALSE))
}))
fwrite(coh, "results/demo_a/pretest_by_cohort_pop.csv")
fwrite(data.table(cells = length(pre), rank = qr(V)$rank, condition_number = max(ev) / min(ev),
                  wald = Wg, p = pchisq(Wg, k, lower.tail = FALSE)),
       "results/demo_a/pretest_allcells_pop.csv")
