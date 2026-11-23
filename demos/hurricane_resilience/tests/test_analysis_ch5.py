"""Step 10, chapter 5 (causes): helpers."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")


def panel(rows, note=False):
    """rows: (doc_id, days, fips, served, out, damage, transport, power, backup)"""
    out = []
    for d, t, f, s, o, dm, tr, pw, bk in rows:
        causes = [dm, tr, pw]
        gap = None if None in causes else o - sum(causes)
        out.append({"storm_key": "K", "storm": "K", "doc_id": d, "days_since_landfall": t, "report_date": f"2024-09-{20 + t}",
                    "fips": f, "sites_served": s, "sites_out": o, "out_damage": dm, "out_transport": tr, "out_power": pw,
                    "out_unattributed": None if gap is None else max(gap, 0),
                    "out_overattributed": None if gap is None else max(-gap, 0),
                    "on_backup_power": bk, "fcc_multiple_causes_note": note, "report_status": "ok", "report_flags": ""})
    return pd.DataFrame(out)


P = panel([("D1", 1, "a", 100, 10, 1, 2, 5, 20),    # 2 unattributed
           ("D1", 1, "b", 100, 10, 0, 6, 6, None),  # 2 overattributed; backup not printed
           ("D2", 2, "a", 100, 4, 0, 1, 3, 10),
           ("D2", 2, "b", 100, 6, 1, 1, 4, 5)])


def test_report_cause_counts_and_shares_of_sites_out():
    r = step10.cause_by_report(P).set_index("doc_id")
    assert r.loc["D1", ["sites_out", "out_damage", "out_transport", "out_power", "out_unattributed", "out_overattributed"]].tolist() == [20, 1, 8, 11, 2, 2]
    sh = step10.cause_shares(r.loc["D1"])
    assert sh == pytest.approx({"damage": 5.0, "transport": 40.0, "power": 55.0, "unattributed": 10.0, "overattributed": 10.0})
    # never netted: the four shares minus over-attribution make 100
    assert sh["damage"] + sh["transport"] + sh["power"] + sh["unattributed"] - sh["overattributed"] == pytest.approx(100)


def test_rows_without_causes_are_left_out_of_the_denominator():
    p = pd.concat([P, panel([("D1", 1, "c", 100, 50, None, None, None, None)])], ignore_index=True)
    r = step10.cause_by_report(p).set_index("doc_id")
    assert r.loc["D1", "sites_out"] == 20 and r.loc["D1", "sites_out_not_collected"] == 50


def test_backup_share_uses_sites_served_where_printed():
    r = step10.cause_by_report(P).set_index("doc_id")
    assert r.loc["D1", "on_backup_power"] == 20 and r.loc["D1", "served_with_backup_column"] == 100
    assert r.loc["D2", "backup_pct_of_served"] == pytest.approx(7.5)


def test_storm_pooled_shares_weight_each_report_by_its_sites_out():
    pooled = step10.pooled_shares(step10.cause_by_report(P))
    # damage 2 of 30, transport 10, power 18, unattributed 2, over 2
    assert pooled["damage"] == pytest.approx(100 * 2 / 30) and pooled["power"] == pytest.approx(60.0)
    assert pooled["sites_out"] == 30


def test_county_bootstrap_of_storm_shares_is_reproducible_and_brackets():
    a = step10.bootstrap_cause_shares(P, draws=400, seed=5)
    b = step10.bootstrap_cause_shares(P, draws=400, seed=5)
    assert np.array_equal(a["power"], b["power"])
    lo, hi = np.percentile(a["power"], [2.5, 97.5])
    assert lo <= 60.0 <= hi


def test_storm_with_no_cause_columns_is_not_collected():
    p = panel([("D1", 1, "a", 100, 10, None, None, None, None)])
    assert step10.cause_by_report(p).sites_out.sum() == 0
    assert step10.has_causes(p) is False


def test_multiple_causes_note_is_carried_per_report():
    r = step10.cause_by_report(panel([("D1", 1, "a", 10, 5, 3, 2, 2, None)], note=True))
    assert bool(r.fcc_multiple_causes_note.iloc[0]) is True


def test_a_report_shared_by_two_storms_stays_split_by_storm():
    # Ida and Nicholas share reports (DA-21-1152): each storm keeps its own rows
    a = panel([("D1", 1, "a", 100, 10, 1, 2, 7, None)]).assign(storm_key="IDA", storm="Ida")
    b = panel([("D1", 1, "b", 100, 4, 0, 1, 3, None)]).assign(storm_key="NIC", storm="Nicholas")
    r = step10.cause_by_report(pd.concat([a, b], ignore_index=True))
    assert sorted(zip(r.storm_key, r.sites_out)) == [("IDA", 10), ("NIC", 4)]



def test_attributed_only_conversion_for_the_external_check():
    got = step10.attributed_only({"damage": 1.0, "transport": 32.1, "power": 59.9})
    assert got["damage"] == pytest.approx(100 * 1.0 / 93.0) and got["power"] == pytest.approx(100 * 59.9 / 93.0)
    assert sum(got.values()) == pytest.approx(100)


def test_chapter_5_storms_carry_no_rule_period():
    assert "rule_period" not in step10.CH5_STORM_FIELDS
