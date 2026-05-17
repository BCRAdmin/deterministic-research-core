from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union


def load_fundamentals(ticker: str, raw_dir: Union[str, Path] = "research_agent/data/raw") -> dict[str, Any]:
    path = Path(raw_dir) / f"{ticker.upper()}_fundamentals.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing fundamentals file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
