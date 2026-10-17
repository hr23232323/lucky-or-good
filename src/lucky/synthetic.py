"""A fake stock market written in MarketParquet's exact layout.

Used by tests and for dry runs before real data is available. Because we
control how prices are made, we know the truth: whether any edge exists and
how strong it is. That lets us check the judge finds real edges and rejects
fake ones.

Layout written:  <root>/by_date/stock_daily/YYYY-MM-DD.parquet
                 <root>/by_date/etf_daily/YYYY-MM-DD.parquet
                 <root>/truth.json

The planted edge: each stock has a daily volume shock z (visible in that day's
volume). If ``edge > 0``, the next session's intraday log return gets
``edge * z`` added. A strategy that buys high-z stocks at the next open earns it.

This is a test rig, not a model of a real market. Some effects exist by
accident of construction: failing companies get volatile before they delist
(as real ones do), so volatility- and lottery-style strategies interact with
delistings. Don't read research conclusions off it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import polars as pl

# MarketParquet daily files used a `timestamp` column before this date and a
# `date` column from it onwards. We reproduce the switch so the reader is tested.
SCHEMA_SWITCH = np.datetime64("2026-03-27")


@dataclass
class SyntheticConfig:
    start: str = "2000-01-03"
    end: str = "2026-10-15"
    n_stocks: int = 300
    edge: float = 0.0  # log-return per unit volume shock, earned next session
    seed: int = 0
    ipo_fraction: float = 0.4  # share of stocks that list after the start
    delist_fraction: float = 0.35  # share of stocks that delist before the end
    failure_share: float = 0.5  # of delistings, how many are failures (rest mergers)


def _business_days(start: str, end: str) -> np.ndarray:
    span = np.arange(np.datetime64(start, "D"), np.datetime64(end, "D") + np.timedelta64(1, "D"))
    return span[np.is_busday(span)]


def generate(root: Path | str, config: SyntheticConfig | None = None) -> dict:
    """Write a synthetic market under ``root`` and return its ground truth."""
    cfg = config or SyntheticConfig()
    rng = np.random.default_rng(cfg.seed)
    root = Path(root)
    days = _business_days(cfg.start, cfg.end)
    n_days, n = len(days), cfg.n_stocks

    # Market factor with two volatility regimes (calm / stressed), switching rarely.
    stressed = np.zeros(n_days, dtype=bool)
    state = False
    for t in range(n_days):
        if rng.random() < (0.02 if state else 0.004):
            state = not state
        stressed[t] = state
    mkt_vol = np.where(stressed, 0.022, 0.008)
    mkt = rng.normal(0.0003, 1.0, n_days) * mkt_vol

    beta = rng.uniform(0.5, 1.5, n)
    idio_vol = rng.uniform(0.01, 0.03, n)
    # Idiosyncratic noise with zero *arithmetic* mean. A zero log mean would hand
    # every stock a free +sigma^2/2 a day, which rebalancing harvests as fake alpha.
    eps = rng.normal(0.0, 1.0, (n_days, n)) * idio_vol - 0.5 * idio_vol**2
    log_ret = mkt[:, None] * beta[None, :] + eps

    # Volume shock z: visible in today's volume, optionally predicts tomorrow.
    z = rng.normal(0.0, 1.0, (n_days, n))
    base_volume = np.exp(rng.normal(13.5, 1.0, n))  # ~700k shares median
    volume = base_volume[None, :] * np.exp(0.5 * z + rng.normal(0, 0.1, (n_days, n)))

    overnight = 0.3 * log_ret
    intraday = 0.7 * log_ret
    if cfg.edge:
        intraday[1:] += cfg.edge * z[:-1]

    # Listing windows.
    first = np.zeros(n, dtype=int)
    is_ipo = rng.random(n) < cfg.ipo_fraction
    first[is_ipo] = rng.integers(1, int(n_days * 0.8), is_ipo.sum())
    last = np.full(n, n_days - 1)
    is_delisted = rng.random(n) < cfg.delist_fraction
    kinds = np.full(n, "", dtype=object)
    for i in np.flatnonzero(is_delisted):
        lo = first[i] + 260
        if lo >= n_days - 2:
            is_delisted[i] = False
            continue
        last[i] = rng.integers(lo, n_days - 1)
        if rng.random() < cfg.failure_share:
            kinds[i] = "failure"
            span = min(60, last[i] - first[i])
            window = slice(last[i] - span + 1, last[i] + 1)
            # A ~-63% slide, with distress-level volatility on the way down. A smooth
            # slide would make "calm" stocks look like the ones that fail, a fake effect.
            extra = 2.0 * idio_vol[i]
            intraday[window, i] += rng.normal(-0.5 * extra**2, extra, span) - 1.0 / span
        else:
            kinds[i] = "merger"
            overnight[last[i], i] += 0.2  # takeover premium on the final day

    # Build prices per stock over its listing window.
    rows = []
    for i in range(n):
        a, b = first[i], last[i] + 1
        p0 = rng.uniform(10, 150)
        o = overnight[a:b, i].copy()
        o[0] = 0.0
        open_log = np.log(p0) + np.cumsum(o + np.concatenate([[0.0], intraday[a : b - 1, i]]))
        close_log = open_log + intraday[a:b, i]
        op, cl = np.exp(open_log), np.exp(close_log)
        wick = np.abs(rng.normal(0, 0.004, (2, b - a)))
        hi = np.maximum(op, cl) * np.exp(wick[0])
        lo_ = np.minimum(op, cl) * np.exp(-wick[1])
        sym = f"S{i:04d}" + ("-DELISTED" if is_delisted[i] else "")
        rows.append(
            pl.DataFrame(
                {
                    "date": days[a:b],
                    "symbol": sym,
                    "asset_type": "Stock",
                    "open": op,
                    "high": hi,
                    "low": lo_,
                    "close": cl,
                    "volume": np.round(volume[a:b, i]),
                }
            )
        )
    stocks = pl.concat(rows)

    # Same overnight/intraday split as the stocks, so open-to-open returns line up.
    mkt_close = 100 * np.exp(np.cumsum(mkt))
    mkt_open = np.concatenate([[100.0], mkt_close[:-1]]) * np.exp(0.3 * mkt)
    etf = pl.DataFrame(
        {
            "date": days,
            "symbol": "MKT",
            "asset_type": "ETF",
            "open": mkt_open,
            "high": np.maximum(mkt_open, mkt_close) * 1.002,
            "low": np.minimum(mkt_open, mkt_close) * 0.998,
            "close": mkt_close,
            "volume": np.full(n_days, 5e7),
        }
    )

    _write_by_date(stocks, root / "by_date" / "stock_daily")
    _write_by_date(etf, root / "by_date" / "etf_daily")

    truth = {
        "config": asdict(cfg),
        "n_days": n_days,
        "delisted": {
            f"S{i:04d}-DELISTED": {"kind": kinds[i], "last_date": str(days[last[i]])}
            for i in np.flatnonzero(is_delisted)
        },
        "ipos": int(is_ipo.sum()),
    }
    (root / "truth.json").write_text(json.dumps(truth, indent=2))
    return truth


def _write_by_date(df: pl.DataFrame, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    df = df.with_columns(pl.col("date").cast(pl.Date))
    switch = SCHEMA_SWITCH.astype(object)
    for (day,), part in df.partition_by("date", as_dict=True, maintain_order=True).items():
        if day < switch:
            part = part.with_columns(pl.col("date").cast(pl.Datetime("us")).alias("timestamp"))
            part = part.select(
                ["timestamp", "symbol", "asset_type", "open", "high", "low", "close", "volume"]
            )
        part.write_parquet(out / f"{day}.parquet", compression="snappy")
