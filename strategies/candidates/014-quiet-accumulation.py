"""014 quiet accumulation: up-volume share among flat stocks."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "quiet accumulation",
    "hypothesis": "A large patient buyer splitting a big order shows up as volume concentrated "
    "on up days while the price barely moves, because the buyer works the order to avoid "
    "impact; a patient seller shows the mirror image. Among stocks whose 40-day return is in "
    "the middle third, long the decile with the highest share of volume on up days and short "
    "the decile with the lowest: the unfinished order keeps pushing in its direction.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "novel",
}

WIN = 40


def weights(panel):
    c = panel.close
    uni = panel.universe
    vol = panel.volume
    up = (c > c.shift(1)).astype(float)
    up_vol = (vol * up).rolling(WIN, min_periods=35).sum()
    all_vol = vol.rolling(WIN, min_periods=35).sum()
    share = up_vol / all_vol.replace(0, np.nan)
    ret = c / c.shift(WIN) - 1
    ret_pct = ret.where(uni).rank(axis=1, pct=True)
    flat = (ret_pct > 1 / 3) & (ret_pct <= 2 / 3)
    pct = share.where(flat).rank(axis=1, pct=True)
    top = (pct > 0.9).astype(float)
    bottom = (pct <= 0.1).astype(float)
    w = 0.5 * top.div(top.sum(axis=1).replace(0, 1), axis=0) - 0.5 * bottom.div(
        bottom.sum(axis=1).replace(0, 1), axis=0
    )
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max()
    return w.loc[month_end.values]
