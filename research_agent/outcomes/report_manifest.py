from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ReportManifest(BaseModel):
    report_id: str
    ticker: str
    company_name: Optional[str] = None
    as_of_date: str
    price_basis_date: str
    price_basis_close: float
    final_rating: str
    preferred_rating: str
    allowed_ratings: List[str]
    quality_score: float
    publishable: bool
    decision_packet_path: str
    metrics_packet_path: str
    validation_report_path: str
    audit_report_path: Optional[str] = None
    final_report_path: str
    pipeline_version: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, object] = Field(default_factory=dict)


def build_report_manifest(
    ticker: str,
    as_of_date: str,
    price_basis_date: str,
    price_basis_close: float,
    final_rating: str,
    preferred_rating: str,
    allowed_ratings: list[str],
    quality_score: float,
    publishable: bool,
    decision_packet_path: Union[str, Path],
    metrics_packet_path: Union[str, Path],
    validation_report_path: Union[str, Path],
    final_report_path: Union[str, Path],
    pipeline_version: str,
    company_name: Optional[str] = None,
    audit_report_path: Optional[Union[str, Path]] = None,
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict[str, object]] = None,
) -> ReportManifest:
    report_id = f"{ticker.upper()}_{as_of_date}"
    return ReportManifest(
        report_id=report_id,
        ticker=ticker.upper(),
        company_name=company_name,
        as_of_date=as_of_date,
        price_basis_date=price_basis_date,
        price_basis_close=price_basis_close,
        final_rating=final_rating,
        preferred_rating=preferred_rating,
        allowed_ratings=allowed_ratings,
        quality_score=quality_score,
        publishable=publishable,
        decision_packet_path=str(decision_packet_path),
        metrics_packet_path=str(metrics_packet_path),
        validation_report_path=str(validation_report_path),
        audit_report_path=str(audit_report_path) if audit_report_path else None,
        final_report_path=str(final_report_path),
        pipeline_version=pipeline_version,
        model_provider=model_provider,
        model_name=model_name,
        tags=tags or [],
        metadata=metadata or {},
    )


def save_report_manifest(manifest: ReportManifest, output_dir: Union[str, Path]) -> Path:
    target_dir = Path(output_dir) / manifest.ticker / manifest.as_of_date
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "report_manifest.json"
    payload = manifest.model_dump(mode="json") if hasattr(manifest, "model_dump") else manifest.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_report_manifest(path: Union[str, Path]) -> ReportManifest:
    return ReportManifest(**json.loads(Path(path).read_text(encoding="utf-8")))

