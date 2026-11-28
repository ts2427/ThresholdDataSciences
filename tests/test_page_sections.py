"""Analysis pages with `toc: true` (2026-11-25): "On this page" navigation and collapsed sections.

Builds the site into a temporary copy (the working dist/ is never touched) and checks the hurricane page: the
navigation lists every h2 and chapters 1 to 12 and every link resolves on the page; the detailed methods, the
external checks, the context tables, Related work and Sources are closed <details>; every old anchor is still an id;
the script that opens a collapsed target, and the print rule that opens every section, are in place.
"""
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD_PYTHON = sys.executable if importlib.util.find_spec("jinja2") else (shutil.which("python") or sys.executable)
NEEDED = ["build.py", "figures.py", "tabs.py", "site.yaml", "templates", "static", "content", "demos/results/osha_audit.json"]
OLD_ANCHORS = ["what-i-found", "how-to-read-it", "1-the-question-and-the-data",
               "2-anatomy-of-a-storm-isaias-october-2026", "3-how-much-goes-dark", "4-how-fast-it-comes-back",
               "5-why-sites-go-dark", "6-the-power-coupling", "7-exposure", "8-who-waits-longest",
               "9-did-the-rules-help", "10-what-the-public-record-misses", "11-sites-on-backup-power",
               "12-which-comes-back-first-power-or-cell-service",
               "13-do-counties-with-more-mobile-providers-recover-differently",
               "14-how-complete-are-the-fccs-public-reports", "methods-data-and-licenses", "audit-trail",
               "external-check", "how-to-cite", "related-work", "sources"]
COLLAPSED = ["Reading the reports.", "Times and censoring.", "Validation.",
             "External check against the FCC's 2017 season report.", "External checks added later",
             "Context tables.", "Show related work", "Show sources", "Show the dated logs"]


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    work = tmp_path_factory.mktemp("site")
    for name in NEEDED:
        src = ROOT / name
        dst = work / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    subprocess.run([BUILD_PYTHON, "build.py"], cwd=work, check=True, capture_output=True)
    return (work / "dist" / "analysis" / "when-the-network-goes-dark" / "index.html").read_text(encoding="utf-8")


def nav_links(html: str, cls: str) -> list:
    block = re.search(rf'<(nav|details) class="{cls}[^"]*".*?</\1>', html, re.S).group(0)
    return re.findall(r'<a href="#([^"]+)">([^<]+)</a>', block)


def test_navigation_lists_sections_and_chapters_1_to_12(page):
    for cls in ("page-toc", "toc-mobile"):
        links = nav_links(page, cls)
        texts = [t for _, t in links]
        chapters = [t for t in texts if re.match(r"\d+\. ", t)]
        assert [int(t.split(".")[0]) for t in chapters] == list(range(1, 13))
        for section in ("Why this page exists", "The data", "Methods", "Related work", "Sources", "How to cite"):
            assert section in texts, (cls, section)
        ids = set(re.findall(r'\bid="([^"]+)"', page))
        assert all(i in ids for i, _ in links), [i for i, _ in links if i not in ids]


def test_old_anchors_are_still_ids(page):
    ids = set(re.findall(r'\bid="([^"]+)"', page))
    assert [a for a in OLD_ANCHORS if a not in ids] == []


def test_detailed_sections_are_closed_by_default(page):
    summaries = re.findall(r"<details(?P<attrs>[^>]*)>\s*<summary>(.*?)</summary>", page, re.S)
    found = {re.sub(r"<[^>]+>", "", s).replace("Exploratory. ", "").strip(): " open" in a for a, s in summaries}
    for want in COLLAPSED:
        hits = [k for k in found if k.startswith(want)]
        assert hits, want
        assert not any(found[k] for k in hits), f"{want} is open by default"


def test_script_and_print_rule(page):
    assert '<script src="/static/js/page-sections.js" defer></script>' in page
    css = (ROOT / "static" / "css" / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "page-sections.js").read_text(encoding="utf-8")
    assert "details::details-content" in css.split("@media print", 1)[1]
    assert "beforeprint" in js and "hashchange" in js
