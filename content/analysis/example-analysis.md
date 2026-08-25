---
draft: true          # excluded from all output until set to false
title: "Example Analysis Piece"
date: 2026-08-25
updated: 2026-08-25
summary: "A placeholder demonstrating the analysis front matter: named data sources, a visible methods note, and an optional CSV download."
method: >-
  One-paragraph methods note. Rendered visibly on the page, in the monospace
  utility face, below the body. Describe the sample, the estimation approach,
  and the main limitation in plain language.
data_sources:
  - name: "Example primary source (agency dataset)"
    url: "https://example.gov/dataset"
  - name: "Example secondary source (published study)"
    url: "https://example.org/study"
download: "/static/data/example.csv"
---

TODO: body of the analysis piece. Plain Markdown — tables, footnotes, and
blockquotes are all styled. Charts are the only images allowed on the site,
generated from real data, each with a text alternative or adjacent data table.

Before publishing any piece that overlaps a pending journal submission, clear
it against the target journal's prior-publication policy (Sherpa/Romeo
aggregates these), then set `draft: false`.
