"""Step 10, chapter 6 (power co-movement): helpers."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")


def panel(n=30, storm="K", seed=0, lag_shift=0.0):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, 80, n)
    rows = []
    for i in range(n):
        out = int(round(x[i] / 2 + rng.normal(0, 2)))
        rows.append({"storm_key": storm, "storm": storm, "doc_id": f"D{i % 3}", "fips": f"{i:05d}", "days_since_landfall": i % 3,
                     "report_date": "2024-09-28", "sites_served": 100, "sites_out": max(out, 0),
                     "out_power": max(out - 1, 0), "out_damage": 0, "out_transport": 1,
                     "eaglei_match": "matched", "eaglei_mcc_flag": "ok", "eaglei_modeled_customers": 1000.0,
                     "eaglei_customers_out": 10 * x[i], "eaglei_customers_out_6h": 10 * x[i] + lag_shift,
                     "eaglei_customers_out_12h": 10 * x[i], "eaglei_customers_out_24h": 10 * x[i] * 0 + 5,
                     "eaglei_customers_out_zero_filled": 10 * x[i], "acs_households": 900.0,
                     "eaglei_coverage_flag": "ok", "report_status": "ok", "report_flags": "", "storm_year": 2024})
    return pd.DataFrame(rows)


def test_spearman_matches_scipy():
    from scipy.stats import spearmanr
    a, b = np.array([1, 5, 2, 8, 3.0]), np.array([2, 9, 1, 7, 4.0])
    assert step10.spearman(a, b) == pytest.approx(spearmanr(a, b).statistic)


def test_power_frame_uses_matched_rows_with_plausible_mcc_only():
    p = panel()
    p.loc[0, "eaglei_mcc_flag"] = "mcc_below_observed_outages"
    p.loc[1, "eaglei_match"] = "no_record_within_30min"
    f = step10.power_frame(p, lag=0)
    assert len(f) == 28
    assert f.pct_customers_out.max() <= 100 and "pct_sites_out" in f and "pct_sites_out_power" in f


def test_lagged_value_is_used_for_the_lag():
    p = panel()
    f24 = step10.power_frame(p, lag=24)
    assert (f24.pct_customers_out == 0.5).all()  # 5 of 1,000 meters, the 24-hour-earlier value


def test_households_denominator_for_the_sensitivity():
    f = step10.power_frame(panel(), lag=0, denominator="acs_households")
    g = step10.power_frame(panel(), lag=0)
    assert f.pct_customers_out.iloc[0] == pytest.approx(g.pct_customers_out.iloc[0] * 1000 / 900)


def test_storm_correlation_is_strong_on_comoving_data_with_a_bracketing_interval():
    r = step10.storm_comovement(step10.power_frame(panel(), lag=0), "pct_sites_out", draws=300, seed=1)
    assert r["value"] > 0.9 and r["ci_low"] <= r["value"] <= r["ci_high"] and r["n"] == 30
    assert r["n_counties"] == 30


def test_too_few_rows_give_no_correlation():
    r = step10.storm_comovement(step10.power_frame(panel(n=8), lag=0), "pct_sites_out", draws=50, seed=1)
    assert r["value"] is None and r["n"] == 8


def test_coverage_counts_are_attached():
    p = panel()
    p.loc[:9, "eaglei_coverage_flag"] = "low_coverage"
    r = step10.storm_comovement(step10.power_frame(p, lag=0), "pct_sites_out", draws=50, seed=1)
    assert r["coverage_counts"] == {"ok": 20, "low_coverage": 10}



def test_lag_sentence_is_generated_and_gives_no_mechanism():
    med = {"lag_0h": {"pct_sites_out": {"value": 0.61}}, "lag_6h": {"pct_sites_out": {"value": 0.62}},
           "lag_12h": {"pct_sites_out": {"value": 0.58}}, "lag_24h": {"pct_sites_out": {"value": 0.35}}}
    s = step10.lag_sentence(med)
    assert "0.62" in s and "0.35" in s and "6 hours" in s and "24 hours" in s
    for word in ("battery", "batteries", "generator", "fuel", "deplet", "because"):
        assert word not in s.lower()


def test_denominator_note_names_the_count_and_an_example():
    ex = {"county": "Henderson", "state": "North Carolina", "modeled": 24, "max_out": 71171, "households": 49494}
    s = step10.mcc_methods_note(230, 2106, ex)
    assert "230 of 2,106" in s and "Henderson County, North Carolina" in s and "24" in s and "71,171" in s
