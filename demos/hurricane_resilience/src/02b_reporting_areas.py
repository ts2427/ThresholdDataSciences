"""Step 2b: each storm's DIRS reporting area over time, from the FCC's own notices.

Reads every notice that step 2 saved in data/raw/notices/ (see notices.py) and writes:
  * manifest/reporting_areas.csv: one row per county per spell in a storm's area: added on/by, removed on/by,
    and every spelling the FCC used for it
  * manifest/storm_states.csv: when reporting began and ended in each state, per storm page
  * manifest/shared_report_counties.csv: for a notice that brings a second storm into an existing activation
    (Nicholas, DA-21-1152A1), which counties belong to the second storm and which stay with the first (flagged)
  * manifest/storms.csv: adds the second storm's own key and each storm's area-change notices
Notice dates are release dates. A notice released on a report's date takes effect after that day's report
(docs/decisions.md, 2026-11-22): the FCC's final report is issued on the day of the deactivation notice and
still lists the counties that notice releases.

Area status of a county row (step 3): table_not_in_list (in the report's table, not in its own county list),
otherwise inside, inside_spelling_variant (an FCC spelling at least 90% alike) or outside_notice_area.
"""
from __future__ import annotations

import difflib
import re
import sys

import pandas as pd

from config import RAW, ROOT
from notices import Op, read_notice

MANIFEST_DIR = ROOT / "manifest"
DOCUMENT_LIST = MANIFEST_DIR / "fcc_storm_documents.csv"
STORMS = MANIFEST_DIR / "storms.csv"
NOTICE_KINDS = ("activation", "area_change", "deactivation")
DIRS_TITLE = r"DIRS|Disaster"
SPELLING_CUTOFF = 0.9  # "Point Coupee" ~ "Pointe Coupee"; "East" vs "West Feliciana" stays apart (0.85)

# A notice that brings a second storm into an existing activation (author's decision, 2026-11-22)
SECOND_STORMS = {
    "DA-21-1152A1": {"storm_page": "ida", "storm_name": "Nicholas", "nhc_id": "AL142021",
                     "first_storm": "Ida", "first_nhc_id": "AL092021", "applies_from": "2021-09-15"},
}


ORDER = {"end": 0, "remove": 1, "remain": 2, "add": 3}  # within one notice; a restated area must not undo additions


def name_key(name) -> str:
    """Case, punctuation and a trailing "County" or "Parish" don't matter."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s+(county|parish)\s*$", "", str(name).lower().strip()))


def closest(key: str, keys) -> str | None:
    if key in keys:
        return key
    near = difflib.get_close_matches(key, list(keys), n=1, cutoff=SPELLING_CUTOFF)
    return near[0] if near else None


def build_intervals(notices: list[dict]) -> pd.DataFrame:
    """notices: dicts with date, doc_id and ops, for one storm page."""
    active, closed = {}, []

    def close(k, date, doc):
        if k not in active:  # already closed: the FCC sometimes names a county twice in one list
            return
        rec = active.pop(k)
        closed.append({**rec, "removed_on": date, "removed_by": doc})

    for n in sorted(notices, key=lambda n: (n["date"], n["doc_id"])):
        date, doc = n["date"], n["doc_id"]
        for op in sorted(n["ops"], key=lambda o: ORDER[o.action]):
            in_state = {k[1] for k in active if k[0] == op.state}
            if op.action == "end":
                for k in [k for k in active if op.state in ("*", k[0])]:
                    close(k, date, doc)
                continue
            found = []
            for name in op.counties:
                key = name_key(name)
                match = closest(key, in_state)
                if match:
                    active[(op.state, match)]["spellings"].add(name)
                found.append((name, key, match))
            if op.action == "add":
                for name, key, match in found:
                    if not match and (op.state, key) not in active:
                        active[(op.state, key)] = {"state": op.state, "county": name, "key": key,
                                                   "spellings": {name}, "added_on": date, "added_by": doc}
            elif op.action == "remove":
                for name, key, match in found:
                    if match:
                        close((op.state, match), date, doc)
            elif op.action == "remain":
                keep = {match or key for _, key, match in found}
                for k in [k for k in active if k[0] == op.state and k[1] not in keep]:
                    close(k, date, doc)
                for name, key, match in found:
                    if not match and (op.state, key) not in active:
                        active[(op.state, key)] = {"state": op.state, "county": name, "key": key,
                                                   "spellings": {name}, "added_on": date, "added_by": doc}
    rows = closed + [{**rec, "removed_on": pd.NaT, "removed_by": ""} for rec in active.values()]
    out = pd.DataFrame(rows, columns=["state", "county", "key", "spellings", "added_on", "added_by", "removed_on",
                                      "removed_by"])
    out["spellings"] = out.spellings.map(lambda s: "; ".join(sorted(s)))
    return out.sort_values(["state", "key", "added_on"]).reset_index(drop=True)


def area_on(intervals: pd.DataFrame, date: pd.Timestamp) -> tuple[set, set]:
    """(area before that day's notices, area after them)."""
    removed = intervals.removed_on
    before = intervals[(intervals.added_on < date) & (removed.isna() | (removed >= date))]
    through = intervals[(intervals.added_on <= date) & (removed.isna() | (removed > date))]
    return set(zip(before.state, before.key)), set(zip(through.state, through.key))


AREA_STATUSES = ("inside", "inside_spelling_variant", "outside_notice_area", "table_not_in_list")


def area_statuses(rows: pd.DataFrame, intervals: pd.DataFrame, lists: pd.DataFrame) -> pd.DataFrame:
    """rows: doc_id, report_date, state, county (one storm page). lists: each report's own county list."""
    listed = {}
    for d, s, c in zip(lists.doc_id, lists.state, lists.county):
        listed.setdefault((d, s), set()).add(name_key(c))
    areas, statuses = {}, []
    for r in rows.itertuples():
        if not closest(name_key(r.county), listed.get((r.doc_id, r.state), set())):
            statuses.append("table_not_in_list")
            continue
        date = pd.Timestamp(r.report_date)
        if date not in areas:
            areas[date] = area_on(intervals, date)[0]  # notices released before the report's date
        keys = {k for s, k in areas[date] if s == r.state}
        key = name_key(r.county)
        statuses.append("inside" if key in keys else "inside_spelling_variant" if closest(key, keys)
                        else "outside_notice_area")
    return rows.assign(area_status=statuses)


def state_starts(intervals: pd.DataFrame) -> pd.DataFrame:
    out = []
    for state, g in intervals.groupby("state"):
        first = g.sort_values(["added_on", "added_by"]).iloc[0]
        ended = g.removed_on.max() if g.removed_on.notna().all() else pd.NaT
        last = g[g.removed_on == ended].removed_by.min() if pd.notna(ended) else ""
        out.append({"state": state, "reporting_began": first.added_on, "began_notice": first.added_by,
                    "reporting_ended": ended, "ended_notice": last})
    return pd.DataFrame(out)


def shared_storm_counties(notices: list[dict], doc_id: str) -> pd.DataFrame:
    """Counties named by a second storm's notice: new ones go to it; ones already in the area stay, flagged."""
    ordered = sorted(notices, key=lambda n: (n["date"], n["doc_id"]))
    at = next(i for i, n in enumerate(ordered) if n["doc_id"] == doc_id)
    prior = build_intervals(ordered[:at])
    prior = prior[prior.removed_on.isna()]
    out = []
    for op in ordered[at]["ops"]:
        keys = set(prior[prior.state == op.state].key)
        for name in op.counties:
            stays = closest(name_key(name), keys) is not None
            out.append({"state": op.state, "county": name, "assigned_to": "first storm" if stays else "second storm",
                        "flag": "also named by the second storm's notice; kept with the first storm" if stays else ""})
    return pd.DataFrame(out)


def load_notices() -> dict[str, list[dict]]:
    docs = pd.read_csv(DOCUMENT_LIST, dtype=str, keep_default_na=False)
    pages = set(pd.read_csv(STORMS, dtype=str).storm_page)
    keep = docs[docs.storm_page.isin(pages) & docs.kind.isin(NOTICE_KINDS)
                & docs.title.str.contains(DIRS_TITLE, regex=True)]
    by_page, unread = {}, []
    for d in keep.itertuples():
        path = RAW / "notices" / f"{d.doc_id}.txt"
        if not path.exists():
            raise SystemExit(f"notice not downloaded: {d.doc_id} (run step 2)")
        notice = read_notice(path.read_text(encoding="utf-8-sig", errors="replace"), d.kind, d.title)
        if notice.unread:
            unread.append(f"{d.storm_page} {d.released} {d.doc_id} [{d.kind}] {d.title}")
        by_page.setdefault(d.storm_page, []).append(
            {"date": pd.Timestamp(d.released), "doc_id": d.doc_id, "kind": d.kind, "ops": notice.ops})
    return by_page, unread


def main():
    by_page, unread = load_notices()
    storms = pd.read_csv(STORMS, dtype=str, keep_default_na=False)
    areas, starts, shared = [], [], []
    for page, notices in sorted(by_page.items()):
        iv = build_intervals(notices)
        areas.append(iv.assign(storm_page=page))
        starts.append(state_starts(iv).assign(storm_page=page))
    for doc, second in SECOND_STORMS.items():
        got = shared_storm_counties(by_page[second["storm_page"]], doc)
        names = {"first storm": (second["first_storm"], second["first_nhc_id"]),
                 "second storm": (second["storm_name"], second["nhc_id"])}
        shared.append(got.assign(notice=doc, storm_page=second["storm_page"], applies_from=second["applies_from"],
                                 assigned_storm=got.assigned_to.map(lambda a: names[a][0]),
                                 assigned_nhc_id=got.assigned_to.map(lambda a: names[a][1])))
        if second["storm_name"] not in set(storms.storm_name):
            row = {c: "" for c in storms.columns}
            row.update(storm_name=second["storm_name"], nhc_id=second["nhc_id"], storm_page=second["storm_page"],
                       dirs_activation_date=pd.Timestamp(
                           next(n["date"] for n in by_page[second["storm_page"]] if n["doc_id"] == doc)).date().isoformat(),
                       activation_doc=doc, notes=f"brought into the {second['first_storm']} activation by {doc}; "
                                                  f"shares {second['first_storm']}'s reports and deactivation")
            first = storms[storms.storm_name == second["first_storm"]].iloc[0]
            for col in ("dirs_deactivation_date", "deactivation_doc", "deactivation_title"):
                row[col] = first[col]
            storms = pd.concat([storms, pd.DataFrame([row])], ignore_index=True)
    changes = {page: "; ".join(f"{n['date'].date()} {n['doc_id']}" for n in sorted(ns, key=lambda n: (n["date"], n["doc_id"]))
                               if n["kind"] == "area_change") for page, ns in by_page.items()}
    storms["area_changes"] = storms.storm_page.map(changes).fillna("")
    storms.loc[storms.storm_name.isin([s["storm_name"] for s in SECOND_STORMS.values()]), "area_changes"] = ""

    fmt = lambda df: df.assign(**{c: pd.to_datetime(df[c]).dt.date.astype("string") for c in df.columns
                                  if c.endswith(("_on", "_began", "_ended"))})
    cols = ["storm_page", "state", "county", "spellings", "added_on", "added_by", "removed_on", "removed_by"]
    fmt(pd.concat(areas))[cols].to_csv(MANIFEST_DIR / "reporting_areas.csv", index=False, lineterminator="\n")
    fmt(pd.concat(starts))[["storm_page", "state", "reporting_began", "began_notice", "reporting_ended",
                            "ended_notice"]].to_csv(MANIFEST_DIR / "storm_states.csv", index=False, lineterminator="\n")
    pd.concat(shared)[["notice", "storm_page", "applies_from", "state", "county", "assigned_storm", "assigned_nhc_id",
                       "flag"]].to_csv(MANIFEST_DIR / "shared_report_counties.csv", index=False, lineterminator="\n")
    storms.to_csv(STORMS, index=False, lineterminator="\n")
    print(f"{sum(len(v) for v in by_page.values())} notices on {len(by_page)} storm pages; "
          f"{sum(len(a) for a in areas)} county spells")
    if unread:
        print("notices with no readable county list:")
        for u in unread:
            print("  ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
