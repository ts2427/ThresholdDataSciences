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
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).parent
CONTENT = HERE / "content"
TEMPLATES = HERE / "templates"
STATIC = HERE / "static"
DIST = HERE / "dist"

MD_EXTENSIONS = ["footnotes", "attr_list", "toc", "tables"]

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
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2]
    md = markdown.Markdown(extensions=MD_EXTENSIONS)
    return meta, md.convert(body.strip())


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
        graph.append(extra)
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

if not SITE.get("contact_email"):
    print("=" * 70)
    print("WARNING: site.yaml contact_email is NOT SET.")
    print("The contact page will render without an email address, and the")
    print("Organization schema will omit it. Set a Threshold Data Sciences")
    print("domain address before launch. DO NOT SHIP THIS BUILD.")
    print("=" * 70)


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


def load_issues():
    issues = []
    for path in sorted((CONTENT / "threshold-effects").glob("*.md")):
        meta, body = parse_md(path)
        if meta.get("draft"):
            continue
        _reject_placeholders(meta, path)
        n = int(meta["number"])
        meta["number_label"] = f"No. {n:03d}"
        meta["slug"] = f"no-{n:03d}"
        meta["url"] = f"/threshold-effects/{meta['slug']}/"
        meta["body"] = body
        meta["display_date"] = fmt_date(meta["date"])
        meta["iso_date"] = iso_date(meta["date"])
        if meta.get("updated") and iso_date(meta["updated"]) != meta["iso_date"]:
            meta["display_updated"] = fmt_date(meta["updated"])
            meta["iso_updated"] = iso_date(meta["updated"])
        issues.append(meta)
    issues.sort(key=lambda m: m["number"], reverse=True)
    return issues


def load_analysis():
    pieces = []
    for path in sorted((CONTENT / "analysis").glob("*.md")):
        meta, body = parse_md(path)
        if meta.get("draft"):
            continue
        meta["slug"] = path.stem
        meta["url"] = f"/analysis/{meta['slug']}/"
        meta["body"] = body
        meta["display_date"] = fmt_date(meta["date"])
        meta["iso_date"] = iso_date(meta["date"])
        if meta.get("updated") and iso_date(meta["updated"]) != meta["iso_date"]:
            meta["display_updated"] = fmt_date(meta["updated"])
            meta["iso_updated"] = iso_date(meta["updated"])
        pieces.append(meta)
    pieces.sort(key=lambda m: m["iso_date"], reverse=True)
    return pieces


def load_pages():
    pages = {}
    for path in sorted((CONTENT / "pages").glob("*.md")):
        meta, body = parse_md(path)
        if meta.get("draft"):
            continue
        meta["body"] = body
        pages[path.stem] = meta
    return pages


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
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
        f"<title>Threshold Effects</title>"
        f"<link>{base}/threshold-effects/</link>"
        f'<atom:link href="{base}/threshold-effects/feed.xml" rel="self" '
        'type="application/rss+xml"/>'
        f"<description>{html.escape(SITE['series_description'])}</description>"
        "<language>en-us</language>"
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


# ------------------------------------------------------------------ build ----

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    issues = load_issues()
    analysis = load_analysis()
    pages = load_pages()
    research = load_yaml(CONTENT / "research.yaml") or []
    press = load_yaml(CONTENT / "press.yaml") or []

    urls = ["/"]

    # Home
    render("home.html", "index.html",
           issues=issues[:3], press=press, page_url="/")

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
        render("issue.html", f"threshold-effects/{issue['slug']}/index.html",
               issue=issue, newer=newer, older=older, page_url=issue["url"],
               schema_extra=article_node(issue, in_series=True))
        urls.append(issue["url"])

    # Analysis
    render("analysis_index.html", "analysis/index.html",
           pieces=analysis, page_url="/analysis/",
           schema_extra=collection_node(
               "Analysis", "/analysis/",
               "Longer data work from Threshold Data Sciences: named "
               "sources and visible methods notes."))
    urls.append("/analysis/")
    for piece in analysis:
        render("analysis.html", f"analysis/{piece['slug']}/index.html",
               piece=piece, page_url=piece["url"],
               schema_extra=article_node(piece))
        urls.append(piece["url"])

    # Research
    render("research.html", "research/index.html",
           research=research, page_url="/research/",
           schema_extra=collection_node(
               "Research", "/research/",
               "Peer-reviewed publications and completed working papers "
               "by Timothy D. Spivey."))
    urls.append("/research/")

    # Markdown-driven pages
    for slug, page in pages.items():
        tpl = page.get("template", "page.html")
        render(tpl, f"{slug}/index.html", page=page, page_url=f"/{slug}/")
        urls.append(f"/{slug}/")

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

    print(f"\nBuilt {len(urls)} pages, {len(issues)} issues, "
          f"{len(analysis)} analysis pieces -> dist/")


if __name__ == "__main__":
    main()
