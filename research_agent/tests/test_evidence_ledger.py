from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import (
    EvidenceLedger,
    build_evidence_ledger_from_source_registry,
    build_fundamental_derivation_evidence,
    build_technical_derivation_evidence,
)
from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    SourceRegistryEntry,
    merge_evidence_sources,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
)


def test_evidence_ledger_finds_metric_and_primary_evidence():
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_IR_Q4_FY2026_FREE_CASH_FLOW",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="MDB_IR_Q4_FY2026",
                source_type="company_ir",
                authority_rank=1,
                statement="FY2026 FCF was 492.6M.",
                value=492600000,
                unit="usd",
                period="FY2026",
                supports_metrics=["free_cash_flow_ttm"],
            )
        ],
    )

    assert ledger.find_by_metric("free_cash_flow_ttm")
    assert ledger.find_by_metric("fcf")
    assert ledger.has_primary_evidence_for_metric("free_cash_flow")


def test_evidence_ledger_finds_claim_evidence():
    ledger = EvidenceLedger(
        ticker="DDOG",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="DDOG_PRESS_GPU_MONITORING_2026_04_22",
                ticker="DDOG",
                claim_type="news",
                source_id="DDOG_PRESS_GPU_MONITORING",
                source_type="official_press_release",
                authority_rank=2,
                statement="GPU monitoring launched on April 22, 2026.",
                date="2026-04-22",
                supports_claims=["claim_gpu_monitoring_launch"],
            )
        ],
    )

    assert ledger.find_by_claim("claim_gpu_monitoring_launch")[0].evidence_id == "DDOG_PRESS_GPU_MONITORING_2026_04_22"


def test_eps_source_registry_does_not_create_pseudo_guidance_or_consensus():
    registry = SourceRegistry(
        registry_id="TEST",
        sources=[
            SourceRegistryEntry(
                source_id="TEST_SEC_COMPANYFACTS",
                ticker="TEST",
                source_type="sec_filing",
                authority_rank=1,
                url="https://data.sec.gov",
                retrieved_at="2026-05-06T00:00:00Z",
                used_for=["eps"],
            )
        ],
    )

    ledger = build_evidence_ledger_from_source_registry(
        ticker="TEST",
        as_of_date="2026-05-06",
        source_registry=registry,
    )

    assert ledger.find_by_metric("eps")
    assert not ledger.find_by_metric("company_guidance_eps")
    assert not ledger.find_by_metric("consensus_forward_eps")


def test_runtime_evidence_sources_are_merged_without_company_rules():
    evidence = EvidenceItem(
        evidence_id="GENERIC_FILING_REVENUE",
        ticker="GENERIC",
        claim_type="financial_metric",
        source_id="GENERIC_FILING_001",
        source_type="sec_filing",
        authority_rank=1,
        statement="Revenue was reported in the filing.",
        supports_metrics=["revenue_ttm"],
        confidence="high",
    )

    registry = merge_evidence_sources(
        None,
        registry_id="GENERIC_2026-07-01",
        ticker="GENERIC",
        evidence_items=[evidence],
    )

    assert registry.source_ids() == {"GENERIC_FILING_001"}
    assert registry.sources[0].used_for == ["revenue_ttm"]
    assert registry.sources[0].owner == "deterministic_research_pipeline"


def test_technical_metrics_are_derived_from_registered_ohlcv():
    registry = SourceRegistry(
        registry_id="GENERIC_2026-07-01",
        sources=[
            SourceRegistryEntry(
                source_id="GENERIC_EXCHANGE",
                ticker="GENERIC",
                source_type="exchange_ohlcv",
                authority_rank=2,
                used_for=["price", "volume"],
            )
        ],
    )
    metrics = MetricsPacket(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        technical=TechnicalMetrics(
            indicator_date="2026-07-01",
            close=100.0,
            sma_50=95.0,
            sma_200=80.0,
            rsi_14=55.0,
            avg_volume_20=1_000_000,
        ),
        fundamentals=FundamentalMetrics(fiscal_period="TTM"),
        valuation=ValuationMetrics(),
    )

    evidence = build_technical_derivation_evidence(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        metrics_packet=metrics,
        source_registry=registry,
    )

    assert {item.supports_metrics[0] for item in evidence} == {
        "close",
        "sma_50",
        "sma_200",
        "rsi_14",
        "avg_volume_20",
    }
    assert {item.source_id for item in evidence} == {"GENERIC_EXCHANGE"}
    assert all(item.claim_type in {"price_data", "technical_metric"} for item in evidence)


def test_interest_coverage_is_precomputed_with_auditable_operands():
    metrics = MetricsPacket(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        technical=TechnicalMetrics(indicator_date="2026-07-01", close=100.0),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            operating_income_ttm=120.0,
            free_cash_flow_ttm=80.0,
            interest_expense_ttm=20.0,
            operating_income_interest_coverage_ttm=6.0,
            free_cash_flow_interest_coverage_ttm=4.0,
        ),
        valuation=ValuationMetrics(),
    )

    evidence = build_fundamental_derivation_evidence(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        metrics_packet=metrics,
        normalized_fundamentals={"ttm_bridges": {}},
    )
    by_metric = {
        item.supports_metrics[0]: item
        for item in evidence
        if item.supports_metrics
        and item.supports_metrics[0].endswith("interest_coverage_ttm")
    }

    assert by_metric[
        "operating_income_interest_coverage_ttm"
    ].formula_id == "operating_income_divided_by_interest_expense"
    assert by_metric[
        "free_cash_flow_interest_coverage_ttm"
    ].formula_id == "free_cash_flow_divided_by_interest_expense"
    assert by_metric[
        "operating_income_interest_coverage_ttm"
    ].formula_operands == {
        "operating_income_ttm": 120.0,
        "interest_expense_ttm": 20.0,
    }
