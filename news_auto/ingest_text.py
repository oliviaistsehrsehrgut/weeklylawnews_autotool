from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import NewsItem

URL_PATTERN = re.compile(r"https?://[^\s<>'\"，。；；、)）\]]+")
TRACKING_PARAMS = {
    "scene",
    "clicktime",
    "enterid",
    "ascene",
    "devicetype",
    "version",
    "nettype",
    "abtest_cookie",
    "pass_ticket",
    "wx_header",
}


def normalize_url(url: str) -> str:
    url = url.strip().rstrip(".,;，。；")
    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_PARAMS
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def extract_links(text: str) -> List[str]:
    seen = set()
    links: List[str] = []
    for match in URL_PATTERN.findall(text):
        link = normalize_url(match)
        if link not in seen:
            seen.add(link)
            links.append(link)
    return links


def items_from_text(text: str, source: str = "人工/元宝粘贴") -> List[NewsItem]:
    return [NewsItem(link=link, source=source) for link in extract_links(text)]


def items_from_file(path: Path, source: str = "人工/元宝粘贴") -> List[NewsItem]:
    return items_from_text(path.read_text(encoding="utf-8"), source=source)


def dedupe_items(items: Iterable[NewsItem]) -> List[NewsItem]:
    seen = set()
    result: List[NewsItem] = []
    for item in items:
        key = item.link or item.title
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
