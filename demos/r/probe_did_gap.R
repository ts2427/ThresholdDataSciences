# Probe (synthetic data only): how did::att_gt handles (1) a missing
# calendar year and (2) time-varying weights. No real data touched.
suppressPackageStartupMessages(library(did))
set.seed(1)
years <- c(2015:2019, 2021:2024)            # 2020 missing
units <- 1:60
g <- rep(c(0, 2019, 2021, 2022), each = 15)
d <- expand.grid(id = units, year = years)
d$g <- g[d$id]
d$y <- rnorm(nrow(d)) + 0.1 * d$year + ifelse(d$g > 0 & d$year >= d$g, -5, 0)
d$w_const <- 100 + d$id
d$w_vary  <- 100 + d$id + (d$year - 2015)
r <- att_gt("y", "year", "id", "g", data = d, control_group = "notyettreated",
            base_period = "universal", est_method = "dr", bstrap = TRUE,
            clustervars = "id", weightsname = "w_const", print_details = FALSE)
cat("\n(g,t) pairs reported for g=2021:\n")
print(data.frame(group = r$group, t = r$t, att = round(r$att, 2))[r$group == 2021, ])
es <- aggte(r, type = "dynamic", na.rm = TRUE)
cat("\nevent times reported by aggte(dynamic):\n"); print(es$egt)
cat("\ntime-varying weights:\n")
res <- tryCatch({att_gt("y", "year", "id", "g", data = d, control_group = "notyettreated",
            base_period = "universal", est_method = "dr", weightsname = "w_vary",
            print_details = FALSE); "accepted"}, error = function(e) conditionMessage(e),
            warning = function(w) paste("WARNING:", conditionMessage(w)))
print(res)
