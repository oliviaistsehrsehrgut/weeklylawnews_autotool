from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict
from urllib.parse import unquote
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from .classify import apply_rule_classification, sort_items
from .config import load_config
from .fetch_article import fetch_items
from .ingest_text import dedupe_items, items_from_text
from .llm import enrich_with_llm, llm_enabled, validate_api_key
from .models import NewsItem
from .official_source import detect_official_source
from .output_naming import as_date, next_word_path
from .parse_reviewed_docx import parse_reviewed_docx_bytes
from .render_docx import render_word_draft
from .render_wechat import render_wechat_html
from .web_store import SessionStore

ROOT = Path(__file__).resolve().parent.parent
CONFIG = load_config(ROOT / "config.toml")
STORE = SessionStore(ROOT / "work" / ".sessions")
SESSION_LLM_CONFIGS: dict[str, Dict[str, Any]] = {}
app = FastAPI(title="News Automation Workbench")


class LlmConfigRequest(BaseModel):
    base_url: str = ""
    model: str = ""
    api_key: str = Field(default="", max_length=500)


class CreateRequest(BaseModel):
    input_text: str = Field(min_length=1)
    week_start: str = ""
    week_end: str = ""
    llm_config: LlmConfigRequest | None = None


class UpdateRequest(BaseModel):
    items: list[Dict[str, Any]]


class RefreshRequest(BaseModel):
    item: Dict[str, Any]
    mode: str


def view_of(
    item: NewsItem,
    original_link: str = "",
    config: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    active_config = config or CONFIG
    link = item.official_link or item.link
    error = item.metadata.get("llm_error", "")
    if not error and item.fetch_status.startswith("failed"):
        error = item.metadata.get("fetch_error", "")
    official, reason = detect_official_source(
        link,
        active_config.get("official", {}).get("authority_tokens", []),
    )
    return {
        "id": item.metadata.get("web_id") or uuid4().hex,
        "original_link": original_link or item.metadata.get("original_link") or item.link,
        "final_link": link,
        "title": item.title,
        "summary": item.summary,
        "full_text": item.content,
        "source": item.source,
        "pub_date": item.pub_date,
        "topic": item.topic,
        "jurisdiction": item.jurisdiction,
        "legal_level": item.legal_level,
        "official_status": official,
        "official_reason": reason,
        "fetch_status": item.fetch_status,
        "reason": item.reason,
        "error": error,
    }


def item_from_view(data: Dict[str, Any]) -> NewsItem:
    item = NewsItem(
        title=str(data.get("title", "")), link=str(data.get("final_link", "")),
        source=str(data.get("source", "")), pub_date=data.get("pub_date"),
        content=str(data.get("full_text", "")), summary=str(data.get("summary", "")),
        topic=str(data.get("topic", "")), jurisdiction=str(data.get("jurisdiction", "")),
        legal_level=str(data.get("legal_level", "")), fetch_status=str(data.get("fetch_status", "pending")),
        official_link=str(data.get("final_link", "")),
    )
    item.metadata["web_id"] = str(data.get("id", uuid4().hex))
    item.metadata["original_link"] = str(data.get("original_link", ""))
    return item


def process_items(
    items: list[NewsItem],
    fetch: bool = True,
    config: Dict[str, Any] | None = None,
) -> list[Dict[str, Any]]:
    active_config = config or CONFIG
    if fetch:
        items = fetch_items(
            items,
            authority_tokens=active_config.get("official", {}).get("authority_tokens", []),
        )
    items = apply_rule_classification(
        items,
        active_config.get("filters", {}).get("keywords", []),
    )
    if llm_enabled(active_config):
        items = enrich_with_llm(items, active_config)
    return [
        view_of(item, item.metadata.get("original_link", ""), config=active_config)
        for item in sort_items(items)
    ]


def auto_sort_items(items: list[NewsItem], config: Dict[str, Any]) -> list[NewsItem]:
    working = apply_rule_classification(
        deepcopy(items),
        config.get("filters", {}).get("keywords", []),
    )
    if llm_enabled(config):
        working = enrich_with_llm(working, config)

    classified_by_id = {
        item.metadata.get("web_id"): item
        for item in working
        if item.metadata.get("web_id")
    }
    ordered = deepcopy(items)
    for item in ordered:
        candidate = classified_by_id.get(item.metadata.get("web_id"))
        if candidate:
            item.topic = candidate.topic or item.topic
            item.jurisdiction = candidate.jurisdiction or item.jurisdiction
            item.legal_level = candidate.legal_level or item.legal_level
            item.is_legal_news = candidate.is_legal_news
            item.reason = candidate.reason or item.reason
        item.include = True
    return sort_items(ordered)


def build_runtime_config(request: LlmConfigRequest | None) -> Dict[str, Any]:
    if request is None:
        return CONFIG

    base_url = request.base_url.strip().rstrip("/")
    model = request.model.strip()
    api_key = request.api_key.strip()
    if not base_url and not model and not api_key:
        return CONFIG
    if not base_url or not model or not api_key:
        raise HTTPException(
            status_code=400,
            detail="API Base URL、模型名称和 API Key 必须同时填写",
        )
    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="API Base URL 必须以 http:// 或 https:// 开头",
        )
    validate_api_key(api_key)

    runtime = deepcopy(CONFIG)
    runtime["llm"].update(
        {
            "enabled": True,
            "base_url": base_url,
            "model": model,
            "api_key": api_key,
            "api_key_env": "",
        }
    )
    return runtime


@app.get("/api/status")
def get_status() -> Dict[str, Any]:
    llm = CONFIG.get("llm", {})
    return {
        "llm_enabled": llm_enabled(CONFIG),
        "llm_model": str(llm.get("model", "")),
        "llm_base_url": str(llm.get("base_url", "")),
        "llm_compatibility": "OpenAI-compatible /chat/completions",
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (ROOT / "templates" / "web_index.html").read_text(encoding="utf-8")


@app.get("/static/{path:path}")
def static_file(path: str) -> FileResponse:
    static_root = (ROOT / "static").resolve()
    file_path = (static_root / path).resolve()
    if static_root not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Session or resource not found")
    return FileResponse(file_path, headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/api/templates/word")
def download_word_template() -> FileResponse:
    template_path = ROOT / CONFIG["paths"].get(
        "word_template", "templates/法讯草稿模板.docx"
    )
    if not template_path.is_file():
        raise HTTPException(status_code=404, detail="Word template not found")
    return FileResponse(
        template_path,
        filename=template_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/templates/html")
def download_html_template() -> FileResponse:
    template_path = ROOT / CONFIG["paths"].get(
        "wechat_template", "templates/公众号编辑器模板.html"
    )
    if not template_path.is_file():
        raise HTTPException(status_code=404, detail="HTML template not found")
    return FileResponse(template_path, filename=template_path.name, media_type="text/html")


@app.post("/api/word/parse")
async def parse_word_upload(
    request: Request,
    week_start: str = "",
    week_end: str = "",
) -> Dict[str, Any]:
    filename = unquote(request.headers.get("x-filename", ""))
    if filename and not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="请上传 .docx Word 文件")
    data = await request.body()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Word 文件不能超过 20 MB")
    try:
        items = parse_reviewed_docx_bytes(data)
    except Exception:
        raise HTTPException(status_code=400, detail="无法解析该 Word 文件，请使用 .docx 格式")
    if not items:
        raise HTTPException(
            status_code=422,
            detail="未识别到新闻条目，请确认 Word 中包含编号标题、摘要和原文链接",
        )

    for item in items:
        item.metadata["original_link"] = item.link
        item.metadata["web_id"] = uuid4().hex
    items = apply_rule_classification(
        items,
        CONFIG.get("filters", {}).get("keywords", []),
    )
    views = [
        view_of(item, item.metadata.get("original_link", ""), config=CONFIG)
        for item in items
    ]
    session_id = uuid4().hex
    payload = {
        "session_id": session_id,
        "week_start": week_start or date.today().isoformat(),
        "week_end": week_end or (date.today() + timedelta(days=6)).isoformat(),
        "items": views,
    }
    STORE.save(session_id, payload)
    normalized_text = "\n\n".join(
        f"{item.title}\n摘要：{item.summary}\n原文链接：{item.link}" for item in items
    )
    return {"session_id": session_id, "items": views, "text": normalized_text}


@app.post("/api/sessions")
def create_session(request: CreateRequest) -> Dict[str, Any]:
    runtime_config = build_runtime_config(request.llm_config)
    items = dedupe_items(items_from_text(request.input_text))
    if not items:
        raise HTTPException(status_code=400, detail="Invalid request")
    for item in items:
        item.metadata["original_link"] = item.link
        item.metadata["web_id"] = uuid4().hex
    session_id = uuid4().hex
    views = process_items(items, config=runtime_config)
    STORE.save(session_id, {
        "session_id": session_id,
        "week_start": request.week_start or date.today().isoformat(),
        "week_end": request.week_end or (date.today() + timedelta(days=6)).isoformat(),
        "items": views,
    })
    if request.llm_config and request.llm_config.api_key.strip():
        SESSION_LLM_CONFIGS[session_id] = runtime_config
    return {"session_id": session_id, "items": views}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str) -> Dict[str, Any]:
    try:
        return STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")


@app.patch("/api/sessions/{session_id}")
def update_session(session_id: str, request: UpdateRequest) -> Dict[str, Any]:
    try:
        payload = STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")
    for item in request.items:
        official, reason = detect_official_source(
            str(item.get("final_link", "")),
            CONFIG.get("official", {}).get("authority_tokens", []),
        )
        item["official_status"] = official
        item["official_reason"] = reason
    payload["items"] = request.items
    STORE.save(session_id, payload)
    return payload


@app.post("/api/sessions/{session_id}/llm-config")
def set_session_llm_config(session_id: str, request: LlmConfigRequest) -> Dict[str, Any]:
    try:
        STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")
    runtime_config = build_runtime_config(request)
    if runtime_config is CONFIG:
        SESSION_LLM_CONFIGS.pop(session_id, None)
        return {"llm_enabled": llm_enabled(CONFIG)}
    SESSION_LLM_CONFIGS[session_id] = runtime_config
    return {"llm_enabled": llm_enabled(runtime_config)}


@app.delete("/api/sessions/{session_id}/llm-config")
def clear_session_llm_config(session_id: str) -> Dict[str, Any]:
    try:
        STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")
    SESSION_LLM_CONFIGS.pop(session_id, None)
    return {"llm_enabled": llm_enabled(CONFIG)}


@app.post("/api/sessions/{session_id}/auto-sort")
def auto_sort_session(session_id: str) -> Dict[str, Any]:
    try:
        payload = STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")
    runtime_config = SESSION_LLM_CONFIGS.get(session_id, CONFIG)
    items = [item_from_view(row) for row in payload.get("items", [])]
    sorted_items = auto_sort_items(items, runtime_config)
    views = [
        view_of(item, item.metadata.get("original_link", ""), config=runtime_config)
        for item in sorted_items
    ]
    payload["items"] = views
    STORE.save(session_id, payload)
    return {"items": views, "llm_used": llm_enabled(runtime_config)}


@app.post("/api/sessions/{session_id}/refresh")
def refresh_item(session_id: str, request: RefreshRequest) -> Dict[str, Any]:
    if request.mode not in {"link", "full"}:
        raise HTTPException(status_code=400, detail="Invalid request")
    try:
        payload = STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")
    runtime_config = SESSION_LLM_CONFIGS.get(session_id, CONFIG)
    if not llm_enabled(runtime_config):
        raise HTTPException(
            status_code=503,
            detail="当前会话未配置可用的 OpenAI-compatible API，请先在 API 配置弹窗中填写 URL、模型和 Key",
        )
    current = request.item
    if request.mode == "full" and not str(current.get("full_text", "")).strip():
        raise HTTPException(status_code=400, detail="Full text is required")
    item_id = str(current.get("id", ""))
    source_item = item_from_view(current)
    source_item.summary = ""
    if request.mode == "link":
        source_item.content = ""
    result_list = process_items(
        [source_item],
        fetch=request.mode == "link",
        config=runtime_config,
    )
    if not result_list:
        raise HTTPException(status_code=422, detail="Item cannot be refreshed")
    result = result_list[0]
    summary = str(result.get("summary", "")).strip()
    if result.get("error"):
        raise HTTPException(status_code=502, detail=f"摘要生成失败：{result['error']}")
    if not summary or summary.startswith("["):
        raise HTTPException(status_code=502, detail="摘要生成失败：模型没有返回可用摘要")
    result["id"] = item_id
    result["original_link"] = current.get("original_link", "")
    payload["items"] = [result if str(row.get("id")) == item_id else row for row in payload["items"]]
    STORE.save(session_id, payload)
    return {"item": result}


@app.post("/api/sessions/{session_id}/word")
def create_word(session_id: str) -> FileResponse:
    try:
        payload = STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")
    items = [item_from_view(row) for row in payload.get("items", [])]
    output_dir = ROOT / CONFIG["paths"].get("output_dir", "output")
    start = payload.get("week_start") or date.today().isoformat()
    end = payload.get("week_end") or start
    try:
        output_path = next_word_path(output_dir, end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid week end date")
    try:
        render_word_draft(items, ROOT / CONFIG["paths"]["word_template"], output_path,
                          authority_tokens=CONFIG.get("official", {}).get("authority_tokens", []),
                          non_official_warning="[NON_OFFICIAL_SOURCE_CHECK_REQUIRED]")
    except PermissionError:
        raise HTTPException(status_code=409, detail="Word file is locked")
    return FileResponse(output_path, filename=output_path.name, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.post("/api/sessions/{session_id}/html")
def create_html(session_id: str) -> FileResponse:
    try:
        payload = STORE.load(session_id)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Session or resource not found")
    items = [item_from_view(row) for row in payload.get("items", [])]
    output_dir = ROOT / CONFIG["paths"].get("output_dir", "output")
    end = payload.get("week_end") or date.today().isoformat()
    try:
        end_date = as_date(end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid week end date")
    output_path = output_dir / f"{end_date:%m%d}\u6cd5\u8baf_{session_id[:8]}.html"
    render_wechat_html(
        items,
        ROOT / CONFIG["paths"].get(
            "wechat_template", "templates/公众号编辑器模板.html"
        ),
        output_path,
    )
    return FileResponse(output_path, filename=output_path.name, media_type="text/html")
