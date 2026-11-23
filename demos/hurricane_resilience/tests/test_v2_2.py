"""V2-2: sites operating on backup power, where collected (blank = not collected, never zero)."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
v2 = importlib.import_module("12_v2_analysis")


def test_blank_is_not_collected_and_shares_use_printed_counties():
    p = pd.DataFrame({"doc_id": ["D1", "D1", "D2", "D2"], "report_date": ["2024-09-01"] * 2 + ["2024-09-02"] * 2,
                      "days_since_landfall": [0.5, 0.5, 1.5, 1.5], "fips": ["A", "B", "A", "B"],
                      "sites_served": [100, 50, 100, 50], "on_backup_power": [20, np.nan, np.nan, np.nan]})
    d1, d2 = v2.backup_by_report(p)
    assert d1["collected"] and d1["sites_on_backup"] == 20 and d1["partial"]
    assert d1["share_of_sites_served"] == 0.2 and abs(d1["share_of_all_sites_served"] - 20 / 150) < 1e-12
    assert not d2["collected"] and "sites_on_backup" not in d2      # never zero-filled
