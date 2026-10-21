"""Scale exposure by where CAPE sits in its past 20 years: cheap third, middle, dear third."""

META = {
    "name": "CAPE terciles, graded exposure",
    "hypothesis": "All-in or all-out on one threshold is fragile. Rank today's CAPE within the "
    "past twenty years: in the cheapest third hold 100% of the equal-weighted universe, in "
    "the middle third 60%, in the dearest third 20%. Valuation should shift the odds, not "
    "call tops, so a graded bet should keep most of the upside with less drawdown.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "market P/E",
}


def weights(panel):
    cape = panel.market["cape"]
    rank = cape.rolling(240, min_periods=240).rank(pct=True)
    exposure = (0.2 + 0.4 * (rank <= 2 / 3) + 0.4 * (rank <= 1 / 3)).where(rank.notna())
    return _hold_universe(panel, exposure)


def _hold_universe(panel, exposure):
    held = panel.universe.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    w = w.mul(exposure.reindex(panel.dates, method="ffill").fillna(0.0), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]

