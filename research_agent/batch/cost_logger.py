from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel


class ModelUsageRecord(BaseModel):
    ticker: str
    agent_name: str
    model_provider: str
    model_name: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    latency_seconds: Optional[float] = None


def append_model_usage(record: ModelUsageRecord, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else record.dict()
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return target


def load_model_usage(path: Union[str, Path]) -> list[ModelUsageRecord]:
    target = Path(path)
    if not target.exists():
        return []
    return [
        ModelUsageRecord.model_validate(json.loads(line))
        for line in target.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
