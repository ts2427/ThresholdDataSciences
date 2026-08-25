#!/usr/bin/env python3
"""Post-build checks: JSON-LD parses, internal links resolve, one h1 per page."""
import json
import re
import sys
from pathlib import Path

DIST = Path(__file__).parent.parent / "dist"
errors = []

pages = sorted(DIST.rglob("*.html"))
for page in pages:
    html = page.read_text(encoding="utf-8")
    rel = page.relative_to(DIST)

    # JSON-LD parses
    for m in re.finditer(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            json.loads(m.group(1))
        except json.JSONDecodeError as e:
            errors.append(f"{rel}: invalid JSON-LD ({e})")

    # exactly one h1
    h1s = re.findall(r"<h1[ >]", html)
    if len(h1s) != 1:
        errors.append(f"{rel}: {len(h1s)} <h1> elements")

    # leftover template syntax
    if "{{" in html or "{%" in html:
        errors.append(f"{rel}: unrendered template syntax")

    # internal links resolve
    for href in re.findall(r'href="(/[^"#]*)"', html):
        if href.startswith("//"):
            continue
        target = DIST / href.lstrip("/")
        ok = (target.exists()
              or (target / "index.html").exists()
              or (DIST / (href.lstrip("/").rstrip("/") + "/index.html")).exists())
        if not ok:
            errors.append(f"{rel}: broken internal link {href}")
    for src in re.findall(r'src="(/[^"]*)"', html):
        if not (DIST / src.lstrip("/")).exists():
            errors.append(f"{rel}: missing asset {src}")

if errors:
    print(f"{len(errors)} problem(s):")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"OK: {len(pages)} pages — JSON-LD valid, one h1 each, links and assets resolve.")
