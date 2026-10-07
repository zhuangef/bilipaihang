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

# =AND(G2>=60,OR(DATEVALUE(LEFT(F2,10))>=DATE(2026,8,15),AND(DATEVALUE(LEFT(F2,10))<DATE(2026,8,15),J2>=200)))
@dataclass(slots=True)
class Settings:
    """Runtime settings for crawling and exporting Bilibili UP videos."""

    cookie: str = os.getenv("BILI_COOKIE", "SESSDATA=48bb4ef7%2C1804869499%2C3ed99191CjBMbLRbC1sydnHFjgiqTgs2IHuY8pncQApENTqt2m9dlB7lWN7FMMOjB-u9laaTlmISVmJ2eEo2VXdsbHRNNExiXzJhX2NWUGVoVVRtSUVBVUI1Y3FIUENzQUlRbDBtdHpBNjZDdEpXZk9QSDhhQlduQVVWUG9reGdaSnh5Y2ZvX0NsTkIyN0lnIIEC; bili_jct=e736fd514b4e9a8dad0bb1cd41a521e9; DedeUserID=335383513")
    # 右眸335383513:387046016(舞蹈区1)
    follow_group_id: int = int(os.getenv("BILI_FOLLOW_GROUP_ID", "387877024"))
    sort_by: SortMetric = os.getenv("BILI_SORT_BY", "favorite")  # type: ignore[assignment]
    sort_desc: bool = os.getenv("BILI_SORT_DESC", "1") not in {"0", "false", "False"}

    # Optional filters. Empty/None means no filtering.
    start_date: str | None = os.getenv("BILI_START_DATE") or None  # YYYY-MM-DD
    end_date: str | None = os.getenv("BILI_END_DATE") or None  # YYYY-MM-DD
    #start_date: str | None = "2026-07-01"
    # end_date: str | None = "2026-06-30"
    # min_duration: int | None = int(os.getenv("BILI_MIN_DURATION", "0")) or None
    min_duration: int | None = 0
    max_duration: int | None = int(os.getenv("BILI_MAX_DURATION", "0")) or None

    page_size: int = int(os.getenv("BILI_PAGE_SIZE", "50"))
    request_interval: float = float(os.getenv("BILI_REQUEST_INTERVAL", "0.05"))
    request_jitter: float = float(os.getenv("BILI_REQUEST_JITTER", "0.2"))
    detail_workers: int = int(os.getenv("BILI_DETAIL_WORKERS", "4"))
    retry_times: int = int(os.getenv("BILI_RETRY_TIMES", "3"))
    retry_backoff: float = float(os.getenv("BILI_RETRY_BACKOFF", "2.0"))
    cache_ttl_seconds: int = int(os.getenv("BILI_CACHE_TTL_SECONDS", str(7 * 24 * 3600)))

    cache_dir: Path = field(default=CACHE_DIR)
    output_dir: Path = field(default=OUTPUT_DIR)
    log_dir: Path = field(default=LOG_DIR)


settings = Settings()
