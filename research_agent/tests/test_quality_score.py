import json
from pathlib import Path

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.quality.quality_score import calculate_quality_score
from research_agent.repair.repair_orchestrator import run_auto_repair
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(fixture_name, filename):
    return json.loads((FIXTURES / fixture_name / filename).read_text(encoding="utf-8"))


def _load_text(fixture_name, filename):
    return (FIXTURES / fixture_name / filename).read_text(encoding="utf-8")


def _quality_inputs(fixture_name):
    markdown = _load_text(fixture_name, "bad_report.md")
    metrics_packet = MetricsPacket(**_load_json(fixture_name, "metrics_packet.json"))
    validation_report = ValidationReport(**_load_json(fixture_name, "validation_report.json"))
    source_registry = SourceRegistry(**_load_json(fixture_name, "source_registry.json"))
    audit_report = audit_markdown_report(
        markdown=markdown,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        source_registry=source_registry,
        ticker=metrics_packet.ticker,
    )
    decision_packet = build_decision_packet(
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
    )
    return markdown, metrics_packet, validation_report, source_registry, audit_report, decision_packet


def test_quality_score_blocks_low_quality_report():
    markdown, _, validation_report, _, audit_report, decision_packet = _quality_inputs("nvda_2026_05_01")

    score = calculate_quality_score(
        validation_report=validation_report,
        audit_report=audit_report,
        decision_packet=decision_packet,
        final_markdown=markdown,
    )

    assert score.total_score < 75
    assert not score.publishable


def test_quality_score_allows_repaired_report():
    from research_agent.research_core.models.data_packet import DataPacket

    markdown, metrics_packet, validation_report, source_registry, audit_report, decision_packet = _quality_inputs("nvda_2026_05_01")
    data_packet = DataPacket(**_load_json("nvda_2026_05_01", "data_packet.json"))
    result = run_auto_repair(
        draft_markdown=markdown,
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        decision_packet=decision_packet,
        source_registry=source_registry,
    )
    score = calculate_quality_score(
        validation_report=validation_report,
        audit_report=result.final_audit_report,
        decision_packet=decision_packet,
        final_markdown=result.final_markdown,
    )

    assert score.total_score >= 85
    assert score.publishable


def test_quality_score_blocks_skeleton_report_without_claims():
    _, _, validation_report, _, audit_report, decision_packet = _quality_inputs("ddog_2026_05_01")

    score = calculate_quality_score(
        validation_report=validation_report,
        audit_report=audit_report.model_copy(update={"issues": [], "has_blocking_errors": False}),
        decision_packet=decision_packet,
        final_markdown="No LLM claims attached. Use validated packets before adding interpretation.",
        analyst_claim_count=0,
    )

    assert score.total_score <= 40
    assert score.content_score <= 40
    assert not score.publishable


def test_quality_score_blocks_unknown_archetype_and_missing_business_kpis():
    (
        markdown,
        _,
        validation_report,
        _,
        audit_report,
        decision_packet,
    ) = _quality_inputs("nvda_2026_05_01")

    score = calculate_quality_score(
        validation_report=validation_report,
        audit_report=audit_report.model_copy(
            update={"issues": [], "has_blocking_errors": False}
        ),
        decision_packet=decision_packet,
        final_markdown=markdown,
        company_archetype="UNKNOWN",
        archetype_confidence=0.0,
        unknown_or_low_confidence_archetype_count=1,
        business_model_kpi_coverage_complete=False,
        business_model_kpi_gap_count=2,
        required_business_kpis=["renewal_rate", "paid_members"],
        missing_business_kpis=["renewal_rate", "paid_members"],
    )

    assert score.publishable is False
    assert score.content_score <= 55
    assert "UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE" in score.manual_review_reasons
    assert "BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE" in score.manual_review_reasons
