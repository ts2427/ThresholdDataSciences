"""Demo B step 3a: exact and same-incident duplicate rows.

Rule (proposed and approved 2026-11-19; applied after hand review by
osha_audit/src/dedupe_apply.py; see docs/decisions.md):

Two rows describe the SAME INCIDENT if they share
  1. the event date and state,
  2. the location: the same normalized street address OR the same 5-digit
     ZIP code, and
  3. the same injury: at least 3 of the 4 OIICS injury codes equal (Nature,
     Part of Body, Event, Source) OR narrative similarity >= 80
     (rapidfuzz token_set_ratio).

A same-incident pair is a SAME-EMPLOYER DUPLICATE — the same report filed
twice — if the two employer names are also similar (token_set_ratio >= 70
on lowercased alphanumerics). One row per duplicate cluster is kept (the
lowest UPA, OSHA's unique report number, carrying the higher injury
counts); the others are removed.

A same-incident pair with DIFFERENT employers (a staffing agency and its
host, a contractor and the site owner) is two employers' reports of one
incident: both rows are kept, because the unit counted is reports filed,
and the pair is flagged.
"""
import re

import pandas as pd
from rapidfuzz import fuzz

CODES = ["Nature", "Part of Body", "Event", "Source"]
CODES_MIN, NARR_MIN, EMP_MIN = 3, 80, 70


def norm_text(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def candidate_pairs(df):
    """Index pairs (i, j), i < j, with the same date and state and the same
    normalized address or ZIP5."""
    addr = df["Address1"].map(norm_text)
    zip5 = df["Zip"].astype(str).str[:5]
    out = []
    for _, g in df.groupby(["EventDate", "State"], sort=False):
        if len(g) < 2:
            continue
        idx = list(g.index)
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                if addr[i] == addr[j] or (zip5[i] and zip5[i] == zip5[j]):
                    out.append((i, j))
    return out


def score_pair(r1, r2):
    return {
        "codes_equal": int(sum(r1[c] == r2[c] for c in CODES)),
        "narr_sim": float(fuzz.token_set_ratio(r1["Final Narrative"], r2["Final Narrative"])),
        "emp_sim": float(fuzz.token_set_ratio(norm_text(r1["Employer"]), norm_text(r2["Employer"]))),
    }


def classify(s):
    """'same_employer_duplicate', 'cross_employer_same_incident' or None."""
    same_incident = s["codes_equal"] >= CODES_MIN or s["narr_sim"] >= NARR_MIN
    if not same_incident:
        return None
    return "same_employer_duplicate" if s["emp_sim"] >= EMP_MIN else "cross_employer_same_incident"


def clusters(pairs, n_hint=None):
    """Union-find over index pairs -> list of sets (size >= 2)."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in pairs:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri
    groups = {}
    for x in parent:
        groups.setdefault(find(x), set()).add(x)
    return [g for g in groups.values() if len(g) > 1]


def plan_removals(df):
    """Return (scored pairs DataFrame, set of row indices to remove). Does
    not modify df."""
    rows = []
    for i, j in candidate_pairs(df):
        s = score_pair(df.loc[i], df.loc[j])
        rows.append({"i": i, "j": j, **s, "class": classify(s)})
    pairs = pd.DataFrame(rows, columns=["i", "j", "codes_equal", "narr_sim", "emp_sim", "class"])
    dup = pairs[pairs["class"] == "same_employer_duplicate"]
    remove = set()
    for c in clusters(list(zip(dup.i, dup.j))):
        keep = min(c, key=lambda k: int(df.loc[k, "UPA"]))
        remove |= c - {keep}
    return pairs, remove
