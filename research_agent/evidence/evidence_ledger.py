from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Union

from pydantic import BaseModel, Field

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.metrics_packet import MetricsPacket


class EvidenceLedger(BaseModel):
    ticker: str
    as_of_date: str
    evidence_items: List[EvidenceItem] = Field(default_factory=list)

    def find_by_metric(self, metric_name: str) -> List[EvidenceItem]:
        aliases = _metric_aliases(metric_name)
        return [
            item
            for item in self.evidence_items
            if aliases.intersection(set(item.supports_metrics))
        ]

    def find_by_claim(self, claim_id: str) -> List[EvidenceItem]:
        return [
            item
            for item in self.evidence_items
            if claim_id in item.supports_claims
        ]

    def has_primary_evidence_for_metric(self, metric_name: str) -> bool:
        return any(item.authority_rank <= 2 for item in self.find_by_metric(metric_name))


def build_evidence_ledger_from_source_registry(
    ticker: str,
    as_of_date: str,
    source_registry: Optional[SourceRegistry],
    metrics_packet: Optional[MetricsPacket] = None,
) -> EvidenceLedger:
    if source_registry is None:
        return EvidenceLedger(ticker=ticker.upper(), as_of_date=as_of_date, evidence_items=[])

    items: list[EvidenceItem] = []
    for source in source_registry.sources:
        metrics = _expand_used_for(source.used_for)
        if not metrics:
            metrics = list(source.used_for)
        for metric in metrics:
            value = _metric_value(metrics_packet, metric) if metrics_packet else None
            items.append(
                EvidenceItem(
                    evidence_id=f"{source.source_id}_{_safe_metric_id(metric)}",
                    ticker=ticker.upper(),
                    claim_type=_claim_type_for_metric(metric, source.source_type),
                    source_id=source.source_id,
                    source_type=source.source_type,
                    authority_rank=source.resolved_authority_rank()
                    if hasattr(source, "resolved_authority_rank")
                    else rank_source(source.source_type),
                    statement=f"{source.source_id} supports {metric}.",
                    value=value,
                    unit=_unit_for_metric(metric),
                    period=None,
                    date=None,
                    url=source.url,
                    retrieved_at=source.retrieved_at,
                    supports_metrics=[metric],
                    confidence="high" if (source.authority_rank or rank_source(source.source_type)) <= 2 else "medium",
                )
            )
    return EvidenceLedger(ticker=ticker.upper(), as_of_date=as_of_date, evidence_items=items)


def save_evidence_ledger(ledger: EvidenceLedger, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = ledger.model_dump(mode="json") if hasattr(ledger, "model_dump") else ledger.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_evidence_ledger(path: Union[str, Path]) -> EvidenceLedger:
    return EvidenceLedger(**json.loads(Path(path).read_text(encoding="utf-8")))


def _expand_used_for(used_for: list[str]) -> list[str]:
    metrics: list[str] = []
    for raw_metric in used_for:
        metric = raw_metric.strip().lower()
        metrics.extend(sorted(_metric_aliases(metric)))
    return list(dict.fromkeys(metrics))


def _metric_aliases(metric_name: str) -> set[str]:
    normalized = metric_name.strip().lower()
    if normalized in {
        "company_guidance_eps",
        "consensus_forward_eps",
        "sbc_to_revenue",
        "sbc_to_fcf",
        "sbc_to_non_gaap_operating_income",
    }:
        return {normalized}
    if normalized == "ev_to_sales":
        return {"ev_to_sales", "revenue_ttm", "close", "price_data"}
    if normalized == "price_to_fcf":
        return {"price_to_fcf", "free_cash_flow_ttm", "close", "price_data"}
    aliases = {normalized}
    alias_map = {
        "revenue": {"revenue", "revenue_ttm", "sales", "umsatz"},
        "free_cash_flow": {"fcf", "free_cash_flow", "free_cash_flow_ttm", "cashflow", "free_cashflow"},
        "fcf": {"fcf", "free_cash_flow", "free_cash_flow_ttm", "cashflow", "free_cashflow"},
        "operating_income": {"operating_income", "operating_income_ttm"},
        "net_income": {"net_income", "net_income_ttm"},
        "eps": {"eps", "eps_diluted"},
        "forward_eps": {"forward_eps"},
        "guidance": {"guidance", "company_guidance_eps"},
        "consensus": {"consensus", "consensus_forward_eps", "forward_eps"},
        "sbc": {"sbc", "sbc_ttm", "sbc_to_revenue", "sbc_to_fcf"},
        "cash": {"cash", "cash_and_equivalents", "cash_and_investments", "net_cash"},
        "debt": {"debt", "total_debt", "net_debt"},
        "price": {"price", "close", "price_basis", "price_data"},
        "ohlcv": {"ohlcv", "price", "close", "price_data"},
    }
    for key, values in alias_map.items():
        if normalized == key or normalized in values:
            aliases.update(values)
    return aliases


def _metric_value(metrics_packet: Optional[MetricsPacket], metric_name: str) -> Optional[float]:
    if metrics_packet is None:
        return None
    for section_name in ["fundamentals", "technical", "valuation"]:
        section = getattr(metrics_packet, section_name)
        if hasattr(section, metric_name):
            value = getattr(section, metric_name)
            return float(value) if isinstance(value, (int, float)) else None
    return None


def _claim_type_for_metric(metric_name: str, source_type: str):
    if metric_name in {"company_guidance_eps", "guidance"}:
        return "guidance"
    if metric_name in {"close", "price", "price_data", "price_basis"} or source_type == "exchange_ohlcv":
        return "price_data"
    if metric_name.startswith("sma") or metric_name.startswith("ema") or metric_name in {"rsi_14", "macd_histogram"}:
        return "technical_metric"
    if metric_name in {"forward_pe_consensus", "price_to_fcf", "ev_to_sales", "peg_ratio"}:
        return "valuation_metric"
    if source_type in {"reuters", "barrons", "wsj", "marketwatch", "official_press_release"}:
        return "news"
    return "financial_metric"


def _unit_for_metric(metric_name: str) -> Optional[str]:
    if "margin" in metric_name or metric_name.startswith("sbc_to"):
        return "percent"
    if "eps" in metric_name:
        return "usd_per_share"
    if metric_name in {"revenue_ttm", "free_cash_flow_ttm", "cash_and_investments", "total_debt", "net_cash"}:
        return "usd"
    return None


def _safe_metric_id(metric_name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in metric_name.upper()).strip("_")
