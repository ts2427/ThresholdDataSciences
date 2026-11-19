"""Unconditional Callaway–Sant'Anna ATT(g,t) in CALENDAR years, for the
secondary analysis (2009–2024 with 2020 absent).

Why not R `did` there: `did` renumbers observed years consecutively, so with
2020 missing it treats 2019 and 2021 as adjacent and shifts every event
time after the gap (shown on synthetic data by r/probe_did_gap.R). Here:

- base period b(g) = the last OBSERVED year before g (universal base);
- event time e = t − g in calendar years, so no e falls on 2020 and a gap
  remains; nothing is interpolated;
- comparison units at (g,t): never-treated, or first treated after
  max(t, b(g)) (not-yet-treated), excluding cohort g;
- weights: each unit's weight in the earlier of the two years compared
  (as `did` does for time-varying weights).

With no covariates the doubly robust estimator equals this difference in
weighted mean changes. Checked against `did` on the main window
(tests + medicaid_did/src/step2_collect.py).
"""
import numpy as np
import pandas as pd


def base_period(g, years):
    prior = [y for y in years if y < g]
    if not prior:
        raise ValueError(f"cohort {g} has no observed pre-period")
    return max(prior)


def att_gt(df, y="y", w="w", unit="id", time="year", group="g"):
    """df: one row per unit-year with outcome y, weight w, cohort g (0 =
    never treated in this sample). Returns a DataFrame of (g, t, e, att,
    n_treated, n_control)."""
    years = sorted(df[time].unique())
    Y = df.pivot(index=unit, columns=time, values=y)
    W = df.pivot(index=unit, columns=time, values=w)
    G = df.groupby(unit)[group].first()
    if Y.isna().any().any():
        raise ValueError("panel is not balanced")
    rows = []
    for g in sorted(c for c in G.unique() if c > 0):
        b = base_period(g, years)
        treated = G.index[G == g]
        for t in years:
            if t == b:
                continue
            ctrl = G.index[(G != g) & ((G == 0) | (G > max(t, b)))]
            if len(ctrl) == 0:
                continue
            wt = W[min(t, b)]
            dy = Y[t] - Y[b]
            att = (np.average(dy[treated], weights=wt[treated])
                   - np.average(dy[ctrl], weights=wt[ctrl]))
            rows.append({"g": g, "t": t, "e": t - g, "att": att,
                         "n_treated": len(treated), "n_control": len(ctrl)})
    return pd.DataFrame(rows)


def dynamic(cells, df, w="w", unit="id", group="g", e_range=None):
    """Event-time averages: ATT(e) = sum_g share_g * ATT(g, g+e) over the
    cohorts observed at e, with share_g proportional to cohort size
    (cohort_sizes: unit weights in the first sample year, as in `did`)."""
    size = cohort_sizes(df, w=w, group=group)
    c = cells.assign(size=cells["g"].map(size))
    if e_range is not None:
        c = c[c["e"].between(*e_range)]
    out = (c.groupby("e")
             .apply(lambda s: pd.Series({"att": np.average(s["att"], weights=s["size"]),
                                         "cohorts": int(s["g"].nunique())}),
                    include_groups=False)
             .reset_index())
    return out


def cluster_bootstrap(df, fn, reps=2000, seed=20261119, unit="id"):
    """Resample units (states) with replacement, re-run fn(sample_df) -> Series
    indexed by a key; return the bootstrap draws as a DataFrame."""
    rng = np.random.default_rng(seed)
    units = df[unit].unique()
    by_unit = {u: d for u, d in df.groupby(unit)}
    draws = []
    for _ in range(reps):
        pick = rng.choice(units, size=len(units), replace=True)
        parts = []
        for k, u in enumerate(pick):
            d = by_unit[u].copy()
            d[unit] = k          # resampled copies are distinct units
            parts.append(d)
        draws.append(fn(pd.concat(parts, ignore_index=True)))
    return pd.DataFrame(draws)


def cohort_sizes(df, w="w", group="g"):
    """Cohort size = sum of unit weights in the FIRST sample year, as R
    `did` computes its group probabilities (verified on the main window)."""
    first = min(df["year"])
    return {g: df.loc[(df[group] == g) & (df["year"] == first), w].sum()
            for g in sorted(c for c in df[group].unique() if c > 0)}


def overall_group(cells, sizes):
    """did's aggte(type='group') overall ATT: each cohort's mean post-period
    ATT(g,t), averaged across cohorts with weights proportional to size."""
    post = cells[cells["t"] >= cells["g"]]
    by_g = post.groupby("g")["att"].mean()
    wts = np.array([sizes[g] for g in by_g.index], dtype=float)
    return float(np.average(by_g.values, weights=wts))
