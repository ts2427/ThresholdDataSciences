r"""Demo B step 3d: precision and recall of the 3c matcher from the labeled
stratified sample, exactly as pre-specified (docs/decisions.md, 3d entry):

  precision = share Y among the accepted sample; 95% Wilson interval
  recall    = est. true matches in the accepted stratum / est. true matches
              in all strata, each stratum's Y share weighted to its pool
              size; 95% interval from a stratified bootstrap (resample
              within strata, 10,000 draws, seed 20261119)

Sensitivity row: the same with every "Judgment call" label flipped.

    .venv\Scripts\python -m osha_audit.src.step3d_estimate
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from osha_audit.src.naive import save_results

ROOT = Path(__file__).resolve().parents[2]
LABELS = ROOT / "review/b_3d_pairs.csv"
SEED, REPS = 20261119, 10000
ACCEPTED = "accepted"


def wilson(k, n, z=1.959963984540054):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, centre - half, centre + half


def point_estimates(y_by_stratum, pool_sizes):
    """y_by_stratum: {stratum: array of 0/1}. Returns precision, recall,
    and estimated true matches per stratum."""
    est = {s: pool_sizes[s] * np.mean(y) for s, y in y_by_stratum.items()}
    total = sum(est.values())
    precision = float(np.mean(y_by_stratum[ACCEPTED]))
    recall = est[ACCEPTED] / total if total else float("nan")
    return precision, recall, est


def stratified_bootstrap(y_by_stratum, pool_sizes, reps=REPS, seed=SEED):
    rng = np.random.default_rng(seed)
    rec, missed = np.empty(reps), np.empty(reps)
    arrays = {s: np.asarray(y) for s, y in y_by_stratum.items()}
    for r in range(reps):
        boot = {s: a[rng.integers(0, len(a), len(a))] for s, a in arrays.items()}
        _, rec[r], est = point_estimates(boot, pool_sizes)
        missed[r] = sum(v for s, v in est.items() if s != ACCEPTED)
    return rec, missed


def summarize(df, pool_sizes):
    y = {s: (g["same employer"].str.upper() == "Y").astype(int).to_numpy()
         for s, g in df.groupby("band")}
    k, n = int(y[ACCEPTED].sum()), len(y[ACCEPTED])
    p, plo, phi = wilson(k, n)
    _, rec, est = point_estimates(y, pool_sizes)
    rb, mb = stratified_bootstrap(y, pool_sizes)
    missed = sum(v for s, v in est.items() if s != ACCEPTED)
    false_merges = pool_sizes[ACCEPTED] * (1 - p)
    return {
        "precision": p, "precision_ci95_wilson": [plo, phi], "precision_k_n": [k, n],
        "recall": rec, "recall_ci95_stratified_bootstrap": [float(np.quantile(rb, .025)), float(np.quantile(rb, .975))],
        "est_true_matches_by_stratum": {s: float(v) for s, v in est.items()},
        "est_missed_matching_pairs": float(missed),
        "est_missed_ci95": [float(np.quantile(mb, .025)), float(np.quantile(mb, .975))],
        "est_false_merges": float(false_merges),
        "y_counts": {s: [int(a.sum()), len(a)] for s, a in y.items()},
    }


def flip_judgment_calls(df):
    d = df.copy()
    m = d["claude_note"].str.contains("judgment call", case=False, na=False)
    d.loc[m, "same employer"] = d.loc[m, "same employer"].str.upper().map({"Y": "N", "N": "Y"})
    return d, int(m.sum())


def main():
    df = pd.read_csv(LABELS, dtype=str, keep_default_na=False)
    lab = df["same employer"].str.strip().str.upper()
    if not lab.isin(["Y", "N"]).all():
        raise ValueError("every item needs a Y or N label")
    res = json.loads((ROOT / "results/osha_audit.json").read_text(encoding="utf-8"))
    pool = res["step3d_sample"]["stratum_sizes"]
    main_ = summarize(df, pool)
    flipped, n_flip = flip_judgment_calls(df)
    sens = summarize(flipped, pool)
    # 80-85 stratum had 0/50: the bootstrap cannot vary it. Report the
    # recall implied by its Wilson upper bound as a stated limitation.
    z80 = df[df.band == "rejected 80-85"]
    k80 = int((z80["same employer"].str.upper() == "Y").sum())
    _, _, hi80 = wilson(k80, len(z80))
    est = dict(main_["est_true_matches_by_stratum"])
    est["rejected 80-85"] = pool["rejected 80-85"] * hi80
    recall_if_80_85_at_upper = est[ACCEPTED] / sum(est.values())
    payload = {"method": {"precision": "Wilson 95% interval",
                          "recall": f"stratified bootstrap, {REPS} draws, seed {SEED}, weighted to pool sizes"},
               "pool_sizes": pool, "main": main_,
               "sensitivity_judgment_calls_flipped": {"n_flipped": n_flip, **sens},
               "limitation_80_85": {"y_k_n": [k80, len(z80)], "wilson_upper": hi80,
                                    "recall_if_at_wilson_upper": recall_if_80_85_at_upper},
               "label_source_note": ("labels supplied by Tim in review/b_3d_pairs.csv; the notes column is "
                                     "named claude_note, so labels may have been drafted by Claude — "
                                     "confirm review before calling this a hand check")}
    if "step3c_final" in res:
        final_n = res["step3c_final"]["final_counts"]["by_name"]
        payload["overstatement"] = overstatement(main_, final_n)
    save_results("step3d_estimate", payload)
    return payload


def overstatement(est, final_employers):
    """Upper bound on how far missed matches inflate the distinct-employer
    count: each missed matching pair removes at most one employer (fewer
    when pairs overlap). False merges push the other way."""
    lo, hi = est["est_missed_ci95"]
    return {"final_employers_by_name": final_employers,
            "missed_pairs": est["est_missed_matching_pairs"], "missed_pairs_ci95": [lo, hi],
            "max_overstatement_pct": 100 * est["est_missed_matching_pairs"] / final_employers,
            "max_overstatement_pct_ci95": [100 * lo / final_employers, 100 * hi / final_employers],
            "false_merges_understate_by": est["est_false_merges"]}


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
