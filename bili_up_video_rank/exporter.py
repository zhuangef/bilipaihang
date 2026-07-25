"""Export merged video data to JSON, CSV and Excel workbooks."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import unicodedata
from typing import Any

import pandas as pd
from openpyxl.utils import get_column_letter

from utils import write_csv, write_json

FIELDS = [
    "bvid", "aid", "title", "up_mid", "up_name", "pubdate", "pubdate_text", "duration", "duration_text",
    "view", "favorite", "like", "coin", "reply", "danmaku", "share", "url", "desc",
]

# Excel files cannot contain most ASCII control characters in cell text.
# Bilibili titles/descriptions may include these characters, which makes
# openpyxl raise IllegalCharacterError while writing all_video.xlsx.
ILLEGAL_EXCEL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")
INVALID_EXCEL_SHEET_NAME_RE = re.compile(r"[\\/*?:\[\]]")
MAX_EXCEL_SHEET_NAME_LENGTH = 31
MIN_EXCEL_COLUMN_WIDTH = 8
MAX_EXCEL_COLUMN_WIDTH = 80
EXCEL_COLUMN_PADDING = 2


def sanitize_excel_value(value: Any) -> Any:
    """Remove characters that are illegal in Excel cell strings."""
    if isinstance(value, str):
        return ILLEGAL_EXCEL_CHARACTERS_RE.sub("", value)
    return value


def sanitize_excel_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy of rows with string values safe for openpyxl export."""
    return [{key: sanitize_excel_value(value) for key, value in row.items()} for row in rows]


def display_width(value: Any) -> int:
    """Estimate the rendered width of an Excel cell value."""
    text = "" if value is None else str(value)
    return sum(2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1 for char in text)


def autofit_excel_columns(writer: pd.ExcelWriter) -> None:
    """Set worksheet column widths based on current cell contents."""
    for worksheet in writer.sheets.values():
        for column_cells in worksheet.columns:
            max_width = max(display_width(cell.value) for cell in column_cells)
            adjusted_width = min(max(max_width + EXCEL_COLUMN_PADDING, MIN_EXCEL_COLUMN_WIDTH), MAX_EXCEL_COLUMN_WIDTH)
            worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = adjusted_width


def unique_excel_sheet_name(name: str, used_names: set[str]) -> str:
    """Return a unique Excel worksheet name derived from an UP name."""
    cleaned = INVALID_EXCEL_SHEET_NAME_RE.sub("_", sanitize_excel_value(name)).strip().strip("'")
    if not cleaned:
        cleaned = "UP"

    base_name = cleaned[:MAX_EXCEL_SHEET_NAME_LENGTH]
    sheet_name = base_name
    suffix = 1
    while sheet_name in used_names:
        suffix_text = f"_{suffix}"
        sheet_name = f"{base_name[:MAX_EXCEL_SHEET_NAME_LENGTH - len(suffix_text)]}{suffix_text}"
        suffix += 1
    used_names.add(sheet_name)
    return sheet_name


def build_up_video_sheets(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group traversed videos into Excel-safe, per-UP sheet names."""
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    up_names: dict[str, str] = {}
    for row in rows:
        up_key = str(row.get("up_mid") or row.get("up_name") or "unknown")
        grouped_rows[up_key].append(row)
        up_names.setdefault(up_key, str(row.get("up_name") or f"UP_{up_key}"))

    used_names = {"全部视频", "按年度统计", "每个UP统计"}
    sheets: list[tuple[str, list[dict[str, Any]]]] = []
    for up_key, up_rows in grouped_rows.items():
        sheet_name = unique_excel_sheet_name(up_names.get(up_key) or f"UP_{up_key}", used_names)
        sheets.append((sheet_name, up_rows))
    return sheets


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


def export_all(rows: list[dict[str, Any]], output_dir: Path, traversed_rows: list[dict[str, Any]] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "all_video.json", rows)
    write_csv(output_dir / "all_video.csv", rows, FIELDS)

    excel_rows = sanitize_excel_rows(rows)
    traversed_excel_rows = sanitize_excel_rows(traversed_rows if traversed_rows is not None else rows)
    with pd.ExcelWriter(output_dir / "all_video.xlsx", engine="openpyxl") as writer:
        pd.DataFrame(excel_rows, columns=FIELDS).to_excel(writer, sheet_name="全部视频", index=False)
        for sheet_name, up_rows in build_up_video_sheets(traversed_excel_rows):
            pd.DataFrame(up_rows, columns=FIELDS).to_excel(writer, sheet_name=sheet_name, index=False)
        pd.DataFrame(build_year_stats(excel_rows)).to_excel(writer, sheet_name="按年度统计", index=False)
        pd.DataFrame(build_up_stats(excel_rows)).to_excel(writer, sheet_name="每个UP统计", index=False)
        autofit_excel_columns(writer)
