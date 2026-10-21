"""CAPE below its median since the 1880s: own the market; above it: cash."""

META = {
    "name": "CAPE below long-run median",
    "hypothesis": "The classic value-investor rule: the market is cheap only by its whole "
    "history's standard, not by recent years'. Hold the equal-weighted universe when CAPE is "
    "below its median over all history up to that month, cash otherwise. Expect it to sit "
    "out most of the past 30 years, so this tests what being 'too early' costs.",
    "expected_sign": "+",
    "author": "human idea (Harsh), written by the builder",
    "category": "market P/E",
}


def weights(panel):
    cape = panel.market["cape"]
    median = cape.expanding(min_periods=240).median()
    cheap = (cape < median).astype(float).where(median.notna())
    return _hold_universe(panel, cheap)


def _hold_universe(panel, exposure):
    held = panel.universe.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    w = w.mul(exposure.reindex(panel.dates, method="ffill").fillna(0.0), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]

