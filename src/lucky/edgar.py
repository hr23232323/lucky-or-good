"""Per-stock trailing EPS from SEC EDGAR, point in time.

Three problems, each solved conservatively:

1. When was a number known? Every XBRL fact carries the date its filing was
   made. We use each period's figure as first reported, usable from the next
   business day after filing. Later restatements are ignored.
2. Which ticker is which company? The price archive lists live companies under
   today's ticker and dead ones as ``<last ticker>-DELISTED``. Live tickers map
   to a CIK through the SEC's current ticker file. Dead ones map through the
   company name the SEC's fails-to-deliver data shows for that ticker shortly
   before it stopped trading, matched to EDGAR's list of every name a CIK has
   used. Unmatched tickers simply have no earnings.
3. Units. The archive's prices are split-adjusted to today, but each filing
   reports EPS in the share count of its day. Later filings restate earlier
   periods in post-split units, so comparing the same period across filings
   reveals each split; EPS is converted to today's units before dividing by
   an adjusted price. The P/E itself is the ratio of two same-day figures, so
   this conversion carries no information about the future.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np
import pandas as pd

EPS_CONCEPTS = (
    "EarningsPerShareDiluted",
    "EarningsPerShareBasicAndDiluted",
    "EarningsPerShareBasic",
)
FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "10-KT", "10-KT/A"}
SPLIT_RATIOS = (1.25, 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100)
SNAP_TOL = 0.03


def eps_facts(companyfacts: dict) -> pd.DataFrame:
    """Every EPS fact from one company's companyfacts JSON: start, end, val, filed, accn."""
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    for concept in EPS_CONCEPTS:
        units = gaap.get(concept, {}).get("units", {}).get("USD/shares")
        if units:
            df = pd.DataFrame(units)
            if "start" not in df:
                continue
            df = df[df["form"].isin(FORMS)].dropna(subset=["start", "end", "val", "filed"])
            if df.empty:
                continue
            for c in ("start", "end", "filed"):
                df[c] = pd.to_datetime(df[c])
            df["days"] = (df["end"] - df["start"]).dt.days
            return df[["start", "end", "days", "val", "filed", "accn"]].reset_index(drop=True)
    return pd.DataFrame(columns=["start", "end", "days", "val", "filed", "accn"])


def _snap(r: float) -> float:
    if not np.isfinite(r) or r <= 0:
        return 1.0
    if abs(r - 1) <= SNAP_TOL:
        return 1.0
    for s in SPLIT_RATIOS:
        for cand in (s, 1 / s):
            if abs(r / cand - 1) <= SNAP_TOL:
                return cand
    return 1.0  # a restatement, not a split


def unit_factors(facts: pd.DataFrame) -> pd.Series:
    """For each filing date, what to divide its EPS by to get today's (latest) units.

    Walks filings from newest to oldest. A period reported in an older filing and
    again in a newer one has value_old / value_new equal to the splits between them.
    """
    if facts.empty:
        return pd.Series(dtype=float)
    f = facts[facts["val"] != 0]
    dates = sorted(facts["filed"].unique())
    by_date = {d: g.set_index(["start", "end"])["val"] for d, g in f.groupby("filed")}
    u = {dates[-1]: 1.0}
    for i in range(len(dates) - 2, -1, -1):
        d = dates[i]
        mine = by_date.get(d)
        factor = None
        if mine is not None:
            for later in dates[i + 1 :]:
                theirs = by_date.get(later)
                if theirs is None:
                    continue
                common = mine.index.intersection(theirs.index)
                if len(common):
                    ratio = float(
                        np.median(mine.loc[common].to_numpy() / theirs.loc[common].to_numpy())
                    )
                    factor = _snap(ratio) * u[later]
                    break
        u[d] = factor if factor is not None else u[dates[i + 1]]
    return pd.Series(u).sort_index()


NEXT_DAY = pd.offsets.BDay(1)


def ttm_eps(facts: pd.DataFrame) -> pd.DataFrame:
    """Trailing-twelve-month EPS in today's units, one row per date it became known.

    Columns: end (last day of the fiscal period), available, eps_ttm.
    """
    cols = ["end", "available", "eps_ttm"]
    if facts.empty:
        return pd.DataFrame(columns=cols)
    u = unit_factors(facts)
    first = facts.sort_values("filed").drop_duplicates(["start", "end"], keep="first").copy()
    first["val"] = first["val"] / first["filed"].map(u).to_numpy()
    first["available"] = first["filed"] + NEXT_DAY

    quarters = first[first["days"].between(80, 100)].set_index("end").sort_index()
    annual = first[first["days"].between(350, 380)].set_index("end").sort_index()
    q = quarters[~quarters.index.duplicated()][["val", "available"]]

    # Fourth quarters usually appear only inside the annual figure.
    for end, row in annual.iterrows():
        prior = q[
            (q.index > end - pd.Timedelta(days=365)) & (q.index < end - pd.Timedelta(days=20))
        ]
        if len(prior) == 3 and end not in q.index:
            q.loc[end] = [
                row["val"] - prior["val"].sum(),
                max(row["available"], prior["available"].max()),
            ]
    q = q.sort_index()

    rows = []
    ends = sorted(set(q.index) | set(annual.index))
    for end in ends:
        if end in annual.index:
            a = annual.loc[[end]].iloc[0]
            rows.append((end, a["available"], a["val"]))
            continue
        window = q[(q.index > end - pd.Timedelta(days=365)) & (q.index <= end)]
        if len(window) == 4:
            spacing = np.diff(window.index.values).astype("timedelta64[D]").astype(int)
            if ((spacing > 75) & (spacing < 105)).all():
                rows.append((end, window["available"].max(), window["val"].sum()))
    out = pd.DataFrame(rows, columns=cols)
    # A figure only counts once it's known, and a newer fiscal period replaces an older one.
    out = out.sort_values(["available", "end"]).drop_duplicates("available", keep="last")
    return out[out["end"] == out["end"].cummax()].reset_index(drop=True)


# ---------- names, for tickers that no longer trade ----------

_SUFFIXES = {
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "LTD",
    "LIMITED",
    "PLC",
    "LP",
    "LLC",
    "HOLDINGS",
    "HOLDING",
    "GROUP",
    "THE",
    "NEW",
    "DEL",
    "DE",
    "COM",
    "CL",
    "A",
    "B",
    "CLASS",
    "COMMON",
    "STOCK",
    "SHS",
    "ORD",
    "PAR",
    "USD",
    "SA",
    "NV",
    "AG",
    "TR",
}


def normalize_name(name: str) -> str:
    """'Twitter, Inc. COM' and 'TWITTER INC' both become 'TWITTER'."""
    s = re.sub(r"/[A-Z]{2,3}/?", " ", str(name).upper())  # EDGAR's /DE/ state tags
    s = re.sub(r"\$?\d+(\.\d+)?", " ", s)  # par values like .001
    s = re.sub(r"[^A-Z& ]", " ", s).replace("&", " AND ")
    words = [w for w in s.split() if w not in _SUFFIXES]
    return " ".join(words)


def name_index(lines: Iterable[str]) -> dict[str, set[int]]:
    """cik-lookup-data.txt ('NAME:0000123456:' per line) -> normalized name -> CIKs."""
    out: dict[str, set[int]] = {}
    for line in lines:
        parts = line.rstrip("\n").rsplit(":", 2)
        if len(parts) < 2 or not parts[-2].strip().isdigit():
            continue
        key = normalize_name(parts[0])
        if key:
            out.setdefault(key, set()).add(int(parts[-2]))
    return out


# ---------- building the table (network + files) ----------

UA_ENV = "SEC_USER_AGENT"
SEC = "https://www.sec.gov"
FTD_URL = SEC + "/files/data/fails-deliver-data/cnsfails{ym}{half}.zip"


def user_agent() -> str:
    import os

    ua = os.environ.get(UA_ENV, "").strip()
    if "@" not in ua:
        raise RuntimeError(
            f"The SEC asks every downloader to say who it is. Set {UA_ENV}, e.g. "
            f'export {UA_ENV}="lucky-or-good research you@example.com"'
        )
    return ua


def fetch(url: str, dest, ua: str, retries: int = 4) -> bool:
    """Download once (skip if present). Returns False on a 404. Stays under SEC's 10 req/s."""
    import time
    import urllib.error
    import urllib.request
    from pathlib import Path

    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries + 1):
        try:
            time.sleep(0.15)
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with (
                urllib.request.urlopen(req, timeout=300) as r,
                open(dest.with_suffix(".part"), "wb") as f,
            ):
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            dest.with_suffix(".part").replace(dest)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            if attempt == retries:
                raise
            time.sleep(2 * 2**attempt)
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries:
                raise
            time.sleep(2 * 2**attempt)
    return False


def _symbol_key(symbol: str) -> str:
    return symbol.removesuffix("-DELISTED").replace(".", "-").upper()


def last_names(ftd_dir, symbols: dict[str, pd.Timestamp]) -> dict[str, str]:
    """Each delisted symbol's company name in fails-to-deliver data, nearest before it stopped."""
    import zipfile
    from pathlib import Path

    want = {_symbol_key(s): (s, d) for s, d in symbols.items()}
    best: dict[str, tuple[pd.Timestamp, str]] = {}
    for z in sorted(Path(ftd_dir).glob("*.zip")):
        try:
            with zipfile.ZipFile(z) as zf:
                raw = zf.read(zf.namelist()[0]).decode("latin-1")
        except (zipfile.BadZipFile, IndexError):
            continue
        for line in raw.splitlines()[1:]:
            parts = line.split("|")
            if len(parts) < 5:
                continue
            key = parts[2].strip().upper().replace(".", "-")
            if key not in want:
                continue
            day = pd.to_datetime(parts[0], format="%Y%m%d", errors="coerce")
            symbol, end = want[key]
            if pd.isna(day) or day > end:
                continue
            if symbol not in best or day > best[symbol][0]:
                best[symbol] = (day, parts[4].strip())
    return {s: name for s, (_, name) in best.items()}


def build(out, data_root, cache, start="2009-01-01", top_n=1000, log=print) -> pd.DataFrame:
    """Write <out>/stock_earnings.parquet for every stock that was ever near the universe."""
    import json
    import zipfile
    from pathlib import Path

    from .data import MarketData

    ua = user_agent()
    out, cache = Path(out), Path(cache)
    md = MarketData(data_root)
    end = md.files()[-1].stem[-10:]
    symbols = md.liquid_candidates(start, end, top_n=top_n)
    con, raw = md._source(start, end)
    spans = con.execute(
        f"SELECT symbol, min(date), max(date) FROM ({raw}) GROUP BY symbol"
    ).fetchall()
    first_day = {s: pd.Timestamp(a) for s, a, _ in spans}
    last_day = {s: pd.Timestamp(b) for s, _, b in spans}
    log(f"{len(symbols)} symbols were ever in the top {2 * top_n} by dollar volume")

    fetch(SEC + "/files/company_tickers.json", cache / "company_tickers.json", ua)
    fetch(SEC + "/Archives/edgar/cik-lookup-data.txt", cache / "cik-lookup-data.txt", ua)
    log("downloading companyfacts.zip (about 1 GB)...")
    fetch(SEC + "/Archives/edgar/daily-index/xbrl/companyfacts.zip", cache / "companyfacts.zip", ua)

    live = {
        v["ticker"].upper().replace(".", "-"): int(v["cik_str"])
        for v in json.loads((cache / "company_tickers.json").read_text()).values()
    }
    dead = {s: last_day[s] for s in symbols if s.endswith("-DELISTED")}
    years = sorted({d.year for d in dead.values()} | {d.year - 1 for d in dead.values()})
    for y in years:
        for m in range(1, 13):
            for half in "ab":
                fetch(
                    FTD_URL.format(ym=f"{y}{m:02d}", half=half),
                    cache / "ftd" / f"{y}{m:02d}{half}.zip",
                    ua,
                )
    names = last_names(cache / "ftd", dead)
    with open(cache / "cik-lookup-data.txt", encoding="latin-1") as f:
        by_name = name_index(f)

    zf = zipfile.ZipFile(cache / "companyfacts.zip")
    members = set(zf.namelist())

    def facts_for(cik: int) -> pd.DataFrame:
        name = f"CIK{cik:010d}.json"
        if name not in members:
            return eps_facts({})
        return eps_facts(json.loads(zf.read(name)))

    rows, stats = [], {"live": 0, "dead": 0, "dead_no_name": 0, "dead_ambiguous": 0, "no_eps": 0}
    for s in symbols:
        candidates = []
        if s in dead:
            name = names.get(s)
            if not name:
                stats["dead_no_name"] += 1
                continue
            candidates = sorted(by_name.get(normalize_name(name), set()))
        elif _symbol_key(s) in live:
            candidates = [live[_symbol_key(s)]]
        chosen = None
        for cik in candidates:
            f = facts_for(cik)
            # The company must have been filing while this symbol traded.
            if not f.empty and f["filed"].max() >= first_day[s] and f["filed"].min() <= last_day[s]:
                if chosen is not None:
                    chosen = "ambiguous"
                    break
                chosen = (cik, f)
        if chosen == "ambiguous":
            stats["dead_ambiguous"] += 1
            continue
        if chosen is None:
            stats["no_eps"] += 1
            continue
        cik, f = chosen
        t = ttm_eps(f)
        if t.empty:
            stats["no_eps"] += 1
            continue
        t["symbol"], t["cik"] = s, cik
        rows.append(t)
        stats["dead" if s in dead else "live"] += 1
    table = pd.concat(rows, ignore_index=True)
    log("mapping: " + ", ".join(f"{k} {v}" for k, v in stats.items()))
    out.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out / "stock_earnings.parquet")
    return table
