import numpy as np
import pandas as pd
import pytest
import statsmodels.formula.api as smf

from medicaid_did.src.twfe_weights import residualize_two_way, twfe_cell_weights


def _staggered():
    rows = []
    for u, g in {1: 0, 2: 0, 3: 2, 4: 2, 5: 4}.items():
        for t in range(1, 6):
            treat = int(g > 0 and t >= g)
            effect = (t - g + 1) if treat else 0       # growing effect
            rows.append({"id": u, "year": t, "treat": treat, "w": 1.0 + u,
                         "y": u + 0.3 * t + effect, "effect": effect})
    return pd.DataFrame(rows)


def test_residualize_removes_means():
    df = _staggered()
    r = residualize_two_way(df["treat"], df["id"], df["year"], df["w"])
    for key in ("id", "year"):
        assert np.allclose((r * df.w).groupby(df[key]).sum(), 0, atol=1e-9)


def test_weights_sum_to_one_and_reconstruct_twfe():
    df = _staggered()
    cw = twfe_cell_weights(df)
    assert cw["twfe_weight"].sum() == pytest.approx(1.0)
    fit = smf.wls("y ~ treat + C(id) + C(year)", data=df, weights=df.w).fit()
    assert fit.params["treat"] == pytest.approx((cw.twfe_weight * cw.effect).sum(), abs=1e-8)
