import pandas as pd

from osha_audit.src.entities3b import assign, counts, suffix_type


def _df():
    return pd.DataFrame({
        "Employer": ["ABC Corp.", "ABC Corporation",   # same type, different states -> merge
                     "ABC LLC",                        # other type, shares OH with ABC Corporation -> merge
                     "ABC",                            # no suffix, FL only -> separate
                     "XYZ Inc", "XYZ LLC"],            # different types, no shared state -> separate
        "State": ["TX", "OH", "OH", "FL", "GA", "AL"],
        "FederalState": ["1", "1", "1", "0", "1", "1"],
    })


def test_suffix_type_canonical():
    assert suffix_type("ABC Corp.") == suffix_type("ABC Corporation") == "corp"
    assert suffix_type("ABC Company, Inc.") == "co inc"
    assert suffix_type("ABC") == ""


def test_narrow_rule():
    d, blocked = assign(_df(), narrow=True)
    e = d.set_index("Employer").entity
    assert e["ABC Corp."] == e["ABC Corporation"] == e["ABC LLC"]
    assert e["ABC"] != e["ABC Corp."]
    assert e["XYZ Inc"] != e["XYZ LLC"]
    assert blocked == 3          # ABC(FL)-corp, ABC(FL)-llc, XYZ inc-llc


def test_original_rule_merges_by_base():
    d, _ = assign(_df(), narrow=False)
    assert d.entity.nunique() == 2


def test_counts_name_and_state():
    d, _ = assign(_df(), narrow=True)
    c = counts(d)
    assert c["by_name"] == 4
    assert c["by_name_and_state"] == 5     # ABC-merged in TX and OH (2) + ABC FL + XYZ Inc GA + XYZ LLC AL
    assert c["federalstate0_reports"] == 1 and c["federalstate0_by_name"] == 1
