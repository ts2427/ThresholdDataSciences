"""Streaming downloads (EAGLE-I, Census, NHC): checked against the publisher's size and MD5, hashed, logged."""
import hashlib
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import download_util as du  # noqa: E402


class _Resp:
    def __init__(self, status, body=b"", headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            yield self._body[i:i + n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Session:
    def __init__(self, *responses):
        self.responses, self.calls, self.headers = list(responses), [], {}

    def get(self, url, **kw):
        self.calls.append((url, kw))
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(du.time, "sleep", lambda s: None)


BODY = b"fips_code,county,state,customers_out,run_start_time\n" * 50


def job(tmp_path, **kw):
    base = {"url": "https://ndownloader.figshare.com/files/1", "dest": tmp_path / "raw" / "a.csv",
            "logged_path": "$EAGLEI_RAW_DIR/a.csv", "doc_id": "a.csv", "kind": "eaglei",
            "bytes": len(BODY), "md5": hashlib.md5(BODY).hexdigest()}
    return {**base, **kw}


def test_download_is_checked_hashed_and_logged(tmp_path):
    log = tmp_path / "downloads.csv"
    s = _Session(_Resp(200, BODY))
    du.run([job(tmp_path)], log, session=s, allowed=("https://ndownloader.figshare.com/",))
    got = pd.read_csv(log, dtype=str)
    assert got.status.tolist() == ["downloaded"] and got.path.tolist() == ["$EAGLEI_RAW_DIR/a.csv"]
    assert got.sha256.iloc[0] == hashlib.sha256(BODY).hexdigest()
    assert (tmp_path / "raw" / "a.csv").read_bytes() == BODY and not list((tmp_path / "raw").glob("*.part"))
    assert s.calls[0][1]["stream"] is True


def test_md5_or_size_mismatch_is_not_kept_and_stops(tmp_path):
    log = tmp_path / "downloads.csv"
    with pytest.raises(SystemExit, match="md5"):
        du.run([job(tmp_path, md5="0" * 32), job(tmp_path, dest=tmp_path / "raw" / "b.csv")], log,
               session=_Session(_Resp(200, BODY)), allowed=("https://ndownloader.figshare.com/",))
    assert not (tmp_path / "raw" / "a.csv").exists()
    assert pd.read_csv(log, dtype=str).status.tolist() == ["md5 mismatch"]


@pytest.mark.parametrize("status", [403, 429])
def test_refusal_stops_without_retry(tmp_path, status):
    s = _Session(_Resp(status), _Resp(200, BODY))
    with pytest.raises(SystemExit, match=f"http {status}"):
        du.run([job(tmp_path), job(tmp_path, dest=tmp_path / "raw" / "b.csv")], tmp_path / "d.csv", session=s,
               allowed=("https://ndownloader.figshare.com/",))
    assert len(s.calls) == 1


def test_existing_file_is_not_fetched_again(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "a.csv").write_bytes(BODY)
    s = _Session()
    du.run([job(tmp_path)], tmp_path / "d.csv", session=s, allowed=("https://ndownloader.figshare.com/",))
    assert s.calls == [] and pd.read_csv(tmp_path / "d.csv").status.tolist() == ["exists"]


def test_url_outside_the_approved_list_is_never_requested(tmp_path):
    s = _Session(_Resp(200, BODY))
    with pytest.raises(SystemExit, match="not approved"):
        du.run([job(tmp_path, url="https://example.com/x.csv")], tmp_path / "d.csv", session=s,
               allowed=("https://ndownloader.figshare.com/",))
    assert s.calls == []


def test_waits_between_requests(tmp_path, monkeypatch):
    waits = []
    monkeypatch.setattr(du.time, "sleep", waits.append)
    du.run([job(tmp_path), job(tmp_path, dest=tmp_path / "raw" / "b.csv", logged_path="$EAGLEI_RAW_DIR/b.csv")],
           tmp_path / "d.csv", session=_Session(_Resp(200, BODY), _Resp(200, BODY)),
           allowed=("https://ndownloader.figshare.com/",))
    assert waits == [3.0, 3.0]


def test_eaglei_dir_comes_from_the_environment(monkeypatch, tmp_path):
    import config
    monkeypatch.setenv("EAGLEI_RAW_DIR", str(tmp_path))
    assert importlib.reload(config).EAGLEI_RAW_DIR == tmp_path
    monkeypatch.delenv("EAGLEI_RAW_DIR")
    assert importlib.reload(config).EAGLEI_RAW_DIR.as_posix().endswith(("/data/eaglei", "/data/input/eaglei"))


def test_census_key_is_read_from_dotenv_and_not_shown(tmp_path, monkeypatch):
    import config
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    (tmp_path / ".env").write_text("# comment\nCENSUS_API_KEY=abc123\n", encoding="utf-8")
    key = config.census_api_key(tmp_path / ".env")
    assert key == "abc123" and "abc123" not in repr(config.census_api_key)


def test_secret_in_the_url_is_never_logged_or_shown(tmp_path, capsys):
    log = tmp_path / "d.csv"
    url = "https://api.census.gov/data/2022/acs/acs5?get=NAME&key=SECRET123"
    with pytest.raises(SystemExit) as stop:
        du.run([job(tmp_path, url=url, logged_url=url.replace("SECRET123", "REDACTED"), bytes=None, md5=None)], log,
               session=_Session(_Resp(500)), allowed=("https://api.census.gov/",))
    assert "SECRET123" not in str(stop.value) and "SECRET123" not in capsys.readouterr().out
    assert "SECRET123" not in log.read_text(encoding="utf-8") and "key=REDACTED" in log.read_text(encoding="utf-8")
