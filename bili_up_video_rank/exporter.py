"""Export merged video data to JSON, CSV and Excel workbooks."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from utils import write_csv, write_json

FIELDS = [
    "bvid", "aid", "title", "up_mid", "up_name", "pubdate", "pubdate_text", "duration", "duration_text",
    "view", "favorite", "like", "coin", "reply", "danmaku", "share", "url", "desc",
]


def build_year_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"year": "", "video_count": 0, "view": 0, "favorite": 0, "like": 0, "coin": 0})
    for row in rows:
        year = row.get("pubdate_text", "")[:4] or "unknown"
        stats[year]["year"] = year
        stats[year]["video_count"] += 1
        for key in ("view", "favorite", "like", "coin"):
            stats[year][key] += int(row.get(key) or 0)
    return sorted(stats.values(), key=lambda item: item["year"], reverse=True)


def build_up_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[int, dict[str, Any]] = defaultdict(lambda: {"up_mid": 0, "up_name": "", "video_count": 0, "view": 0, "favorite": 0, "like": 0, "coin": 0})
    for row in rows:
        mid = int(row.get("up_mid") or 0)
        stats[mid]["up_mid"] = mid
        stats[mid]["up_name"] = row.get("up_name", "")
        stats[mid]["video_count"] += 1
        for key in ("view", "favorite", "like", "coin"):
            stats[mid][key] += int(row.get(key) or 0)
    return sorted(stats.values(), key=lambda item: item["view"], reverse=True)


def export_all(rows: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "all_video.json", rows)
    write_csv(output_dir / "all_video.csv", rows, FIELDS)

    with pd.ExcelWriter(output_dir / "all_video.xlsx", engine="openpyxl") as writer:
        pd.DataFrame(rows, columns=FIELDS).to_excel(writer, sheet_name="全部视频", index=False)
        pd.DataFrame(build_year_stats(rows)).to_excel(writer, sheet_name="按年度统计", index=False)
        pd.DataFrame(build_up_stats(rows)).to_excel(writer, sheet_name="每个UP统计", index=False)
