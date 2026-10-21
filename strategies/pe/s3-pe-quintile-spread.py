"""Long the cheapest fifth by P/E, short the dearest fifth, dollar-neutral."""

META = {
    "name": "P/E quintile spread (long cheap, short dear)",
    "hypothesis": "Holding only one bucket mostly measures the market. The textbook value test "
    "is the spread: long the fifth of profitable stocks with the lowest P/E, short the fifth "
    "with the highest, equal dollars on each side, monthly. Positive if cheap beats dear "
    "regardless of where the market goes.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "stock P/E",
}


def weights(panel):
    ey = panel.earnings_yield.where(panel.universe & (panel.earnings_yield > 0))
    rank = ey.rank(axis=1, pct=True)
    long = _equal(rank > 0.8) * 0.5
    short = _equal(rank <= 0.2) * 0.5
    return _monthly(panel, long - short)


def _monthly(panel, w):
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]


def _equal(mask):
    held = mask.astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)

