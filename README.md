# Threshold Data Sciences — site

Static site for [thresholddatasciences.com](https://thresholddatasciences.com):
the Threshold Effects research series, analysis, published research, and the
advisory practice. Python generator, no CMS, no database, no JS framework.
The site works fully with JavaScript disabled.

## Build

```
pip install -r requirements.txt
python build.py
```

Output goes to `dist/`. That's the entire toolchain.

## Adding a Threshold Effects issue

Create one file — `content/threshold-effects/no-012.md`:

```yaml
---
number: 12
title: "The Title"
category: "Regulation"        # drives the archive's category filter
date: 2026-09-01
updated: 2026-09-01           # show an "Updated" line by setting this later
summary: "One or two sentences. Used on the archive index and in OG tags."
linkedin_url: ""              # optional
---

Body in plain Markdown. Cite primary sources as inline links with
descriptive labels. Footnotes, tables, and blockquotes are styled.
```

Run `python build.py`. The archive, the homepage latest-issues block, the RSS
feed, and the sitemap all regenerate from the content directory — there is
nothing else to edit.

`draft: true` in any front matter excludes that file from all output (pages,
feeds, sitemap). Use it for pieces awaiting a journal prior-publication check.

## Adding an analysis piece

Create `content/analysis/<slug>.md`. Same front matter as an issue minus
`number`/`category`, plus:

```yaml
data_sources:                 # every source named and linkable
  - name: "FCC Form 477 deployment data"
    url: "https://..."
method: >-
  One-paragraph methods note, rendered visibly on the page.
download: "/static/data/<file>.csv"   # optional; put the CSV in static/data/
```

`content/analysis/example-analysis.md` demonstrates the full shape and is
marked `draft: true` so it never publishes.

## Research and press

- `content/research.yaml` — published, peer-reviewed work and completed
  working papers only. **Never** dissertation findings, unpublished results,
  or anything overlapping a pending journal submission (check the target
  journal's policy via Sherpa/Romeo first).
- `content/press.yaml` — press mentions. While empty, the homepage's
  "In the press" section is omitted entirely.

## Swapping the logo and favicons

The final logo replaces placeholder files; templates reference paths only.

1. Replace `static/img/logo.svg` (1:1 viewBox; sized via CSS).
2. Replace `static/img/favicon.svg`, `static/img/favicon-32.png`,
   `static/img/apple-touch-icon.png` (180×180), `static/img/og-image.png`
   (1200×630).
3. `python build.py`. Nothing else.

The wordmark beside the mark is HTML text in the display face, so the lockup
can become a single SVG later by editing only the `.brand` block in
`templates/base.html`.

## Design system (for future edits)

- Palette: Ink `#0F2338`, Slate `#2E5A88`, Field `#F2F4F6`, Rule `#C9D1D8`,
  Signal `#C7621B`. **Signal is restricted** to the step-function riser (logo
  and section rules) and threshold lines in data charts. Never links,
  buttons, labels, or hover states.
- Type, all self-hosted in `static/fonts/` (SIL OFL licensed): Source Serif 4
  (display), IBM Plex Sans (body), IBM Plex Mono (issue numbers, dates,
  methods notes). No font CDN, no third-party assets of any kind.
- Flat surfaces, square corners (2px max — currently 0), hairline rules, no
  shadows, no gradients, no motion, no photography. The only images the site
  admits are charts generated from real data, each needing a text alternative
  or adjacent data table.

## Deploy

**Cloudflare Pages** or **Netlify**, static deploy from this repo:

- Build command: `pip install -r requirements.txt && python build.py`
- Output directory: `dist`
- `_redirects` (repo root) is copied into `dist/` by the build.

The contact form uses Netlify Forms (`data-netlify="true"`), which works with
zero backend on Netlify. **On Cloudflare Pages the form needs a different
backend** (e.g. a Pages Function); set `form_backend: ""` in `site.yaml` to
render the contact page without the form until one is wired up.

Analytics: none, deliberately. If a counter is ever wanted, use a cookieless
one (Cloudflare Web Analytics or GoatCounter) and update `/privacy/` first.

## Accessibility audit

`python tools/a11y_audit.py` serves `dist/` locally and runs **axe-core
4.10.2** (WCAG 2.0/2.1/2.2 A+AA + best-practice rulesets) in headless Chrome
against 11 representative pages. (axe via Selenium is used because the build
machine has Python and Chrome but not Node; the ruleset is the same engine
pa11y uses.)

**Result, 2026-08-25 (initial build): PASS — 0 violations across all 11
pages audited** (home, archive, issue No. 011, issue No. 001, analysis,
research, advisory, about, contact, privacy, 404).

Manual checks in the same pass: skip-to-content link, visible focus states,
logical tab order, real `<label>` elements on all form fields,
`prefers-reduced-motion` honored (no motion exists), no horizontal scroll at
360px, all color token pairs ≥ 4.5:1 for text.

Re-run the audit after any template or CSS change.

## Redirect mapping — old blog → this site

The Threshold Effects series originally published at
`timothydspivey.com/blog/`. Two mechanisms:

1. **This domain** — `_redirects` (repo root) already maps the old `/blog/`
   paths to the new issue URLs, so stale links pasted against this host
   resolve.
2. **The old domain** — `timothydspivey.com` is GitHub Pages, which cannot
   serve real 301s. When this site is live, each old blog page there should
   be replaced with a stub carrying `<link rel="canonical">` to the new URL
   and a `<meta http-equiv="refresh">` redirect. That change happens in the
   personal site's repo.

| Old URL (timothydspivey.com) | New URL (this site) |
|---|---|
| `/blog/the-faster-is-better-assumption.html` | `/threshold-effects/no-001/` |
| `/blog/cover-yourself-8-ks.html` | `/threshold-effects/no-002/` |
| `/blog/paper-trails-and-shadow-ai.html` | `/threshold-effects/no-003/` |
| `/blog/shadow-it-was-the-rehearsal.html` | `/threshold-effects/no-004/` |
| `/blog/three-rules-same-outcome.html` | `/threshold-effects/no-005/` |
| `/blog/wanted-the-best-counterexample.html` | `/threshold-effects/no-006/` |
| `/blog/what-the-broadband-labels-revealed.html` | `/threshold-effects/no-007/` |
| `/blog/the-dashboard-is-green.html` | `/threshold-effects/no-008/` |
| `/blog/say-something-vs-build-something.html` | `/threshold-effects/no-009/` |
| `/blog/a-fair-fight-with-sox-404.html` | `/threshold-effects/no-010/` |
| `/blog/gulf-coast-who-the-money-moves-through.html` | `/threshold-effects/no-011/` |
| `/blog/why-threshold-effects.html` | `/threshold-effects/` |
| `/blog/` | `/threshold-effects/` |

## Launch blockers and open TODOs

Content:

- [ ] **Contact email** — a Threshold Data Sciences domain address in
      `site.yaml` (`contact_email`). Business inquiries must not route
      through an employer mail system. Launch blocker.
- [ ] Backfill issue bodies No. 001–010 (front matter is done; each file has
      a `TODO` body). Add inline source links while pasting.
- [ ] Issue No. 011 body is in place as published; its citations still need
      inline source links.
- [ ] `content/research.yaml`: article URLs, and the third ISACA Journal
      article (insider threat dynamics) — exact title, year, URL from the
      published record.
- [ ] ORCID iD in `site.yaml` for the Person schema `sameAs`.
- [ ] Final logo + favicons (placeholders shipped; swap per above).

Reconciliation with the personal site (from the build brief §11 — Tim's to
action, listed here so they aren't lost):

- [ ] **Service-line conflict.** The personal site's consulting section and
      `/threshold/` page describe three service lines; this site launches
      with two. Shrink the personal site's consulting section to a pointer
      at this domain, and redirect `/threshold/` here.
- [ ] **Email routing.** The personal site's contact form (including its
      "Consulting Engagement" topic) posts to a Pensacola State address via
      formsubmit.co. Move business inquiries to the Threshold address.
- [ ] **Publication count.** Personal site hero counter says "2
      Publications"; there are three ISACA Journal articles. Reconcile, then
      remove the counter.
- [ ] **Dissertation findings.** The personal site's About section states
      dissertation conclusions; this site deliberately states none. Decide
      whether the personal site should too.
- [ ] **Personal-site accessibility defects** (scanner-findable): gold
      `#b8970a` small text on white ≈ 2.7:1 (below 4.5:1), and
      `.nav-links { display:none }` under 768px removes all navigation on
      mobile.
- [ ] **Personal-site hotlinked assets:** Wikimedia `Special:FilePath` and
      Unsplash URLs are fragile, and institution logos imply endorsement.

Domain cutover note: `thresholddatasciences.com` currently 301-redirects (via
Squarespace forwarding) to `www.timothydspivey.com`. Launching this site
means pointing the domain's DNS at Cloudflare Pages/Netlify instead of the
forward.
