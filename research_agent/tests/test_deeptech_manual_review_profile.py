from pathlib import Path

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.batch.batch_manifest import BatchManifest, BatchRunItem
from research_agent.batch.dashboard_adapter import build_dashboard_status
from research_agent.batch.display_policy import external_rating_payload
from research_agent.decision.decision_packet import DecisionPacket, RatingPermission, SignalScores
from research_agent.decision.rating_taxonomy import Rating
from research_agent.quality.deeptech_manual_review import (
    ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND,
    CompanyArchetype,
    EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING,
    EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE,
    EVIDENCE_INCOMPLETE_FOR_GOLD,
    MANUAL_REVIEW_EVIDENCE_INCOMPLETE_DISPLAY_RATING,
    MANUAL_REVIEW_DISPLAY_RATING,
    ORDER_MATERIALITY_MISSING,
    SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE,
    TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS,
    VENDOR_ONLY_HARD_METRICS,
    assess_speculative_deep_tech_manual_review,
)
from research_agent.quality.quality_score import calculate_quality_score
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry
from research_agent.research_core.models.metrics_packet import FundamentalMetrics, MetricsPacket, TechnicalMetrics, ValuationMetrics
from research_agent.research_core.models.validation_report import ValidationReport


def _rgti_metrics() -> MetricsPacket:
    return MetricsPacket(
        ticker="RGTI",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=17.0),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=7_090_000,
            operating_income_ttm=-75_000_000,
            free_cash_flow_ttm=-77_200_000,
            sbc_to_revenue=2.48,
        ),
        valuation=ValuationMetrics(market_cap=6_340_000_000),
    )


def _vendor_sources() -> SourceRegistry:
    return SourceRegistry(
        registry_id="rgti_vendor",
        sources=[
            SourceRegistryEntry(source_id="yf_revenue", ticker="RGTI", source_type="yahoo_finance", used_for=["revenue_ttm", "free_cash_flow_ttm", "sbc"]),
        ],
    )


def _rklb_metrics() -> MetricsPacket:
    return MetricsPacket(
        ticker="RKLB",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=124.77, atr_14=8.89, rsi_14=70.82),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=622_495_000,
            operating_income_ttm=-233_765_000,
            free_cash_flow_ttm=-220_123_000,
            sbc_to_revenue=0.12,
        ),
        valuation=ValuationMetrics(
            market_cap=75_540_078_250,
            enterprise_value=73_938_534_250,
            ev_to_sales=118.78,
        ),
    )


def _space_infrastructure_sources() -> SourceRegistry:
    return SourceRegistry(
        registry_id="rklb_primary",
        sources=[
            SourceRegistryEntry(
                source_id="rklb_10q",
                ticker="RKLB",
                source_type="sec_filing",
                used_for=["revenue_ttm", "operating_income", "free_cash_flow_ttm", "financials", "cash"],
            ),
            SourceRegistryEntry(
                source_id="rklb_ir",
                ticker="RKLB",
                source_type="company_ir",
                used_for=[
                    "current_q_revenue",
                    "backlog",
                    "contract_backlog",
                    "contracted_missions",
                    "launch_cadence",
                    "electron_execution",
                    "neutron_development_risk",
                    "product_revenue",
                    "space_systems_revenue",
                    "service_revenue",
                    "launch_services_revenue",
                    "free_cash_flow",
                ],
            ),
        ],
    )


def _rklb_text() -> str:
    return """
    This company has real commercial space-infrastructure revenue, TTM revenue of $622.5M, Q1 revenue of $200.3M,
    backlog above $2.2B, contracted missions, launch manifest, Electron launch cadence, Space Systems/product revenue,
    Launch Services/service revenue, and a Neutron development program.
    It remains capital-intensive with major execution milestone risk, high volatility, negative operating income,
    negative FCF and EV/Sales above 100x. Contract value, delivery revenue timing, market cap, annual revenue,
    recurring versus one-off programmatic revenue, commercial/government mix and valuation support are discussed.
    """


def _decision(rating: Rating = Rating.UNDERWEIGHT) -> DecisionPacket:
    return DecisionPacket(
        ticker="RGTI",
        as_of_date="2026-05-15",
        signal_scores=SignalScores(fundamental_score=20, technical_score=20, valuation_score=5, risk_score=90, composite_score=30),
        rating_permission=RatingPermission(
            allowed_ratings=[Rating.HOLD, Rating.UNDERWEIGHT, Rating.TACTICAL_UNDERWEIGHT],
            blocked_ratings=[Rating.BUY, Rating.ACCUMULATE, Rating.STRONG_BUY],
            preferred_rating=rating,
            reason="Speculative deep-tech manual review.",
        ),
    )


def _rgti_text() -> str:
    return """
    # RGTI report
    Rating: Underweight
    RGTI is an early commercial quantum hardware story stock. Market cap / revenue is above 800x.
    Revenue TTM is $7.09M, operating income remains negative, free cash flow is negative, and SBC / revenue is 248%.
    Hard financial metrics are vendor-only and no SEC/IR current-period evidence is available.
    Loss narrowed and GAAP net income improved after derivative and warrant fair-value effects.
    Beta: 1.8. Adoption is limited commercial adoption and not scaled.
    The report mentions a defense contract, roadmap milestone, and order but lacks a quantified materiality bridge.
    """


def test_rgti_profile_is_manual_review_and_not_publishable():
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=_rgti_text(),
        metrics_packet=_rgti_metrics(),
        source_registry=_vendor_sources(),
    )
    codes = {issue.code for issue in assessment.issues}

    assert assessment.active
    assert assessment.status == "manual_review"
    assert assessment.publishable is False
    assert assessment.external_display_rating == MANUAL_REVIEW_DISPLAY_RATING
    assert assessment.company_archetype == CompanyArchetype.SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL
    assert assessment.archetype_confidence > 0.25
    assert "vendor_only_hard_financial_metrics" in assessment.archetype_triggered_rules
    assert SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE in codes
    assert VENDOR_ONLY_HARD_METRICS in codes
    assert ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND in codes
    assert ORDER_MATERIALITY_MISSING in codes


def test_rklb_triggers_early_commercial_capital_intensive_not_speculative():
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=_rklb_text(),
        metrics_packet=_rklb_metrics(),
        source_registry=_space_infrastructure_sources(),
        rating_text="Rating: Hold. FCF path, execution milestones and valuation discipline block clean Accumulate.",
    )
    codes = {issue.code for issue in assessment.issues}

    assert assessment.status == "manual_review"
    assert assessment.publishable is False
    assert assessment.company_archetype == CompanyArchetype.EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH
    assert assessment.company_archetype != CompanyArchetype.SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL
    assert assessment.counts["early_commercial_capital_intensive_tech_count"] == 1
    assert assessment.counts["speculative_deep_tech_profile_count"] == 0
    assert assessment.external_display_rating == EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING
    assert EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE in codes
    assert SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE not in codes
    assert "backlog_contracts_or_contracted_missions_present" in assessment.archetype_triggered_rules
    assert "current_period_evidence_exists_but_fcf_path_negative" in assessment.archetype_triggered_rules


def test_quality_score_caps_and_blocks_publishability_for_rgti_profile():
    audit = audit_markdown_report(
        markdown=_rgti_text(),
        metrics_packet=_rgti_metrics(),
        source_registry=_vendor_sources(),
        decision_packet=_decision(),
        ticker="RGTI",
    )
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=_rgti_text(),
        metrics_packet=_rgti_metrics(),
        source_registry=_vendor_sources(),
    )
    quality = calculate_quality_score(
        validation_report=ValidationReport(ticker="RGTI", as_of_date="2026-05-15", has_blocking_errors=False),
        audit_report=audit,
        decision_packet=_decision(),
        final_markdown=_rgti_text(),
        analyst_claim_count=20,
        evidence_mapped_claim_ratio=1.0,
        hard_claim_evidence_ratio=1.0,
        substantive_analyst_claim_count=20,
        substantive_claim_ratio=1.0,
        current_period_kpi_claim_count=3,
        ticker_specific_kpi_claim_count=3,
        final_rating_rationale_quality=80,
        mechanical_rating_language_count=0,
        company_specific_claim_count=1,
        valuation_specific_claim_count=1,
        technical_specific_claim_count=1,
        rating_rationale_claim_count=1,
        publish_report_exists=1,
        publish_current_kpi_count=3,
        publish_evidence_appendix_exists=1,
        publish_mechanical_language_count=0,
        publish_claim_id_main_body_count=0,
        publish_valuation_sensitivity_present=1,
        publish_action_plan_trigger_count=2,
        **assessment.to_quality_payload(),
    )

    assert quality.publishable is False
    assert quality.total_score <= 70
    assert quality.external_display_rating == MANUAL_REVIEW_DISPLAY_RATING
    assert quality.company_archetype == CompanyArchetype.SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL.value
    assert "vendor_only_hard_financial_metrics" in quality.archetype_triggered_rules
    assert SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE in quality.risk_profiles


def test_technical_dominance_guard_and_dashboard_counts(tmp_path: Path):
    metrics = _rgti_metrics()
    text = _rgti_text()
    rating_text = """
    Rating: Underweight. The rating rationale is technical because the chart lost the 200-day SMA.
    The investment thesis is technical because RSI, MACD, support, and resistance dominate the decision.
    The decision is technical because momentum defines the long-term view.
    """
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=text,
        metrics_packet=metrics,
        source_registry=_vendor_sources(),
        rating_text=rating_text,
    )
    assert TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS in {issue.code for issue in assessment.issues}

    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text(
        '{"issues":[{"code":"SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE"},{"code":"VENDOR_ONLY_HARD_METRICS"}]}',
        encoding="utf-8",
    )
    item = BatchRunItem(
        ticker="RGTI",
        status="manual_review",
        counts=assessment.counts,
        artifacts={"audit_report.json": str(audit_path)},
        publishable=False,
    )
    dashboard = build_dashboard_status(BatchManifest(batch_id="rgti_deeptech_profile_check", as_of_date="2026-05-15", status="completed_with_issues", items=[item]))
    display = external_rating_payload(item)

    assert dashboard["summary"]["speculative_deep_tech_profile_count"] == 1
    assert dashboard["summary"]["vendor_only_hard_metrics_count"] == 1
    assert display["display_rating"] == MANUAL_REVIEW_DISPLAY_RATING


def test_order_materiality_requires_recurring_and_counterparty_classification():
    incomplete = """
    RGTI is an early commercial quantum hardware story stock.
    Revenue TTM is below $50M, operating income and free cash flow are negative, and beta is 1.8.
    The report mentions a defense contract and roadmap milestone.
    Contract value is $5M, delivery revenue timing is over 24 months, contract value vs market cap is immaterial,
    contract value vs annual revenue is material, and the valuation support is limited.
    """
    incomplete_assessment = assess_speculative_deep_tech_manual_review(
        markdown=incomplete,
        metrics_packet=_rgti_metrics(),
        source_registry=_vendor_sources(),
    )
    assert ORDER_MATERIALITY_MISSING in {issue.code for issue in incomplete_assessment.issues}

    complete = incomplete + " The contract is one-off rather than recurring, and it is a government research/prototype contract rather than scaled commercial adoption."
    complete_assessment = assess_speculative_deep_tech_manual_review(
        markdown=complete,
        metrics_packet=_rgti_metrics(),
        source_registry=_vendor_sources(),
    )
    assert ORDER_MATERIALITY_MISSING not in {issue.code for issue in complete_assessment.issues}


def test_gold_v1_primary_evidence_does_not_trigger_and_qcom_rule_still_wins(tmp_path: Path):
    metrics = MetricsPacket(
        ticker="GOOGL",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=175),
        fundamentals=FundamentalMetrics(fiscal_period="TTM", revenue_ttm=350_000_000_000, operating_income_ttm=100_000_000_000, free_cash_flow_ttm=65_000_000_000, sbc_to_revenue=0.04),
        valuation=ValuationMetrics(market_cap=2_000_000_000_000),
    )
    sources = SourceRegistry(
        registry_id="googl_primary",
        sources=[SourceRegistryEntry(source_id="sec_10q", ticker="GOOGL", source_type="sec_filing", used_for=["revenue_ttm", "free_cash_flow_ttm", "financials"])],
    )
    assessment = assess_speculative_deep_tech_manual_review(markdown="GOOGL large-cap SEC/IR report.", metrics_packet=metrics, source_registry=sources)
    assert not assessment.active
    assert assessment.company_archetype == CompanyArchetype.MEGA_CAP_PLATFORM

    audit_path = tmp_path / "audit_report.json"
    audit_path.write_text('{"issues":[{"code":"MISSING_FCF_SUPPORT_FOR_ACCUMULATE"}]}', encoding="utf-8")
    qcom = BatchRunItem(ticker="QCOM", status="manual_review", final_rating="Accumulate", preferred_rating="Accumulate", artifacts={"audit_report.json": str(audit_path)})
    display = external_rating_payload(qcom)
    assert display["display_rating"] == "Hold Pending FCF Support"


def test_saas_and_real_revenue_high_growth_do_not_trigger_archetype():
    snow = MetricsPacket(
        ticker="SNOW",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=180),
        fundamentals=FundamentalMetrics(fiscal_period="TTM", revenue_ttm=4_500_000_000, operating_income_ttm=-1_000_000_000, free_cash_flow_ttm=1_000_000_000, sbc_to_revenue=0.25),
        valuation=ValuationMetrics(market_cap=70_000_000_000),
    )
    primary_sources = SourceRegistry(
        registry_id="snow_primary",
        sources=[SourceRegistryEntry(source_id="sec_10q", ticker="SNOW", source_type="sec_filing", used_for=["revenue_ttm", "free_cash_flow_ttm", "financials"])],
    )
    snow_assessment = assess_speculative_deep_tech_manual_review(
        markdown="SNOW is a SaaS consumption company with high valuation but scaled commercial adoption.",
        metrics_packet=snow,
        source_registry=primary_sources,
    )
    real_revenue = MetricsPacket(
        ticker="REAL",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=50),
        fundamentals=FundamentalMetrics(fiscal_period="TTM", revenue_ttm=800_000_000, operating_income_ttm=-50_000_000, free_cash_flow_ttm=-20_000_000, sbc_to_revenue=0.08),
        valuation=ValuationMetrics(market_cap=36_000_000_000),
    )
    real_assessment = assess_speculative_deep_tech_manual_review(
        markdown="High-growth real revenue company with scaled commercial adoption and SEC/IR evidence.",
        metrics_packet=real_revenue,
        source_registry=primary_sources,
    )

    assert not snow_assessment.active
    assert snow_assessment.company_archetype == CompanyArchetype.SAAS_CONSUMPTION
    assert not real_assessment.active
    assert real_assessment.company_archetype == CompanyArchetype.STANDARD_GROWTH


def test_saas_ticker_outweighs_generic_platform_language():
    ddog = MetricsPacket(
        ticker="DDOG",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=145),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=2_700_000_000,
            operating_income_ttm=-50_000_000,
            free_cash_flow_ttm=700_000_000,
            sbc_to_revenue=0.2,
        ),
        valuation=ValuationMetrics(market_cap=48_000_000_000),
    )
    primary_sources = SourceRegistry(
        registry_id="ddog_primary",
        sources=[
            SourceRegistryEntry(
                source_id="sec_10q",
                ticker="DDOG",
                source_type="sec_filing",
                used_for=["revenue_ttm", "free_cash_flow_ttm", "financials"],
            )
        ],
    )

    assessment = assess_speculative_deep_tech_manual_review(
        markdown="Datadog is a SaaS observability platform with scaled commercial adoption.",
        metrics_packet=ddog,
        source_registry=primary_sources,
    )

    assert not assessment.active
    assert assessment.company_archetype == CompanyArchetype.SAAS_CONSUMPTION


def test_msft_not_deeptech_archetype():
    metrics = MetricsPacket(
        ticker="MSFT",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=409),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=318_270_000_000,
            operating_income_ttm=148_960_000_000,
            free_cash_flow_ttm=72_920_000_000,
            sbc_to_revenue=0.0388,
        ),
        valuation=ValuationMetrics(market_cap=3_130_000_000_000),
    )
    assessment = assess_speculative_deep_tech_manual_review(
        markdown="Microsoft is a mega-cap cloud AI platform. Hard financial metrics are vendor-only. No SEC/IR current-period evidence.",
        metrics_packet=metrics,
        source_registry=_vendor_sources(),
    )

    assert assessment.company_archetype == CompanyArchetype.MEGA_CAP_PLATFORM
    assert not assessment.active
    assert "operating_income_ttm_lt_0" not in assessment.archetype_triggered_rules
    assert "free_cash_flow_ttm_lt_0" not in assessment.archetype_triggered_rules
    assert EVIDENCE_INCOMPLETE_FOR_GOLD in {issue.code for issue in assessment.issues}
    assert assessment.external_display_rating == MANUAL_REVIEW_EVIDENCE_INCOMPLETE_DISPLAY_RATING


def test_vendor_only_megacap_does_not_trigger_deeptech():
    metrics = MetricsPacket(
        ticker="MEGA",
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=100),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=10_000_000_000,
            operating_income_ttm=2_000_000_000,
            free_cash_flow_ttm=1_500_000_000,
            sbc_to_revenue=0.05,
        ),
        valuation=ValuationMetrics(market_cap=150_000_000_000),
    )
    assessment = assess_speculative_deep_tech_manual_review(
        markdown="Mega-cap platform with vendor-only hard metrics and no SEC/IR current-period evidence.",
        metrics_packet=metrics,
        source_registry=_vendor_sources(),
    )

    assert assessment.status == "manual_review"
    assert assessment.publishable is False
    assert assessment.company_archetype != CompanyArchetype.SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL
    assert assessment.external_display_rating == MANUAL_REVIEW_EVIDENCE_INCOMPLETE_DISPLAY_RATING
