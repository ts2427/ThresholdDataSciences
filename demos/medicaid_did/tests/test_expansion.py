from datetime import date

import pytest

from medicaid_did.src.expansion import (parse_kff_table, prior_coverage,
                                        treatment_year)


def _page(rows):
    head = ("<table><thead><tr><th>Location</th><th>Status</th>"
            "<th>Expansion Implementation Date</th><th>B</th><th>T</th></tr></thead><tbody>"
            "<tr><td>United States</td><td>x</td><td></td><td></td><td></td></tr>")
    return head + "".join(rows) + "</tbody></table>"


def _states(n_adopted=41):
    rows = []
    for i in range(51):
        if i < n_adopted:
            rows.append(f"<tr><td>S{i}</td><td>Adopted</td><td>1/1/2014</td><td>No</td><td>No</td></tr>")
        else:
            rows.append(f"<tr><td>S{i}</td><td>Not Adopted</td><td>N/A</td><td>N/A</td><td></td></tr>")
    return rows


def test_parse_kff_table_counts_and_dates():
    df = parse_kff_table(_page(_states()))
    assert len(df) == 51
    assert (df["status"] == "Adopted").sum() == 41
    assert df.loc[0, "effective_date"] == date(2014, 1, 1)
    assert df.loc[50, "effective_date"] is None


def test_parse_kff_table_rejects_wrong_count():
    with pytest.raises(ValueError):
        parse_kff_table(_page(_states()[:50]))


def test_parse_kff_table_rejects_adopted_without_date():
    rows = _states()
    rows[0] = "<tr><td>S0</td><td>Adopted</td><td>N/A</td><td>No</td><td>No</td></tr>"
    with pytest.raises(ValueError):
        parse_kff_table(_page(rows))


def test_parse_kff_unescapes_names():
    rows = _states()
    rows[0] = "<tr><td>A &amp; B</td><td>Adopted</td><td>1/1/2014</td><td>No</td><td>No</td></tr>"
    assert parse_kff_table(_page(rows)).loc[0, "state"] == "A & B"


@pytest.mark.parametrize("d,expected", [
    (date(2014, 1, 1), 2014),
    (date(2014, 4, 1), 2014),     # Michigan
    (date(2016, 7, 1), 2016),     # on the cutoff counts as that year
    (date(2014, 8, 15), 2015),    # New Hampshire
    (date(2015, 9, 1), 2016),     # Alaska
    (date(2023, 12, 1), 2024),    # North Carolina
    ("2019-01-10", 2019),
    (None, None),
])
def test_treatment_year(d, expected):
    assert treatment_year(d) == expected


def test_prior_coverage():
    assert prior_coverage("District of Columbia") == "prior_full"
    assert prior_coverage("Wisconsin") == "prior_limited"
    assert prior_coverage("California") == "prior_limited"
    assert prior_coverage("Texas") == "none"
