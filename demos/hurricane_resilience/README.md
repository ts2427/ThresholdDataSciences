# When the Network Goes Dark (code)

Gulf and Southeast hurricanes, 2017–2026: how much of the cell network goes dark, how fast it comes back, and
what moves with it, from FCC DIRS county reports and other public data. Demonstration on public data. Not client
work. Write-up: thresholddatasciences.com/analysis/when-the-network-goes-dark/

Every number on the page is in `output/results.json`, produced by `src/10_analysis.py`. Read
`docs/analysis_plan.md` first (committed before any outcome was computed) and `docs/decisions.md` (every decision
and deviation, dated).

```
src/            numbered steps 01-11 and their helpers
tests/          pytest -q (two tests skip without the raw data)
manifest/       report list, exception lists, downloads.csv (URL and SHA-256 of every download)
docs/           analysis plan, decision log, data sources, literature
output/         results.json, validation_dirs.csv, validation_summary.csv, excluded_reports.csv
data/processed/ dirs_county_day.csv: the cleaned county-report panel (CC BY 4.0; see DATA_LICENSE.md)
```

Raw downloads are not included. Run order: `src/01_check_manifest.py` to `src/10_analysis.py` (see each
docstring). EAGLE-I's year files (about 9 GB) are read from the folder in the `EAGLEI_RAW_DIR` environment
variable. The Census key goes in a git-ignored `.env` as `CENSUS_API_KEY=...`.
