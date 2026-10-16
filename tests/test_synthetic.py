import numpy as np

from lucky.data import MarketData
from lucky.synthetic import SyntheticConfig, generate


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


def test_no_free_alpha_from_rebalancing(tmp_path):
    """Equal weight should track the market. A zero *log*-mean noise term once
    handed every stock a free ~5%/yr that rebalancing harvested."""
    cfg = SyntheticConfig(
        start="2023-01-02",
        end="2024-12-31",
        n_stocks=400,
        seed=7,
        delist_fraction=0,
        ipo_fraction=0,
    )
    generate(tmp_path, cfg)
    stocks = MarketData(tmp_path).load()
    mkt = MarketData(tmp_path, asset="etf").load().close["MKT"]
    ew = stocks.close.pct_change(fill_method=None).mean(axis=1)
    excess = (ew - mkt.pct_change()).dropna()
    assert abs(excess.mean() * 252) < 0.025


def test_market_benchmark_lines_up_with_stocks(noise_market):
    stocks = MarketData(noise_market).load()
    mkt = MarketData(noise_market, asset="etf").load().open["MKT"]
    ew = (stocks.open.shift(-1) / stocks.open - 1).mean(axis=1)
    assert ew.corr(mkt.shift(-1) / mkt - 1) > 0.8


def test_truth_file_records_delistings(noise_truth):
    kinds = {v["kind"] for v in noise_truth["delisted"].values()}
    assert kinds <= {"failure", "merger"}
    assert noise_truth["config"]["edge"] == 0.0


def test_etf_benchmark_exists(noise_market):
    etf = MarketData(noise_market, asset="etf").load()
    assert list(etf.symbols) == ["MKT"]
