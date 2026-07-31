from __future__ import annotations

import re
from datetime import date
from pathlib import Path


WORD_LABEL = "\u6cd5\u8baf"


def as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip()[:10])


def next_word_path(output_dir: Path, week_end: date | str) -> Path:
    end_date = as_date(week_end)
    stem = f"{end_date:%m%d}{WORD_LABEL}"
    pattern = re.compile(rf"^{re.escape(stem)}_v(\d+)\.docx$")
    versions = []
    for path in output_dir.glob(f"{stem}_v*.docx"):
        match = pattern.match(path.name)
        if match:
            versions.append(int(match.group(1)))
    version = max(versions, default=0) + 1
    return output_dir / f"{stem}_v{version}.docx"
