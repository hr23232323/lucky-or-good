"""010 composite rank: calm, trending, non-lottery."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "composite rank (vol, momentum, MAX)",
    "hypothesis": "Averaging cross-sectional ranks of three weakly related signals (low 60-day "
    "volatility, high 12-1 momentum, low maximum daily return over the past month) cancels "
    "much of each signal's noise while keeping their separate premia (leverage-constrained "
    "investors overpay for risk and lottery payoffs, and under-react to news), so the top "
    "decile of the average rank beats any one signal per unit of risk. Long-only, monthly.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "numeric",
}


def weights(panel):
    c = panel.close
    uni = panel.universe
    daily = c.pct_change(fill_method=None)
    vol = daily.rolling(60, min_periods=50).std()
    mom = c.shift(21) / c.shift(252) - 1
    mx = daily.rolling(21, min_periods=18).max()
    r_vol = (-vol).where(uni).rank(axis=1, pct=True)
    r_mom = mom.where(uni).rank(axis=1, pct=True)
    r_max = (-mx).where(uni).rank(axis=1, pct=True)
    score = (r_vol + r_mom + r_max) / 3
    pct = score.rank(axis=1, pct=True)
    top = (pct > 0.9).astype(float)
    w = top.div(top.sum(axis=1).replace(0, 1), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
