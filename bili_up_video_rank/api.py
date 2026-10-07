"""Bilibili API client with cache, retries, rate limiting and WBI signing."""
from __future__ import annotations

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

import requests

from utils import cache_key, is_cache_valid, read_json, write_json
from wbi import extract_wbi_keys, sign_params

LOGGER = logging.getLogger(__name__)


class BiliApiError(RuntimeError):
    """Raised when Bilibili returns an unexpected response."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class BiliClient:
    def __init__(
        self,
        cookie: str,
        cache_dir: Path,
        ttl_seconds: int,
        interval: float,
        retries: int,
        backoff: float,
        jitter: float = 0.2,
    ) -> None:
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_seconds
        self.interval = interval
        self.retries = retries
        self.backoff = backoff
        self.jitter = max(0.0, jitter)
        self.last_request_at = 0.0
        self._rate_lock = threading.Lock()
        self._wbi_lock = threading.Lock()
        self._thread_local = threading.local()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Referer": "https://www.bilibili.com/",
            "Cookie": cookie,
        }
        self.img_key = ""
        self.sub_key = ""

    @property
    def session(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update(self.headers)
            self._thread_local.session = session
        return session

    def _rate_limit(self) -> None:
        """Apply a process-wide minimum request gap with small jitter.

        The lock keeps concurrent detail workers from starting requests in a
        burst.  This preserves a human-like cadence while allowing network
        latency to overlap between workers.
        """
        with self._rate_lock:
            elapsed = time.time() - self.last_request_at
            wait = self.interval - elapsed
            if wait > 0:
                time.sleep(wait)
            if self.jitter:
                time.sleep(random.uniform(0, self.jitter))
            self.last_request_at = time.time()

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
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") not in (0, None):
                    raise BiliApiError(f"API code={data.get('code')}, message={data.get('message')}", code=data.get("code"))
                write_json(cache_path, data)
                return data
            except Exception as exc:  # noqa: BLE001 - retry wrapper logs all transient errors
                if isinstance(exc, BiliApiError) and exc.code == -404:
                    raise
                if attempt >= self.retries:
                    raise
                sleep_for = self.backoff ** (attempt - 1)
                LOGGER.warning("request failed (%s/%s): %s; sleep %.1fs", attempt, self.retries, exc, sleep_for)
                time.sleep(sleep_for)
        raise BiliApiError("unreachable retry state")

    def ensure_wbi_keys(self) -> None:
        if self.img_key and self.sub_key:
            return
        with self._wbi_lock:
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
            "https://api.bilibili.com/x/web-interface/view/detail",
            {"bvid": bvid},
            use_cache=True,
        ).get("data", {})

    def iter_video_details(self, videos: Iterable[dict[str, Any]], max_workers: int = 1) -> Iterable[tuple[dict[str, Any], dict[str, Any] | BiliApiError]]:
        """Yield video detail results, optionally fetched by safe concurrent workers."""
        video_list = list(videos)
        workers = max(1, max_workers)
        if workers == 1 or len(video_list) <= 1:
            for video in video_list:
                yield video, self.get_video_detail(str(video.get("bvid") or ""))
            return

        def fetch(video: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | BiliApiError]:
            try:
                return video, self.get_video_detail(str(video.get("bvid") or ""))
            except BiliApiError as exc:
                return video, exc

        with ThreadPoolExecutor(max_workers=workers) as executor:
            yield from executor.map(fetch, video_list)
