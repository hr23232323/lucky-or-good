META = {
    "name": "weekly reversal",
    "hypothesis": "Last week's biggest losers bounce back next week (Lehmann 1990).",
    "expected_sign": "+",
    "author": "baseline",
}

BOTTOM = 0.1


def weights(panel):
    past = panel.close / panel.close.shift(5) - 1
    pct = past.where(panel.universe).rank(axis=1, pct=True)
    held = (pct <= BOTTOM).astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    week_end = panel.dates.to_series().groupby(panel.dates.to_period("W")).max()
    return w.loc[week_end.values]
