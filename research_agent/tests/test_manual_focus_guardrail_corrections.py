from research_agent.audit.audit_report import AuditIssue, AuditReport
from research_agent.audit.report_linter import audit_markdown_report
from research_agent.content.publish_composer import compose_internal_best_report, compose_manual_review_publish_stub
from research_agent.decision.decision_packet import DecisionPacket, RatingPermission, SignalScores
from research_agent.decision.rating_taxonomy import Rating
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.quality.deeptech_manual_review import CompanyArchetype, assess_speculative_deep_tech_manual_review
from research_agent.quality.quality_score import calculate_quality_score
from research_agent.reconciliation.canonical_financials import CanonicalFinancials, CanonicalMetric
from research_agent.research_core.models.data_packet import DataPacket, PriceBasis
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry
from research_agent.research_core.models.metrics_packet import FundamentalMetrics, MetricsPacket, TechnicalMetrics, ValuationMetrics
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.research_core.validation.data_quality import validate_price_date


def test_qcom_missing_fcf_blocks_plain_accumulate():
    audit = audit_markdown_report(
        markdown="QCOM Rating: Accumulate. FCF TTM and P/FCF are unavailable, but the report is bullish.",
        metrics_packet=_qcom_metrics(fcf=None, p_fcf=None),
        decision_packet=_decision("QCOM", Rating.ACCUMULATE),
        canonical_financials=_canonical_cashflow("QCOM", operating_cash_flow_only=True),
        ticker="QCOM",
    )

    assert audit.has_issue("MISSING_FCF_SUPPORT_FOR_ACCUMULATE", metric="free_cash_flow_ttm")
    assert audit.has_blocking_errors

    quality = calculate_quality_score(
        validation_report=ValidationReport(ticker="QCOM", as_of_date="2026-05-17", has_blocking_errors=False),
        audit_report=audit,
        decision_packet=_decision("QCOM", Rating.ACCUMULATE),
        final_markdown=_strong_report_text("QCOM"),
        analyst_claim_count=24,
        substantive_analyst_claim_count=18,
        substantive_claim_ratio=0.80,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        current_period_kpi_claim_count=5,
        ticker_specific_kpi_claim_count=5,
        final_rating_rationale_quality=85,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=2,
        valuation_specific_claim_count=1,
        technical_specific_claim_count=1,
        rating_rationale_claim_count=1,
        publish_report_exists=1,
        publish_current_kpi_count=5,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=1,
        publish_action_plan_trigger_count=2,
    )

    assert quality.publishable is False
    assert quality.external_display_rating == "Hold Pending FCF Support"
    assert "MISSING_FCF_SUPPORT_FOR_ACCUMULATE" in quality.manual_review_reasons
    assert quality.internal_research_quality_score <= 85


def test_missing_fcf_support_outputs_are_not_clean_accumulate_public_surfaces():
    data_packet = DataPacket(
        ticker="QCOM",
        company_name="Qualcomm",
        as_of_date="2026-05-17",
        price_basis=PriceBasis(date="2026-05-15", close=201.49, source="csv_price_provider"),
        source_registry_id="qcom_sources",
    )
    claims = []
    evidence = EvidenceLedger(ticker="QCOM", as_of_date="2026-05-17", evidence_items=[])
    publish_stub = compose_manual_review_publish_stub(
        data_packet=data_packet,
        metrics_packet=_qcom_metrics(fcf=None, p_fcf=None),
        evidence_ledger=evidence,
        claims=claims,
        external_display_rating="Hold Pending FCF Support",
        reason="MISSING_FCF_SUPPORT_FOR_ACCUMULATE",
    )
    internal_best = compose_internal_best_report(
        data_packet=data_packet,
        metrics_packet=_qcom_metrics(fcf=None, p_fcf=None),
        decision_packet=_decision("QCOM", Rating.ACCUMULATE),
        evidence_ledger=evidence,
        claims=claims,
        status="manual_review",
        publishable=False,
        external_display_rating="Hold Pending FCF Support",
        company_archetype="SEMICONDUCTOR_AI_INFRA",
        quality_score=80,
        publish_quality_score=70,
        internal_research_quality_score=85,
        data_confidence_score=75,
    )

    assert "Hold Pending FCF Support" in publish_stub
    assert "Final Rating: Accumulate" not in publish_stub
    assert "No clean Buy or Accumulate should be shown" in publish_stub
    assert "External display rating: Hold Pending FCF Support" in internal_best
    assert "Internal rating anchor: Accumulate" in internal_best
    assert "Final Rating: Accumulate" not in internal_best


def test_accumulate_allowed_when_current_primary_fcf_support_exists():
    audit = audit_markdown_report(
        markdown="SEMI Rating: Accumulate. FCF support is current-period and evidence-backed.",
        metrics_packet=_qcom_metrics(fcf=14_000_000_000, p_fcf=15.4),
        decision_packet=_decision("SEMI", Rating.ACCUMULATE),
        canonical_financials=_canonical_cashflow("SEMI", operating_cash_flow_only=False),
        ticker="SEMI",
    )

    assert not audit.has_issue("MISSING_FCF_SUPPORT_FOR_ACCUMULATE", metric="free_cash_flow_ttm")


def test_ionq_like_frontier_profile_does_not_default_to_standard_growth():
    metrics = MetricsPacket(
        ticker="IONQ",
        as_of_date="2026-05-17",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=51.95, atr_14=3.1),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=132_800_000,
            operating_income_ttm=-240_000_000,
            free_cash_flow_ttm=-233_300_000,
            sbc_to_revenue=1.462,
        ),
        valuation=ValuationMetrics(market_cap=17_600_000_000, enterprise_value=17_580_000_000, ev_to_sales=132.41),
    )
    assessment = assess_speculative_deep_tech_manual_review(
        markdown="IonQ is a quantum computing frontier-tech company with real revenue but negative FCF.",
        metrics_packet=metrics,
        source_registry=_primary_sources("IONQ"),
    )

    assert assessment.company_archetype == CompanyArchetype.EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH
    assert assessment.company_archetype != CompanyArchetype.STANDARD_GROWTH
    assert assessment.status == "manual_review"
    assert "frontier_real_revenue_extreme_economics" in assessment.archetype_triggered_rules


def test_weekend_friday_close_is_not_price_date_warning():
    assert validate_price_date("2026-05-17", "2026-05-15") is None
    assert validate_price_date("2026-05-18", "2026-05-15")["code"] == "PRICE_DATE_BEFORE_AS_OF_DATE"


def test_internal_quality_score_caps_when_manual_review_reasons_exist():
    quality = calculate_quality_score(
        validation_report=ValidationReport(ticker="NVDA", as_of_date="2026-05-17", has_blocking_errors=False),
        audit_report=AuditReport.from_issues(
            [
                AuditIssue(severity="warning", code="TRUE_FINANCIAL_ANOMALY", message="Manual financial anomaly review."),
            ],
            ticker="NVDA",
        ),
        decision_packet=_decision("NVDA", Rating.HOLD),
        final_markdown=_strong_report_text("NVDA"),
        reconciliation_warnings=[
            {
                "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
                "severity": "warning",
                "count": 10,
            },
            {
                "code": "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED",
                "severity": "warning",
                "metric": "total_debt",
            },
        ],
        analyst_claim_count=30,
        substantive_analyst_claim_count=24,
        substantive_claim_ratio=0.85,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        current_period_kpi_claim_count=6,
        ticker_specific_kpi_claim_count=8,
        final_rating_rationale_quality=90,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=4,
        valuation_specific_claim_count=2,
        technical_specific_claim_count=1,
        rating_rationale_claim_count=1,
        publish_report_exists=1,
        publish_current_kpi_count=6,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=1,
        publish_action_plan_trigger_count=2,
    )

    assert "TRUE_FINANCIAL_ANOMALY" in quality.manual_review_reasons
    assert "TRUE_SOURCE_VALUE_DISAGREEMENT" in quality.manual_review_reasons
    assert "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED" in quality.manual_review_reasons
    assert quality.internal_research_quality_score <= 90
    assert quality.internal_research_quality_score < 100


def test_empty_archetype_required_sections_cap_internal_quality():
    quality = calculate_quality_score(
        validation_report=ValidationReport(ticker="IONQ", as_of_date="2026-05-17", has_blocking_errors=False),
        audit_report=AuditReport.from_issues(
            [
                AuditIssue(
                    severity="error",
                    code="EXTREME_VALUATION_REQUIRES_REVIEW",
                    metric="ev_to_sales",
                    message="Extreme valuation requires review.",
                )
            ],
            ticker="IONQ",
        ),
        decision_packet=_decision("IONQ", Rating.HOLD),
        final_markdown=(
            "# IonQ Internal Draft\n\n"
            "## Business Model Reality\n\nNo evidence-backed discussion is available for this section.\n\n"
            "## Revenue Scale and Backlog\n\nNo evidence-backed discussion is available for this section.\n\n"
            "## FCF Path\n\nNo evidence-backed discussion is available for this section.\n\n"
            "## Final Internal View\n\nManual review required.\n"
        ),
        analyst_claim_count=22,
        substantive_analyst_claim_count=18,
        substantive_claim_ratio=0.82,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        current_period_kpi_claim_count=5,
        ticker_specific_kpi_claim_count=5,
        final_rating_rationale_quality=85,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=3,
        valuation_specific_claim_count=2,
        technical_specific_claim_count=1,
        rating_rationale_claim_count=1,
        publish_report_exists=1,
        publish_current_kpi_count=5,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=1,
        publish_action_plan_trigger_count=2,
        early_commercial_capital_intensive_tech_count=1,
        company_archetype="EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH",
    )

    assert quality.empty_required_section_count >= 3
    assert quality.internal_research_quality_score <= 70


def _qcom_metrics(*, fcf: float | None, p_fcf: float | None) -> MetricsPacket:
    return MetricsPacket(
        ticker="QCOM",
        as_of_date="2026-05-17",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=155, rsi_14=55),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=44_195_000_000,
            operating_income_ttm=11_557_000_000,
            operating_cash_flow_ttm=15_596_000_000,
            free_cash_flow_ttm=fcf,
            sbc_to_revenue=0.065,
        ),
        valuation=ValuationMetrics(market_cap=215_997_000_000, ev_to_sales=4.62, price_to_fcf=p_fcf),
    )


def _canonical_cashflow(ticker: str, *, operating_cash_flow_only: bool) -> CanonicalFinancials:
    metrics = [
        CanonicalMetric(
            metric_name="operating_cash_flow",
            value=15_596_000_000,
            unit="usd",
            period="latest_companyfacts_ttm",
            period_bucket="ttm",
            basis="gaap",
            statement_type="cash_flow",
            source_ids=[f"{ticker}_SEC_CURRENT_PERIOD_COMPANYFACTS_2026_05_15"],
            confidence="high",
            end_date="2026-05-15",
        )
    ]
    if not operating_cash_flow_only:
        metrics.append(
            CanonicalMetric(
                metric_name="free_cash_flow",
                value=14_000_000_000,
                unit="usd",
                period="latest_companyfacts_ttm",
                period_bucket="ttm",
                basis="gaap",
                statement_type="cash_flow",
                source_ids=[f"{ticker}_SEC_CURRENT_PERIOD_COMPANYFACTS_2026_05_15"],
                confidence="high",
                end_date="2026-05-15",
            )
        )
    return CanonicalFinancials(ticker=ticker, as_of_date="2026-05-17", metrics=metrics)


def _primary_sources(ticker: str) -> SourceRegistry:
    return SourceRegistry(
        registry_id=f"{ticker.lower()}_primary",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker}_10q",
                ticker=ticker,
                source_type="sec_filing",
                used_for=["revenue_ttm", "operating_income", "free_cash_flow_ttm", "financials", "sbc"],
            )
        ],
    )


def _decision(ticker: str, rating: Rating) -> DecisionPacket:
    return DecisionPacket(
        ticker=ticker,
        as_of_date="2026-05-17",
        signal_scores=SignalScores(fundamental_score=60, technical_score=55, valuation_score=45, risk_score=40, composite_score=55),
        rating_permission=RatingPermission(
            allowed_ratings=[Rating.HOLD, Rating.ACCUMULATE, Rating.UNDERWEIGHT],
            blocked_ratings=[Rating.BUY, Rating.STRONG_BUY],
            preferred_rating=rating,
            reason="Test decision.",
        ),
    )


def _strong_report_text(ticker: str) -> str:
    return f"""
    # {ticker} Report
    ## Executive Summary
    Current-period KPIs, revenue, margin, FCF and valuation are discussed with evidence.
    ## Investment Thesis
    The rating logic is company-specific and identifies data gaps and risk.
    ## Fundamental Analysis
    Revenue and operating evidence are connected to cash conversion.
    ## Valuation / Multiples
    EV/Sales, P/FCF and scenario sensitivity are included.
    ## Technical Setup
    Technical setup is timing only.
    ## Key Risks
    Source disagreement, FCF anomaly and valuation risk are explicit.
    ## Scenario / Triggers
    Improve if FCF conversion and current-period KPIs improve; reduce risk if evidence weakens.
    ## Final Rating and Action
    Hold until the next current-period evidence point confirms cash conversion.
    ## Follow-up Checklist
    Recheck FCF, source reconciliation and valuation support.
    """
