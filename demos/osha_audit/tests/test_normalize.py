import pytest

from osha_audit.src.normalize import name_key, normalize_name, split_dba


@pytest.mark.parametrize("raw,expected", [
    ("The Home Depot, Inc.", "home depot"),
    ("Walmart, Inc.", "walmart"),
    ("Wal-Mart Supercenter #287", "wal mart supercenter"),
    ("PUBLIX SUPER MARKETS # 0246, INC. ", "publix super markets"),
    ("Walmart Store #249 ", "walmart"),
    ("Labor Ready #1188", "labor ready"),
    ("U.S. Postal Service", "us postal service"),
    ("Lowe's Home Centers, LLC", "lowes home centers"),
    ("Packers Sanitation Services, Inc., LTD.", "packers sanitation services"),
    ("Packers Sanitation Services, Inc (PSSI)", "packers sanitation services"),
    ("CHEROKEE BRICK & TILE COMPANY", "cherokee brick and tile"),
    ("Brookdale, dba Horizon Bay Altamonte Springs", "brookdale"),
    ("COLUMBIA WEST VIRGINIA CORP DBA COLUMBIA FOREST", "columbia west virginia"),
    ("HDA Motors, Inc. d/b/a Continental Honda", "hda motors"),
    ("Red River Partners, L.L.C.", "red river partners"),
    ("3M Company", "3m"),
    ("Company", "company"),                        # never strip a name to nothing
])
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_name_key_joins_spacing_variants():
    assert name_key("Wal-Mart Stores, Inc.") == name_key("Walmart Stores Inc")
    assert name_key("Cross Cut Hardwood") == name_key("Cross-Cut Hardwood")


def test_split_dba():
    assert split_dba("Home Depot, dba Home Depot Interiors") == ("Home Depot", "Home Depot Interiors")
    assert split_dba("Acme Inc") == ("Acme Inc", "")


def test_store_numbers_only_when_marked():
    assert normalize_name("7-Eleven #33") == "7 eleven"
    assert normalize_name("Route 66 Diner") == "route 66 diner"


def test_grouped_top_labels_and_variants():
    import pandas as pd
    from osha_audit.src.step3b_preview import grouped_top
    df = pd.DataFrame({"Employer": ["Acme Inc", "ACME, Inc.", "Acme Inc", "Beta"],
                       "FederalState": ["1", "0", "1", "1"]})
    df["key"] = df.Employer.map(name_key)
    t = grouped_top(df, top=2)
    assert t.loc[0, "key"] == "acme" and t.loc[0, "reports"] == 3
    assert t.loc[0, "raw_variants"] == 2 and t.loc[0, "label"] == "Acme Inc"
    assert t.loc[0, "federalstate0_reports"] == 1


def test_suffix_tail():
    from osha_audit.src.normalize import suffix_tail
    assert suffix_tail("ABC Co.") == ("co",)
    assert suffix_tail("ABC Company, Inc.") == ("company", "inc")
    assert suffix_tail("ABC") == ()
    assert normalize_name("ABC Co", strip_suffixes=False) == "abc co"
