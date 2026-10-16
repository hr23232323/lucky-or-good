"""Append-only, hash-chained trial log.

Every line is a JSON object carrying ``prev``: the SHA-256 of the previous
line. Editing or deleting any line breaks the chain, which ``verify`` reports.
That doesn't stop tampering; it makes it visible to anyone auditing a run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

GENESIS = "genesis"


def _digest(line: str) -> str:
    return hashlib.sha256(line.encode()).hexdigest()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class Ledger:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return [ln for ln in self.path.read_text().splitlines() if ln.strip()]

    def entries(self) -> list[dict]:
        return [json.loads(ln) for ln in self._lines()]

    def append(self, entry: dict) -> dict:
        lines = self._lines()
        record = {
            "seq": len(lines) + 1,
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "prev": _digest(lines[-1]) if lines else GENESIS,
            **entry,
        }
        line = json.dumps(record, sort_keys=True, default=str)
        with self.path.open("a") as f:
            f.write(line + "\n")
        return record

    def verify(self) -> list[str]:
        """Problems with the chain; empty means intact."""
        problems = []
        prev = GENESIS
        for i, line in enumerate(self._lines(), start=1):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                problems.append(f"line {i}: not valid JSON")
                prev = _digest(line)
                continue
            if rec.get("prev") != prev:
                problems.append(f"line {i}: chain broken (edited, inserted or deleted before it)")
            if rec.get("seq") != i:
                problems.append(f"line {i}: sequence number {rec.get('seq')} out of order")
            prev = _digest(line)
        return problems
