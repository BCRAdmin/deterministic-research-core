from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_agent.decision.decision_packet import DecisionPacket
from research_agent.e2e.e2e_case import E2ECase
from research_agent.e2e.golden_expectations import build_golden_case
from research_agent.evidence.evidence_ledger import EvidenceLedger, build_evidence_ledger_from_source_registry, load_evidence_ledger
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


def load_case(path: str | Path) -> E2ECase:
    path = Path(path)
    if path.is_dir():
        return build_golden_case(path.name, path.parent)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return E2ECase(**payload)


def load_cases_from_path(path: str | Path) -> list[E2ECase]:
    path = Path(path)
    if path.is_file():
        return [load_case(path)]
    json_cases = sorted(path.glob("*.json"))
    if json_cases:
        return [load_case(case_path) for case_path in json_cases]
    fixture_dirs = [item for item in sorted(path.iterdir()) if item.is_dir() and (item / "bad_report.md").exists()]
    return [load_case(item) for item in fixture_dirs]


def load_packets(case: E2ECase) -> dict[str, Any]:
    data_packet = DataPacket(**_load_json(case.data_packet_path))
    metrics_packet = MetricsPacket(**_load_json(case.metrics_packet_path))
    validation_report = ValidationReport(**_load_json(case.validation_report_path))
    source_registry = SourceRegistry(**_load_json(case.source_registry_path)) if case.source_registry_path else None
    evidence_ledger = (
        load_evidence_ledger(case.evidence_ledger_path)
        if case.evidence_ledger_path
        else build_evidence_ledger_from_source_registry(
            ticker=metrics_packet.ticker,
            as_of_date=metrics_packet.as_of_date,
            source_registry=source_registry,
            metrics_packet=metrics_packet,
        )
    )
    decision_packet = DecisionPacket(**_load_json(case.decision_packet_path)) if case.decision_packet_path else None
    return {
        "data_packet": data_packet,
        "metrics_packet": metrics_packet,
        "validation_report": validation_report,
        "source_registry": source_registry,
        "evidence_ledger": evidence_ledger,
        "decision_packet": decision_packet,
    }


def _load_json(path: str | None) -> dict:
    if not path:
        raise ValueError("Missing required E2E packet path.")
    return json.loads(Path(path).read_text(encoding="utf-8"))
