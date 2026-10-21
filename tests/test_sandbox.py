import time

import pytest
from helpers import make_panel

from lucky.sandbox import StrategyError, run_strategy


def test_a_child_that_dies_silently_fails_fast(tmp_path):
    # A strategy (or a crash in the interpreter) can end the child without it
    # ever reporting back. The parent must notice, not wait out the timeout.
    path = tmp_path / "dies.py"
    path.write_text("import os\n\ndef weights(panel):\n    os._exit(3)\n")
    panel = make_panel({"A": [1.0, 2.0, 3.0]})
    start = time.monotonic()
    with pytest.raises(StrategyError, match="exited"):
        run_strategy(path, panel, timeout=60)
    assert time.monotonic() - start < 30


def test_a_normal_strategy_still_returns_weights(tmp_path):
    path = tmp_path / "ok.py"
    path.write_text("def weights(panel):\n    return panel.close * 0 + 1.0\n")
    w = run_strategy(path, make_panel({"A": [1.0, 2.0, 3.0]}), timeout=60)
    assert w.shape == (3, 1)
