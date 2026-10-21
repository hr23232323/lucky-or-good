"""011 residual, volatility-scaled weekly reversal."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "residual z-score reversal",
    "hypothesis": "Weekly reversal is liquidity provision: stocks pushed down by temporary "
    "selling bounce back. The raw 5-day loser decile mixes that with stocks that merely fell "
    "with the market (high beta) or move a lot anyway (high vol). Removing the beta-predicted "
    "market move and dividing by the stock's own volatility isolates unusual idiosyncratic "
    "drops, which should revert more cleanly. Long the bottom decile of the z-score, weekly.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "numeric",
}

BETA_WIN = 120


def weights(panel):
    c = panel.close
    uni = panel.universe
    daily = c.pct_change(fill_method=None)
    mkt = daily.where(uni).mean(axis=1)
    # Rolling beta of each stock on the equal-weighted market (trailing data only).
    mx = daily.mul(mkt, axis=0).rolling(BETA_WIN, min_periods=100).mean()
    mean_x = daily.rolling(BETA_WIN, min_periods=100).mean()
    mean_m = mkt.rolling(BETA_WIN, min_periods=100).mean()
    var_m = mkt.rolling(BETA_WIN, min_periods=100).var()
    beta = (mx - mean_x.mul(mean_m, axis=0)).div(var_m, axis=0)
    r5 = c / c.shift(5) - 1
    m5 = (1 + mkt.fillna(0.0)).rolling(5).apply(np.prod, raw=True) - 1
    resid = r5 - beta.mul(m5, axis=0)
    vol = daily.rolling(60, min_periods=50).std() * np.sqrt(5)
    z = resid / vol
    pct = z.where(uni).rank(axis=1, pct=True)
    held = (pct <= 0.1).astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    week_end = panel.dates.to_series().groupby(panel.dates.to_period("W")).max()
    return w.loc[week_end.values]
