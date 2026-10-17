"""Checks that catch strategies peeking at the future or reaching outside their box.

Static checks read the syntax tree before anything runs. The dynamic
truncation check runs the strategy again on data cut off at t and requires
identical weights up to t. Static rules are a first filter; the truncation
check is what actually proves causality for the dates tested.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

ALLOWED_IMPORTS = {
    "__future__",
    "collections",
    "dataclasses",
    "functools",
    "itertools",
    "math",
    "numpy",
    "pandas",
    "statistics",
    "typing",
}
BANNED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "exit",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "quit",
    "setattr",
    "vars",
}
# Methods that read the future (back-fill, interpolation) or touch the filesystem.
_IO_FORMATS = ("csv", "parquet", "pickle", "json", "sql", "hdf", "excel", "feather", "clipboard")
BANNED_METHODS = {
    "backfill",
    "bfill",
    "interpolate",
    "read_table",
    "read_html",
    *(f"read_{x}" for x in _IO_FORMATS),
    *(f"to_{x}" for x in _IO_FORMATS),
    # numpy file I/O
    "fromfile",
    "genfromtxt",
    "load",
    "loadtxt",
    "memmap",
    "save",
    "savetxt",
    "savez",
    "savez_compressed",
    "tofile",
    # pandas I/O objects and string evaluation
    "ExcelFile",
    "ExcelWriter",
    "HDFStore",
    "eval",
}
# Submodules that lead to file I/O or compiled code.
BANNED_MODULE_ATTRS = {"compat", "ctypeslib", "f2py", "io"}
REQUIRED_META = {"name", "hypothesis", "expected_sign"}

# Strategies are rules over features. A date or a ticker in the code is the
# model's memory of history leaking in ("avoid 2008", "hold NVDA").
DATE_LITERAL = re.compile(r"^\s*(19|20)\d{2}([-/.]\d{1,2}|\d{4})")
TICKER_LITERAL = re.compile(r"^[A-Z][A-Z0-9]{0,5}([.-][A-Z0-9]+)*$")


@dataclass(frozen=True)
class Violation:
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.rule}: {self.detail}"


def _is_negative(node: ast.AST) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return True
    return isinstance(node, ast.Constant) and isinstance(node.value, int | float) and node.value < 0


def _selects_columns(node: ast.AST, parent: dict) -> bool:
    """Is this string used to pick columns (a subscript, a literal list, a comparison)?"""
    cur = node
    while cur in parent:
        up = parent[cur]
        if isinstance(up, ast.Subscript) and cur is up.slice:
            return True
        if isinstance(up, ast.Compare | ast.List | ast.Tuple | ast.Set):
            return True
        if isinstance(up, ast.stmt | ast.Call | ast.Dict | ast.keyword):
            return False
        cur = up
    return False


def static_check(source: str) -> list[Violation]:
    """Reject strategy source that breaks the rules. Empty list means it passed."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [Violation(e.lineno or 0, "syntax", str(e))]
    out: list[Violation] = []

    def bad(node, rule, detail):
        out.append(Violation(getattr(node, "lineno", 0), rule, detail))

    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bad(node, "class", "strategies are functions; classes aren't allowed")
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "__"
        ):
            bad(node, "dunder", f"def {node.name}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if DATE_LITERAL.match(node.value):
                bad(node, "date-literal", f"'{node.value}': use rules, not calendar dates")
            elif TICKER_LITERAL.match(node.value) and _selects_columns(node, parent):
                bad(node, "ticker-literal", f"'{node.value}': use rules, not named stocks")

        if isinstance(node, ast.Import | ast.ImportFrom):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module]
            for name in names:
                if (name or "").split(".")[0] not in ALLOWED_IMPORTS:
                    bad(node, "import", f"'{name}' is not allowed")
        elif isinstance(node, ast.Name) and node.id in BANNED_CALLS | {"__builtins__"}:
            bad(node, "banned-name", node.id)
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                bad(node, "dunder", node.attr)
            if node.attr in BANNED_METHODS:
                bad(node, "banned-method", node.attr)
            if node.attr in BANNED_MODULE_ATTRS:
                bad(node, "banned-module-attr", node.attr)
            if node.attr == "year":
                bad(node, "calendar-year", "rules can't depend on which year it is")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Attribute) and fn.attr == "shift":
                args = list(node.args[:1]) + [k.value for k in node.keywords if k.arg == "periods"]
                if any(_is_negative(a) for a in args):
                    bad(node, "future-shift", "shift with a negative period reads the future")
            for kw in node.keywords:
                if kw.arg == "center" and isinstance(kw.value, ast.Constant) and kw.value.value:
                    bad(node, "centered-window", "center=True uses future rows")
                if (
                    kw.arg == "method"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value in {"bfill", "backfill"}
                ):
                    bad(node, "back-fill", "fill method reads the future")

    top = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if "weights" not in top:
        bad(tree, "contract", "define a top-level function `weights(panel)`")
    meta = next(
        (
            n.value
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "META" for t in n.targets)
        ),
        None,
    )
    if not isinstance(meta, ast.Dict):
        bad(tree, "contract", "define a literal `META = {...}` dict")
    else:
        keys = {k.value for k in meta.keys if isinstance(k, ast.Constant)}
        missing = REQUIRED_META - keys
        if missing:
            bad(meta, "contract", f"META is missing {sorted(missing)}")
    return out


def compare_prefix(full: pd.DataFrame, cut: pd.DataFrame, t) -> dict:
    """Compare weights decided on or before ``t`` from a full run and a truncated run."""
    t = pd.Timestamp(t)
    a = full.loc[:t]
    b = cut.loc[:t]
    # Calendar exception: a strategy that trades on "the last day of the month"
    # sees the cut date as a month-end and trades there, while the full run
    # doesn't. Knowing tomorrow's date isn't look-ahead (calendars are public),
    # so a final row at t that the full run doesn't trade on is not compared.
    full_trades_at_t = t in a.index and a.loc[t].notna().any()
    ignored_final_row = bool(len(b) and b.index[-1] == t and not full_trades_at_t)
    if ignored_final_row:
        b = b.iloc[:-1]
        a = a.drop(index=t, errors="ignore")
    idx = a.index.union(b.index)
    cols = a.columns.union(b.columns)
    a = a.reindex(index=idx, columns=cols).to_numpy(dtype=float)
    b = b.reindex(index=idx, columns=cols).to_numpy(dtype=float)
    nan_mismatch = np.isnan(a) != np.isnan(b)
    diff = np.where(np.isnan(a) | np.isnan(b), 0.0, np.abs(a - b))
    bad = nan_mismatch | (diff > 1e-9 + 1e-6 * np.abs(np.nan_to_num(a)))
    return {
        "date": str(t.date()),
        "ok": not bool(bad.any()),
        "mismatched_cells": int(bad.sum()),
        "max_abs_diff": float(diff.max()) if diff.size else 0.0,
        "ignored_final_row": ignored_final_row,
    }
