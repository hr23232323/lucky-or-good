import numpy as np

from lucky.data import MarketData


def _volume_shock_ic(root) -> float:
    """Mean cross-sectional correlation between today's volume shock and the
    next session's open-to-close return."""
    p = MarketData(root).load()
    logv = np.log(p.volume)
    shock = logv - logv.rolling(250, min_periods=50).mean().shift(1)
    nxt = (p.close / p.open - 1).shift(-1)
    ic = shock.rank(axis=1).corrwith(nxt.rank(axis=1), axis=1)
    return float(ic.mean())


def test_noise_market_has_no_edge(noise_market):
    assert abs(_volume_shock_ic(noise_market)) < 0.02


def test_edge_market_has_planted_edge(edge_market):
    assert _volume_shock_ic(edge_market) > 0.05


def test_truth_file_records_delistings(noise_truth):
    kinds = {v["kind"] for v in noise_truth["delisted"].values()}
    assert kinds <= {"failure", "merger"}
    assert noise_truth["config"]["edge"] == 0.0


def test_etf_benchmark_exists(noise_market):
    etf = MarketData(noise_market, asset="etf").load()
    assert list(etf.symbols) == ["MKT"]
