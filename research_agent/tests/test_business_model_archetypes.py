from research_agent.quality.deeptech_manual_review import (
    BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE,
    UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE,
    CompanyArchetype,
    assess_speculative_deep_tech_manual_review,
)
from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    SourceRegistryEntry,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
)


def _metrics(ticker: str) -> MetricsPacket:
    return MetricsPacket(
        ticker=ticker,
        as_of_date="2026-08-10",
        technical=TechnicalMetrics(indicator_date="2026-08-10", close=100),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=20_000_000_000,
            operating_income_ttm=3_000_000_000,
            free_cash_flow_ttm=2_000_000_000,
        ),
        valuation=ValuationMetrics(market_cap=100_000_000_000),
    )


def _sources(ticker: str) -> SourceRegistry:
    return SourceRegistry(
        registry_id=f"{ticker}_sources",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker}_SEC",
                ticker=ticker,
                source_type="sec_filing",
                used_for=["revenue_ttm", "free_cash_flow_ttm", "financials"],
            )
        ],
    )


def test_waste_archetype_requires_operating_kpis_generically() -> None:
    text = (
        "The company provides solid waste collection and landfill environmental services. "
        "Collection and disposal yield rose 5%, while volume fell 1%. Adjusted EBITDA "
        "margin was 30%. Free cash flow guidance is $3.8 billion to $3.9 billion. "
        "The company returned $1 billion to shareholders through share repurchases "
        "and cash dividends."
    )
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=text,
        metrics_packet=_metrics("GENERIC"),
        source_registry=_sources("GENERIC"),
    )

    assert assessment.company_archetype == CompanyArchetype.WASTE_ENVIRONMENTAL_SERVICES
    assert assessment.business_model_kpi_coverage_complete is True
    assert assessment.missing_business_kpis == []


def test_membership_retail_missing_kpis_blocks_publication() -> None:
    text = (
        "The membership warehouse retailer reported 82.9 million paid members and "
        "a 92.2% renewal rate. Comparable sales increased."
    )
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=text,
        metrics_packet=_metrics("GENERIC"),
        source_registry=_sources("GENERIC"),
    )

    assert assessment.company_archetype == CompanyArchetype.MEMBERSHIP_RETAIL
    assert assessment.business_model_kpi_coverage_complete is False
    assert {"cardholders", "traffic_and_ticket", "digital_sales"}.issubset(
        assessment.missing_business_kpis
    )
    assert assessment.publishable is False
    assert BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE in {
        issue.code for issue in assessment.issues
    }


def test_medical_devices_profile_checks_transaction_and_integration_context() -> None:
    text = (
        "This diversified medical devices and diagnostics group reported organic growth "
        "and segment growth. Adjusted EPS guidance was reaffirmed. The acquisition "
        "purchase price was financed with debt. Integration costs and amortization "
        "were disclosed, alongside regulatory approval and a product launch."
    )
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=text,
        metrics_packet=_metrics("GENERIC"),
        source_registry=_sources("GENERIC"),
    )

    assert (
        assessment.company_archetype
        == CompanyArchetype.DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS
    )
    assert assessment.business_model_kpi_coverage_complete is True


def test_ticker_alone_cannot_select_business_model_archetype() -> None:
    assessment = assess_speculative_deep_tech_manual_review(
        markdown="A profitable operating company with current SEC evidence.",
        metrics_packet=_metrics("WM"),
        source_registry=_sources("WM"),
    )

    assert assessment.company_archetype == CompanyArchetype.UNKNOWN
    assert assessment.publishable is False
    assert UNKNOWN_OR_LOW_CONFIDENCE_ARCHETYPE in {
        issue.code for issue in assessment.issues
    }


def test_wm_failure_fixture_blocks_when_fcf_guidance_is_missing() -> None:
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=(
            "Waste Management provides solid waste collection, disposal and landfill "
            "environmental services. Collection and disposal yield rose 4%, volume "
            "fell 1%, adjusted EBITDA margin was 29%, and the company returned "
            "$1 billion to shareholders."
        ),
        metrics_packet=_metrics("WM"),
        source_registry=_sources("WM"),
    )
    assert assessment.company_archetype == CompanyArchetype.WASTE_ENVIRONMENTAL_SERVICES
    assert assessment.business_model_kpi_coverage_complete is False
    assert assessment.missing_business_kpis == ["free_cash_flow_guidance"]
    assert assessment.publishable is False


def test_cost_failure_fixture_blocks_when_membership_economics_are_partial() -> None:
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=(
            "Costco is a membership warehouse retailer with 82.9 million paid members. "
            "Renewal rates were 92.2% and comparable sales rose 5.7%."
        ),
        metrics_packet=_metrics("COST"),
        source_registry=_sources("COST"),
    )
    assert assessment.company_archetype == CompanyArchetype.MEMBERSHIP_RETAIL
    assert {"cardholders", "traffic_and_ticket", "digital_sales"}.issubset(
        assessment.missing_business_kpis
    )
    assert assessment.publishable is False


def test_abt_failure_fixture_blocks_without_transaction_and_integration_context() -> None:
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=(
            "Abbott is a diversified medical devices and diagnostics group. Organic "
            "growth and segment growth were reported, adjusted EPS guidance was "
            "reaffirmed, and a regulatory product approval was announced."
        ),
        metrics_packet=_metrics("ABT"),
        source_registry=_sources("ABT"),
    )
    assert (
        assessment.company_archetype
        == CompanyArchetype.DIVERSIFIED_MEDICAL_DEVICES_DIAGNOSTICS
    )
    assert {"transaction_financing", "integration_effects"}.issubset(
        assessment.missing_business_kpis
    )
    assert assessment.publishable is False
