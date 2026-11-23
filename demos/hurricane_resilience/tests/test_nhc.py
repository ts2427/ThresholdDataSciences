"""Step 7: HURDAT2 parser on a known storm, and the exposure measures."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step7 = importlib.import_module("07_nhc")

HELENE = """AL092024,             HELENE,      3,
20240926, 1800,  , HU, 26.9N,  84.6W, 115,  942,  240,  270,  150,  140,  100,  110,   60,   50,   60,   70,   35,   35,   20
20240927, 0310, L, HU, 30.0N,  83.7W, 120,  939,  240,  270,  150,  140,  100,  110,   60,   50,   60,   70,   35,   35,   20
20240927, 0600,  , HU, 31.1N,  83.5W,  85,  950,  210,  250,  130,  120,   90,  100,   40,   40,   40,   50,   30,   30,  -999
AL012024,              ALBERTO,      1,
20240620, 0000,  , TS, 22.2N,  96.0W,  40,  992,  240,  250,   90,  -999,    0,    0,    0,    0,    0,    0,    0,    0,  -999
"""


def test_hurdat2_parser_on_helene():
    t = step7.parse_hurdat2(HELENE)
    h = t[t.nhc_id == "AL092024"]
    assert len(h) == 3 and h.name.iloc[0] == "HELENE"
    lf = h[h.landfall]
    assert lf.time_utc.tolist() == [pd.Timestamp("2024-09-27 03:10", tz="UTC")]
    assert (lf.lat.iloc[0], lf.lon.iloc[0], lf.wind_kt.iloc[0]) == (30.0, -83.7, 120)
    assert (lf.r34_ne.iloc[0], lf.r64_nw.iloc[0]) == (240, 35)
    assert pd.isna(t[t.nhc_id == "AL012024"].r34_nw.iloc[0])  # -999 is missing, not a radius


@pytest.mark.skipif(not step7.HURDAT2.exists(), reason="needs the downloaded HURDAT2 file (data, not committed)")
def test_real_file_has_every_storm_through_2025():
    t = step7.parse_hurdat2(step7.HURDAT2.read_text(encoding="utf-8"))
    h = t[(t.nhc_id == "AL092024") & t.landfall]
    assert pd.Timestamp("2024-09-27 03:10", tz="UTC") in set(h.time_utc)
    storms = pd.read_csv(step7.STORMS)
    assert set(storms.nhc_id) - set(t.nhc_id) == {"AL092026"}


def test_distance_and_wind_at_closest_point():
    track = step7.parse_hurdat2(HELENE)
    track = track[track.nhc_id == "AL092024"]
    pts = pd.DataFrame({"fips": ["12123"], "lat": [30.0], "lon": [-83.7]})  # on the landfall point
    e = step7.exposure(track, pts).iloc[0]
    assert e.min_dist_km == pytest.approx(0, abs=0.5) and e.wind_kt_at_closest == pytest.approx(120, abs=1)
    assert e.in_64kt and e.nearest_landfall_utc == pd.Timestamp("2024-09-27 03:10", tz="UTC")


def test_wind_radii_use_the_quadrant_the_county_is_in():
    track = pd.DataFrame([{"nhc_id": "X", "time_utc": pd.Timestamp("2024-01-01", tz="UTC"), "lat": 30.0, "lon": -85.0,
                           "wind_kt": 100, "landfall": False,
                           **{f"r{k}_{q}": 0 for k in (34, 50, 64) for q in ("ne", "se", "sw", "nw")},
                           "r34_ne": 100}])  # 100 nm to the northeast only
    near_ne = step7.destination(30.0, -85.0, 45, 150)  # 150 km = 81 nm, inside 100 nm
    near_sw = step7.destination(30.0, -85.0, 225, 150)
    pts = pd.DataFrame({"fips": ["ne", "sw"], "lat": [near_ne[0], near_sw[0]], "lon": [near_ne[1], near_sw[1]]})
    e = step7.exposure(track, pts).set_index("fips")
    assert e.loc["ne", "in_34kt"] and not e.loc["sw", "in_34kt"]


def test_track_is_interpolated_between_fixes():
    track = step7.parse_hurdat2(HELENE)
    track = track[track.nhc_id == "AL092024"]
    mid = ((26.9 + 30.0) / 2, (-84.6 - 83.7) / 2)  # halfway between 18 UTC and the 03:10 landfall
    e = step7.exposure(track, pd.DataFrame({"fips": ["m"], "lat": [mid[0]], "lon": [mid[1]]})).iloc[0]
    assert e.min_dist_km < 10


def _shapes():
    import geopandas as gpd
    from shapely.geometry import box
    return gpd.GeoDataFrame({"STUSPS": ["FL"]}, geometry=[box(-87.0, 25.0, -80.0, 31.0)], crs=4326).to_crs(5070)


def _track(rows):
    return pd.DataFrame([{"time_utc": pd.Timestamp(t, tz="UTC"), "landfall": lf, "status": st, "lat": la, "lon": lo}
                         for t, lf, st, la, lo in rows])


def test_fallback_counts_only_study_state_landfalls_at_tropical_storm_strength():
    tr = _track([("2020-09-10 00:00", True, "HU", 22.3, -83.3),   # Cuba: outside the study states
                 ("2020-09-12 06:00", True, "TD", 25.6, -80.2),   # depression: not counted
                 ("2020-09-16 09:45", True, "HU", 30.3, -86.0)])  # in the state
    e = pd.DataFrame({"fips": ["12001"], "min_dist_km": [5.0], "closest_utc": [pd.Timestamp("2020-09-16 18:00", tz="UTC")],
                      "first_34kt_utc": [pd.NaT]})                # no 34-kt radii reach the county: fallback
    got = step7.time_origin("X", tr, e, _shapes())
    assert got["time_origin_utc"] == pd.Timestamp("2020-09-16 09:45", tz="UTC") and got["fallback"]
    assert got["time_origin_source"] == "fallback: first study-state landfall (FL)"


def test_day0_is_the_first_34kt_arrival_at_any_county():
    tr = _track([("2019-09-06 12:30", True, "HU", 30.0, -84.0)])
    e = pd.DataFrame({"fips": ["12001", "37003"], "min_dist_km": [150.0, 36.0],
                      "closest_utc": [pd.Timestamp("2019-09-04 07:00", tz="UTC"), pd.Timestamp("2019-09-06 09:15", tz="UTC")],
                      "first_34kt_utc": [pd.Timestamp("2019-09-02 21:15", tz="UTC"), pd.Timestamp("2019-09-05 20:00", tz="UTC")]})
    got = step7.time_origin("X", tr, e, _shapes())
    assert got["time_origin_utc"] == pd.Timestamp("2019-09-02 21:15", tz="UTC") and not got["fallback"]
    assert got["time_origin_source"] == "34-kt winds first reach a study-state county" and got["first_34kt_fips"] == "12001"
    # the interim rule (earlier of study-state landfall and closest approach) is kept for comparison
    assert got["interim_origin_utc"] == pd.Timestamp("2019-09-06 09:15", tz="UTC")
