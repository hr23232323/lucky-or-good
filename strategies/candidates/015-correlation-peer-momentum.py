"""015 correlation-peer momentum: follow what your closest co-movers just did."""

import numpy as np  # noqa: F401
import pandas as pd  # noqa: F401

META = {
    "name": "correlation-peer momentum",
    "hypothesis": "Economically linked firms (same industry, suppliers, customers) share news, "
    "but attention is limited, so news priced in some firms reaches their linked firms with a "
    "lag. Without industry data, find each stock's ten most correlated peers from a year of "
    "market-residual daily returns; stocks whose peers rose most over the last month should "
    "rise next month, those whose peers fell most should fall. Long top decile of peer "
    "return, short bottom decile, monthly.",
    "expected_sign": "+",
    "author": "claude-opus-5-5",
    "category": "novel",
}

WIN = 252
PEERS = 10


def weights(panel):
    c = panel.close
    uni = panel.universe
    daily = c.pct_change(fill_method=None)
    mkt = daily.where(uni).mean(axis=1)
    resid = daily.sub(mkt, axis=0)
    r21 = c / c.shift(21) - 1
    month_end = panel.dates.to_series().groupby(panel.dates.to_period("M")).max().values
    pos = {d: i for i, d in enumerate(panel.dates)}
    out = pd.DataFrame(np.nan, index=month_end, columns=c.columns)
    for d in month_end:
        i = pos[d]
        if i + 1 < WIN:
            continue
        window = resid.iloc[i + 1 - WIN : i + 1]
        ok = uni.loc[d] & (window.notna().sum() >= 200) & r21.loc[d].notna()
        cols = ok[ok].index
        if len(cols) < 50:
            continue
        x = window[cols].fillna(0.0).to_numpy()
        x = x - x.mean(axis=0)
        sd = x.std(axis=0)
        sd[sd == 0] = np.nan
        z = x / sd
        corr = np.nan_to_num(z.T @ z / len(z), nan=-1.0)
        np.fill_diagonal(corr, -np.inf)
        peers = np.argpartition(-corr, PEERS, axis=1)[:, :PEERS]
        own = r21.loc[d, cols].to_numpy()
        peer_ret = own[peers].mean(axis=1)
        pct = pd.Series(peer_ret, index=cols).rank(pct=True)
        top = (pct > 0.9).astype(float)
        bot = (pct <= 0.1).astype(float)
        row = 0.5 * top / max(top.sum(), 1) - 0.5 * bot / max(bot.sum(), 1)
        out.loc[d] = 0.0
        out.loc[d, cols] = row.to_numpy()
    return out
