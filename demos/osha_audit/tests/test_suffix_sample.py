import pandas as pd

from osha_audit.src.suffix_sample import suffix_forms, suffix_pairs


def _df():
    return pd.DataFrame({
        "Employer": ["ABC Co.", "ABC Inc", "ABC, Inc.", "ABC", "XYZ LLC"],
        "State": ["TX", "OH", "OH", "TX", "FL"],
        "FederalState": ["1", "1", "0", "1", "1"],
    })


def test_suffix_forms():
    f = suffix_forms(_df()).set_index(["key", "tail"])
    assert f.loc[("abc", "inc"), "reports"] == 2
    assert f.loc[("abc", "inc"), "raw_variants"] == 2
    assert f.loc[("abc", "inc"), "federalstate0_reports"] == 1
    assert f.loc[("abc", "co"), "states"] == "TX"


def test_suffix_pairs_split_by_class():
    only, omit = suffix_pairs(suffix_forms(_df()))
    assert len(only) == 1                         # co vs inc
    assert set([only.iloc[0].tail_a, only.iloc[0].tail_b]) == {"co", "inc"}
    assert len(omit) == 2                         # "" vs co, "" vs inc
