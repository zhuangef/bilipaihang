"""Bilibili WBI signature helpers."""
from __future__ import annotations

import hashlib
import re
import time
from functools import reduce
from typing import Any
from urllib.parse import quote

MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]


def _extract_key(url: str) -> str:
    match = re.search(r"/([^/?]+)\.(?:png|jpg|webp)", url)
    if not match:
        return ""
    return match.group(1)


def get_mixin_key(img_key: str, sub_key: str) -> str:
    raw = img_key + sub_key
    return reduce(lambda s, i: s + raw[i], MIXIN_KEY_ENC_TAB, "")[:32]


def extract_wbi_keys(nav_data: dict[str, Any]) -> tuple[str, str]:
    wbi_img = nav_data.get("wbi_img") or {}
    return _extract_key(wbi_img.get("img_url", "")), _extract_key(wbi_img.get("sub_url", ""))


def sign_params(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, Any]:
    signed = {k: v for k, v in params.items() if v is not None}
    signed["wts"] = int(time.time())
    mixin_key = get_mixin_key(img_key, sub_key)
    query = "&".join(
        f"{quote(str(k), safe='')}={quote(str(v), safe='')}"
        for k, v in sorted(signed.items())
    )
    signed["w_rid"] = hashlib.md5((query + mixin_key).encode("utf-8")).hexdigest()
    return signed
