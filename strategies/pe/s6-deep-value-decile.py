"""Only the cheapest tenth of profitable stocks by P/E."""

META = {
    "name": "deep value (cheapest decile)",
    "hypothesis": "If cheapness pays, the cheapest stocks should pay most, though they also "
    "include value traps whose earnings are about to fall. Hold the tenth of profitable "
    "universe stocks with the lowest P/E, equally weighted, monthly.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "stock P/E",
}


def weights(panel):
    ey = panel.earnings_yield.where(panel.universe & (panel.earnings_yield > 0))
    rank = ey.rank(axis=1, pct=True)
    return _monthly(panel, _equal(rank > 0.9))


def _monthly(panel, w):
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]


def _equal(mask):
    held = mask.astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)

