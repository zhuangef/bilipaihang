"""Command line entry for ranking videos from a Bilibili follow group."""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Any

from api import BiliClient
from config import settings
from exporter import export_all
from utils import duration_to_seconds, ensure_dirs, parse_date_to_ts, read_json, setup_logging, write_json

LOGGER = logging.getLogger(__name__)
STATE_FILE = settings.cache_dir / "progress_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取B站指定关注分组UP主投稿并按指标排序导出")
    parser.add_argument("--group-id", type=int, default=settings.follow_group_id, help="关注分组ID(tagid)")
    parser.add_argument("--cookie", default=settings.cookie, help="B站 Cookie；也可用 BILI_COOKIE 环境变量")
    parser.add_argument("--sort-by", default=settings.sort_by, choices=["view", "favorite", "like", "coin", "reply", "share", "pubdate", "duration"])
    parser.add_argument("--asc", action="store_true", help="升序排序，默认降序")
    parser.add_argument("--start-date", default=settings.start_date, help="筛选起始发布时间 YYYY-MM-DD")
    parser.add_argument("--end-date", default=settings.end_date, help="筛选结束发布时间 YYYY-MM-DD")
    parser.add_argument("--min-duration", type=int, default=settings.min_duration, help="最小时长（秒）")
    parser.add_argument("--max-duration", type=int, default=settings.max_duration, help="最大时长（秒）")
    parser.add_argument("--reset", action="store_true", help="清空断点状态后重新抓取")
    return parser.parse_args()


def extract_bgm_tag_names(detail: dict[str, Any]) -> str:
    """Return comma-separated tag names whose tag_type is bgm from view/detail data."""
    tags = detail.get("Tags") or detail.get("tags") or []
    return ", ".join(
        str(tag.get("tag_name"))
        for tag in tags
        if tag.get("tag_type") == "bgm" and tag.get("tag_name")
    )


def normalize_video(detail: dict[str, Any], fallback: dict[str, Any], up: dict[str, Any]) -> dict[str, Any]:
    view = detail.get("View") or detail
    stat = view.get("stat", {})
    up_mid = up.get("mid") or up.get("fid")
    up_name = up.get("uname") or up.get("name")
    pubdate = int(view.get("pubdate") or fallback.get("created") or 0)
    duration = int(view.get("duration") or duration_to_seconds(fallback.get("length")))
    return {
        "bvid": view.get("bvid") or fallback.get("bvid"),
        "aid": view.get("aid") or fallback.get("aid"),
        "title": view.get("title") or fallback.get("title"),
        "up_mid": up_mid,
        "up_name": up_name,
        "pubdate": pubdate,
        "pubdate_text": datetime.fromtimestamp(pubdate).strftime("%Y-%m-%d %H:%M:%S") if pubdate else "",
        "duration": duration,
        "duration_text": str(fallback.get("length") or ""),
        "view": stat.get("view", 0),
        "favorite": stat.get("favorite", 0),
        "like": stat.get("like", 0),
        "coin": stat.get("coin", 0),
        "reply": stat.get("reply", 0),
        "danmaku": stat.get("danmaku", 0),
        "share": stat.get("share", 0),
        "url": f"https://www.bilibili.com/video/{view.get('bvid') or fallback.get('bvid')}",
        "desc": view.get("desc", ""),
        "bgm_tag_name": extract_bgm_tag_names(detail),
    }


def pass_filters(row: dict[str, Any], args: argparse.Namespace) -> bool:
    start_ts = parse_date_to_ts(args.start_date)
    end_ts = parse_date_to_ts(args.end_date, end_of_day=True)
    if start_ts and row["pubdate"] < start_ts:
        return False
    if end_ts and row["pubdate"] > end_ts:
        return False
    if args.min_duration is not None and row["duration"] < args.min_duration:
        return False
    if args.max_duration is not None and row["duration"] > args.max_duration:
        return False
    return True


def main() -> None:
    args = parse_args()
    ensure_dirs(settings.cache_dir, settings.output_dir, settings.log_dir)
    setup_logging(settings.log_dir)

    if not args.cookie:
        raise SystemExit("请通过 --cookie 或 BILI_COOKIE 提供B站 Cookie。")
    if not args.group_id:
        raise SystemExit("请通过 --group-id 或 BILI_FOLLOW_GROUP_ID 提供关注分组ID。")
    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()

    state = read_json(STATE_FILE, {"done_up_mids": [], "videos": [], "traversed_videos": []})
    done_up_mids = set(state.get("done_up_mids", []))
    rows: list[dict[str, Any]] = state.get("videos", [])
    traversed_rows: list[dict[str, Any]] = state.get("traversed_videos", rows.copy())
    seen_bvids = {row.get("bvid") for row in rows}
    seen_traversed_bvids = {row.get("bvid") for row in traversed_rows}
    start_ts = parse_date_to_ts(args.start_date)

    client = BiliClient(args.cookie, settings.cache_dir, settings.cache_ttl_seconds, settings.request_interval, settings.retry_times, settings.retry_backoff)
    ups = client.get_follow_group_members(args.group_id, settings.page_size)
    LOGGER.info("found %s UPs in group %s", len(ups), args.group_id)

    for up in ups:
        mid = int(up.get("mid") or up.get("fid") or 0)
        if not mid or mid in done_up_mids:
            continue
        LOGGER.info("fetching videos for UP %s (%s)", up.get("uname") or up.get("name"), mid)
        for video in client.get_up_videos(mid, settings.page_size, stop_before_ts=start_ts):
            bvid = video.get("bvid")
            if not bvid or bvid in seen_traversed_bvids:
                continue
            detail = client.get_video_detail(bvid)
            row = normalize_video(detail, video, up)
            if bvid not in seen_traversed_bvids:
                traversed_rows.append(row)
                seen_traversed_bvids.add(bvid)
            if pass_filters(row, args):
                rows.append(row)
                seen_bvids.add(bvid)
        done_up_mids.add(mid)
        write_json(STATE_FILE, {"done_up_mids": sorted(done_up_mids), "videos": rows, "traversed_videos": traversed_rows})

    sort_desc = False if args.asc else settings.sort_desc
    rows.sort(key=lambda row: row.get(args.sort_by) or 0, reverse=sort_desc)
    export_all(rows, settings.output_dir, traversed_rows)
    write_json(STATE_FILE, {"done_up_mids": sorted(done_up_mids), "videos": rows, "traversed_videos": traversed_rows})
    LOGGER.info("exported %s videos to %s", len(rows), settings.output_dir)


if __name__ == "__main__":
    main()
