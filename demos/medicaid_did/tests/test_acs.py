import math

import pytest

from medicaid_did.src.acs import (ALL_BINS, moe_proportion, moe_sum,
                                  select_vars, state_year_rates, _norm)


def _meta(colons=True):
    c = ":" if colons else ""
    v, n = {}, 1
    for b in ALL_BINS:
        for age in ("Under 19 years", "19 to 64 years", "65 years and over"):
            base = f"Estimate!!Total{c}!!{b} of poverty threshold{c}!!{age}{c}"
            v[f"C27016_{n:03d}E"] = {"label": base}; n += 1
            v[f"C27016_{n:03d}E"] = {"label": base + "!!With health insurance coverage"}; n += 1
            v[f"C27016_{n:03d}E"] = {"label": base + "!!No health insurance coverage"}; n += 1
    v["NAME"] = {"label": "Geographic Area Name"}
    v["C27016_001M"] = {"label": "Margin of Error!!Total:"}
    return v


@pytest.mark.parametrize("colons", [True, False])
def test_select_vars_both_label_styles(colons):
    m = select_vars(_meta(colons))
    assert list(m) == list(ALL_BINS)
    # first bin: 19-64 total is the 4th variable, uninsured the 6th
    assert m["Under 1.00"] == {"total": "C27016_004E", "uninsured": "C27016_006E"}


def test_select_vars_missing_bin_raises():
    meta = {k: v for k, v in _meta().items() if "4.00 and over" not in v["label"]}
    with pytest.raises(ValueError):
        select_vars(meta)


def test_select_vars_duplicate_raises():
    meta = _meta()
    meta["C27016_999E"] = dict(meta["C27016_004E"])
    with pytest.raises(ValueError):
        select_vars(meta)


def test_norm():
    assert _norm("Estimate!!Total:!!19 to 64 years:") == ("Estimate", "Total", "19 to 64 years")


def test_moe_sum():
    assert moe_sum([3, 4]) == 5.0


def test_moe_proportion_and_fallback():
    assert moe_proportion(20, 100, 5, 10) == pytest.approx(math.sqrt(25 - 0.04 * 100) / 100)
    # negative under the root -> ratio formula
    assert moe_proportion(50, 100, 1, 10) == pytest.approx(math.sqrt(1 + 0.25 * 100) / 100)


def test_state_year_rates():
    m = select_vars(_meta())
    row = {"NAME": "X", "state": "01"}
    for b in ALL_BINS:
        t, u = m[b]["total"], m[b]["uninsured"]
        row[t], row[u] = "100", "10"
        row[t[:-1] + "M"], row[u[:-1] + "M"] = "0", "0"
    row[m["Under 1.00"]["uninsured"]] = "30"
    rec = state_year_rates([row], m)[0]
    assert rec["lowinc_pop"] == 200 and rec["lowinc_uninsured"] == 40
    assert rec["lowinc_rate"] == pytest.approx(0.2)
    assert rec["all_rate"] == pytest.approx(70 / 500)
    assert rec["lowinc_rate_moe90"] == 0


def test_select_vars_top_bin_wording():
    meta = {k: {"label": v["label"].replace("4.00 and over of poverty threshold",
                                            "4.00 of poverty threshold and over")}
            for k, v in _meta().items()}
    assert "4.00 of poverty threshold and over" in str(meta)
    assert "4.00 and over" in select_vars(meta)
