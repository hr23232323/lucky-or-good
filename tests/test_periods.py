from pathlib import Path

import pandas as pd
import pytest

from lucky.periods import load, parse

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("name", ["marketparquet", "synthetic"])
def test_shipped_configs_parse(name):
    p = load(ROOT / "config" / "periods" / f"{name}.toml")
    kinds = {b.kind for b in p.blocks}
    assert {"discovery", "validation", "vault", "forward"} <= kinds


def test_overlap_rejected():
    text = """
[[block]]
name = "a"
kind = "discovery"
start = "2020-01-01"
end = "2021-01-01"
[[block]]
name = "b"
kind = "vault"
start = "2020-06-01"
end = "2022-01-01"
"""
    with pytest.raises(ValueError, match="overlap"):
        parse(text)


def test_load_window_has_warmup_and_stops_at_block_end():
    p = load(ROOT / "tests" / "fixtures" / "periods_small.toml")
    b = p.block("discovery")
    start, end = p.load_window(b)
    assert end == b.end
    assert start == b.start - pd.offsets.BDay(120)
