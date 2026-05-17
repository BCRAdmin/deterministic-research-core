from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field


class BatchRunItem(BaseModel):
    ticker: str
    status: str
    output_path: Optional[str] = None
    quality_score: Optional[float] = None
    price_basis_date: Optional[str] = None
    data_freshness_status: Optional[str] = None
    stale_price_basis: bool = False
    current_report_allowed: Optional[bool] = None
    historical_qa_only: bool = False
    minimum_viable_report_possible: Optional[bool] = None
    current_report_possible: Optional[bool] = None
    missing_minimum_inputs: list[str] = Field(default_factory=list)
    final_rating: Optional[str] = None
    preferred_rating: Optional[str] = None
    publishable: Optional[bool] = None
    error_message: Optional[str] = None
    failure_type: Optional[str] = None
    counts: dict[str, int] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)


class BatchManifest(BaseModel):
    batch_id: str
    as_of_date: str
    batch_mode: str = "current_research"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    status: str
    items: list[BatchRunItem]


def save_batch_manifest(manifest: BatchManifest, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_batch_manifest(path: Union[str, Path]) -> BatchManifest:
    return BatchManifest.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
