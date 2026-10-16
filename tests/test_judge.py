import shutil
from pathlib import Path

import pandas as pd
import pytest

from lucky.judge import GateError, Judge
from lucky.season import Season

HERE = Path(__file__).parent
PERIODS = HERE / "fixtures" / "periods_small.toml"
STRATS = HERE / "strategies"


@pytest.fixture
def judge(tmp_path, edge_market):
    season = Season.create(
        tmp_path / "season",
        PERIODS,
        edge_market,
        top_n=30,
        benchmark="MKT",
        validation_budget=5,
        lookahead_samples=2,
    )
    return Judge(season)


def strat(tmp_path, name) -> Path:
    dst = tmp_path / f"{name}.py"
    shutil.copyfile(STRATS / f"{name}.py", dst)
    return dst


def test_discovery_scores_an_honest_strategy(judge, tmp_path):
    rec = judge.evaluate(strat(tmp_path, "volume_shock"))
    assert rec["status"] == "scored"
    assert rec["metrics"]["sharpe"] > 1.0
    assert rec["deflation"]["strategies_tried"] == 1
    assert "extra_lag_sharpe" in rec
    assert (judge.season.dir / "returns" / f"{rec['seq']:05d}.parquet").exists()
    assert judge.ledger.verify() == []


def test_static_cheat_rejected_and_logged(judge, tmp_path):
    rec = judge.evaluate(strat(tmp_path, "cheat_negative_shift"))
    assert rec["status"] == "rejected"
    assert any("future-shift" in v for v in rec["violations"])
    assert judge.ledger.entries()[-1]["status"] == "rejected"


def test_full_sample_cheat_caught_by_truncation(judge, tmp_path):
    rec = judge.evaluate(strat(tmp_path, "cheat_full_sample_zscore"))
    assert rec["status"] == "lookahead"
    assert not all(c["ok"] for c in rec["lookahead"])


def test_strategy_never_sees_past_block_end(judge, tmp_path):
    spy = tmp_path / "spy.py"
    spy.write_text(
        'META = {"name": "spy", "hypothesis": "-", "expected_sign": "+"}\n'
        "def weights(panel):\n"
        "    raise RuntimeError('LAST=' + str(panel.dates.max().date()))\n"
    )
    rec = judge.evaluate(spy)
    assert rec["status"] == "error"
    last = pd.Timestamp(rec["error"].rsplit("LAST=", 1)[1][:10])
    assert last <= judge.periods.block("discovery").end


def test_trial_count_counts_distinct_strategies(judge, tmp_path):
    judge.evaluate(strat(tmp_path, "volume_shock"))
    judge.evaluate(strat(tmp_path, "volume_shock"))  # same file again
    rec = judge.evaluate(strat(tmp_path, "momentum"))
    assert rec["deflation"]["strategies_tried"] == 2


def test_validation_needs_discovery_first(judge, tmp_path):
    with pytest.raises(GateError, match="discovery"):
        judge.evaluate(strat(tmp_path, "volume_shock"), "validation")


def test_validation_answers_coarsely_and_consistently(judge, tmp_path):
    path = strat(tmp_path, "volume_shock")
    judge.evaluate(path)
    rec = judge.evaluate(path, "validation")
    assert rec["status"] == "scored"
    assert "metrics" not in rec  # true numbers are sealed
    assert rec["answer"]["sharpe"] % 0.25 == pytest.approx(0)
    assert (judge.season.dir / "sealed" / f"{rec['seq']:05d}.json").exists()
    again = judge.evaluate(path, "validation")
    assert again["repeat"] and again["answer"] == rec["answer"]


def test_validation_budget_enforced(tmp_path, edge_market):
    season = Season.create(
        tmp_path / "s", PERIODS, edge_market, top_n=30, validation_budget=0, lookahead_samples=1
    )
    j = Judge(season)
    path = strat(tmp_path, "momentum")
    j.evaluate(path)
    with pytest.raises(GateError, match="budget"):
        j.evaluate(path, "validation")


def test_vault_needs_freeze_and_opens_once(judge, tmp_path):
    path = strat(tmp_path, "volume_shock")
    with pytest.raises(GateError):
        judge.evaluate(path, "vault_b")
    judge.evaluate(path)
    with pytest.raises(GateError, match="frozen"):
        judge.open_sealed(path, "vault_b")
    judge.freeze(path, note="looks real")
    report = judge.open_sealed(path, "vault_b")
    assert report["status"] == "scored" and report["metrics"]["sharpe"] > 1.0
    with pytest.raises(GateError, match="already opened"):
        judge.open_sealed(path, "vault_b")
    assert judge.ledger.verify() == []


def test_editing_after_freeze_voids_it(judge, tmp_path):
    path = strat(tmp_path, "volume_shock")
    judge.evaluate(path)
    judge.freeze(path)
    path.write_text(path.read_text().replace("k = 5", "k = 6"))
    with pytest.raises(GateError, match="frozen"):
        judge.open_sealed(path, "vault_a")
