META = {
    "name": "equal weight",
    "hypothesis": "Holding every liquid stock equally, rebalanced monthly, is a tough benchmark.",
    "expected_sign": "+",
    "author": "baseline",
}


def weights(panel):
    held = panel.universe.astype(float)
    w = held.div(held.sum(axis=1).replace(0, 1), axis=0)
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
