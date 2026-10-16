META = {
    "name": "low volatility",
    "hypothesis": "The calmest stocks earn as much as risky ones with less risk (Ang et al. 2006).",
    "expected_sign": "+",
    "author": "baseline",
}

BOTTOM = 0.2


def weights(panel):
    daily = panel.close.pct_change(fill_method=None)
    vol = daily.rolling(60, min_periods=50).std()
    pct = vol.where(panel.universe).rank(axis=1, pct=True)
    held = (pct <= BOTTOM).astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
