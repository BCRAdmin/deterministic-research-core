from __future__ import annotations

from pydantic import BaseModel, Field

from research_agent.audit.audit_report import AuditReport
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.quality.quality_report import QualityReport


class E2EResult(BaseModel):
    case_id: str
    ticker: str
    initial_audit: AuditReport
    final_audit: AuditReport
    decision_packet: DecisionPacket
    quality_score: QualityReport
    repaired: bool
    final_markdown: str
    passed: bool
    final_status: str
    failure_reasons: list[str] = Field(default_factory=list)
