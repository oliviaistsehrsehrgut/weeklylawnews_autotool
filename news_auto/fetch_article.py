from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

from .models import NewsItem
from .official_source import detect_official_source

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
}


def fetch_items(
    items: Iterable[NewsItem],
    timeout: int = 20,
    authority_tokens: Iterable[str] = (),
) -> List[NewsItem]:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    result: List[NewsItem] = []
    for item in items:
        if not item.link:
            item.fetch_status = "missing_link"
            item.metadata["official_source"] = False
            item.metadata["official_source_reason"] = "No valid source link"
            result.append(item)
            continue
        try:
            result.append(fetch_one(session, item, timeout=timeout, authority_tokens=authority_tokens))
        except Exception as exc:  # noqa: BLE001 - batch jobs should keep going
            item.fetch_status = f"failed: {exc.__class__.__name__}"
            item.metadata["fetch_error"] = str(exc)
            item.metadata.setdefault("official_source", False)
            item.metadata.setdefault("official_source_reason", "Fetch failed; source not verified")
            result.append(item)
    return result



def fetch_html_with_edge(url: str, timeout: int) -> str:
    if sync_playwright is None:
        raise RuntimeError("Playwright is required for HTTP 412 fallback")
    timeout_ms = max(5, timeout) * 1000
    with sync_playwright() as playwright:
        browser = None
        try:
            try:
                browser = playwright.chromium.launch(channel="msedge", headless=True)
            except Exception:
                browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"], extra_http_headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"})
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1200)
            html = page.content()
            if len(html) < 500:
                raise RuntimeError("Browser was blocked by the source website")
            return html
        finally:
            if browser is not None:
                browser.close()

def fetch_one(
    session: requests.Session,
    item: NewsItem,
    timeout: int = 20,
    authority_tokens: Iterable[str] = (),
) -> NewsItem:
    item.metadata.pop("fetch_error", None)
    is_official, reason = detect_official_source(item.link, authority_tokens)
    item.metadata["official_source"] = is_official
    item.metadata["official_source_reason"] = reason
    if is_official:
        item.official_link = item.link

    response = session.get(item.link, timeout=timeout)
    if response.status_code == 412:
        html = fetch_html_with_edge(item.link, timeout)
        response_headers = response.headers
    else:
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        html = response.text
        response_headers = response.headers
    parsed = urlparse(item.link)
    if "mp.weixin.qq.com" in parsed.netloc:
        parse_wechat_article(item, html)
    else:
        parse_generic_article(item, html, response_headers)

    if not item.official_link:
        official_link, official_reason = find_official_link(item.link, html, authority_tokens)
        if official_link:
            item.official_link = official_link
            item.metadata["official_source"] = True
            item.metadata["official_source_reason"] = official_reason
    item.fetch_status = "ok"
    item.metadata.pop("fetch_error", None)
    return item


def parse_wechat_article(item: NewsItem, html: str) -> None:
    soup = BeautifulSoup(html, "lxml")
    title = text_of(soup.select_one("#activity-name")) or meta_content(soup, "og:title")
    source = text_of(soup.select_one("#js_name")) or item.source or "WeChat official account"
    date = text_of(soup.select_one("#publish_time")) or extract_date_text(soup.get_text("\n"))
    content_node = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
    content = text_of(content_node) if content_node else text_of(soup.body)
    item.title = item.title or clean_spaces(title)
    item.source = clean_spaces(source)
    item.pub_date = normalize_date(date)
    item.content = clean_spaces(content)


def parse_generic_article(item: NewsItem, html: str, headers: requests.structures.CaseInsensitiveDict) -> None:
    soup = BeautifulSoup(html, "lxml")
    title = meta_content(soup, "og:title") or text_of(soup.title) or first_heading(soup)
    date = (
        meta_content(soup, "article:published_time")
        or meta_content(soup, "pubdate")
        or headers.get("Last-Modified")
        or extract_date_text(soup.get_text("\n"))
    )
    content_node = (
        soup.select_one("article")
        or soup.select_one("main")
        or soup.select_one("#content")
        or soup.select_one(".content")
        or soup.body
    )
    item.title = item.title or clean_spaces(title)
    item.pub_date = normalize_date(date)
    item.content = clean_spaces(text_of(content_node))
    if not item.source:
        item.source = urlparse(item.link).netloc


def text_of(node: Optional[object]) -> str:
    if node is None:
        return ""
    if hasattr(node, "get_text"):
        return node.get_text("\n", strip=True)
    return str(node).strip()


def first_heading(soup: BeautifulSoup) -> str:
    for selector in ("h1", "h2"):
        found = soup.select_one(selector)
        if found:
            return text_of(found)
    return ""


def meta_content(soup: BeautifulSoup, name: str) -> str:
    selectors = [
        f'meta[property="{name}"]',
        f'meta[name="{name}"]',
        f'meta[itemprop="{name}"]',
    ]
    for selector in selectors:
        found = soup.select_one(selector)
        if found and found.get("content"):
            return found["content"].strip()
    return ""


def extract_date_text(text: str) -> str:
    patterns = [
        r"20\d{2}\s*[-/.年]\s*\d{1,2}\s*[-/.月]\s*\d{1,2}\s*日?",
        r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def normalize_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = clean_spaces(value)
    chinese_date = re.fullmatch(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?", value)
    if chinese_date:
        year, month, day = chinese_date.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except Exception:  # noqa: BLE001
        return value


def clean_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def find_official_link(
    source_url: str,
    html: str,
    authority_tokens: Iterable[str] = (),
) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[tuple[int, str, str]] = []
    preferred_labels = ("original", "source", "view original", "full text", "document", "announcement")
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href", "")).strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        candidate = urljoin(source_url, href)
        is_official, reason = detect_official_source(candidate, authority_tokens)
        if not is_official:
            continue
        label = clean_spaces(text_of(anchor))
        score = 10 if any(term in label for term in preferred_labels) else 0
        score += 1 if candidate != source_url else 0
        candidates.append((score, candidate, reason))
    if not candidates:
        return "", "No official link found in page"
    _, link, reason = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
    return link, f"Official link found: {reason}"
