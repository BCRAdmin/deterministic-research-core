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


def test_source_registry_evidence_uses_cross_market_units():
    registry = SourceRegistry(
        registry_id="ANY_TEST",
        sources=[
            SourceRegistryEntry(
                source_id="ANY_BSE_OHLCV",
                ticker="ANY",
                source_type="exchange_ohlcv",
                authority_rank=1,
                used_for=["close", "sma_50", "rsi_14", "avg_volume_20"],
            ),
            SourceRegistryEntry(
                source_id="ANY_BSE_FINANCIALS",
                ticker="ANY",
                source_type="company_ir",
                authority_rank=1,
                used_for=[
                    "current_assets",
                    "debt_noncurrent",
                    "economic_share_count",
                    "operating_margin_ttm",
                    "fcf_margin_ttm",
                    "sbc_to_revenue",
                    "free_cash_flow_conversion_ttm",
                    "current_ratio",
                    "market_cap",
                ],
            ),
        ],
    )
    ledger = build_evidence_ledger_from_source_registry(
        ticker="ANY",
        as_of_date="2026-07-27",
        source_registry=registry,
        currency="HUF",
    )
    units = {
        item.supports_metrics[0]: item.unit
        for item in ledger.evidence_items
    }

    assert {
        metric: units[metric]
        for metric in (
            "close",
            "sma_50",
            "rsi_14",
            "avg_volume_20",
            "current_assets",
            "debt_noncurrent",
            "economic_share_count",
            "operating_margin_ttm",
            "fcf_margin_ttm",
            "sbc_to_revenue",
            "free_cash_flow_conversion_ttm",
            "current_ratio",
            "market_cap",
        )
    } == {
        "close": "HUF",
        "sma_50": "HUF",
        "rsi_14": "index",
        "avg_volume_20": "shares",
        "current_assets": "HUF",
        "debt_noncurrent": "HUF",
        "economic_share_count": "shares",
        "operating_margin_ttm": "percent",
        "fcf_margin_ttm": "percent",
        "sbc_to_revenue": "percent",
        "free_cash_flow_conversion_ttm": "multiple",
        "current_ratio": "multiple",
        "market_cap": "HUF",
    }


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
        currency="HUF",
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
    assert {
        item.unit
        for item in evidence
        if item.supports_metrics[0] in {"close", "sma_50", "sma_200"}
    } == {"HUF"}


def test_material_calculations_require_exact_auditable_operands():
    ttm_values = {
        "revenue": 200.0,
        "operating_income": 120.0,
        "net_income": 100.0,
        "operating_cash_flow": 100.0,
        "capex": 20.0,
        "sbc": 8.0,
        "buybacks": 30.0,
        "dividends_paid": 60.0,
        "depreciation_and_amortization": 30.0,
        "interest_expense": 20.0,
        "eps_diluted": 10.0,
    }
    ttm_bridges = {
        metric_name: {
            "formula_id": "sum_four_contiguous_quarters",
            "operands": {
                f"2025_Q{quarter}": value / 4
                for quarter in range(1, 5)
            },
            "period_start": "2025-07-01",
            "period_end": "2026-06-30",
            "source_ids": ["SEC_GENERIC_FILING_A"],
        }
        for metric_name, value in ttm_values.items()
    }
    metrics = MetricsPacket(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        technical=TechnicalMetrics(indicator_date="2026-07-01", close=100.0),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_growth_yoy=0.25,
            revenue_ttm=200.0,
            operating_income_ttm=120.0,
            operating_margin_ttm=0.6,
            ebitda_ttm=150.0,
            net_income_ttm=100.0,
            net_margin_ttm=0.5,
            operating_cash_flow_ttm=100.0,
            capex_ttm=20.0,
            free_cash_flow_ttm=80.0,
            free_cash_flow_formula="cfo_minus_capex",
            fcf_margin_ttm=0.4,
            free_cash_flow_conversion_ttm=0.8,
            sbc_ttm=8.0,
            sbc_to_revenue=0.04,
            sbc_to_fcf=0.1,
            buybacks=30.0,
            dividends_paid=60.0,
            shareholder_distributions_ttm=90.0,
            shareholder_distributions_minus_fcf_ttm=10.0,
            cash_and_equivalents=50.0,
            short_term_investments=20.0,
            cash_and_investments=70.0,
            debt_current=70.0,
            debt_noncurrent=200.0,
            total_debt=270.0,
            lease_liability_current=5.0,
            lease_liability_noncurrent=25.0,
            total_lease_liabilities=30.0,
            current_assets=300.0,
            current_liabilities=150.0,
            current_ratio=2.0,
            equity=400.0,
            net_cash=-200.0,
            listed_share_count=10.0,
            economic_share_count=10.0,
            diluted_share_count=11.0,
            treasury_share_count=1.0,
            treasury_stock_value=100.0,
            trailing_eps=10.0,
            depreciation_and_amortization_ttm=30.0,
            interest_expense_ttm=20.0,
            operating_income_interest_coverage_ttm=6.0,
            free_cash_flow_interest_coverage_ttm=4.0,
        ),
        valuation=ValuationMetrics(
            market_cap=1_000.0,
            enterprise_value=1_200.0,
            price_to_fcf=12.5,
            ev_to_sales=6.0,
            ev_to_ebit=10.0,
            ev_to_ebitda=8.0,
            fcf_yield=0.08,
            trailing_pe=10.0,
        ),
    )
    direct_values = {
        "close": 100.0,
        "cash_and_equivalents": 50.0,
        "short_term_investments": 20.0,
        "debt_current": 70.0,
        "debt_noncurrent": 200.0,
        "lease_liability_current": 5.0,
        "lease_liability_noncurrent": 25.0,
        "current_assets": 300.0,
        "current_liabilities": 150.0,
        "equity": 400.0,
        "listed_share_count": 10.0,
        "shares_diluted": 11.0,
        "treasury_share_count": 1.0,
        "treasury_stock_value": 100.0,
    }
    runtime_evidence = [
        EvidenceItem(
            evidence_id=f"GENERIC_RAW_{metric_name.upper()}",
            ticker="GENERIC",
            claim_type=(
                "price_data"
                if metric_name == "close"
                else "financial_metric"
            ),
            source_id=(
                "GENERIC_EXCHANGE"
                if metric_name == "close"
                else "SEC_GENERIC_FILING_A"
            ),
            source_type=(
                "exchange_ohlcv"
                if metric_name == "close"
                else "sec_filing"
            ),
            authority_rank=1,
            statement=f"Exact source value for {metric_name}.",
            value=value,
            unit="HUF",
            period="current",
            date="2026-06-30",
            supports_metrics=[metric_name],
            raw_value=value,
            normalized_value=value,
            confidence="high",
        )
        for metric_name, value in direct_values.items()
    ]
    runtime_evidence.extend(
        EvidenceItem(
            evidence_id=(
                f"GENERIC_RAW_{metric_name.upper()}_{quarter}"
            ),
            ticker="GENERIC",
            claim_type="financial_metric",
            source_id="SEC_GENERIC_FILING_A",
            source_type="sec_filing",
            authority_rank=1,
            statement=f"Exact source operand for {metric_name}.",
            value=value / 4,
            unit="HUF",
            period=f"2025_Q{quarter}",
            date="2026-06-30",
            supports_metrics=[metric_name],
            raw_value=value / 4,
            normalized_value=value / 4,
            confidence="high",
        )
        for metric_name, value in ttm_values.items()
        for quarter in range(1, 5)
    )
    runtime_evidence.extend(
        [
            EvidenceItem(
                evidence_id=f"GENERIC_RAW_REVENUE_FY_{year}",
                ticker="GENERIC",
                claim_type="financial_metric",
                source_id="SEC_GENERIC_FILING_A",
                source_type="sec_filing",
                authority_rank=1,
                statement=f"Annual revenue for {year}.",
                value=value,
                unit="HUF",
                period=f"FY{year}",
                date=f"{year}-12-31",
                supports_metrics=["revenue"],
                raw_value=value,
                normalized_value=value,
                confidence="high",
            )
            for year, value in ((2024, 160.0), (2025, 200.0))
        ]
    )

    evidence = build_fundamental_derivation_evidence(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        metrics_packet=metrics,
        normalized_fundamentals={
            "ttm_bridges": ttm_bridges,
            "revenue_growth_yoy_bridge": {
                "formula_id": "annual_revenue_yoy_growth",
                "operands": {
                    "current_annual_revenue": 200.0,
                    "prior_annual_revenue": 160.0,
                },
                "period_start": "2024-01-01",
                "period_end": "2025-12-31",
                "source_ids": ["SEC_GENERIC_FILING_A"],
            },
        },
        price_source_id="GENERIC_EXCHANGE",
        runtime_evidence=runtime_evidence,
        currency="HUF",
    )
    assert evidence
    assert {item.source_type for item in evidence} == {
        "deterministic_calculation"
    }
    by_metric = {
        item.supports_metrics[0]: item
        for item in evidence
        if item.supports_metrics
    }
    newly_bound_metrics = {
        "revenue_growth_yoy",
        "operating_margin_ttm",
        "net_margin_ttm",
        "fcf_margin_ttm",
        "sbc_to_fcf",
        "current_ratio",
        "ebitda_ttm",
        "total_lease_liabilities",
        "economic_share_count",
        "diluted_share_count",
        "ev_to_ebit",
        "ev_to_ebitda",
        "fcf_yield",
        "trailing_pe",
    }
    assert newly_bound_metrics <= by_metric.keys()
    assert by_metric["operating_margin_ttm"].unit == "percent"
    assert by_metric["net_margin_ttm"].unit == "percent"
    assert by_metric["fcf_margin_ttm"].unit == "percent"
    assert by_metric["sbc_to_fcf"].unit == "percent"
    assert by_metric["free_cash_flow_conversion_ttm"].unit == "multiple"
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
    assert by_metric["price_to_fcf"].formula_operands == {
        "market_cap": 1_000.0,
        "free_cash_flow_ttm": 80.0,
    }
    assert by_metric["ev_to_sales"].formula_operands == {
        "enterprise_value": 1_200.0,
        "revenue_ttm": 200.0,
    }
    assert by_metric["ev_to_sales"].source_lineage == [
        "ROOM16_GENERIC_DETERMINISTIC_CALCULATIONS",
        "GENERIC_EXCHANGE",
        "SEC_GENERIC_FILING_A",
    ]
    assert by_metric[
        "shareholder_distributions_ttm"
    ].formula_operands == {
        "buybacks": 30.0,
        "dividends_paid": 60.0,
    }
    assert by_metric["shareholder_distributions_ttm"].source_lineage == [
        "ROOM16_GENERIC_DETERMINISTIC_CALCULATIONS",
        "SEC_GENERIC_FILING_A",
    ]
    assert by_metric[
        "shareholder_distributions_minus_fcf_ttm"
    ].formula_operands == {
        "shareholder_distributions_ttm": 90.0,
        "free_cash_flow_ttm": 80.0,
    }
    assert by_metric["cash_and_investments"].formula_operands == {
        "cash_and_equivalents": 50.0,
        "short_term_investments": 20.0,
    }
    assert by_metric["market_cap"].unit == "HUF"
    assert by_metric["revenue_ttm"].unit == "HUF"
    assert by_metric["operating_income_ttm"].unit == "HUF"
    assert by_metric["trailing_eps"].unit == "HUF_per_share"

    inconsistent = MetricsPacket(**metrics.model_dump(mode="python"))
    inconsistent.valuation.ev_to_ebit = 9.0
    invalid_evidence = build_fundamental_derivation_evidence(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        metrics_packet=inconsistent,
        normalized_fundamentals={"ttm_bridges": ttm_bridges},
        price_source_id="GENERIC_EXCHANGE",
        runtime_evidence=runtime_evidence,
        currency="HUF",
    )
    assert "ev_to_ebit" not in {
        item.supports_metrics[0]
        for item in invalid_evidence
        if item.supports_metrics
    }


def test_trailing_eps_fallback_is_evidenced_from_income_and_share_basis():
    metrics = MetricsPacket(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        technical=TechnicalMetrics(indicator_date="2026-07-01", close=100.0),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            net_income_ttm=100.0,
            economic_share_count=10.0,
            trailing_eps=10.0,
        ),
        valuation=ValuationMetrics(trailing_pe=10.0),
    )
    runtime_evidence = [
        EvidenceItem(
            evidence_id=f"GENERIC_RAW_{metric_name.upper()}",
            ticker="GENERIC",
            claim_type="financial_metric",
            source_id="GENERIC_OFFICIAL_FILING",
            source_type="company_ir",
            authority_rank=1,
            statement=f"Exact source value for {metric_name}.",
            value=value,
            unit="HUF" if metric_name == "net_income_ttm" else "shares",
            period="TTM" if metric_name == "net_income_ttm" else "current",
            date="2026-06-30",
            supports_metrics=[metric_name],
            normalized_value=value,
            confidence="high",
        )
        for metric_name, value in (
            ("net_income_ttm", 100.0),
            ("economic_share_count", 10.0),
        )
    ]
    runtime_evidence.append(
        EvidenceItem(
            evidence_id="GENERIC_EXCHANGE_CLOSE",
            ticker="GENERIC",
            claim_type="price_data",
            source_id="GENERIC_EXCHANGE",
            source_type="exchange_ohlcv",
            authority_rank=1,
            statement="Exact closing price.",
            value=100.0,
            unit="HUF",
            period="daily_history",
            date="2026-07-01",
            supports_metrics=["close"],
            normalized_value=100.0,
            confidence="high",
        )
    )

    evidence = build_fundamental_derivation_evidence(
        ticker="GENERIC",
        as_of_date="2026-07-01",
        metrics_packet=metrics,
        normalized_fundamentals={},
        price_source_id="GENERIC_EXCHANGE",
        runtime_evidence=runtime_evidence,
        currency="HUF",
    )
    by_metric = {
        item.supports_metrics[0]: item
        for item in evidence
        if item.supports_metrics
    }

    assert by_metric["trailing_eps"].formula_operands == {
        "net_income_ttm": 100.0,
        "economic_share_count": 10.0,
    }
    assert by_metric["trailing_eps"].unit == "HUF_per_share"
    assert by_metric["trailing_pe"].formula_operands == {
        "close": 100.0,
        "trailing_eps": 10.0,
    }
