from pathlib import Path

import pytest

from lucky.checks import static_check
from lucky.judge import Judge
from lucky.season import Season

ROOT = Path(__file__).parents[1]
BASELINES = sorted((ROOT / "strategies" / "baselines").glob("*.py"))


@pytest.fixture(scope="module")
def judge(tmp_path_factory, noise_market):
    season = Season.create(
        tmp_path_factory.mktemp("baselines") / "season",
        ROOT / "tests" / "fixtures" / "periods_small.toml",
        noise_market,
        top_n=30,
        benchmark="MKT",
        lookahead_samples=3,
    )
    return Judge(season)


def test_there_are_baselines():
    assert len(BASELINES) >= 5


@pytest.mark.parametrize("path", BASELINES, ids=lambda p: p.stem)
def test_baseline_passes_static_checks(path):
    assert static_check(path.read_text()) == []


@pytest.mark.parametrize("path", BASELINES, ids=lambda p: p.stem)
def test_baseline_is_scored_honestly(judge, path):
    rec = judge.evaluate(path)
    assert rec["status"] == "scored", rec.get("lookahead") or rec.get("error")
    assert rec["metrics"]["avg_gross_exposure"] > 0
