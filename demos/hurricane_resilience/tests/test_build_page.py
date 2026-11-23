"""Step 11: page build helpers."""
import importlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
step11 = importlib.import_module("11_build_page")
from config import DOCS, OUTPUT, RAW  # noqa: E402  (same layout in the private project and the public repository)
RESULTS = OUTPUT / "results.json"
needs_results = pytest.mark.skipif(not RESULTS.exists() or "chapter_9" not in RESULTS.read_text(encoding="utf-8"),
                                   reason="needs output/results.json from step 10 (not committed)")


def test_figure_verification_catches_a_changed_value(tmp_path):
    rows = {"x.csv": [{"storm": "Helene", "peak_pct_out": 12.1}]}
    step11.write_figure_csvs(rows, tmp_path)
    assert step11.verify_figure_csvs(rows, tmp_path) == {"x.csv": True}
    pd.DataFrame([{"storm": "Helene", "peak_pct_out": 12.4}]).to_csv(tmp_path / "x.csv", index=False)
    assert step11.verify_figure_csvs(rows, tmp_path) == {"x.csv": False}


def test_deviations_are_read_from_the_log():
    log = ("| Date | Decision | Why |\n|---|---|---|\n| 2026-11-22 | DEVIATION (x): did y | because z |\n"
           "| 2026-11-22 | ordinary decision | w |\n")
    assert step11.deviations(log) == [("2026-11-22", "DEVIATION (x): did y", "because z")]


def test_seen_before_registration_is_taken_from_the_plan():
    plan = "# Plan\n\n## Seen before registration\nline one\n- item\n\n## Questions\n1. q"
    assert step11.seen_before_registration(plan) == "line one\n- item"


def test_snapshot_lists_exclude_raw_data_secrets_and_prompts():
    allowed = set(step11.SNAPSHOT_DIRS) | set(step11.SNAPSHOT_DOCS) | set(step11.SNAPSHOT_RESULTS)
    for bad in ("data", ".env", "CLAUDE.md", "KICKOFF_PROMPT.md", "interim", "raw"):
        assert bad not in allowed


@needs_results
def test_page_wording_and_required_items():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    body = step11.build_page(r)
    low = body.lower()
    for bad in ("because of vulnerab", "neglect", "prioritiz", "caused by", "coincided with faster",
                "battery", "generator depletion"):
        assert bad not in low, bad
    assert "can't yet show whether the fcc's 2024–2025 rules" in low
    assert "6 to 11 of 20" in body and "Nicole: no report after its peak, so no recovery could be observed." in body  # Nicole left out (2026-11-23)


@needs_results
def test_every_figure_marker_has_a_figure():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    body = step11.build_page(r) + step11.methods_section(
        r, (DOCS / "decisions.md").read_text(encoding="utf-8"),
        (DOCS / "analysis_plan.md").read_text(encoding="utf-8"),
        pd.read_csv(OUTPUT / "validation_dirs.csv"),
        pd.read_csv(OUTPUT / "excluded_reports.csv", keep_default_na=False))
    ids = {f["id"] for f in step11.figures_front_matter({k: True for k in step11.figure_rows(r)}, r)}
    import re
    assert set(re.findall(r"\[figure:([a-z0-9-]+)\]", body)) == ids


def test_front_matter_reads_back_as_yaml_structure():
    text = step11._yaml({"draft": True, "title": "When the Network Goes Dark",
                         "figures": [{"id": "fig-1", "verified": True, "title": "A title – dash"}]})
    lines = text.splitlines()
    assert lines[0] == "draft: true" and '  - id: "fig-1"' in lines and "    verified: true" in lines



def test_days_print_at_their_stated_precision():
    assert step11.fdays(7.000000000000001) == "7"
    assert step11.fdays(3.0000000000000004) == "3"
    assert step11.fdays(1.9583333333333335) == "2"
    assert step11.fdays(2.5) == "2.5"
    assert step11.fdays(None) == "–"



def test_neutral_wording_keeps_the_change_and_drops_who_chose():
    s = step11.neutral("Second independent check, finding 8; chosen by Tim from options proposed by Claude Code, "
                       "2026-11-23 (the footnote wording is Tim's)")
    assert s == "Second independent check, finding 8"
    assert step11.neutral("Tim's instruction, 2026-11-23") == ""
    w = step11.neutral("Serious (Tim): a, b. Assigned by Claude Code, not named by Tim: 'x' = serious")
    assert "Tim" not in w and "Claude" not in w and "Serious: a, b" in w and "'x' = serious" in w



def test_neutral_keeps_the_reason_inside_an_attributing_parenthesis():
    s = step11.neutral("Chosen by Tim from options proposed by Claude Code, 2026-11-22 (naming Helene Oct 1 is Tim's "
                       "addition; independent check, finding 15)")
    assert s == "Independent check, finding 15"
    assert step11.neutral("New exhibits (chosen by Tim from options proposed by Claude Code, 2026-11-22): a") == "New exhibits: a"



def test_opening_numbers_come_from_results():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    n = step11.opening_numbers(r)
    h4 = r["chapter_4"]["headlines"]["n_storms_reaching_90pct_restored"]
    assert n["n_reports"] == r["chapter_1"]["headlines"]["n_reports_used"]["value"]
    assert (n["n90_low"], n["n90_high"], n["n_storms_recovery"]) == (h4["min"], h4["max"], h4["n"])
    text = "\n".join(step11.opening_section(r))
    assert "[" not in text and "{: .page-lede}" in text



def test_lookup_data_from_the_panel_leaves_flagged_reports_off_the_timeline():
    r = {"chapter_3": {"storms": [{"storm_key": "K", "storm": "Laura", "rule_period": "P0",
                                   "landfall_utc": "2020-08-26 14:00:00+00:00"}]},
         "chapter_1": {"time_flagged_reports": [{"storm": "Laura", "report_date": "2020-08-25", "doc_id": "D0"}]}}
    p = pd.DataFrame({"storm_key": "K", "doc_id": ["D0", "D1", "D1"], "fips": ["22001", "22001", "22003"],
                      "county": ["ACADIA", "ACADIA", "ALLEN"], "state": "Louisiana",
                      "as_of_utc": ["2020-08-25 16:00:00+00:00", "2020-08-27 14:00:00+00:00", "2020-08-27 14:00:00+00:00"],
                      "report_date": ["2020-08-25", "2020-08-27", "2020-08-27"], "sites_served": [10, 10, 20],
                      "sites_out": [5, 2, 0], "time_flag": ["pre_onset_likely_marco", "", ""]})
    d = step11.lookup_data(r, p)
    acadia = next(c for c in d["counties"] if c["fips"] == "22001")
    assert acadia["series"]["K"] == [[1.0, 20.0, 2, 10, "2020-08-27"]]        # the flagged report is not on the line
    assert d["storms"][0]["report_days"] == [1.0] and "left off Laura's line" in d["note"]



def test_map_topology_round_trip_matches_the_simplified_shapes():
    import shapely
    from shapely.geometry import Polygon
    ring = [(-90.0, 30.0), (-89.5, 30.0), (-89.5, 30.4), (-90.0, 30.4), (-90.0, 30.0)]
    x0, y0, kx, ky = -91.0, 29.0, 0.001, 0.001
    arc = step11._encode_ring(ring, x0, y0, kx, ky)
    back = step11.decode_arc(arc, {"scale": [kx, ky], "translate": [x0, y0]})
    assert max(abs(a - c) + abs(b - d) for (a, b), (c, d) in zip(ring, back)) < 2 * kx
    assert Polygon(back).equals_exact(Polygon(ring), tolerance=kx)


def test_map_data_leaves_flagged_reports_off_the_slider_and_keeps_causes_blank_when_not_printed():
    r = {"chapter_3": {"storms": [{"storm_key": "K", "storm": "Laura", "rule_period": "P0",
                                   "landfall_utc": "2020-08-26 14:00:00+00:00"}]},
         "chapter_1": {"time_flagged_reports": [{"storm": "Laura", "report_date": "2020-08-25", "doc_id": "D0"}]}}
    p = pd.DataFrame({"storm_key": "K", "doc_id": ["D0", "D1"], "fips": ["22001", "22001"],
                      "as_of_utc": ["2020-08-25 16:00:00+00:00", "2020-08-27 14:00:00+00:00"],
                      "report_date": ["2020-08-25", "2020-08-27"], "sites_served": [10, 10], "sites_out": [5, 4],
                      "out_damage": [None, None], "out_transport": [None, None], "out_power": [None, None],
                      "time_flag": ["pre_onset_likely_marco", ""]})
    d = step11.map_data(r, p)
    reps = d["storms"][0]["reports"]
    assert [x["doc_id"] for x in reps] == ["D1"] and reps[0]["counties"]["22001"] == [40.0, 4, 10, None]



def test_map_topology_rings_wind_clockwise_for_d3():
    import json
    import shapely
    from shapely.geometry import LinearRing
    topo = json.loads(step11.MAP_TOPO.read_text(encoding="utf-8")) if step11.MAP_TOPO.exists() else step11.map_topology()
    tr = topo["transform"]
    first_rings = [g["arcs"][0][0][0] for g in topo["objects"]["counties"]["geometries"][:50]]
    assert all(not LinearRing(step11.decode_arc(topo["arcs"][i], tr)).is_ccw for i in first_rings)


def test_v2_sections_wording_and_generated_numbers():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    if "v2_5_network_redundancy" not in r:
        return
    text = step11.v2_sections(r) + "\n".join(step11.v2_opening(r))
    low = text.lower()
    for bad in ("because of vulnerab", "neglect", "prioritiz", "caused by", "leads to", "drives", "predicted fail",
                "about to fail", "never restored", "abandon", "claude"):
        assert bad not in low, bad
    a = r["v2_1_public_record_misses"]["headlines"]
    assert f"{a['n_storms']} storms" in text and f"{a['sites_out_at_last_reports_headline']['value']:,.0f}" in text
    assert "Exploratory: added after version 1" in text



def test_plan_commit_on_the_page_is_in_the_history():
    import subprocess
    out = subprocess.run(["git", "-C", str(ROOT), "log", "--format=%h %ad %s", "--date=short", "--", "docs/analysis_plan.md"],
                         capture_output=True, text=True).stdout
    if not out:  # the public repository has no private history; it checks the plan file's SHA-256 instead
        import pytest
        pytest.skip("the plan's commit is in the private repository's history")
    line = next((ln for ln in out.splitlines() if ln.startswith(step11.PLAN_COMMIT["hash"])), "")
    assert line and "2026-11-22" in line and "before any recovery outcome" in line


def test_fcc_caveat_is_quoted_verbatim_from_the_reports():
    raw = RAW / "dirs"
    if not raw.exists():
        return
    hits = [p for p in raw.glob("*.txt") if step11.FCC_CAVEAT in p.read_text(encoding="utf-8", errors="replace")]
    assert len(hits) >= 1


def test_no_priority_or_preregistration_wording_on_the_page():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    text = step11.build_page(r).lower() + step11.v2_sections(r).lower()
    for bad in ("pre-registered", "preregistered", "pre-registration", "for the first time", "the first to",
                "first-ever", "first study of", "first analysis"):
        assert bad not in text, bad
