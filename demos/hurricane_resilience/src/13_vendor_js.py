"""Step 13 (v2-6): vendor D3 7.9.0 and topojson-client 3.1.0 into the site, verified against npm (2026-11-23).

For each package: the npm registry's metadata gives the tarball URL and its SHA-512 integrity; the tarball is
downloaded and checked against it; the dist file is fetched from jsDelivr and must equal, byte for byte, the file in
the verified tarball; the LICENSE comes from the verified tarball. Files go to threshold-site/static/js/vendor/, so
the page loads them from its own site (no third-party request; the privacy page stays true).
Conduct: generic User-Agent, at least 3 s between requests, any non-200 (403/429 included) stops with no retry; every
request is logged in manifest/downloads.csv with its SHA-256. Tarballs stay in data/raw/vendor/ (git-ignored).
"""
import base64
import hashlib
import io
import tarfile
import time
from datetime import datetime, timezone

import pandas as pd
import requests

from config import DOWNLOADS_LOG, RAW, ROOT, USER_AGENT

SITE_VENDOR = ROOT.parent / "static" / "js" / "vendor"
PACKAGES = [("d3", "7.9.0", "dist/d3.min.js"), ("topojson-client", "3.1.0", "dist/topojson-client.min.js")]
GAP = 3.0


def log(url, path, status, sha):
    pd.DataFrame([{"url": url, "path": path, "status": status, "sha256": sha, "doc_id": url.rsplit("/", 1)[-1],
                   "kind": "vendor_js", "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}]).to_csv(
        DOWNLOADS_LOG, mode="a", header=False, index=False, lineterminator="\n")


def get(s, url, path_label):
    r = s.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    if r.status_code != 200:
        log(url, path_label, f"http_{r.status_code}", "")
        raise SystemExit(f"STOP: HTTP {r.status_code} for {url} (no retry)")
    log(url, path_label, "downloaded", hashlib.sha256(r.content).hexdigest())
    time.sleep(GAP)
    return r.content


def main():
    s = requests.Session()
    (RAW / "vendor").mkdir(parents=True, exist_ok=True)
    SITE_VENDOR.mkdir(parents=True, exist_ok=True)
    for name, ver, dist in PACKAGES:
        meta = get(s, f"https://registry.npmjs.org/{name}/{ver}", f"data/raw/vendor/{name}-{ver}.metadata.json")
        (RAW / "vendor" / f"{name}-{ver}.metadata.json").write_bytes(meta)
        import json
        d = json.loads(meta)["dist"]
        algo, want = d["integrity"].split("-", 1)
        if algo != "sha512":
            raise SystemExit(f"{name}: unexpected integrity algorithm {algo}")
        tgz = get(s, d["tarball"], f"data/raw/vendor/{name}-{ver}.tgz")
        if base64.b64encode(hashlib.sha512(tgz).digest()).decode() != want:
            raise SystemExit(f"{name}: tarball does not match the npm registry's sha512 integrity")
        (RAW / "vendor" / f"{name}-{ver}.tgz").write_bytes(tgz)
        with tarfile.open(fileobj=io.BytesIO(tgz), mode="r:gz") as t:
            from_tar = t.extractfile(f"package/{dist}").read()
            lic = next(m for m in t.getmembers() if m.name.lower() in ("package/license", "package/license.md",
                                                                         "package/license.txt"))
            licence = t.extractfile(lic).read()
        cdn = get(s, f"https://cdn.jsdelivr.net/npm/{name}@{ver}/{dist}", f"data/raw/vendor/{name}-{ver}.min.js")
        (RAW / "vendor" / f"{name}-{ver}.min.js").write_bytes(cdn)
        if cdn != from_tar:
            raise SystemExit(f"{name}: the jsDelivr file differs from the file in the verified npm tarball")
        (SITE_VENDOR / f"{name}-{ver}.min.js").write_bytes(cdn)
        (SITE_VENDOR / f"LICENSE-{name}.txt").write_bytes(licence)
        print(f"{name} {ver}: npm sha512 integrity OK; jsDelivr file identical to tarball; {len(cdn):,} bytes; licence "
              f"from tarball ({lic.name.split('/')[-1]})")


if __name__ == "__main__":
    main()
