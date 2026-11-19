import numpy as np
import pandas as pd
import pytest

from osha_audit.src.step3d_estimate import (flip_judgment_calls, point_estimates,
                                            stratified_bootstrap, wilson)


def test_wilson_known_value():
    p, lo, hi = wilson(145, 150)
    assert p == pytest.approx(0.9667, abs=1e-4)
    assert lo == pytest.approx(0.9244, abs=1e-3) and hi == pytest.approx(0.9857, abs=1e-3)


def test_wilson_zero():
    p, lo, hi = wilson(0, 50)
    assert p == 0 and lo == pytest.approx(0, abs=1e-12) and hi == pytest.approx(0.0713, abs=1e-3)


def test_point_estimates_weighting():
    y = {"accepted": np.array([1, 1, 1, 0]), "rejected x": np.array([1, 0])}
    sizes = {"accepted": 100, "rejected x": 1000}
    p, r, est = point_estimates(y, sizes)
    assert p == 0.75 and est["accepted"] == 75 and est["rejected x"] == 500
    assert r == pytest.approx(75 / 575)


def test_bootstrap_reproducible_and_bounded():
    y = {"accepted": np.array([1, 1, 0, 1]), "rejected x": np.array([0, 1, 0, 0])}
    sizes = {"accepted": 10, "rejected x": 40}
    a, _ = stratified_bootstrap(y, sizes, reps=200, seed=3)
    b, _ = stratified_bootstrap(y, sizes, reps=200, seed=3)
    assert np.array_equal(a, b)
    assert np.nanmin(a) >= 0 and np.nanmax(a) <= 1


def test_flip_judgment_calls():
    df = pd.DataFrame({"same employer": ["Y", "N", "Y"],
                       "claude_note": ["Judgment call: x", "judgment call: y", "plain note"]})
    out, n = flip_judgment_calls(df)
    assert n == 2 and out["same employer"].tolist() == ["N", "Y", "Y"]


def test_overstatement():
    from osha_audit.src.step3d_estimate import overstatement
    est = {"est_missed_matching_pairs": 100.0, "est_missed_ci95": [50.0, 200.0], "est_false_merges": 3.0}
    o = overstatement(est, 10000)
    assert o["max_overstatement_pct"] == 1.0 and o["max_overstatement_pct_ci95"] == [0.5, 2.0]
