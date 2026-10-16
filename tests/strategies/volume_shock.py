"""Honest strategy that finds the synthetic market's planted edge."""

import numpy as np

META = {
    "name": "volume shock long-short",
    "hypothesis": "Unusually heavy volume today predicts a higher return tomorrow.",
    "expected_sign": "+",
    "author": "test fixture",
}


def weights(panel):
    logv = np.log(panel.volume)
    shock = (logv - logv.rolling(250, min_periods=50).mean().shift(1)).where(panel.universe)
    rank = shock.rank(axis=1)
    n = shock.notna().sum(axis=1)
    k = 5
    long = rank.gt(n - k, axis=0).astype(float)
    short = rank.le(k).astype(float)
    return (long - short) / (2 * k)
