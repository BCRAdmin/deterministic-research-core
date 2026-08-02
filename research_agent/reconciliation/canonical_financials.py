from __future__ import annotations

import json
from pathlib import Path
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field

from research_agent.sources.sec.xbrl_concepts import concept_priority


BasisType = Literal["gaap", "non_gaap", "company_defined", "consensus", "technical"]
StatementType = Literal["income_statement", "balance_sheet", "cash_flow", "guidance", "price", "technical"]
ConfidenceType = Literal["high", "medium", "low"]


class CanonicalMetric(BaseModel):
    metric_name: str
    value: float
    unit: str
    period: str
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    period_bucket: str = "duration_unknown"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    frame: Optional[str] = None
    source_concept: Optional[str] = None
    basis: BasisType = "gaap"
    statement_type: StatementType
    source_ids: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: ConfidenceType
    reconciliation_notes: List[str] = Field(default_factory=list)


class CanonicalFinancials(BaseModel):
    ticker: str
    as_of_date: str
    metrics: List[CanonicalMetric] = Field(default_factory=list)

    def get_metric(self, metric_name: str, period: Optional[str] = None) -> Optional[CanonicalMetric]:
        candidates = [metric for metric in self.metrics if metric.metric_name == metric_name]
        if period:
            candidates = [metric for metric in candidates if metric.period == period]
        if not candidates:
            return None
        if len(candidates) > 1:
            candidates = sorted(
                candidates,
                key=lambda metric: (
                    metric.end_date or "",
                    _confidence_rank(metric.confidence),
                    concept_priority(metric.metric_name, metric.source_concept),
                ),
                reverse=True,
            )
        return candidates[0]

    def metrics_for(self, metric_name: str) -> list[CanonicalMetric]:
        return [metric for metric in self.metrics if metric.metric_name == metric_name]


def save_canonical_financials(canonical: CanonicalFinancials, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical.model_dump(mode="json") if hasattr(canonical, "model_dump") else canonical.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_canonical_financials(path: Union[str, Path]) -> CanonicalFinancials:
    return CanonicalFinancials(**json.loads(Path(path).read_text(encoding="utf-8")))


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)
