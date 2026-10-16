import numpy as np
import pandas as pd
import pytest
from helpers import make_panel

from lucky.data import MarketData
from lucky.engine import ZERO_COSTS, CostModel, backtest
from lucky.metrics import sharpe

FLAT_10BPS = CostModel(tiers=(), floor_bps=10.0, borrow_bps_per_year=0.0)


def test_weights_trade_next_open_and_earn_open_to_open():
    p = make_panel({"A": [10, 11, 12, 12, 13], "B": [20, 20, 22, 21, 20]})
    w = pd.DataFrame({"A": [1.0]}, index=p.dates[:1])  # decided day 0, then no more trades
    res = backtest(p, w, costs=ZERO_COSTS)
    expected = [12 / 11 - 1, 12 / 12 - 1, 13 / 12 - 1]  # held from open day 1
    assert res.returns.tolist() == pytest.approx(expected)
    assert res.returns.index[0] == p.dates[1]


def test_turnover_and_costs_on_a_switch():
    p = make_panel({"A": [10, 10, 10, 10], "B": [20, 20, 20, 20]})
    w = pd.DataFrame({"A": [1.0, 0.0], "B": [0.0, 1.0]}, index=p.dates[:2])
    res = backtest(p, w, costs=FLAT_10BPS)
    # Day 1's cost comes out of cash, so the position is very slightly over 100%
    # by day 2. Hence the loose tolerance.
    assert res.turnover.tolist() == pytest.approx([1.0, 2.0], rel=1e-2)
    assert res.costs.tolist() == pytest.approx([0.001, 0.002], rel=1e-2)
    assert res.returns.tolist() == pytest.approx([-0.001, -0.002], rel=1e-2)


def test_positions_drift_between_trades():
    p = make_panel({"A": [10, 10, 20, 20], "B": [10, 10, 10, 10]})
    w = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=p.dates[:1])
    res = backtest(p, w, costs=ZERO_COSTS)
    # Day 1: A doubles open-to-open, portfolio +50%. No rebalancing afterwards.
    assert res.returns.iloc[0] == pytest.approx(0.5)
    assert res.turnover.iloc[1] == 0.0


def test_same_bar_strategy_earns_nothing_in_noise(noise_market):
    p = MarketData(noise_market).load()
    move = p.close / p.open - 1
    # "Buy what went up today": with real same-bar execution this would print money.
    w = np.sign(move).div(move.notna().sum(axis=1), axis=0)
    res = backtest(p, w, costs=ZERO_COSTS)
    assert abs(sharpe(res.returns)) < 1.5


def test_failed_company_costs_terminal_loss(noise_market, noise_truth):
    p = MarketData(noise_market).load()
    sym, info = next((s, v) for s, v in noise_truth["delisted"].items() if v["kind"] == "failure")
    last = pd.Timestamp(info["last_date"])
    entry = p.dates[p.dates.get_loc(last) - 20]
    w = pd.DataFrame({sym: [1.0]}, index=[entry])
    res = backtest(p, w, costs=ZERO_COSTS)
    final_bar = p.close.loc[last, sym] / p.open.loc[last, sym] - 1
    assert res.returns.loc[last] == pytest.approx((1 + final_bar) * 0.7 - 1)
    after = res.gross_exposure.loc[last:].iloc[1:]
    assert (after == 0).all()


def test_weights_outside_universe_are_zeroed():
    p = make_panel({"A": [10, 10, 10, 10], "B": [10, 10, 10, 10]})
    p.universe.loc[:, "B"] = False
    w = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=p.dates[:1])
    res = backtest(p, w, costs=ZERO_COSTS)
    assert res.gross_exposure.iloc[0] == pytest.approx(0.5)
    assert any("outside the universe" in n for n in res.notes)


def test_gross_exposure_is_capped():
    p = make_panel({"A": [10, 10, 10, 10], "B": [10, 10, 10, 10]})
    w = pd.DataFrame({"A": [2.0], "B": [-2.0]}, index=p.dates[:1])
    res = backtest(p, w, costs=ZERO_COSTS, max_gross=1.0)
    assert res.gross_exposure.iloc[0] == pytest.approx(1.0)


def _volume_shock_weights(p, k=5):
    logv = np.log(p.volume)
    shock = (logv - logv.rolling(250, min_periods=50).mean().shift(1)).where(p.universe)
    rank = shock.rank(axis=1)
    n = shock.notna().sum(axis=1)
    long = rank.gt(n - k, axis=0)
    short = rank.le(k)
    return (long.astype(float) - short.astype(float)) / (2 * k)


def test_planted_edge_survives_costs(edge_market):
    p = MarketData(edge_market).load(top_n=30)
    res = backtest(p, _volume_shock_weights(p))
    assert sharpe(res.returns) > 1.0


def test_no_edge_no_profit_after_costs(noise_market):
    p = MarketData(noise_market).load(top_n=30)
    res = backtest(p, _volume_shock_weights(p))
    assert sharpe(res.returns) < 0.5


def test_unknown_symbols_rejected():
    p = make_panel({"A": [10, 10, 10]})
    with pytest.raises(ValueError):
        backtest(p, pd.DataFrame({"ZZZ": [1.0]}, index=p.dates[:1]))
