import pandas as pd
import pytest

from medicaid_did.src.panel import build_panel, main_window_group, weighted_group_rates


def _inputs():
    rates = pd.DataFrame({"year": [2013, 2013], "fips": ["01", "02"],
                          "lowinc_rate": [0.3, 0.2], "lowinc_pop": [100, 300]})
    exp = pd.DataFrame({"state": ["A", "B"], "first_treated_year": [2014, None],
                        "prior_coverage_kaestner": ["none", "none"]})
    names = pd.DataFrame({"fips": ["01", "02"], "state": ["A", "B"]})
    return rates, exp, names


def test_build_panel_cohorts():
    p = build_panel(*_inputs())
    assert p.set_index("fips")["cohort"].to_dict() == {"01": 2014, "02": 0}


def test_build_panel_missing_fips_raises():
    rates, exp, names = _inputs()
    with pytest.raises(ValueError):
        build_panel(rates, exp, names.iloc[:1])


@pytest.mark.parametrize("c,label", [(2014, "2014"), (2019, "2019"), (0, "untreated through 2019"),
                                     (2021, "untreated through 2019")])
def test_main_window_group(c, label):
    assert main_window_group(c) == label


def test_main_window_group_rejects_unlisted_cohort():
    with pytest.raises(ValueError):
        main_window_group(2017)


def test_weighted_group_rates():
    p = build_panel(*_inputs()).assign(g="all")
    out = weighted_group_rates(p, "g")
    assert out.loc[0, "rate_pct"] == pytest.approx(100 * (30 + 60) / 400)
    assert out.loc[0, "states"] == 2
