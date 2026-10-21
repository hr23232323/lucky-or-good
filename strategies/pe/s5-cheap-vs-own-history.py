"""Stocks whose P/E is below their own one-year median P/E."""

META = {
    "name": "cheap versus its own history",
    "hypothesis": "Comparing P/Es across companies mixes industries that always trade cheap "
    "(banks, utilities) with ones that never do (software). Comparing a stock with itself "
    "avoids that: a stock trading below its own usual P/E has been marked down, and part "
    "of that markdown reverses. Hold profitable universe stocks whose earnings yield is "
    "above its median of the past year (the longest history every period has), equally weighted, monthly.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "stock P/E",
}


def weights(panel):
    ey = panel.earnings_yield
    usual = ey.rolling(252, min_periods=200).median()
    cheap = panel.universe & (ey > 0) & (ey > usual)
    return _monthly(panel, _equal(cheap))


def _monthly(panel, w):
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]


def _equal(mask):
    held = mask.astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)

