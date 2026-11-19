import pandas as pd
import pytest

from medicaid_did.src.validate import compare_rates


def test_compare_rates():
    pums = pd.DataFrame({"year": [2017, 2017], "fips": ["01", "02"],
                         "lowinc_rate": [0.20, 0.30]})
    pub = pd.DataFrame({"year": [2017, 2017], "fips": ["01", "02"],
                        "lowinc_rate": [0.21, 0.25], "lowinc_rate_moe90": [0.02, 0.02]})
    s, j = compare_rates(pums, pub)
    assert s["n"] == 2
    assert s["mean_diff_pp"] == pytest.approx((-1 + 5) / 2)
    assert s["max_abs_diff_pp"] == pytest.approx(5)
    assert s["share_within_published_moe90"] == 0.5
    assert j["within_moe90"].tolist() == [True, False]


def test_compare_rates_unmatched_raises():
    pums = pd.DataFrame({"year": [2017], "fips": ["01"], "lowinc_rate": [0.2]})
    pub = pd.DataFrame({"year": [2017, 2017], "fips": ["01", "02"],
                        "lowinc_rate": [0.2, 0.2], "lowinc_rate_moe90": [0.01, 0.01]})
    with pytest.raises(ValueError):
        compare_rates(pums, pub)
