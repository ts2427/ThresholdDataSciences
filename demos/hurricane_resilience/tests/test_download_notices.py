"""Step 2 for the FCC's reporting-area notices: which ones, where they go, and the same terms as reports."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
step2 = importlib.import_module("02_download")

BASE = "https://docs.fcc.gov/public/attachments/"


def doc(page, kind, title, doc_id):
    return {"storm_page": page, "kind": kind, "role": "primary", "title": title, "released": "Sep 1, 2020",
            "doc_id": doc_id, "pdf_url": f"{BASE}{doc_id}.pdf", "txt_url": f"{BASE}{doc_id}.txt", "source_page": ""}


LIST = pd.DataFrame([
    doc("sally", "activation", "FCC Activates Disaster Reporting for Hurricane Sally", "DA-20-1078A1"),
    doc("sally", "area_change", "FCC Updates Disaster Reporting Area for Hurricane Sally", "DA-20-1095A1"),
    doc("sally", "deactivation", "FCC Deactivates Disaster Information Reporting for Hurricane Sally", "DA-20-1114A1"),
    doc("sally", "status_report", "Hurricane Sally Communications Status Report for September 15, 2020", "DOC-1A1"),
    doc("debby", "activation", "FCC Activates MDRI in Virginia for Debby", "DA-24-786A1"),
    doc("irma", "area_change", "Waiver Expanding Public Safety Communications in Puerto Rico & USVI", "DA-17-944A1"),
    doc("fiona", "activation", "FCC Activates Disaster Reporting for Tropical Storm Fiona", "DA-22-971A1"),
])
PAGES = {"sally", "debby", "irma"}


def test_selects_dirs_notices_of_in_scope_storms_only():
    got = step2.notice_jobs(LIST, PAGES)
    assert [j["doc_id"] for j in got] == ["DA-20-1078A1", "DA-20-1095A1", "DA-20-1114A1"]


def test_text_file_only_into_the_notices_folder():
    got = step2.notice_jobs(LIST, PAGES)
    assert {j["kind"] for j in got} == {"txt"}
    assert all(j["url"].endswith(".txt") and j["dest"] == step2.RAW / "notices" / f"{j['doc_id']}.txt" for j in got)


@pytest.fixture
def fake(tmp_path, monkeypatch):
    class Fake:
        requested, waits = [], []
        code = 200

    class Response:
        def __init__(self):
            self.status_code = Fake.code
            self.content = b"x" * 300

    class Session:
        def __init__(self):
            self.headers = {}

        def get(self, url, **options):
            assert options["allow_redirects"] is False
            Fake.requested.append(url)
            return Response()

    (tmp_path / "manifest").mkdir()
    LIST.to_csv(tmp_path / "manifest" / "fcc_storm_documents.csv", index=False)
    pd.DataFrame({"storm_page": sorted(PAGES)}).to_csv(tmp_path / "manifest" / "storms.csv", index=False)
    monkeypatch.setattr(step2, "ROOT", tmp_path)
    monkeypatch.setattr(step2, "RAW", tmp_path / "data" / "raw")
    monkeypatch.setattr(step2, "DOCUMENT_LIST", tmp_path / "manifest" / "fcc_storm_documents.csv")
    monkeypatch.setattr(step2, "STORMS", tmp_path / "manifest" / "storms.csv")
    monkeypatch.setattr(step2, "DOWNLOADS_LOG", tmp_path / "manifest" / "downloads.csv")
    monkeypatch.setattr(step2.requests, "Session", Session)
    monkeypatch.setattr(step2.time, "sleep", lambda s: Fake.waits.append(s))
    return Fake


def test_notices_download_and_log_with_the_same_pace(fake, tmp_path):
    step2.download_notices()
    log = pd.read_csv(tmp_path / "manifest" / "downloads.csv")
    assert log.path.tolist() == [f"data/raw/notices/{d}.txt" for d in ["DA-20-1078A1", "DA-20-1095A1", "DA-20-1114A1"]]
    assert fake.waits == [3.0, 3.0, 3.0]


def test_notices_rerun_makes_no_requests_and_leaves_the_log(fake, tmp_path):
    step2.download_notices()
    first = (tmp_path / "manifest" / "downloads.csv").read_bytes()
    fake.requested.clear()
    step2.download_notices()
    assert fake.requested == [] and (tmp_path / "manifest" / "downloads.csv").read_bytes() == first


@pytest.mark.parametrize("code", [403, 429])
def test_notices_stop_on_a_refusal(fake, tmp_path, code):
    fake.code = code
    with pytest.raises(SystemExit, match=str(code)):
        step2.download_notices()
    assert len(fake.requested) == 1
