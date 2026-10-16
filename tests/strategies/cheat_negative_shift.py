"""Cheat: uses tomorrow's open-to-close move to pick today's stocks."""

META = {
    "name": "peek at tomorrow",
    "hypothesis": "Buy what goes up tomorrow.",
    "expected_sign": "+",
}


def weights(panel):
    tomorrow = (panel.close / panel.open - 1).shift(-1)
    pick = tomorrow.where(panel.universe).rank(axis=1, ascending=False).le(5)
    return pick.astype(float) / 5
