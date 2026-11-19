r"""Step A1b: expansion dates table from the saved KFF page.
    .venv\Scripts\python -m medicaid_did.src.build_expansion
"""
from pathlib import Path

from common import manifest
from medicaid_did.src.expansion import KFF_URL, build_expansion_table

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/kff_expansion_status_2026-11.html"
OUT = ROOT / "data/processed/expansion_dates.csv"
ACCESSED = "2026-11-19"

if __name__ == "__main__":
    page = RAW.read_text(encoding="utf-8")
    df = build_expansion_table(page, ACCESSED)
    manifest.record(RAW, KFF_URL, rows=len(df))
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(df)} rows)")
