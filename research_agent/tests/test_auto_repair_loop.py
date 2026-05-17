import json
from pathlib import Path

import pytest

from research_agent.audit.rating_action_extractor import (
    extract_action_lines,
    infer_report_action_class,
)
from research_agent.audit.report_linter import audit_markdown_report
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.repair.repair_orchestrator import run_auto_repair
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.research_core.reporting.report_builder import render_markdown_report


FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(fixture_name, filename):
    return json.loads((FIXTURES / fixture_name / filename).read_text(encoding="utf-8"))


def _load_text(fixture_name, filename):
    return (FIXTURES / fixture_name / filename).read_text(encoding="utf-8")


def _fixture_objects(fixture_name):
    markdown = _load_text(fixture_name, "bad_report.md")
    data_packet = DataPacket(**_load_json(fixture_name, "data_packet.json"))
    metrics_packet = MetricsPacket(**_load_json(fixture_name, "metrics_packet.json"))
    validation_report = ValidationReport(**_load_json(fixture_name, "validation_report.json"))
    source_registry = SourceRegistry(**_load_json(fixture_name, "source_registry.json"))
    audit_report = audit_markdown_report(
        markdown=markdown,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        source_registry=source_registry,
        ticker=data_packet.ticker,
    )
    action_class = infer_report_action_class(extract_action_lines(markdown))
    decision_packet = build_decision_packet(
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        action_class=action_class if action_class != "unknown" else None,
    )
    return markdown, data_packet, metrics_packet, validation_report, source_registry, audit_report, decision_packet


def test_auto_repair_fixes_ddog_long_stop_above_entry():
    markdown, data_packet, metrics_packet, validation_report, source_registry, audit_report, decision_packet = _fixture_objects("ddog_2026_05_01")
    result = run_auto_repair(
        draft_markdown=markdown,
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        decision_packet=decision_packet,
        source_registry=source_registry,
    )

    assert result.success
    assert not result.final_audit_report.has_issue("INVALID_TRADE_LEVEL")
    assert not result.final_audit_report.has_issue("RATING_TOO_HARSH_FOR_ACTION")


def test_auto_repair_softens_mdb_news_causality():
    markdown, data_packet, metrics_packet, validation_report, source_registry, audit_report, decision_packet = _fixture_objects("mdb_2026_05_01")
    result = run_auto_repair(
        draft_markdown=markdown,
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        decision_packet=decision_packet,
        source_registry=source_registry,
    )

    assert result.success
    assert not result.final_audit_report.has_issue("OVERSTATED_CAUSALITY")


def test_auto_repair_fixes_nvda_fcf_mismatch():
    markdown, data_packet, metrics_packet, validation_report, source_registry, audit_report, decision_packet = _fixture_objects("nvda_2026_05_01")
    result = run_auto_repair(
        draft_markdown=markdown,
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        decision_packet=decision_packet,
        source_registry=source_registry,
    )

    assert result.success
    assert not result.final_audit_report.has_issue("NUMERIC_MISMATCH", metric="free_cash_flow_ttm")
    assert "$96.575B" in result.final_markdown


def test_report_builder_auto_repair_writes_final_and_quality_artifacts(tmp_path):
    _, data_packet, metrics_packet, validation_report, source_registry, _, decision_packet = _fixture_objects("nvda_2026_05_01")
    claims = [
        ResearchClaim(
            agent="fundamental",
            claim="FCF TTM is $58.1B.",
            evidence_metrics=["free_cash_flow_ttm"],
            source_ids=["NVDA_IR_FY2026"],
            confidence="high",
        )
    ]

    report = render_markdown_report(
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        claims=claims,
        source_registry=source_registry,
        decision_packet=decision_packet,
        run_audit=True,
        enable_auto_repair=True,
        audit_output_dir=str(tmp_path),
    )

    assert "$96.575B" in report
    assert (tmp_path / "repaired_report.md").exists()
    assert (tmp_path / "final_report.md").exists()
    assert (tmp_path / "quality_score.json").exists()


def test_auto_repair_failure_writes_manual_review(tmp_path):
    class NoopRepairClient:
        def repair_report(
            self,
            draft,
            data_packet,
            metrics_packet,
            validation_report,
            audit_report,
            decision_packet,
            source_registry,
            attempt,
        ):
            from research_agent.repair.repair_result import RepairResult

            return RepairResult(
                ticker=data_packet.ticker,
                attempt=attempt,
                success=False,
                repaired_markdown=draft,
                changes=[],
                remaining_blocking_errors=[issue.code for issue in audit_report.issues],
            )

    _, data_packet, metrics_packet, validation_report, source_registry, _, decision_packet = _fixture_objects("nvda_2026_05_01")
    claims = [
        ResearchClaim(
            agent="fundamental",
            claim="FCF TTM is $58.1B.",
            evidence_metrics=["free_cash_flow_ttm"],
            source_ids=["NVDA_IR_FY2026"],
            confidence="high",
        )
    ]

    with pytest.raises(RuntimeError):
        render_markdown_report(
            data_packet=data_packet,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            claims=claims,
            source_registry=source_registry,
            decision_packet=decision_packet,
            run_audit=True,
            enable_auto_repair=True,
            repair_client=NoopRepairClient(),
            audit_output_dir=str(tmp_path),
        )

    assert (tmp_path / "manual_review_required.md").exists()
    assert (tmp_path / "draft_failed_audit.md").exists()
    assert (tmp_path / "audit_report.json").exists()
