import pandas as pd
import pytest

from lucky.data import MarketData, liquidity_universe


def test_reads_both_column_schemas(noise_market):
    panel = MarketData(noise_market).load()
    # Files before 2026-03-27 use `timestamp`, later ones use `date`.
    assert panel.dates.min() < pd.Timestamp("2026-03-27") < panel.dates.max()
    assert not panel.close.loc["2026-03-26"].isna().all()
    assert not panel.close.loc["2026-03-27"].isna().all()


def test_file_filter_uses_filename_dates(noise_market):
    md = MarketData(noise_market)
    files = md.files("2022-01-01", "2022-01-31")
    assert files and all(f.stem.startswith("2022-01") for f in files)


def test_delisted_symbols_present_until_they_stop(noise_market, noise_truth):
    panel = MarketData(noise_market).load()
    assert noise_truth["delisted"], "fixture should include delistings"
    for sym, info in noise_truth["delisted"].items():
        last = pd.Timestamp(info["last_date"])
        col = panel.close[sym]
        assert col.last_valid_index() == last
        assert col.loc[last:].iloc[1:].isna().all()


def test_universe_is_point_in_time(noise_market):
    panel = MarketData(noise_market).load()
    dv = panel.dollar_volume
    full = liquidity_universe(dv, top_n=10)
    t = panel.dates[400]
    # Wreck everything from t onwards; membership up to and including t must not move.
    tampered = dv.copy()
    tampered.loc[t:] = tampered.loc[t:].sample(frac=1.0, axis=1, random_state=0).to_numpy()
    assert full.loc[:t].equals(liquidity_universe(tampered, top_n=10).loc[:t])


def test_universe_size_capped(noise_market):
    panel = MarketData(noise_market).load(top_n=10)
    assert panel.universe.sum(axis=1).max() <= 10
    assert panel.universe.sum(axis=1).iloc[-1] == 10


def test_until_drops_future_rows(noise_market):
    panel = MarketData(noise_market).load()
    t = panel.dates[100]
    cut = panel.until(t)
    assert cut.dates.max() == t
    assert cut.universe.index.equals(cut.close.index)


def test_missing_dir_is_clear(tmp_path):
    with pytest.raises(FileNotFoundError):
        MarketData(tmp_path)
