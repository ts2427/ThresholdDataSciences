import pandas as pd

from osha_audit.src.naive import naive_counts


def test_naive_counts_raw_strings_not_merged():
    df = pd.DataFrame({"Employer": ["Acme Inc", "ACME INC", "Acme Inc", "Beta", "Beta ", "Zed"]})
    top, distinct = naive_counts(df, top=3)
    assert distinct == 5                    # case and trailing space stay distinct
    assert top.loc[0, "employer"] == "Acme Inc" and top.loc[0, "reports"] == 2
    assert top["rank"].tolist() == [1, 2, 3]


def test_naive_counts_ties_alphabetical_and_share():
    df = pd.DataFrame({"Employer": ["b", "a", "c", "c"]})
    top, _ = naive_counts(df, top=3)
    assert top["employer"].tolist() == ["c", "a", "b"]
    assert top.loc[0, "share_pct"] == 50.0
