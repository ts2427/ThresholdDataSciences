"""Step 10, chapter 7 (exposure): helpers."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step10 = importlib.import_module("10_analysis")


def test_county_peak_is_taken_at_the_countys_own_peak_report():
    p = pd.DataFrame({"storm_key": "K", "storm": "K", "fips": ["a", "a", "b", "b"], "doc_id": ["D1", "D2", "D1", "D2"],
                      "sites_served": [100, 80, 50, 50], "sites_out": [10, 40, 5, 1], "min_dist_km": [10.0] * 2 + [90.0] * 2,
                      "wind_kt_at_closest": 100.0, "in_34kt": True, "in_50kt": [True, True, False, False],
                      "in_64kt": False, "report_status": "ok", "report_flags": ""})
    c = step10.county_peaks(p).set_index("fips")
    assert (c.loc["a", "peak_out"], c.loc["a", "peak_served"]) == (40, 80)  # 50% beats 10%
    assert c.loc["b", "zone"] == "34-50 kt" and c.loc["a", "zone"] == "50-64 kt"


@pytest.mark.parametrize("r34, r50, r64, zone", [(True, True, True, "inside 64 kt"), (True, True, False, "50-64 kt"),
                                                 (True, False, False, "34-50 kt"), (False, False, False, "outside 34 kt")])
def test_wind_zone(r34, r50, r64, zone):
    assert step10.wind_zone(r34, r50, r64) == zone


def simulated(n_storms=12, per=60, seed=0):
    """Counties whose true log-odds of a site being out fall with distance and rise with wind and zone."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_storms):
        for i in range(per):
            dist = rng.uniform(0, 400)
            wind = rng.uniform(40, 140)
            zone = rng.choice(["inside 64 kt", "50-64 kt", "34-50 kt", "outside 34 kt"])
            eta = -2.0 - 0.5 * np.log1p(dist) + 0.3 * wind / 10 + {"inside 64 kt": 1.0, "50-64 kt": 0.6,
                                                                    "34-50 kt": 0.3, "outside 34 kt": 0.0}[zone]
            n = int(rng.integers(20, 300))
            rows.append({"storm_key": f"S{s}", "storm": f"S{s}", "fips": f"{s}-{i}", "min_dist_km": dist,
                         "wind_kt_at_closest": wind, "zone": zone, "peak_served": n,
                         "peak_out": rng.binomial(n, 1 / (1 + np.exp(-eta)))})
    return pd.DataFrame(rows)


def test_model_recovers_known_coefficients():
    fit = step10.fit_exposure_model(simulated())
    assert fit.params["log1p_dist_km"] == pytest.approx(-0.5, abs=0.1)
    assert fit.params["wind_per_10kt"] == pytest.approx(0.3, abs=0.06)
    assert fit.params["zone_inside 64 kt"] == pytest.approx(1.0, abs=0.25)


def test_held_out_predictions_never_use_the_held_out_storm():
    c = simulated(n_storms=4, per=30)
    pred = step10.leave_one_storm_out(c)
    assert len(pred) == len(c) and pred.between(0, 1).all()
    # changing a held-out storm's outcomes does not change its own predictions
    c2 = c.copy()
    c2.loc[c2.storm_key == "S0", "peak_out"] = 0
    assert np.allclose(step10.leave_one_storm_out(c2)[c.storm_key == "S0"], pred[c.storm_key == "S0"])


def test_calibration_of_a_well_specified_model_is_near_ideal():
    c = simulated(n_storms=12, per=80, seed=2)
    cal = step10.calibration(c, step10.leave_one_storm_out(c))
    assert cal["slope"]["value"] == pytest.approx(1.0, abs=0.15)
    assert cal["in_the_large"]["value"] == pytest.approx(0.0, abs=0.15)
    assert len(cal["deciles"]) == 10 and sum(d["n"] for d in cal["deciles"]) == len(c)


def test_calibration_detects_overconfident_predictions():
    c = simulated(n_storms=10, per=80, seed=3)
    p = step10.leave_one_storm_out(c)
    logit = np.log(p / (1 - p))
    too_steep = 1 / (1 + np.exp(-(2 * logit - logit.mean())))
    assert step10.calibration(c, too_steep)["slope"]["value"] < 0.7


def test_band_shares_are_site_weighted_with_counts():
    c = pd.DataFrame({"storm_key": ["A", "A", "B"], "min_dist_km": [10.0, 30.0, 150.0], "peak_out": [10, 30, 5],
                      "peak_served": [100, 100, 100], "zone": ["inside 64 kt"] * 3})
    got = step10.band_shares(c, "dist_band", draws=50, seed=0)
    assert got["0-50 km"]["value"] == pytest.approx(20.0) and got["0-50 km"]["n"] == 2
    assert got["100-200 km"]["value"] == pytest.approx(5.0)



def test_storm_misses_note_names_unmeasured_factors_as_possibilities_only():
    storms = [{"storm": "Ida", "observed_pct": 28.4, "predicted_pct_held_out": 9.1},
              {"storm": "Nicole", "observed_pct": 1.2, "predicted_pct_held_out": 10.0},
              {"storm": "Sally", "observed_pct": 12.9, "predicted_pct_held_out": 11.7}]
    s = step10.storm_misses_note(storms, min_gap=5.0)
    assert "Ida (28.4% observed, 9.1% predicted)" in s and "Nicole" in s and "Sally" not in s
    assert "flooding, road access and fiber cuts" in s.lower() and "possible" in s
    for word in ("because", "explain", "caused", "due to"):
        assert word not in s.lower()


def test_page_layout_leads_with_the_wind_zone_table():
    lay = step10.CH7_PAGE_LAYOUT
    assert lay["lead_exhibit"] == "by_wind_zone"
    assert {"headlines.odds_ratios", "headlines.calibration_held_out"} <= set(lay["methods"])
