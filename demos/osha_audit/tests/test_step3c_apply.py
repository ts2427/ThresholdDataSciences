import pandas as pd
import pytest

from osha_audit.src.step3c_apply import alias_links, merge_entities, waterfall_rows


def test_alias_links_maps_labels_and_skips_rejected():
    E = pd.DataFrame({"entity": [1, 2, 3], "label": ["UPS", "United Parcel Service", "FedEx"]})
    a = pd.DataFrame({"name_a": ["United Parcel Service", "FedEx"], "name_b": ["UPS", "UPS"],
                      "approve": ["Y", "N"]})
    assert alias_links(E, a) == [(2, 1)]


def test_alias_links_ambiguous_label_raises():
    E = pd.DataFrame({"entity": [1, 2], "label": ["UPS", "UPS"]})
    a = pd.DataFrame({"name_a": ["UPS"], "name_b": ["UPS"], "approve": ["Y"]})
    with pytest.raises(ValueError):
        alias_links(E, a)


def test_merge_entities_labels_by_most_common_spelling():
    d = pd.DataFrame({"entity": [1, 1, 2, 3], "Employer": ["UPS", "UPS", "United Parcel Service", "X"]})
    out = merge_entities(d, [(1, 2)])
    assert out.employer_id.tolist() == [1, 1, 1, 3]
    assert out.employer_label.iloc[2] == "UPS"


def test_waterfall_rows_counts():
    base = pd.DataFrame({"Employer": ["a", "A", "b"], "State": ["TX", "TX", "OH"], "FederalState": ["1", "0", "1"],
                         "entity": [1, 1, 2], "entity3c": [1, 1, 1], "employer_id": [1, 1, 1]})
    w = waterfall_rows(base, base, base, base, base)
    assert w.employers_by_name.tolist() == [3, 3, 2, 1, 1]
    assert w.employers_by_name_and_state.iloc[-1] == 2
    assert w.federalstate0_reports.iloc[0] == 1
