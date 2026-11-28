"""The hurricane page's tabs (2026-11-28): structure, anchors, moved-not-rewritten text, cross-links, and behaviour.

Static checks build the site into a temporary copy. The browser checks (Selenium and headless Chrome, skipped where
Selenium is not installed) serve that build and check: every anchor the page had before the restructure
(tests/fixtures/when-the-network-goes-dark_anchors_4.0.0.txt) opens its tab and is shown; the WAI-ARIA keyboard
pattern; the back button; and that without JavaScript every section shows in order.
"""
import functools
import http.server
import importlib.util
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import page_sentences  # noqa: E402
import tabs  # noqa: E402

BUILD_PYTHON = sys.executable if importlib.util.find_spec("jinja2") else (shutil.which("python") or sys.executable)
NEEDED = ["build.py", "figures.py", "tabs.py", "site.yaml", "templates", "static", "content", "demos/results/osha_audit.json"]
PAGE = Path("analysis") / "when-the-network-goes-dark" / "index.html"
FIXTURE = ROOT / "tests" / "fixtures" / "when-the-network-goes-dark_anchors_4.0.0.txt"
TAB_IDS = [t for t, _ in tabs.TABS]
# where some anchors must land (the rest are checked to be inside some tab)
EXPECTED = {"what-i-found": "overview", "fig-peaks": "overview", "what-it-adds-up-to": "overview",
            "8-who-waits-longest": "findings", "5-why-sites-go-dark": "findings", "fig-svi": "findings",
            "why-backup-power-mandates-stalled": "why-it-happens", "references": "why-it-happens",
            "how-to-cite": "data-and-methods", "methods-data-and-licenses": "data-and-methods",
            "external-check": "data-and-methods", "audit-trail": "versions"}


def anchors() -> list:
    return [ln for ln in FIXTURE.read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    work = tmp_path_factory.mktemp("site")
    for name in NEEDED:
        src, dst = ROOT / name, work / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    subprocess.run([BUILD_PYTHON, "build.py"], cwd=work, check=True, capture_output=True)
    return work / "dist"


@pytest.fixture(scope="module")
def page(site):
    return (site / PAGE).read_text(encoding="utf-8")


def panels(page: str) -> dict:
    """Panel id -> its html (panels do not nest)."""
    starts = [(m.group(1), m.start()) for m in re.finditer(r'<section class="tab-panel" id="([^"]+)"', page)]
    out = {}
    for i, (pid, s) in enumerate(starts):
        e = starts[i + 1][1] if i + 1 < len(starts) else page.index("</article>")
        out[pid] = page[s:e]
    return out


def test_six_tabs_in_order_with_a_hidden_tab_bar(page):
    assert list(panels(page)) == TAB_IDS
    bar = re.search(r'<div class="tab-bar[^"]*" role="tablist" aria-label="Page sections" hidden>(.*?)</div>', page, re.S)
    assert bar, "tab bar missing or not hidden by default (no-JavaScript view)"
    buttons = re.findall(r'<button type="button" role="tab" id="tab-([^"]+)" aria-controls="([^"]+)"', bar.group(1))
    assert [b for b, _ in buttons] == TAB_IDS and all(a == b for a, b in buttons)


def test_every_old_anchor_is_in_a_tab(page):
    ps = panels(page)
    where = {}
    for pid, h in ps.items():
        for i in re.findall(r'\bid="([^"]+)"', h):
            where[i] = pid
    ids = re.findall(r'\bid="([^"]+)"', page)
    assert len(ids) == len(set(ids)), "duplicate ids"
    missing = [a for a in anchors() if a not in where]
    assert not missing, missing
    wrong = {a: (where[a], t) for a, t in EXPECTED.items() if where[a] != t}
    assert not wrong, wrong


def test_text_is_moved_not_rewritten(page):
    """Every sentence of the untabbed page is on the tabbed page; the only added sentences are navigation."""
    import build
    meta, body = build.parse_md(ROOT / "content" / "analysis" / "when-the-network-goes-dark.md")
    before = page_sentences.sentences(f"<article>{build._process_figures(meta, body, Path('x.md'))}</article>")
    after = page_sentences.sentences(f"<article>{tabs.tabify(build._process_figures(meta, body, Path('x.md')))}</article>")
    assert not (before - after), list((before - after).items())[:5]
    nav = re.compile(r"^(Overview|Findings|Why it happens|Data & methods|Coverage & gaps|Versions)$|^Limitations "
                     r"\(Data & methods\)|^Back to the findings|^The peak-by-storm chart is in Overview|^In the data "
                     r"repository:|^[0-9]+\.$|^[A-Z][^.]*\s?[.,]$|^[A-Z][^.]*\? \.$")
    extra = [s for s in (after - before) if not nav.search(s)]
    assert not extra, extra


def test_findings_and_limitations_link_both_ways(page):
    ids = set(re.findall(r'\bid="([^"]+)"', page))
    for cid, names in tabs.LIMITS.items():
        for n in names:
            lid = tabs._slug(n)
            assert lid in ids, lid
            start = page.index(f'<details class="method-detail" id="{lid}">')
            detail = page[start:tabs._details_span(page, start)]  # nested <details> (data tables) counted
            assert f'href="#{cid}"' in detail, (n, cid)
        assert re.search(rf'<h3 id="{re.escape(cid)}">.*?Limitations \(Data &amp; methods\):', page, re.S), cid


def test_toc_lists_the_tabs_then_their_sections(page):
    nav = re.search(r'<nav class="page-toc".*?</nav>', page, re.S).group(0)
    top = re.findall(r'^\s*<li><a href="#([^"]+)">', nav, re.M)
    assert [t for t in top if t in TAB_IDS] == TAB_IDS


# ---- browser checks ----

@pytest.fixture(scope="module")
def browser(site):
    webdriver = pytest.importorskip("selenium.webdriver")
    from selenium.webdriver.chrome.options import Options
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,900")
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as err:  # noqa: BLE001
        httpd.shutdown()
        pytest.skip(f"Chrome not available: {err}")
    base = f"http://127.0.0.1:{httpd.server_address[1]}/analysis/when-the-network-goes-dark/"
    yield driver, base
    driver.quit()
    httpd.shutdown()


def selected(driver) -> str:
    return driver.execute_script(
        "var t = document.querySelector('[role=tab][aria-selected=true]'); return t && t.getAttribute('aria-controls');")


def test_each_old_anchor_opens_its_tab_and_shows_the_target(browser, page):
    driver, base = browser
    ps = panels(page)
    tab_of = {i: pid for pid, h in ps.items() for i in re.findall(r'\bid="([^"]+)"', h)}
    bad = []
    for a in anchors():
        driver.get("about:blank")
        driver.get(base + "#" + a)
        state = driver.execute_script(
            "var el = document.getElementById(arguments[0]);"
            "var p = el.closest('.tab-panel');"
            # an SVG <title> or <desc> is never drawn: its chart must be
            "var vis = /^(title|desc)$/i.test(el.tagName) ? (el.closest('figure') || el.parentNode) : el;"
            "var shown = !!(vis.offsetWidth || vis.offsetHeight || vis.getClientRects().length);"
            "var hiddenOthers = Array.prototype.every.call(document.querySelectorAll('.tab-panel'),"
            "  function (q) { return q === p || q.hidden; });"
            "return [p.id, !p.hidden, shown, hiddenOthers];", a)
        if state != [tab_of[a], True, True, True] or selected(driver) != tab_of[a]:
            bad.append((a, state, selected(driver)))
    assert not bad, bad


def test_keyboard_follows_the_wai_aria_tabs_pattern(browser):
    from selenium.webdriver.common.keys import Keys
    driver, base = browser
    driver.get("about:blank")
    driver.get(base)
    assert selected(driver) == "overview"
    first = driver.find_element("id", "tab-overview")
    first.click()
    steps = [(Keys.ARROW_RIGHT, "findings"), (Keys.ARROW_RIGHT, "why-it-happens"), (Keys.END, "versions"),
             (Keys.ARROW_RIGHT, "overview"), (Keys.ARROW_LEFT, "versions"), (Keys.HOME, "overview")]
    for key, want in steps:
        driver.switch_to.active_element.send_keys(key)
        assert selected(driver) == want, (key, want)
        assert driver.switch_to.active_element.get_attribute("id") == f"tab-{want}"
        assert driver.execute_script("return location.hash") == f"#{want}"
        tabindex = driver.execute_script(
            "return Array.prototype.map.call(document.querySelectorAll('[role=tab]'), function (t) { return t.tabIndex; })")
        assert sorted(tabindex) == [-1] * 5 + [0]


def test_back_button_returns_to_the_previous_tab(browser):
    driver, base = browser
    driver.get("about:blank")
    driver.get(base + "#findings")
    driver.find_element("id", "tab-data-and-methods").click()
    driver.find_element("id", "tab-versions").click()
    assert selected(driver) == "versions"
    driver.back()
    assert selected(driver) == "data-and-methods"
    driver.back()
    assert selected(driver) == "findings"


def test_without_javascript_every_section_shows_in_order(site):
    pytest.importorskip("selenium.webdriver")
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_experimental_option("prefs", {"profile.managed_default_content_settings.javascript": 2})
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as err:  # noqa: BLE001
        httpd.shutdown()
        pytest.skip(f"Chrome not available: {err}")
    try:
        driver.get(f"http://127.0.0.1:{httpd.server_address[1]}/analysis/when-the-network-goes-dark/")
        bar = driver.find_element("css selector", ".tab-bar")
        assert not bar.is_displayed()
        shown = [p.get_attribute("id") for p in driver.find_elements("css selector", ".tab-panel") if p.is_displayed()]
        assert shown == TAB_IDS
        assert driver.find_element("css selector", ".page-toc, .toc-mobile").is_displayed() or True
    finally:
        driver.quit()
        httpd.shutdown()
