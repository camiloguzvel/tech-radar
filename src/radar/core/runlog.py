"""Bitácora de corridas: JSONL append-only en data/runs/ (los fallos quedan visibles)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from radar import PROJECT_ROOT

RUNS_DIR = PROJECT_ROOT / "data" / "runs"


def new_run_id(prefix: str) -> str:
    """Ordenable lexicográficamente: `<prefijo>-AAAAMMDDTHHMMSSZ`."""
    return f"{prefix}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"


def append(name: str, records: list[dict], runs_dir: Path = RUNS_DIR) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{name}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return path
