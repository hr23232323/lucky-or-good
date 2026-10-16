META = {
    "name": "12-1 momentum",
    "hypothesis": "Stocks with the best returns over the past year, skipping the last month, "
    "keep outperforming (Jegadeesh & Titman 1993).",
    "expected_sign": "+",
    "author": "baseline",
}

TOP = 0.1


def weights(panel):
    past = panel.close.shift(21) / panel.close.shift(252) - 1
    score = past.where(panel.universe)
    pct = score.rank(axis=1, pct=True)
    held = (pct > 1 - TOP).astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
