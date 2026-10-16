META = {
    "name": "200-day trend",
    "hypothesis": "Stocks trading above their 200-day average keep rising; those below don't.",
    "expected_sign": "+",
    "author": "baseline",
}


def weights(panel):
    ma = panel.close.rolling(200, min_periods=180).mean()
    held = ((panel.close > ma) & panel.universe).astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
