"""Tiny hand-built panels for exact engine tests."""

import pandas as pd

from lucky.data import Panel


def make_panel(
    opens: dict[str, list[float]], closes: dict[str, list[float]] | None = None
) -> Panel:
    n = len(next(iter(opens.values())))
    idx = pd.bdate_range("2024-01-01", periods=n, name="date")
    o = pd.DataFrame(opens, index=idx, dtype=float)
    c = pd.DataFrame(closes, index=idx, dtype=float) if closes else o.copy()
    return Panel(
        open=o,
        high=pd.concat([o, c]).groupby(level=0).max(),
        low=pd.concat([o, c]).groupby(level=0).min(),
        close=c,
        volume=pd.DataFrame(1e6, index=idx, columns=o.columns),
        universe=o.notna(),
    )
