"""Tests on SYNTHETIC report text. Add a test from a real report as soon as one is downloaded."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dirs_parser import parse_text, reconcile  # noqa: E402

SAMPLE = """
Communications Status Report for Areas Impacted by Hurricane Example
October 12, 2026 9:00 a.m. EDT
As of this morning, 1.8% of the cell sites in the disaster area are out of service.
Cable and wireline companies reported 82,858 subscribers out of service, which may include the loss of telephone, television, and/or Internet services.

State    County     Cell Sites Served  Cell Sites Out  % Out  Out Damage  Out Transport  Out Power  On Backup
Florida  Okaloosa        310        12    3.9%    1     4     7    20
Florida  Santa Rosa      220         6    2.7%    0     2     4    11
Florida  St. Johns       150         0    0.0%    0     0     0     0
Florida  Total           680        18    2.6%    1     6    11    31
Alabama  Baldwin         294         1    0.3%    0     1     0     5
Louisiana  St. Tammany   1,204      30    2.5%    2    10    18    40
"""


def test_county_rows_and_causes():
    rep = parse_text(SAMPLE)
    assert len(rep.rows) == 5
    ok = next(r for r in rep.rows if r["county"] == "Okaloosa")
    assert (ok["sites_served"], ok["sites_out"], ok["pct_out"]) == (310, 12, 3.9)
    assert (ok["out_damage"], ok["out_transport"], ok["out_power"], ok["on_backup_power"]) == (1, 4, 7, 20)


def test_multiword_and_saint_counties_and_commas():
    rep = parse_text(SAMPLE)
    names = {r["county"] for r in rep.rows}
    assert {"Santa Rosa", "St. Johns", "St. Tammany"} <= names
    assert next(r for r in rep.rows if r["county"] == "St. Tammany")["sites_served"] == 1204


def test_totals_separated_and_reconciled():
    rep = parse_text(SAMPLE)
    assert len(rep.state_totals) == 1 and rep.state_totals[0]["state"] == "Florida"
    assert reconcile(rep) == []


def test_reconcile_flags_mismatch():
    rep = parse_text(SAMPLE.replace("Florida  Total           680", "Florida  Total           700"))
    assert any("sites_served" in i for i in reconcile(rep))


def test_report_level_figures():
    rep = parse_text(SAMPLE)
    assert rep.pct_sites_out == 1.8
    assert rep.cable_wireline_subs_out == 82858


def test_row_without_percent_column():
    rep = parse_text("Texas  Harris  1000  50  2  10  38\n")
    r = rep.rows[0]
    assert r["sites_out"] == 50 and abs(r["pct_out"] - 5.0) < 1e-9 and r["out_power"] == 38


def test_empty_text_warns():
    assert "no county rows found" in parse_text("nothing here").warnings


# --- Real report snippets: pdfplumber text from the FCC PDFs, copied verbatim ---

ISAIAS_2026 = """The following table provides information on cell sites out of service by county. Overall, there is
1.8% (down from 9.8% yesterday) of the cell sites in the affected area reported in the DIRS as
being out of service.
Alabama:
AL BALDWIN 294 1 0.3% 0 0 1 24
AL BUTLER 51 0 0% 0 0 0 10
AL CHOCTAW 41 0 0% 0 0 0 3
AL CLARKE 50 0 0% 0 0 0 8
AL CONECUH 33 5 15.2% 0 1 3 14
AL COVINGTON 58 3 5.2% 0 0 3 9
AL CRENSHAW 36 0 0% 0 0 0 2
AL ESCAMBIA 65 6 9.2% 1 2 2 13
AL GENEVA 55 2 3.6% 0 0 2 18
AL MOBILE 414 1 0.2% 0 0 1 17
AL MONROE 37 3 8.1% 1 0 1 11
AL WASHINGTON 39 0 0% 0 0 0 3
TOTAL - 1173 21 1.8% 2 3 13 132
There is 1.8% (down from 11.5% yesterday) reported in the DIRS as being out of service in the
areas of Alabama impacted by Hurricane Isaias.
"""

MICHAEL_2018 = """The following table provides cell sites reported out of service by county. There are 5.5% (down from
6.6%) of cell sites reported out of service in the affected area in Florida. The information shown was
provided by the signatories to the Wireless Network Resiliency Cooperative Agreement.
Florida
State Affected Counties Cell Sites Served Cell Sites Out Percent Out
FL BAY 345 117 33.9%
FL CALHOUN 42 3 7.1%
FL CITRUS 104 1 1.0%
FL DIXIE 20 0 0.0%
FL ESCAMBIA 243 0 0.0%
FL FRANKLIN 36 1 2.8%
FL GADSDEN 62 0 0.0%
FL GULF 23 7 30.4%
FL HERNANDO 100 0 0.0%
FL HOLMES 27 1 3.7%
FL JACKSON 83 7 8.4%
FL JEFFERSON 261 0 0.0%
FL LEON 418 0 0.0%
FL LEVY 70 0 0.0%
FL LIBERTY 9 0 0.0%
FL OKALOOSA 225 0 0.0%
FL SANTA ROSA 165 0 0.0%
FL TAYLOR 45 0 0.0%
FL WAKULLA 39 0 0.0%
FL WALTON 205 1 0.5%
FL WASHINGTON 39 4 10.3%
TOTAL 2,561 142 5.5%
"""


def test_real_state_abbreviations():
    rep = parse_text(ISAIAS_2026)
    assert len(rep.rows) == 12 and {r["state"] for r in rep.rows} == {"Alabama"}
    r = next(r for r in rep.rows if r["county"] == "CONECUH")
    assert (r["sites_served"], r["sites_out"], r["out_damage"], r["out_transport"], r["out_power"],
            r["on_backup_power"]) == (33, 5, 0, 1, 3, 14)


def test_real_row_with_no_cause_columns():
    rep = parse_text(MICHAEL_2018)
    assert len(rep.rows) == 21 and {r["state"] for r in rep.rows} == {"Florida"}
    r = next(r for r in rep.rows if r["county"] == "SANTA ROSA")
    assert (r["sites_served"], r["sites_out"], r["out_power"]) == (165, 0, None)


def test_real_total_with_dash_takes_state_from_rows_above():
    rep = parse_text(ISAIAS_2026)
    [t] = rep.state_totals
    assert (t["state"], t["sites_served"], t["sites_out"], t["on_backup_power"]) == ("Alabama", 1173, 21, 132)
    assert reconcile(rep) == []


def test_real_total_without_dash():
    rep = parse_text(MICHAEL_2018)
    [t] = rep.state_totals
    assert (t["state"], t["sites_served"], t["sites_out"]) == ("Florida", 2561, 142)
    assert reconcile(rep) == []


def test_real_total_after_second_state_is_not_given_to_the_first():
    rep = parse_text(ISAIAS_2026 + "MS GEORGE 37 0 0% 0 0 0 0\nTOTAL - 37 0 0% 0 0 0 0\n")
    assert [t["state"] for t in rep.state_totals] == ["Alabama", "Mississippi"]


def test_total_with_no_rows_above_warns():
    rep = parse_text("TOTAL - 1173 21 1.8% 2 3 13 132\n")
    assert rep.state_totals == [] and any("total with no county rows" in w for w in rep.warnings)


def test_real_headline_percent_with_change_in_brackets():
    assert parse_text(ISAIAS_2026).pct_sites_out == 1.8
    assert parse_text(MICHAEL_2018).pct_sites_out == 5.5  # not yesterday's 6.6


def test_real_subscribers_with_change_in_brackets():
    text = ("Cable and wireline companies reported in the DIRS that there are 155,813 (down from 193,964\n"
            "yesterday) subscribers out of service in the disaster area. This includes the loss of telephone,\n")
    assert parse_text(text).cable_wireline_subs_out == 155813


def test_real_subscribers_2018_wording():
    text = ("There are 60,300 cable system and wireline outage subscribers out of service in the affected\n"
            "areas in Florida. This is down from 63,856 yesterday.\n")
    assert parse_text(text).cable_wireline_subs_out == 60300


def test_lowercase_words_are_not_state_abbreviations():
    assert parse_text("in Florida 10 20 30\nor counties 1 2 3\n").rows == []


def test_unusable_txt_falls_back_to_pdf(tmp_path, monkeypatch):
    import importlib
    step3 = importlib.import_module("03_parse_dirs")
    d = tmp_path / "dirs"
    d.mkdir()
    # Verbatim start of the Isaias .txt table: the cells are run together.
    (d / "DOC-1A1.txt").write_text("ALBALDWIN29410.3%00124ALBUTLER5100%00010", encoding="utf-8")
    (d / "DOC-1A1.pdf").write_bytes(b"stub")
    monkeypatch.setattr(step3, "RAW", tmp_path)
    monkeypatch.setattr(step3, "pdf_text", lambda path: ISAIAS_2026, raising=False)
    assert step3.report_text("DOC-1A1") == (ISAIAS_2026, "pdf")


def test_real_county_name_wrapped_inside_its_cell():
    # Isaias page 5: plain text extraction gave "PEARL" / "MS RIVER 72 ...", losing half the name.
    import importlib
    step3 = importlib.import_module("03_parse_dirs")
    cells = [["MS", "PEARL\nRIVER", "72", "0", "0%", "0", "0", "0", "0"],
             ["MS", "STONE", "20", "0", "0%", "0", "0", "0", "1"]]

    class Table:
        bbox = (0, 0, 1, 1)

        def extract(self):
            return cells

    class Page:
        def find_tables(self):
            return [Table()]

        def outside_bbox(self, bbox):
            return self

        def extract_text(self):
            return "Mississippi:"

    assert [r["county"] for r in parse_text(step3.page_text(Page())).rows] == ["PEARL RIVER", "STONE"]


DEBBY_2024 = """Florida: Alachua, Baker, Bay, Bradford, Calhoun, and Washington.
911 Services
Florida
Affected Counties Cell Sites Served Cell Sites Out Percent Out
Alachua 301 13 4.32% 0 2 6 16
Baker 23 3 13.04% 0 1 1 2
Bay 377 0 0% 0 0 0 0
Bradford 37 2 5.41% 0 0 1 4
Brevard 153 0 0% 0 0 0 0
Calhoun 26 0 0% 0 0 0 0
TOTAL 9627 99 1.0% 5 8 34 176
"""


def test_real_table_without_a_state_column():
    rep = parse_text(DEBBY_2024)
    assert [r["county"] for r in rep.rows] == ["Alachua", "Baker", "Bay", "Bradford", "Brevard", "Calhoun"]
    assert {r["state"] for r in rep.rows} == {"Florida"}
    r = rep.rows[0]
    assert (r["sites_served"], r["sites_out"], r["pct_out"], r["out_damage"], r["out_transport"], r["out_power"],
            r["on_backup_power"]) == (301, 13, 4.32, 0, 2, 6, 16)
    [t] = rep.state_totals
    assert (t["state"], t["sites_served"], t["on_backup_power"]) == ("Florida", 9627, 176)


def test_no_state_column_is_not_guessed_when_the_report_lists_two_states():
    assert parse_text("Georgia: Appling, and Bacon.\n" + DEBBY_2024).rows == []


def test_no_state_column_rule_is_off_when_rows_carry_a_state():
    rep = parse_text(DEBBY_2024 + "FL GULF 27 0 0% 0 0 0 1\n")
    assert [r["county"] for r in rep.rows] == ["GULF"]



# --- Ida 2021 .txt: multi-word names wrap onto the line above (verbatim, DOC-375367A1 and DOC-375778A1) ---

IDA_2021_TXT = """         EAST BATON
 LA      ROUGE                   360       76     21.1%              9                17           49
         EAST
 LA      FELICIANA                27        2      7.4%              0                 0            2
 LA      EVANGELINE               41        0      0.0%              0                 0            0
 LA      POINTE COUPEE            25        1      4.0%              0                 0            1
         ST. JOHN THE
 LA      BAPTIST                  27       18     66.7%              1                 1           16
LA     JEFFERSON             301      9     3.0%             1               4           4
       JEFFERSON
LA     DAVIS                  29      1     3.4%             0               1           0
"""


def test_real_name_wrapped_onto_the_line_above():
    names = [r["county"] for r in parse_text(IDA_2021_TXT).rows]
    assert names == ["EAST BATON ROUGE", "EAST FELICIANA", "EVANGELINE", "POINTE COUPEE", "ST. JOHN THE BAPTIST",
                     "JEFFERSON", "JEFFERSON DAVIS"]
    r = parse_text(IDA_2021_TXT).rows[0]
    assert (r["sites_served"], r["sites_out"], r["pct_out"], r["out_power"]) == (360, 76, 21.1, 49)


def test_a_state_name_line_is_not_a_name_prefix():
    assert parse_text("  LOUISIANA\n LA      ACADIA   10  1  10.0%  0  0  1\n").rows[0]["county"] == "ACADIA"


# --- Sally Sep 18-21, 2020: rows print only served and out (verbatim, DOC-367015A1 as step 3 reads it) ---

SALLY_2020 = """State Affected Counties Cell Sites Served Cell Sites Out
AL BALDWIN 361 65
AL BUTLER 44 2
AL WASHINGTON 41 1
TOTAL  446 68
Cell Sites Out Due to Transport1 Cell Sites Out Due to Power
26 35
2 0
"""


def test_real_rows_with_only_served_and_out():
    rep = parse_text(SALLY_2020)
    assert [(r["county"], r["sites_served"], r["sites_out"]) for r in rep.rows] == [
        ("BALDWIN", 361, 65), ("BUTLER", 44, 2), ("WASHINGTON", 41, 1)]
    r = rep.rows[0]
    assert r["pct_printed"] is False and abs(r["pct_out"] - 100 * 65 / 361) < 1e-9
    assert (r["out_damage"], r["out_transport"], r["out_power"]) == (None, None, None)  # not paired by row order
    [t] = rep.state_totals
    assert (t["state"], t["sites_served"], t["sites_out"]) == ("Alabama", 446, 68)


def test_printed_percent_is_marked_printed():
    assert parse_text(IDA_2021_TXT).rows[0]["pct_printed"] is True



# --- Michael Oct 25, 2018 (DOC-354788A1): "more than 15%" is not the headline ---

def test_threshold_percent_is_not_the_headline():
    text = ("In Florida, for example, there are no counties with\nmore than 15% of cell sites out of service. The FCC "
            "continues to closely monitor.\nThe following table provides cell sites reported out of service by county. "
            "There are 2.0% (slightly down\nfrom 2.2% yesterday) of cell sites reported out of service in the affected "
            "area in Florida.\n")
    assert parse_text(text).pct_sites_out == 2.0


# --- Harvey Aug 26, 2017 (DOC-346368A1 .txt): one table, two states, one TOTAL split over three lines ---

HARVEY_2017 = """State Affected Counties Cell Sites Served Cell Sites Out Percent Out
LA ACADIA 50 0 0.0%
LA CAMERON 30 0 0.0%
TX ARANSAS 40 30 75.0%
TX WILSON 29 1 3.4%
TOTAL

149 31 20.8%
"""


def test_overall_total_split_over_lines_covers_all_states():
    rep = parse_text(HARVEY_2017)
    assert rep.state_totals == []
    [t] = rep.overall_totals
    assert (t["sites_served"], t["sites_out"], t["states"]) == (149, 31, "Louisiana; Texas")


def test_single_state_total_is_still_a_state_total():
    rep = parse_text("LA ACADIA 50 0 0.0%\nTOTAL\n\n50 0 0.0%\n")
    assert [t["state"] for t in rep.state_totals] == ["Louisiana"] and rep.overall_totals == []


# --- Laura 2020 PDFs: the page footer runs into the county list (DOC-366394A1) ---

def test_page_footer_does_not_enter_the_county_list():
    text = ("Texas: Walker, Waller, Wood As prepared by the Federal Communications Commission: August 25,\n"
            "2020 12:00 p.m. EDT\nPa ge | 2\n911 Services\n")
    assert [c["county"] for c in parse_text(text).county_list] == ["Walker", "Waller", "Wood"]



# --- step 3 picks, page by page, the reading that gives more complete rows ---

class _Table:
    bbox = (0, 0, 1, 1)

    def __init__(self, cells):
        self.cells = cells

    def extract(self):
        return self.cells


class _Page:
    def __init__(self, plain, cells):
        self.plain, self.cells = plain, cells

    def find_tables(self):
        return [_Table(self.cells)] if self.cells else []

    def outside_bbox(self, bbox):
        return _Page("", [])

    def extract_text(self):
        return self.plain


def test_cell_reading_wins_when_it_keeps_a_wrapped_name_whole():
    # Isaias Oct 10, 2026 (DOC-425790A1): plain text splits "PEARL RIVER" across lines
    import importlib
    step3 = importlib.import_module("03_parse_dirs")
    page = _Page("MS JACKSON 119 0 0% 0 0 0 1\nPEARL 72 0 0% 0 0 0 0\nMS RIVER\n",
                 [["MS", "JACKSON", "119", "0", "0%", "0", "0", "0", "1"],
                  ["MS", "PEARL\nRIVER", "72", "0", "0%", "0", "0", "0", "0"]])
    assert [r["county"] for r in parse_text(step3.page_text(page)).rows] == ["JACKSON", "PEARL RIVER"]


def test_plain_reading_wins_when_the_cell_reading_drops_columns():
    # Zeta Oct 29, 2020 (DOC-367859A1): table cells lost the transport and power columns
    import importlib
    step3 = importlib.import_module("03_parse_dirs")
    page = _Page("AL WILCOX 30 3 10.0% 0 0 3\nTOTAL 4,746 416 8.8% 134 56 213\n",
                 [["AL", "WILCOX", "30", "3", "10.0%", "0"], ["TOTAL", "", "4,746", "416", "8.8%", "134"]])
    r = parse_text(step3.page_text(page)).rows[0]
    assert (r["out_damage"], r["out_transport"], r["out_power"]) == (0, 0, 3)



# --- round 1 of Prompt 2 fixes (2026-11-22) ---

def test_unindented_wrapped_name_in_pdf_text():
    # Delta Oct 10, 2020 (DOC-367454A1) and Laura Aug 29, 2020 (DOC-366524A1), as step 3 reads them
    text = ("LA DE SOTO 41 0 0.0% 0 0 0\nEAST BATON\nLA ROUGE 367 34 9.3% 17 6 11\nLA EAST CARROLL 7 0 0.0% 0 0 0\n"
            "State Counties Served Out Out Damage Transport Power\nMD ALLEGANY 63 0 0.0% 0 0 0\nANNE\n"
            "MD ARUNDEL 635 0 0.0% 0 0 0\n")
    assert [r["county"] for r in parse_text(text).rows] == ["DE SOTO", "EAST BATON ROUGE", "EAST CARROLL", "ALLEGANY",
                                                            "ANNE ARUNDEL"]


def test_uppercase_header_or_state_line_is_not_a_name_prefix():
    text = "STATE AFFECTED COUNTIES\nAL BALDWIN 295 0 0.0%\nMS\nMS GEORGE 37 0 0%\nTOTAL\nAL MOBILE 398 1 0.3%\n"
    assert [r["county"] for r in parse_text(text).rows] == ["BALDWIN", "GEORGE", "MOBILE"]


def test_total_goes_to_the_state_whose_rows_it_matches():
    # Helene Sep 28, 2024 (DOC-405893A1): Georgia's table prints no TOTAL; North Carolina's TOTAL follows
    text = ("GA Whitfield 88 0 0% 0 0 0 0\nGA Worth 35 1 2.9% 0 0 1 0\nNC Ashe 9 2 22.2% 0 1 1 0\n"
            "NC Yancey 22 18 81.82% 0 6 12 0\nTOTAL - 31 20 64.5% 0 7 13 0\n")
    rep = parse_text(text)
    assert [(t["state"], t["sites_served"]) for t in rep.state_totals] == [("North Carolina", 31)]
    assert rep.overall_totals == []


def test_total_matching_all_rows_is_still_an_overall_total():
    text = "LA ACADIA 50 0 0.0%\nTX WILSON 29 1 3.4%\nTOTAL\n\n79 1 1.3%\n"
    assert [t["states"] for t in parse_text(text).overall_totals] == ["Louisiana; Texas"]


def test_county_list_cleanups_from_real_reports():
    text = ("Louisiana: Lafourche, St, Martin, St, Mary, and Terrebonne.\n"  # Ida 2021 lists
            "North Carolina: Graham, Jackson (Eastern Band of Cherokee Indians and Jackson), and Swain.\n"  # Zeta 2020
            "U.S. Virgin Islands: St. Croix, St. John, and St. Thomas.\n"
            "911 Services\n")
    got = [(c["state"], c["county"]) for c in parse_text(text).county_list]
    assert got == [("Louisiana", "Lafourche"), ("Louisiana", "St. Martin"), ("Louisiana", "St. Mary"),
                   ("Louisiana", "Terrebonne"), ("North Carolina", "Graham"), ("North Carolina", "Jackson"),
                   ("North Carolina", "Swain"), ("U.S. Virgin Islands", "St. Croix"), ("U.S. Virgin Islands", "St. John"),
                   ("U.S. Virgin Islands", "St. Thomas")]


def test_virgin_islands_label_matches_the_table_state():
    got = parse_text("Virgin Islands: St. Croix, and St. Thomas.\n911 Services\n").county_list
    assert {c["state"] for c in got} == {"U.S. Virgin Islands"}


def test_county_list_printed_after_the_tables():
    # Laura Aug 27-31, 2020: the list comes after the 911 section and the tables
    text = ("911 Services\nTX TYLER 63 7 11.1% 5 1 2\n"
            "The following counties are in the current geographic area that is part of DIRS (the “disaster area”) "
            "for today’s\nreport.\nArkansas: Arkansas, Ashley, and Baxter.\nTexas: Tyler, and Wood.\n")
    got = [(c["state"], c["county"]) for c in parse_text(text).county_list]
    assert got == [("Arkansas", "Arkansas"), ("Arkansas", "Ashley"), ("Arkansas", "Baxter"), ("Texas", "Tyler"),
                   ("Texas", "Wood")]


def test_headline_without_of():  # Irma Sep 9, 2017 (DOC-346632A1)
    text = ("31.1% cell sites are out of service (down from 38.1% yesterday). 29.3% of cell sites are out of service "
            "in Puerto Rico.\n")
    assert parse_text(text).pct_sites_out == 31.1



# --- as-of time (2026-11-22), for matching EAGLE-I to each snapshot ---

@pytest.mark.parametrize("text, expected", [
    # Helene Sep 28, 2024 (DOC-405893A1)
    ("impacted by Hurricane Helene as of September 28, 2024, at 9:00 a.m. EDT. The", ("2024-09-28", "09:00", "EDT")),
    # Irma Sep 9, 2017 (DOC-346632A1)
    ("impacted by Hurricane Irma as of September 9, 2017 at 11:00 a.m. EDT.", ("2017-09-09", "11:00", "EDT")),
    # Isaias Oct 10, 2026 (DOC-425790A1): no date in the sentence
    ("impacted by Hurricane Isaias as of 10:00 a.m. EDT today.", (None, "10:00", "EDT")),
    ("Hurricane Delta as of October 10, 2020 at 12:00 p.m.", ("2020-10-10", "12:00", "")),
    ("as of November 10, 2022 at 12:00 p.m. EST", ("2022-11-10", "12:00", "EST")),
])
def test_as_of_time(text, expected):
    rep = parse_text(text)
    assert (rep.as_of_date, rep.as_of_time, rep.as_of_tz) == expected


def test_no_as_of_time():
    assert parse_text("AL BALDWIN 295 0 0.0%\n").as_of_time is None
