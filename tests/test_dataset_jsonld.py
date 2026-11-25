"""The hurricane page's Dataset JSON-LD meets Google's Dataset structured-data guidelines (read 2026-11-25:
developers.google.com/search/docs/appearance/structured-data/dataset).

Required: name, description (50 to 5000 characters). Recommended and checked here: url, identifier (the DOIs),
sameAs, license (a URL to a specific licence version), creator (Person with an ORCID sameAs), temporalCoverage (ISO
8601 interval), spatialCoverage, distribution (DataDownload with contentUrl, required, and encodingFormat),
isAccessibleForFree, version, includedInDataCatalog, keywords, variableMeasured. The site's own CSV download must exist.
"""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD_PYTHON = sys.executable if importlib.util.find_spec("jinja2") else (shutil.which("python") or sys.executable)
NEEDED = ["build.py", "figures.py", "site.yaml", "templates", "static", "content", "demos/results/osha_audit.json"]
CONCEPT_DOI = "10.5281/zenodo.24477809"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    work = tmp_path_factory.mktemp("site")
    for name in NEEDED:
        src, dst = ROOT / name, work / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    subprocess.run([BUILD_PYTHON, "build.py"], cwd=work, check=True, capture_output=True)
    html = (work / "dist" / "analysis" / "when-the-network-goes-dark" / "index.html").read_text(encoding="utf-8")
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        data = json.loads(block)
        for item in data.get("@graph", [data]):
            if item.get("@type") == "Dataset":
                return work, item
    pytest.fail("no Dataset in the page's JSON-LD")


def test_required(built):
    _, d = built
    assert d["name"].strip()
    assert 50 <= len(d["description"]) <= 5000


def test_identity_and_licence(built):
    _, d = built
    dois = {i["value"] for i in d["identifier"] if i.get("propertyID") == "DOI"}
    assert CONCEPT_DOI in dois and len(dois) == 2  # concept and this version
    assert d["url"] == f"https://doi.org/{CONCEPT_DOI}"
    assert re.fullmatch(r"https://creativecommons\.org/licenses/by/4\.0/?", d["license"])  # a specific version
    assert d["isAccessibleForFree"] is True and re.fullmatch(r"\d+\.\d+\.\d+", d["version"])
    assert d["includedInDataCatalog"]["name"] == "Zenodo"


def test_creator_has_orcid(built):
    _, d = built
    c = d["creator"]
    assert c["@type"] == "Person" and re.fullmatch(r"https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]", c["sameAs"])


def test_coverage(built):
    _, d = built
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}", d["temporalCoverage"])
    assert len(d["spatialCoverage"]) == 10 and all(p["@type"] == "Place" for p in d["spatialCoverage"])
    assert d["keywords"] and d["variableMeasured"]


def test_distribution(built):
    work, d = built
    assert all(x["@type"] == "DataDownload" and x["contentUrl"] and x["encodingFormat"] for x in d["distribution"])
    formats = {x["encodingFormat"] for x in d["distribution"]}
    assert {"application/zip", "text/csv"} <= formats
    csv = next(x for x in d["distribution"] if x["encodingFormat"] == "text/csv")
    path = csv["contentUrl"].replace("https://thresholddatasciences.com", "")
    assert (work / "dist" / path.lstrip("/")).is_file()
