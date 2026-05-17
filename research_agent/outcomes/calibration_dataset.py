from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from pydantic import BaseModel, Field

from research_agent.decision.decision_packet import DecisionPacket
from research_agent.outcomes.price_outcome import PriceOutcomeReport
from research_agent.outcomes.report_manifest import ReportManifest
from research_agent.quality.quality_report import QualityReport


class CalibrationRow(BaseModel):
    report_id: str
    ticker: str
    as_of_date: str
    rating: str
    quality_score: float
    fundamental_score: Optional[float] = None
    technical_score: Optional[float] = None
    valuation_score: Optional[float] = None
    risk_score: Optional[float] = None
    return_20d: Optional[float] = None
    return_90d: Optional[float] = None
    excess_return_20d: Optional[float] = None
    return_60d: Optional[float] = None
    excess_return_60d: Optional[float] = None
    excess_return_90d: Optional[float] = None
    max_drawdown_60d: Optional[float] = None
    max_drawdown_90d: Optional[float] = None
    rating_success_60d: Optional[bool] = None
    action_success: Optional[bool] = None
    triggered_rules: list[str] = Field(default_factory=list)
    agent_issue_counts: dict[str, int] = Field(default_factory=dict)


def build_calibration_row(
    manifest: ReportManifest,
    price_outcome_report: PriceOutcomeReport,
    decision_packet: Optional[DecisionPacket] = None,
    quality_report: Optional[QualityReport] = None,
    rating_success_60d: Optional[bool] = None,
    action_success: Optional[bool] = None,
    excess_return_20d: Optional[float] = None,
    excess_return_60d: Optional[float] = None,
    excess_return_90d: Optional[float] = None,
    triggered_rules: Optional[list[str]] = None,
    agent_issue_counts: Optional[dict[str, int]] = None,
) -> CalibrationRow:
    outcome_20d = price_outcome_report.outcomes.get("20d")
    outcome_60d = price_outcome_report.outcomes.get("60d")
    outcome_90d = price_outcome_report.outcomes.get("90d")
    scores = decision_packet.signal_scores if decision_packet else None
    return CalibrationRow(
        report_id=manifest.report_id,
        ticker=manifest.ticker,
        as_of_date=manifest.as_of_date,
        rating=manifest.final_rating,
        quality_score=quality_report.total_score if quality_report else manifest.quality_score,
        fundamental_score=scores.fundamental_score if scores else None,
        technical_score=scores.technical_score if scores else None,
        valuation_score=scores.valuation_score if scores else None,
        risk_score=scores.risk_score if scores else None,
        return_20d=outcome_20d.return_pct if outcome_20d else None,
        return_90d=outcome_90d.return_pct if outcome_90d else None,
        return_60d=outcome_60d.return_pct if outcome_60d else None,
        excess_return_20d=excess_return_20d,
        excess_return_60d=excess_return_60d,
        excess_return_90d=excess_return_90d,
        max_drawdown_60d=outcome_60d.max_drawdown_pct if outcome_60d else None,
        max_drawdown_90d=outcome_90d.max_drawdown_pct if outcome_90d else None,
        rating_success_60d=rating_success_60d,
        action_success=action_success,
        triggered_rules=triggered_rules if triggered_rules is not None else (
            decision_packet.triggered_rules if decision_packet else []
        ),
        agent_issue_counts=agent_issue_counts or {},
    )


def append_calibration_row(row: CalibrationRow, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = row.model_dump(mode="json") if hasattr(row, "model_dump") else row.dict()
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return target


def load_calibration_rows(path: Union[str, Path]) -> list[CalibrationRow]:
    target = Path(path)
    if not target.exists():
        return []
    rows = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(CalibrationRow(**json.loads(line)))
    return rows
