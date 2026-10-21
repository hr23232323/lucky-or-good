"""012 breadth regime: own the market only when most stocks are in uptrends."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "breadth regime timing",
    "hypothesis": "When fewer than half of liquid stocks trade above their 200-day average, the "
    "market is in a broad downtrend in which volatility is high and forward returns per unit "
    "of risk are poor (trends in the aggregate persist because risk appetite and leverage "
    "unwind slowly). Hold the equal-weighted universe when breadth is above 50%, cash "
    "otherwise, decided monthly.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "market-regime",
}


def weights(panel):
    c = panel.close
    uni = panel.universe
    ma = c.rolling(200, min_periods=180).mean()
    above = (c > ma).where(uni & ma.notna())
    breadth = above.mean(axis=1)
    held = uni.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    on = (breadth > 0.5).astype(float)
    w = w.mul(on, axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
