from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class NewsItem:
    title: str = ""
    link: str = ""
    source: str = ""
    pub_date: Optional[str] = None
    content: str = ""
    summary: str = ""
    topic: str = ""
    jurisdiction: str = ""
    legal_level: str = ""
    is_legal_news: bool = False
    include: bool = True
    reason: str = ""
    fetch_status: str = "pending"
    official_link: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsItem":
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in allowed})
