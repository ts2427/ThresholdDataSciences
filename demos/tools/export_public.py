r"""Build the public snapshot of this repository (no git history) and scan it.

    .venv\Scripts\python tools/export_public.py <output_dir>

- Takes the files tracked at HEAD (git archive), then drops anything that
  must not be public: label files (review/), raw and
  interim data (never tracked, excluded again for safety), .env, and
  CLAUDE.md (local paths and assistant instructions).
- Scans (a) every blob in the FULL git history and (b) the snapshot for the
  Census API key from .env, reporting only counts — the key is never
  printed — plus local paths and e-mail addresses in the snapshot.
- Publishing is a fresh single-commit repository from the snapshot, so the
  history (which contains the review files) is never pushed.
"""
import io
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = (re.compile(r"^review/"), re.compile(r"^data/(raw|interim)/"),
           re.compile(r"^\.env$"), re.compile(r"^CLAUDE\.md$"))


def excluded(path):
    return any(p.search(path) for p in EXCLUDE)


def git(*args, binary=False):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True)
    return out.stdout if binary else out.stdout.decode("utf-8", errors="replace")


def history_hits(secret):
    """Count history blobs containing the secret (scans every object)."""
    objs = [l.split()[0] for l in git("rev-list", "--all", "--objects").splitlines() if l.strip()]
    hits = 0
    for o in objs:
        if git("cat-file", "-t", o).strip() != "blob":
            continue
        if secret.encode() in git("cat-file", "-p", o, binary=True):
            hits += 1
    return hits, len(objs)


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tar = tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", "HEAD", binary=True)))
    kept, dropped = [], []
    for m in tar.getmembers():
        if not m.isfile():
            continue
        (dropped if excluded(m.name) else kept).append(m.name)
        if not excluded(m.name):
            dest = out / m.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(tar.extractfile(m).read())
    secret = dotenv_values(ROOT / ".env").get("CENSUS_API_KEY", "")
    if not secret:
        raise SystemExit("no key in .env to scan for")
    h_hits, n_obj = history_hits(secret)
    s_hits, paths, emails = 0, [], []
    for f in out.rglob("*"):
        if f.is_file():
            b = f.read_bytes()
            s_hits += secret.encode() in b
            t = b.decode("utf-8", errors="ignore")
            if re.search(r"[A-Za-z]:\\Users\\|/c/Users/", t):
                paths.append(str(f.relative_to(out)))
            if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", t) and not f.name.endswith((".png", ".pdf")):
                emails.append(str(f.relative_to(out)))
    print(f"snapshot: {len(kept)} files kept, {len(dropped)} dropped")
    print("dropped:", ", ".join(sorted(dropped)))
    print(f"key in git history: {h_hits} blobs of {n_obj} objects scanned")
    print(f"key in snapshot: {s_hits} files")
    print(f".env ever committed: {'yes' if git('log', '--all', '--oneline', '--', '.env').strip() else 'no'}")
    print("local paths in snapshot:", paths or "none")
    print("e-mail-like strings in snapshot:", emails or "none")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"snapshot size: {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1])
