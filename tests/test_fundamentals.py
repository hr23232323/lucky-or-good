from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from helpers import make_panel

from lucky.fundamentals import (
    SHILLER_LAG_MONTHS,
    as_of,
    attach,
    market_valuation,
    parse_shiller_sheet,
    stock_earnings_yield,
)


def monthly(n=200, start="2000-01"):
    idx = pd.period_range(start, periods=n, freq="M").to_timestamp()
    return pd.DataFrame(
        {
            "price": np.linspace(1000, 2000, n),
            "earnings": np.full(n, 50.0),
            "cpi": np.full(n, 200.0),
        },
        index=idx,
    )


def test_parse_reads_shiller_dates_including_october():
    raw = pd.DataFrame(
        [
            ["Date", "P", "D", "E", "CPI"],
            [2025.09, 10.0, 1, 2.0, 300],
            [2025.1, 11.0, 1, 2.1, 301],
            [2025.11, 12.0, 1, np.nan, 302],
        ]
    )
    m = parse_shiller_sheet(raw)
    assert list(m.index) == [
        pd.Timestamp("2025-09-01"),
        pd.Timestamp("2025-10-01"),
        pd.Timestamp("2025-11-01"),
    ]
    assert m.loc["2025-10-01", "earnings"] == 2.1


def test_a_month_is_only_visible_after_it_ends():
    v = market_valuation(monthly())
    days = pd.bdate_range("2015-01-26", "2015-02-06")
    daily = as_of(v, days)
    jan_last, feb_first = pd.Timestamp("2015-01-30"), pd.Timestamp("2015-02-02")
    # January's value can't be known on January's last trading day.
    assert daily.loc[jan_last, "pe"] == pytest.approx(v.loc[pd.Timestamp("2015-01-01"), "pe"])
    assert daily.loc[feb_first, "pe"] == pytest.approx(v.loc[pd.Timestamp("2015-02-01"), "pe"])


def test_earnings_are_lagged_so_only_reported_numbers_are_used():
    base = monthly()
    shocked = base.copy()
    shocked.loc["2010-06-01", "earnings"] = 500.0  # a huge June figure
    a, b = market_valuation(base), market_valuation(shocked)
    changed = a.index[(a["pe"] - b["pe"]).abs() > 1e-9]
    # June's earnings first affect the P/E published after month June + lag ends.
    first = changed.min()
    assert first == pd.Timestamp("2010-06-01") + pd.DateOffset(months=SHILLER_LAG_MONTHS + 1)


def test_cape_uses_ten_years_of_lagged_real_earnings():
    v = market_valuation(monthly(n=300))
    assert v["cape"].iloc[:125].isna().all()
    row = v.dropna().iloc[0]
    assert row["cape"] == pytest.approx(row["pe"])  # flat earnings and prices in real terms


def test_panel_until_keeps_valuation_fields_point_in_time():
    p = make_panel({"A": [1.0, 2.0, 3.0, 4.0]})
    p = replace(
        p,
        market=pd.DataFrame({"pe": [10.0, 11, 12, 13]}, index=p.dates),
        earnings_yield=pd.DataFrame({"A": [0.1, 0.1, 0.2, 0.2]}, index=p.dates),
    )
    cut = p.until(p.dates[1])
    assert len(cut.market) == 2 and len(cut.earnings_yield) == 2
    plain = make_panel({"A": [1.0, 2.0]})
    assert plain.until(plain.dates[0]).market is None


def test_stock_earnings_count_only_from_the_day_they_are_available():
    p = make_panel({"A": [10.0] * 6, "B": [20.0] * 6})
    d = p.dates
    table = pd.DataFrame(
        {"symbol": ["A", "A", "B"], "available": [d[1], d[4], d[2]], "eps_ttm": [1.0, 2.0, -1.0]}
    )
    ey = stock_earnings_yield(table, p)
    assert ey["A"].isna().iloc[0]
    assert list(ey["A"].iloc[1:]) == [0.1, 0.1, 0.1, 0.2, 0.2]
    assert ey["B"].iloc[2] == -0.05  # losses stay as negative yield, no P/E games


def test_stale_earnings_become_unknown():
    p = make_panel({"A": [10.0] * 600})
    table = pd.DataFrame({"symbol": ["A"], "available": [p.dates[0]], "eps_ttm": [1.0]})
    ey = stock_earnings_yield(table, p)
    assert ey["A"].iloc[100] == 0.1 and ey["A"].isna().iloc[-1]


def test_attach_gives_history_but_nothing_after_the_panel_ends(tmp_path):
    v = market_valuation(monthly(n=300))
    v.to_parquet(tmp_path / "market_valuation.parquet")
    p = make_panel({"A": [1.0] * 30})  # January-February 2024
    out = attach(p, tmp_path)
    assert out.market.index.max() <= p.dates[-1]
    assert out.market.index.min() < p.dates[0] - pd.DateOffset(years=10)
    assert out.earnings_yield is None
