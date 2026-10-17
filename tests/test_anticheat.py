"""A catalogue of ways a strategy can cheat, run through the real judge.

Every row must stay caught. Found a new trick? Add a row, watch it pass the
judge, then fix the judge until it's caught. Record it in LEARNINGS.md.
"""

from pathlib import Path
from textwrap import dedent, indent

import pytest

from lucky.judge import Judge
from lucky.season import Season

PERIODS = Path(__file__).parent / "fixtures" / "periods_small.toml"

HEADER = """\
import numpy as np
import pandas as pd

META = {"name": "cheat", "hypothesis": "testing the judge", "expected_sign": "+"}

"""
TOP10 = """\
pick = score.where(panel.universe).rank(axis=1).le(10)
return pick.astype(float) / 10
"""
ROLLED = "pd.DataFrame(np.roll(panel.close.to_numpy(), -1, axis=0), index=panel.dates, columns=panel.symbols)"  # noqa: E501


def strategy(body: str, prelude: str = "") -> str:
    return HEADER + dedent(prelude) + "\ndef weights(panel):\n" + indent(dedent(body), "    ")


def top10(expr: str, prelude: str = "") -> str:
    """A strategy that holds the 10 lowest-scoring stocks, scored by ``expr``."""
    return strategy(f"score = {expr}\n{TOP10}", prelude)


# (id, source, expected status, rule or None)
# fmt: off
CATALOGUE = [
    # Reading the future, visibly: caught before anything runs.
    ("negative-shift", top10("panel.close.shift(-1) / panel.close"), "rejected", "future-shift"),
    ("back-fill", top10("panel.close.bfill()"), "rejected", "banned-method"),
    ("interpolate", top10("panel.close.interpolate()"), "rejected", "banned-method"),
    ("centered-window", top10("panel.close.rolling(21, center=True).mean()"), "rejected", "centered-window"),
    # Reaching outside the box.
    ("read-file", top10("pd.read_parquet('/data/x.parquet')"), "rejected", "banned-method"),
    ("getattr-read", top10("getattr(pd, 'read_' + 'parquet')('/data/x.parquet')"), "rejected", "banned-name"),
    ("numpy-load", top10("pd.DataFrame(np.load('/data/x.npy'))"), "rejected", "banned-method"),
    ("pandas-io", top10("pd.io.parquet.read_parquet('/data/x.parquet')"), "rejected", "banned-module-attr"),
    ("pandas-eval", top10("pd.eval('panel.close * 2')"), "rejected", "banned-method"),
    ("import-os", "import os\n" + top10("panel.close"), "rejected", "import"),
    ("class-smuggling", strategy("return W(panel.close * 0)\n", "class W(pd.DataFrame):\n    pass\n"), "rejected", "class"),
    ("module-getattr", top10("panel.close", "def __getattr__(name):\n    return 1\n"), "rejected", "dunder"),
    # Using memory of history instead of rules over features.
    ("hard-coded-date", top10("panel.close.loc[:'2015-01-01']"), "rejected", "date-literal"),
    ("calendar-year", top10("panel.close.where(panel.dates.year != 2008)"), "rejected", "calendar-year"),
    ("named-ticker", strategy("w = panel.close * 0.0\nw['S0001'] = 1.0\nreturn w\n"), "rejected", "ticker-literal"),
    ("ticker-list", strategy("w = panel.close * 0.0\nw[['S0001', 'S0002']] = 0.5\nreturn w\n"), "rejected", "ticker-literal"),
    # Reading the future, hidden from syntax: caught by the truncation check.
    ("hidden-negative-shift", top10("panel.close.shift(k) / panel.close", "k = -1\n"), "lookahead", None),
    ("reversed-window", top10("panel.close[::-1].rolling(5).mean()[::-1]"), "lookahead", None),
    ("future-max", top10("panel.close.iloc[::-1].cummax().iloc[::-1] / panel.close"), "lookahead", None),
    ("rank-over-time", top10("panel.close.rank(axis=0, pct=True)"), "lookahead", None),
    ("full-sample-zscore", top10("(panel.close - panel.close.mean()) / panel.close.std()"), "lookahead", None),
    ("np-roll", top10(ROLLED), "lookahead", None),
]
# fmt: on


@pytest.fixture(scope="module")
def judge(tmp_path_factory, edge_market):
    season = Season.create(
        tmp_path_factory.mktemp("anticheat") / "season",
        PERIODS,
        edge_market,
        top_n=30,
        benchmark="MKT",
        lookahead_samples=3,
    )
    return Judge(season)


@pytest.mark.parametrize("name, source, status, rule", CATALOGUE, ids=[c[0] for c in CATALOGUE])
def test_cheat_is_caught(judge, tmp_path, name, source, status, rule):
    path = tmp_path / f"{name}.py"
    path.write_text(source)
    rec = judge.evaluate(path)
    assert rec["status"] == status, rec
    if rule:
        assert any(f": {rule}:" in v for v in rec["violations"]), rec["violations"]


def test_leverage_is_capped(judge, tmp_path):
    path = tmp_path / "leverage.py"
    path.write_text(strategy("return panel.universe.astype(float) * 10.0\n"))
    rec = judge.evaluate(path)
    assert rec["status"] == "scored"
    assert rec["metrics"]["avg_gross_exposure"] <= 1.0 + 1e-9
    assert any("scaled down" in n for n in rec["notes"])


def test_weights_outside_universe_are_ignored(judge, tmp_path):
    path = tmp_path / "outside.py"
    path.write_text(strategy("return (~panel.universe).astype(float) / 10\n"))
    rec = judge.evaluate(path)
    assert rec["status"] == "scored"
    assert rec["metrics"]["avg_gross_exposure"] == 0
    assert any("outside the universe" in n for n in rec["notes"])


def test_honest_version_of_the_template_passes(judge, tmp_path):
    path = tmp_path / "honest.py"
    path.write_text(top10("panel.close / panel.close.shift(20)"))
    assert judge.evaluate(path)["status"] == "scored"
