import numpy as np
import pandas as pd
import pytest

from lucky.metrics import (
    deflated_sharpe,
    expected_max_sharpe,
    max_drawdown,
    psr,
    sharpe,
)


def test_sharpe_of_constant_is_zero():
    assert sharpe(pd.Series([0.01] * 10)) == 0.0


def test_max_drawdown():
    r = pd.Series([0.1, -0.5, 0.2])
    assert max_drawdown(r) == pytest.approx(-0.5)


def test_psr_at_benchmark_is_half():
    assert psr(0.05, 0.05, 1000, 0.0, 3.0) == pytest.approx(0.5)


def test_more_trials_raise_the_bar():
    bars = [expected_max_sharpe(n, 0.001) for n in (2, 10, 100, 1000)]
    assert bars == sorted(bars) and bars[0] > 0


def test_best_of_many_noise_strategies_is_not_significant():
    rng = np.random.default_rng(0)
    trials = pd.DataFrame(rng.normal(0, 0.01, (1260, 200)))  # 200 noise strategies, 5 years
    per_period = trials.mean() / trials.std()
    best = trials[per_period.idxmax()]
    assert sharpe(best) > 0.8  # looks good on its own...
    dsr = deflated_sharpe(best, n_trials=200, trial_sharpe_var=float(per_period.var()))
    assert dsr < 0.9  # ...but not once you count the tries


def test_real_edge_stays_significant():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.0015, 0.01, 2520))  # ~2.4 annual Sharpe, 10 years
    assert deflated_sharpe(r, n_trials=20, trial_sharpe_var=0.0005) > 0.95
