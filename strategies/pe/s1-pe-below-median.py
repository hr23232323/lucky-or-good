"""Stocks with a P/E below the median of profitable universe stocks."""

META = {
    "name": "P/E below median (cheap half)",
    "hypothesis": "The value effect: among profitable stocks, the cheaper half by trailing P/E "
    "earns more, because investors overpay for exciting growth stories and extrapolate recent "
    "bad news. Each month, hold the profitable universe stocks with P/E below that month's "
    "median, equally weighted.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "stock P/E",
}


def weights(panel):
    ey = panel.earnings_yield.where(panel.universe & (panel.earnings_yield > 0))
    cheap = ey.gt(ey.median(axis=1), axis=0)  # high earnings yield = low P/E
    return _monthly(panel, _equal(cheap))


def _monthly(panel, w):
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]


def _equal(mask):
    held = mask.astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)

