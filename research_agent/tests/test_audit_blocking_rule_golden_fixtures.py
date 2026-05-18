import json
from pathlib import Path
from typing import Optional

import pytest

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.audit.rule_registry import AUDIT_RULE_BY_ID
from research_agent.decision.decision_packet import DecisionPacket, RatingPermission, SignalScores
from research_agent.decision.rating_taxonomy import Rating
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
)
from research_agent.research_core.models.validation_report import ValidationReport


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "rule_id,audit_factory",
    [
        ("NUMERIC_MISMATCH", lambda: _audit_existing_fixture("nvda_2026_05_01")),
        ("PERIOD_MISMATCH", lambda: _audit_existing_fixture("nvda_2026_05_01")),
        ("RATING_BLOCKED_BY_DECISION_PACKET", lambda: _blocked_rating_audit()),
        ("MISSING_EVIDENCE_FOR_HARD_CLAIM", lambda: _missing_evidence_audit()),
        ("UNSUPPORTED_GUIDANCE_CLAIM", lambda: _unsupported_guidance_audit()),
        ("NO_NEWS_WITH_AVAILABLE_SOURCES", lambda: _no_news_contradiction_audit()),
        ("CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED", lambda: _current_period_ir_audit()),
    ],
)
def test_critical_blocking_rules_have_golden_fixtures(rule_id, audit_factory):
    audit = audit_factory()

    assert audit.has_issue(rule_id)
    assert audit.has_blocking_errors
    assert AUDIT_RULE_BY_ID[rule_id].public_gate_effect == "blocks_publish"


def _audit_existing_fixture(name: str):
    return audit_markdown_report(
        markdown=_load_fixture(name, "bad_report.md"),
        metrics_packet=MetricsPacket(**_load_fixture(name, "metrics_packet.json")),
        validation_report=ValidationReport(**_load_fixture(name, "validation_report.json")),
        source_registry=SourceRegistry(**_load_fixture(name, "source_registry.json")),
    )


def _blocked_rating_audit():
    return audit_markdown_report(
        markdown="## Final Rating\nBuy.",
        metrics_packet=_base_metrics(ticker="TST", free_cash_flow_ttm=1_000_000_000),
        decision_packet=_decision("TST", preferred=Rating.HOLD, blocked=[Rating.BUY]),
        ticker="TST",
    )


def _missing_evidence_audit():
    return audit_markdown_report(
        markdown="FCF TTM was $96.575B.",
        metrics_packet=_base_metrics(ticker="NVDA", free_cash_flow_ttm=96_575_000_000),
        evidence_ledger=EvidenceLedger(ticker="NVDA", as_of_date="2026-05-01"),
        ticker="NVDA",
    )


def _unsupported_guidance_audit():
    return audit_markdown_report(
        markdown="Management guidance implies a stronger FY2027 EPS outlook.",
        metrics_packet=_base_metrics(ticker="NVDA"),
        evidence_ledger=EvidenceLedger(ticker="NVDA", as_of_date="2026-05-01"),
        ticker="NVDA",
    )


def _no_news_contradiction_audit():
    return audit_markdown_report(
        markdown="No relevant news found for the company.",
        metrics_packet=_base_metrics(ticker="AMZN"),
        source_registry=SourceRegistry(
            registry_id="AMZN_sources",
            sources=[
                SourceRegistryEntry(
                    source_id="AMZN_REUTERS",
                    ticker="AMZN",
                    source_type="reuters",
                    authority_rank=2,
                    used_for=["news"],
                )
            ],
        ),
        ticker="AMZN",
    )


def _current_period_ir_audit():
    return audit_markdown_report(
        markdown="## Executive Summary\nValidated current-period skeleton.",
        metrics_packet=_base_metrics(
            ticker="AMZN",
            as_of_date="2026-05-05",
            revenue_ttm=700_000_000_000,
            free_cash_flow_ttm=10_000_000_000,
        ),
        ticker="AMZN",
    )


def _base_metrics(
    *,
    ticker: str,
    as_of_date: str = "2026-05-01",
    revenue_ttm: Optional[float] = 100_000_000_000,
    free_cash_flow_ttm: Optional[float] = 5_000_000_000,
) -> MetricsPacket:
    return MetricsPacket(
        ticker=ticker,
        as_of_date=as_of_date,
        technical=TechnicalMetrics(indicator_date=as_of_date, close=100),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=revenue_ttm,
            operating_income_ttm=20_000_000_000,
            free_cash_flow_ttm=free_cash_flow_ttm,
        ),
        valuation=ValuationMetrics(market_cap=500_000_000_000, enterprise_value=480_000_000_000),
    )


def _decision(ticker: str, *, preferred: Rating, blocked: list[Rating]) -> DecisionPacket:
    return DecisionPacket(
        ticker=ticker,
        as_of_date="2026-05-01",
        signal_scores=SignalScores(
            fundamental_score=50,
            technical_score=50,
            valuation_score=50,
            risk_score=50,
            composite_score=50,
        ),
        rating_permission=RatingPermission(
            allowed_ratings=[rating for rating in Rating if rating not in blocked],
            blocked_ratings=blocked,
            preferred_rating=preferred,
            reason="Golden fixture decision packet.",
        ),
    )


def _load_fixture(name: str, filename: str):
    path = FIXTURES / name / filename
    if filename.endswith(".json"):
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")
