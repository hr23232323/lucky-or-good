"""003 high-volume return premium."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "high-volume return premium",
    "hypothesis": "Stocks whose trading volume over the last week was unusually high relative to "
    "their own norm earn higher returns over the following month (Gervais, Kaniel & Mingelgrin, "
    "'The high-volume return premium', JF): a volume shock raises the stock's visibility, "
    "widening its investor base, while short-sale limits keep pessimists from offsetting the "
    "new demand. Long the top decile of the volume shock, short the bottom decile.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "research",
}


def weights(panel):
    vol = panel.volume
    recent = vol.rolling(5, min_periods=5).mean()
    normal = vol.shift(5).rolling(50, min_periods=40).mean()
    shock = np.log(recent / normal)
    pct = shock.where(panel.universe).rank(axis=1, pct=True)
    top = (pct > 0.9).astype(float)
    bottom = (pct <= 0.1).astype(float)
    w = 0.5 * top.div(top.sum(axis=1).replace(0, 1), axis=0) - 0.5 * bottom.div(
        bottom.sum(axis=1).replace(0, 1), axis=0
    )
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
