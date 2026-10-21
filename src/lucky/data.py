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
import re
from dataclasses import dataclass, fields, replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

FIELDS = ("open", "high", "low", "close", "volume")
DELISTED_SUFFIX = "-DELISTED"
DATE_IN_NAME = re.compile(r"\d{4}-\d{2}-\d{2}$")
BAD_PRINT_JUMP = 3.0  # a close or open this many times away from the previous close...
BAD_PRINT_REVERT = 2.0  # ...that reverses by this much is treated as a bad print
MAX_PRICE = 2_000_000  # above any US share price ever (Berkshire A peaked near $0.8M)
THIN_VOLUME = 0.01  # a bar trading under 1% of its usual volume at a far-off price is junk
SPLIT_RATIOS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100)
SPLIT_PRICE_TOL = 0.12  # log-distance between the overnight price ratio and the split ratio


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
            # Accept our layout (2024-01-02.parquet) and MarketParquet's own names
            # (stock_daily_2024-01-02.parquet).
            match = DATE_IN_NAME.search(path.stem)
            if not match:
                continue
            day = pd.Timestamp(match.group(0))
            if (lo is None or day >= lo) and (hi is None or day <= hi):
                out.append(path)
        return out

    def _source(self, start, end) -> tuple[duckdb.DuckDBPyConnection, str]:
        files = self.files(start, end)
        if not files:
            raise ValueError(f"No files in {self.dir} between {start} and {end}")
        con = duckdb.connect()
        src = f"read_parquet({[str(f) for f in files]!r}, union_by_name=true)"
        cols = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()}
        parts = [c for c in ("date", "timestamp") if c in cols]
        day = f"COALESCE({', '.join(f'CAST({c} AS DATE)' for c in parts)})"
        raw = f"SELECT {day} AS date, symbol, {', '.join(FIELDS)} FROM {src}"
        return con, raw

    def _clean_sql(self, raw: str) -> str:
        """Flag bars that can't be real trades. Three rules, in order:

        1. Non-positive prices, zero volume, or a price above $2 million (more
           than any US stock has traded at): not a real trade.
        2. Thin junk: volume under 1% of the symbol's median over the previous
           20 bars while the close is more than 3x away from their median close
           (a stray print from another security; uses past bars only).
        3. Spike and revert: a close more than 3x away from the previous close
           that the next close reverses by more than 2x, or an open more than 3x
           away that the same bar's close reverses. Recognising the reversal
           needs the next bar, as any vendor's cleaning does; real moves that
           stick are kept.
        """
        jump, revert = f"ln({BAD_PRINT_JUMP})", f"ln({BAD_PRINT_REVERT})"
        return f"""
        WITH raw AS ({raw}),
        pos AS (SELECT * FROM raw WHERE open > 0 AND close > 0 AND high > 0 AND low > 0
                AND volume > 0 AND close < {MAX_PRICE} AND open < {MAX_PRICE}),
        thin AS (SELECT *,
            coalesce(volume < {THIN_VOLUME} * median(volume) OVER past
                     AND abs(ln(close / median(close) OVER past)) > {jump}, false) AS bad_thin
          FROM pos
          WINDOW past AS (PARTITION BY symbol ORDER BY date
                          ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING)),
        kept AS (SELECT * FROM thin WHERE NOT bad_thin),
        nb AS (SELECT *, lag(close) OVER w AS pc, lead(close) OVER w AS nc FROM kept
               WINDOW w AS (PARTITION BY symbol ORDER BY date)),
        flagged AS (SELECT *,
            coalesce(abs(ln(close / pc)) > {jump} AND abs(ln(nc / close)) > {revert}
                     AND sign(ln(close / pc)) != sign(ln(nc / close)), false)
            OR coalesce(abs(ln(open / pc)) > {jump} AND abs(ln(close / open)) > {revert}
                     AND sign(ln(open / pc)) != sign(ln(close / open)), false) AS bad
          FROM nb)
        SELECT date, symbol, {", ".join(FIELDS)}, bad FROM flagged
        UNION ALL
        SELECT date, symbol, {", ".join(FIELDS)}, true AS bad FROM thin WHERE bad_thin
        UNION ALL
        SELECT date, symbol, {", ".join(FIELDS)}, true AS bad FROM raw
        WHERE NOT (open > 0 AND close > 0 AND high > 0 AND low > 0 AND volume > 0
                   AND close < {MAX_PRICE} AND open < {MAX_PRICE})
           OR open IS NULL OR close IS NULL OR volume IS NULL"""

    def load_long(self, start=None, end=None, symbols=None, clean: bool = True) -> pd.DataFrame:
        con, raw = self._source(start, end)
        base = self._clean_sql(raw) if clean else f"SELECT *, false AS bad FROM ({raw})"
        where, params = "WHERE NOT bad", []
        if symbols is not None:
            where += " AND symbol IN (SELECT unnest(?))"
            params.append(list(symbols))
        df = con.execute(
            f"SELECT date, symbol, {', '.join(FIELDS)} FROM ({base}) {where} ORDER BY date, symbol",
            params,
        ).df()
        self.dropped_bars = int(
            con.execute(f"SELECT count(*) FROM ({base}) WHERE bad").fetchone()[0]
        )
        df["date"] = pd.to_datetime(df["date"])
        return df

    def liquid_candidates(self, start, end, top_n: int, lookback: int = 60) -> list[str]:
        """Symbols ever ranked in the top ``2 * top_n`` by trailing median dollar volume.

        A cheap superset of the exact universe, computed in DuckDB so the full
        archive never has to be pivoted. Uses only past bars, like the universe.
        """
        con, raw = self._source(start, end)
        query = f"""
        WITH c AS ({self._clean_sql(raw)}),
        dv AS (SELECT date, symbol,
                 median(close * volume) OVER (PARTITION BY symbol ORDER BY date
                   ROWS BETWEEN {lookback} PRECEDING AND 1 PRECEDING) AS m
               FROM c WHERE NOT bad),
        ranked AS (SELECT symbol, rank() OVER (PARTITION BY date ORDER BY m DESC) AS r
                   FROM dv WHERE m IS NOT NULL)
        SELECT DISTINCT symbol FROM ranked WHERE r <= {2 * top_n} ORDER BY symbol"""
        return [row[0] for row in con.execute(query).fetchall()]

    def load(
        self,
        start=None,
        end=None,
        symbols=None,
        top_n: int | None = None,
        lookback: int = 60,
        clean: bool = True,
    ) -> Panel:
        if top_n is not None and symbols is None:
            symbols = self.liquid_candidates(start, end, top_n, lookback)
        long = self.load_long(start, end, symbols, clean=clean)
        wide = {f: long.pivot(index="date", columns="symbol", values=f) for f in FIELDS}
        del long
        self.split_events = 0
        if clean:
            wide, self.split_events = adjust_unadjusted_splits(wide)
        close = wide["close"]
        if top_n is None:
            universe = close.notna()
        else:
            universe = liquidity_universe(close * wide["volume"], top_n, lookback) & close.notna()
        return Panel(universe=universe, **wide)


def adjust_unadjusted_splits(wide: dict[str, pd.DataFrame]) -> tuple[dict, int]:
    """Find splits the vendor didn't adjust for, and adjust earlier bars.

    A split shows up as an overnight price jump close to a common split ratio
    (2, 3, ... 100, or the reverse) on a day when volume moves the other way by
    at least the square root of that ratio, compared with the previous 20 bars.
    Both conditions use only that day and earlier bars. Earlier prices are then
    scaled so returns are correct, the same way vendors adjust for splits.
    """
    o, c, v = wide["open"], wide["close"], wide["volume"]
    prev_close = c.ffill(limit=5).shift(1)
    lr = np.log(o / prev_close)
    lvr = np.log(v / v.rolling(20, min_periods=5).median().shift(1))
    mult = pd.DataFrame(1.0, index=c.index, columns=c.columns)
    for k in SPLIT_RATIOS:
        lk = np.log(k)
        reverse = ((lr - lk).abs() < SPLIT_PRICE_TOL) & (lvr < -lk / 2)  # price up k, volume down
        forward = ((lr + lk).abs() < SPLIT_PRICE_TOL) & (lvr > lk / 2)  # price down k, volume up
        mult = mult.mask(reverse, float(k)).mask(forward, 1.0 / k)
    events = int((mult != 1.0).to_numpy().sum())
    if not events:
        return wide, 0
    # Bars before an event are scaled by every event after them.
    after = mult.iloc[::-1].cumprod().iloc[::-1].shift(-1).fillna(1.0)
    out = dict(wide)
    for f in ("open", "high", "low", "close"):
        out[f] = wide[f] * after
    out["volume"] = wide["volume"] / after
    return out, events


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
