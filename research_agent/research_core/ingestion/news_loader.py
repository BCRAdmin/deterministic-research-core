from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union


def load_news(ticker: str, raw_dir: Union[str, Path] = "research_agent/data/raw") -> list[dict[str, Any]]:
    path = Path(raw_dir) / f"{ticker.upper()}_news.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
