import pandas as pd

from osha_audit.src.sample3d import stratified_sample, stratum


def test_stratum():
    assert stratum(96, True) == "accepted"
    assert stratum(82, False) == "rejected 80-85"
    assert stratum(85, False) == "rejected 85-92"
    assert stratum(93, False) == "rejected 92+ (distinctive)"


def test_stratified_sample_caps_small_strata_and_is_reproducible():
    pool = pd.DataFrame({"stratum": ["accepted"] * 10 + ["rejected 80-85"] * 3, "x": range(13)})
    alloc = {"accepted": 4, "rejected 80-85": 5}
    s1 = stratified_sample(pool, alloc, seed=1)
    s2 = stratified_sample(pool, alloc, seed=1)
    assert (s1.stratum == "accepted").sum() == 4 and (s1.stratum == "rejected 80-85").sum() == 3
    assert s1.equals(s2)
