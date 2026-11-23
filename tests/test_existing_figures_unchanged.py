"""Snapshot test: every Medicaid and OSHA figure renders exactly as it did before the new chart types were added.

The snapshot (tests/snapshots/existing_figures.json) was written on 2026-11-22, before figures.py was changed.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
import figures  # noqa: E402

SNAP = json.loads((SITE / "tests" / "snapshots" / "existing_figures.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("snap", SNAP, ids=[f"{s['page']}:{s['fig']['id']}" for s in SNAP])
def test_existing_figure_renders_identically(snap):
    html = figures.render_figure(snap["fig"], SITE / "content" / "data")
    assert hashlib.sha256(html.encode("utf-8")).hexdigest() == snap["sha256"]
    assert html == snap["html"]
