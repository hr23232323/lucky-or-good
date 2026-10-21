"""007 gap-down reversal candle."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "gap-down reversal candle",
    "hypothesis": "A stock that opens at least 3% below the prior close but then closes above "
    "its open has had its overnight selling (stop orders, retail panic at the open) absorbed "
    "by buyers during the day; the selling pressure was temporary, so the price keeps "
    "recovering over the next week. Long for five days after the pattern.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "pattern",
}

GAP = 0.03
HOLD = 5
SLOT = 0.02  # 2% of capital per position; scaled down only if more than 50 are held


def weights(panel):
    prev = panel.close.shift(1)
    event = (panel.open < prev * (1 - GAP)) & (panel.close > panel.open) & panel.universe
    held = event.astype(float).rolling(HOLD, min_periods=1).max().fillna(0.0)
    held = held * panel.universe.astype(float)
    n = held.sum(axis=1)
    per = pd.Series(SLOT, index=held.index).where(n * SLOT <= 1, 1 / n.replace(0, np.nan))
    return held.mul(per.fillna(0.0), axis=0)
