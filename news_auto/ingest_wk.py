from __future__ import annotations

from datetime import date
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .fetch_article import DEFAULT_HEADERS, extract_date_text, normalize_date, text_of
from .models import NewsItem


def fetch_wk_list(
    list_url: str,
    cookie: str = "",
    week_start: Optional[date] = None,
    week_end: Optional[date] = None,
    timeout: int = 20,
) -> List[NewsItem]:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if cookie:
        session.headers["Cookie"] = cookie
    response = session.get(list_url, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    soup = BeautifulSoup(response.text, "lxml")
    items: List[NewsItem] = []
    for a_tag in soup.select("a[href]"):
        title = text_of(a_tag)
        href = a_tag.get("href", "")
        if not title or len(title) < 6:
            continue
        link = urljoin(list_url, href)
        surrounding = text_of(a_tag.parent) if a_tag.parent else title
        pub_date = normalize_date(extract_date_text(surrounding))
        if pub_date and week_start and week_end:
            try:
                parsed = date.fromisoformat(pub_date)
                if not (week_start <= parsed <= week_end):
                    continue
            except ValueError:
                pass
        if looks_like_noise(title):
            continue
        items.append(
            NewsItem(
                title=title,
                link=link,
                pub_date=pub_date,
                source="威科速递",
                fetch_status="wk_list",
            )
        )
    return dedupe_by_link(items)


def looks_like_noise(title: str) -> bool:
    noise = {"登录", "注册", "首页", "更多", "上一页", "下一页", "威科先行"}
    return title.strip() in noise


def dedupe_by_link(items: List[NewsItem]) -> List[NewsItem]:
    seen = set()
    result: List[NewsItem] = []
    for item in items:
        key = item.link or item.title
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
