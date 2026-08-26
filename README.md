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
feeds, sitemap). Use it for pieces awaiting a journal prior-publication check,
and for backfill files whose metadata isn't verified yet.

**Content integrity rules.** This site's entire claim is a citable record,
and issues cross-link to public posts anyone can verify:

- Every title, date, category, and summary comes from the published record —
  never from memory, never invented, never "close enough."
- The build **fails** if a non-draft issue has a title containing `TBC`, a
  summary containing `TODO`, or no date. Placeholder files sit in the repo as
  `draft: true` until their verified values are supplied.
- Tooling (including AI assistants) must never generate content for this
  site — structure, markup, and styling only.

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

## Figures (build-time SVG charts)

Charts are static SVG generated at build time by `figures.py` from CSVs in
`content/data/` — no JavaScript, no plotting library, no external service.
Types: `bar` (horizontal, optional `group` column), `column`, `line`, `dot`
(group means + annotation rows from the data), `timeline` (dated milestones
with the phase transition rendered as a step, riser in Signal).

Declare figures in front matter (see the commented blocks in `no-003.md`,
`no-007.md`, `no-011.md` for ready examples). Place a figure in the body
with a `[figure:fig-1]` marker on its own line, or it is appended after the
body. Every figure renders with a `<figcaption>` (title states the finding;
caption and sourced/retrieval line below), a "View data table" `<details>`
element, and — when `data_public: true` — a CSV download link; only CSVs
behind a verified public figure are copied into `dist/static/data/`.

**Verification guard: `verified: false` (the default) on any figure on a
published page FAILS the build.** Data sits in `content/data/` while it is
checked against the primary source; a figure ships only after `verified:
true` is set deliberately. Signal (`#C7621B`) appears at most once per
chart — named via `signal:` (annotation kind) or the timeline's transition
riser — and only to mark the threshold or point the argument turns on.
**No simulated data, ever**: an issue without a real dataset renders no
figure.

The three activation steps for a waiting figure: check the CSV against the
primary source, set `verified: true`, uncomment the `figures:` block.

## Methods page and corrections

`content/pages/methods.md` is a `draft: true` skeleton — the nav link and
page appear only when its TODO blocks are replaced with Tim's wording (the
build fails if a published page still contains TODO text). Corrections are
front-matter (`corrections:` list of `date` + `note`) rendered as a dated
block above the Sources and citation blocks; never generate an example.
Per-issue sources are front-matter (`sources:` list of `name`, `publisher`,
`date`, `url`) rendered at the foot of the page; empty list = no section.

## Research and press

- `content/research.yaml` — published, peer-reviewed work and completed
  working papers only. **Never** dissertation findings, unpublished results,
  or anything overlapping a pending journal submission (check the target
  journal's policy via Sherpa/Romeo first).
- `content/press.yaml` — press mentions. While empty, the homepage's
  "In the press" section is omitted entirely.

## The logo

The step-function mark **is** the logo — it encodes the firm's name, doubles
as the site's structural device (the section rules), and scales cleanly. It
is not a placeholder awaiting a commissioned design.

- `static/img/logo.svg` — the mark as shown on the Ink site header (white
  segments, Signal riser). Sized via CSS, never inlined into templates.
- `static/img/favicon.svg`, `favicon-32.png`, `apple-touch-icon.png` — the
  mark on white for browser tabs.
- `static/img/og-image.png` (1200×630) — Ink field, mark and wordmark
  centered.
- `python tools/make_placeholders.py` regenerates the three PNGs from the
  mark's geometry (needs `pillow`, `fonttools`, `brotli` for the wordmark
  type).

The wordmark beside the mark is HTML text in the display face; if a single
SVG lockup is ever wanted, only the `.brand` block in `templates/base.html`
changes. To replace the mark entirely: swap the files, rerun the build,
nothing else.

**Per-issue share cards.** The build also generates a 1200×630 card for
every published issue at `dist/static/img/og/no-0XX.png` (Ink field, mono
issue number, title in the display serif) and points that issue's
`og:image`/`twitter:image` at it, so shared links don't all look identical.
Drawn directly with Pillow — pinned pip wheels, no system packages, no SVG
rasterizer. Non-issue pages keep the global `og-image.png`.

**Citations.** Every issue and analysis page carries a "Cite this" block
generated from front matter (`citation_name` in `site.yaml` + title, year,
number, canonical URL) — never hand-written.

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

## Licensing

Split, deliberately:

- **Root `LICENSE` (MIT)** covers the software only: `build.py`,
  `templates/`, `static/css/`, `static/js/`, `tools/`, and the deploy
  workflow.
- **`content/LICENSE` (all rights reserved)** covers the written work in
  `content/` and the visual identity assets in `static/img/`. Quotation with
  attribution is welcome under normal fair use; anything more requires
  permission via the contact page. The About page's "Permissions" section
  states the same in plain language.

**Do not apply a Creative Commons license to the content.** CC licenses are
irrevocable, and there is a pending journal submission plus an unpublished
dissertation whose publishers may require transferable rights.

## Deploy — GitHub Pages

Deployment is automatic: `.github/workflows/deploy.yml` builds on every push
to `main` (Python 3.12, pinned requirements) and publishes `dist/` via
`actions/deploy-pages`. Two output files GitHub Pages depends on, both
produced by `build.py`:

- `dist/CNAME` (sourced from `static/CNAME`) — keeps the custom domain
  `thresholddatasciences.com` from resetting on each deploy.
- `dist/.nojekyll` — stops GitHub running Jekyll over the output, which
  would drop files and directories beginning with an underscore.

One-time setup in the GitHub repo: **Settings → Pages → Source: GitHub
Actions**, then set the custom domain and enable **Enforce HTTPS** once the
certificate issues. DNS (wherever the domain is managed): apex A records to
GitHub Pages (185.199.108.153, .109.153, .110.153, .111.153) and, if wanted,
`www` CNAME to `ts2427.github.io` — replacing the current Squarespace
forward.

**Contact is a form** posting via FormSubmit (formsubmit.co) to the address
in `site.yaml` `contact_form_action` — interim target is the PSC address
(Tim's choice, 2026-08-25) until the new Threshold address is wired in;
swapping is that one line plus FormSubmit's one-time activation click in the
receiving inbox. `contact_email`, when set, also shows on the page and joins
the JSON-LD Organization schema. The privacy policy describes the form and
FormSubmit; keep it in sync with any change here.

Analytics: none, deliberately. If a counter is ever wanted, use a cookieless
one (e.g. GoatCounter) and update `/privacy/` first.

## Accessibility audit

`python tools/a11y_audit.py` serves `dist/` locally and runs **axe-core
4.10.2** (WCAG 2.0/2.1/2.2 A+AA + best-practice rulesets) in headless Chrome
against 11 representative pages. (axe via Selenium is used because the build
machine has Python and Chrome but not Node; the ruleset is the same engine
pa11y uses.)

**Result, 2026-08-25 (after revision pass 2): PASS — 0 violations across
all 10 pages audited** (home, archive, issue No. 011, analysis, research,
advisory, about, contact, privacy, 404).

Manual checks in the same pass: skip-to-content link, visible focus states,
logical tab order, `prefers-reduced-motion` honored (no motion exists), no
horizontal scroll at 360px, all color token pairs ≥ 4.5:1 for text.

Re-run the audit after any template or CSS change.

**Manual pre-launch checklist** — automated tools catch roughly a third to a
half of real accessibility problems. Before launch, and after any redesign,
a human verifies:

- [ ] Tab through every page: focus always visible, order logical, the
      skip-to-content link appears on first Tab and works.
- [ ] Zoom to 200% in the browser: no clipped text, no horizontal scroll.
- [ ] Look at the muted white text on the Ink header and footer: readable by
      eye, not just by the computed ratios (~8.8:1 body, ~6.5:1 fine print).
- [ ] Read each page by its headings alone (screen-reader rotor or an
      outline extension): the outline should make sense on its own.
- [ ] Open the site at 360px width on an actual phone, not just a resized
      desktop window.
- [ ] Print an issue page to PDF: nav and step rules gone, link URLs shown,
      citation block present.

## Redirects — handled outside this repo

Hosting is GitHub Pages, which has no server-side redirects, so **there is
no redirects file here and the URLs in this repo are permanent — do not
restructure `/threshold-effects/no-0XX/` after launch.**

The `timothydspivey.com` → `thresholddatasciences.com` redirects — the old
`/threshold/` page and the old blog post URLs — are configured wherever the
personal site is hosted, not in this repo. The personal site is also GitHub
Pages, so its old pages get canonical/meta-refresh stubs (`<link
rel="canonical">` to the new URL plus `<meta http-equiv="refresh">`) in the
personal site's repo once this site is live.

**The issue numbers in this table are UNVERIFIED** — they came from an
earlier reconstruction that revision pass 2 found to be wrong in at least
two places (the say-something/build-something piece is No. 010, and No. 009
was a different piece). Confirm every number against the published record
when backfilling the issues, and correct this table at the same time. Only
the No. 011 row is verified.

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

Done (2026-08-25 go-live pass):

- [x] License split (MIT for software, all-rights-reserved for content) with
      an About-page Permissions section.
- [x] GitHub Pages deployment workflow, `dist/CNAME`, `dist/.nojekyll`,
      pinned `requirements.txt`.
- [x] Netlify/Cloudflare remnants removed (`_redirects`, form backend); the
      contact page is a plain `mailto:` link and the privacy policy matches.
- [x] Contact address single-sourced in `site.yaml` with a loud build
      warning while unset.
- [x] Verification pass: clean build, axe audit, checks below.

Remaining:

- [ ] **DNS cutover — the only launch blocker.** GitHub Pages already
      serves the site and has the custom domain attached (the interim URL
      301s to thresholddatasciences.com). In Squarespace: remove the domain
      forward to www.timothydspivey.com, add the four apex A records (see
      Deploy above), then Enforce HTTPS in GitHub Pages settings.
- [ ] **Swap the contact form target** to the new Threshold email (created;
      address to be wired later) — one line in `site.yaml`
      (`contact_form_action`) + FormSubmit activation click in that inbox.
- [ ] Inline source links in issue bodies (all 11 carry the published text;
      citations are not yet hyperlinked inline).
- [ ] ORCID iD in `site.yaml` for the Person schema `sameAs`.
- [ ] After DNS cutover: validate the live feed with the W3C Feed
      Validator; reconcile the personal site (consulting section shrinks to
      a pointer here, `/threshold/` redirects here, old blog posts get
      canonical stubs per the mapping above).

Resolved 2026-08-25 (archive restore): all 11 issues are published,
restored verbatim from the blog record at timothydspivey.com/blog — whose
post footers carry the series numbering — so the redirect mapping table
above is now verified against that record. The axe audit re-run after the
restore and the contact form: PASS, 0 violations.

Resolved in the design revision pass (2026-08-25): both ISACA Journal
entries now link to their isaca.org pages; the publication record is two
articles (security culture; shadow IT governance) — consistent across the
About page, Research page, and the revised brief; the step-function mark is
the final logo (see "The logo" above).

Reconciliation with the personal site (from the build brief §11 — Tim's to
action, listed here so they aren't lost):

- [ ] **Service-line conflict.** The personal site's consulting section and
      `/threshold/` page describe three service lines; this site launches
      with two. Shrink the personal site's consulting section to a pointer
      at this domain, and redirect `/threshold/` here.
- [ ] **Email routing.** The personal site's contact form (including its
      "Consulting Engagement" topic) posts to a Pensacola State address via
      formsubmit.co. Move business inquiries to the Threshold address.
- [ ] **Publication count.** Two ISACA Journal articles, both published —
      the count is accurate on both sites, no discrepancy to fix. The
      personal site's stat counter should still come off (a two-item counter
      undersells rather than sells).
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
means removing that forward and pointing the domain's DNS at GitHub Pages
(see Deploy above).
