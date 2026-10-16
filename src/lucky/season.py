"""A research season: one frozen setup, one ledger.

Everything that would change a result is pinned when the season is created:
the period layout (copied in), universe size, costs, benchmark, the
proposing model and its training cutoff. Change any of them and you start a
new season, so trial counts never mix setups.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from . import periods as periods_mod
from .ledger import Ledger


@dataclass
class Season:
    dir: Path
    name: str
    data_root: str
    model: str = "unspecified"
    model_cutoff: str = "unknown"
    top_n: int = 1000
    benchmark: str = "SPY"
    validation_budget: int = 25
    lookahead_samples: int = 3
    created: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    @property
    def periods(self) -> periods_mod.Periods:
        return periods_mod.load(self.dir / "periods.toml")

    @property
    def ledger(self) -> Ledger:
        return Ledger(self.dir / "ledger.jsonl")

    @classmethod
    def create(
        cls, dir: Path | str, periods_path: Path | str, data_root: Path | str, **kw
    ) -> Season:
        dir = Path(dir)
        if (dir / "season.toml").exists():
            raise FileExistsError(f"season already exists at {dir}")
        text = Path(periods_path).read_text()
        periods_mod.parse(text)  # validate before writing anything
        dir.mkdir(parents=True, exist_ok=True)
        (dir / "periods.toml").write_text(text)
        season = cls(dir=dir, name=kw.pop("name", dir.name), data_root=str(data_root), **kw)
        season._write()
        season.ledger.append(
            {
                "kind": "season",
                "settings": {k: v for k, v in asdict(season).items() if k != "dir"},
                "periods_hash": season.periods.source_hash,
            }
        )
        return season

    @classmethod
    def load(cls, dir: Path | str) -> Season:
        dir = Path(dir)
        raw = tomllib.loads((dir / "season.toml").read_text())
        return cls(dir=dir, **raw)

    def _write(self) -> None:
        lines = []
        for k, v in asdict(self).items():
            if k == "dir":
                continue
            lines.append(f"{k} = {v!r}" if isinstance(v, int) else f"{k} = {json.dumps(str(v))}")
        (self.dir / "season.toml").write_text("\n".join(lines) + "\n")
