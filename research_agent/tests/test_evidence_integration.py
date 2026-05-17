import json
from pathlib import Path

import pytest

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.research_core.reporting.report_builder import render_markdown_report


FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(fixture_name, filename):
    return json.loads((FIXTURES / fixture_name / filename).read_text(encoding="utf-8"))


def test_markdown_auditor_uses_evidence_ledger_for_hard_claims():
    metrics = MetricsPacket(**_load_json("nvda_2026_05_01", "metrics_packet.json"))
    validation = ValidationReport(**_load_json("nvda_2026_05_01", "validation_report.json"))
    ledger = EvidenceLedger(ticker="NVDA", as_of_date="2026-05-01", evidence_items=[])

    audit = audit_markdown_report(
        markdown="FCF TTM was $96.575B.",
        metrics_packet=metrics,
        validation_report=validation,
        evidence_ledger=ledger,
        ticker="NVDA",
    )

    assert audit.has_issue("MISSING_EVIDENCE_FOR_HARD_CLAIM", metric="free_cash_flow_ttm")


def test_markdown_auditor_blocks_guidance_claim_without_company_guidance():
    metrics = MetricsPacket(**_load_json("nvda_2026_05_01", "metrics_packet.json"))
    validation = ValidationReport(**_load_json("nvda_2026_05_01", "validation_report.json"))
    ledger = EvidenceLedger(ticker="NVDA", as_of_date="2026-05-01", evidence_items=[])

    audit = audit_markdown_report(
        markdown="Management guidance implies a stronger FY2027 EPS outlook.",
        metrics_packet=metrics,
        validation_report=validation,
        evidence_ledger=ledger,
        ticker="NVDA",
    )

    assert audit.has_issue("UNSUPPORTED_GUIDANCE_CLAIM")


def test_markdown_auditor_blocks_event_risk_without_confirmed_earnings():
    metrics = MetricsPacket(**_load_json("nvda_2026_05_01", "metrics_packet.json"))
    validation = ValidationReport(
        ticker="NVDA",
        as_of_date="2026-05-01",
        has_blocking_errors=False,
        issues=[
            {
                "severity": "warning",
                "code": "EARNINGS_DATE_UNAVAILABLE",
                "message": "Next earnings date is unavailable.",
            }
        ],
    )

    audit = audit_markdown_report(
        markdown="Earnings event risk is elevated within 10 trading days.",
        metrics_packet=metrics,
        validation_report=validation,
        evidence_ledger=EvidenceLedger(ticker="NVDA", as_of_date="2026-05-01"),
        ticker="NVDA",
    )

    assert audit.has_issue("UNSUPPORTED_EARNINGS_EVENT_CLAIM")


def test_report_builder_blocks_claims_without_evidence():
    data_packet = DataPacket(**_load_json("nvda_2026_05_01", "data_packet.json"))
    metrics = MetricsPacket(**_load_json("nvda_2026_05_01", "metrics_packet.json"))
    validation = ValidationReport(**_load_json("nvda_2026_05_01", "validation_report.json"))
    claim = ResearchClaim(
        agent="fundamental",
        claim="NVIDIA has strong FCF generation.",
        evidence_metrics=["free_cash_flow_ttm"],
        source_ids=[],
        confidence="high",
    )
    ledger = EvidenceLedger(ticker="NVDA", as_of_date="2026-05-01", evidence_items=[])

    with pytest.raises(RuntimeError, match="Evidence grounding failed"):
        render_markdown_report(
            data_packet=data_packet,
            metrics_packet=metrics,
            validation_report=validation,
            claims=[claim],
            evidence_ledger=ledger,
        )


def test_report_builder_renders_claim_evidence_ids_when_available():
    data_packet = DataPacket(**_load_json("nvda_2026_05_01", "data_packet.json"))
    metrics = MetricsPacket(**_load_json("nvda_2026_05_01", "metrics_packet.json"))
    validation = ValidationReport(**_load_json("nvda_2026_05_01", "validation_report.json"))
    claim = ResearchClaim(
        agent="fundamental",
        claim="NVIDIA has strong FCF generation.",
        evidence_metrics=["free_cash_flow_ttm"],
        source_ids=[],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="NVDA",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="NVDA_IR_FCF",
                ticker="NVDA",
                claim_type="financial_metric",
                source_id="NVDA_IR_FY2026",
                source_type="company_ir",
                authority_rank=1,
                statement="FCF TTM was 96.575B.",
                supports_metrics=["free_cash_flow_ttm"],
            ),
            EvidenceItem(
                evidence_id="NVDA_IR_SBC",
                ticker="NVDA",
                claim_type="financial_metric",
                source_id="NVDA_IR_FY2026",
                source_type="company_ir",
                authority_rank=1,
                statement="SBC to revenue was 8%.",
                supports_metrics=["sbc_to_revenue"],
            ),
            EvidenceItem(
                evidence_id="NVDA_EXCHANGE_CLOSE",
                ticker="NVDA",
                claim_type="price_data",
                source_id="exchange_ohlcv",
                source_type="exchange_ohlcv",
                authority_rank=2,
                statement="Close price was 900.",
                supports_metrics=["close"],
            ),
        ],
    )

    report = render_markdown_report(
        data_packet=data_packet,
        metrics_packet=metrics,
        validation_report=validation,
        claims=[claim],
        evidence_ledger=ledger,
    )

    assert "Evidence IDs: `NVDA_IR_FCF`" in report
