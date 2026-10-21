"""009 wide-range day closing at the high, hedged."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "wide-range strong close, hedged",
    "hypothesis": "A day with at least twice the stock's normal high-low range that closes in "
    "the top tenth of that range, up on the day, shows buyers still pressing into the close "
    "after a big move; demand that persists to the closing auction tends to come from "
    "institutions with more to buy, so the stock beats the market over the next week. Long "
    "the event stocks, short the equal-weighted universe by the same amount.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "pattern",
}

HOLD = 5
SLOT = 0.01  # long side: 1% per name, at most 0.5 in total; hedge matches it


def weights(panel):
    rng = panel.high - panel.low
    avg = rng.shift(1).rolling(20, min_periods=15).mean()
    clv = (panel.close - panel.low) / rng.replace(0, np.nan)
    up = panel.close > panel.close.shift(1)
    event = (rng > 2 * avg) & (clv > 0.9) & up & panel.universe
    held = event.astype(float).rolling(HOLD, min_periods=1).max().fillna(0.0)
    held = held * panel.universe.astype(float)
    n = held.sum(axis=1)
    per = pd.Series(SLOT, index=held.index).where(n * SLOT <= 0.5, 0.5 / n.replace(0, np.nan))
    long = held.mul(per.fillna(0.0), axis=0)
    uni = panel.universe.astype(float)
    ew = uni.div(uni.sum(axis=1).replace(0, 1), axis=0)
    return long - ew.mul(long.sum(axis=1), axis=0)
