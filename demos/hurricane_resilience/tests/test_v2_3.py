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
