from __future__ import annotations

from datetime import date
from typing import Iterable, List, Sequence

from .models import NewsItem

DOMESTIC_MARKERS = ["中国", "我国", "全国", "国务院", "最高人民法院", "最高人民检察院", "国家", "北京", "上海", "深圳", "广东"]
FOREIGN_MARKERS = ["美国", "欧盟", "英国", "日本", "韩国", "新加坡", "德国", "法国", "澳大利亚", "加拿大", "国际"]

LEGAL_LEVEL_ORDER = {
    "宪法": 0,
    "法律": 1,
    "行政法规": 2,
    "地方性法规": 3,
    "部门规章/地方政府规章": 4,
    "规范性文件": 5,
    "国内其他事件": 6,
    "其他事件": 6,
    "国际公约": 7,
    "外国法律": 8,
    "国外其他事件": 9,
}

FOREIGN_LEVEL_ORDER = {
    "国际公约": 0,
    "外国法律": 1,
    "国外其他事件": 2,
    "其他事件": 2,
}


def apply_rule_classification(items: Iterable[NewsItem], keywords: Sequence[str]) -> List[NewsItem]:
    result: List[NewsItem] = []
    for item in items:
        text = f"{item.title}\n{item.content}\n{item.source}\n{item.link}"
        matched = [keyword for keyword in keywords if keyword and keyword in text]
        if not item.topic and matched:
            item.topic = "、".join(matched[:3])
        if not item.jurisdiction:
            item.jurisdiction = guess_jurisdiction(text)
        if not item.legal_level:
            item.legal_level = guess_legal_level(text, item.jurisdiction)
        if not item.summary:
            item.summary = "[待生成摘要]"
        item.is_legal_news = item.legal_level not in {"国内其他事件", "国外其他事件", "其他事件"}
        item.include = True
        if item.fetch_status.startswith("failed"):
            item.reason = "网页抓取失败，已保留供人工复核"
        elif not matched and not item.reason:
            item.reason = "未做关键词筛选，已保留供人工复核"
        result.append(item)
    return result


def filter_by_week(items: Iterable[NewsItem], week_start: date, week_end: date) -> List[NewsItem]:
    result: List[NewsItem] = []
    for item in items:
        if not item.pub_date:
            result.append(item)
            continue
        try:
            parsed = date.fromisoformat(item.pub_date[:10])
        except ValueError:
            result.append(item)
            continue
        if week_start <= parsed <= week_end:
            result.append(item)
    return result


def sort_items(items: Iterable[NewsItem]) -> List[NewsItem]:
    def key(item: NewsItem) -> tuple:
        level = item.legal_level
        if level == "其他事件":
            level = "国外其他事件" if item.jurisdiction == "国外" else "国内其他事件"
        level_rank = LEGAL_LEVEL_ORDER.get(level, 99)
        date_rank = item.pub_date or "9999-12-31"
        return (level_rank, date_rank, item.title)

    return sorted([item for item in items if item.include], key=key)


def guess_jurisdiction(text: str) -> str:
    if any(marker in text for marker in FOREIGN_MARKERS):
        return "国外"
    if any(marker in text for marker in DOMESTIC_MARKERS):
        return "国内"
    return "国内"


def guess_legal_level(text: str, jurisdiction: str) -> str:
    if jurisdiction == "国外":
        if "公约" in text or "协定" in text or "条约" in text:
            return "国际公约"
        if any(word in text for word in ("法案", "法律", "条例", "规则", "监管规定")):
            return "外国法律"
        return "国外其他事件"
    if "宪法" in text:
        return "宪法"
    if any(word in text for word in ("法草案", "法修订", "法施行", "法正式", "法通过", "中华人民共和国")):
        return "法律"
    if "条例" in text or "国务院令" in text:
        return "行政法规"
    if "地方性法规" in text:
        return "地方性法规"
    if any(word in text for word in ("办法", "规定", "规章")):
        return "部门规章/地方政府规章"
    if any(word in text for word in ("意见", "通知", "指引", "指南", "公告", "决定", "标准")):
        return "规范性文件"
    return "国内其他事件"



