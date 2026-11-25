#!/usr/bin/env python3
"""Static site generator for Threshold Data Sciences.

    python build.py           # regenerates ./dist from content/, templates/, static/

Adding a Threshold Effects issue = drop one .md file in content/threshold-effects/
and rerun. The archive, homepage latest-issues block, RSS feed, and sitemap are
all derived from the content directory. Nothing is hand-indexed.

Front matter is YAML between --- fences; body is Markdown (footnotes, tables,
attr_list, toc enabled). `draft: true` excludes a file from all output.
"""

import html
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

import figures as figlib

HERE = Path(__file__).parent
CONTENT = HERE / "content"
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"
DIST = HERE / "dist"

MD_EXTENSIONS = ["footnotes", "attr_list", "toc", "tables", "md_in_html"]  # md_in_html: markdown inside <details markdown="1">

env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ---------------------------------------------------------------- helpers ----

def load_yaml(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def parse_md(path):
    """Split YAML front matter from Markdown body; return (meta, html_body)."""
    # utf-8-sig: a stray BOM (e.g. from a Windows editor) must not silently
    # disable front-matter parsing.
    text = Path(path).read_text(encoding="utf-8-sig")
    # An author's note may sit above the front matter as a single HTML
    # comment line (e.g. "<!-- Have counsel review ... -->"). It is a
    # source-file note only and never reaches the output.
    text = re.sub(r"\A\s*<!--.*?-->[ \t]*\r?\n", "", text, count=1,
                  flags=re.S)
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2]
    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    html_body = md.convert(body.strip())
    # Wide tables scroll inside their own focusable region on small screens
    # instead of widening the page (no horizontal page scroll at 375px).
    # Each region gets a unique accessible name (landmarks must be unique).
    counter = iter(range(1, 10_000))
    html_body = re.sub(
        r"<table>", lambda _: '<div class="table-scroll" tabindex="0" role="region" '
                              f'aria-label="Table {next(counter)} (scrolls horizontally)"><table>',
        html_body)
    html_body = html_body.replace("</table>", "</table></div>")
    return meta, html_body


def fmt_date(d):
    """'August 24, 2026' — no zero-padding, portable across platforms."""
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def iso_date(d):
    if isinstance(d, str):
        return d
    return d.isoformat()


def rfc822(d):
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d").date()
    dt = datetime(d.year, d.month, d.day, 12, 0, 0)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


def write(relpath, content):
    out = DIST / relpath
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print("wrote", relpath)


def jsonld_graph(extra=None):
    """The page's JSON-LD, built as Python dicts and emitted with json.dumps
    so the serialization is always well-formed (malformed schema fails
    silently in the wild — nothing warns you)."""
    base = SITE["base_url"]
    author = SITE["author"]
    org = {
        "@type": "Organization",
        "@id": f"{base}/#organization",
        "name": SITE["name"],
        "url": f"{base}/",
        "founder": {"@id": f"{base}/#person"},
        "description": SITE["description"],
    }
    if SITE.get("contact_email"):
        org["email"] = SITE["contact_email"]
    person = {
        "@type": "Person",
        "@id": f"{base}/#person",
        "name": author["name"],
        "url": f"{base}/about/",
        "jobTitle": author["job_title"],
        "knowsAbout": author["knows_about"],
        "affiliation": {"@id": f"{base}/#organization"},
        "sameAs": [u for u in (author.get("linkedin"), author.get("scholar"),
                               author.get("orcid"), author.get("personal_site"))
                   if u],
    }
    graph = [org, person]
    if extra:
        graph.extend(extra if isinstance(extra, list) else [extra])
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      indent=2)


def article_node(view, in_series=False):
    base = SITE["base_url"]
    node = {
        "@type": "Article",
        "headline": view["title"],
        "description": view.get("summary", ""),
        "datePublished": view["iso_date"],
        "url": base + view["url"],
        "author": {"@id": f"{base}/#person"},
        "publisher": {"@id": f"{base}/#organization"},
    }
    if view.get("iso_updated"):
        node["dateModified"] = view["iso_updated"]
    if in_series:
        node["isPartOf"] = {
            "@type": "CreativeWorkSeries",
            "name": "Threshold Effects",
            "url": f"{base}/threshold-effects/",
        }
    return node


def dataset_node(view):
    """schema.org Dataset for a page whose front matter has a `dataset` block (data archived with a DOI)."""
    base, d = SITE["base_url"], view["dataset"]
    orcid = SITE["author"].get("orcid")
    return {
        "@type": "Dataset",
        "@id": f"{base}{view['url']}#dataset",
        "name": d["name"],
        "description": d["description"],
        "keywords": d["keywords"],
        "url": f"https://doi.org/{d['concept_doi']}",
        "sameAs": [f"https://doi.org/{d['version_doi']}", d["repository"]],
        "identifier": [
            {"@type": "PropertyValue", "propertyID": "DOI", "value": d["version_doi"],
             "url": f"https://doi.org/{d['version_doi']}", "description": f"version {d['version']}"},
            {"@type": "PropertyValue", "propertyID": "DOI", "value": d["concept_doi"],
             "url": f"https://doi.org/{d['concept_doi']}", "description": "all versions"},
        ],
        "version": d["version"],
        "license": d["license"],
        "isAccessibleForFree": True,
        "creator": {"@type": "Person", "@id": f"{base}/#person", "name": SITE["author"]["name"],
                    **({"sameAs": orcid, "identifier": orcid} if orcid else {})},
        "temporalCoverage": d["temporal_coverage"],
        "spatialCoverage": [{"@type": "Place", "name": f"{s}, United States"} for s in d["spatial_coverage"]],
        "variableMeasured": [{"@type": "PropertyValue", "name": v["name"], "description": v["description"],
                              **({"unitText": v["unit"]} if v["unit"] else {})} for v in d["variables"]],
        "distribution": [{"@type": "DataDownload", "encodingFormat": d["distribution"]["format"],
                          "contentUrl": d["distribution"]["url"],
                          "contentSize": f"{d['distribution']['bytes']} bytes"}]
                        + ([{"@type": "DataDownload", "name": d["panel_csv"]["name"],
                             "encodingFormat": d["panel_csv"]["format"],
                             "contentUrl": f"{base}{d['panel_csv']['path']}",
                             "contentSize": f"{d['panel_csv']['bytes']} bytes"}] if d.get("panel_csv") else []),
        "includedInDataCatalog": {"@type": "DataCatalog", "name": "Zenodo", "url": "https://zenodo.org"},
        "subjectOf": {"@id": f"{base}{view['url']}#article"},
    }


def collection_node(name, path, description):
    base = SITE["base_url"]
    return {
        "@type": "CollectionPage",
        "name": name,
        "url": base + path,
        "description": description,
        "isPartOf": {"@id": f"{base}/#organization"},
        "author": {"@id": f"{base}/#person"},
    }


def render(template, relpath, schema_extra=None, **ctx):
    tpl = env.get_template(template)
    write(relpath, tpl.render(site=SITE, jsonld=jsonld_graph(schema_extra),
                              **ctx))


# ----------------------------------------------------------------- config ----

SITE = load_yaml(HERE / "site.yaml")
SITE["year"] = date.today().year
# Production only: the deploy workflow sets SITE_ENV=production. Local builds, previews, audits and tests leave
# the Google Analytics tag out (templates/_analytics.html), so they never send hits to the live property.
SITE["production"] = os.environ.get("SITE_ENV") == "production"

if not SITE.get("contact_email") and not SITE.get("contact_form_action"):
    print("=" * 70)
    print("WARNING: neither contact_email nor contact_form_action is set in")
    print("site.yaml — the contact page has no working contact channel.")
    print("DO NOT SHIP THIS BUILD.")
    print("=" * 70)


def _is_placeholder(v):
    return not str(v or "").strip() or "TODO" in str(v)


# Prices: shown only when show_prices is true; the range line additionally
# needs both ends filled in (never renders a TODO).
SITE["show_prices"] = bool(SITE.get("show_prices"))
SITE["show_price_range"] = (
    SITE["show_prices"]
    and not _is_placeholder(SITE.get("price_range_low"))
    and not _is_placeholder(SITE.get("price_range_high")))

DEMO_TAG = "Demonstration · Public data · Not client work"
WORK_LABEL = "Demonstrations built on public data. None is client work."  # said once, at the top of /work/
FEATURED_LABEL = "Demonstration · Public data"  # the home page's featured example stands alone there
WORK_MARKERS = ("Open dataset", "DOI", "Reproducible code", "Datasheet")  # shown only where true
SITE["demo_tag"] = DEMO_TAG

if "pensacolastate" in SITE.get("contact_form_action", ""):
    print("NOTE: contact box delivers to the PSC address (interim). Swap")
    print("site.yaml contact_form_action to the Threshold Data Sciences")
    print("address once it exists.")


# ---------------------------------------------------------------- content ----

def _reject_placeholders(meta, path):
    """A non-draft issue with placeholder metadata must never publish.

    This site's claim is a citable record cross-linked to public posts;
    plausible-looking wrong metadata is worse than an obvious gap. Files with
    placeholders may sit in the repo, but only as draft: true.
    """
    problems = []
    if "TBC" in str(meta.get("title", "")):
        problems.append("title contains TBC")
    if "TODO" in str(meta.get("summary", "")):
        problems.append("summary contains TODO")
    if not meta.get("date"):
        problems.append("date is missing")
    if problems:
        sys.exit(
            f"BUILD FAILED: {path.name} is published (not draft: true) but "
            f"still has placeholder metadata: {'; '.join(problems)}.\n"
            "Fill in verified values from the published record, or mark the "
            "file draft: true."
        )


DATA_DIR = CONTENT / "data"
_unverified_figures = []   # (file, fig id) on non-draft pages — fails build
_figure_count = 0
_public_csvs = set()       # data_public CSVs to copy into dist/static/data/


def _process_figures(meta, body, path):
    """Render each front-matter figure to inline SVG and place it in the
    body — at its [figure:fig-id] marker if present, else appended.

    Verification guard: figures carry a stronger claim than prose, so a
    figure on a published (non-draft) page with verified: false FAILS the
    build. Data may sit in content/data/ while it is checked against the
    primary source; it cannot ship unverified by accident."""
    global _figure_count
    for fig in meta.get("figures", []) or []:
        if not fig.get("verified"):
            _unverified_figures.append(f"{path.name}: {fig.get('id', '?')}")
            continue
        html_block = figlib.render_figure(fig, DATA_DIR)
        _figure_count += 1
        if fig.get("data_public"):
            _public_csvs.add(fig["data"])
        marker = f'<p>[figure:{fig["id"]}]</p>'
        if marker in body:
            body = body.replace(marker, html_block)
        else:
            body += html_block
    return body


def _citation(meta, container):
    """APA-style citation string, generated from front matter only."""
    title = str(meta["title"]).rstrip()
    if title[-1:] not in ".?!":
        title += "."
    year = meta["iso_date"][:4]
    return (f"{SITE['author']['citation_name']} ({year}). {title} "
            f"{container}{SITE['name']}. {SITE['base_url']}{meta['url']}")


def load_issues():
    """Returns (published issues, draft slugs). Drafts appear in NO output;
    the slugs are kept so the build can verify they never leak."""
    issues, draft_slugs = [], []
    for path in sorted((CONTENT / "threshold-effects").glob("*.md")):
        meta, body = parse_md(path)
        n = int(meta["number"])
        if meta.get("draft"):
            draft_slugs.append(f"no-{n:03d}")
            continue
        _reject_placeholders(meta, path)
        meta["number_label"] = f"No. {n:03d}"
        meta["slug"] = f"no-{n:03d}"
        meta["url"] = f"/threshold-effects/{meta['slug']}/"
        meta["body"] = _process_figures(meta, body, path)
        meta["display_date"] = fmt_date(meta["date"])
        meta["iso_date"] = iso_date(meta["date"])
        if meta.get("updated") and iso_date(meta["updated"]) != meta["iso_date"]:
            meta["display_updated"] = fmt_date(meta["updated"])
            meta["iso_updated"] = iso_date(meta["updated"])
        meta["citation"] = _citation(
            meta, f"Threshold Effects, {meta['number_label']}. ")
        issues.append(meta)
    issues.sort(key=lambda m: m["number"], reverse=True)
    return issues, draft_slugs


TOC_CHAPTER = re.compile(r"\d+\.\s")  # numbered chapters ("1. Anatomy of a storm") are listed under their part


def page_toc(body: str) -> list:
    """"On this page" entries for a page with `toc: true`: every h2, with the numbered h3 chapters under it, and How to
    cite where the template places it (the cite_inline marker). Built from the rendered headings, so it can't drift."""
    body = body.replace("<!-- how-to-cite -->", '<h2 id="how-to-cite">How to cite</h2>')
    toc = []
    for level, hid, inner in re.findall(r'<h([23]) id="([^"]+)">(.*?)</h\1>', body, flags=re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        if level == "2":
            toc.append({"id": hid, "text": text, "children": []})
        elif TOC_CHAPTER.match(text) and toc:
            toc[-1]["children"].append({"id": hid, "text": text})
    return toc


def load_analysis():
    pieces, draft_slugs = [], []
    for path in sorted((CONTENT / "analysis").glob("*.md")):
        meta, body = parse_md(path)
        if meta.get("draft"):
            draft_slugs.append(path.stem)
            continue
        meta["slug"] = path.stem
        meta["url"] = f"/analysis/{meta['slug']}/"
        meta["body"] = _process_figures(meta, body, path)
        if meta.get("toc"):
            meta["toc"] = page_toc(meta["body"])
        meta["display_date"] = fmt_date(meta["date"])
        meta["iso_date"] = iso_date(meta["date"])
        if meta.get("updated") and iso_date(meta["updated"]) != meta["iso_date"]:
            meta["display_updated"] = fmt_date(meta["updated"])
            meta["iso_updated"] = iso_date(meta["updated"])
        meta["citation"] = _citation(meta, "")
        pieces.append(meta)
    pieces.sort(key=lambda m: m["iso_date"], reverse=True)
    return pieces, draft_slugs


def load_pages():
    pages = {}
    for path in sorted((CONTENT / "pages").glob("*.md")):
        meta, body = parse_md(path)
        if meta.get("draft"):
            continue
        if "TODO" in body:
            sys.exit(
                f"BUILD FAILED: pages/{path.name} is published (not "
                "draft: true) but its body still contains TODO text. "
                "Replace the TODO blocks or mark the page draft: true."
            )
        meta["body"] = body
        pages[path.stem] = meta
    return pages


def load_services():
    data = load_yaml(CONTENT / "services.yaml")
    services = data.get("services", [])
    for svc in services:
        svc["url"] = f"/services/#{svc['slug']}"
    return services, data.get("entry_offers", [])


def audit_numbers(path):
    """The OSHA audit's own output (demos/results/osha_audit.json): the counts its Work card states."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    strata = d["step3d_estimate"]["main"]["y_counts"].values()
    return {"raw_names": d["step2_naive"]["distinct_raw_employer_names"],
            "final_employers": d["step3c_final"]["final_counts"]["by_name"],
            "labeled_pairs": sum(n for _, n in strata)}


def fill_what(text, path):
    """A Work card's "what it is" line with its numbers taken from the example's output file, never typed."""
    nums = {k: f"{v:,}" for k, v in audit_numbers(path).items()}
    out = text.format(**nums)
    if "{" in out or "}" in out:
        sys.exit(f"BUILD FAILED: unfilled number in work.yaml what line: {out!r}")
    return out


def load_work(services, analysis):
    """Worked examples from work.yaml plus every published analysis page.
    in_progress items are kept apart and never presented as finished; a
    TODO target date is simply not shown."""
    by_question = {s["question"]: s for s in services}
    live, in_progress = [], []
    for item in load_yaml(CONTENT / "work.yaml") or []:
        status = item.get("status")
        if status not in ("live", "in_progress"):
            sys.exit(f"BUILD FAILED: work.yaml item {item.get('title')!r} has "
                     f"status {status!r}; use live or in_progress.")
        q = item.get("question")
        if q not in by_question:
            sys.exit(f"BUILD FAILED: work.yaml item {item.get('title')!r} "
                     f"question {q!r} matches no service in services.yaml.")
        for field in ("title", "summary", "data_note", "url", "what"):
            if "TODO" in str(item.get(field) or ""):
                sys.exit(f"BUILD FAILED: work.yaml item {item.get('title')!r} "
                         f"has TODO in {field}.")
        if status == "live" and not item.get("url"):
            sys.exit(f"BUILD FAILED: live work item {item.get('title')!r} "
                     "has no url.")
        item["service"] = by_question[q]
        if _is_placeholder(item.get("target_date")):
            item["target_date"] = ""
        item["methods"] = item.get("methods") or []
        if item.get("what_numbers"):
            item["what"] = fill_what(item["what"], HERE / item["what_numbers"])
        item["markers"] = item.get("markers") or []
        bad = [m for m in item["markers"] if m not in WORK_MARKERS]
        if bad:
            sys.exit(f"BUILD FAILED: work.yaml item {item.get('title')!r} has unknown markers {bad}; "
                     f"use only {WORK_MARKERS}.")
        (live if status == "live" else in_progress).append(item)
    listed = {w.get("url") for w in live + in_progress}
    for piece in analysis:
        if piece["url"] in listed:      # already in work.yaml (with its question)
            continue
        live.append({
            "title": piece["title"], "url": piece["url"],
            "question": piece.get("question", ""),
            "service": by_question.get(piece.get("question")),
            "summary": piece.get("summary", ""),
            "methods": piece.get("methods_list", []) or [],
            "data_note": "", "status": "live", "target_date": "",
        })
    return live, in_progress


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


# ------------------------------------------------------------------ feeds ----

def build_rss(issues):
    base = SITE["base_url"]
    items = []
    for i in issues:
        items.append(
            "<item>"
            f"<title>{html.escape(i['number_label'] + ' — ' + i['title'])}</title>"
            f"<link>{base}{i['url']}</link>"
            f'<guid isPermaLink="true">{base}{i["url"]}</guid>'
            f"<pubDate>{rfc822(i['date'])}</pubDate>"
            f"<description>{html.escape(i.get('summary', ''))}</description>"
            "</item>"
        )
    last_build = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S GMT")
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>Threshold Effects</title>"
        f"<link>{base}/threshold-effects/</link>"
        f'<atom:link href="{base}/threshold-effects/feed.xml" rel="self" '
        'type="application/rss+xml"/>'
        f"<description>{html.escape(SITE['series_description'])}</description>"
        "<language>en-us</language>"
        f"<lastBuildDate>{last_build}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )
    write("threshold-effects/feed.xml", rss)


def build_sitemap(urls):
    base = SITE["base_url"]
    entries = "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls)
    write(
        "sitemap.xml",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + entries
        + "</urlset>\n",
    )


def build_robots():
    write(
        "robots.txt",
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE['base_url']}/sitemap.xml\n",
    )


# --------------------------------------------------- per-issue social cards --

INK_RGB = (15, 35, 56)
CARD_MUTED = (184, 190, 195)   # 72% white over Ink
CARD_W, CARD_H = 1200, 630


def _ttf(woff2_name):
    """Convert a shipped woff2 to a cached TTF Pillow can load (fonttools +
    brotli — pure pip wheels, no system packages)."""
    from fontTools.ttLib import TTFont
    out = Path(tempfile.gettempdir()) / f"tds-{woff2_name}.ttf"
    if not out.exists():
        f = TTFont(STATIC / "fonts" / woff2_name)
        f.flavor = None
        f.save(out)
    return out


def _wrap(draw, text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def issue_card(issue):
    """1200x630 share card: Ink field, mono issue number, serif title."""
    from PIL import Image, ImageDraw, ImageFont
    serif = ImageFont.truetype(str(_ttf("source-serif-4-600.woff2")), 76)
    mono = ImageFont.truetype(str(_ttf("ibm-plex-mono-500.woff2")), 34)

    img = Image.new("RGB", (CARD_W, CARD_H), INK_RGB)
    d = ImageDraw.Draw(img)
    margin = 90
    d.text((margin, 110), f"{issue['number_label'].upper()}  ·  THRESHOLD EFFECTS",
           font=mono, fill=CARD_MUTED)
    lines = _wrap(d, issue["title"], serif, CARD_W - 2 * margin)
    if len(lines) > 3:
        serif = ImageFont.truetype(str(_ttf("source-serif-4-600.woff2")), 58)
        lines = _wrap(d, issue["title"], serif, CARD_W - 2 * margin)
    y = 210
    for line in lines:
        d.text((margin, y), line, font=serif, fill=(255, 255, 255))
        y += int(serif.size * 1.22)
    out = DIST / "static" / "img" / "og" / f"{issue['slug']}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return f"/static/img/og/{issue['slug']}.png"


# ------------------------------------------------------------------ build ----

def _verify_drafts_excluded(draft_slugs):
    """Regression check: draft slugs must appear nowhere in the output."""
    if not draft_slugs:
        print("draft check: no drafts in content/")
        return
    haystacks = [DIST / "sitemap.xml", DIST / "threshold-effects" / "feed.xml",
                 DIST / "index.html", DIST / "threshold-effects" / "index.html"]
    # Category pages and issue pages (related-issue blocks) are also surfaces
    # a draft could leak into.
    haystacks += list((DIST / "threshold-effects").rglob("index.html"))
    haystacks += [DIST / "work" / "index.html", DIST / "analysis" / "index.html"]
    leaks = []
    for slug in draft_slugs:
        for hay in haystacks:
            if hay.exists() and f"/{slug}/" in hay.read_text(encoding="utf-8"):
                leaks.append(f"{slug} referenced in {hay.relative_to(DIST)}")
        if (DIST / "threshold-effects" / slug).exists() or \
                (DIST / "analysis" / slug).exists():
            leaks.append(f"{slug} has a rendered page in dist/")
    if leaks:
        sys.exit("BUILD FAILED: draft content leaked into output:\n  "
                 + "\n  ".join(leaks))
    print(f"draft check: {len(draft_slugs)} draft file(s) verified absent "
          "from sitemap, feed, homepage, archive, and rendered pages")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    issues, issue_drafts = load_issues()
    analysis, analysis_drafts = load_analysis()

    # Figure verification guard (see _process_figures).
    if _unverified_figures:
        sys.exit(
            "BUILD FAILED: figures with verified: false on published "
            "(non-draft) pages:\n  " + "\n  ".join(_unverified_figures)
            + "\nCheck each dataset against its primary source, then set "
            "verified: true — or mark the page draft: true."
        )
    print(f"figure check: {_figure_count} verified figure(s) rendered, "
          "0 unverified on published pages")

    pages = load_pages()
    SITE["has_methods"] = "methods" in pages
    research = load_yaml(CONTENT / "research.yaml") or []
    research_html = env.get_template("_research_list.html").render(
        research=research)
    for page in pages.values():
        page["body"] = page["body"].replace("<p>[research-list]</p>",
                                            research_html)
    services, entry_offers = load_services()
    work_live, work_in_progress = load_work(services, analysis)
    questions_with_work = {w["question"] for w in work_live}
    featured = [w for w in work_live if w.get("featured")]
    if len(featured) != 1:
        sys.exit(f"BUILD FAILED: work.yaml must mark exactly one live item featured (found {len(featured)}).")
    question_examples = {}  # the home page's question cards link to their own example
    for w in work_live:
        if w.get("home_card"):
            if w["question"] in question_examples:
                sys.exit(f"BUILD FAILED: two home_card examples for {w['question']!r}.")
            question_examples[w["question"]] = w["url"]
    press = load_yaml(CONTENT / "press.yaml") or []

    # Category cross-links (from content, never hardcoded).
    for i in issues:
        if i.get("category"):
            i["category_url"] = (f"/threshold-effects/category/"
                                 f"{slugify(i['category'])}/")

    urls = ["/"]

    # Home
    render("home.html", "index.html",
           issues=issues[:2], press=press, services=services,
           entry_offers=entry_offers,
           featured=featured[0], featured_label=FEATURED_LABEL,
           question_examples=question_examples,
           questions_with_work=questions_with_work, page_url="/")

    # Services
    render("services.html", "services/index.html",
           services=services, entry_offers=entry_offers,
           questions_with_work=questions_with_work, page_url="/services/",
           schema_extra=collection_node(
               "Services", "/services/",
               "Impact & Evaluation Analysis, Data & Measurement Audit, and "
               "Predictive & Retention Models from Threshold Data Sciences."))
    urls.append("/services/")

    # Work
    render("work.html", "work/index.html",
           live=work_live, in_progress=work_in_progress, work_label=WORK_LABEL, page_url="/work/",
           schema_extra=collection_node(
               "Work", "/work/",
               "Worked examples on public data from Threshold Data Sciences."))
    urls.append("/work/")

    # Threshold Effects archive + issues
    categories = sorted({i["category"] for i in issues if i.get("category")})
    render("te_index.html", "threshold-effects/index.html",
           issues=issues, categories=categories,
           page_url="/threshold-effects/",
           schema_extra=collection_node(
               "Threshold Effects", "/threshold-effects/",
               SITE["series_description"]))
    urls.append("/threshold-effects/")
    for idx, issue in enumerate(issues):
        newer = issues[idx - 1] if idx > 0 else None
        older = issues[idx + 1] if idx + 1 < len(issues) else None
        related = [i for i in issues
                   if i.get("category") == issue.get("category")
                   and i["slug"] != issue["slug"]][:3] \
            if issue.get("category") else []
        render("issue.html", f"threshold-effects/{issue['slug']}/index.html",
               issue=issue, newer=newer, older=older, related=related,
               page_url=issue["url"],
               og_image=f"/static/img/og/{issue['slug']}.png",
               schema_extra=article_node(issue, in_series=True))
        urls.append(issue["url"])

    # Category pages — only categories with published issues.
    for cat in categories:
        cat_issues = [i for i in issues if i.get("category") == cat]
        cat_url = f"/threshold-effects/category/{slugify(cat)}/"
        render("category.html",
               f"threshold-effects/category/{slugify(cat)}/index.html",
               category=cat, issues=cat_issues, page_url=cat_url,
               schema_extra=collection_node(
                   f"Threshold Effects — {cat}", cat_url,
                   f"Threshold Effects issues in the {cat} category."))
        urls.append(cat_url)

    # Analysis
    render("analysis_index.html", "analysis/index.html",
           pieces=analysis, page_url="/analysis/",
           schema_extra=collection_node(
               "Analysis", "/analysis/",
               "Longer data work from Threshold Data Sciences: named "
               "sources and visible methods notes."))
    urls.append("/analysis/")
    for piece in analysis:
        extra = article_node(piece)
        if piece.get("dataset"):
            extra = [{**extra, "@id": f"{SITE['base_url']}{piece['url']}#article",
                      "isBasedOn": {"@id": f"{SITE['base_url']}{piece['url']}#dataset"}}, dataset_node(piece)]
        render("analysis.html", f"analysis/{piece['slug']}/index.html",
               piece=piece, page_url=piece["url"],
               schema_extra=extra)
        urls.append(piece["url"])

    # Retired URLs: meta-refresh + canonical stubs (GitHub Pages has no
    # server-side redirects). Not in the sitemap.
    for old, new, label in (("/advisory/", "/services/", "Services"),
                            ("/research/", "/about/#writing", "Writing")):
        tpl = env.get_template("redirect.html")
        write(old.strip("/") + "/index.html",
              tpl.render(site=SITE, target=new, label=label))

    # Markdown-driven pages
    for slug, page in pages.items():
        tpl = page.get("template", "page.html")
        render(tpl, f"{slug}/index.html", page=page, page_url=f"/{slug}/")
        urls.append(f"/{slug}/")

    # Contact-form landing page (noindex, excluded from sitemap)
    if SITE.get("contact_form_action"):
        render("thanks.html", "contact/thanks/index.html",
               page_url="/contact/thanks/")

    # 404
    render("404.html", "404.html", page_url="/404.html")

    build_rss(issues)
    build_sitemap(urls)
    build_robots()

    # Static assets. CNAME is copied to the output root separately (GitHub
    # Pages requires it there to keep the custom domain across deploys).
    shutil.copytree(STATIC, DIST / "static",
                    ignore=shutil.ignore_patterns("CNAME"))
    for fav in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png"):
        src = STATIC / "img" / fav
        if src.exists():
            shutil.copy(src, DIST / fav)
    cname = STATIC / "CNAME"
    if cname.exists():
        shutil.copy(cname, DIST / "CNAME")
    # .nojekyll stops GitHub Pages running Jekyll over the output (Jekyll
    # would drop files and directories that begin with an underscore).
    (DIST / ".nojekyll").write_text("")

    # Per-issue share cards (after copytree so dist/static exists).
    for issue in issues:
        issue_card(issue)

    # Public datasets: only CSVs behind a verified, data_public figure.
    for name in sorted(_public_csvs):
        (DIST / "static" / "data").mkdir(parents=True, exist_ok=True)
        shutil.copy(DATA_DIR / name, DIST / "static" / "data" / name)
        print("wrote static/data/" + name)

    _verify_drafts_excluded(issue_drafts + analysis_drafts)

    print("Google Analytics tag: " + ("included (SITE_ENV=production)" if SITE["production"]
                                      else "left out (not a production build)"))
    print(f"\nBuilt {len(urls)} pages, {len(issues)} issues, "
          f"{len(analysis)} analysis pieces -> dist/")


if __name__ == "__main__":
    main()
