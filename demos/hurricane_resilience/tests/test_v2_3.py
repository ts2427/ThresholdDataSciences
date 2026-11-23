"""V2-3: power vs. cell timing (rebound rule, order under censoring)."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
v2 = importlib.import_module("12_v2_analysis")


def test_crossing_rebound_rule_and_censoring():
    assert v2.crossing([0, 1, 2], [3, 4, 2], 5) is None                         # never at risk
    assert v2.crossing([0, 1, 2, 3], [9, 4, 6, 2], 5) == {"event": True, "time": 3.0}  # stays below only from day 3
    assert v2.crossing([0, 1], [9, 7], 5) == {"event": False, "time": 1.0}      # censored at its last report


def test_order_under_censoring():
    E, C = (lambda t: {"event": True, "time": t}), (lambda t: {"event": False, "time": t})
    assert v2.order(E(1), E(2)) == "power_first" and v2.order(E(2), E(2)) == "same_report"
    assert v2.order(E(3), E(1)) == "cell_first"
    assert v2.order(E(1), C(4)) == "power_first"     # cell still out at day 4, after power fell below at day 1
    assert v2.order(E(5), C(4)) == "undetermined"    # cell censored before power fell below
    assert v2.order(C(4), C(4)) == "undetermined"


def test_whole_value_groups_close_to_thirds_with_minimum_share():
    import pandas as pd
    v = pd.Series([0] * 19 + [1] * 49 + [2] * 160 + [3] * 386 + [4] * 151 + [5] * 22 + [6] * 1)
    g = v2.whole_value_groups(v)
    assert g["labels"] == ["2 or fewer", "3", "4 or more"] and list(g["sizes"].values()) == [228, 386, 174]
    flat = pd.Series([3] * 130 + [4] * 409 + [5] * 228 + [6] * 19 + [7] * 2)
    assert g is not None and v2.whole_value_groups(flat)["groups"] is None   # 3 alone is under 20%
