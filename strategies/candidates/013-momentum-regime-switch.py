"""013 regime switch: momentum in calm bull states, low volatility otherwise."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "momentum / low-vol regime switch",
    "hypothesis": "Momentum's crashes come in 'panic states' after market declines with high "
    "volatility, when beaten-down losers rebound hardest (Daniel & Moskowitz, 'Momentum "
    "crashes'). Using the equal-weighted market built from the panel, hold the 12-1 momentum "
    "top decile when the market's two-year return is positive and its three-month volatility "
    "is below its two-year median; otherwise hold the low-volatility quintile, which is "
    "defensive in stress. Long-only, monthly; should beat either style held alone.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "market-regime",
}


def equal(mask):
    m = mask.astype(float)
    return m.div(m.sum(axis=1).replace(0, 1), axis=0)


def weights(panel):
    c = panel.close
    uni = panel.universe
    daily = c.pct_change(fill_method=None)
    mkt = daily.where(uni).mean(axis=1).fillna(0.0)
    level = (1 + mkt).cumprod()
    mkt_2y = level / level.shift(504) - 1
    mvol = mkt.rolling(63, min_periods=60).std()
    mvol_med = mvol.rolling(504, min_periods=252).median()
    calm_bull = (mkt_2y > 0) & (mvol < mvol_med)

    mom = (c.shift(21) / c.shift(252) - 1).where(uni).rank(axis=1, pct=True)
    vol = daily.rolling(60, min_periods=50).std().where(uni).rank(axis=1, pct=True)
    w_mom = equal(mom > 0.9)
    w_low = equal(vol <= 0.2)
    on = calm_bull.astype(float)
    w = w_mom.mul(on, axis=0) + w_low.mul(1 - on, axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
