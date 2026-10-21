"""Market P/E below its 10-year median: own the market; above it: cash."""

META = {
    "name": "market P/E below 10y median",
    "hypothesis": "When the S&P 500's trailing P/E is below its own median of the past ten "
    "years, future returns are higher (cheap markets pay more); when above, risk per unit of "
    "return is worse. Hold the equal-weighted universe when cheap, cash when expensive, "
    "decided monthly from the latest published P/E.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "market P/E",
}


def weights(panel):
    pe = panel.market["pe"]
    median = pe.rolling(120, min_periods=120).median()
    cheap = (pe < median).astype(float).where(median.notna())
    return _hold_universe(panel, cheap)


def _hold_universe(panel, exposure):
    held = panel.universe.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    w = w.mul(exposure.reindex(panel.dates, method="ffill").fillna(0.0), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]

