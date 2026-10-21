"""Point-in-time valuation data that sits beside prices in the panel.

Market P/E and CAPE come from Robert Shiller's monthly S&P 500 data. Two things in
that file are not known when they're dated:

- Earnings for month m are interpolated from quarterly figures that S&P reports
  weeks to months after the quarter ends, and the latest months are estimates.
  We use earnings from ``SHILLER_LAG_MONTHS`` months earlier.
- The price for month m is that month's average, so it's known only once the
  month is over. Every value is indexed by the day it becomes available: the
  first day of the following month.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SHILLER_LAG_MONTHS = 6
CAPE_YEARS = 10


def parse_shiller_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    """The 'Data' sheet of ie_data.xls, read with header=None -> monthly price, earnings, cpi."""
    date = pd.to_numeric(raw.iloc[:, 0], errors="coerce")
    rows = raw[date.notna()]
    date = date[date.notna()]
    year = np.floor(date).astype(int)
    month = np.round((date - year) * 100).astype(int)  # 2025.1 is October
    idx = pd.to_datetime({"year": year, "month": month, "day": 1})
    out = pd.DataFrame(
        {
            "price": pd.to_numeric(rows.iloc[:, 1], errors="coerce").to_numpy(),
            "earnings": pd.to_numeric(rows.iloc[:, 3], errors="coerce").to_numpy(),
            "cpi": pd.to_numeric(rows.iloc[:, 4], errors="coerce").to_numpy(),
        },
        index=pd.DatetimeIndex(idx, name="month"),
    )
    return out


def read_shiller(path: Path | str) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Data", header=None)
    return parse_shiller_sheet(raw)


def market_valuation(monthly: pd.DataFrame, lag: int = SHILLER_LAG_MONTHS) -> pd.DataFrame:
    """Trailing P/E and CAPE, indexed by the date each becomes available.

    P/E for month m is the month's average price over earnings from month m - lag.
    CAPE deflates earnings to last month's CPI (this month's isn't published yet)
    and averages ten years of them, ending at m - lag.
    """
    m = monthly.sort_index()
    known_e = m["earnings"].shift(lag)
    pe = m["price"] / known_e
    cpi_now = m["cpi"].shift(1)
    months = CAPE_YEARS * 12
    real_e = m["earnings"] / m["cpi"]  # in constant dollars, rescaled below
    avg_real = real_e.shift(lag).rolling(months, min_periods=months).mean()
    cape = m["price"] / (avg_real * cpi_now)
    out = pd.DataFrame({"pe": pe, "cape": cape})
    out.index = out.index + pd.DateOffset(months=1)  # available once the month is over
    out.index.name = "available"
    return out.replace([np.inf, -np.inf], np.nan)


def as_of(frame: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """The latest row available on or before each date."""
    frame = frame.sort_index()
    pos = frame.index.searchsorted(dates, side="right") - 1
    out = frame.iloc[np.clip(pos, 0, None)].copy()
    out.index = dates
    out[pos < 0] = np.nan
    return out


MARKET_FILE = "market_valuation.parquet"
EARNINGS_FILE = "stock_earnings.parquet"


def fundamentals_files(root: Path | str) -> list[Path]:
    if not root:
        return []
    return [p for p in (Path(root) / MARKET_FILE, Path(root) / EARNINGS_FILE) if p.exists()]


def attach(panel, root: Path | str):
    """The panel with whatever valuation tables ``root`` has, aligned to its dates."""
    from dataclasses import replace

    root = Path(root)
    kw = {}
    if (root / MARKET_FILE).exists():
        # Monthly rows with their full history (a valuation signal needs decades),
        # but nothing available after the panel's last day.
        kw["market"] = pd.read_parquet(root / MARKET_FILE).sort_index().loc[: panel.dates[-1]]
    if (root / EARNINGS_FILE).exists():
        kw["earnings_yield"] = stock_earnings_yield(pd.read_parquet(root / EARNINGS_FILE), panel)
    return replace(panel, **kw)


MAX_EARNINGS_AGE_DAYS = 456  # about 15 months: no new filing in that long = unknown


def stock_earnings_yield(table: pd.DataFrame, panel) -> pd.DataFrame:
    """Trailing-twelve-month EPS over each day's close, per stock.

    ``table`` has one row per filing: symbol, available (the first day the filing
    could be traded on), eps_ttm (in the price archive's split-adjusted units).
    A figure older than ``MAX_EARNINGS_AGE_DAYS`` counts as unknown.
    """
    t = table[table["symbol"].isin(panel.symbols)].sort_values("available")
    t = t.drop_duplicates(["symbol", "available"], keep="last")
    wide = t.pivot(index="available", columns="symbol", values="eps_ttm")
    when = t.pivot(index="available", columns="symbol", values="available")
    wide, when = wide.ffill(), when.ffill()
    eps = as_of(wide, panel.dates)
    stamp = as_of(when, panel.dates)
    days = panel.dates.values.astype("datetime64[D]").astype("int64")
    filed = stamp.apply(lambda c: pd.to_datetime(c).values.astype("datetime64[D]").astype("float"))
    filed = filed.where(stamp.notna())
    age = pd.DataFrame(days[:, None] - filed.to_numpy(), index=stamp.index, columns=stamp.columns)
    eps = eps.where(age.le(MAX_EARNINGS_AGE_DAYS))
    eps = eps.reindex(columns=panel.symbols)
    return eps / panel.close
