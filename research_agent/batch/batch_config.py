from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


class BatchTickerConfig(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    mode: Literal["manual_packet_mode", "source_ingestion_mode"] = "manual_packet_mode"
    priority: Literal["low", "normal", "high"] = "normal"
    benchmark: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class BatchConfig(BaseModel):
    batch_id: str
    as_of_date: str
    batch_mode: Literal["current_research", "historical_guardrail_test"] = "current_research"
    freshness_reference_date: Optional[str] = None
    freshness_max_trading_days: int = 2
    tickers: list[BatchTickerConfig]
    max_parallel_jobs: int = 1
    output_dir: str = "outputs/batches"
    pipeline_version: str
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    price_csv_dir: Optional[str] = None
    price_start_date: Optional[str] = None
    cik_records_path: Optional[str] = None
    sec_companyfacts_dir: Optional[str] = None
    sec_user_agent: Optional[str] = None
    earnings_calendar_path: Optional[str] = None
    ir_release_dir: Optional[str] = None


def load_batch_config(path: Union[str, Path]) -> BatchConfig:
    """Load a batch config from JSON or a simple tickers CSV.

    CSV support is intentionally minimal for dashboard handoff runs. The CSV
    must contain at least `ticker`; batch-level metadata is read from adjacent
    defaults and can be overridden by using JSON when more precision is needed.
    """

    target = Path(path)
    if target.suffix.lower() == ".json":
        return BatchConfig.model_validate(json.loads(target.read_text(encoding="utf-8")))
    if target.suffix.lower() == ".csv":
        return _load_csv_batch_config(target)
    raise ValueError(f"Unsupported batch config format: {target.suffix}")


def _load_csv_batch_config(path: Path) -> BatchConfig:
    rows = list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
    if not rows:
        raise ValueError("Ticker CSV must contain at least one row.")
    tickers = [
        BatchTickerConfig(
            ticker=row["ticker"],
            company_name=row.get("company_name") or None,
            mode=row.get("mode") or "manual_packet_mode",
            priority=row.get("priority") or "normal",
            benchmark=row.get("benchmark") or None,
            tags=_split_tags(row.get("tags")),
        )
        for row in rows
    ]
    stem = path.stem.replace(" ", "_")
    return BatchConfig(
        batch_id=stem,
        as_of_date=rows[0].get("as_of_date") or "unknown",
        tickers=tickers,
        pipeline_version=rows[0].get("pipeline_version") or "research_agent_v0.1.0",
        model_provider=rows[0].get("model_provider") or None,
        model_name=rows[0].get("model_name") or None,
        price_csv_dir=rows[0].get("price_csv_dir") or None,
        price_start_date=rows[0].get("price_start_date") or None,
        cik_records_path=rows[0].get("cik_records_path") or None,
        sec_companyfacts_dir=rows[0].get("sec_companyfacts_dir") or None,
        sec_user_agent=rows[0].get("sec_user_agent") or None,
        earnings_calendar_path=rows[0].get("earnings_calendar_path") or None,
        ir_release_dir=rows[0].get("ir_release_dir") or None,
    )


def _split_tags(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
