from medicaid_did.src.step2_collect import RANGE, in_range, red_flags


def test_range_from_benchmarks():
    assert RANGE == (-8.2, -6.0)


def test_in_range_inclusive():
    assert in_range(-8.2) and in_range(-6.0) and in_range(-7.0)
    assert not in_range(-8.3) and not in_range(-5.9)


def test_red_flags():
    f = red_flags(pretest_p=0.24, headline=-7.2, e1=-6.9)
    assert f == {"pre_period_jointly_significant": False,
                 "headline_outside_published_range": False,
                 "e1_outside_published_range": False}
    f = red_flags(pretest_p=0.01, headline=-3.0, e1=-9.0)
    assert all(f.values())
