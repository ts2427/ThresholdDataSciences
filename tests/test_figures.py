"""Tests for the chart types added for the demo pages (interval, waterfall).

    tds-demos\\.venv\\Scripts\\python -m pytest tests     (from the site root)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import figures  # noqa: E402

WF = [{"step": "Raw names", "value": "100", "kind": "start"},
      {"step": "Duplicates removed", "value": "-10", "kind": "step"},
      {"step": "Names normalized", "value": "-30", "kind": "step"},
      {"step": "Employers final", "value": "60", "kind": "end"}]


def test_waterfall_rows_geometry():
    bars = figures.waterfall_rows(WF, "step", "value")
    assert [(b[1], b[2]) for b in bars] == [(0, 100), (90, 100), (60, 90), (0, 60)]


def test_waterfall_rows_end_must_reconcile():
    bad = WF[:-1] + [{"step": "End", "value": "61", "kind": "end"}]
    with pytest.raises(ValueError):
        figures.waterfall_rows(bad, "step", "value")


def test_waterfall_rows_rejects_unknown_kind_and_missing_start():
    with pytest.raises(ValueError):
        figures.waterfall_rows([{"step": "x", "value": "1", "kind": "bar"}], "step", "value")
    with pytest.raises(ValueError):
        figures.waterfall_rows(WF[1:], "step", "value")


def test_waterfall_chart_labels_steps_with_sign():
    svg = figures.waterfall_chart({"x": "step", "y": "value", "title": "t"}, WF)
    assert "−10" in svg and "−30" in svg and ">100<" in svg and ">60<" in svg
    assert svg.count("<rect") == 4
    assert figures.SIGNAL not in svg


def test_interval_chart_draws_points_intervals_and_one_signal():
    rows = [{"e": str(e), "est": str(v), "lo": str(v - 1), "hi": str(v + 1)}
            for e, v in [(-2, 0.3), (-1, 0.0), (0, -4.0), (1, -6.0)]]
    svg = figures.interval_chart({"x": "e", "y": "est", "lo": "lo", "hi": "hi",
                                  "title": "t", "signal_before": 0}, rows)
    assert svg.count("<circle") == 4
    assert svg.count(figures.SIGNAL) == 1


def test_registry():
    assert figures.RENDERERS["waterfall"] is figures.waterfall_chart
    assert figures.RENDERERS["interval"] is figures.interval_chart


def test_wrap_label():
    assert figures.wrap_label("Duplicates removed") == ["Duplicates", "removed"]
    assert figures.wrap_label("Raw employer names") == ["Raw employer", "names"]
    assert figures.wrap_label("Employers (final)") == ["Employers", "(final)"]
