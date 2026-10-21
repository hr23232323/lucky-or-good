"""008 relative-strength breakout on volume."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "relative breakout on volume",
    "hypothesis": "A stock whose price relative to the equal-weighted market closes at a new "
    "50-day high on at least 1.5x its normal volume is being re-rated by large buyers who "
    "build positions over weeks; the breakout marks the start of that accumulation, so it "
    "keeps outperforming for about a month. Long for 20 days after the breakout.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "pattern",
}

LOOK = 50
HOLD = 20
SLOT = 0.02


def weights(panel):
    c = panel.close
    daily = c.pct_change(fill_method=None)
    mkt = daily.where(panel.universe).mean(axis=1).fillna(0.0)
    index = (1 + mkt).cumprod()
    rel = c.div(index, axis=0)
    prior_high = rel.shift(1).rolling(LOOK, min_periods=LOOK).max()
    avg_vol = panel.volume.shift(1).rolling(LOOK, min_periods=40).mean()
    event = (rel > prior_high) & (panel.volume > 1.5 * avg_vol) & panel.universe
    held = event.astype(float).rolling(HOLD, min_periods=1).max().fillna(0.0)
    held = held * panel.universe.astype(float)
    n = held.sum(axis=1)
    per = pd.Series(SLOT, index=held.index).where(n * SLOT <= 1, 1 / n.replace(0, np.nan))
    return held.mul(per.fillna(0.0), axis=0)
