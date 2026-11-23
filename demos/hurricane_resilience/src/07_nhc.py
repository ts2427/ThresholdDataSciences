"""Step 7: storm exposure from NHC.

* HURDAT2 (data/raw/nhc/hurdat2-1851-2025-092326.txt, from https://www.nhc.noaa.gov/data/) for every storm in
  manifest/storms.csv through 2025, by NHC ID. -999 is missing.
* Isaias 2026 (AL092026) is not in HURDAT2 yet: the NHC GIS best track (data/raw/nhc/al092026_best_track.zip),
  points plus the quadrant wind radii table. It has no landfall marker, so its landfall is left blank.
* Counties: Census 2020 Gazetteer internal points (INTPTLAT/INTPTLONG), for the counties in that storm's reports
  (row_nhc_id, so Nicholas counties in the shared Ida reports go with Nicholas).
* The track is interpolated linearly to one point every 15 minutes (position, wind and radii). For each county:
  minimum great-circle distance to the track and its time, wind at that point; inside the 34/50/64-kt radii if,
  at some track point, the county is no farther than that threshold's radius in the quadrant the county lies in;
  first time inside 34 kt; the landfall (HURDAT2 "L") nearest the county and its distance.
A county without a Gazetteer point fails (the U.S. Virgin Islands, which have none, are out of scope since
2026-11-22).
* Time origin (second correction, 2026-11-23): day 0 is the first time the storm's 34-kt wind radii reach any
  study-state county in its reports (the earliest first_34kt_utc above). Fallback for a storm whose 34-kt radii reach
  no county: its first HURDAT2 landfall in the study states at tropical-storm strength or above (status TS or HU; the
  landfall point within LANDFALL_IN_STATES_KM of a study-state county in the Census 2022 cartographic boundary file).
  The first 2026-11-23 rule (the earlier of that landfall and the closest approach to the counties) is kept as
  interim_origin_utc for comparison.
Outputs: data/interim/county_storm_exposure.parquet, data/interim/storm_time_origin.parquet.
"""
import io
import math
import zipfile

import numpy as np
import pandas as pd

from config import INTERIM, RAW, ROOT

HURDAT2 = RAW / "nhc" / "hurdat2-1851-2025-092326.txt"
ISAIAS_GIS = RAW / "nhc" / "al092026_best_track.zip"
GAZETTEER = RAW / "census" / "2020_Gaz_counties_national.zip"
BOUNDARIES = RAW / "census" / "cb_2022_us_county_500k.zip"
STUDY_STATE_FIPS = {"48", "22", "28", "01", "12", "13", "45", "37", "47", "51"}  # config.STUDY_STATES
LANDFALL_IN_STATES_KM = 25.0  # study-state landfalls lie within 9 km of a county; others are 180 km or more away
LANDFALL_STATUSES = {"TS", "HU"}
STORMS = ROOT / "manifest" / "storms.csv"
EARTH_KM = 6371.0
NM_KM = 1.852
QUADS = ("ne", "se", "sw", "nw")
RADII = [f"r{k}_{q}" for k in (34, 50, 64) for q in QUADS]
STEP = "15min"
NO_GAZETTEER_POINT: set[str] = set()  # was the U.S. Virgin Islands, now out of scope (step 5)


def _coord(tok: str) -> float:
    tok = tok.strip()
    v = float(tok[:-1])
    return -v if tok[-1] in "SW" else v


def parse_hurdat2(text: str) -> pd.DataFrame:
    out, storm, name = [], None, None
    for line in text.splitlines():
        f = [x.strip() for x in line.split(",")]
        if len(f) >= 3 and f[0][:2].isalpha() and len(f[0]) == 8:
            storm, name = f[0], f[1]
            continue
        if storm is None or len(f) < 20:
            continue
        rec = {"nhc_id": storm, "name": name,
               "time_utc": pd.Timestamp(f"{f[0]} {f[1][:2]}:{f[1][2:]}", tz="UTC"),
               "landfall": f[2] == "L", "status": f[3], "lat": _coord(f[4]), "lon": _coord(f[5]),
               "wind_kt": float(f[6])}
        for col, val in zip(RADII, f[8:20]):
            rec[col] = np.nan if val == "-999" else float(val)
        out.append(rec)
    t = pd.DataFrame(out)
    t["wind_kt"] = t.wind_kt.where(t.wind_kt >= 0)
    return t


def read_isaias_gis(path=ISAIAS_GIS) -> pd.DataFrame:
    import geopandas as gpd
    pts = gpd.read_file(f"zip://{path.as_posix()}!AL092026_pts.shp")
    radii = gpd.read_file(f"zip://{path.as_posix()}!AL092026_radii.shp")
    t = pd.DataFrame({"nhc_id": "AL092026", "name": "ISAIAS",
                      "time_utc": pd.to_datetime(pts.YEAR.astype(int).astype(str) + pts.MONTH.astype(str).str.zfill(2)
                                                 + pts.DAY.astype(int).astype(str).str.zfill(2) + pts.HHMM.astype(str).str.zfill(4),
                                                 format="%Y%m%d%H%M", utc=True),
                      "landfall": False, "status": pts.STORMTYPE, "lat": pts.LAT.astype(float),
                      "lon": pts.LON.astype(float), "wind_kt": pts.INTENSITY.astype(float)})
    radii["time_utc"] = pd.to_datetime(radii.SYNOPTIME.astype(str), format="%Y%m%d%H", utc=True)
    for k in (34, 50, 64):
        r = radii[radii.RADII == k].set_index("time_utc")[["NE", "SE", "SW", "NW"]].astype(float)
        r.columns = [f"r{k}_{q}" for q in QUADS]
        t = t.merge(r, left_on="time_utc", right_index=True, how="left")
    t[RADII] = t[RADII].fillna(0.0)  # no radius listed at a time = no winds of that strength
    t.attrs["landfall_note"] = "GIS best track has no landfall marker"
    return t


def read_county_points(path=GAZETTEER) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        g = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), sep="\t", dtype={"GEOID": str})
    g.columns = [c.strip() for c in g.columns]
    return pd.DataFrame({"fips": g.GEOID, "lat": g.INTPTLAT.astype(float), "lon": g.INTPTLONG.astype(float)})


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2, dl = np.radians(lat1), np.radians(lat2), np.radians(lon2 - lon1)
    y = np.sin(dl) * np.cos(p2)
    x = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dl)
    return (np.degrees(np.arctan2(y, x)) + 360) % 360


def destination(lat, lon, bearing, km):
    """Point at a bearing and distance (for tests)."""
    d, b, p1, l1 = km / EARTH_KM, math.radians(bearing), math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), math.degrees(l2)


def interpolate(track: pd.DataFrame) -> pd.DataFrame:
    t = track.sort_values("time_utc").drop_duplicates("time_utc").set_index("time_utc")
    cols = ["lat", "lon", "wind_kt", *RADII]
    grid = pd.date_range(t.index.min().ceil(STEP), t.index.max(), freq=STEP)
    full = t[cols].reindex(t.index.union(grid))
    full = full.interpolate(method="time", limit_area="inside")
    return full.loc[full.index.isin(grid) | full.index.isin(t.index)].reset_index(names="time_utc")


def exposure(track: pd.DataFrame, points: pd.DataFrame) -> pd.DataFrame:
    t = interpolate(track)
    lat, lon = t.lat.to_numpy()[None, :], t.lon.to_numpy()[None, :]
    plat, plon = points.lat.to_numpy()[:, None], points.lon.to_numpy()[:, None]
    dist = haversine_km(lat, lon, plat, plon)  # counties x track points
    quad = (bearing_deg(lat, lon, plat, plon) // 90).astype(int)  # 0 NE, 1 SE, 2 SW, 3 NW
    i = dist.argmin(axis=1)
    out = pd.DataFrame({"fips": points.fips.to_numpy(), "min_dist_km": dist.min(axis=1),
                        "closest_utc": t.time_utc.to_numpy()[i], "wind_kt_at_closest": t.wind_kt.to_numpy()[i]})
    for k in (34, 50, 64):
        r = np.stack([t[f"r{k}_{q}"].to_numpy() for q in QUADS])  # quadrants x track points
        radius_km = np.take_along_axis(np.broadcast_to(r[None], (len(points), 4, len(t))),
                                       quad[:, None, :], axis=1)[:, 0, :] * NM_KM
        inside = dist <= np.nan_to_num(radius_km, nan=-1)
        out[f"in_{k}kt"] = inside.any(axis=1)
        if k == 34:
            first = np.where(inside.any(axis=1), inside.argmax(axis=1), -1)
            out["first_34kt_utc"] = [t.time_utc.iloc[j] if j >= 0 else pd.NaT for j in first]
    lf = track[track.landfall]
    if len(lf):
        d = haversine_km(lf.lat.to_numpy()[None, :], lf.lon.to_numpy()[None, :], plat, plon)
        j = d.argmin(axis=1)
        out["nearest_landfall_utc"] = lf.time_utc.to_numpy()[j]
        out["nearest_landfall_km"] = d.min(axis=1)
    else:
        out["nearest_landfall_utc"], out["nearest_landfall_km"] = pd.NaT, np.nan
    out["closest_utc"] = pd.to_datetime(out.closest_utc, utc=True)
    out["nearest_landfall_utc"] = pd.to_datetime(out.nearest_landfall_utc, utc=True)
    return out


def study_state_shapes(path=BOUNDARIES):
    import geopandas as gpd
    g = gpd.read_file(f"zip://{path.as_posix()}")
    return g[g.STATEFP.isin(STUDY_STATE_FIPS)].to_crs(5070)


def landfalls_in_states(track: pd.DataFrame, shapes) -> pd.DataFrame:
    """The track's landfalls at tropical-storm strength or above that lie in the study states, with the state."""
    import geopandas as gpd
    lf = track[track.landfall & track.status.isin(LANDFALL_STATUSES)]
    if lf.empty:
        return lf.assign(state="", km=np.nan)
    pts = gpd.GeoSeries(gpd.points_from_xy(lf.lon, lf.lat), crs=4326).to_crs(5070)
    near = [shapes.distance(p) for p in pts]
    km = np.array([d.min() / 1000 for d in near])
    state = [shapes.loc[d.idxmin(), "STUSPS"] for d in near]
    out = lf.assign(state=state, km=km)
    return out[out.km <= LANDFALL_IN_STATES_KM]


def time_origin(nhc_id: str, track: pd.DataFrame, e: pd.DataFrame, shapes) -> dict:
    """Day 0: the first time 34-kt winds reach a study-state county; fallback, the first study-state landfall (TS or
    HU). Also the interim rule (earlier of that landfall and the closest approach), kept for comparison."""
    lf = landfalls_in_states(track, shapes).sort_values("time_utc")
    e = e.dropna(subset=["min_dist_km"])
    c = e.loc[e.min_dist_km.idxmin()]
    rec = {"nhc_id": nhc_id, "first_study_landfall_utc": lf.time_utc.iloc[0] if len(lf) else pd.NaT,
           "first_study_landfall_state": lf.state.iloc[0] if len(lf) else "",
           "closest_approach_utc": c.closest_utc, "closest_approach_km": float(c.min_dist_km),
           "closest_approach_fips": c.fips}
    if len(lf) and rec["first_study_landfall_utc"] <= rec["closest_approach_utc"]:
        rec.update(interim_origin_utc=rec["first_study_landfall_utc"],
                   interim_origin_source=f"first study-state landfall ({rec['first_study_landfall_state']})")
    else:
        rec.update(interim_origin_utc=rec["closest_approach_utc"],
                   interim_origin_source="closest approach to the study-state counties")
    w = e.dropna(subset=["first_34kt_utc"]) if "first_34kt_utc" in e else e.iloc[0:0]
    if len(w):
        k = w.first_34kt_utc.idxmin()
        rec.update(first_34kt_utc=w.loc[k, "first_34kt_utc"], first_34kt_fips=w.loc[k, "fips"],
                   time_origin_utc=w.loc[k, "first_34kt_utc"],
                   time_origin_source="34-kt winds first reach a study-state county", fallback=False)
    elif len(lf):
        rec.update(first_34kt_utc=pd.NaT, first_34kt_fips="", time_origin_utc=rec["first_study_landfall_utc"],
                   time_origin_source=f"fallback: first study-state landfall ({rec['first_study_landfall_state']})",
                   fallback=True)
    else:
        raise ValueError(f"{nhc_id}: no 34-kt radii reach a county and no study-state landfall")
    return rec


def main():
    tracks = parse_hurdat2(HURDAT2.read_text(encoding="utf-8"))
    tracks = pd.concat([tracks, read_isaias_gis()], ignore_index=True)
    storms = pd.read_csv(STORMS)
    rows = pd.read_parquet(INTERIM / "dirs_county_rows_fips.parquet", columns=["row_nhc_id", "fips"])
    pts = read_county_points()
    out, lines, origins = [], [], []
    shapes = study_state_shapes()
    for s in storms.itertuples():
        counties = sorted(set(rows[rows.row_nhc_id == s.nhc_id].fips))
        track = tracks[tracks.nhc_id == s.nhc_id]
        if not counties:
            lines.append(f"{s.storm_name} {s.nhc_id}: no county rows")
            continue
        if track.empty:
            raise SystemExit(f"no track for {s.nhc_id}")
        p = pts[pts.fips.isin(counties)]
        missing = set(counties) - set(p.fips)
        if missing - NO_GAZETTEER_POINT:
            raise SystemExit(f"no Gazetteer point for {sorted(missing - NO_GAZETTEER_POINT)}")
        e = exposure(track, p)
        e = pd.concat([e, pd.DataFrame({"fips": sorted(missing), "exposure_note": "no Census Gazetteer point"})],
                      ignore_index=True)
        e = e.assign(nhc_id=s.nhc_id, storm_name=s.storm_name,
                                      track_source="GIS best track" if s.nhc_id == "AL092026" else "HURDAT2")
        out.append(e)
        origins.append(time_origin(s.nhc_id, track, e, shapes))
        lines.append(f"{s.storm_name:9} {s.nhc_id}: {len(e):4} counties, track points {len(track):3}, "
                     f"in 34 kt {int(e.in_34kt.sum()):4}, 64 kt {int(e.in_64kt.sum()):3}, "
                     f"median distance {e.min_dist_km.median():5.0f} km, landfalls {int(track.landfall.sum())}")
    res = pd.concat(out, ignore_index=True)
    res.to_parquet(INTERIM / "county_storm_exposure.parquet", index=False)
    org = pd.DataFrame(origins)
    for col in ("first_study_landfall_utc", "closest_approach_utc", "interim_origin_utc", "first_34kt_utc",
                "time_origin_utc"):
        org[col] = pd.to_datetime(org[col], utc=True)
    org.to_parquet(INTERIM / "storm_time_origin.parquet", index=False)
    for o in org.itertuples():
        lines.append(f"day 0 {o.nhc_id}: {o.time_origin_utc:%Y-%m-%d %H:%M} UTC, {o.time_origin_source}")
    print("\n".join(lines))
    print(f"{len(res)} storm-county rows")


if __name__ == "__main__":
    main()
