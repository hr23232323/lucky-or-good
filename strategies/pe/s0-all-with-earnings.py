"""Reference for the stock P/E buckets: every universe stock whose earnings are known."""

META = {
    "name": "all stocks with known earnings",
    "hypothesis": "Not a prediction: the pool every P/E bucket is cut from. Per-stock earnings "
    "only exist for companies the SEC data can be matched to, which may not be a random "
    "subset. Each bucket should be compared with this, not just with the whole market.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "stock P/E",
}


def weights(panel):
    known = panel.universe & panel.earnings_yield.notna()
    return _monthly(panel, _equal(known))


def _monthly(panel, w):
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]


def _equal(mask):
    held = mask.astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)

