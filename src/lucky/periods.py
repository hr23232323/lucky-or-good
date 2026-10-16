"""Time blocks: which stretches of history a proposer may see, and how."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

KINDS = {"discovery", "validation", "vault", "forward"}
SEALED = {"vault", "forward"}


@dataclass(frozen=True)
class Block:
    name: str
    kind: str
    start: pd.Timestamp
    end: pd.Timestamp
    note: str = ""


@dataclass(frozen=True)
class Periods:
    dataset: str
    warmup_days: int
    blocks: tuple[Block, ...]
    source_hash: str = ""

    def block(self, name: str) -> Block:
        for b in self.blocks:
            if b.name == name:
                return b
        raise KeyError(f"no block named '{name}'; have {[b.name for b in self.blocks]}")

    def load_window(self, block: Block) -> tuple[pd.Timestamp, pd.Timestamp]:
        """Data a strategy may read for ``block``: warm-up before it, nothing after it."""
        return block.start - pd.offsets.BDay(self.warmup_days), block.end


def parse(text: str) -> Periods:
    raw = tomllib.loads(text)
    blocks = tuple(
        Block(
            name=b["name"],
            kind=b["kind"],
            start=pd.Timestamp(b["start"]),
            end=pd.Timestamp(b["end"]),
            note=b.get("note", ""),
        )
        for b in raw["block"]
    )
    for b in blocks:
        if b.kind not in KINDS:
            raise ValueError(f"block {b.name}: kind must be one of {sorted(KINDS)}")
        if b.end <= b.start:
            raise ValueError(f"block {b.name}: end must be after start")
    ordered = sorted(blocks, key=lambda b: b.start)
    for a, b in zip(ordered, ordered[1:], strict=False):
        if b.start <= a.end:
            raise ValueError(f"blocks {a.name} and {b.name} overlap")
    if not any(b.kind == "discovery" for b in blocks):
        raise ValueError("need at least one discovery block")
    return Periods(
        dataset=raw.get("dataset", ""),
        warmup_days=int(raw.get("warmup_days", 260)),
        blocks=blocks,
        source_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
    )


def load(path: Path | str) -> Periods:
    return parse(Path(path).read_text())
