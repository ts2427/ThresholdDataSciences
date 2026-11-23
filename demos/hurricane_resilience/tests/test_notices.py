"""Reading FCC DIRS notices. Snippets are copied from the real notices (whitespace collapsed)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from notices import read_notice  # noqa: E402

IDA_ACTIVATION = (  # DA-21-1070A1, Aug 29, 2021 (FCC spelling kept: "St, Martin", "Point Coupee", "Vermillion")
    "COUNTIES OF INTEREST FOR THIS ACTIVATION INCLUDE THE FOLLOWING: Alabama: Baldwin, Clarke, Conecuh, Escambia, "
    "Mobile, Monroe, Washington. Louisiana: Acadia, Lafourche, Point Coupee, St, Martin, St, Mary, St. Bernard, "
    "St. John the Baptist, Vermillion, West Feliciana. Mississippi: Adams, Pearl River, Yazoo. The FCC continues to "
    "monitor the storm and may amend the DIRS activation area in the coming days.")

IDA_PARTIAL = (  # DA-21-1109A1, Sep 3, 2021: a removal list, with unrelated text between the cue and the list
    "DIRS deactivated in Alabama and Mississippi. DIRS remains active in Louisiana. At the request of the Department "
    "of Homeland Security, the Federal Communications Commission (FCC) has deactivated its Disaster Information "
    "Reporting System (DIRS) DIRS is a voluntary, web-based system that communications providers can use to report "
    "communications infrastructure status during times of crisis. for the following areas affected by Hurricane Ida: "
    "Alabama: Baldwin, Clarke, Conecuh, Escambia, Mobile, Monroe, Washington. Mississippi: Adams, Pearl River, Yazoo. "
    "Communications providers do not need to provide any additional reporting in DIRS for these areas in Alabama and "
    "Mississippi with respect to Hurricane Ida.")

NICHOLAS = (  # DA-21-1152A1, Sep 14, 2021: two lists with no full stop between them
    "COUNTIES OF INTEREST FOR THIS ACTIVATION INCLUDE THE FOLLOWING: Louisiana: Acadia, Calcasieu, Cameron, "
    "Pointe Coupee, Vermilion, West Feliciana Texas: Brazoria, Chambers, Fort Bend, Galveston, Harris, Wharton The "
    "FCC continues to monitor the storm and may amend the DIRS activation area in the coming days.")

HELENE_OCT_12 = (  # DA-24-1071A1: a removal list, then the counties that remain
    "announces the deactivation of the Disaster Information Reporting System (DIRS) for the following counties in "
    "North Carolina impacted by Hurricane Helene: North Carolina: Ashe, Avery, Burke, Caldwell, Cherokee. "
    "Communications providers do not need to provide any additional reporting in DIRS for these areas in North "
    "Carolina with respect to Hurricane Helene. DIRS remains activated in the following counties: North Carolina: "
    "Buncombe, Haywood, Henderson, Madison, McDowell, Mitchell, Polk, Rutherford, and Yancey.")

BERYL_ACTIVATION = (  # DA-24-657A1: "until DIRS is deactivated" is not a deactivation
    "Reports are due daily at 10:00 a.m. (CDT) until DIRS is deactivated. THE AREA OF INTEREST FOR THIS ACTIVATION "
    "INCLUDES THE FOLLOWING COUNTIES IN TEXAS: Texas: Brazoria, Chambers, Fort Bend, Galveston, Harris, and Matagorda "
    "The FCC continues to monitor this event and may amend the DIRS activation area in the coming days.")

ISAIAS_ACTIVATION = (  # DA-26-1091A1: the same list repeated for the MDRI
    "DIRS IS ACTIVATED IN THE FOLLOWING GEOGRAPHIC AREAS: State of Alabama: Baldwin, Butler, Choctaw. State of "
    "Mississippi: George, Stone. Upon the release of this Public Notice, THE MDRI IS ACTIVATED IN THE FOLLOWING "
    "GEOGRAPHIC AREAS: State of Alabama: Baldwin, Butler, Choctaw, Geneva. State of Mississippi: George, Stone.")

ISAIAS_EXPANSION = (  # DA-26-1103A1: one county, no "State:" list
    "The Public Safety and Homeland Security Bureau (PSHSB) of the Federal Communications Commission (Commission) is "
    "expanding its disaster data collection to include Geneva County in Alabama.")

LAURA_NO_CHANGE = (  # DA-20-989A1
    "DIRS remains activated in the following counties in Louisiana and Texas: Louisiana (no change): Acadia, Allen, "
    "St. John The Baptist, Winn Texas: Jasper, Newton, Orange The FCC appreciates the efforts of communications "
    "providers.")

DORIAN_SEP_5 = (  # DA-19-882A1: "St." inside a list, and "Union and Volusia" with no comma
    "has deactivated its Disaster Information Reporting System (DIRS) for the following areas: Florida: Alachua, "
    "Baker, St. Johns, St. Lucie, Sumter, Union and Volusia Communications providers do not need to provide any "
    "additional reporting in DIRS for these areas in Florida with respect to Hurricane Dorian.")

FINAL = ("the Federal Communications Commission (FCC) has deactivated its Disaster Information Reporting System (DIRS) "
         "for Hurricane Delta. Communications providers do not need to provide any additional reporting in DIRS in "
         "connection with this event.")


def ops(text, kind="area_change", title=""):
    return [(o.action, o.state, o.counties) for o in read_notice(text, kind, title).ops]


def test_activation_lists_are_additions_and_fcc_spellings_are_kept():
    got = ops(IDA_ACTIVATION, "activation")
    assert [(a, s) for a, s, _ in got] == [("add", "Alabama"), ("add", "Louisiana"), ("add", "Mississippi")]
    assert got[1][2] == ["Acadia", "Lafourche", "Point Coupee", "St. Martin", "St. Mary", "St. Bernard",
                         "St. John the Baptist", "Vermillion", "West Feliciana"]


def test_removal_list_after_interjected_text():
    # The opening "DIRS deactivated in Alabama and Mississippi" ends both whole states; the lists name counties.
    assert ops(IDA_PARTIAL) == [("end", "Alabama", []), ("end", "Mississippi", []),
                                ("remove", "Alabama", ["Baldwin", "Clarke", "Conecuh", "Escambia", "Mobile", "Monroe",
                                                      "Washington"]),
                                ("remove", "Mississippi", ["Adams", "Pearl River", "Yazoo"])]


def test_lists_run_together_without_a_full_stop():
    got = ops(NICHOLAS)
    assert got[0][2][-1] == "West Feliciana" and got[1] == ("add", "Texas", ["Brazoria", "Chambers", "Fort Bend",
                                                                          "Galveston", "Harris", "Wharton"])


def test_removal_then_remaining_counties():
    got = ops(HELENE_OCT_12)
    assert [(a, s) for a, s, _ in got] == [("remove", "North Carolina"), ("remain", "North Carolina")]
    assert got[1][2][-1] == "Yancey"


def test_until_dirs_is_deactivated_is_not_a_deactivation():
    assert ops(BERYL_ACTIVATION, "activation") == [("add", "Texas", ["Brazoria", "Chambers", "Fort Bend", "Galveston",
                                                                    "Harris", "Matagorda"])]


def test_mdri_lists_are_ignored():
    got = ops(ISAIAS_ACTIVATION, "activation")
    assert got == [("add", "Alabama", ["Baldwin", "Butler", "Choctaw"]), ("add", "Mississippi", ["George", "Stone"])]


def test_single_county_named_in_a_sentence():
    assert ops(ISAIAS_EXPANSION) == [("add", "Alabama", ["Geneva"])]


def test_no_change_list_and_the_baptist_inside_a_list():
    assert ops(LAURA_NO_CHANGE) == [("remain", "Louisiana", ["Acadia", "Allen", "St. John The Baptist", "Winn"]),
                                    ("remain", "Texas", ["Jasper", "Newton", "Orange"])]


def test_saint_names_and_and_without_comma():
    assert ops(DORIAN_SEP_5) == [("remove", "Florida", ["Alachua", "Baker", "St. Johns", "St. Lucie", "Sumter", "Union",
                                                        "Volusia"])]


def test_final_deactivation_ends_everything():
    assert ops(FINAL, "deactivation", "FCC Deactivates Disaster Reporting for Hurricane Delta") == [("end", "*", [])]


@pytest.mark.parametrize("title,states", [
    ("FCC Deactivates DIRS and MDRI in the Carolinas for Hurricane Debby", ["North Carolina", "South Carolina"]),
    ("FCC Deactivates Disaster Reporting in Florida for Hurricane Idalia", ["Florida"]),
    ("FCC Deactivates Disaster Information Reporting in Puerto Rico and USVI for Hurricane Dorian",
     ["Puerto Rico", "U.S. Virgin Islands"]),
])
def test_deactivation_with_no_list_ends_the_states_in_its_title(title, states):
    assert ops(FINAL, "deactivation", title) == [("end", s, []) for s in states]


def test_area_change_with_nothing_readable_is_reported():
    notice = read_notice("The FCC continues to monitor the storm.", "area_change", "FCC Narrows Something")
    assert notice.ops == [] and notice.unread


def test_ste_genevieve_does_not_end_a_list():  # DA-20-987A1
    text = ("the Federal Communications Commission (FCC) has deactivated its Disaster Information Reporting System "
            "(DIRS) for the following areas affected by Hurricane Laura: Missouri: St. Francois, Ste. Genevieve, Stoddard, "
            "Wright Oklahoma: Adair, Wagoner Communications providers do not need to provide any additional reporting "
            "in DIRS for these areas with respect to Hurricane Laura.")
    assert ops(text) == [("remove", "Missouri", ["St. Francois", "Ste. Genevieve", "Stoddard", "Wright"]),
                         ("remove", "Oklahoma", ["Adair", "Wagoner"])]


def test_footnote_between_lists_keeps_the_meaning():  # DA-24-1021A1
    text = ("announces the deactivation of the Disaster Information Reporting System (DIRS) and the Mandatory Disaster "
            "Response Initiative (MDRI) for the following counties affected by Hurricane Helene: Florida: Alachua, "
            "Baker. See The Federal Communications Commission Announces the Activation of DIRS for Hurricane Helene in "
            "Florida, Public Notice, DA 24-991 (rel. Sept. 25, 2024) (DIRS and MDRI Activation PN). Georgia: Atkinson, "
            "Baker. Communications providers do not need to provide any additional reporting in DIRS for these areas.")
    assert [(a, s) for a, s, _ in ops(text)] == [("remove", "Florida"), ("remove", "Georgia")]


def test_announce_deactivation_without_s():  # DA-24-1039A1
    text = ("In consultation with the States of Georgia and Tennessee, PSHSB announce deactivation of DIRS for the "
            "following counties affected by Hurricane Helene: Georgia: Ben Hill, Bryan. Tennessee: Sevier.")
    assert ops(text) == [("remove", "Georgia", ["Ben Hill", "Bryan"]), ("remove", "Tennessee", ["Sevier"])]


def test_footnote_number_after_a_name_is_dropped():  # DA-20-962A1 prints "Washington (3)"
    text = "COUNTIES OF INTEREST INCLUDE THE FOLLOWING: Tennessee: Wilson (2), Wayne. Indiana: Washington (3)."
    assert ops(text) == [("add", "Tennessee", ["Wilson", "Wayne"]), ("add", "Indiana", ["Washington"])]


@pytest.mark.parametrize("opening,ended", [
    ("DIRS deactivated in Alabama and Mississippi. DIRS remains active in Louisiana.", ["Alabama", "Mississippi"]),
    ("DIRS deactivated in Alabama, Mississipi and some counties in Texas. DIRS remains active in Louisiana.",
     ["Alabama", "Mississippi"]),
    ("DIRS deactivated for all counties in Georgia, South Carolina and Virginia DIRS remains active in North Carolina",
     ["Georgia", "South Carolina", "Virginia"]),
    ("DIRS deactivated for all counties Florida DIRS remains active in Georgia", ["Florida"]),
    ("DIRS deactivated for most counties in Texas. DIRS remains active in some counties in Texas.", []),
])
def test_opening_statement_ends_whole_states(opening, ended):
    got = ops("ANNOUNCES PARTIAL DEACTIVATION OF THE DISASTER INFORMATION REPORTING SYSTEM FOR HURRICANE X " + opening)
    assert [s for a, s, _ in got if a == "end"] == ended


def test_footnote_printed_inside_a_list_at_a_page_break():  # DA-17-899A1
    text = ("DIRS remains activated in the following areas: Florida: Alachua, Gadsden, Gilchrist, 1 DIRS is a "
            "voluntary, web-based system that communications providers, including wireless, wireline, broadcast, cable "
            "and Voice over Internet Protocol providers, can use to report communications infrastructure status and "
            "situational awareness information during times of crisis. 2Glades, Gulf, Washington U.S. Virgin Islands: "
            "St. Croix The FCC appreciates the cooperation of all the communications providers.")
    assert ops(text)[0] == ("remain", "Florida", ["Alachua", "Gadsden", "Gilchrist", "Glades", "Gulf", "Washington"])


def test_a_map_sentence_ends_a_list():  # DA-18-943A1
    text = ("COUNTIES OF INTEREST FOR THIS ACTIVATION INCLUDE: VIRGINIA: Chesapeake City, Suffolk City, Virginia Beach "
            "City A map of the activation area is given below:")
    assert ops(text, "activation") == [("add", "Virginia", ["Chesapeake City", "Suffolk City", "Virginia Beach City"])]
