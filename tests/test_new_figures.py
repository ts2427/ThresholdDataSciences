"""Tests for the chart types added for "When the Network Goes Dark" (multiples, heatmap, calibration, map).

    tds-demos\\.venv\\Scripts\\python -m pytest tests     (from the site root)
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import figures  # noqa: E402

NS = "{http://www.w3.org/2000/svg}"


def parse(svg):
    return ET.fromstring(svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1))


def described(svg, fid):
    root = parse(svg)
    assert root.get("role") == "img" and root.get("aria-labelledby") == f"{fid}-t {fid}-d"
    assert root.find(f"{NS}title").text and root.find(f"{NS}desc").text
    return root


MULT = [{"storm": s, "period": g, "day": str(d), "series": k, "pct": str(v), "lo": str(max(v - 5, 0)), "hi": str(v + 5)}
        for s, g in (("Ida", "P0"), ("Helene", "P1"))
        for d in (0, 1, 2) for k, v in (("stay_out", 10 * d), ("restored", 15 * d))]
MFIG = {"id": "fig-m", "type": "multiples", "title": "T", "description": "D", "panel": "storm", "x": "day", "y": "pct",
        "series": "series", "series_order": ["stay_out", "restored"], "lo": "lo", "hi": "hi", "group": "period",
        "y_max": 100}


def test_multiples_panels_series_band_and_period_marker():
    svg = figures.multiples_chart(MFIG, MULT)
    described(svg, "fig-m")
    assert svg.count('fill-opacity="0.12" stroke="none"') == 2          # one band per panel
    assert svg.count('stroke-dasharray="5 3"') >= 2                     # second series dashed (not colour alone)
    assert figures.SIGNAL in svg and svg.count(f'stroke="{figures.SIGNAL}"') == 1  # one period change -> one rule


def test_multiples_uses_only_ink_slate_rule_muted_and_signal():
    colours = set(re.findall(r'#[0-9A-Fa-f]{6}', figures.multiples_chart(MFIG, MULT)))
    assert colours <= {figures.INK, figures.SLATE, figures.RULE, figures.MUTED, figures.SIGNAL}


HEAT = [{"storm": "Ida", "period": "P0", "day": "0", "pct": "28"}, {"storm": "Ida", "period": "P0", "day": "2", "pct": "10"},
        {"storm": "Helene", "period": "P1", "day": "1", "pct": "12"}]
HFIG = {"id": "fig-h", "type": "heatmap", "title": "T", "description": "D", "row": "storm", "col": "day", "value": "pct",
        "group": "period", "value_max": 30}


def test_heatmap_cells_blank_where_no_report():
    svg = figures.heatmap_chart(HFIG, HEAT)
    described(svg, "fig-h")
    shaded = len(re.findall(r'<rect [^>]*fill="#0F2338" fill-opacity="0\.(?!08\b)', svg))
    assert svg.count('fill="none" stroke="#C9D1D8"') == 3 + 1   # 2 rows x 3 days - 3 reports, plus the legend swatch
    assert shaded >= 3
    assert svg.count(f'stroke="{figures.SIGNAL}"') == 1     # the P0 -> P1 boundary


def test_calibration_points_and_diagonal():
    rows = [{"pred": "1", "obs": "2"}, {"pred": "10", "obs": "9"}, {"pred": "30", "obs": "31"}]
    svg = figures.calibration_chart({"id": "fig-c", "type": "calibration", "title": "T", "x": "pred", "y": "obs"}, rows)
    described(svg, "fig-c")
    assert svg.count("<circle") == 3 and 'stroke-dasharray="4 4"' in svg and figures.SIGNAL not in svg


def test_map_areas_no_data_and_signal_track():
    rows = [{"kind": "area", "label": "Okaloosa, FL", "pct": "52.4", "d": "M0 0 L10 0 L10 10 Z", "x": "", "y": ""},
            {"kind": "area", "label": "Elsewhere", "pct": "", "d": "M20 0 L30 0 L30 10 Z", "x": "", "y": ""},
            {"kind": "track", "label": "", "pct": "", "d": "", "x": "5", "y": "50"},
            {"kind": "track", "label": "", "pct": "", "d": "", "x": "6", "y": "5"}]
    fig = {"id": "fig-map", "type": "map", "title": "T", "description": "D", "value": "pct", "path": "d", "tx": "x", "ty": "y",
           "value_max": 60}
    svg = figures.map_chart(fig, rows)
    described(svg, "fig-map")
    assert 'fill="#FFFFFF" stroke="#C9D1D8"' in svg               # no data: white, outlined
    assert f'stroke="{figures.SIGNAL}"' in svg                     # the track, the one highlight


def test_render_figure_table_options_leave_other_figures_alone(tmp_path):
    (tmp_path / "m.csv").write_text("kind,label,pct,d\narea,A,1,M0 0 Z\ntrack,,,\n", encoding="utf-8")
    fig = {"id": "f", "type": "column", "title": "T", "data": "m.csv", "x": "label", "y": "pct"}
    (tmp_path / "c.csv").write_text("label,pct\nA,1\n", encoding="utf-8")
    plain = figures.render_figure({**fig, "data": "c.csv"}, tmp_path)
    assert "fig-caption" not in plain                               # no description key -> nothing added
    out = figures.data_table([{"kind": "area", "label": "A", "d": "M"}], ["label"])
    assert "<th>label</th>" in out and "<th>d</th>" not in out



def test_interval_vertical_labels_read_downward_and_default_is_unchanged():
    rows = [{"storm": n, "v": str(v), "lo": str(v - 2), "hi": str(v + 3)} for n, v in (("Harvey", 4.7), ("Francine", 9.3))]
    fig = {"id": "f", "type": "interval", "title": "T", "x": "storm", "y": "v", "lo": "lo", "hi": "hi"}
    plain = figures.interval_chart(fig, rows)
    assert "rotate(" not in plain
    turned = figures.interval_chart({**fig, "vertical_labels": True}, rows)
    assert turned.count('transform="rotate(90 ') == 2 and 'text-anchor="start"' in turned



def test_heatmap_marks_excluded_reports_and_legend_reaches_the_maximum():
    rows = HEAT + [{"storm": "Helene", "period": "P1", "day": "2", "pct": ""}]
    svg = figures.heatmap_chart({**HFIG, "value_max": None, "excluded_label": "report excluded"}, rows)
    assert "report excluded" in svg and svg.count(f'stroke="{figures.MUTED}" stroke-width="0.8"/>') >= 2
    assert ">28<" in svg                                         # the legend ends at the maximum, 28
    assert 'fill-opacity="0.08' not in svg                       # lightest shade kept clear of blank cells


def test_map_track_is_clipped_to_the_frame():
    rows = [{"kind": "area", "label": "A", "pct": "5", "d": "M0 0 L10 0 L10 10 Z", "x": "", "y": ""},
            {"kind": "track", "label": "", "pct": "", "d": "", "x": "50", "y": "900"},
            {"kind": "track", "label": "", "pct": "", "d": "", "x": "50", "y": "100"}]
    fig = {"id": "m", "type": "map", "title": "T", "value": "pct", "path": "d", "tx": "x", "ty": "y", "width": 200,
           "height": 300}
    svg = figures.map_chart(fig, rows)
    track = re.search(r'<path d="(M[^"]+)" fill="none" stroke="' + figures.SIGNAL, svg).group(1)
    ys = [float(v) for v in re.findall(r"[ML][\d.]+ ([\d.]+)", track)]
    assert max(ys) <= 300 and min(ys) == 100


def test_heatmap_flagged_cell_is_shaded_outlined_and_labelled():
    rows = [{**r, "flag": ""} for r in HEAT] + [{"storm": "Helene", "period": "P1", "day": "-1", "pct": "3", "flag": "x"}]
    svg = figures.heatmap_chart({**HFIG, "flag": "flag", "flag_label": "combined report"}, rows)
    assert svg.count('stroke-dasharray="2.5 1.5"') == 2          # the cell and its legend swatch
    assert "combined report" in svg
    plain = figures.heatmap_chart(HFIG, HEAT)
    assert 'stroke-dasharray="2.5 1.5"' not in plain
