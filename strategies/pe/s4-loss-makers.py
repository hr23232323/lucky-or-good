"""Stocks with negative trailing earnings (no meaningful P/E)."""

META = {
    "name": "loss-makers (negative earnings)",
    "hypothesis": "A bucket P/E can't rank: companies losing money. They're riskier and often "
    "speculative growth bets, which investors overpay for like lottery tickets, so they "
    "should earn less per unit of risk than profitable stocks. Hold the universe stocks with "
    "negative trailing earnings, equally weighted; expect a Sharpe well below the pool of "
    "all stocks with known earnings.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "stock P/E",
}


def weights(panel):
    losing = panel.universe & (panel.earnings_yield < 0)
    return _monthly(panel, _equal(losing))


def _monthly(panel, w):
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]


def _equal(mask):
    held = mask.astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)

