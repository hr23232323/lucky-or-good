import shutil
from pathlib import Path

import pytest

from lucky.judge import Judge
from lucky.report import build, gather, write
from lucky.season import Season

HERE = Path(__file__).parent
PERIODS = HERE / "fixtures" / "periods_small.toml"


@pytest.fixture(scope="module")
def season(tmp_path_factory, edge_market):
    root = tmp_path_factory.mktemp("report")
    s = Season.create(
        root / "season", PERIODS, edge_market, top_n=30, benchmark="MKT", lookahead_samples=1
    )
    j = Judge(s)
    files = {}
    for name in ("volume_shock", "momentum", "cheat_negative_shift"):
        files[name] = root / f"{name}.py"
        shutil.copyfile(HERE / "strategies" / f"{name}.py", files[name])
        j.evaluate(files[name])
    j.evaluate(files["volume_shock"], "validation")
    j.freeze(files["volume_shock"])
    j.open_sealed(files["volume_shock"], "vault_b")
    return s


def test_report_renders_everything(season):
    page = build(season)
    assert page.startswith("<!doctype html>")
    for text in ("volume shock long-short", "6-month momentum", "noise bar", "ledger intact"):
        assert text in page
    assert "future-shift" in page  # the rejected strategy and why
    assert 'id="equity-data"' in page


def test_sealed_results_hidden_by_default(season):
    data = gather(season, include_sealed=False)
    assert data["vaults"] and all("metrics" not in r for r in data["vaults"].values())
    assert all("true_sharpe" not in a for a in data["validation"].values())
    page = build(season)
    assert "sealed results hidden" in page and "includes sealed results" not in page


def test_sealed_results_shown_on_request(season):
    data = gather(season, include_sealed=True)
    assert all(r.get("metrics") for r in data["vaults"].values())
    assert any("true_sharpe" in a for a in data["validation"].values())
    path = write(season, include_sealed=True)
    assert path.name == "report-sealed.html"
    assert "includes sealed results" in path.read_text()


def test_report_needs_no_market_data(season, tmp_path):
    """Reports are built from the season folder alone, so they can be shared."""
    moved = tmp_path / "copy"
    shutil.copytree(season.dir, moved)
    copy = Season.load(moved)
    copy.data_root = str(tmp_path / "nowhere")
    assert "volume shock" in build(copy)


def test_comparison_views(season):
    public = build(season)
    assert 'class="comparison"' in public and "volume shock long-short" in public
    assert (
        'class="pt pt-vault_b"' not in public
    )  # the discovery-vs-sealed chart needs sealed results
    sealed = build(season, include_sealed=True)
    assert 'class="pt pt-vault_b"' in sealed
    assert "benchmark (MKT)" in sealed  # reference line from the synthetic market's ETF
