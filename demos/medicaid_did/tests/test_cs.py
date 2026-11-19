import numpy as np
import pandas as pd
import pytest

from medicaid_did.src.cs import att_gt, base_period, cluster_bootstrap, dynamic


def _panel(years, effect=-5.0):
    """3 never-treated, 2 cohort-2019, 2 cohort-2021 units; parallel trends,
    constant effect from g onward."""
    rows = []
    cohorts = {1: 0, 2: 0, 3: 0, 4: 2019, 5: 2019, 6: 2021, 7: 2021}
    for u, g in cohorts.items():
        for t in years:
            y = 10 + u + 0.5 * (t - years[0]) + (effect if g and t >= g else 0)
            rows.append({"id": u, "year": t, "g": g, "y": y, "w": 1.0 + u})
    return pd.DataFrame(rows)


def test_base_period_skips_gap():
    assert base_period(2021, [2017, 2018, 2019, 2021]) == 2019
    assert base_period(2019, [2017, 2018, 2019, 2021]) == 2018
    with pytest.raises(ValueError):
        base_period(2017, [2017, 2018])


def test_att_gt_recovers_effect_and_calendar_event_time():
    years = [2016, 2017, 2018, 2019, 2021, 2022]
    cells = att_gt(_panel(years))
    post = cells[cells.t >= cells.g]
    assert np.allclose(post.att, -5.0)
    pre = cells[cells.t < cells.g]
    assert np.allclose(pre.att, 0.0)
    # 2021 cohort: base 2019 is e=-2 in calendar years; no e=-1 row (2020 absent)
    c21 = cells[cells.g == 2021]
    assert -1 not in set(c21.e) and set(c21.e) == {-5, -4, -3, 0, 1}


def test_att_gt_not_yet_treated_controls():
    years = [2016, 2017, 2018, 2019, 2021, 2022]
    cells = att_gt(_panel(years)).set_index(["g", "t"])
    # at t=2019, cohort 2021 is not yet treated -> 3 never + 2 cohort-2021
    assert cells.loc[(2019, 2019), "n_control"] == 5
    # at t=2021 nobody but never-treated
    assert cells.loc[(2019, 2021), "n_control"] == 3


def test_att_gt_unbalanced_raises():
    p = _panel([2017, 2018, 2019]).iloc[1:]
    with pytest.raises(ValueError):
        att_gt(p)


def test_dynamic_weights_by_cohort_size():
    cells = pd.DataFrame({"g": [2019, 2021], "t": [2019, 2021], "e": [0, 0], "att": [-4.0, -8.0]})
    df = pd.DataFrame({"id": [1, 2], "year": [2018, 2018], "g": [2019, 2021], "w": [1.0, 3.0]})
    out = dynamic(cells, df)
    assert out.loc[0, "att"] == pytest.approx((-4 * 1 + -8 * 3) / 4)
    assert out.loc[0, "cohorts"] == 2


def test_cluster_bootstrap_shape_and_determinism():
    p = _panel([2017, 2018, 2019, 2021])
    fn = lambda d: pd.Series({"mean_y": d.y.mean()})
    a = cluster_bootstrap(p, fn, reps=20, seed=1)
    b = cluster_bootstrap(p, fn, reps=20, seed=1)
    assert a.shape == (20, 1) and a.equals(b)


def test_overall_group():
    from medicaid_did.src.cs import overall_group
    cells = pd.DataFrame({"g": [2014, 2014, 2016, 2016], "t": [2014, 2015, 2015, 2016],
                          "att": [-2.0, -4.0, 9.0, -6.0]})
    # 2016's pre cell (t=2015) is ignored; cohort means -3 and -6, sizes 1:2
    assert overall_group(cells, {2014: 1.0, 2016: 2.0}) == pytest.approx((-3 * 1 + -6 * 2) / 3)


def test_cohort_sizes_uses_first_year():
    from medicaid_did.src.cs import cohort_sizes
    df = pd.DataFrame({"id": [1, 1, 2, 2], "year": [2017, 2019, 2017, 2019],
                       "g": [2019, 2019, 0, 0], "w": [5.0, 7.0, 1.0, 1.0]})
    assert cohort_sizes(df) == {2019: 5.0}
