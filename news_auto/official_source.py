from __future__ import annotations

import re
from typing import Iterable, Tuple
from urllib.parse import urlparse


DEFAULT_AUTHORITY_TOKENS = (
    "miit",
    "mofcom",
    "mof",
    "ndrc",
    "cac",
    "samr",
    "mep",
    "mee",
    "mps",
    "moj",
    "nhc",
    "mohurd",
    "nmpa",
    "customs",
    "chinacourt",
    "court",
    "spc",
    "spp",
    "csrc",
    "pbc",
    "nfra",
    "sasac",
    "tc260",
    "caict",
    "cnca",
    "nca",
)


def detect_official_source(url: str, authority_tokens: Iterable[str] = ()) -> Tuple[bool, str]:
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        return False, "无有效域名"

    if host == "gov.cn" or host.endswith(".gov.cn") or host.endswith(".gov"):
        return True, "域名属于 gov/gov.cn 官方域名"

    normalized_host = re.sub(r"[^a-z0-9]", "", host)
    tokens = [token.lower().strip() for token in authority_tokens if token and token.strip()]
    tokens = tokens or list(DEFAULT_AUTHORITY_TOKENS)
    for token in tokens:
        normalized_token = re.sub(r"[^a-z0-9]", "", token)
        if normalized_token and normalized_token in normalized_host:
            return True, f"主域名包含权威机关标识：{token}"

    return False, "未命中官网域名或权威机关标识"
