"""001 MAX effect (lottery stocks underperform)."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "MAX effect long-short",
    "hypothesis": "Stocks with the largest single-day return in the past month are lottery-like "
    "and overpriced by investors who like positive skew, so they underperform those with the "
    "smallest maximum (Bali, Cakici & Whitelaw, 'Maxing out', JFE). Short-sale costs and "
    "arbitrage risk keep the gap open. Long low-MAX decile, short high-MAX decile.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "research",
}


def weights(panel):
    daily = panel.close.pct_change(fill_method=None)
    mx = daily.rolling(21, min_periods=18).max()
    pct = mx.where(panel.universe).rank(axis=1, pct=True)
    low = (pct <= 0.1).astype(float)
    high = (pct > 0.9).astype(float)
    w = 0.5 * low.div(low.sum(axis=1).replace(0, 1), axis=0) - 0.5 * high.div(
        high.sum(axis=1).replace(0, 1), axis=0
    )
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
