import pandas as pd
import pytest

from medicaid_did.src.before_after import before_after, frame, group_rate


def _d():
    rows = []
    for i, (grp, pre, post, w) in enumerate([("treated", 30, 15, 1), ("treated", 40, 20, 3),
                                             ("comparison", 50, 45, 2)]):
        rows.append({"id": i, "year": 2013, "group": grp, "y": pre, "w": w})
        for y in (2016, 2017, 2018, 2019):
            rows.append({"id": i, "year": y, "group": grp, "y": post, "w": w})
    return pd.DataFrame(rows)


def test_group_rate_weighted():
    d = _d()
    assert group_rate(d[d.group == "treated"], [2013]) == pytest.approx((30 + 120) / 4)


def test_before_after():
    r = before_after(_d())
    assert r.naive_change == pytest.approx(18.75 - 37.5)
    assert r.comparison_change == pytest.approx(-5)
    assert r.adjusted_change == pytest.approx(-18.75 + 5)


def test_frame_groups():
    panel = pd.DataFrame({"fips": ["01", "02", "03", "04"], "year": [2013] * 4,
                          "cohort": [2014, 0, 2021, 2015], "lowinc_rate": [.3, .4, .5, .6],
                          "lowinc_pop": [1, 1, 1, 1]})
    f = frame(panel)
    assert f.set_index("id").group.to_dict() == {1: "treated", 2: "comparison", 3: "comparison"}
