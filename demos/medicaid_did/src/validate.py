"""Check the PUMS state-year rates against published C27016 (2017–2019,
when both use ages 19–64 and the same income cut)."""
import numpy as np
import pandas as pd


def compare_rates(pums, published, col="lowinc_rate"):
    """Join on (year, fips) and summarise the difference PUMS − published
    in percentage points. `published` must carry `<col>_moe90`. Returns
    (summary dict, joined frame)."""
    j = pums.merge(published, on=["year", "fips"], suffixes=("_pums", "_pub"),
                   validate="one_to_one")
    if len(j) != len(published):
        raise ValueError("not every published state-year matched a PUMS row")
    diff_pp = 100 * (j[f"{col}_pums"] - j[f"{col}_pub"])
    within = (diff_pp.abs() <= 100 * j[f"{col}_moe90"])
    summary = {
        "n": int(len(j)),
        "mean_diff_pp": float(diff_pp.mean()),
        "mean_abs_diff_pp": float(diff_pp.abs().mean()),
        "max_abs_diff_pp": float(diff_pp.abs().max()),
        "corr": float(np.corrcoef(j[f"{col}_pums"], j[f"{col}_pub"])[0, 1]),
        "share_within_published_moe90": float(within.mean()),
    }
    j = j.assign(diff_pp=diff_pp, within_moe90=within)
    return summary, j
