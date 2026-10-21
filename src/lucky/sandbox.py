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
import queue as queue_mod
import tempfile
import time
import traceback
from pathlib import Path

import numpy as np
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
        # Rebuild as a plain float DataFrame so nothing defined by the strategy
        # (a subclass, a custom pickle hook) travels back to the judge.
        clean = pd.DataFrame(
            np.asarray(w, dtype=float),
            index=pd.DatetimeIndex(w.index),
            columns=[str(c) for c in w.columns],
        )
        queue.put(("ok", clean))
    except BaseException:  # noqa: BLE001 - report anything back to the parent
        queue.put(("error", traceback.format_exc(limit=5)))


def _wait(proc, queue, timeout: float):
    """The child's answer, or a StrategyError if it times out or dies without one."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return queue.get(timeout=1.0)
        except queue_mod.Empty:
            pass
        if not proc.is_alive():
            try:  # it may have answered just before exiting
                return queue.get(timeout=1.0)
            except queue_mod.Empty:
                raise StrategyError(
                    f"strategy process exited (code {proc.exitcode}) without returning weights"
                ) from None
        if time.monotonic() > deadline:
            proc.kill()
            raise StrategyError(f"strategy timed out after {timeout:.0f}s")


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
        status, payload = _wait(proc, queue, timeout)
    finally:
        proc.join(timeout=10)
        if proc.is_alive():
            proc.kill()
        if tmp is not None:
            os.unlink(tmp)
    if status != "ok":
        raise StrategyError(payload)
    return payload
