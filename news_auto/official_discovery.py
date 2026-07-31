from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .models import NewsItem
from .official_source import detect_official_source

NORMATIVE_MARKERS = (
    "征求意见",
    "意见稿",
    "草案",
    "法律",
    "法规",
    "条例",
    "办法",
    "规定",
    "通知",
    "指导意见",
    "决定",
    "标准",
    "规章",
    "实施细则",
    "规范性文件",
)

SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
}


def discover_official_sources(items: Iterable[NewsItem], config: Dict[str, Any]) -> List[NewsItem]:
    search_cfg = config.get("official_search", {})
    if search_cfg.get("enabled", True) is False:
        return list(items)

    result: List[NewsItem] = []
    attempted = 0
    found = 0
    for item in items:
        if item.official_link or not looks_like_normative_document(item):
            result.append(item)
            continue
        attempted += 1
        item.metadata["official_search_attempted"] = True
        try:
            matched = discover_one(item, config)
            if matched.metadata.get("official_search_found"):
                found += 1
            result.append(matched)
        except Exception as exc:  # noqa: BLE001 - discovery must not stop a batch
            item.metadata["official_search_error"] = f"{exc.__class__.__name__}: {exc}"
            result.append(item)
    for item in result:
        if attempted and found:
            item.metadata["official_search_batch_found"] = found
    return result


def discover_one(item: NewsItem, config: Dict[str, Any]) -> NewsItem:
    search_cfg = config.get("official_search", {})
    max_results = int(search_cfg.get("max_results", 5))
    max_queries = int(search_cfg.get("max_queries", 12))
    timeout = int(search_cfg.get("timeout_seconds", 20))
    threshold = float(search_cfg.get("title_similarity_threshold", 0.48))
    document_titles = extract_document_titles(f"{item.title}\n{item.content}")
    attempts: List[Dict[str, Any]] = []

    for query in build_queries(item)[:max_queries]:
        search_results = search_web(query, search_cfg, timeout)
        attempts.append({"query": query, "candidate_count": len(search_results)})
        matched = accept_candidate(
            item,
            search_results[:max_results],
            document_titles,
            query,
            threshold,
            config,
            timeout,
        )
        if matched:
            item.metadata["official_search_attempts"] = attempts
            return item

    # 搜索引擎没有收录时，直接尝试从正文识别出的机关官网站内搜索。
    for domain in extract_official_domains(f"{item.title}\n{item.source}\n{item.content}")[:3]:
        for document_title in document_titles[:3]:
            site_query = f"site:{domain} {document_title}"
            try:
                site_results = search_official_site(domain, document_title, timeout)
            except requests.RequestException as exc:
                attempts.append(
                    {
                        "query": site_query,
                        "source": "official_site_search",
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )
                continue
            attempts.append(
                {
                    "query": site_query,
                    "source": "official_site_search",
                    "candidate_count": len(site_results),
                }
            )
            if accept_candidate(
                item,
                site_results[:max_results],
                document_titles,
                site_query,
                threshold,
                config,
                timeout,
            ):
                item.metadata["official_search_attempts"] = attempts
                return item

    item.metadata["official_search_found"] = False
    item.metadata["official_search_attempts"] = attempts
    item.metadata["official_search_note"] = "未找到标题足够相似的官方原文"
    return item


def looks_like_normative_document(item: NewsItem) -> bool:
    text = f"{item.title}\n{item.content}"
    return any(marker in text for marker in NORMATIVE_MARKERS)


def build_queries(item: NewsItem) -> List[str]:
    source_text = f"{item.title}\n{item.source}\n{item.content}"
    title = item.title.strip()
    if not title:
        return []

    document_titles = extract_document_titles(source_text)
    domains = extract_official_domains(source_text)
    queries: List[str] = []

    for document_title in document_titles[:3]:
        core_title = simplify_document_title(document_title)
        for domain in domains[:3]:
            queries.append(f'site:{domain} "{document_title}"')
            if core_title != document_title:
                queries.append(f'site:{domain} "{core_title}"')
        queries.append(f'site:gov.cn "{document_title}"')
        queries.append(f'site:org.cn "{document_title}"')
        queries.append(f'"{document_title}" 官方 原文')
        if core_title != document_title:
            queries.append(f'"{core_title}" 官方 原文')

    queries.extend(
        [
            f'site:gov.cn "{title}"',
            f'site:org.cn "{title}"',
            f'"{title}" 官方 原文',
        ]
    )
    return list(dict.fromkeys(queries))


def extract_document_titles(text: str) -> List[str]:
    titles = re.findall(r"《([^》]{6,160})》", text or "")
    cleaned = []
    for title in titles:
        title = re.sub(r"\s+", " ", title).strip()
        if title and title not in cleaned:
            cleaned.append(title)
    if not cleaned:
        first_line = (text or "").split("\n", 1)[0].strip()
        if first_line:
            cleaned.append(first_line)
    return cleaned


def simplify_document_title(title: str) -> str:
    """Remove procedural suffixes so a shorter official file name can match."""
    simplified = re.sub(
        r"[\(（](?:修订草案征求意见稿|草案征求意见稿|征求意见稿|修订草案|草案|试行|征求意见)[\)）]",
        "",
        title,
    )
    simplified = re.sub(r"\s+", " ", simplified).strip()
    return simplified or title


def extract_official_domains(text: str) -> List[str]:
    pattern = r"(?<![a-z0-9])([a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:gov\.cn|org\.cn|gov))(?![a-z0-9])"
    domains = []
    for domain in re.findall(pattern, (text or "").lower()):
        if domain not in domains:
            domains.append(domain)
    return domains


def search_web(query: str, config: Dict[str, Any], timeout: int) -> List[Tuple[str, str]]:
    configured = config.get("engines") or [config.get("engine", "edge_html"), "baidu_html", "ddg_html"]
    engines = [str(engine).lower() for engine in configured]
    all_results: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for engine in engines:
        try:
            if engine == "baidu_html":
                results = search_baidu(query, timeout)
            elif engine in {"edge_html", "bing_html"}:
                # Edge 默认搜索通常使用 Bing；这里直接请求 Bing HTML 结果页。
                results = search_bing(query, timeout)
            elif engine == "ddg_html":
                results = search_duckduckgo(query, timeout)
            else:
                continue
            for url, title in results:
                canonical = canonical_url(url)
                if canonical and canonical not in seen:
                    seen.add(canonical)
                    all_results.append((canonical, title))
        except requests.RequestException:
            continue
    return all_results


def search_baidu(query: str, timeout: int) -> List[Tuple[str, str]]:
    response = requests.get(
        "https://www.baidu.com/s",
        params={"wd": query},
        headers=SEARCH_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    results: List[Tuple[str, str]] = []
    for anchor in soup.select("h3 a[href]"):
        url = str(anchor.get("href", "")).strip()
        title = anchor.get_text(" ", strip=True)
        if not url or not title:
            continue
        if urlparse(url).hostname and "baidu.com" in (urlparse(url).hostname or ""):
            try:
                redirected = requests.get(
                    url,
                    headers=SEARCH_HEADERS,
                    timeout=timeout,
                    allow_redirects=True,
                )
                url = redirected.url
            except requests.RequestException:
                continue
        results.append((url, title))
    return results


def search_bing(query: str, timeout: int) -> List[Tuple[str, str]]:
    response = requests.get(
        "https://www.bing.com/search",
        params={"q": query, "count": 10},
        headers=SEARCH_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    results: List[Tuple[str, str]] = []
    for anchor in soup.select("li.b_algo h2 a[href]"):
        url = str(anchor.get("href", "")).strip()
        title = anchor.get_text(" ", strip=True)
        if url and title:
            results.append((url, title))
    return results


def search_duckduckgo(query: str, timeout: int) -> List[Tuple[str, str]]:
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers=SEARCH_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    results: List[Tuple[str, str]] = []
    for anchor in soup.select("a.result__a[href]"):
        url = str(anchor.get("href", "")).strip()
        title = anchor.get_text(" ", strip=True)
        parsed = urlparse(url)
        if parsed.hostname == "duckduckgo.com":
            url = parse_qs(parsed.query).get("uddg", [url])[0]
        if url and title:
            results.append((url, title))
    return results


def search_official_site(domain: str, query: str, timeout: int) -> List[Tuple[str, str]]:
    """Try common search forms and endpoints exposed by government websites."""
    base = f"https://{domain}/"
    try:
        response = requests.get(base, headers=SEARCH_HEADERS, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return search_official_site_browser(domain, query, timeout)
    soup = BeautifulSoup(response.text, "lxml")
    search_urls: List[str] = []

    for form in soup.select("form"):
        action = str(form.get("action", "")).strip()
        if not action:
            continue
        action_url = urlparse(urljoin(base, action))
        if action_url.scheme not in {"http", "https"}:
            continue
        field_name = ""
        for field in form.select("input[name], textarea[name]"):
            name = str(field.get("name", "")).strip()
            if any(
                token in name.lower()
                for token in ("keyword", "key", "query", "search", "title", "q", "kw")
            ):
                field_name = name
                break
        if field_name:
            search_urls.append(add_query_parameter(action_url.geturl(), field_name, query))

    for path, parameter in (
        ("/search", "keyword"),
        ("/search", "kw"),
        ("/search", "query"),
        ("/search/index.html", "keyword"),
        ("/search/index.html", "q"),
    ):
        search_urls.append(add_query_parameter(urljoin(base, path), parameter, query))

    results: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for search_url in dict.fromkeys(search_urls):
        try:
            page = requests.get(search_url, headers=SEARCH_HEADERS, timeout=timeout)
            page.raise_for_status()
        except requests.RequestException:
            continue
        page_soup = BeautifulSoup(page.text, "lxml")
        for anchor in page_soup.select("a[href]"):
            href = str(anchor.get("href", "")).strip()
            label = anchor.get_text(" ", strip=True)
            if not href or not label:
                continue
            candidate_url = canonical_url(urljoin(search_url, href))
            parsed = urlparse(candidate_url)
            if parsed.hostname != domain and not (parsed.hostname or "").endswith(f".{domain}"):
                continue
            if candidate_url in seen:
                continue
            seen.add(candidate_url)
            results.append((candidate_url, label))
    if not results:
        return search_official_site_browser(domain, query, timeout)
    return sorted(results, key=lambda pair: title_similarity(query, pair[1]), reverse=True)


def search_official_site_browser(domain: str, query: str, timeout: int) -> List[Tuple[str, str]]:
    """Use the installed Edge browser when a site blocks direct HTTP requests."""
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        return []

    base = f"https://{domain}/"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
            page = browser.new_page(
                user_agent=SEARCH_HEADERS["User-Agent"],
                viewport={"width": 1440, "height": 1000},
            )
            page.goto(base, wait_until="domcontentloaded", timeout=timeout * 1000)
            page.wait_for_timeout(1500)
            form_data = page.locator("form").evaluate_all(
                """forms => forms.map((form, index) => ({
                    index,
                    action: form.action || location.href,
                    method: (form.method || 'get').toLowerCase(),
                    input: Array.from(form.querySelectorAll('input[name], textarea[name]')).find(input =>
                        /keyword|key|query|search|title|\\bq\\b|kw/i.test(input.name)
                    )?.name || ''
                })).filter(item => item.input)"""
            )
            search_urls: List[str] = []
            for form in form_data:
                form_locator = page.locator("form").nth(int(form["index"]))
                field = form_locator.locator(f'[name="{form["input"]}"]').first
                try:
                    field.fill(query)
                    form_locator.evaluate("form => form.submit()")
                    page.wait_for_load_state("domcontentloaded", timeout=timeout * 1000)
                    page.wait_for_timeout(1000)
                    search_urls.append(page.url)
                    page.goto(base, wait_until="domcontentloaded", timeout=timeout * 1000)
                except (PlaywrightTimeoutError, Exception):
                    continue

            for path, parameter in (
                ("/search", "keyword"),
                ("/search", "kw"),
                ("/search", "query"),
                ("/search/index.html", "keyword"),
                ("/search/index.html", "q"),
            ):
                search_urls.append(add_query_parameter(urljoin(base, path), parameter, query))

            results: List[Tuple[str, str]] = []
            seen: set[str] = set()
            for search_url in dict.fromkeys(search_urls):
                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=timeout * 1000)
                    page.wait_for_timeout(1000)
                except PlaywrightTimeoutError:
                    continue
                soup = BeautifulSoup(page.content(), "lxml")
                for anchor in soup.select("a[href]"):
                    href = str(anchor.get("href", "")).strip()
                    label = anchor.get_text(" ", strip=True)
                    if not href or not label:
                        continue
                    candidate_url = canonical_url(urljoin(page.url, href))
                    parsed = urlparse(candidate_url)
                    if parsed.hostname != domain and not (parsed.hostname or "").endswith(f".{domain}"):
                        continue
                    if candidate_url in seen:
                        continue
                    seen.add(candidate_url)
                    results.append((candidate_url, label))
            browser.close()
            return sorted(results, key=lambda pair: title_similarity(query, pair[1]), reverse=True)
    except Exception:
        return []


def add_query_parameter(url: str, name: str, value: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params[name] = [value]
    return parsed._replace(query=urlencode(params, doseq=True)).geturl()


def accept_candidate(
    item: NewsItem,
    candidates: List[Tuple[str, str]],
    document_titles: List[str],
    query: str,
    threshold: float,
    config: Dict[str, Any],
    timeout: int,
) -> bool:
    for candidate_url, candidate_title in candidates:
        if candidate_url == item.link:
            continue
        is_official, reason = detect_official_source(
            candidate_url,
            config.get("official", {}).get("authority_tokens", []),
        )
        if not is_official:
            continue
        candidate = fetch_candidate(candidate_url, timeout)
        if candidate is None:
            continue
        title_score = max(
            title_similarity(item.title, candidate.title),
            title_similarity(item.title, candidate_title),
        )
        document_score = max(
            (
                document_evidence_score(document_title, candidate.title, candidate.content)
                for document_title in document_titles
            ),
            default=0.0,
        )
        score = max(title_score, document_score)
        if score < threshold and document_score < 0.9:
            continue
        item.metadata["original_news_link"] = item.link
        item.metadata["official_search_query"] = query
        item.metadata["official_search_score"] = round(score, 3)
        item.metadata["official_search_title_score"] = round(title_score, 3)
        item.metadata["official_search_document_score"] = round(document_score, 3)
        item.metadata["official_search_found"] = True
        item.metadata["official_source_reason"] = f"主动搜索：{reason}"
        item.official_link = candidate_url
        if candidate.content and len(candidate.content) >= 200:
            item.content = candidate.content
            item.metadata["official_content_loaded"] = True
        if candidate.pub_date and not item.pub_date:
            item.pub_date = candidate.pub_date
        return True
    return False


def document_evidence_score(document_title: str, candidate_title: str, candidate_content: str) -> float:
    core_title = simplify_document_title(document_title)
    normalized_core = normalize_text(core_title)
    normalized_title = normalize_text(candidate_title)
    normalized_content = normalize_text(candidate_content)
    if not normalized_core:
        return 0.0
    if normalized_core in normalized_title:
        return 0.98
    if normalized_core in normalized_content:
        return 0.82
    return title_similarity(core_title, candidate_title)


def fetch_candidate(url: str, timeout: int) -> NewsItem | None:
    from .fetch_article import fetch_items

    candidate = fetch_items([NewsItem(link=url)], timeout=timeout)[0]
    if candidate.fetch_status != "ok" or not candidate.content:
        return None
    return candidate


def canonical_url(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return parsed._replace(fragment="").geturl()


def title_similarity(left: str, right: str) -> float:
    left_normalized = normalize_text(left)
    right_normalized = normalize_text(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized in right_normalized or right_normalized in left_normalized:
        return 0.95
    sequence_score = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    left_chars = set(left_normalized)
    right_chars = set(right_normalized)
    overlap_score = len(left_chars & right_chars) / max(1, len(left_chars))
    return max(sequence_score, overlap_score)


def normalize_text(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", value or "").lower()
