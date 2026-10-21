"""002 cross-sectional return seasonality."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "return seasonality",
    "hypothesis": "A stock's return over the coming month resembles its return over the same "
    "month in earlier years (Heston & Sadka, 'Seasonality in the cross-section of stock "
    "returns', JFE), plausibly from recurring flows, earnings timing and information releases "
    "that repeat at an annual rhythm. Long the decile with the highest average same-month "
    "return over the last five years, short the lowest.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "research",
}

YEAR = 252
MONTH = 21
YEARS = 5


def weights(panel):
    c = panel.close
    parts = []
    for k in range(1, YEARS + 1):
        # Return over the month that followed this same point k years ago (all in the past).
        parts.append(c.shift(k * YEAR - MONTH) / c.shift(k * YEAR) - 1)
    stacked = sum(p.fillna(0) for p in parts)
    count = sum(p.notna().astype(float) for p in parts)
    score = (stacked / count.replace(0, np.nan)).where(count >= 3)
    pct = score.where(panel.universe).rank(axis=1, pct=True)
    top = (pct > 0.9).astype(float)
    bottom = (pct <= 0.1).astype(float)
    w = 0.5 * top.div(top.sum(axis=1).replace(0, 1), axis=0) - 0.5 * bottom.div(
        bottom.sum(axis=1).replace(0, 1), axis=0
    )
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
