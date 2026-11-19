r"""Demo B step 3c (PROPOSED — preview only until Tim approves): fuzzy entity
resolution on the step-3b employers.

Unit: step-3b employers ("entities"), compared on their normalized names.

Blocking
  C1  within state: two employers are compared only if they filed reports
      in a common state.
  C2  across states: allowed only when at least one side is plausibly
      multi-state — present in >= MULTI_STATES (5) states.
  C3  national-employer aliases (acronyms such as USPS / UPS, and
      store-format names such as "Walmart Supercenter"): NOT automatic. A
      candidate list is derived from the data for employers in >= 10 states
      and shown to Tim; only approved links are used.

Match rule (C1 and C2)
  - overall: rapidfuzz token_sort_ratio(name_a, name_b) >= OVERALL (92), and
  - distinctive part: the names with GENERIC tokens removed must also agree,
    ratio >= DISTINCT (85). Generic tokens are derived from the data: words
    that appear in >= GENERIC_MIN (150) employer names (e.g. construction,
    services, industries). If either distinctive part is shorter than 4
    characters, the distinctive parts must be identical.
  "united states" is read as "us" before comparing.
Matches are merged transitively (union-find).
"""
import re
from collections import Counter

import numpy as np
import pandas as pd
from rapidfuzz import fuzz, process

OVERALL, DISTINCT, GENERIC_MIN, MULTI_STATES, MIN_DISTINCT_LEN = 92, 85, 150, 5, 4


def canon(name):
    return re.sub(r"\bunited states\b", "us", name)


def generic_tokens(names, min_count=GENERIC_MIN):
    c = Counter(t for n in names for t in set(n.split()))
    return {t for t, k in c.items() if k >= min_count}


def distinctive(name, generic):
    return " ".join(t for t in name.split() if t not in generic)


def is_match(a, b, generic, overall=OVERALL, distinct=DISTINCT):
    a, b = canon(a), canon(b)
    if fuzz.token_sort_ratio(a, b) < overall:
        return False
    da, db = distinctive(a, generic), distinctive(b, generic)
    if len(da) < MIN_DISTINCT_LEN or len(db) < MIN_DISTINCT_LEN:
        return da == db and da != ""
    return fuzz.ratio(da, db) >= distinct


def candidate_pairs(E, cutoff):
    """E: DataFrame with entity, name (canon applied inside), states
    (frozenset), nstates. Returns set of (e1, e2) with overall score >=
    cutoff under the blocking rules (C1 within state, C2 cross-state with a
    multi-state side)."""
    E = E.assign(cname=E["name"].map(canon))
    out = set()
    ex = E.explode("states")
    for _, s in ex.groupby("states"):                                # C1
        if len(s) < 2:
            continue
        names, ids = s.cname.tolist(), s.entity.tolist()
        M = process.cdist(names, names, scorer=fuzz.token_sort_ratio, score_cutoff=cutoff, workers=-1)
        for i, j in zip(*np.nonzero(np.triu(M, 1))):
            out.add((min(ids[i], ids[j]), max(ids[i], ids[j])))
    multi = E[E.nstates >= MULTI_STATES]                               # C2
    if len(multi):
        M = process.cdist(multi.cname.tolist(), E.cname.tolist(), scorer=fuzz.token_sort_ratio,
                          score_cutoff=cutoff, workers=-1)
        mids, aids = multi.entity.tolist(), E.entity.tolist()
        for i, j in zip(*np.nonzero(M)):
            if mids[i] != aids[j]:
                out.add((min(mids[i], aids[j]), max(mids[i], aids[j])))
    return out
