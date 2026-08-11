from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Union

from pydantic import BaseModel, Field


SOURCE_AUTHORITY = {
    "company_ir": 1,
    "sec_filing": 1,
    "earnings_transcript": 2,
    "exchange_ohlcv": 2,
    "trusted_market_data_vendor": 2,
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

SOURCE_TIERS = {
    "company_ir": "official_financial_authority",
    "sec_filing": "official_financial_authority",
    "official_press_release": "official_financial_authority",
    "exchange_ohlcv": "market_authority",
    "trusted_market_data_vendor": "market_authority",
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


def merge_evidence_sources(
    registry: Optional[SourceRegistry],
    *,
    registry_id: str,
    ticker: str,
    evidence_items: Iterable[object],
) -> SourceRegistry:
    """Register every runtime evidence source without ticker-specific rules.

    Source ingestion can discover filings, releases, events, and price feeds
    after an initial registry was created. The registry must be expanded before
    validation and export so the evidence ledger never points at an undeclared
    source.
    """

    symbol = ticker.strip().upper()
    if registry is None:
        registry = SourceRegistry(registry_id=registry_id)
    if registry.registry_id != registry_id:
        raise ValueError(
            f"source registry identity mismatch: {registry.registry_id} != {registry_id}"
        )

    by_id = {source.source_id: source for source in registry.sources}
    for evidence in evidence_items:
        source_id = str(getattr(evidence, "source_id", "") or "").strip()
        evidence_ticker = str(getattr(evidence, "ticker", "") or "").strip().upper()
        if not source_id:
            raise ValueError("runtime evidence has no source_id")
        if evidence_ticker != symbol:
            raise ValueError(
                f"runtime evidence ticker mismatch: {evidence_ticker} != {symbol}"
            )
        metrics = {
            str(metric)
            for metric in getattr(evidence, "supports_metrics", []) or []
            if str(metric)
        }
        existing = by_id.get(source_id)
        if existing is None:
            existing = SourceRegistryEntry(
                source_id=source_id,
                ticker=symbol,
                source_type=str(getattr(evidence, "source_type", "") or "unknown"),
                authority_rank=int(getattr(evidence, "authority_rank", 99) or 99),
                url=getattr(evidence, "url", None),
                retrieved_at=getattr(evidence, "retrieved_at", None),
                used_for=sorted(metrics),
                owner="deterministic_research_pipeline",
                source_tier=SOURCE_TIERS.get(
                    str(getattr(evidence, "source_type", "") or "unknown")
                ),
                freshness_status=(
                    "current_ingestion"
                    if getattr(evidence, "retrieved_at", None)
                    else "retrieval_time_unavailable"
                ),
            )
            registry.sources.append(existing)
            by_id[source_id] = existing
            continue
        if existing.ticker.strip().upper() != symbol:
            raise ValueError(
                f"registered source ticker mismatch: {existing.ticker} != {symbol}"
            )
        existing.used_for = sorted(set(existing.used_for) | metrics)
        evidence_rank = int(getattr(evidence, "authority_rank", 99) or 99)
        existing.authority_rank = min(
            existing.resolved_authority_rank(),
            evidence_rank,
        )
        if not existing.url:
            existing.url = getattr(evidence, "url", None)
        if not existing.retrieved_at:
            existing.retrieved_at = getattr(evidence, "retrieved_at", None)
        if not existing.source_tier:
            existing.source_tier = SOURCE_TIERS.get(existing.source_type)
        if not existing.freshness_status:
            existing.freshness_status = (
                "current_ingestion"
                if existing.retrieved_at
                else "retrieval_time_unavailable"
            )
    return registry


def bind_registry_claims(
    registry: SourceRegistry,
    fact_ledger: dict,
    research_claims: Optional[Iterable[object]] = None,
) -> SourceRegistry:
    """Bind registered sources to exact research-claim source edges.

    Fact lineage remains in the fact/evidence ledgers.  Copying every lineage
    source onto every claim overstates support and makes the reverse graph
    asymmetric, so the registry is rebuilt solely from each claim's declared
    source IDs.
    """

    by_id = {source.source_id: source for source in registry.sources}
    for source in registry.sources:
        source.claim_ids = []
    for claim in research_claims or []:
        claim_id = str(getattr(claim, "claim_id", "") or "").strip()
        if not claim_id:
            continue
        for raw_source_id in getattr(claim, "source_ids", []) or []:
            source_id = str(raw_source_id or "").strip()
            source = by_id.get(source_id)
            if source is None:
                raise ValueError(
                    f"research claim {claim_id} references unregistered source {source_id}"
                )
            source.claim_ids = sorted(set(source.claim_ids) | {claim_id})
    return registry


def _model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()
