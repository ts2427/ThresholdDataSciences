"""Step 6f (v2-5): county provider counts from step 6e's rows, with no provider ID or name.

For each BDC release and study-state county: the number of providers under each measure in 12_v2_analysis.MEASURES
(mobile or fixed; any service or at least half of locations; near-universal fixed providers excluded or not), and the
number of near-universal fixed providers (one number). This is the only BDC-derived file v2-5 reads, and the only
one published.
Output: data/processed/bdc_county_provider_counts.csv and bdc_county_provider_counts_meta.json.
"""
import importlib
import json

import pandas as pd

from config import BDC_COUNTS, BDC_COUNTS_META, INTERIM

v2 = importlib.import_module("12_v2_analysis")


def main():
    b = pd.read_parquet(INTERIM / "bdc_provider_county.parquet")
    counts, n_universal = v2.county_counts(b)
    assert not any("provider" in c and c != "n_near_universal_providers" for c in counts.columns)
    counts.to_csv(BDC_COUNTS, index=False, lineterminator="\n")
    BDC_COUNTS_META.write_text(json.dumps({"n_near_universal_providers": n_universal,
                                           "near_universal_rule": "fixed providers reporting any residential service "
                                           "in at least 95% of the study-state counties of some release",
                                           "measures": {m: list(v) for m, v in v2.MEASURES.items()}}, indent=1) + "\n",
                               encoding="utf-8")
    print(f"{len(counts):,} release-county rows; {n_universal} near-universal providers")


if __name__ == "__main__":
    main()
