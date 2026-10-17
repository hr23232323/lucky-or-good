"""NNN short name.

Copy to strategies/candidates/NNN-short-name.py and fill in.

panel has wide DataFrames (index = date, columns = symbol):
    panel.open, panel.high, panel.low, panel.close, panel.volume,
    panel.dollar_volume, panel.universe (bool: may hold this symbol today)
plus panel.dates and panel.symbols.

Return target weights: index = dates, columns = symbols, values = fraction of
capital (negative = short). Gross exposure (longs plus shorts) is capped at
1.0, so a dollar-neutral book is 0.5 long and 0.5 short. Row t is decided
after the close of t and traded at the next open; the judge applies that lag.
A row that's all NaN (or missing) means "don't trade today". To rebalance
monthly, return only month-end rows.

Allowed imports: numpy, pandas, math, statistics, functools, itertools,
collections, typing, dataclasses. No files, no network, no dates or tickers.
"""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "short name",
    "hypothesis": "What behaviour you expect, why it should exist, and which direction.",
    "expected_sign": "+",  # sign you expect for this portfolio's returns, as coded
    "author": "model or person",
}

LONG_ONLY = True  # set False for the long-short version below


def weights(panel):
    score = panel.close / panel.close.shift(20) - 1  # replace with your signal
    pct = score.where(panel.universe).rank(axis=1, pct=True)
    top = (pct > 0.9).astype(float)
    if LONG_ONLY:
        w = top.div(top.sum(axis=1).replace(0, 1), axis=0)
    else:
        # Dollar-neutral: 0.5 long the top decile, 0.5 short the bottom decile.
        bottom = (pct <= 0.1).astype(float)
        w = 0.5 * top.div(top.sum(axis=1).replace(0, 1), axis=0) - 0.5 * bottom.div(
            bottom.sum(axis=1).replace(0, 1), axis=0
        )
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
