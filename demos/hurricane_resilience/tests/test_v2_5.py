"""V2-5: provider counts never carry provider identifiers into results; groups follow the fixed cut points."""
import importlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
v2 = importlib.import_module("12_v2_analysis")


def test_assign_group_uses_fixed_cut_points():
    g = {"cut_low": 2, "cut_high": 3, "labels": ["2 or fewer", "3", "4 or more"]}
    assert [v2.assign_group(x, g) for x in (0, 2, 3, 4, 6)] == ["2 or fewer"] * 2 + ["3", "4 or more", "4 or more"]


def test_counts_never_expose_provider_ids():
    b = pd.DataFrame({"release": "R", "geoid": ["01001"] * 3, "data_type": "Mobile Broadband",
                      "provider_id": ["111", "222", "333"], "res_st_pct": [0.9, 0.6, 0.1], "bus_iv_pct": 0.0})
    c = v2.provider_counts(b, "mobile_half", set())
    assert c.loc[("R", "01001")] == 2 and c.name == "provider_id" and "111" not in str(c.to_dict())


@pytest.mark.skipif(not (ROOT / "output" / "results.json").exists(), reason="no results")
def test_results_hold_no_provider_identifier_key():
    r = json.loads((ROOT / "output" / "results.json").read_text(encoding="utf-8"))
    txt = json.dumps({k: v for k, v in r.items() if k.startswith("v2_5")})
    assert '"provider_id"' not in txt and "provider_name" not in txt
