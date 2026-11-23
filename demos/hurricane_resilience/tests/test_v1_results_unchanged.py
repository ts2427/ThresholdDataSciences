"""Version 2 must not change version 1's results: every chapter_* key of results.json keeps its SHA-256 (addendum)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "src"))
from config import OUTPUT  # noqa: E402
RESULTS = OUTPUT / "results.json"
SNAP = ROOT / "tests" / "snapshots" / "v1_results_sha256.json"


def test_v1_chapter_keys_are_unchanged():
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    want = json.loads(SNAP.read_text(encoding="utf-8"))
    got = {k: hashlib.sha256(json.dumps(r[k], sort_keys=True, ensure_ascii=False).encode()).hexdigest() for k in want}
    assert got == want, [k for k in want if got[k] != want[k]]
