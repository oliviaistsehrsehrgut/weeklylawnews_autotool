from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - Python 3.9/3.10
    import tomli as tomllib


DEFAULT_AUTHORITY_TOKENS = [
    "miit", "mofcom", "mof", "ndrc", "cac", "samr", "mep", "mee", "mps",
    "moj", "nhc", "mohurd", "nmpa", "customs", "chinacourt", "court", "spc",
    "spp", "csrc", "pbc", "nfra", "sasac", "tc260", "caict", "cnca", "nca",
]

DEFAULT_CONFIG: Dict[str, Any] = {
    "paths": {
        "output_dir": "output",
        "debug_dir": ".debug",
        "debug_keep_count": 20,
        "word_template": "templates/法讯草稿模板.docx",
        "wechat_template": "templates/公众号编辑器模板.html",
        "wechat_profile_dir": ".wechat-browser",
    },
    "llm": {
        "enabled": True,
        "base_url": "",
        "api_key": "",
        "api_key_env": "",
        "model": "",
        "timeout_seconds": 90,
        "max_content_chars": 12000,
        "temperature": 0.2,
        "json_mode": False,
        "retries": 2,
    },
    "filters": {
        "keywords": [
            "网络安全", "数据合规", "个人信息", "数据保护", "人工智能", "低空经济",
            "电信", "信息通信", "通信管理", "互联网基础资源", "网信办", "国家数据局",
            "贸易合规", "出口管制", "公司治理", "广告", "医疗", "劳动",
        ]
    },
    "official": {
        "authority_tokens": DEFAULT_AUTHORITY_TOKENS,
        "non_official_warning": "【可能非官方网站，待核实修改】",
    },
    "official_search": {
        "enabled": False,
        "engines": ["edge_html", "baidu_html", "ddg_html"],
        "max_results": 5,
        "max_queries": 12,
        "timeout_seconds": 20,
        "title_similarity_threshold": 0.48,
    },
    "wk": {
        "list_url": "https://law.wkinfo.com.cn/news/list",
        "enabled": False,
        "cookie": "",
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return DEFAULT_CONFIG
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return deep_merge(DEFAULT_CONFIG, data)