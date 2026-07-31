from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List

from .models import NewsItem

DEFAULT_DEBUG_KEEP_COUNT = 20


def prepare_debug_dir(
    output_dir: Path,
    debug_dir_name: str = ".debug",
    keep_count: int = DEFAULT_DEBUG_KEEP_COUNT,
) -> Path:
    debug_dir = output_dir / debug_dir_name
    debug_dir.mkdir(parents=True, exist_ok=True)
    hide_dir_on_windows(debug_dir)
    move_root_debug_files(output_dir, debug_dir)
    prune_debug_files(debug_dir, keep_count)
    return debug_dir


def hide_dir_on_windows(path: Path) -> None:
    if os.name != "nt":
        return
    subprocess.run(
        ["attrib", "+h", str(path)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def move_root_debug_files(output_dir: Path, debug_dir: Path) -> None:
    for source in output_dir.glob("items_*.jsonl"):
        if not source.is_file():
            continue
        target = debug_dir / source.name
        if target.exists():
            target = debug_dir / f"{source.stem}_{int(source.stat().st_mtime)}{source.suffix}"
        shutil.move(str(source), str(target))


def prune_debug_files(debug_dir: Path, keep_count: int = DEFAULT_DEBUG_KEEP_COUNT) -> None:
    files = sorted(
        [path for path in debug_dir.glob("items_*.jsonl") if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in files[max(0, keep_count):]:
        path.unlink(missing_ok=True)


def write_jsonl(path: Path, items: Iterable[NewsItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> List[NewsItem]:
    result: List[NewsItem] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                result.append(NewsItem.from_dict(json.loads(line)))
    return result