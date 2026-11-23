"""The parser reads each report's own county list (real snippets except where noted)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from dirs_parser import parse_text  # noqa: E402


def listed(text):
    return [(c["state"], c["county"]) for c in parse_text(text).county_list]


def test_real_county_list_isaias():
    got = listed("Mississippi: George, Greene, Hancock, Harrison, Jackson, Pearl River, and Stone.\n"
                 "1 On October 8, 2026 the Commission activated the Disaster Information Reporting System\n"
                 "911 Services\n")
    assert len(got) == 7 and ("Mississippi", "Pearl River") in got and got[-1] == ("Mississippi", "Stone")


def test_real_county_list_wraps_and_changes_state():
    got = listed("Florida: Hamilton, Holmes, Jackson, Santa Rosa,\n"
                 "Suwannee, Taylor, Wakulla, Walton, and Washington.\n"
                 "Mississippi: George, and Stone.\n911 Services\n")
    assert len(got) == 11 and got[-3] == ("Florida", "Washington") and got[-1] == ("Mississippi", "Stone")


def test_real_county_list_without_final_stop():
    got = listed("FLORIDA: Bay, Calhoun, Jackson,\nJefferson, Walton, Washington\n"
                 "The following map shows the counties in the disaster area:\n911 Services\n")
    assert got[-1] == ("Florida", "Washington") and len(got) == 6


def test_real_county_list_with_name_split_across_lines():
    got = listed("Puerto Rico: Lares, Las Marias, Las \nPiedras, Loiza, Vega Alta, Vega \n"
                 "Baja, Vieques, Villalba, Yabucoa, and Yauco \n\n \n911 Services\n")
    assert ("Puerto Rico", "Las Piedras") in got and ("Puerto Rico", "Vega Baja") in got
    assert got[-1] == ("Puerto Rico", "Yauco")


def test_county_list_line_ending_in_saint_abbreviation():  # synthetic line break
    got = listed("Florida: Seminole, St.\nJohns, and Volusia.\n911 Services\n")
    assert [c for _, c in got] == ["Seminole", "St. Johns", "Volusia"]


def test_county_list_last_name_wrapped():  # synthetic line break
    got = listed("Florida: Bay, and Santa\nRosa.\n911 Services\n")
    assert [c for _, c in got] == ["Bay", "Santa Rosa"]


def test_county_list_single_county():
    assert listed("Florida: Hamilton.\nGeorgia: Appling, and Bacon.\n911 Services\n")[0] == ("Florida", "Hamilton")


def test_state_labels_after_the_list_section_are_not_lists():
    assert listed("911 Services\nFlorida: Tyndall Airforce FD, Tyndall Airforce Law\n") == []
