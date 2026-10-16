import shutil
from pathlib import Path

from lucky.cli import main

HERE = Path(__file__).parent


def test_full_loop_through_the_cli(tmp_path, edge_market, capsys):
    season = tmp_path / "season"
    periods = HERE / "fixtures" / "periods_small.toml"
    new = f"season new {season} --periods {periods} --data {edge_market} --top-n 30"
    assert main([*new.split(), "--benchmark", "MKT", "--model", "test", "--cutoff", "2026-06"]) == 0
    strat = tmp_path / "volume_shock.py"
    shutil.copyfile(HERE / "strategies" / "volume_shock.py", strat)
    s = ["--season", str(season)]

    assert main(["check", str(strat)]) == 0
    assert main([*s, "judge", str(strat)]) == 0
    out = capsys.readouterr().out
    assert "Sharpe" in out and "strategies tried" in out

    assert main([*s, "judge", str(strat), "--block", "validation"]) == 0
    assert "validation:" in capsys.readouterr().out

    assert main([*s, "vault", str(strat), "--block", "vault_b"]) == 2  # not frozen
    assert main([*s, "freeze", str(strat), "--note", "test"]) == 0
    assert main([*s, "vault", str(strat), "--block", "vault_b"]) == 0
    assert main([*s, "vault", str(strat), "--block", "vault_b"]) == 2  # second look refused

    capsys.readouterr()
    assert main([*s, "ledger"]) == 0
    listing = capsys.readouterr().out
    assert "discovery" in listing and "frozen" in listing
    assert main([*s, "verify"]) == 0


def test_check_reports_problems(tmp_path, capsys):
    bad = tmp_path / "bad.py"
    bad.write_text("import os\n")
    assert main(["check", str(bad)]) == 1
    assert "import" in capsys.readouterr().out
