"""out_unattributed must survive from step 3 to the panel and the public CSV."""
import ast
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from carried import add_unattributed, require_carried  # noqa: E402


def frame(out, *causes):
    return pd.DataFrame([dict(zip(["sites_out", "out_damage", "out_transport", "out_power"], [out, *causes]))])


@pytest.mark.parametrize("out,causes,short,over", [(5, (0, 1, 3), 1, 0), (1, (0, 1, 6), 0, 6), (3, (1, 1, 1), 0, 0)])
def test_shortfall_and_excess(out, causes, short, over):
    r = add_unattributed(frame(out, *causes)).iloc[0]
    assert (r.out_unattributed, r.out_overattributed) == (short, over)
    # the identity chapter 5 relies on
    assert sum(causes) + r.out_unattributed - r.out_overattributed == out


def test_no_cause_columns_is_unknown_not_zero():
    r = add_unattributed(frame(5, None, None, None)).iloc[0]
    assert pd.isna(r.out_unattributed) and pd.isna(r.out_overattributed)


@pytest.mark.parametrize("col", ["out_unattributed", "out_overattributed"])
def test_a_table_that_drops_the_column_is_refused(col):
    with pytest.raises(ValueError, match=col):
        require_carried(add_unattributed(frame(5, 0, 1, 3)).drop(columns=col), "panel")


def test_column_survives_a_csv_round_trip(tmp_path):
    add_unattributed(frame(5, 0, 1, 3)).to_csv(tmp_path / "x.csv", index=False)
    require_carried(pd.read_csv(tmp_path / "x.csv"), "public csv")


def test_step_3_writes_the_column_and_the_county_list(tmp_path, monkeypatch):
    step3 = importlib.import_module("03_parse_dirs")
    text = "Florida: Bay.\n911 Services\nFL BAY 10 3 30% 0 1 1 4\nTOTAL - 10 3 30% 0 1 1 4\n"
    pd.DataFrame([{"doc_id": "DOC-1A1", "storm_name": "X", "nhc_id": "AL012026", "report_date": "2026-10-12"}]
                 ).to_csv(tmp_path / "manifest.csv", index=False)
    monkeypatch.setattr(step3, "MANIFEST", tmp_path / "manifest.csv")
    monkeypatch.setattr(step3, "INTERIM", tmp_path)
    monkeypatch.setattr(step3, "report_text", lambda doc: (text, "txt"))
    step3.main()
    rows = pd.read_parquet(tmp_path / "dirs_county_rows.parquet")
    require_carried(rows, "step 3")
    assert rows.out_unattributed.tolist() == [1]
    assert {"row_storm", "row_nhc_id", "row_dirs_activation_date", "storm_key_flag", "area_status"} <= set(rows.columns)
    assert pd.read_parquet(tmp_path / "dirs_county_lists.parquet").county.tolist() == ["Bay"]


@pytest.mark.parametrize("script", ["05_fips.py", "09_build_panel.py"])
def test_downstream_steps_must_check_the_column_once_built(script):
    """Passes while the step is a stub; fails if it gets built without calling require_carried."""
    src = (ROOT / "src" / script).read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert "out_unattributed" in ast.get_docstring(tree), "the step's spec must name the column"
    if "Not implemented yet" in src:
        return
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "require_carried"]
    assert calls, f"{script} must call require_carried on what it writes"
