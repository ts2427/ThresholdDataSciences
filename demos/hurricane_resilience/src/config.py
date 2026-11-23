"""Paths and constants shared by all scripts."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
OUTPUT = ROOT / "output"
DOCS = ROOT / "docs"
MANIFEST = ROOT / "manifest" / "dirs_reports.csv"
DOWNLOADS_LOG = ROOT / "manifest" / "downloads.csv"

# Raw EAGLE-I year files (~9 GB) live outside the cloud-synced project folder; only filtered extracts go in data/.
EAGLEI_RAW_DIR = Path(os.environ.get("EAGLEI_RAW_DIR", str(Path.home() / "data" / "eaglei")))
# Step 6's filtered extract (study counties and storm windows only); built from the year files if missing.
EAGLEI_EXTRACT = INTERIM / "eaglei_extract.parquet"
# Step 6f's county provider counts (no provider IDs or names) and the one count of near-universal providers.
BDC_COUNTS = PROCESSED / "bdc_county_provider_counts.csv"
BDC_COUNTS_META = PROCESSED / "bdc_county_provider_counts_meta.json"


def census_api_key(env_file: Path = ROOT / ".env") -> str:
    """The Census API key from the environment or .env (gitignored). Never print or log it."""
    key = os.environ.get("CENSUS_API_KEY")
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "CENSUS_API_KEY":
                key = value.strip().strip('"')
    if not key:
        raise SystemExit("CENSUS_API_KEY not set (add it to .env)")
    return key

# Study area: Gulf and Southeast states
STUDY_STATES = ["Texas", "Louisiana", "Mississippi", "Alabama", "Florida", "Georgia",
                "South Carolina", "North Carolina", "Tennessee", "Virginia"]

# Regime boundaries for the policy chapter (descriptive only)
REGIMES = [
    ("Voluntary DIRS, voluntary Framework", "2016-01-01", "2024-04-30"),
    ("MDRI in force, DIRS voluntary", "2024-05-01", "2025-02-19"),
    ("MDRI + mandatory DIRS", "2025-02-20", "2026-06-29"),
    ("Streamlined DIRS (FCC 26-34)", "2026-06-30", "2099-12-31"),
]

USER_AGENT = "public-records-archiver/1.0"  # generic on purpose; see docs/decisions.md
OPENFEMA_DISCLAIMER = ("This product uses the Federal Emergency Management Agency's OpenFEMA API, but is not "
                       "endorsed by FEMA. The Federal Government or FEMA cannot vouch for the data or analyses derived "
                       "from these data after the data have been retrieved from the Agency's website(s).")

# Reports kept in the panel but left out of every time-based result (decision 2026-11-23). Laura's Aug 25, 2020 report
# is the FCC's combined Marco and Laura report, keyed to Laura, and falls before Laura's 34-kt winds reach a county.
TIME_FLAGS = {"DOC-366394A1": "pre_onset_likely_marco"}
