"""Honest strategy with no edge in the synthetic market: 6-month momentum."""

META = {
    "name": "6-month momentum",
    "hypothesis": "Recent winners keep winning.",
    "expected_sign": "+",
}


def weights(panel):
    past = panel.close.shift(21) / panel.close.shift(126) - 1
    score = past.where(panel.universe)
    top = score.rank(axis=1, ascending=False).le(10)
    w = top.astype(float).div(top.sum(axis=1).replace(0, 1), axis=0)
    month_ends = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_ends.values]
