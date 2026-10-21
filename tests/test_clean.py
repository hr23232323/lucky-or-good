"""Bad-print cleaning and the liquid-candidate pre-filter, on the real archive's failures."""

import pandas as pd
import pytest

from lucky.data import MarketData, liquidity_universe
from lucky.synthetic import SyntheticConfig, generate


def write_days(root, rows):
    folder = root / "by_date" / "stock_daily"
    folder.mkdir(parents=True)
    df = pd.DataFrame(rows, columns=["date", "symbol", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for day, part in df.groupby("date"):
        part.to_parquet(folder / f"{day}.parquet")


def bars(symbol, closes, start="2024-01-01", opens=None, volume=1e6):
    days = pd.bdate_range(start, periods=len(closes))
    opens = opens or closes
    return [
        (d, symbol, o, max(o, c), min(o, c), c, volume)
        for d, o, c in zip(days, opens, closes, strict=True)
    ]


def test_spike_and_revert_print_is_dropped(tmp_path):
    # A $67,000 print in a $20 stock, the day after back to $20 (seen in the real archive).
    write_days(tmp_path, bars("SAF", [20, 20, 67000, 20, 21]) + bars("OK", [10, 10, 10, 10, 10]))
    md = MarketData(tmp_path)
    p = md.load(clean=True)
    assert p.close["SAF"].isna().sum() == 1 and p.close["SAF"].max() < 100
    assert md.dropped_bars == 1
    assert MarketData(tmp_path).load(clean=False).close["SAF"].max() == 67000


def test_crash_print_is_dropped(tmp_path):
    write_days(tmp_path, bars("SSE", [23.6, 23.2, 0.01, 23.3, 23.4]))
    assert MarketData(tmp_path).load().close["SSE"].min() > 20


def test_bad_open_with_good_close_is_dropped(tmp_path):
    write_days(tmp_path, bars("X", [20, 20, 20, 20], opens=[20, 20, 900, 20]))
    assert MarketData(tmp_path).load().open["X"].max() == 20


def test_real_moves_that_stick_are_kept(tmp_path):
    # A biotech tripling on news and staying there, and a collapse that stays down.
    write_days(tmp_path, bars("BIO", [5, 5, 20, 21, 22]) + bars("BUST", [40, 40, 4, 3.5, 3.2]))
    p = MarketData(tmp_path).load()
    assert p.close["BIO"].notna().all() and p.close["BUST"].notna().all()


def test_non_positive_prices_dropped(tmp_path):
    write_days(tmp_path, bars("Z", [5, 0, 5, 5]) + bars("OK", [9, 9, 9, 9]))
    assert MarketData(tmp_path).load().close["Z"].isna().sum() == 1


@pytest.mark.parametrize("seed", [3, 4])
def test_prefiltered_universe_matches_the_full_one(tmp_path, seed):
    cfg = SyntheticConfig(start="2022-01-03", end="2024-12-31", n_stocks=120, seed=seed)
    generate(tmp_path, cfg)
    md = MarketData(tmp_path)
    fast = md.load(top_n=25)
    full = md.load()
    exact = liquidity_universe(full.dollar_volume, 25) & full.close.notna()
    held = fast.universe.columns
    assert len(held) < len(full.symbols)  # the pre-filter actually dropped symbols
    assert exact.loc[:, exact.any()].columns.isin(held).all()
    pd.testing.assert_frame_equal(fast.universe, exact[held], check_names=False)


def test_thin_junk_run_is_dropped(tmp_path):
    # Like UAUA in 2006: days at $1 on a handful of shares between real $35 days.
    closes = [33] * 22 + [1.05, 1.1, 0.9, 34.9, 1.6, 35.2]
    vols = [5e6] * 22 + [15, 3, 24, 1.5e6, 17, 2e6]
    days = pd.bdate_range("2024-01-01", periods=len(closes))
    rows = [(d, "UA", c, c, c, c, v) for d, c, v in zip(days, closes, vols, strict=True)]
    write_days(tmp_path, rows + bars("OK", [9] * len(closes)))
    p = MarketData(tmp_path).load()
    assert p.close["UA"].min() > 30


def test_unadjusted_reverse_split_is_adjusted(tmp_path):
    # Like JDSU in 2006: $2.13 to $16.50 overnight (1-for-8) while volume drops ~8x.
    closes = [2.1 + 0.01 * (i % 3) for i in range(25)] + [16.6, 16.6, 15.75]
    opens = closes[:25] + [16.5, 16.52, 16.28]
    vols = [25e6] * 25 + [2.2e6, 3.7e6, 7.7e6]
    days = pd.bdate_range("2024-01-01", periods=len(closes))
    rows = [
        (d, "JD", o, max(o, c), min(o, c), c, v)
        for d, o, c, v in zip(days, opens, closes, vols, strict=True)
    ]
    write_days(tmp_path, rows)
    md = MarketData(tmp_path)
    p = md.load()
    assert md.split_events == 1
    r = p.open["JD"].pct_change().abs()
    assert r.max() < 0.1  # no fake +675% day
    dv = p.dollar_volume["JD"]
    assert dv.iloc[0] == pytest.approx(closes[0] * vols[0])  # dollar volume unchanged


def test_big_real_gap_without_volume_drop_is_not_a_split(tmp_path):
    closes = [10.0] * 25 + [20.0, 21.0]
    vols = [1e6] * 25 + [4e6, 3e6]  # doubled on news with heavy volume: real
    days = pd.bdate_range("2024-01-01", periods=len(closes))
    write_days(
        tmp_path, [(d, "NEWS", c, c, c, c, v) for d, c, v in zip(days, closes, vols, strict=True)]
    )
    md = MarketData(tmp_path)
    p = md.load()
    assert md.split_events == 0 and p.close["NEWS"].iloc[-1] == 21.0


def test_absurd_price_is_dropped(tmp_path):
    # Like DOMH: prices near $70 billion a share.
    write_days(tmp_path, bars("DM", [7e10, 7e10, 7e10]) + bars("OK", [9, 9, 9]))
    assert "DM" not in MarketData(tmp_path).load().symbols
