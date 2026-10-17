"""The judge: checks, runs, scores and logs a strategy file.

Discovery answers in full. Validation answers coarsely and on a budget.
Vault and forward blocks need a frozen strategy and give one look each.
Every call ends in exactly one ledger entry, whatever happens.
"""

from __future__ import annotations

import ast
import json
import math
import shutil
import tempfile
import weakref
from pathlib import Path

import numpy as np
import pandas as pd

from .checks import compare_prefix, static_check
from .data import MarketData, Panel
from .engine import backtest, open_to_open
from .ledger import content_hash
from .metrics import DAYS, deflated_sharpe, expected_max_sharpe, sharpe, summary
from .periods import SEALED, Block
from .sandbox import StrategyError, run_strategy, save_panel
from .season import Season

THRESHOLD = 0.5  # validation answers only move when it disagrees with discovery by this much
NOISE = 0.25  # Laplace scale (annual Sharpe units) for validation answers
STEP = 0.25  # validation answers are rounded to this


class GateError(RuntimeError):
    """The gate refused: wrong order, budget spent, or a second look."""


def _round(x: float, step: float = STEP) -> float:
    return round(round(x / step) * step, 2)


def read_meta(source: str) -> dict:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "META" for t in node.targets
        ):
            return ast.literal_eval(node.value)
    return {}


class Judge:
    def __init__(self, season: Season, data_root: Path | str | None = None):
        self.season = season
        self.root = Path(data_root or season.data_root)
        self.periods = season.periods
        self.ledger = season.ledger
        self._panels: dict[str, Panel] = {}
        self._panel_files: dict[str, Path] = {}
        self._tmp = tempfile.TemporaryDirectory(prefix="lucky-panels-")
        weakref.finalize(self, self._tmp.cleanup)
        self._rng = np.random.default_rng()

    # ---------- data ----------
    def panel(self, block: Block) -> Panel:
        if block.name not in self._panels:
            start, end = self.periods.load_window(block)
            self._panels[block.name] = MarketData(self.root).load(
                start, end, top_n=self.season.top_n
            )
        return self._panels[block.name]

    def panel_file(self, block: Block) -> Path:
        if block.name not in self._panel_files:
            path = Path(self._tmp.name) / f"{block.name}.pkl"
            self._panel_files[block.name] = save_panel(self.panel(block), path)
        return self._panel_files[block.name]

    def benchmark(self, block: Block) -> pd.Series | None:
        start, end = self.periods.load_window(block)
        try:
            etf = MarketData(self.root, asset="etf").load(
                start, end, symbols=[self.season.benchmark]
            )
        except (FileNotFoundError, ValueError):
            return None
        if self.season.benchmark not in etf.symbols:
            return None
        return open_to_open(etf, self.season.benchmark)

    # ---------- ledger views ----------
    def _trials(self, **match) -> list[dict]:
        return [
            e
            for e in self.ledger.entries()
            if e.get("kind") == "trial" and all(e.get(k) == v for k, v in match.items())
        ]

    def discovery_stats(self, extra: tuple[str, float] | None = None) -> tuple[int, float]:
        """Distinct strategies scored in discovery, and the variance of their per-day Sharpes.

        ``extra`` adds a (hash, annual Sharpe) pair not yet in the ledger.
        """
        latest: dict[str, float] = {}
        for e in self._trials(block_kind="discovery", status="scored"):
            latest[e["hash"]] = e["metrics"]["sharpe"] / math.sqrt(DAYS)
        if extra:
            latest[extra[0]] = extra[1] / math.sqrt(DAYS)
        vals = list(latest.values())
        return len(vals), float(np.var(vals, ddof=1)) if len(vals) > 1 else 0.0

    def _discovery_sharpe(self, h: str) -> float | None:
        hits = self._trials(hash=h, block_kind="discovery", status="scored")
        return hits[-1]["metrics"]["sharpe"] if hits else None

    # ---------- the pipeline ----------
    def _run(self, path: Path, block: Block) -> dict:
        """Checks, runs and scores. Returns a dict with status and (if scored) results."""
        source = path.read_text()
        h = content_hash(source)
        base = {
            "file": str(path),
            "hash": h,
            "block": block.name,
            "block_kind": block.kind,
            "span": f"{block.start.date()} to {block.end.date()}",
            "universe": f"top {self.season.top_n} by liquidity",
        }
        violations = static_check(source)
        if violations:
            return {**base, "status": "rejected", "violations": [str(v) for v in violations]}
        base["meta"] = read_meta(source)
        panel = self.panel(block)
        pfile = self.panel_file(block)
        try:
            w = run_strategy(path, pfile)
            problem = _weights_problem(w, panel)
            if problem:
                return {**base, "status": "error", "error": problem}
            dates = panel.dates[(panel.dates >= block.start) & (panel.dates <= block.end)]
            pool = dates[5:-1]
            k = min(self.season.lookahead_samples, len(pool))
            picks = sorted(self._rng.choice(pool, size=k, replace=False)) if k else []
            lookahead = [compare_prefix(w, run_strategy(path, pfile, until=t), t) for t in picks]
        except StrategyError as e:
            return {**base, "status": "error", "error": str(e)[-2000:]}
        if not all(c["ok"] for c in lookahead):
            return {**base, "status": "lookahead", "lookahead": lookahead}

        res = backtest(panel, w).between(block.start, block.end)
        lagged = backtest(panel, w.shift(1)).between(block.start, block.end)
        metrics = summary(res, self.benchmark(block))
        expected = str(base["meta"].get("expected_sign", "")).strip()
        sign = {}
        if expected in {"+", "-"}:
            sign = {"sign_matches": (metrics["sharpe"] > 0) == (expected == "+")}
        return {
            **base,
            "status": "scored",
            "metrics": metrics,
            **sign,
            "lookahead": lookahead,
            "extra_lag_sharpe": round(sharpe(lagged.returns), 3),
            "notes": res.notes,
            "_returns": res.returns,
        }

    def _log(self, outcome: dict, sealed: bool, extra: dict | None = None) -> dict:
        returns = outcome.pop("_returns", None)
        public = dict(outcome)
        if sealed and outcome.get("status") == "scored":
            # True numbers go to sealed/; the ledger only keeps what the proposer was told.
            for k in ("metrics", "extra_lag_sharpe", "notes"):
                public.pop(k, None)
        record = self.ledger.append({"kind": "trial", **public, **(extra or {})})
        if returns is not None:
            folder = self.season.dir / ("sealed" if sealed else "returns")
            folder.mkdir(exist_ok=True)
            returns.rename("return").to_frame().to_parquet(folder / f"{record['seq']:05d}.parquet")
            if sealed:
                (folder / f"{record['seq']:05d}.json").write_text(
                    json.dumps(outcome, indent=2, default=str)
                )
        return record

    # ---------- public API ----------
    def evaluate(self, path: Path | str, block_name: str = "discovery") -> dict:
        path = Path(path)
        block = self.periods.block(block_name)
        if block.kind in SEALED:
            raise GateError(f"{block.name} is sealed; freeze the strategy and use open_sealed()")
        if block.kind == "validation":
            return self._validate(path, block)
        outcome = self._run(path, block)
        if outcome["status"] == "scored":
            n, var = self.discovery_stats(extra=(outcome["hash"], outcome["metrics"]["sharpe"]))
            dsr = deflated_sharpe(outcome["_returns"], n, var)
            outcome["deflation"] = {
                "strategies_tried": n,
                "best_noise_sharpe_expected": round(
                    expected_max_sharpe(n, var) * math.sqrt(DAYS), 3
                ),
                "deflated_sharpe": round(dsr, 3),
            }
        return self._log(outcome, sealed=False)

    def _validate(self, path: Path, block: Block) -> dict:
        source = path.read_text()
        h = content_hash(source)
        disc = self._discovery_sharpe(h)
        if disc is None:
            raise GateError("score this exact file in discovery before asking validation")
        asked = [e for e in self._trials(hash=h, block_kind="validation") if "answer" in e]
        if asked:
            # Same file, same answer: re-asking must not average away the noise.
            return {**asked[-1], "repeat": True}
        spent = sum(1 for e in self._trials(block_kind="validation") if e.get("spent"))
        left = self.season.validation_budget - spent
        if left <= 0:
            raise GateError("validation budget for this season is spent")
        outcome = self._run(path, block)
        if outcome["status"] != "scored":
            return self._log(outcome, sealed=False)
        true = outcome["metrics"]["sharpe"]
        noise = float(self._rng.laplace(0, NOISE))
        if abs(true - disc) < THRESHOLD + noise:
            answer = {"verdict": "consistent with discovery", "sharpe": _round(disc)}
            used = False
        else:
            answer = {
                "verdict": "differs from discovery",
                "sharpe": _round(true + float(self._rng.laplace(0, NOISE))),
            }
            used = True
        return self._log(
            outcome,
            sealed=True,
            extra={"answer": answer, "spent": used, "budget_left": left - int(used)},
        )

    def freeze(self, path: Path | str, note: str = "") -> dict:
        path = Path(path)
        source = path.read_text()
        h = content_hash(source)
        if static_check(source):
            raise GateError("fix static check violations before freezing")
        if self._discovery_sharpe(h) is None:
            raise GateError("score this exact file in discovery before freezing")
        frozen = self.season.dir / "frozen"
        frozen.mkdir(exist_ok=True)
        shutil.copyfile(path, frozen / f"{h}.py")
        return self.ledger.append({"kind": "freeze", "file": str(path), "hash": h, "note": note})

    def open_sealed(self, path: Path | str, block_name: str) -> dict:
        """One look at a vault or forward block for a frozen strategy."""
        path = Path(path)
        block = self.periods.block(block_name)
        if block.kind not in SEALED:
            raise GateError(f"{block.name} is not sealed; use evaluate()")
        h = content_hash(path.read_text())
        if not any(e.get("kind") == "freeze" and e.get("hash") == h for e in self.ledger.entries()):
            raise GateError("this exact file isn't frozen (edited since freezing?)")
        if self._trials(hash=h, block=block.name):
            raise GateError(f"{block.name} was already opened for this strategy")
        frozen = self.season.dir / "frozen" / f"{h}.py"
        outcome = self._run(frozen, block)
        outcome["file"] = str(path)
        if outcome["status"] == "scored":
            opens = len(self._trials(block=block.name, status="scored")) + 1
            outcome["deflation"] = {
                "vault_opens": opens,
                "deflated_sharpe": round(
                    deflated_sharpe(outcome["_returns"], opens, self.discovery_stats()[1]), 3
                ),
            }
        report = {k: v for k, v in outcome.items() if k != "_returns"}
        record = self._log(outcome, sealed=True)
        return {**report, "seq": record["seq"]}


def _weights_problem(w: pd.DataFrame, panel: Panel) -> str | None:
    if not isinstance(w.index, pd.DatetimeIndex):
        return "weights must be indexed by date (use panel.dates)"
    unknown = w.columns.difference(panel.symbols)
    if len(unknown):
        return f"weights reference symbols not in the panel: {list(unknown[:5])}"
    vals = w.to_numpy(dtype=float)
    if np.isinf(vals).any():
        return "weights contain infinite values"
    if w.index.max() > panel.dates.max():
        return "weights are dated after the last available bar"
    return None
