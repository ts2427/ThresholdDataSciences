"""V2-1: what the public record misses (last report's sites still out, counties left while out)."""
import importlib
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
v2 = importlib.import_module("12_v2_analysis")


def panel():
    rows = [("D1", 0.5, "2024-09-01", "A", 100, 40), ("D1", 0.5, "2024-09-01", "B", 50, 10), ("D1", 0.5, "2024-09-01", "C", 20, 5),
            ("D2", 1.5, "2024-09-02", "A", 100, 12), ("D2", 1.5, "2024-09-02", "B", 50, 0),           # C left while out (5)
            ("D3", 2.5, "2024-09-03", "A", 100, 3)]                                                    # B left, at 0
    return pd.DataFrame([{"storm_key": "K", "doc_id": d, "days_since_landfall": t, "report_date": r, "fips": f,
                          "county": f, "state": "Florida", "sites_served": s, "sites_out": o} for d, t, r, f, s, o in rows])


def test_last_report_sites_still_out_and_counties():
    m = v2.last_report_misses(panel(), peak_sites_out=55)
    assert m["last_report"]["doc_id"] == "D3" and m["sites_out_at_last_report"]["value"] == 3
    assert abs(m["share_of_peak"]["value"] - 3 / 55) < 1e-12
    assert [c["fips"] for c in m["counties_still_out"]] == ["A"]


def test_counties_that_left_while_out_are_listed_with_their_last_value():
    m = v2.last_report_misses(panel(), peak_sites_out=55)
    assert [(c["fips"], c["sites_out"], c["last_report_date"]) for c in m["counties_left_while_out"]] == [("C", 5, "2024-09-01")]
    assert m["carried_forward"]["sites_out"]["value"] == 8   # 3 in the last report + C's 5 carried


def test_storm_whose_reports_are_all_shared_is_footnoted():
    p = pd.DataFrame({"storm_key": ["I", "I", "N", "N"], "storm": ["Ida", "Ida", "Nicholas", "Nicholas"],
                      "doc_id": ["D1", "D2", "D2", "D2"]})
    assert v2.shared_only_note("N", p) == "Nicholas: its 1 reports are shared with Ida, so its record is short."
    assert v2.shared_only_note("I", p) is None
