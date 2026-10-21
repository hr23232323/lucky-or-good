"""004 RSI(2) pullback in an uptrend (Connors-style)."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "RSI(2) pullback in uptrend",
    "hypothesis": "The retail-popular Connors rule: in a stock above its 200-day average, a "
    "two-day RSI below 10 marks a short-lived oversold pullback that liquidity providers are "
    "paid to absorb, so it bounces. Buy then, sell when the close recovers above the 5-day "
    "average. Long-only.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "popular-online",
}

MAX_POS = 0.10  # no single position above 10% of capital


def rsi(close, n):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def weights(panel):
    c = panel.close
    ma200 = c.rolling(200, min_periods=180).mean()
    ma5 = c.rolling(5, min_periods=5).mean()
    r = rsi(c, 2)
    entry = (c > ma200) & (r < 10) & panel.universe
    exit_ = (c > ma5) | ~panel.universe | c.isna()
    state = pd.DataFrame(np.where(entry, 1.0, np.where(exit_, 0.0, np.nan)), index=c.index,
                         columns=c.columns).ffill().fillna(0.0)
    n = state.sum(axis=1)
    per = (1.0 / n.replace(0, np.nan)).clip(upper=MAX_POS).fillna(0.0)
    return state.mul(per, axis=0)
