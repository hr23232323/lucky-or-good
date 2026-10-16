META = {
    "name": "52-week high",
    "hypothesis": "Stocks closest to their 52-week high outperform (George & Hwang 2004).",
    "expected_sign": "+",
    "author": "baseline",
}

TOP = 0.1


def weights(panel):
    nearness = panel.close / panel.high.rolling(252, min_periods=200).max()
    pct = nearness.where(panel.universe).rank(axis=1, pct=True)
    held = (pct > 1 - TOP).astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
