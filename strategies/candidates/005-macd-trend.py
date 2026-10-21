"""005 MACD bullish state, weekly."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "MACD bullish state",
    "hypothesis": "The forum-standard MACD(12,26,9) rule: hold a stock while its MACD line is "
    "above both zero and its signal line, i.e. medium-term trend up and accelerating. If "
    "investors under-react to news, prices trend and this captures the middle of the move. "
    "Long-only, equal weight across bullish stocks, rebalanced weekly to limit costs.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "popular-online",
}


def weights(panel):
    c = panel.close
    fast = c.ewm(span=12, adjust=False, min_periods=26).mean()
    slow = c.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = fast - slow
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    held = ((macd > 0) & (macd > signal) & panel.universe).astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    week_end = panel.dates.to_series().groupby(panel.dates.to_period("W")).max()
    return w.loc[week_end.values]
