"""Implicit weights of the static two-way fixed-effects estimator on each
treated state-year (de Chaisemartin & D'Haultfœuille 2020): the TWFE
coefficient equals sum_it w_it * effect_it over treated cells (under
parallel trends), with w_it proportional to the residual of the treatment
indicator after removing state and year fixed effects, times the
regression weight. Negative or unequal weights are why TWFE can differ from
a cohort-share average of effects."""
import numpy as np
import pandas as pd


def residualize_two_way(x, unit, time, w, tol=1e-12, max_iter=10000):
    """Weighted within-transformation of x on unit and time fixed effects
    by alternating projections."""
    r = x.astype(float).copy()
    for _ in range(max_iter):
        prev = r.copy()
        for key in (unit, time):
            m = (r * w).groupby(key).transform("sum") / w.groupby(key).transform("sum")
            r = r - m
        if np.max(np.abs(r - prev)) < tol:
            break
    return r


def twfe_cell_weights(df, d="treat", unit="id", time="year", w="w"):
    """Return treated rows with their implicit TWFE weight (sums to 1)."""
    res = residualize_two_way(df[d], df[unit], df[time], df[w])
    raw = res * df[w]
    treated = df[d] == 1
    denom = (raw * df[d]).sum()
    out = df.loc[treated].copy()
    out["twfe_weight"] = raw[treated] / denom
    return out
