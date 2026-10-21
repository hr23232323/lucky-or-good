"""CAPE below its 10-year median: own the market; above it: cash."""

META = {
    "name": "CAPE below 10y median",
    "hypothesis": "One year of earnings is noisy (recessions make P/E spike). Shiller's CAPE "
    "divides price by ten years of inflation-adjusted earnings, which is the version of "
    "valuation that has predicted long-run returns. Hold the equal-weighted universe when "
    "CAPE is below its median of the past ten years, cash otherwise, monthly.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "market P/E",
}


def weights(panel):
    cape = panel.market["cape"]
    median = cape.rolling(120, min_periods=120).median()
    cheap = (cape < median).astype(float).where(median.notna())
    return _hold_universe(panel, cheap)


def _hold_universe(panel, exposure):
    held = panel.universe.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    w = w.mul(exposure.reindex(panel.dates, method="ffill").fillna(0.0), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]

