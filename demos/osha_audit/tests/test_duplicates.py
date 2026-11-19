import pandas as pd

from osha_audit.src.duplicates import (candidate_pairs, classify, clusters, norm_text,
                                       plan_removals, score_pair)


def _row(upa, emp, addr="1 Main St", zipc="12345", date="1/1/2020", state="TX",
         narr="An employee cut a finger on a saw.", codes=("a", "b", "c", "d")):
    return {"UPA": str(upa), "Employer": emp, "Address1": addr, "Zip": zipc, "EventDate": date,
            "State": state, "Final Narrative": narr, "Nature": codes[0], "Part of Body": codes[1],
            "Event": codes[2], "Source": codes[3]}


def test_norm_text():
    assert norm_text("  Acme, Inc. #12 ") == "acme inc 12"


def test_candidate_pairs_address_or_zip():
    df = pd.DataFrame([_row(1, "A"), _row(2, "A", addr="1 MAIN ST."), _row(3, "A", addr="9 Elm", zipc="12345-6789"),
                       _row(4, "A", addr="9 Elm", zipc="99999"), _row(5, "A", date="1/2/2020")])
    pairs = set(candidate_pairs(df))
    assert (0, 1) in pairs and (0, 2) in pairs and (1, 2) in pairs
    assert not any(4 in p for p in pairs)            # different date
    assert (0, 3) not in pairs                       # different address and ZIP


def test_classify():
    assert classify({"codes_equal": 4, "narr_sim": 10, "emp_sim": 95}) == "same_employer_duplicate"
    assert classify({"codes_equal": 1, "narr_sim": 85, "emp_sim": 30}) == "cross_employer_same_incident"
    assert classify({"codes_equal": 2, "narr_sim": 79, "emp_sim": 100}) is None


def test_score_pair():
    s = score_pair(pd.Series(_row(1, "Acme Inc")), pd.Series(_row(2, "ACME, Inc.", codes=("a", "b", "c", "x"))))
    assert s["codes_equal"] == 3 and s["emp_sim"] == 100 and s["narr_sim"] == 100


def test_clusters_union_find():
    cs = clusters([(1, 2), (2, 3), (7, 8)])
    assert sorted(map(sorted, cs)) == [[1, 2, 3], [7, 8]]


def test_plan_removals_keeps_lowest_upa_and_keeps_cross_employer():
    df = pd.DataFrame([
        _row(30, "Acme Inc"), _row(10, "ACME, Inc."),               # same employer: remove UPA 30
        _row(20, "Staffing Co", addr="5 Oak", zipc="55555"),
        _row(21, "Host Plant LLC", addr="5 Oak", zipc="55555"),     # cross-employer: keep both
    ])
    pairs, remove = plan_removals(df)
    assert remove == {0}
    assert (pairs["class"] == "cross_employer_same_incident").sum() == 1
