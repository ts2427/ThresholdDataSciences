"""Check that a site branch's hurricane chart data and data download match the data release.

  python tools/check_release_data.py --site <repo URL or path> --site-branch release-4.0.0 \
      --data <data repo URL or path> --data-branch release-4.0.0 --rows 11296

Added 2026-11-28 (When the Network Goes Dark 4.0.0) after the site branch release-4.0.0 was pushed at 1dd7242 with the
4.0.0 page text but the 3.2.1 chart data and download: the site checks ran on the working tree and passed.

This check reads no local working files. It makes a fresh clone of the site branch and of the data branch (or tag)
into a temporary folder, with line-ending conversion off, so it sees the committed bytes, and then requires:
  1. the download (static/data/hurricane-dirs-county-day.csv) has --rows data rows, and its SHA-256 equals the
     release's: the hash in the data release's datapackage.json, the release file's own bytes, and the site's record;
  2. the site's release record (content/data/hurricane-release.json, written by the page build) names this data
     release's version, and the results.json it was built from has the release's SHA-256 (datapackage.json and bytes);
  3. every chart data file (content/data/hurricane-*.csv, the county lookup and the map) has the SHA-256 the record
     gives, and no chart data file is missing from the record.
Exit 0 only if every check passes.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RECORD = "content/data/hurricane-release.json"
EXTRA_CHART_DATA = ("static/data/hurricane-county-lookup.json", "static/data/hurricane-map.json")


def clone(src: str, branch: str, dest: Path) -> Path:
    subprocess.run(["git", "-c", "core.autocrlf=false", "clone", "--quiet", "--depth", "1", "--single-branch",
                    "--branch", branch, "--no-local", src, str(dest)], check=True)
    head = subprocess.run(["git", "-C", str(dest), "rev-parse", "--short", "HEAD"], check=True,
                          capture_output=True, text=True).stdout.strip()
    print(f"cloned {src} @ {branch} ({head})")
    return dest


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data_rows(path: Path) -> int:
    with open(path, encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def run(site: Path, data: Path, rows: int) -> list:
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}{': ' + detail if detail else ''}")

    pkg = json.loads((data / "datapackage.json").read_text(encoding="utf-8"))
    hashes = {r["path"]: r.get("hash", "").removeprefix("sha256:") for r in pkg["resources"]}
    rec_path = site / RECORD
    check("site release record exists", rec_path.exists(), RECORD)
    rec = json.loads(rec_path.read_text(encoding="utf-8")) if rec_path.exists() else {}
    dl = rec.get("download", {"path": "static/data/hurricane-dirs-county-day.csv",
                              "release_path": "data/analysis/dirs_county_day.csv"})

    # 1. the download
    site_dl, rel_dl = site / dl["path"], data / dl["release_path"]
    n = data_rows(site_dl) if site_dl.exists() else -1
    check("download row count", n == rows, f"{n:,} rows, expected {rows:,}")
    got, want = (sha256(site_dl) if site_dl.exists() else "missing"), hashes.get(dl["release_path"], "missing")
    check("download SHA-256 = release datapackage.json", got == want, f"{got[:16]} vs {want[:16]}")
    check("download SHA-256 = release file bytes", rel_dl.exists() and got == sha256(rel_dl))
    check("download SHA-256 = site record", got == dl.get("sha256"))
    check("record row count", dl.get("rows") == rows, str(dl.get("rows")))

    # 2. the release the charts were built from
    check("record names this data release", rec.get("data_release") == pkg.get("version"),
          f"{rec.get('data_release')} vs datapackage {pkg.get('version')}")
    want = hashes.get("data/analysis/results.json", "missing")
    check("charts built from the release's results.json (datapackage.json)", rec.get("results_json_sha256") == want,
          f"{str(rec.get('results_json_sha256'))[:16]} vs {want[:16]}")
    check("charts built from the release's results.json (file bytes)",
          rec.get("results_json_sha256") == sha256(data / "data" / "analysis" / "results.json"))

    # 3. the chart data files
    listed = rec.get("chart_data_sha256", {})
    on_branch = {p.relative_to(site).as_posix() for p in (site / "content" / "data").glob("hurricane-*.csv")}
    on_branch |= {p for p in EXTRA_CHART_DATA if (site / p).exists()}
    check("every chart data file is in the record", bool(listed) and on_branch <= set(listed),
          ", ".join(sorted(on_branch - set(listed))) or f"{len(on_branch)} files")
    bad = [p for p, h in listed.items() if not (site / p).exists() or sha256(site / p) != h]
    check("chart data SHA-256 = record", bool(listed) and not bad, ", ".join(bad) or f"{len(listed)} files")
    return results


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--site", required=True)
    a.add_argument("--site-branch", required=True)
    a.add_argument("--data", required=True)
    a.add_argument("--data-branch", required=True, help="a branch or a tag, e.g. v4.0.0")
    a.add_argument("--rows", type=int, required=True, help="the release's county-report rows, e.g. 11296")
    args = a.parse_args(argv)
    with tempfile.TemporaryDirectory() as tmp:
        site = clone(args.site, args.site_branch, Path(tmp) / "site")
        data = clone(args.data, args.data_branch, Path(tmp) / "data")
        results = run(site, data, args.rows)
    print(f"{sum(results)} of {len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
