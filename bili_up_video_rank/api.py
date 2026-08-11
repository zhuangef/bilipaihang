"""Bilibili API client with cache, retries, rate limiting and WBI signing."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests

from utils import cache_key, is_cache_valid, read_json, write_json
from wbi import extract_wbi_keys, sign_params

LOGGER = logging.getLogger(__name__)


class BiliApiError(RuntimeError):
    """Raised when Bilibili returns an unexpected response."""


class BiliClient:
    def __init__(self, cookie: str, cache_dir: Path, ttl_seconds: int, interval: float, retries: int, backoff: float) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.interval = interval
        self.retries = retries
        self.backoff = backoff
        self.last_request_at = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Cookie": cookie,
        })
        self.img_key = ""
        self.sub_key = ""

    def _rate_limit(self) -> None:
        wait = self.interval - (time.time() - self.last_request_at)
        if wait > 0:
            time.sleep(wait)

    def get_json(self, url: str, params: dict[str, Any] | None = None, use_cache: bool = True, sign: bool = False) -> dict[str, Any]:
        params = dict(params or {})
        if sign:
            self.ensure_wbi_keys()
            params = sign_params(params, self.img_key, self.sub_key)
        key = cache_key(url, params)
        cache_path = self.cache_dir / f"{key}.json"
        if use_cache and is_cache_valid(cache_path, self.ttl_seconds):
            return read_json(cache_path, {})

        for attempt in range(1, self.retries + 1):
            try:
                self._rate_limit()
                resp = self.session.get(url, params=params, timeout=20)
                self.last_request_at = time.time()
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") not in (0, None):
                    raise BiliApiError(f"API code={data.get('code')}, message={data.get('message')}")
                write_json(cache_path, data)
                return data
            except Exception as exc:  # noqa: BLE001 - retry wrapper logs all transient errors
                if attempt >= self.retries:
                    raise
                sleep_for = self.backoff ** (attempt - 1)
                LOGGER.warning("request failed (%s/%s): %s; sleep %.1fs", attempt, self.retries, exc, sleep_for)
                time.sleep(sleep_for)
        raise BiliApiError("unreachable retry state")

    def ensure_wbi_keys(self) -> None:
        if self.img_key and self.sub_key:
            return
        data = self.get_json("https://api.bilibili.com/x/web-interface/nav", use_cache=False)
        self.img_key, self.sub_key = extract_wbi_keys(data.get("data", {}))
        if not self.img_key or not self.sub_key:
            raise BiliApiError("failed to retrieve WBI keys; check cookie/network")

    def get_follow_group_members(self, tagid: int, page_size: int = 50) -> list[dict[str, Any]]:
        members: list[dict[str, Any]] = []
        pn = 1
        while True:
            data = self.get_json(
                "https://api.bilibili.com/x/relation/tag",
                {"tagid": tagid, "pn": pn, "ps": page_size},
                use_cache=False,
            ).get("data", {})
            batch = data if isinstance(data, list) else data.get("list", [])
            if not batch:
                break
            members.extend(batch)
            if len(batch) < page_size:
                break
            pn += 1
        return members

    def get_up_videos(self, mid: int, page_size: int = 50, stop_before_ts: int | None = None) -> list[dict[str, Any]]:
        """Return UP videos in publish-date order, optionally stopping before a timestamp."""
        videos: list[dict[str, Any]] = []
        pn = 1
        while True:
            data = self.get_json(
                "https://api.bilibili.com/x/space/wbi/arc/search",
                {"mid": mid, "pn": pn, "ps": page_size, "order": "pubdate"},
                sign=True,
            ).get("data", {})
            vlist = data.get("list", {}).get("vlist", [])
            if not vlist:
                break
            should_stop = False
            for video in vlist:
                pubdate = int(video.get("created") or video.get("pubdate") or 0)
                if stop_before_ts and pubdate and pubdate < stop_before_ts:
                    should_stop = True
                    break
                videos.append(video)
            if should_stop:
                LOGGER.info("stop fetching UP %s videos at page %s because pubdate is before start_date", mid, pn)
                break
            page = data.get("page", {})
            total = int(page.get("count", 0) or 0)
            if pn * page_size >= total or len(vlist) < page_size:
                break
            pn += 1
        return videos

    def get_video_detail(self, bvid: str) -> dict[str, Any]:
        return self.get_json(
            "https://api.bilibili.com/x/web-interface/view",
            {"bvid": bvid},
            use_cache=True,
        ).get("data", {})

    def get_video_tags(self, bvid: str) -> list[dict[str, Any]]:
        """Return tag metadata for a video, including BGM tags when present."""
        data = self.get_json(
            "https://api.bilibili.com/x/tag/archive/tags",
            {"bvid": bvid},
            use_cache=True,
        ).get("data", [])
        return data if isinstance(data, list) else []
