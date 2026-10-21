"""006 Sell in May and go away (Halloween indicator)."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "sell in May",
    "hypothesis": "The old trader's adage: equities earn most of their return from November "
    "to April and little from May to October, attributed to seasonal shifts in risk appetite, "
    "vacations and fund flows (the 'Halloween indicator'). Hold the equal-weighted universe "
    "for the November-April half-year and cash for May-October; should beat holding all year "
    "per unit of risk.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "popular-online",
}

# Months whose month-end close starts a winter-half holding month (Nov..Apr).
INVEST_AFTER = {10, 11, 12, 1, 2, 3}


def weights(panel):
    held = panel.universe.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    w = w.loc[month_end.values]
    invest = pd.Series(w.index.month, index=w.index).isin(INVEST_AFTER).astype(float)
    return w.mul(invest, axis=0)
