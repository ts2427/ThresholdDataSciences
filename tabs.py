"""Tabbed analysis pages (2026-11-28): the rendered page body regrouped into tab panels, without rewriting it.

Only build.py's rendered HTML is touched; the page's Markdown (written by the hurricane project's step 11) is not.
Each tab is a <section> with its own id, so a tab has a stable URL (#overview, #findings, ...), and every id the page
had before stays where it was inside its section. Without JavaScript every section shows in order under the table of
contents; static/js/page-sections.js turns the sections into a WAI-ARIA tab set.

The only words added are navigation: each tab's title, the cross-links between findings and their limitations, the
note where the peak chart moved, and pointers to files in the data repository. tests/test_page_tabs.py checks that
every sentence and every id of the untabbed page is still on the tabbed one.
"""
import html as htmllib
import re

DATA_REPO = "https://github.com/ts2427/when-the-network-goes-dark-data"
CITE_MARKER = "<!-- how-to-cite -->"

TABS = [("overview", "Overview"), ("findings", "Findings"), ("why-it-happens", "Why it happens"),
        ("data-and-methods", "Data & methods"), ("coverage-and-gaps", "Coverage & gaps"), ("versions", "Versions")]

# h2 section id -> tab, in the order each tab shows them
SECTIONS = {
    "overview": ["why-this-page-exists", "*fig-peaks", "what-it-adds-up-to", "look-up-a-county", "if-this-were-your-data"],
    "findings": ["map-where-cell-sites-were-out-report-by-report", "1-the-question-and-the-data",
                 "part-i-what-happens-when-the-network-goes-dark", "part-ii-why-it-goes-dark", "part-iii-who-waits-longest",
                 "part-iv-what-the-public-record-can-and-cant-tell-us", "*footnotes"],
    "why-it-happens": ["*why-backup-power-mandates-stalled", "references"],
    "data-and-methods": ["download-the-data", "*how-to-cite", "methods-data-and-licenses", "*data-repo-checks",
                         "related-work", "sources"],
    "coverage-and-gaps": ["*coverage-links", "*detail:Gap audit.", "*detail:Excluded reports"],
    "versions": ["*audit-trail", "*version-links"],
}

# each finding (chapter anchor) -> the limitations (method-detail summaries) that bear on it
LIMITS = {
    "2-anatomy-of-a-storm-isaias-october-2026": ["What the FCC's numbers measure.", "Times and censoring."],
    "3-how-much-goes-dark": ["What the FCC's numbers measure.", "Reading the reports."],
    "4-how-fast-it-comes-back": ["Times and censoring.", "Intervals."],
    "5-why-sites-go-dark": ["Cause-field limitations."],
    "6-the-power-coupling": ["EAGLE-I denominators."],
    "11-sites-on-backup-power": ["What the FCC's numbers measure."],
    "7-exposure": ["Exposure model (chapter 7), checked for calibration."],
    "8-who-waits-longest": ["Waiting-time model (chapter 8).", "Intervals."],
    "13-do-counties-with-more-mobile-providers-recover-differently": ["Mobile and fixed providers (chapter 9)."],
    "10-what-the-public-record-misses": ["Times and censoring."],
    "14-how-complete-are-the-fccs-public-reports": ["Validation."],
    "9-did-the-rules-help": ["Sensitivity displays."],
}

NAV = {  # pointers to files that are not on the page (navigation only)
    "data-repo-checks": (
        '<p class="xref">In the data repository: the reconciliation pass rates and the validation counts in '
        f'<a href="{DATA_REPO}/blob/release-4.0.0/DATASHEET.md">DATASHEET.md</a>; the external headline check in '
        f'<a href="{DATA_REPO}/blob/release-4.0.0/data/derived/external_headline_check.csv">'
        'data/derived/external_headline_check.csv</a>.</p>'),
    "coverage-links": (
        '<p class="xref">In the data repository: the storm coverage summary in '
        f'<a href="{DATA_REPO}/blob/release-4.0.0/docs/STORM_COVERAGE.md">docs/STORM_COVERAGE.md</a>, every event in '
        f'<a href="{DATA_REPO}/blob/release-4.0.0/docs/storm_inventory.csv">docs/storm_inventory.csv</a>, and the '
        f'search log in <a href="{DATA_REPO}/blob/release-4.0.0/docs/gap_audit_2026-11-28.md">'
        'docs/gap_audit_2026-11-28.md</a>.</p>'),
    "version-links": (
        '<p class="xref">In the data repository: the '
        f'<a href="{DATA_REPO}/blob/release-4.0.0/CHANGELOG.md">changelog</a>, the '
        f'<a href="{DATA_REPO}/blob/release-4.0.0/ERRATA.md">errata</a>, and the versioning rules in '
        f'<a href="{DATA_REPO}/blob/release-4.0.0/docs/update_procedure.md">docs/update_procedure.md</a>.</p>'),
}

TAB_PAGES = {"when-the-network-goes-dark"}


def _slug(text: str) -> str:
    return "limits-" + re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _text(fragment: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _block_end(body: str, start: int, levels=("h2",)) -> int:
    """The end of the block starting at `start`: the next heading of one of `levels`, the cite marker or the footnotes."""
    ends = [m.start() for lv in levels for m in [re.compile(rf"<{lv}\b").search(body, start + 1)] if m]
    for marker in (CITE_MARKER, '<div class="footnote">'):
        i = body.find(marker, start + 1)
        if i >= 0:
            ends.append(i)
    return min(ends) if ends else len(body)


def _cut(body: str, start: int, end: int) -> tuple:
    return body[:start] + body[end:], body[start:end]


def _details_span(body: str, start: int) -> int:
    """The end of the <details> element opening at `start` (nested details counted)."""
    depth, i = 0, start
    for m in re.finditer(r"<(/?)details\b[^>]*>", body[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start + m.end()
    raise ValueError("unbalanced <details>")


def split(body: str) -> dict:
    """The body's pieces by name: each h2 section, and the pieces moved out of them."""
    pieces = {}
    m = re.search(r'<figure class="chart" id="fig-peaks">', body)
    if m:
        end = body.index("</figure>", m.start()) + len("</figure>")
        body, pieces["*fig-peaks"] = _cut(body, m.start(), end)
        note = '<p class="xref">The peak-by-storm chart is in <a href="#fig-peaks">Overview</a>.</p>'
        body = body[:m.start()] + note + body[m.start():]
    m = re.search(r'<h3 id="why-backup-power-mandates-stalled">', body)
    if m:
        body, pieces["*why-backup-power-mandates-stalled"] = _cut(body, m.start(), _block_end(body, m.start(), ("h2",)))
    m = re.search(r'<h3 id="audit-trail">', body)
    if m:
        body, pieces["*audit-trail"] = _cut(body, m.start(), _block_end(body, m.start(), ("h2",)))
    for name in ("Gap audit.", "Excluded reports"):
        m = re.search(r'<details class="method-detail"[^>]*>\s*<summary>(?:<span[^>]*></span>)?' + re.escape(name), body)
        if m:
            body, pieces[f"*detail:{name}"] = _cut(body, m.start(), _details_span(body, m.start()))
    i = body.find('<div class="footnote">')
    if i >= 0:
        end = body.index("</div>", body.index("</ol>", i)) + len("</div>")
        body, pieces["*footnotes"] = _cut(body, i, end)
    i = body.find(CITE_MARKER)
    if i >= 0:
        body = body[:i] + body[i + len(CITE_MARKER):]
        pieces["*how-to-cite"] = CITE_MARKER
    pre = body[:body.find("<h2")] if "<h2" in body else body
    if pre.strip():
        pieces["*pre"] = pre
    for m in re.finditer(r'<h2 id="([^"]+)"', body):
        pieces[m.group(1)] = body[m.start():_block_end(body, m.start())]
    for k, v in NAV.items():
        pieces[f"*{k}"] = v
    return pieces


def cross_links(html: str) -> str:
    """Each finding links to its limitations; each limitation links back (navigation only)."""
    titles = {cid: _text(m.group(1)) for cid in LIMITS
              for m in [re.search(rf'<h3 id="{re.escape(cid)}">(.*?)</h3>', html, re.S)] if m}
    back = {}
    for cid, names in LIMITS.items():
        for n in names:
            back.setdefault(n, []).append(cid)
    # ids on the limitation details, then the back links inside them
    for name, cids in back.items():
        m = re.search(r'<details class="method-detail">\s*<summary>(?:<span[^>]*></span>)?(?:<em>Exploratory\.</em> )?'
                      + re.escape(name), html)
        if not m:
            raise ValueError(f"limitation not found: {name}")
        start = m.start()
        opening = '<details class="method-detail">'
        html = html[:start] + f'<details class="method-detail" id="{_slug(name)}">' + html[start + len(opening):]
        end = _details_span(html, start)
        links = ", ".join(f'<a href="#{c}">{htmllib.escape(titles[c])}</a>' for c in cids if c in titles)
        html = html[:end - len("</details>")] + f'<p class="xref">Back to the findings: {links}.</p>\n' + html[end - len("</details>"):]
    for cid, names in LIMITS.items():
        m = re.search(rf'<h3 id="{re.escape(cid)}">', html)
        if not m:
            raise ValueError(f"finding not found: {cid}")
        end = _block_end(html, m.start(), ("h2", "h3"))
        links = ", ".join(f'<a href="#{_slug(n)}">{htmllib.escape(n.rstrip("."))}</a>' for n in names)
        html = html[:end] + f'<p class="xref">Limitations (Data &amp; methods): {links}.</p>\n' + html[end:]
    return html


def tabify(body: str) -> str:
    pieces = split(body)
    used = {"*pre", "*how-to-cite"}
    out = []
    for tab, title in TABS:
        parts = [pieces.get("*pre", "")] if tab == "overview" else []
        for name in SECTIONS[tab]:
            if name not in pieces:
                raise ValueError(f"tabs: section not found on the page: {name}")
            parts.append(pieces[name])
            used.add(name)
        out.append(f'<section class="tab-panel" id="{tab}" aria-labelledby="{tab}-title">\n'
                   f'<h2 class="tab-title" id="{tab}-title">{htmllib.escape(title)}</h2>\n' + "\n".join(parts)
                   + "\n</section>")
    left = [k for k in pieces if k not in used]
    if left:
        raise ValueError(f"tabs: sections not placed in any tab: {left}")
    return cross_links("\n".join(out))


def toc(body: str) -> list:
    """The table of contents of a tabbed body: each tab, its h2 sections (with the numbered chapters under them) and
    the h3 sections that open a tab directly."""
    entries = []
    body = body.replace(CITE_MARKER, '<h2 id="how-to-cite">How to cite</h2>')  # where the template puts the cite block
    for m in re.finditer(r'<section class="tab-panel" id="([^"]+)"[^>]*>(.*?)</section>', body, re.S):
        tab, inner = m.group(1), m.group(2)
        title = dict(TABS)[tab]
        node = {"id": tab, "text": title, "children": []}
        for h in re.finditer(r'<h([23]) id="([^"]+)"[^>]*>(.*?)</h\1>', inner, re.S):
            level, hid, text = h.group(1), h.group(2), _text(h.group(3))
            if hid == f"{tab}-title":
                continue
            if level == "2":
                node["children"].append({"id": hid, "text": text, "children": []})
            elif re.match(r"\d+\.\s", text) and node["children"]:
                node["children"][-1]["children"].append({"id": hid, "text": text})
            elif not node["children"] or hid in ("why-backup-power-mandates-stalled", "audit-trail"):
                node["children"].append({"id": hid, "text": text, "children": []})
        entries.append(node)
    return entries
