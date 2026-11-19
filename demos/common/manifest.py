"""Download log: every raw file gets a row in manifest/downloads.csv
(file, url, accessed, sha256, rows). Raw files are never edited."""
import csv
import hashlib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "manifest" / "downloads.csv"
FIELDS = ["file", "url", "accessed", "sha256", "rows"]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record(path, url, rows, accessed=None, manifest=MANIFEST):
    """Add or replace the manifest row for `path` (relative to the repo
    root). `rows` is the number of data rows the file holds (as parsed), so
    a later reader can check the file is complete."""
    path = Path(path)
    try:
        rel = Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        rel = Path(path).as_posix()
    row = {"file": rel, "url": url,
           "accessed": (accessed or date.today()).isoformat(),
           "sha256": sha256_file(path), "rows": int(rows)}
    manifest = Path(manifest)
    existing = []
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as fh:
            existing = [r for r in csv.DictReader(fh) if r["file"] != rel]
    with open(manifest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(existing + [row])
    return row
