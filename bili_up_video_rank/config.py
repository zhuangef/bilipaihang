"""Project configuration.

Copy this file or edit values directly before running. Cookie is required for
reading private follow groups. Prefer setting BILI_COOKIE in the environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

SortMetric = Literal["view", "favorite", "like", "coin", "reply", "share", "pubdate", "duration"]


@dataclass(slots=True)
class Settings:
    """Runtime settings for crawling and exporting Bilibili UP videos."""

    cookie: str = os.getenv("BILI_COOKIE", "")
    follow_group_id: int = int(os.getenv("BILI_FOLLOW_GROUP_ID", "0"))
    sort_by: SortMetric = os.getenv("BILI_SORT_BY", "favorite")  # type: ignore[assignment]
    sort_desc: bool = os.getenv("BILI_SORT_DESC", "1") not in {"0", "false", "False"}

    # Optional filters. Empty/None means no filtering.
    start_date: str | None = os.getenv("BILI_START_DATE") or None  # YYYY-MM-DD
    end_date: str | None = os.getenv("BILI_END_DATE") or None  # YYYY-MM-DD
    min_duration: int | None = int(os.getenv("BILI_MIN_DURATION", "0")) or None
    max_duration: int | None = int(os.getenv("BILI_MAX_DURATION", "0")) or None

    page_size: int = int(os.getenv("BILI_PAGE_SIZE", "50"))
    request_interval: float = float(os.getenv("BILI_REQUEST_INTERVAL", "1.0"))
    retry_times: int = int(os.getenv("BILI_RETRY_TIMES", "3"))
    retry_backoff: float = float(os.getenv("BILI_RETRY_BACKOFF", "2.0"))
    cache_ttl_seconds: int = int(os.getenv("BILI_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))

    cache_dir: Path = field(default=CACHE_DIR)
    output_dir: Path = field(default=OUTPUT_DIR)
    log_dir: Path = field(default=LOG_DIR)


settings = Settings()
