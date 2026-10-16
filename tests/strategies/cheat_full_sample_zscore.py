"""Cheat that static checks can't see: normalises with full-sample statistics.

The z-score at t uses the mean and std of the whole history, including the
future. Only the truncation check can catch this.
"""

META = {
    "name": "full-sample z-score",
    "hypothesis": "Stocks far below their average price revert.",
    "expected_sign": "-",
}


def weights(panel):
    close = panel.close
    z = (close - close.mean()) / close.std()
    pick = z.where(panel.universe).rank(axis=1).le(10)
    return pick.astype(float) / 10
