#!/usr/bin/env python3
"""Sanity-check the built RSS feed with feedparser (local counterpart to the
W3C Feed Validator — run that against the live URL after deploy)."""
import sys
from pathlib import Path

import feedparser

feed_path = Path(__file__).parent.parent / "dist" / "threshold-effects" / "feed.xml"
f = feedparser.parse(feed_path.read_bytes())

problems = []
if f.bozo:
    problems.append(f"parse error: {f.bozo_exception}")
for key in ("title", "link", "description"):
    if not f.feed.get(key):
        problems.append(f"channel missing {key}")
if not f.feed.get("updated"):
    problems.append("channel missing lastBuildDate")
for e in f.entries:
    if not e.get("id"):
        problems.append(f"entry missing guid: {e.get('title')}")
    if not e.get("published"):
        problems.append(f"entry missing pubDate: {e.get('title')}")
    if not (e.get("link") or "").startswith("https://"):
        problems.append(f"entry link not absolute: {e.get('title')}")

if problems:
    print("FEED PROBLEMS:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print(f"feed OK: {len(f.entries)} item(s), guid/pubDate/link present, "
      "channel has title/link/description/lastBuildDate, no parse errors")
