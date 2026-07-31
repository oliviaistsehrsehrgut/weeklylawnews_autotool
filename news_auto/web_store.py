from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict


class SessionStore:
    def __init__(self, root: Path, ttl_seconds: int = 86400) -> None:
        self.root = root
        self.ttl_seconds = ttl_seconds
        self.root.mkdir(parents=True, exist_ok=True)
        self.cleanup()

    def path_for(self, session_id: str) -> Path:
        if not session_id.isalnum():
            raise ValueError("invalid session id")
        return self.root / f"{session_id}.json"

    def create(self, payload: Dict[str, Any]) -> str:
        session_id = f"{int(time.time() * 1000):x}{os.urandom(4).hex()}"
        payload = dict(payload)
        payload["session_id"] = session_id
        self.save(session_id, payload)
        return session_id

    def load(self, session_id: str) -> Dict[str, Any]:
        path = self.path_for(session_id)
        if not path.exists():
            raise FileNotFoundError(session_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, session_id: str, payload: Dict[str, Any]) -> None:
        path = self.path_for(session_id)
        payload = dict(payload)
        payload["updated_at"] = time.time()
        fd, temp_name = tempfile.mkstemp(prefix=f".{session_id}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temp_name, path)
        finally:
            temp_path = Path(temp_name)
            if temp_path.exists():
                temp_path.unlink()

    def cleanup(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        for path in self.root.glob("*.json"):
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue
