"""Stocks with a P/E above the median of profitable universe stocks."""

META = {
    "name": "P/E above median (dear half)",
    "hypothesis": "The other bucket of the same split, tested in its own right: expensive "
    "stocks are expensive because the market expects faster growth, and in a decade when "
    "growth companies led, the dear half may have won. Each month, hold the profitable "
    "universe stocks with P/E above the median, equally weighted.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "stock P/E",
}


def weights(panel):
    ey = panel.earnings_yield.where(panel.universe & (panel.earnings_yield > 0))
    dear = ey.lt(ey.median(axis=1), axis=0)
    return _monthly(panel, _equal(dear))


def _monthly(panel, w):
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]


def _equal(mask):
    held = mask.astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)

