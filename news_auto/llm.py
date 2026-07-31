from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, List

import requests

from .models import NewsItem
from .official_source import detect_official_source


SYSTEM_PROMPT = """你是法律新闻事实摘编助手，负责把公开网页原文整理成法讯初稿。
请基于标题、来源、日期和正文整体判断，不要只根据关键词判断相关性。

总原则：新闻稿只展示事实，不展示观点、情绪、宣传性表达或编辑解释。事实、观点、情感必须分开；输出字段中除reason外不得写观点、评价、推测或情感。

标题规则：
1. title 是小标题，应与原文章标题含义接近，只做事件概述。
2. 不得使用文学性修辞、宣传性词语、评价性词语或夸张表达。
3. 优先采用“主体 + 发布/印发/征求意见 + 文件名称”的结构。
4. 不写文号、发文字号。

摘要规则：
1. summary 只写原文明确出现的新闻事实，核心要素包括：主体、时间、文件/事件名称、发布/印发/征求意见等动作、核心内容摘要（如有）、反馈截止日期（如有）、适用对象（如有）。
2. 核心内容提炼（最重要）：如果原文（含通知正文、附件描述、新闻通稿）有实质性内容（如主要规定、核心条款、重点任务、制度要点等），必须提炼并嵌入摘要，不能只写“就某文件公开征求意见”这类空话。
原文没有具体内容时，不要补写目的、意义、影响、背景或评价；只写网页已经披露的事实。
3. 摘要必须包含以下任一内容，优先级从高到低：①优先：文件正文中的实质性规定（如“提出……要求”“明确……责任”“规定……标准”）②次之：如正文不可获取，复制新闻稿中的提炼内容③再次：原文对文件目的的说明④最低：确实无任何实质内容时，只写“就某文件公开征求意见，反馈截止至某日
不得写“意在、意味着、体现、公开页面仅包含、未披露、无法判断、需人工复核”等描述性或推测性表述，特别是针对新闻事件以外（例如对你抓取到的文本中“没有包含正文”这类描述），除非这些词是文件名称的一部分。
4. 不得写邮箱地址、文号、发文字号。
5. 摘要控制在80-150字，句式平实，语言精炼，逻辑严谨，不写评论。

分类规则：
1. 判断是否属于本法讯关注的法律、监管或合规新闻，重点关注网络安全、数据合规、个人信息、人工智能、低空经济、电信、贸易合规、出口管制、公司治理、广告、医疗、劳动等领域，但不能机械依赖关键词。
2. reason 可以写筛选理由和需要人工复核的原因；summary 中不要写人工复核提示。
3. 只输出一个 JSON 对象，不要输出 Markdown、代码围栏或解释文字。"""


LEGAL_LEVELS = {
    "宪法",
    "法律",
    "行政法规",
    "地方性法规",
    "部门规章/地方政府规章",
    "规范性文件",
    "国内其他事件",
    "国际公约",
    "外国法律",
    "国外其他事件",
}


def resolve_api_key(llm: Dict[str, Any]) -> str:
    env_name = str(llm.get("api_key_env", "")).strip()
    if env_name:
        return os.environ.get(env_name, "").strip()
    configured = str(llm.get("api_key", "")).strip()
    if configured.startswith("${") and configured.endswith("}"):
        return os.environ.get(configured[2:-1], "").strip()
    return configured


def llm_enabled(config: Dict[str, Any]) -> bool:
    llm = config.get("llm", {})
    if llm.get("enabled") is False:
        return False
    return bool(llm.get("base_url") and resolve_api_key(llm) and llm.get("model"))


def enrich_with_llm(items: Iterable[NewsItem], config: Dict[str, Any]) -> List[NewsItem]:
    if not llm_enabled(config):
        return list(items)
    result: List[NewsItem] = []
    for item in items:
        try:
            result.append(enrich_one(item, config))
        except Exception as exc:  # noqa: BLE001 - batch jobs should keep going
            item.metadata["llm_error"] = f"{exc.__class__.__name__}: {exc}"
            if not item.summary or item.summary == "[待生成摘要]":
                item.summary = "[LLM生成失败，待人工补充摘要]"
            if not item.reason:
                item.reason = "LLM处理失败，已保留供人工复核"
            result.append(item)
    return result


def enrich_one(item: NewsItem, config: Dict[str, Any]) -> NewsItem:
    if not item.content.strip():
        item.include = True
        item.summary = "[网页正文未能抓取，待人工补充摘要]"
        item.reason = "正文为空，无法由 LLM 可靠判断"
        return item

    llm = config["llm"]
    endpoint = completion_endpoint(str(llm["base_url"]))
    api_key = resolve_api_key(llm)
    validate_api_key(api_key)
    content_limit = int(llm.get("max_content_chars", 12000))
    payload: Dict[str, Any] = {
        "model": llm["model"],
        "temperature": float(llm.get("temperature", 0.2)),
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "title": item.title,
                        "source": item.source,
                        "pub_date": item.pub_date,
                        "link": item.link,
                        "content": item.content[:content_limit],
                        "output_schema": {
                            "include": "boolean",
                            "title": "用于法讯的中文标题",
                            "summary": "80-150字中文事实摘要；以原文明确事实为依据，区分事实、观点和情感，不把编辑判断写入摘要",
                            "topic": "主题标签，多个主题用顿号分隔",
                            "jurisdiction": "国内或国外",
                            "legal_level": "宪法/法律/行政法规/地方性法规/部门规章/地方政府规章/规范性文件/国内其他事件/国际公约/外国法律/国外其他事件",
                            "is_legal_news": "boolean",
                            "official_link": "官方原文链接，如无法确认则为空字符串",
                            "reason": "筛选或分类理由，简短且基于原文",
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    if llm.get("json_mode", False):
        payload["response_format"] = {"type": "json_object"}

    response = post_with_retries(
        endpoint,
        payload,
        api_key=api_key,
        timeout=int(llm.get("timeout_seconds", 90)),
        retries=int(llm.get("retries", 2)),
    )
    data = response.json()
    raw = data["choices"][0]["message"]["content"]
    if isinstance(raw, list):
        raw = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in raw)
    parsed = parse_json_object(str(raw))

    item.include = to_bool(parsed.get("include"), item.include)
    item.title = text_value(parsed.get("title"), item.title)
    item.summary = text_value(parsed.get("summary"), item.summary)
    item.topic = text_value(parsed.get("topic"), item.topic)
    item.jurisdiction = text_value(parsed.get("jurisdiction"), item.jurisdiction)
    item.legal_level = normalize_legal_level(
        parsed.get("legal_level"),
        item.legal_level,
        item.jurisdiction,
    )
    item.is_legal_news = to_bool(parsed.get("is_legal_news"), item.is_legal_news)
    official_link = text_value(parsed.get("official_link"), "")
    if official_link.startswith(("http://", "https://")):
        authority_tokens = config.get("official", {}).get("authority_tokens", [])
        is_official, reason = detect_official_source(official_link, authority_tokens)
        if is_official:
            item.official_link = official_link
            item.metadata["official_link_source_reason"] = reason
    item.reason = text_value(parsed.get("reason"), item.reason)
    item.metadata["llm_raw"] = parsed
    item.metadata.pop("llm_error", None)
    return item


def validate_api_key(api_key: str) -> None:
    if any(ord(char) > 127 for char in api_key):
        raise ValueError("API Key 含有非 ASCII 字符，请重新复制纯文本 API Key")
    if any(char.isspace() for char in api_key):
        raise ValueError("API Key 含有空格或换行，请重新复制纯文本 API Key")


def completion_endpoint(base_url: str) -> str:
    endpoint = base_url.strip().rstrip("/")
    suffix = "/chat/completions"
    return endpoint if endpoint.endswith(suffix) else f"{endpoint}{suffix}"


def post_with_retries(
    endpoint: str,
    payload: Dict[str, Any],
    *,
    api_key: str,
    timeout: int,
    retries: int,
) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(max(0, retries) + 1):
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            return response
        except requests.HTTPError as exc:
            response = exc.response
            detail = response.text.strip()[:500] if response is not None else str(exc)
            status = response.status_code if response is not None else "unknown"
            last_error = RuntimeError(f"LLM请求失败：HTTP {status} {detail}")
            if attempt < retries:
                time.sleep(min(2**attempt, 4))
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2**attempt, 4))
    raise RuntimeError(f"LLM请求失败：{last_error}") from last_error


def parse_json_object(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```").removeprefix("json").strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("LLM response does not contain JSON object")
    parsed = json.loads(raw[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON is not an object")
    return parsed


def text_value(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def to_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "是", "相关"}:
            return True
        if normalized in {"false", "no", "0", "否", "不相关"}:
            return False
    return fallback


def normalize_legal_level(value: Any, fallback: str, jurisdiction: str = "") -> str:
    candidate = text_value(value, fallback)
    if candidate == "其他事件":
        return "国外其他事件" if jurisdiction == "国外" else "国内其他事件"
    return candidate if candidate in LEGAL_LEVELS else fallback





