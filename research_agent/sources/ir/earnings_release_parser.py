from __future__ import annotations

from typing import Optional

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.sources.ir.guidance_extractor import GuidanceRange, extract_eps_guidance, extract_revenue_guidance


def extract_guidance_ranges(text: str, period: str) -> list[GuidanceRange]:
    return extract_eps_guidance(text, period) + extract_revenue_guidance(text, period)


def guidance_range_to_evidence(
    ticker: str,
    guidance: GuidanceRange,
    source_id: str,
    source_type: str = "earnings_release",
    url: Optional[str] = None,
    retrieved_at: Optional[str] = None,
) -> EvidenceItem:
    statement = (
        f"{ticker.upper()} guided {guidance.metric} to "
        f"{guidance.low}-{guidance.high} {guidance.unit} for {guidance.period}."
    )
    return EvidenceItem(
        evidence_id=f"{ticker.upper()}_{source_id}_{guidance.metric}_{guidance.period}",
        ticker=ticker.upper(),
        claim_type="guidance",
        source_id=source_id,
        source_type=source_type,
        authority_rank=rank_source(source_type),
        statement=statement,
        value=_midpoint(guidance.low, guidance.high),
        unit=guidance.unit,
        period=guidance.period,
        url=url,
        retrieved_at=retrieved_at,
        supports_metrics=[guidance.metric],
        confidence="high" if rank_source(source_type) <= 2 else "medium",
    )


def parse_earnings_release_evidence(
    ticker: str,
    text: str,
    period: str,
    source_id: str,
    source_type: str = "earnings_release",
    url: Optional[str] = None,
    retrieved_at: Optional[str] = None,
) -> list[EvidenceItem]:
    return [
        guidance_range_to_evidence(ticker, guidance, source_id, source_type, url, retrieved_at)
        for guidance in extract_guidance_ranges(text, period)
    ]


def _midpoint(low: Optional[float], high: Optional[float]) -> Optional[float]:
    if low is None or high is None:
        return None
    return (low + high) / 2
