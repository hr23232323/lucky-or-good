"""Download the MarketParquet archive into the layout the judge reads.

    read -s MARKETPARQUET_API_KEY && export MARKETPARQUET_API_KEY   # paste the key, Enter
    uv run lucky data download --dest ~/marketparquet

Files land at <dest>/by_date/<dataset>/YYYY-MM-DD.parquet. Re-running only
fetches what's missing or the wrong size, so it doubles as the daily update.
API reference: https://marketparquet.com/documentation
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

API = "https://marketparquet.com/api/v1"
KEY_ENV = "MARKETPARQUET_API_KEY"
DEFAULT_DATASETS = ("stock_daily", "etf_daily")
USER_AGENT = "lucky-or-good-downloader"


class DownloadError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        raise DownloadError(
            f"Set {KEY_ENV} first. To keep the key out of your shell history and off the "
            f"screen: read -s {KEY_ENV} && export {KEY_ENV}   (then paste the key, press Enter). "
            "This tool reads it from the environment only and never writes it anywhere."
        )
    return key


def _scrub(text: str, key: str) -> str:
    return text.replace(key, "<key>") if key else text


@dataclass
class Http:
    """Thin HTTP layer, swappable in tests. Retries 429s and transient errors."""

    key: str
    retries: int = 5
    sleep: Callable[[float], None] = time.sleep

    def _open(self, req: urllib.request.Request):
        delay = 2.0
        for attempt in range(self.retries + 1):
            try:
                return urllib.request.urlopen(req, timeout=120)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    raise DownloadError(
                        f"401 Unauthorized: check {KEY_ENV} (keys start with bt_)"
                    ) from None
                if e.code == 429 or e.code >= 500:
                    if attempt == self.retries:
                        raise DownloadError(f"HTTP {e.code} after {attempt} retries") from None
                    wait = float(e.headers.get("Retry-After") or delay) if e.headers else delay
                    self.sleep(wait)
                    delay = min(delay * 2, 60)
                    continue
                raise DownloadError(f"HTTP {e.code} for {req.full_url.split('?')[0]}") from None
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self.retries:
                    raise DownloadError(f"network error: {_scrub(str(e), self.key)}") from None
                self.sleep(delay)
                delay = min(delay * 2, 60)
        raise DownloadError("unreachable")

    def get_json(self, url: str) -> dict:
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {self.key}", "User-Agent": USER_AGENT}
        )
        with self._open(req) as resp:
            return json.loads(resp.read().decode())

    def download(self, url: str, target: Path) -> int:
        # Presigned URLs carry their own auth; don't send the key to the storage host.
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        tmp = target.with_suffix(target.suffix + ".part")
        try:
            with self._open(req) as resp, tmp.open("wb") as f:
                while chunk := resp.read(1 << 20):
                    f.write(chunk)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        size = tmp.stat().st_size
        tmp.replace(target)
        return size


@dataclass
class Summary:
    downloaded: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    bytes: int = 0


def manifest(http: Http, dataset: str, start: str, end: str) -> list[dict]:
    data = http.get_json(f"{API}/manifest/{dataset}?start={start}&end={end}")
    return list(data.get("files") or [])


def target_path(dest: Path, dataset: str, day: str) -> Path:
    return dest / "by_date" / dataset / f"{day}.parquet"


def download(
    dest: Path | str,
    datasets=DEFAULT_DATASETS,
    start_year: int = 2000,
    end_year: int | None = None,
    workers: int = 8,
    http: Http | None = None,
    log: Callable[[str], None] = print,
) -> Summary:
    dest = Path(dest).expanduser()
    http = http or Http(api_key())
    end_year = end_year or date.today().year
    summary = Summary()
    for dataset in datasets:
        (dest / "by_date" / dataset).mkdir(parents=True, exist_ok=True)
        for year in range(start_year, end_year + 1):
            # Fresh manifest per year: its links expire after an hour.
            files = manifest(http, dataset, f"{year}-01-01", f"{year}-12-31")
            todo = []
            for f in files:
                target = target_path(dest, dataset, f["date"])
                if target.exists() and target.stat().st_size == f["file_size_bytes"]:
                    summary.skipped += 1
                else:
                    todo.append((f, target))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                jobs = {pool.submit(http.download, f["download_url"], t): (f, t) for f, t in todo}
                for job in as_completed(jobs):
                    f, target = jobs[job]
                    try:
                        size = job.result()
                    except Exception as e:  # noqa: BLE001 - record and carry on; rerun resumes
                        summary.failed.append(f"{dataset} {f['date']}: {_scrub(str(e), http.key)}")
                        continue
                    if size != f["file_size_bytes"]:
                        target.unlink(missing_ok=True)
                        want = f["file_size_bytes"]
                        summary.failed.append(
                            f"{dataset} {f['date']}: got {size} bytes, expected {want}"
                        )
                        continue
                    summary.downloaded += 1
                    summary.bytes += size
            log(
                f"{dataset} {year}: {len(files)} files, {len(todo)} fetched, "
                f"{len(files) - len(todo)} already here"
            )
    return summary
