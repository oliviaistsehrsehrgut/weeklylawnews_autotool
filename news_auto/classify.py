from __future__ import annotations

from datetime import date
from typing import Iterable, List, Sequence

from .models import NewsItem

DOMESTIC_MARKERS = ["中国", "我国", "全国", "国务院", "最高人民法院", "最高人民检察院", "国家", "北京", "上海", "深圳", "广东"]
FOREIGN_MARKERS = ["美国", "欧盟", "英国", "日本", "韩国", "新加坡", "德国", "法国", "澳大利亚", "加拿大", "国际"]

# Central-level (中央部委) agencies — items from these rank before 地方 items in auto-sort
CENTRAL_AGENCY_MARKERS = [
    # Cyber / Data / AI
    "网信办", "中央网信办", "国家互联网信息办公室",
    "国家数据局",
    # Telecom / Industry
    "工信部", "工业和信息化部",
    # Security / Police
    "公安部", "国家安全部",
    # Market / Standards
    "市场监管总局", "国家市场监督管理总局",
    "国家标准化管理委员会", "国家标准委",
    # Finance
    "人民银行", "中国人民银行",
    "证监会", "中国证券监督管理委员会",
    "金融监管总局", "国家金融监督管理总局",
    "银保监会",
    # Drugs / Medical
    "药监局", "国家药品监督管理局",
    "国家卫健委", "国家卫生健康委",
    # Trade / Customs
    "商务部", "海关总署",
    # IP / Copyright
    "国家知识产权局", "国家版权局",
    # Broadcast
    "广电总局", "国家广播电视总局",
    # Labor
    "人社部", "人力资源和社会保障部",
    # Development / Science
    "发改委", "国家发展和改革委员会",
    "科技部",
    # Top-level
    "国务院",
    "全国人大", "全国人民代表大会",
    "最高人民法院", "最高人民检察院",
]

# Sort order for legal levels (lower number = higher output priority in auto-sort)
LEGAL_LEVEL_ORDER = {
    # High-level legislation (rarely changes; appears first when present)
    "宪法": 0,
    "法律": 1,
    "行政法规": 2,
    # Main user-defined categories: 部门规章 → ... → 地方文件
    "部门规章": 3,
    "规范性文件": 4,
    "国家标准": 5,
    "行业标准": 6,
    "技术指南": 7,
    "征求意见稿": 8,
    "工作动态": 9,
    "地方文件": 10,
    # Legacy mappings for stored sessions
    "地方性法规": 10,
    "部门规章/地方政府规章": 3,
    "国内其他事件": 9,
    "其他事件": 9,
    # International (always sorted after domestic)
    "国际公约": 20,
    "外国法律": 21,
    "国外其他事件": 22,
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
        item.is_legal_news = item.legal_level not in {"国内其他事件", "国外其他事件", "其他事件", "工作动态"}
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


def _authority_rank(item: NewsItem) -> int:
    """0 = central ministry (中央部委), 1 = local/regional (地方), 2 = international (国外)."""
    if item.jurisdiction == "国外":
        return 2
    text = f"{item.title} {item.source}"
    if any(marker in text for marker in CENTRAL_AGENCY_MARKERS):
        return 0
    return 1


def sort_items(items: Iterable[NewsItem]) -> List[NewsItem]:
    def key(item: NewsItem) -> tuple:
        level = item.legal_level or ""
        if level == "其他事件":
            level = "国外其他事件" if item.jurisdiction == "国外" else "国内其他事件"
        level_rank = LEGAL_LEVEL_ORDER.get(level, 99)
        date_rank = item.pub_date or "9999-12-31"
        return (_authority_rank(item), level_rank, date_rank, item.title)

    return sorted([item for item in items if item.include], key=key)


def guess_jurisdiction(text: str) -> str:
    if any(marker in text for marker in FOREIGN_MARKERS):
        return "国外"
    if any(marker in text for marker in DOMESTIC_MARKERS):
        return "国内"
    return "国内"


def guess_legal_level(text: str, jurisdiction: str) -> str:
    if jurisdiction == "国外":
        if any(word in text for word in ("公约", "协定", "条约")):
            return "国际公约"
        if any(word in text for word in ("法案", "法律", "条例", "规则", "监管规定")):
            return "外国法律"
        return "国外其他事件"
    # Domestic: full legislation (highest authority)
    if "宪法" in text:
        return "宪法"
    if any(word in text for word in ("法草案", "法修订", "法施行", "法正式", "法通过", "中华人民共和国")):
        return "法律"
    if "条例" in text and ("国务院" in text or "行政法规" in text):
        return "行政法规"
    # Draft for comment overrides the document type
    if "征求意见" in text:
        return "征求意见稿"
    # Standards
    if any(word in text for word in ("GB/T", "GB ", "国家标准", "国标")):
        return "国家标准"
    if any(word in text for word in ("行业标准", "YD/T", "YD ", "QB/T", "团标")):
        return "行业标准"
    # Technical guidance
    if any(word in text for word in ("技术指南", "技术要求", "技术规范")):
        return "技术指南"
    # Local government documents (check before 部门规章 to avoid misclassifying local "办法")
    if any(word in text for word in ("省人民政府", "市人民政府", "自治区人民政府", "地方政府", "地方性法规")):
        return "地方文件"
    # Formal departmental regulations / rules
    if any(word in text for word in ("办法", "规定", "规章")):
        return "部门规章"
    # Normative documents
    if any(word in text for word in ("意见", "通知", "指引", "公告", "决定", "函", "规划")):
        return "规范性文件"
    return "工作动态"
