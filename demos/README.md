# Threshold Data Sciences — worked examples (code)

Two public-data demonstrations from Threshold Data Sciences, each answering
one question from raw public data to a result with its uncertainty. Every
number in the write-ups is produced by code in this folder, which lives at
`demos/` in the site repository
(https://github.com/ts2427/ThresholdDataSciences/tree/main/demos). Run every
command below from inside `demos/`.

| Demo | Question | Folder | Write-up |
|---|---|---|---|
| A. Medicaid expansion and the low-income adult uninsured rate | Did it work? | `medicaid_did/`, `r/` | thresholddatasciences.com/analysis/medicaid-expansion-uninsured/ |
| B. OSHA Severe Injury Reports: who files the reports | Can you trust the number? | `osha_audit/` | thresholddatasciences.com/analysis/osha-severe-injury-reports-audit/ |

Demonstrations on public data. Not client work.

## What is here

```
common/          download manifest helper
medicaid_did/    Demo A: data pipeline, estimators, figures (src/, tests/)
osha_audit/      Demo B: audit pipeline, entity resolution, estimates (src/, tests/)
r/               R scripts for Demo A (did, HonestDiD)
site_pages/      renders the two web pages from results/*.json and verifies figure data
docs/            analysis plan (Demo A, written before any estimate), decisions log, sources
manifest/        downloads.csv: every source file with URL, access date, SHA-256 and row count
data/processed/  analysis-ready files derived from the public sources
results/         every reported number (<demo>.json) and the figure CSVs/PNGs
```

Raw downloads are not included (they are large and are public at the URLs
in `manifest/downloads.csv`); the scripts below re-download them, and the
SHA-256 column lets you confirm you have the same files. Label files
used during the audit are not included; their outcomes are recorded in
`docs/decisions.md` and `results/osha_audit.json`.

## Setup

Python 3.13:

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt     # Windows
# .venv/bin/python -m pip install -r requirements.txt       # macOS/Linux
```

R 4.6 with the packages `did` (2.5.1), `HonestDiD` (0.2.8), `fixest` and
`data.table`, for Demo A's estimation scripts.

Demo A needs a free Census Data API key
(https://api.census.gov/data/key_signup.html). Put it in a file named `.env`
in the repository root:

```
CENSUS_API_KEY=your-key-here
```

`.env` is git-ignored; the scripts never print the key or write it to the
manifest.

## Run Demo A — Medicaid expansion (did it work?)

```
python -m medicaid_did.src.build_expansion     # expansion dates (KFF page saved under data/raw/)
python -m medicaid_did.src.download_pums       # ACS PUMS, 2009–2024 (about 1 GB)
python -m medicaid_did.src.download_acs        # published table C27016, 2017–2019 (check)
python -m medicaid_did.src.step1_summary       # panel + check against the published table
Rscript r/demo_a_main.R                        # Callaway–Sant'Anna, TWFE, robustness
Rscript r/demo_a_honestdid.R                   # sensitivity bounds
Rscript r/investigate_pretest.R                # pre-trend investigation
Rscript r/demo_a_posthoc.R                     # robustness rows added after seeing results
python -m medicaid_did.src.secondary           # 2009–2024, calendar-year event time
python -m medicaid_did.src.step2_collect       # assemble results/medicaid_did.json
python -m medicaid_did.src.before_after        # naive vs comparison-adjusted
python -m medicaid_did.src.figures             # figure CSVs and PNGs
```

`build_expansion` reads a saved copy of KFF's State Health Facts page; fetch
it to `data/raw/kff_expansion_status_2026-11.html` from the URL in the
manifest first. Read `docs/analysis_plan.md` before the results: it was
committed before any estimator was run.

## Run Demo B — OSHA Severe Injury Reports (can you trust the number?)

```
python -m osha_audit.src.download              # Severe Injury Reports zip
python -m osha_audit.src.naive                 # the naive count
python -m osha_audit.src.dedupe_apply          # 3a: confirmed duplicates (needs review/b_dup_pairs.csv)
python -m osha_audit.src.entities3b --apply    # 3b: name normalization (narrower suffix rule)
python -m osha_audit.src.step3c_apply          # 3c: fuzzy matching + approved aliases (needs review/b_3c_alias_candidates.csv)
python -m osha_audit.src.step3d_estimate       # 3d: precision/recall (needs review/b_3d_pairs.csv)
python -m osha_audit.src.headcounts            # 3e: headcount illustration (needs the 10-K filings in data/raw/filings/)
```

Steps 3a, 3c and 3d use label files that are not published (see
above); the decisions they encode are listed in `docs/decisions.md`.
`osha_audit/src/ita_feasibility.py` is a one-year feasibility check for
future work (`docs/paper_idea_ita_linkage.md`); it publishes no rates.

## Tests

```
python -m pytest
```

## Licence

Code: MIT (see `LICENSE`). The source data are public U.S. government data
and company filings, used under their own terms; the written analysis on
thresholddatasciences.com is not covered by this licence.
