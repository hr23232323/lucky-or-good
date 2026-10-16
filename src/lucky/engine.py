"""Turn target weights into daily returns, honestly.

Timing: a weight row dated t is decided after the close of t. It is traded at
the open of t+1 and earns open-to-open returns from there. The engine applies
this lag; strategies cannot opt out of it.

Weight semantics:
- a row that is entirely NaN (or missing) means "no trade today": positions drift;
- a NaN inside a row that has any values means zero weight for that symbol;
- weights are fractions of capital; negative is short; cash earns nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import Panel


@dataclass(frozen=True)
class CostModel:
    """One-way trading costs by liquidity rank, plus a borrow fee on shorts.

    Liquidity rank is by trailing median dollar volume through t-1. Defaults are
    deliberately not generous: roughly half-spread plus impact for a small
    account trading at the open.
    """

    tiers: tuple[tuple[int, float], ...] = ((200, 3.0), (1000, 8.0))  # (rank <=, bps)
    floor_bps: float = 20.0  # everything less liquid than the last tier
    borrow_bps_per_year: float = 50.0
    lookback: int = 60

    def scaled(self, k: float) -> CostModel:
        return CostModel(
            tiers=tuple((r, b * k) for r, b in self.tiers),
            floor_bps=self.floor_bps * k,
            borrow_bps_per_year=self.borrow_bps_per_year * k,
            lookback=self.lookback,
        )

    def bps(self, dollar_volume: pd.DataFrame) -> np.ndarray:
        trailing = dollar_volume.rolling(self.lookback, min_periods=1).median().shift(1)
        rank = trailing.rank(axis=1, ascending=False).to_numpy()
        out = np.full(rank.shape, self.floor_bps)
        for max_rank, bps in sorted(self.tiers, reverse=True):
            out[rank <= max_rank] = bps
        return out


ZERO_COSTS = CostModel(tiers=(), floor_bps=0.0, borrow_bps_per_year=0.0)


@dataclass(frozen=True)
class Delisting:
    """Return applied when a held symbol stops trading.

    MarketParquet doesn't say why a symbol delisted. We call it a failure if the
    last close is below ``failure_price`` or more than ``failure_drawdown`` under
    its trailing 120-day high, and apply ``failure_return``; otherwise (likely a
    merger) we apply nothing extra. The usual research convention for failures
    is -30% (NYSE/Amex) to -55% (Nasdaq).
    """

    failure_return: float = -0.30
    failure_price: float = 1.0
    failure_drawdown: float = 0.5


@dataclass
class Result:
    returns: pd.Series  # net daily returns, indexed by execution date
    gross_returns: pd.Series
    costs: pd.Series
    turnover: pd.Series
    gross_exposure: pd.Series
    net_exposure: pd.Series
    positions: pd.Series  # number of non-zero positions
    notes: list[str] = field(default_factory=list)

    def between(self, start, end) -> Result:
        sl = slice(pd.Timestamp(start), pd.Timestamp(end))
        return Result(
            returns=self.returns.loc[sl],
            gross_returns=self.gross_returns.loc[sl],
            costs=self.costs.loc[sl],
            turnover=self.turnover.loc[sl],
            gross_exposure=self.gross_exposure.loc[sl],
            net_exposure=self.net_exposure.loc[sl],
            positions=self.positions.loc[sl],
            notes=list(self.notes),
        )


def _holding_returns(panel: Panel, delisting: Delisting) -> tuple[np.ndarray, np.ndarray]:
    """Open-to-open return for holding from the open of d to the open of d+1.

    On a symbol's final bar the holding return is open-to-close, then the
    terminal return. Short gaps (halts) are bridged; returns are NaN where the
    symbol cannot be held.
    """
    opens = panel.open
    last_idx = panel.close.apply(lambda s: s.last_valid_index())
    first_idx = panel.open.apply(lambda s: s.first_valid_index())
    listed = pd.DataFrame(False, index=opens.index, columns=opens.columns)
    for sym in opens.columns:
        if pd.notna(first_idx[sym]) and pd.notna(last_idx[sym]):
            listed.loc[first_idx[sym] : last_idx[sym], sym] = True
    bridged = opens.ffill(limit=5).where(listed)
    ret = bridged.shift(-1) / bridged - 1.0

    final = pd.DataFrame(False, index=opens.index, columns=opens.columns)
    # The panel's own last date isn't a delisting; it's just where data ends.
    end = opens.index[-1]
    for sym, day in last_idx.items():
        if pd.notna(day) and day < end:
            final.loc[day, sym] = True
    close = panel.close
    peak = close.rolling(120, min_periods=1).max()
    failed = (close < delisting.failure_price) | (close < peak * (1 - delisting.failure_drawdown))
    last_ret = close / opens - 1.0
    terminal = np.where(failed, delisting.failure_return, 0.0)
    final_ret = (1 + last_ret) * (1 + terminal) - 1
    ret = ret.where(~final, final_ret)
    return ret.to_numpy(), final.to_numpy()


def open_to_open(panel: Panel, symbol: str) -> pd.Series:
    """Buy-and-hold returns for one symbol on the engine's clock (for benchmarks)."""
    o = panel.open[symbol]
    return (o.shift(-1) / o - 1).iloc[:-1]


def backtest(
    panel: Panel,
    weights: pd.DataFrame,
    costs: CostModel | None = None,
    delisting: Delisting | None = None,
    max_gross: float = 1.0,
) -> Result:
    costs = costs or CostModel()
    delisting = delisting or Delisting()
    notes: list[str] = []
    dates, symbols = panel.dates, panel.symbols

    unknown = weights.columns.difference(symbols)
    if len(unknown):
        raise ValueError(f"weights reference unknown symbols: {list(unknown[:5])}")
    off_calendar = weights.index.difference(dates)
    if len(off_calendar):
        notes.append(
            f"ignored {len(off_calendar)} weight rows dated off the trading calendar "
            f"(e.g. {off_calendar[0]}); date rows with panel.dates"
        )
    W = weights.reindex(index=dates, columns=symbols).astype(float)

    traded = W.notna().any(axis=1).to_numpy()
    W = W.fillna(0.0)
    outside = (W != 0) & ~panel.universe.reindex_like(W).fillna(False).astype(bool)
    if outside.to_numpy().any():
        notes.append(
            f"zeroed {int(outside.to_numpy().sum())} weights outside the universe on "
            f"{int(outside.any(axis=1).sum())} days"
        )
        W = W.mask(outside, 0.0)
    gross = W.abs().sum(axis=1)
    over = gross > max_gross + 1e-9
    if over.any():
        notes.append(f"scaled down {int(over.sum())} rows above gross exposure {max_gross}")
        W = W.div(np.maximum(gross / max_gross, 1.0), axis=0)

    w_dec = W.to_numpy()
    R, final = _holding_returns(panel, delisting)
    tradeable = panel.open.notna().to_numpy()
    bps = costs.bps(panel.dollar_volume)
    borrow_daily = costs.borrow_bps_per_year / 1e4 / 252

    n_days, n = w_dec.shape
    out = {k: np.zeros(n_days) for k in ("net", "gross", "cost", "turn", "gexp", "nexp", "npos")}
    w_cur = np.zeros(n)
    for d in range(1, n_days):
        if traded[d - 1]:
            target = w_dec[d - 1].copy()
            frozen = ~tradeable[d]
            target[frozen] = w_cur[frozen]
        else:
            target = w_cur
        delta = np.abs(target - w_cur)
        cost = float(np.nansum(delta * bps[d]) / 1e4)
        r = np.nan_to_num(R[d], nan=0.0)
        gross_ret = float(target @ r)
        borrow = float(np.clip(-target, 0, None).sum() * borrow_daily)
        net = gross_ret - cost - borrow
        out["net"][d], out["gross"][d], out["cost"][d] = net, gross_ret, cost + borrow
        out["turn"][d] = float(delta.sum())
        out["gexp"][d] = float(np.abs(target).sum())
        out["nexp"][d] = float(target.sum())
        out["npos"][d] = float((target != 0).sum())
        growth = 1.0 + net
        w_cur = target * (1.0 + r) / growth if growth > 0 else np.zeros(n)
        w_cur[final[d]] = 0.0  # delisted: proceeds become cash

    # The last date has no next open, so its holding return is unknown.
    idx = dates[1:-1]
    sl = slice(1, n_days - 1)
    series = {k: pd.Series(v[sl], index=idx) for k, v in out.items()}
    return Result(
        returns=series["net"],
        gross_returns=series["gross"],
        costs=series["cost"],
        turnover=series["turn"],
        gross_exposure=series["gexp"],
        net_exposure=series["nexp"],
        positions=series["npos"],
        notes=notes,
    )
