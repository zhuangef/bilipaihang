"""Shared utilities for logging, cache, state and data normalization."""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def setup_logging(log_dir: Path) -> None:
    ensure_dirs(log_dir)
    log_file = log_dir / "run.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
    )


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def cache_key(url: str, params: dict[str, Any] | None = None) -> str:
    raw = json.dumps({"url": url, "params": params or {}}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_cache_valid(path: Path, ttl_seconds: int) -> bool:
    if not path.exists():
        return False
    return time.time() - path.stat().st_mtime <= ttl_seconds


def parse_date_to_ts(value: str | None, end_of_day: bool = False) -> int | None:
    if not value:
        return None
    dt = datetime.strptime(value, "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def duration_to_seconds(duration: str | int | None) -> int:
    if duration is None:
        return 0
    if isinstance(duration, int):
        return duration
    parts = [int(p) for p in str(duration).split(":")]
    total = 0
    for part in parts:
        total = total * 60 + part
    return total


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
