r"""Demo B step 3d: stratified hand-check sample of fuzzy-match candidate
pairs (Tim, 2026-11-19).

Candidate pool: every pair of step-3b employers allowed by the approved
blocking (C1 same state; C2 cross-state with a side in >= 5 states) whose
overall token_sort_ratio is >= 80. Each pair is classified by the approved
3c rule (fuzzy3c.is_match). Strata:
  accepted                      — the rule merges them (all score >= 92)
  rejected 80-85                — overall 80 <= score < 85
  rejected 85-92                — overall 85 <= score < 92
  rejected 92+ (distinctive)    — overall >= 92, rejected by the
                                  distinctive-part check
Sample: 150 accepted + 50 from each rejected stratum (or all of a stratum
smaller than 50), seed 20261119. National-alias links (C3) are hand-approved
and not part of this sample.

    .venv\Scripts\python -m osha_audit.src.sample3d
"""
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz

from osha_audit.src.fuzzy3c import canon, candidate_pairs, distinctive, generic_tokens, is_match
from osha_audit.src.naive import save_results
from osha_audit.src.step3c_preview import entity_table

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data/interim/osha_step3b.csv"
OUT = ROOT / "review/b_3d_pairs.csv"
POOL = ROOT / "data/interim/3d_candidate_pool.csv"
SEED, CUTOFF = 20261119, 80
ALLOC = {"accepted": 150, "rejected 80-85": 50, "rejected 85-92": 50, "rejected 92+ (distinctive)": 50}


def stratum(score, accepted):
    if accepted:
        return "accepted"
    if score < 85:
        return "rejected 80-85"
    if score < 92:
        return "rejected 85-92"
    return "rejected 92+ (distinctive)"


def stratified_sample(pool, alloc, seed=SEED):
    parts = []
    for s, n in alloc.items():
        g = pool[pool.stratum == s]
        parts.append(g.sample(n=min(n, len(g)), random_state=seed))
    return pd.concat(parts, ignore_index=True)


def build_pool(E, generic):
    nm = E.set_index("entity")
    rows = []
    for a, b in candidate_pairs(E[["entity", "name", "states", "nstates"]], cutoff=CUTOFF):
        na, nb = nm.at[a, "name"], nm.at[b, "name"]
        score = fuzz.token_sort_ratio(canon(na), canon(nb))
        acc = is_match(na, nb, generic)
        rows.append({"entity_a": a, "entity_b": b, "score": round(score, 1),
                     "distinctive_score": round(fuzz.ratio(distinctive(canon(na), generic),
                                                           distinctive(canon(nb), generic)), 1),
                     "accepted": acc, "stratum": stratum(score, acc)})
    return pd.DataFrame(rows)


def main():
    d = pd.read_csv(IN, dtype=str, keep_default_na=False)
    E = entity_table(d)
    generic = generic_tokens(E.name.map(canon))
    pool = build_pool(E, generic)
    pool.to_csv(POOL, index=False)
    sizes = pool.stratum.value_counts().to_dict()
    smp = stratified_sample(pool, ALLOC).sample(frac=1, random_state=SEED).reset_index(drop=True)
    info = E.set_index("entity")
    fmt_states = lambda s: "; ".join(sorted(s))
    out = pd.DataFrame({
        "item": range(1, len(smp) + 1),
        "name_a": smp.entity_a.map(info.label), "states_a": smp.entity_a.map(lambda e: fmt_states(info.at[e, "states"])),
        "reports_a": smp.entity_a.map(info.reports),
        "name_b": smp.entity_b.map(info.label), "states_b": smp.entity_b.map(lambda e: fmt_states(info.at[e, "states"])),
        "reports_b": smp.entity_b.map(info.reports),
        "score": smp.score, "distinctive_score": smp.distinctive_score, "band": smp.stratum,
        "entity_a": smp.entity_a, "entity_b": smp.entity_b,
        "same employer": "",
    })
    out.to_csv(OUT, index=False, encoding="utf-8-sig")
    payload = {"candidate_cutoff": CUTOFF, "pool_size": int(len(pool)), "stratum_sizes": sizes,
               "allocation": {s: int(min(n, sizes.get(s, 0))) for s, n in ALLOC.items()},
               "seed": SEED, "status": "awaiting labels in review/b_3d_pairs.csv"}
    save_results("step3d_sample", payload)
    return payload


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=1))
