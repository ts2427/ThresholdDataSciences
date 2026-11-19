import csv

from common.manifest import record, sha256_file


def test_sha256_file(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_record_adds_and_replaces(tmp_path):
    m = tmp_path / "downloads.csv"
    f = tmp_path / "raw.csv"
    f.write_text("x\n1\n")
    record(f, "https://example.org/a", rows=1, manifest=m)
    f.write_text("x\n1\n2\n")
    record(f, "https://example.org/b", rows=2, manifest=m)
    rows = list(csv.DictReader(open(m, encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.org/b" and rows[0]["rows"] == "2"
    assert rows[0]["sha256"] == sha256_file(f)
