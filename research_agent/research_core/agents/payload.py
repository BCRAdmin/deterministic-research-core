from __future__ import annotations

from typing import Optional

from research_agent.audit.audit_report import AuditReport
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


ALLOWED_AGENT_PACKET_KEYS = {
    "data_packet",
    "metrics_packet",
    "validation_report",
    "audit_report",
    "decision_packet",
    "source_registry",
}


def build_agent_payload(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    validation_report: ValidationReport,
    source_registry: Optional[SourceRegistry] = None,
    audit_report: Optional[AuditReport] = None,
    decision_packet: Optional[DecisionPacket] = None,
) -> dict:
    if validation_report.has_blocking_errors:
        raise RuntimeError("Blocking validation errors. LLM agent payload was not created.")
    if audit_report is not None and audit_report.has_blocking_errors:
        raise RuntimeError("Blocking audit errors. LLM agent payload was not created.")

    payload = {
        "data_packet": _model_to_dict(data_packet),
        "metrics_packet": _model_to_dict(metrics_packet),
        "validation_report": _model_to_dict(validation_report),
    }
    if audit_report is not None:
        payload["audit_report"] = _model_to_dict(audit_report)
    if decision_packet is not None:
        payload["decision_packet"] = _model_to_dict(decision_packet)
    if source_registry is not None:
        payload["source_registry"] = _model_to_dict(source_registry)
    assert set(payload).issubset(ALLOWED_AGENT_PACKET_KEYS)
    return payload


def _model_to_dict(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
