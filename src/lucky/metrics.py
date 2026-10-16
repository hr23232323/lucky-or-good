"""Performance metrics and the statistics that keep them honest.

Sharpe ratios here are annualised from daily returns (sqrt(252)) unless a name
says ``per_period``. The deflation formulas follow Bailey & Lopez de Prado,
"The Deflated Sharpe Ratio" (2014): they work on per-period Sharpe ratios.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

DAYS = 252
_N = NormalDist()
EULER_GAMMA = 0.5772156649015329


def sharpe(returns: pd.Series) -> float:
    r = returns.dropna()
    sd = r.std(ddof=1)
    if len(r) < 2 or not math.isfinite(sd) or sd < 1e-12:
        return 0.0
    return float(r.mean() / sd * math.sqrt(DAYS))


def max_drawdown(returns: pd.Series) -> float:
    wealth = (1 + returns.fillna(0)).cumprod()
    return float((wealth / wealth.cummax() - 1).min()) if len(wealth) else 0.0


def annual_return(returns: pd.Series) -> float:
    r = returns.dropna()
    if r.empty:
        return 0.0
    total = float((1 + r).prod())
    return total ** (DAYS / len(r)) - 1 if total > 0 else -1.0


def psr(sr: float, sr_benchmark: float, n_obs: int, skew: float, kurtosis: float) -> float:
    """Probabilistic Sharpe Ratio: P(true Sharpe > benchmark), per-period inputs.

    ``kurtosis`` is raw (normal = 3), not excess.
    """
    if n_obs < 2:
        return 0.0
    var = (1 - skew * sr + (kurtosis - 1) / 4 * sr**2) / (n_obs - 1)
    if var <= 0:
        return 0.0
    return _N.cdf((sr - sr_benchmark) / math.sqrt(var))


def expected_max_sharpe(n_trials: int, trial_sharpe_var: float) -> float:
    """Expected best per-period Sharpe among ``n_trials`` strategies with no skill.

    ``trial_sharpe_var`` is the variance of per-period Sharpe ratios across the
    trials actually run. More trials, or wilder trials, raise the bar.
    """
    if n_trials <= 1 or trial_sharpe_var <= 0:
        return 0.0
    n = n_trials
    return math.sqrt(trial_sharpe_var) * (
        (1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n) + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n * math.e))
    )


def deflated_sharpe(returns: pd.Series, n_trials: int, trial_sharpe_var: float) -> float:
    """P(true Sharpe > 0) after accounting for how many strategies were tried."""
    r = returns.dropna()
    if len(r) < 3 or r.std(ddof=1) < 1e-12:
        return 0.0
    sr = float(r.mean() / r.std(ddof=1))
    bar = expected_max_sharpe(n_trials, trial_sharpe_var)
    return psr(sr, bar, len(r), float(r.skew()), float(r.kurt()) + 3.0)


def summary(result, benchmark: pd.Series | None = None) -> dict:
    """Headline numbers for a backtest ``Result`` (see ``lucky.engine``)."""
    r = result.returns.dropna()
    years = len(r) / DAYS
    sr = sharpe(r)
    out = {
        "days": int(len(r)),
        "years": round(years, 2),
        "sharpe": round(sr, 3),
        "t_stat": round(sr * math.sqrt(years), 2) if years > 0 else 0.0,
        "annual_return": round(annual_return(r), 4),
        "annual_vol": round(float(r.std(ddof=1) * math.sqrt(DAYS)), 4) if len(r) > 1 else 0.0,
        "max_drawdown": round(max_drawdown(r), 4),
        "gross_sharpe": round(sharpe(result.gross_returns), 3),
        "annual_cost_drag": round(float(result.costs.mean() * DAYS), 4),
        "annual_turnover": round(float(result.turnover.mean() * DAYS), 2),
        "avg_gross_exposure": round(float(result.gross_exposure.mean()), 3),
        "avg_positions": round(float(result.positions.mean()), 1),
        "skew": round(float(r.skew()), 3) if len(r) > 2 else 0.0,
        "kurtosis": round(float(r.kurt()) + 3.0, 3) if len(r) > 3 else 3.0,
    }
    if benchmark is not None:
        b = benchmark.reindex(r.index).dropna()
        out["benchmark_sharpe"] = round(sharpe(b), 3)
        out["benchmark_annual_return"] = round(annual_return(b), 4)
        if len(b) > 2 and b.var() > 0:
            aligned = r.reindex(b.index)
            beta = float(np.cov(aligned, b)[0, 1] / b.var())
            out["beta"] = round(beta, 3)
            out["alpha_sharpe"] = round(sharpe(aligned - beta * b), 3)
    return out
