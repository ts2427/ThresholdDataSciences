import pandas as pd
import pytest

from osha_audit.src.dedupe_apply import apply_merges, confirmed_pairs


def _df():
    return pd.DataFrame({"UPA": ["10", "20", "30", "40"],
                         "Employer": ["A", "A ", "B", "C"],
                         "Hospitalized": ["0.00", "1.00", "1.00", "1.00"],
                         "Amputation": ["1.00", "0.00", "0.00", "0.00"],
                         "Loss of Eye": ["0.00", "", "0.00", "1.00"]})


def test_confirmed_pairs_filters_and_validates():
    r = pd.DataFrame({"pair": ["1", "2", "3"], "upa_kept": ["10", "30", "x"],
                      "upa_removed": ["20", "40", "y"], "confirm": ["Y", "N", "Y — judgment call"]})
    assert confirmed_pairs(r) == [("10", "20"), ("x", "y")]
    r.loc[1, "confirm"] = ""
    with pytest.raises(ValueError):
        confirmed_pairs(r)


def test_apply_merges_keeps_lowest_upa_with_max_counts():
    out, removed = apply_merges(_df(), [("20", "10")])
    assert removed == ["20"]
    kept = out.set_index("UPA").loc["10"]
    assert kept["Hospitalized"] == "1.00" and kept["Amputation"] == "1.00"
    assert len(out) == 3


def test_apply_merges_clusters_chain():
    out, removed = apply_merges(_df(), [("10", "20"), ("20", "30")])
    assert removed == ["20", "30"] and out["UPA"].tolist() == ["10", "40"]


def test_apply_merges_unknown_upa_raises():
    with pytest.raises(ValueError):
        apply_merges(_df(), [("10", "99")])
