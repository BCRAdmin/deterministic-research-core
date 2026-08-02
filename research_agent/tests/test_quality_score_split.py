from pathlib import Path

from research_agent.audit.audit_report import AuditIssue, AuditReport
from research_agent.batch.batch_manifest import BatchManifest, BatchRunItem
from research_agent.batch.dashboard_adapter import build_dashboard_status
from research_agent.decision.decision_packet import DecisionPacket, RatingPermission, SignalScores
from research_agent.decision.rating_taxonomy import Rating
from research_agent.quality.quality_score import calculate_quality_score
from research_agent.research_core.models.validation_report import (
    ValidationIssue,
    ValidationReport,
)


def test_manual_review_can_have_high_internal_quality():
    quality = calculate_quality_score(
        validation_report=_validation("RKLB"),
        audit_report=_audit(
            "RKLB",
            [
                AuditIssue(
                    severity="error",
                    code="EXTREME_VALUATION_REQUIRES_REVIEW",
                    message="EV/Sales is extreme but evidence-backed.",
                )
            ],
        ),
        decision_packet=_decision("RKLB", Rating.HOLD),
        final_markdown=_strong_rklb_internal_text(),
        reconciliation_warnings=[
            {"code": "TRUE_SOURCE_VALUE_DISAGREEMENT", "severity": "warning", "count": 2}
        ],
        analyst_claim_count=24,
        substantive_analyst_claim_count=16,
        substantive_claim_ratio=0.75,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        current_period_kpi_claim_count=6,
        current_period_kpi_metric_count=6,
        ticker_specific_kpi_claim_count=10,
        final_rating_rationale_quality=80,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=3,
        valuation_specific_claim_count=2,
        technical_specific_claim_count=1,
        rating_rationale_claim_count=1,
        publish_report_exists=1,
        publish_current_kpi_count=1,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=1,
        publish_action_plan_trigger_count=2,
        early_commercial_capital_intensive_tech_count=1,
        deeptech_sec_ir_current_period_evidence_complete=True,
        company_archetype="EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH",
        archetype_confidence=1.0,
        archetype_triggered_rules=["revenue_ttm_gt_100m", "ev_sales_gt_20"],
    )

    assert quality.publishable is False
    assert quality.publish_quality_score < quality.internal_research_quality_score
    assert 60 <= quality.publish_quality_score <= 70
    assert 75 <= quality.internal_research_quality_score <= 85
    assert quality.external_display_rating == "Manual Review / Hold Pending FCF and Execution Evidence"


def test_rgti_vendor_only_low_publish_but_useful_internal():
    quality = calculate_quality_score(
        validation_report=_validation("RGTI"),
        audit_report=_audit(
            "RGTI",
            [
                AuditIssue(severity="warning", code="VENDOR_SOURCE_USED_AS_PRIMARY", message="Vendor hard metrics."),
                AuditIssue(severity="warning", code="VENDOR_ONLY_HARD_METRICS", message="Vendor-only hard metrics."),
            ],
        ),
        decision_packet=_decision("RGTI", Rating.UNDERWEIGHT),
        final_markdown=_strong_rgti_internal_text(),
        analyst_claim_count=22,
        substantive_analyst_claim_count=15,
        substantive_claim_ratio=0.75,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        data_limitation_claim_count=2,
        current_period_kpi_claim_count=3,
        ticker_specific_kpi_claim_count=5,
        final_rating_rationale_quality=80,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=3,
        valuation_specific_claim_count=2,
        technical_specific_claim_count=1,
        rating_rationale_claim_count=1,
        publish_report_exists=1,
        publish_current_kpi_count=3,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=1,
        publish_action_plan_trigger_count=2,
        speculative_deep_tech_profile_count=1,
        vendor_only_hard_metrics_count=1,
        deeptech_sec_ir_current_period_evidence_complete=False,
        company_archetype="SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL",
        archetype_confidence=0.83,
        archetype_triggered_rules=["vendor_only_hard_financial_metrics", "revenue_ttm_lt_50m"],
    )

    assert quality.publishable is False
    assert quality.publish_quality_score <= 70
    assert quality.internal_research_quality_score >= 75
    assert quality.data_confidence_score < quality.internal_research_quality_score
    assert quality.external_display_rating == "Manual Review / Preliminary Underweight"


def test_gold_report_scores_high_on_all_three():
    quality = calculate_quality_score(
        validation_report=_validation("GOOGL"),
        audit_report=_audit("GOOGL"),
        decision_packet=_decision("GOOGL", Rating.HOLD),
        final_markdown=_gold_text(),
        analyst_claim_count=9,
        substantive_analyst_claim_count=7,
        substantive_claim_ratio=7 / 9,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        data_limitation_claim_count=0,
        current_period_kpi_claim_count=6,
        current_period_kpi_metric_count=6,
        ticker_specific_kpi_claim_count=8,
        final_rating_rationale_quality=90,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=4,
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
    )

    assert quality.publishable is True
    assert quality.publish_quality_score >= 85
    assert quality.internal_research_quality_score >= 85
    assert quality.data_confidence_score >= 80


def test_manual_review_reason_blocks_compact_complete_report():
    validation = _validation("MCD").model_copy(
        update={
            "issues": [
                ValidationIssue(
                    severity="warning",
                    code="EARNINGS_DATE_UNAVAILABLE",
                    message="Next earnings date is unavailable.",
                )
            ]
        }
    )
    quality = calculate_quality_score(
        validation_report=validation,
        audit_report=_audit("MCD"),
        decision_packet=_decision("MCD", Rating.HOLD),
        final_markdown=_gold_text(),
        analyst_claim_count=9,
        substantive_analyst_claim_count=7,
        substantive_claim_ratio=7 / 9,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        data_limitation_claim_count=0,
        current_period_kpi_claim_count=6,
        current_period_kpi_metric_count=6,
        ticker_specific_kpi_claim_count=8,
        final_rating_rationale_quality=90,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=4,
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
    )

    assert quality.publishable is False
    assert quality.manual_review_reasons == ["EARNINGS_DATE_UNAVAILABLE"]


def test_good_data_bad_writing_split():
    quality = calculate_quality_score(
        validation_report=_validation("GOOD"),
        audit_report=_audit("GOOD"),
        decision_packet=_decision("GOOD", Rating.HOLD),
        final_markdown="# Report\n\nRevenue is supported, but the write-up is generic.",
        analyst_claim_count=5,
        substantive_analyst_claim_count=3,
        substantive_claim_ratio=0.40,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        current_period_kpi_claim_count=1,
        ticker_specific_kpi_claim_count=1,
        final_rating_rationale_quality=35,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.80,
        company_specific_claim_count=1,
        valuation_specific_claim_count=0,
        technical_specific_claim_count=0,
        rating_rationale_claim_count=0,
        publish_report_exists=1,
        publish_current_kpi_count=1,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=0,
        publish_action_plan_trigger_count=0,
    )

    assert quality.data_confidence_score >= 80
    assert quality.internal_research_quality_score < quality.data_confidence_score
    assert quality.publish_quality_score < 85
    assert quality.publishable is False


def test_good_text_missing_evidence_split():
    quality = calculate_quality_score(
        validation_report=_validation("TEXT"),
        audit_report=_audit(
            "TEXT",
            [
                AuditIssue(
                    severity="error",
                    code="MISSING_EVIDENCE_FOR_HARD_CLAIM",
                    message="Hard claim has no evidence.",
                )
            ],
        ),
        decision_packet=_decision("TEXT", Rating.HOLD),
        final_markdown=_gold_text(),
        analyst_claim_count=22,
        substantive_analyst_claim_count=18,
        substantive_claim_ratio=0.80,
        evidence_mapped_claim_ratio=0.65,
        hard_claim_evidence_ratio=0.45,
        current_period_kpi_claim_count=5,
        ticker_specific_kpi_claim_count=5,
        final_rating_rationale_quality=85,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=3,
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

    assert 50 <= quality.internal_research_quality_score <= 70
    assert quality.publish_quality_score < 70
    assert quality.data_confidence_score < 60
    assert quality.publishable is False


def test_publishable_never_depends_on_internal_score():
    quality = calculate_quality_score(
        validation_report=_validation("RKLB"),
        audit_report=_audit(
            "RKLB",
            [
                AuditIssue(
                    severity="error",
                    code="EXTREME_VALUATION_REQUIRES_REVIEW",
                    message="EV/Sales is extreme but evidence-backed.",
                )
            ],
        ),
        decision_packet=_decision("RKLB", Rating.HOLD),
        final_markdown=_strong_rklb_internal_text(),
        analyst_claim_count=24,
        substantive_analyst_claim_count=16,
        substantive_claim_ratio=0.75,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        current_period_kpi_claim_count=6,
        ticker_specific_kpi_claim_count=10,
        final_rating_rationale_quality=80,
        mechanical_rating_language_count=0,
        generic_claim_ratio=0.0,
        company_specific_claim_count=3,
        valuation_specific_claim_count=2,
        technical_specific_claim_count=1,
        rating_rationale_claim_count=1,
        publish_report_exists=1,
        publish_current_kpi_count=1,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=1,
        publish_action_plan_trigger_count=2,
        early_commercial_capital_intensive_tech_count=1,
        deeptech_sec_ir_current_period_evidence_complete=True,
    )

    assert quality.internal_research_quality_score >= 75
    assert quality.publishable is False


def test_dashboard_surfaces_score_split(tmp_path: Path):
    quality_path = tmp_path / "quality_score.json"
    quality_path.write_text(
        """
        {
          "total_score": 65,
          "publish_quality_score": 65,
          "internal_research_quality_score": 78,
          "data_confidence_score": 72,
          "score_explanation_short": "Manual review due to negative FCF and extreme valuation.",
          "company_archetype": "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH"
        }
        """,
        encoding="utf-8",
    )
    item = BatchRunItem(
        ticker="RKLB",
        status="manual_review",
        quality_score=65,
        publishable=False,
        artifacts={"quality_score.json": str(quality_path)},
    )

    dashboard = build_dashboard_status(
        BatchManifest(batch_id="score_split", as_of_date="2026-05-15", status="completed_with_issues", items=[item])
    )

    dashboard_item = dashboard["items"][0]
    assert dashboard_item["publish_quality_score"] == 65
    assert dashboard_item["internal_research_quality_score"] == 78
    assert dashboard_item["data_confidence_score"] == 72
    assert dashboard_item["total_score_legacy"] == 65
    assert dashboard_item["score_explanation_short"].startswith("Manual review")
    assert dashboard["summary"]["avg_publish_quality_score"] == 65
    assert dashboard["summary"]["avg_internal_research_quality_score"] == 78
    assert dashboard["summary"]["avg_data_confidence_score"] == 72


def _validation(ticker: str) -> ValidationReport:
    return ValidationReport(ticker=ticker, as_of_date="2026-05-15", has_blocking_errors=False)


def _audit(ticker: str, issues: list[AuditIssue] | None = None) -> AuditReport:
    return AuditReport.from_issues(issues or [], ticker=ticker)


def _decision(ticker: str, rating: Rating) -> DecisionPacket:
    return DecisionPacket(
        ticker=ticker,
        as_of_date="2026-05-15",
        signal_scores=SignalScores(
            fundamental_score=50,
            technical_score=50,
            valuation_score=50,
            risk_score=50,
            composite_score=50,
        ),
        rating_permission=RatingPermission(
            allowed_ratings=[Rating.HOLD, Rating.UNDERWEIGHT, Rating.TACTICAL_UNDERWEIGHT],
            blocked_ratings=[Rating.BUY, Rating.ACCUMULATE, Rating.STRONG_BUY],
            preferred_rating=rating,
            reason="Test decision.",
        ),
    )


def _strong_rklb_internal_text() -> str:
    return """
    # Rocket Lab (RKLB) — Interne Research-Lesefassung
    ## Executive Summary
    TTM revenue is $622.5M, Q1 revenue is $200.3M, backlog is above $2.20B, FCF is $-220.1M and EV/Sales is 118.78x.
    ## Investment Thesis
    Manual review is required because negative FCF, capital intensity, Neutron risk and valuation are not publishable as a clean Buy.
    ## Key Bull Points
    Backlog conversion, Electron/HASTE cadence and Space Systems revenue are real commercial evidence.
    ## Key Bear Points
    Neutron delay, persistent FCF losses and valuation expansion without cash conversion are the key risks.
    ## Valuation / Multiples
    EV/Sales is extreme and becomes more plausible only if backlog converts into revenue and FCF improves.
    ## Technical Setup
    Technical setup is timing only.
    ## Risk Section
    The report names execution, funding and contract timing risk.
    ## Scenario / Triggers
    What would improve the view: backlog conversion and narrowing FCF losses. What would weaken the view: Neutron delay.
    ## Final Rating and Action
    Hold pending FCF and execution evidence.
    ## Follow-up Checklist
    Recheck backlog conversion, Neutron timing and FCF path.
    """


def _strong_rgti_internal_text() -> str:
    return """
    # RGTI Internal Risk Note
    ## Executive Summary
    RGTI is a speculative deep-tech manual review case, not a public report.
    ## Investment Thesis
    The internal note is useful because it explains vendor-heavy hard metrics, revenue below $50M, negative FCF and milestone risk.
    ## Key Bull Points
    The possible upside depends on validated orders, adoption and future SEC/IR support.
    ## Key Bear Points
    Market-cap/revenue is extreme, commercial adoption is limited and hard metrics are vendor-heavy.
    ## Valuation / Multiples
    Valuation cannot be defended without stronger primary evidence.
    ## Technical Setup
    Technicals are timing only and must not dominate the thesis.
    ## Risk Section
    Data limitations, derivative accounting and order materiality risks are clearly marked.
    ## Scenario / Triggers
    What would improve the view: SEC/IR evidence, quantified orders and commercial adoption.
    ## Final Rating and Action
    Preliminary Underweight for public display, useful internally as a deep-tech risk note.
    ## Follow-up Checklist
    Reconfirm SEC/IR evidence and order materiality.
    """


def _gold_text() -> str:
    return """
    # GOOGL Gold-v1 Report
    ## Executive Summary
    Current-period KPIs, revenue, Cloud growth, operating margin and FCF support a coherent internal and public report.
    ## Investment Thesis
    The rating logic is evidence-backed and company-specific.
    ## Key Bull Points
    Revenue, Cloud and FCF support the thesis.
    ## Key Bear Points
    Capex, valuation and regulatory risk are concrete.
    ## Valuation / Multiples
    Scenario sensitivity and valuation discipline are included.
    ## Technical Setup
    Technical setup is timing only.
    ## Risk Section
    Risks are specific and connected to rating logic.
    ## Scenario / Triggers
    Action triggers and sensitivity are clear.
    ## Final Rating and Action
    Hold with coherent rating logic and evidence support.
    """
