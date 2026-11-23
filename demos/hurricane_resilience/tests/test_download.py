"""Step 2's log: relative paths, and no change on a rerun. No network is used."""
import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
step2 = importlib.import_module("02_download")


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A throwaway project with one report in its manifest and a fake HTTP session."""
    (tmp_path / "manifest").mkdir()
    manifest = tmp_path / "manifest" / "dirs_reports.csv"
    base = "https://docs.fcc.gov/public/attachments/DOC-1A1"
    manifest.write_text(f"doc_id,txt_url,pdf_url\nDOC-1A1,{base}.txt,{base}.pdf\n", encoding="utf-8")

    class Project:
        root = tmp_path
        log = tmp_path / "manifest" / "downloads.csv"
        failing = ""  # URLs with this ending return 404
        requested = []
        options = []
        events = []  # waits and requests, in order
        headers = {}
        code = 404  # what a failing URL returns
        error = ""  # URLs with this ending raise a timeout
        body = b""  # what the server sends for every request, if set

    class Response:
        def __init__(self, ok):
            self.status_code = 200 if ok else Project.code
            self.content = Project.body or b"x" * 300

    class Session:
        def __init__(self):
            self.headers = Project.headers

        def get(self, url, **options):
            Project.requested.append(url)
            if Project.error and url.endswith(Project.error):
                raise step2.requests.exceptions.ReadTimeout("Read timed out. (read timeout=60)")
            Project.options.append(options)
            Project.events.append("get")
            return Response(not (Project.failing and url.endswith(Project.failing)))

    monkeypatch.setattr(step2, "ROOT", tmp_path, raising=False)
    monkeypatch.setattr(step2, "RAW", tmp_path / "data" / "raw")
    monkeypatch.setattr(step2, "MANIFEST", manifest)
    monkeypatch.setattr(step2, "DOWNLOADS_LOG", Project.log)
    monkeypatch.setattr(step2.requests, "Session", Session)
    monkeypatch.setattr(step2.time, "sleep", lambda seconds: Project.events.append(seconds))
    ticks = iter(range(1, 100))

    class Clock:
        """A later time on every call, so a rewritten 'when' cannot go unnoticed."""

        @staticmethod
        def now(tz):
            return datetime(2026, 1, 1, tzinfo=tz) + timedelta(hours=next(ticks))

    monkeypatch.setattr(step2, "datetime", Clock)
    return Project


def test_paths_are_relative_to_the_project_root(project):
    step2.download_dirs()
    assert pd.read_csv(project.log).path.tolist() == ["data/raw/dirs/DOC-1A1.txt", "data/raw/dirs/DOC-1A1.pdf"]


def test_running_twice_leaves_downloads_csv_unchanged(project):
    step2.download_dirs()
    first = project.log.read_bytes()
    step2.download_dirs()
    assert project.log.read_bytes() == first
    assert len(project.requested) == 2  # the second run made no requests


def test_running_twice_with_a_failed_download_leaves_it_unchanged(project):
    project.failing = ".pdf"
    step2.download_dirs()
    first = project.log.read_bytes()
    step2.download_dirs()
    assert project.log.read_bytes() == first


def test_rerun_from_a_copy_in_another_folder_leaves_it_unchanged(project, tmp_path, monkeypatch):
    step2.download_dirs()
    first = project.log.read_bytes()
    copy = tmp_path / "elsewhere"
    monkeypatch.setattr(step2, "ROOT", copy, raising=False)
    monkeypatch.setattr(step2, "RAW", copy / "data" / "raw")
    step2.download_dirs()
    assert project.log.read_bytes() == first


def test_log_uses_the_same_line_endings_on_every_system(project):
    step2.download_dirs()
    assert b"\r" not in project.log.read_bytes()


def test_committed_log_has_no_absolute_paths():
    root = Path(__file__).resolve().parents[1]
    for path in pd.read_csv(root / "manifest" / "downloads.csv").path:
        # EAGLE-I files live outside the project (author's decision 2026-11-22), logged with a placeholder
        assert path.startswith(("data/raw/", "$EAGLEI_RAW_DIR/")) and ":" not in path and ".." not in path, path


# --- the approved download terms (docs/decisions.md, 2026-11-22) ---

def test_at_least_three_seconds_before_every_request(project):
    step2.download_dirs()
    assert project.events[1::2] == ["get", "get"]
    assert all(wait >= 3 for wait in project.events[0::2])


def test_existing_files_cost_no_wait_and_no_request(project):
    step2.download_dirs()
    project.events.clear()
    step2.download_dirs()
    assert project.events == []


def test_generic_user_agent(project):
    step2.download_dirs()
    assert project.headers["User-Agent"] == "public-records-archiver/1.0"


@pytest.mark.parametrize("code", [403, 429])
def test_a_refusal_stops_at_once_without_retrying(project, code):
    project.failing, project.code = ".txt", code  # the first of the two files
    with pytest.raises(SystemExit, match=str(code)):
        step2.download_dirs()
    assert len(project.requested) == 1
    assert pd.read_csv(project.log).status.tolist() == [f"http {code}"]


def test_redirects_are_not_followed(project):
    step2.download_dirs()
    assert all(options["allow_redirects"] is False for options in project.options)


def test_only_docs_fcc_gov_is_requested(project):
    man = step2.MANIFEST
    man.write_text(man.read_text(encoding="utf-8").replace("docs.fcc.gov", "www.fcc.gov"), encoding="utf-8")
    with pytest.raises(SystemExit, match="docs.fcc.gov"):
        step2.download_dirs()
    assert project.requested == []



def test_a_request_error_keeps_the_log_and_stops_without_retrying(project):
    # 2026-11-22: a read timeout on the last file lost the log of 323 downloads.
    project.error = ".pdf"  # the second of the two files
    with pytest.raises(SystemExit, match="ReadTimeout"):
        step2.download_dirs()
    assert len(project.requested) == 2
    log = pd.read_csv(project.log)
    assert log.status.tolist() == ["downloaded", "error ReadTimeout"]
    assert not (project.root / "data" / "raw" / "dirs" / "DOC-1A1.pdf").exists()


def test_out_of_scope_reports_are_not_downloaded(project):
    man = step2.MANIFEST
    text = man.read_text(encoding="utf-8")
    lines = text.splitlines()
    lines[0] += ",status"
    lines[1] += ",out_of_scope"
    man.write_text("\n".join(lines) + "\n", encoding="utf-8")
    step2.download_dirs()
    assert project.requested == []


# Verbatim start of what docs.fcc.gov returned, with status 200, for DOC-358472A1.txt on 2026-11-22.
HTML_404 = (b'<!DOCTYPE HTML><html>\n   <head>\n      <meta http-equiv="Content-Type" content="text/html; '
            b'charset=UTF-8">\n      <title>404 - \n                    The page not found</title>\n' + b" " * 400)


def test_an_html_404_page_sent_with_status_200_is_not_saved_or_logged_as_downloaded(project):
    project.body = HTML_404
    step2.download_dirs()  # not a refusal: the run goes on
    log = pd.read_csv(project.log, keep_default_na=False)
    assert log.status.tolist() == ["not found (html 404 page)"] * 2 and (log.sha256 == "").all()
    assert list((project.root / "data" / "raw" / "dirs").glob("*")) == []
