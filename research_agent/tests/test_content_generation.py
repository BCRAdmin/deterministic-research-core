import json
from pathlib import Path

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.content.claim_generator import claim_quality_metrics, generate_research_claims
from research_agent.content.report_composer import compose_research_report
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.quality.quality_score import calculate_quality_score
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


def _load_packet(ticker: str):
    base = Path("research_agent/data/packets") / ticker / "2026-05-05"
    return (
        DataPacket(**json.loads((base / "data_packet.json").read_text(encoding="utf-8"))),
        MetricsPacket(**json.loads((base / "metrics_packet.json").read_text(encoding="utf-8"))),
        ValidationReport(**json.loads((base / "validation_report.json").read_text(encoding="utf-8"))),
        EvidenceLedger(**json.loads((base / "evidence_ledger.json").read_text(encoding="utf-8"))),
        DecisionPacket(**json.loads((base / "decision_packet.json").read_text(encoding="utf-8"))),
    )


def test_content_generator_creates_minimum_evidence_mapped_claims():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    quality = claim_quality_metrics(claims)

    assert quality["analyst_claim_count"] >= 15
    assert quality["evidence_mapped_claim_ratio"] >= 0.90
    assert quality["hard_claim_evidence_ratio"] == 1.0
    assert all(claim.evidence_ids for claim in claims)


def test_composed_claim_report_can_pass_quality_when_audit_is_clean():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    report = compose_research_report(data, metrics, validation, decision, ledger, claims)

    audit = audit_markdown_report(
        report,
        metrics_packet=metrics,
        validation_report=validation,
        decision_packet=decision,
        evidence_ledger=ledger,
        ticker=data.ticker,
    )
    claim_quality = claim_quality_metrics(claims)
    quality = calculate_quality_score(
        validation_report=validation,
        audit_report=audit,
        decision_packet=decision,
        final_markdown=report,
        analyst_claim_count=claim_quality["analyst_claim_count"],
        evidence_mapped_claim_ratio=claim_quality["evidence_mapped_claim_ratio"],
        hard_claim_evidence_ratio=claim_quality["hard_claim_evidence_ratio"],
        substantive_analyst_claim_count=claim_quality["substantive_analyst_claim_count"],
        generic_claim_ratio=claim_quality["generic_claim_ratio"],
        company_specific_claim_count=claim_quality["company_specific_claim_count"],
        valuation_specific_claim_count=claim_quality["valuation_specific_claim_count"],
        technical_specific_claim_count=claim_quality["technical_specific_claim_count"],
        rating_rationale_claim_count=claim_quality["rating_rationale_claim_count"],
    )

    assert not audit.has_blocking_errors
    assert quality.publishable
    assert "No LLM claims attached" not in report
    assert "## Evidence Appendix" in report
    assert claim_quality["substantive_analyst_claim_count"] >= 15


def test_financial_sanity_errors_still_block_claim_rich_reports():
    data, metrics, validation, ledger, decision = _load_packet("NVDA")
    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    report = compose_research_report(data, metrics, validation, decision, ledger, claims)

    audit = audit_markdown_report(
        report,
        metrics_packet=metrics,
        validation_report=validation,
        decision_packet=decision,
        evidence_ledger=ledger,
        ticker=data.ticker,
    )
    claim_quality = claim_quality_metrics(claims)
    quality = calculate_quality_score(
        validation_report=validation,
        audit_report=audit,
        decision_packet=decision,
        final_markdown=report,
        analyst_claim_count=claim_quality["analyst_claim_count"],
        evidence_mapped_claim_ratio=claim_quality["evidence_mapped_claim_ratio"],
        hard_claim_evidence_ratio=claim_quality["hard_claim_evidence_ratio"],
        substantive_analyst_claim_count=claim_quality["substantive_analyst_claim_count"],
        generic_claim_ratio=claim_quality["generic_claim_ratio"],
        company_specific_claim_count=claim_quality["company_specific_claim_count"],
        valuation_specific_claim_count=claim_quality["valuation_specific_claim_count"],
        technical_specific_claim_count=claim_quality["technical_specific_claim_count"],
        rating_rationale_claim_count=claim_quality["rating_rationale_claim_count"],
    )

    assert any(issue.code.startswith("FINANCIAL_SANITY_") for issue in audit.issues)
    assert not quality.publishable
