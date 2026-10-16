META = {
    "name": "buy the dip",
    "hypothesis": "Liquid stocks that fell more than 10% in a week are oversold and recover.",
    "expected_sign": "+",
    "author": "baseline",
}


def weights(panel):
    drop = panel.close / panel.close.shift(5) - 1
    held = ((drop < -0.10) & panel.universe).astype(float)
    return held.div(held.sum(axis=1).replace(0, 1), axis=0)
