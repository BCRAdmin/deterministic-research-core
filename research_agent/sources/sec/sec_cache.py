from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Union


class SecCache:
    def __init__(self, cache_dir: Union[str, Path] = "research_agent/data/cache/sec", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not path.exists():
            return None
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age > self.ttl:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def set(self, key: str, data: Any) -> Path:
        path = self._path(key)
        path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        return path
