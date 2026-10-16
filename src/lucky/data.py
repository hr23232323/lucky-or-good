"""Load MarketParquet-style daily bars into aligned date x symbol matrices.

Expected layout (MarketParquet, or the synthetic market):
    <root>/by_date/<asset>_daily/YYYY-MM-DD.parquet
with columns ``symbol, open, high, low, close, volume`` and either ``date``
(files from 2026-03-27) or ``timestamp`` (earlier files).

Prices are split-adjusted, not dividend-adjusted. Delisted symbols keep their
history and carry a ``-DELISTED`` suffix.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, fields, replace
from pathlib import Path

import duckdb
import pandas as pd

FIELDS = ("open", "high", "low", "close", "volume")
DELISTED_SUFFIX = "-DELISTED"


def data_dir() -> Path:
    """The local data root, from ``LUCKY_DATA_DIR``."""
    value = os.environ.get("LUCKY_DATA_DIR")
    if not value:
        raise RuntimeError(
            "Set LUCKY_DATA_DIR to your MarketParquet copy (the folder containing by_date/), "
            "or run `lucky synthetic <dir>` to make a fake market for trying things out."
        )
    return Path(value)


@dataclass(frozen=True)
class Panel:
    """Daily bars as wide DataFrames: index = date, columns = symbol.

    ``universe`` marks which symbols a strategy may hold on each date. It is
    computed from data strictly before that date.
    """

    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame
    volume: pd.DataFrame
    universe: pd.DataFrame

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.close.index

    @property
    def symbols(self) -> pd.Index:
        return self.close.columns

    @property
    def dollar_volume(self) -> pd.DataFrame:
        # Split adjustment scales price and volume inversely, so this is the
        # real traded value even on adjusted data.
        return self.close * self.volume

    def _map(self, fn) -> Panel:
        return replace(self, **{f.name: fn(getattr(self, f.name)) for f in fields(self)})

    def until(self, t) -> Panel:
        """Only rows on or before ``t``."""
        t = pd.Timestamp(t)
        return self._map(lambda df: df.loc[:t])

    def between(self, start, end) -> Panel:
        return self._map(lambda df: df.loc[pd.Timestamp(start) : pd.Timestamp(end)])

    def copy(self) -> Panel:
        return self._map(lambda df: df.copy())


class MarketData:
    """Reads one asset class (``stock`` or ``etf``) of daily files."""

    def __init__(self, root: Path | str, asset: str = "stock"):
        self.dir = Path(root) / "by_date" / f"{asset}_daily"
        if not self.dir.is_dir():
            raise FileNotFoundError(f"No daily files at {self.dir}")

    def files(self, start=None, end=None) -> list[Path]:
        """Files whose date (from the filename) falls in [start, end]."""
        lo = pd.Timestamp(start) if start is not None else None
        hi = pd.Timestamp(end) if end is not None else None
        out = []
        for path in sorted(self.dir.glob("*.parquet")):
            try:
                day = pd.Timestamp(path.stem)
            except ValueError:
                continue
            if (lo is None or day >= lo) and (hi is None or day <= hi):
                out.append(path)
        return out

    def load_long(self, start=None, end=None, symbols=None) -> pd.DataFrame:
        files = self.files(start, end)
        if not files:
            raise ValueError(f"No files in {self.dir} between {start} and {end}")
        con = duckdb.connect()
        src = f"read_parquet({[str(f) for f in files]!r}, union_by_name=true)"
        cols = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
        parts = [c for c in ("date", "timestamp") if c in cols]
        day = f"COALESCE({', '.join(f'CAST({c} AS DATE)' for c in parts)})"
        where = ""
        params: list = []
        if symbols is not None:
            where = "WHERE symbol IN (SELECT unnest(?))"
            params.append(list(symbols))
        query = (
            f"SELECT {day} AS date, symbol, {', '.join(FIELDS)} FROM {src} {where} "
            "ORDER BY date, symbol"
        )
        df = con.execute(query, params).df()
        df["date"] = pd.to_datetime(df["date"])
        return df

    def load(
        self, start=None, end=None, symbols=None, top_n: int | None = None, lookback: int = 60
    ) -> Panel:
        long = self.load_long(start, end, symbols)
        wide = {f: long.pivot(index="date", columns="symbol", values=f) for f in FIELDS}
        close = wide["close"]
        if top_n is None:
            universe = close.notna()
        else:
            universe = liquidity_universe(close * wide["volume"], top_n, lookback) & close.notna()
        return Panel(universe=universe, **wide)


def liquidity_universe(
    dollar_volume: pd.DataFrame, top_n: int, lookback: int = 60, min_history: int | None = None
) -> pd.DataFrame:
    """Top ``top_n`` symbols by trailing median dollar volume, using data through t-1.

    The shift is what keeps this point-in-time: membership on date t never
    depends on anything that happened on t or later.
    """
    min_history = min_history or int(lookback * 0.8)
    trailing = dollar_volume.rolling(lookback, min_periods=min_history).median().shift(1)
    rank = trailing.rank(axis=1, ascending=False, method="first")
    return rank.le(top_n) & trailing.notna()
