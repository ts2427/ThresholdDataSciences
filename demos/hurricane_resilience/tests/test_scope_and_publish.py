"""Out-of-scope reports, and the summary's place in the publish step."""
import ast
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
step1 = importlib.import_module("01_check_manifest")
step3 = importlib.import_module("03_parse_dirs")
step11 = importlib.import_module("11_build_page")


def test_out_of_scope_rows_are_exactly_these_with_a_note():
    # Both Fiona reports (Puerto Rico) and Dorian's Aug 29, 2019 report (Puerto Rico and USVI only)
    man = pd.read_csv(ROOT / "manifest" / "dirs_reports.csv")
    out = man[man.status == "out_of_scope"]
    assert sorted(out.doc_id) == ["DOC-359363A1", "DOC-387555A1", "DOC-387584A1"]
    assert out.notes.str.contains("outside the study area").all()


def test_manifest_check_accepts_out_of_scope():
    man = pd.read_csv(ROOT / "manifest" / "dirs_reports.csv")
    assert step1.check(man[man.status.isin(["ok", "out_of_scope"])]) == []  # "verify" rows are still open


def test_manifest_check_still_counts_rows_to_verify():
    man = pd.read_csv(ROOT / "manifest" / "dirs_reports.csv")
    assert step1.check(man.assign(status="verify")) == [f"{len(man)} rows still need storm/date confirmation (status != ok)"]


def test_step_3_skips_out_of_scope_reports(tmp_path, monkeypatch):
    base = {"storm_name": "X", "nhc_id": "AL012026", "report_date": "2026-10-12"}
    pd.DataFrame([{**base, "doc_id": "DOC-1A1", "status": "ok"},
                  {**base, "doc_id": "DOC-2A1", "status": "out_of_scope"}]
                 ).to_csv(tmp_path / "manifest.csv", index=False)
    read = []
    monkeypatch.setattr(step3, "MANIFEST", tmp_path / "manifest.csv")
    monkeypatch.setattr(step3, "INTERIM", tmp_path)
    monkeypatch.setattr(step3, "RAW", tmp_path)
    monkeypatch.setattr(step3, "report_text", lambda doc: read.append(doc) or ("", "missing"))
    step3.main()
    assert read == ["DOC-1A1"]
    assert pd.read_parquet(tmp_path / "dirs_reports.parquet").doc_id.tolist() == ["DOC-1A1"]


@pytest.fixture
def output(tmp_path, monkeypatch):
    out = tmp_path / "output"
    out.mkdir()
    (out / "validation_summary.csv").write_bytes(b"Report,Rows\nX,1\n")
    (out / "validation_dirs.csv").write_bytes(b"doc_id,status\nDOC-1A1,flagged\n")
    monkeypatch.setattr(step11, "OUTPUT", out)
    return out


def test_summary_is_copied_into_the_snapshot(output, tmp_path):
    dest = step11.copy_validation_summary(tmp_path / "snapshot")
    assert dest == tmp_path / "snapshot" / "validation_summary.csv"
    assert dest.read_bytes() == (output / "validation_summary.csv").read_bytes()


def test_default_snapshot_folder_uses_the_underscore_name():
    assert step11.SNAPSHOT.parts[-2:] == ("demos", "hurricane_resilience")


def test_missing_summary_stops_publishing(output, tmp_path):
    (output / "validation_summary.csv").unlink()
    with pytest.raises(FileNotFoundError):
        step11.copy_validation_summary(tmp_path / "snapshot")


def test_failed_validation_is_not_published(output, tmp_path):
    (output / "validation_dirs.csv").write_bytes(b"doc_id,status\nDOC-1A1,fail\n")
    with pytest.raises(ValueError):
        step11.copy_validation_summary(tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()


def test_publish_step_must_copy_the_summary_once_built():
    src = (ROOT / "src" / "11_build_page.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert "validation_summary.csv" in ast.get_docstring(tree)
    if "Not implemented yet" in src:
        return
    assert any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "copy_validation_summary"
               for n in ast.walk(tree)), "step 11 must call copy_validation_summary"



def test_report_text_keeps_the_more_complete_of_txt_and_pdf(tmp_path, monkeypatch):
    # Harvey Sep 3, 2017 (DOC-346478A1): the .txt breaks rows across lines; the PDF does not
    (tmp_path / "dirs").mkdir()
    (tmp_path / "dirs" / "DOC-1A1.txt").write_text("TX ARANSAS 40 30 75.0%\nSAN\nPATRICIO\n58 1 1.70%\n", encoding="utf-8")
    (tmp_path / "dirs" / "DOC-1A1.pdf").write_bytes(b"stub")
    pdf = "TX ARANSAS 40 30 75.0%\nTX SAN PATRICIO 58 1 1.7%\n"
    monkeypatch.setattr(step3, "RAW", tmp_path)
    monkeypatch.setattr(step3, "pdf_text", lambda path: pdf)
    assert step3.report_text("DOC-1A1") == (pdf, "pdf")


def test_report_text_prefers_txt_on_a_tie(tmp_path, monkeypatch):
    (tmp_path / "dirs").mkdir()
    txt = "TX ARANSAS 40 30 75.0%\n"
    (tmp_path / "dirs" / "DOC-1A1.txt").write_text(txt, encoding="utf-8")
    (tmp_path / "dirs" / "DOC-1A1.pdf").write_bytes(b"stub")
    monkeypatch.setattr(step3, "RAW", tmp_path)
    monkeypatch.setattr(step3, "pdf_text", lambda path: txt)
    assert step3.report_text("DOC-1A1") == (txt, "txt")


def test_listed_excluded_reports_have_a_reason_and_date():
    got = pd.read_csv(ROOT / "manifest" / "excluded_reports.csv", keep_default_na=False)
    assert list(got.columns) == ["doc_id", "storm_name", "report_date", "reason", "decided_on"]
    assert (got[["doc_id", "reason", "decided_on"]] != "").all().all()



@pytest.mark.parametrize("date, clock, tz, utc", [
    ("2024-09-28", "09:00", "EDT", "2024-09-28T13:00:00+00:00"),
    ("2022-11-10", "12:00", "EST", "2022-11-10T17:00:00+00:00"),
    ("2020-10-10", "12:00", "", "2020-10-10T16:00:00+00:00"),  # no zone printed: Eastern assumed
])
def test_as_of_utc(date, clock, tz, utc):
    assert step3.as_of_utc(date, clock, tz).isoformat() == utc


def test_as_of_zone_misprint_is_read_by_the_calendar_and_noted():
    # Zeta, Nov 1, 2020: "12:00 p.m. EDT", but daylight time ended at 2 a.m. that day
    assert step3.as_of_utc("2020-11-01", "12:00", "EDT").isoformat() == "2020-11-01T17:00:00+00:00"
    assert step3.as_of_zone_note("2020-11-01", "12:00", "EDT") == "EDT printed, but Eastern time then was EST; read as EST"
    assert step3.as_of_zone_note("2024-09-28", "09:00", "EDT") == ""
