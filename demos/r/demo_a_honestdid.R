# Demo A step 2, HonestDiD (analysis plan §6). Relative-magnitudes bounds on
# the main-window event study (headline weighting).
#   Rscript r/demo_a_honestdid.R
# Breakdown value: the largest Mbar on the grid 0, 0.05, ..., 3 at which the
# robust 95% interval excludes zero. Robust intervals widen monotonically in
# Mbar, so the grid point is found by bisection over the grid (same answer
# as evaluating every grid point, in ~6 evaluations instead of 61).
suppressPackageStartupMessages({library(HonestDiD); library(data.table)})
out_dir <- "results/demo_a"
h <- readRDS(file.path(out_dir, "es_pop_for_honestdid.rds"))
npre <- sum(h$e < 0); npost <- sum(h$e >= 0)
rm_ci <- function(M, l) {
  s <- createSensitivityResults_relativeMagnitudes(betahat = h$beta, sigma = h$V,
         numPrePeriods = npre, numPostPeriods = npost, Mbarvec = M, l_vec = l)
  data.frame(Mbar = s$Mbar, lb = s$lb, ub = s$ub, method = s$method)
}
excludes0 <- function(ci) ci$ub < 0 | ci$lb > 0
targets <- list(avg_post = rep(1 / npost, npost), e0 = c(1, rep(0, npost - 1)))
hd <- list(); bd <- list()
for (tn in names(targets)) {
  l <- targets[[tn]]
  t0 <- Sys.time()
  orig <- constructOriginalCS(betahat = h$beta, sigma = h$V, numPrePeriods = npre,
                              numPostPeriods = npost, l_vec = l)
  main <- rm_ci(c(0.5, 1, 1.5, 2), l)
  hd[[tn]] <- rbind(data.frame(target = tn, Mbar = NA, lb = orig$lb, ub = orig$ub, method = "original"),
                    cbind(target = tn, main))
  grid <- seq(0, 3, by = 0.05)
  if (!excludes0(rm_ci(grid[1], l))) {
    bdv <- NA
  } else if (excludes0(rm_ci(grid[length(grid)], l))) {
    bdv <- grid[length(grid)]
  } else {
    lo <- 1; hi <- length(grid)          # excludes at lo, not at hi
    while (hi - lo > 1) {
      mid <- (lo + hi) %/% 2
      if (excludes0(rm_ci(grid[mid], l))) lo <- mid else hi <- mid
    }
    bdv <- grid[lo]
  }
  bd[[tn]] <- data.frame(target = tn, breakdown_Mbar = bdv, grid_step = 0.05, grid_max = 3)
  cat(tn, "done in", round(as.numeric(difftime(Sys.time(), t0, units = "secs"))), "s; breakdown", bdv, "\n")
}
fwrite(rbindlist(hd), file.path(out_dir, "honestdid.csv"))
fwrite(rbindlist(bd), file.path(out_dir, "honestdid_breakdown.csv"))
