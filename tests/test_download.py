import io
import json
import urllib.error
import urllib.request
from email.message import Message

import pandas as pd
import pytest

from lucky import download as dl
from lucky.data import MarketData

KEY = "bt_supersecret123"


class FakeHttp(dl.Http):
    """Serves a fake archive: two trading days per year, one optionally truncated."""

    def __init__(self, truncate=None, fail=None):
        super().__init__(key=KEY, sleep=lambda s: None)
        self.truncate = truncate or set()
        self.fail = fail or set()
        self.fetched = []

    def get_json(self, url):
        dataset = url.split("/manifest/")[1].split("?")[0]
        year = url.split("start=")[1][:4]
        days = [f"{year}-01-02", f"{year}-01-03"]
        return {
            "files": [
                {
                    "date": d,
                    "filename": f"{dataset}_{d}.parquet",
                    "file_size_bytes": 100,
                    "download_url": f"https://storage.example/{dataset}/{d}?sig=x",
                }
                for d in days
            ]
        }

    def download(self, url, target):
        day = url.split("/")[-1].split("?")[0]
        self.fetched.append(day)
        if day in self.fail:
            raise dl.DownloadError(f"boom while using {KEY}")
        size = 60 if day in self.truncate else 100
        target.write_bytes(b"x" * size)
        return size


def run(tmp_path, http, **kw):
    return dl.download(
        tmp_path, ("stock_daily",), 2023, 2024, workers=2, http=http, log=lambda m: None, **kw
    )


def test_files_land_in_the_judges_layout(tmp_path):
    s = run(tmp_path, FakeHttp())
    assert s.downloaded == 4 and not s.failed
    assert (tmp_path / "by_date" / "stock_daily" / "2023-01-02.parquet").exists()


def test_rerun_only_fetches_whats_missing(tmp_path):
    run(tmp_path, FakeHttp())
    again = FakeHttp()
    s = run(tmp_path, again)
    assert s.downloaded == 0 and s.skipped == 4 and again.fetched == []


def test_wrong_size_is_rejected_and_refetched_next_time(tmp_path):
    s = run(tmp_path, FakeHttp(truncate={"2024-01-03"}))
    assert len(s.failed) == 1 and "expected 100" in s.failed[0]
    assert not (tmp_path / "by_date" / "stock_daily" / "2024-01-03.parquet").exists()
    retry = FakeHttp()
    assert run(tmp_path, retry).downloaded == 1 and retry.fetched == ["2024-01-03"]


def test_key_never_appears_in_failures(tmp_path):
    s = run(tmp_path, FakeHttp(fail={"2023-01-02"}))
    assert s.failed and all(KEY not in line for line in s.failed)


def test_missing_key_explains_what_to_do(monkeypatch):
    monkeypatch.delenv(dl.KEY_ENV, raising=False)
    with pytest.raises(dl.DownloadError, match=dl.KEY_ENV):
        dl.api_key()


def _http_error(code, retry_after=None):
    headers = Message()
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://x", code, "err", headers, io.BytesIO(b""))


def test_rate_limit_waits_for_retry_after(monkeypatch):
    calls, waits = [], []

    def fake_urlopen(req, timeout):
        calls.append(req)
        if len(calls) == 1:
            raise _http_error(429, retry_after=7)
        return io.BytesIO(json.dumps({"files": []}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    http = dl.Http(KEY, sleep=waits.append)
    assert http.get_json("https://x/manifest/stock_daily?start=2024-01-01") == {"files": []}
    assert waits == [7.0]
    assert calls[0].get_header("Authorization") == f"Bearer {KEY}"


def test_bad_key_says_so_without_echoing_it(monkeypatch):
    def fake_urlopen(req, timeout):
        raise _http_error(401)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(dl.DownloadError) as err:
        dl.Http(KEY).get_json("https://x")
    assert "401" in str(err.value) and KEY not in str(err.value)


def test_storage_downloads_do_not_send_the_key(monkeypatch, tmp_path):
    seen = []

    def fake_urlopen(req, timeout):
        seen.append(req.get_header("Authorization"))
        return io.BytesIO(b"abc")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert dl.Http(KEY).download("https://storage.example/f?sig=1", tmp_path / "f.parquet") == 3
    assert seen == [None]


def test_reader_accepts_marketparquets_own_filenames(tmp_path):
    folder = tmp_path / "by_date" / "stock_daily"
    folder.mkdir(parents=True)
    df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02").date()],
            "symbol": ["A"],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [10.0],
        }
    )
    df.to_parquet(folder / "stock_daily_2024-01-02.parquet")
    files = MarketData(tmp_path).files()
    assert [f.name for f in files] == ["stock_daily_2024-01-02.parquet"]
    assert MarketData(tmp_path).load().close.shape == (1, 1)
