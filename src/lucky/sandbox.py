"""Run a strategy file in a fresh child process with a timeout.

The child is spawned (not forked: forking a process that runs DuckDB threads
can deadlock), reads the panel from a pickle file, optionally truncates it, and
calls ``weights``. This contains honest mistakes (infinite loops, accidental
file or network access). It is not a security boundary; see the threat model
in docs/design.md.
"""

from __future__ import annotations

import importlib.util
import multiprocessing as mp
import os
import pickle
import tempfile
import traceback
from pathlib import Path

import pandas as pd

from .data import Panel


class StrategyError(RuntimeError):
    pass


def save_panel(panel: Panel, path: Path | str) -> Path:
    path = Path(path)
    with path.open("wb") as f:
        pickle.dump(panel, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def _deny_network() -> None:
    import socket

    def refuse(*_a, **_k):
        raise PermissionError("strategies may not use the network")

    socket.socket = refuse  # type: ignore[assignment]
    socket.create_connection = refuse  # type: ignore[assignment]


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("strategy_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _child(path: str, panel_file: str, until, queue) -> None:
    try:
        with open(panel_file, "rb") as f:
            panel: Panel = pickle.load(f)
        if until is not None:
            panel = panel.until(until)
        os.environ.pop("LUCKY_DATA_DIR", None)
        os.chdir(tempfile.mkdtemp(prefix="lucky-strategy-"))
        _deny_network()
        module = load_module(Path(path))
        w = module.weights(panel)
        if not isinstance(w, pd.DataFrame):
            raise TypeError(f"weights() must return a DataFrame, got {type(w).__name__}")
        queue.put(("ok", w))
    except BaseException:  # noqa: BLE001 - report anything back to the parent
        queue.put(("error", traceback.format_exc(limit=5)))


def run_strategy(
    path: Path | str, panel: Panel | Path | str, until=None, timeout: float = 300.0
) -> pd.DataFrame:
    """Call ``weights(panel)`` from ``path`` in a child process.

    ``panel`` is a Panel or a file written by ``save_panel``. ``until`` cuts the
    panel at a date before the strategy sees it (for the truncation check).
    """
    tmp = None
    if isinstance(panel, Panel):
        fd, tmp = tempfile.mkstemp(suffix=".pkl")
        os.close(fd)
        panel_file = save_panel(panel, tmp)
    else:
        panel_file = Path(panel)
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(
        target=_child, args=(str(Path(path).resolve()), str(panel_file), until, queue), daemon=True
    )
    proc.start()
    try:
        status, payload = queue.get(timeout=timeout)
    except Exception as e:
        proc.kill()
        raise StrategyError(f"strategy timed out after {timeout:.0f}s") from e
    finally:
        proc.join(timeout=10)
        if proc.is_alive():
            proc.kill()
        if tmp is not None:
            os.unlink(tmp)
    if status != "ok":
        raise StrategyError(payload)
    return payload
