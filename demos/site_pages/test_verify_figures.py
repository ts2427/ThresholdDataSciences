import pandas as pd

from site_pages.verify_figures import check_event_study, check_naive_vs_careful, check_waterfall

RES_A = {"step2_main": {"event_study": {"pop": [
    {"e": -1, "att": None, "lo": None, "hi": None},
    {"e": 0, "att": -4.0891, "lo": -5.8424, "hi": -2.3358}]}},
    "naive_vs_careful": {"point": {"naive_change": -18.79, "comparison_change": -10.64, "adjusted_change": -8.15},
                         "ci95": {"naive_change": [-21.31, -15.34], "comparison_change": [-12.36, -9.10],
                                  "adjusted_change": [-11.17, -4.33]}}}
RES_B = {"final_tables": {"waterfall": [
    {"employers_by_name": 100, "employers_by_name_and_state": 120},
    {"employers_by_name": 90, "employers_by_name_and_state": 110},
    {"employers_by_name": 60, "employers_by_name_and_state": 80}]}}


def test_event_study_match_and_mismatch():
    good = pd.DataFrame({"year_relative_to_expansion": [-1, 0], "estimate_pp": [0.0, -4.09],
                         "ci95_low": [0.0, -5.84], "ci95_high": [0.0, -2.34]})
    assert check_event_study(good, RES_A) == []
    bad = good.assign(estimate_pp=[0.0, -4.2])
    assert len(check_event_study(bad, RES_A)) == 1


def test_naive_vs_careful():
    csv = pd.DataFrame({"comparison": ["a", "b", "c"], "decline_pp": [18.8, 10.6, 8.2],
                        "change_pp": [-18.79, -10.64, -8.15], "ci95_low": [-21.31, -12.36, -11.17],
                        "ci95_high": [-15.34, -9.10, -4.33]})
    assert check_naive_vs_careful(csv, RES_A) == []
    assert check_naive_vs_careful(csv.assign(decline_pp=[18.8, 10.6, 8.3]), RES_A) != []


def test_waterfall():
    csv = pd.DataFrame({"step": ["start", "dup", "end"], "value": [100, -10, 90], "kind": ["start", "step", "end"],
                        "employers_by_name_after": [100, 90, 90],
                        "employers_by_name_and_state_after": [120, 110, 110]})
    # json has 3 levels -> expects start, 2 steps, end
    assert check_waterfall(csv, RES_B) == ["waterfall: unexpected row kinds"]
    csv = pd.DataFrame({"step": ["s", "a", "b", "e"], "value": [100, -10, -30, 60],
                        "kind": ["start", "step", "step", "end"],
                        "employers_by_name_after": [100, 90, 60, 60],
                        "employers_by_name_and_state_after": [120, 110, 80, 80]})
    assert check_waterfall(csv, RES_B) == []
