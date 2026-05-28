from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseModel, Field


SOURCE_AUTHORITY = {
    "company_ir": 1,
    "sec_filing": 1,
    "earnings_transcript": 2,
    "exchange_ohlcv": 2,
    "reuters": 3,
    "barrons": 3,
    "marketwatch": 3,
    "analyst_note": 4,
    "zacks": 5,
    "yahoo_finance": 5,
    "simply_wall_st": 6,
    "insider_monkey": 6,
    "stockstory": 6,
    "social_media": 7,
}


class SourceRegistryEntry(BaseModel):
    source_id: str
    ticker: str
    source_type: str
    authority_rank: Optional[int] = None
    url: Optional[str] = None
    retrieved_at: Optional[str] = None
    used_for: List[str] = Field(default_factory=list)
    owner: Optional[str] = None
    source_tier: Optional[str] = None
    claim_ids: List[str] = Field(default_factory=list)
    freshness_status: Optional[str] = None

    def resolved_authority_rank(self) -> int:
        return self.authority_rank or SOURCE_AUTHORITY.get(self.source_type, 99)


class SourceRegistry(BaseModel):
    registry_id: str
    sources: List[SourceRegistryEntry] = Field(default_factory=list)

    def source_ids(self) -> set[str]:
        return {source.source_id for source in self.sources}

    def authority_for_metric(self, metric_name: str) -> list[SourceRegistryEntry]:
        return [source for source in self.sources if metric_name in source.used_for]


def get_source_authority_rank(source_type: str) -> int:
    return SOURCE_AUTHORITY.get(source_type, 99)


def load_source_registry(path: Union[str, Path]) -> SourceRegistry:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return SourceRegistry(**payload)


def save_source_registry(registry: SourceRegistry, path: Union[str, Path]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _model_to_dict(registry)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()
