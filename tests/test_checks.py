import pandas as pd
import pytest

from lucky.checks import compare_prefix, static_check

OK = """
import numpy as np
import pandas as pd
META = {"name": "x", "hypothesis": "y", "expected_sign": "+"}
def weights(panel):
    return panel.close.pct_change(20).rank(axis=1).le(5).astype(float) / 5
"""


def rules(src: str) -> set[str]:
    return {v.rule for v in static_check(src)}


def test_clean_strategy_passes():
    assert static_check(OK) == []


@pytest.mark.parametrize(
    "snippet, rule",
    [
        ("import os", "import"),
        ("from subprocess import run", "import"),
        ("import requests", "import"),
        ("x = open('/etc/passwd')", "banned-name"),
        ("x = eval('1')", "banned-name"),
        ("x = __import__('os')", "banned-name"),
        ("x = (1).__class__", "dunder"),
        ("def f(p): return p.close.bfill()", "banned-method"),
        ("def f(p): return p.close.interpolate()", "banned-method"),
        ("def f(p): return pd.read_parquet('x')", "banned-method"),
        ("def f(p): return p.close.to_csv('x')", "banned-method"),
        ("def f(p): return p.close.shift(-1)", "future-shift"),
        ("def f(p): return p.close.shift(periods=-5)", "future-shift"),
        ("def f(p): return p.close.rolling(5, center=True).mean()", "centered-window"),
        ("def f(p): return p.close.fillna(method='bfill')", "back-fill"),
    ],
)
def test_banned_patterns(snippet, rule):
    assert rule in rules(OK + "\n" + snippet + "\n")


def test_frequency_codes_are_not_tickers():
    src = OK + (
        "def g(panel):\n"
        "    m = panel.dates.to_series().groupby(panel.dates.to_period('M')).max()\n"
        "    w = panel.close.resample('W-FRI').last()\n"
        "    return panel.close.rank(axis=1, method='first'), m, w\n"
    )
    assert static_check(src) == []


def test_contract_required():
    assert "contract" in rules("META = {'name': 'x', 'hypothesis': 'y', 'expected_sign': '+'}")
    assert "contract" in rules("def weights(panel): return None")
    assert "contract" in rules("META = {'name': 'x'}\ndef weights(panel): return None")


def test_syntax_error_reported():
    assert rules("def weights(:") == {"syntax"}


def test_compare_prefix_detects_changes_before_t():
    idx = pd.bdate_range("2024-01-01", periods=5)
    full = pd.DataFrame({"A": [1.0, 0.0, 1.0, 0.0, 1.0]}, index=idx)
    same = full.iloc[:3]
    assert compare_prefix(full, same, idx[2])["ok"]
    changed = same.copy()
    changed.iloc[1, 0] = 0.5
    out = compare_prefix(full, changed, idx[2])
    assert not out["ok"] and out["mismatched_cells"] == 1


def test_month_end_calendar_effect_is_not_lookahead():
    idx = pd.bdate_range("2024-01-01", periods=10)
    full = pd.DataFrame({"A": [1.0, 0.5]}, index=[idx[0], idx[9]])  # trades at "month ends"
    cut = pd.DataFrame({"A": [1.0, 0.7]}, index=[idx[0], idx[4]])  # cut date looks like one
    out = compare_prefix(full, cut, idx[4])
    assert out["ok"] and out["ignored_final_row"]


def test_missing_row_in_truncated_run_is_flagged():
    idx = pd.bdate_range("2024-01-01", periods=5)
    full = pd.DataFrame({"A": [1.0, 1.0, 1.0]}, index=idx[:3])
    cut = pd.DataFrame({"A": [1.0, 1.0]}, index=idx[:2])
    assert not compare_prefix(full, cut, idx[2])["ok"]
