"""The Google Analytics tag is in production builds only (the deploy workflow sets SITE_ENV=production).

Each test builds the site into a temporary copy of the repository, so the working dist/ is never touched.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GA_ID = re.search(r'^ga4_measurement_id:\s*"([^"]*)"', (ROOT / "site.yaml").read_text(encoding="utf-8"), re.M).group(1)
# The build needs Jinja2, Markdown and PyYAML: use this interpreter if it has them, else the "python" on PATH.
BUILD_PYTHON = sys.executable if importlib.util.find_spec("jinja2") else (shutil.which("python") or sys.executable)
NEEDED = ["build.py", "figures.py", "site.yaml", "templates", "static", "content",
          "demos/results/osha_audit.json"]  # the OSHA Work card's numbers come from the audit's output


def has_tag(html: str) -> bool:
    """The tag itself (the script element or the config call), not a mention of Google's host in page text."""
    return "googletagmanager.com/gtag/js" in html or "gtag('config'" in html or "function gtag(" in html


def build(tmp_path: Path, env_value: str | None) -> list:
    for name in NEEDED:
        src = ROOT / name
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copyfile)(src, tmp_path / name)
    env = {k: v for k, v in os.environ.items() if k != "SITE_ENV"}
    if env_value is not None:
        env["SITE_ENV"] = env_value
    subprocess.run([BUILD_PYTHON, "build.py"], cwd=tmp_path, env=env, check=True, capture_output=True)
    pages = sorted((tmp_path / "dist").rglob("*.html"))
    assert pages, "the build wrote no pages"
    return pages


@pytest.fixture(scope="module")
def default_pages(tmp_path_factory):
    return build(tmp_path_factory.mktemp("default"), None)


@pytest.fixture(scope="module")
def production_pages(tmp_path_factory):
    return build(tmp_path_factory.mktemp("production"), "production")


def test_measurement_id_is_set():
    assert GA_ID and GA_ID.startswith("G-")


def test_default_build_has_no_analytics_tag(default_pages):
    hits = [p for p in default_pages if has_tag(p.read_text(encoding="utf-8"))]
    assert not hits, [str(p) for p in hits[:5]]


def test_other_site_env_values_leave_the_tag_out(tmp_path):
    pages = build(tmp_path, "preview")
    assert not any(has_tag(p.read_text(encoding="utf-8")) for p in pages)


def test_production_build_has_the_tag_once_in_the_head_of_every_page(production_pages):
    for p in production_pages:
        html = p.read_text(encoding="utf-8")
        head = html.split("</head>")[0]
        assert html.count(f"googletagmanager.com/gtag/js?id={GA_ID}") == 1, p
        assert html.count(f"gtag('config', '{GA_ID}')") == 1, p
        assert f"gtag('config', '{GA_ID}')" in head, p


def test_deploy_workflow_builds_for_production():
    wf = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert wf.count("run: python build.py") == 1
    step = wf.split("run: python build.py", 1)[1].split("- uses:", 1)[0]
    assert re.search(r"env:\s*\n\s*SITE_ENV:\s*production\b", step), step


def test_browser_audit_blocks_google_hosts():
    src = (ROOT / "tools" / "a11y_audit.py").read_text(encoding="utf-8")
    assert "--host-resolver-rules=" in src
    for host in ("www.googletagmanager.com", "www.google-analytics.com", "www.google.com"):
        assert host in src
