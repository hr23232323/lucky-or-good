"""Market P/E below its 10-year average: own the market; above it: cash."""

META = {
    "name": "market P/E below 10y average",
    "hypothesis": "Same bet as the median version, with the past ten years' average P/E as "
    "the line. The average is pulled up by earnings collapses (P/E spikes when earnings "
    "vanish), so this version calls the market cheap more often after a crash. Hold the "
    "equal-weighted universe when P/E is below the average, cash otherwise, monthly.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "market P/E",
}


def weights(panel):
    pe = panel.market["pe"]
    mean = pe.rolling(120, min_periods=120).mean()
    cheap = (pe < mean).astype(float).where(mean.notna())
    return _hold_universe(panel, cheap)


def _hold_universe(panel, exposure):
    held = panel.universe.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    w = w.mul(exposure.reindex(panel.dates, method="ffill").fillna(0.0), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]

