import math

import pandas as pd
import pytest

from medicaid_did.src.pums import aggregate, in_universe, records_to_frame


def _api(rows):
    return [["PWGTP", "AGEP", "POVPIP", "HICOV", "MIL", "ST"]] + rows


def test_records_to_frame_coerces_blanks():
    df = records_to_frame(_api([["10", "30", "", "1", "4", "01"]]))
    assert math.isnan(df.loc[0, "POVPIP"]) and df.loc[0, "PWGTP"] == 10


def test_in_universe():
    df = records_to_frame(_api([
        ["1", "19", "100", "1", "4", "01"],   # in
        ["1", "18", "100", "1", "4", "01"],   # too young
        ["1", "65", "100", "1", "4", "01"],   # too old
        ["1", "30", "-1", "1", "4", "01"],    # no poverty status
        ["1", "30", "", "1", "4", "01"],      # no poverty status
        ["1", "30", "100", "1", "1", "01"],   # active duty
        ["1", "64", "501", "2", "", "01"],    # in (MIL blank)
    ]))
    assert in_universe(df).tolist() == [True, False, False, False, False, False, True]


def test_aggregate_weights_and_cutoff():
    df = records_to_frame(_api([
        ["10", "30", "137", "2", "4", "01"],  # low-income, uninsured
        ["30", "30", "50", "1", "4", "01"],   # low-income, insured
        ["20", "30", "138", "2", "4", "01"],  # not low-income (138%), uninsured
        ["40", "30", "300", "1", "4", "01"],
        ["99", "70", "50", "2", "4", "01"],   # outside universe
    ]))
    a = aggregate(df)
    assert a["lowinc_pop"] == 40 and a["lowinc_uninsured"] == 10
    assert a["lowinc_rate"] == pytest.approx(0.25)
    assert a["all_pop"] == 100 and a["all_rate"] == pytest.approx(0.30)
    assert a["lowinc_n"] == 2 and a["all_n"] == 4


def test_aggregate_rejects_bad_hicov():
    df = records_to_frame(_api([["1", "30", "50", "9", "4", "01"]]))
    with pytest.raises(ValueError):
        aggregate(df)


def test_records_to_frame_duplicate_predicate_column():
    api = [["PWGTP", "AGEP", "POVPIP", "HICOV", "MIL", "AGEP", "state"],
           ["5", "30", "100", "1", "4", "30", "01"]]
    df = records_to_frame(api)
    assert list(df.columns).count("AGEP") == 1 and df.loc[0, "AGEP"] == 30


def test_records_to_frame_duplicate_disagreeing_raises():
    api = [["PWGTP", "AGEP", "POVPIP", "HICOV", "MIL", "AGEP", "state"],
           ["5", "30", "100", "1", "4", "31", "01"]]
    with pytest.raises(ValueError):
        records_to_frame(api)
