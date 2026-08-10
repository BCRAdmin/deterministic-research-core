import pytest

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.agents.payload import build_agent_payload
from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    SourceRegistryEntry,
)
from research_agent.research_core.models.data_packet import (
    DataPacket,
    EventInfo,
    FiscalContext,
    MaterialNewsEvent,
    NewsCoverage,
    PriceBasis,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
)
from research_agent.research_core.models.validation_report import (
    describe_blocking_validation_errors,
)
from research_agent.research_core.reporting.report_builder import render_markdown_report
from research_agent.research_core.validation.data_quality import (
    validate_cash_investments_separation,
    validate_indicator_date,
    validate_net_debt_sign,
    validate_price_date,
)
from research_agent.research_core.validation.metric_consistency import validate_margin
from research_agent.research_core.validation.rating_consistency import (
    infer_action_class,
    validate_rating_vs_actions,
)
from research_agent.research_core.validation.runner import run_all_validations
from research_agent.research_core.validation.source_quality import validate_source_authority


def _packet():
    return DataPacket(
        ticker="MDB",
        company_name="MongoDB Inc.",
        as_of_date="2026-05-01",
        price_basis=PriceBasis(close=250.83, date="2026-04-30", source="exchange_ohlcv"),
        fiscal_context=FiscalContext(latest_fiscal_year="FY2026"),
        next_events=EventInfo(next_earnings_date=None, confirmed=False, source=None),
        source_registry_id="MDB_2026_05_01",
    )


def _metrics():
    return MetricsPacket(
        ticker="MDB",
        as_of_date="2026-05-01",
        technical=TechnicalMetrics(indicator_date="2026-04-30", close=250.83),
        fundamentals=FundamentalMetrics(fiscal_period="FY2026"),
        valuation=ValuationMetrics(),
    )


def test_price_and_indicator_dates_are_checked():
    assert validate_price_date("2026-05-01", "2026-05-02")["code"] == "PRICE_DATE_AFTER_AS_OF_DATE"
    assert validate_price_date("2026-05-01", "2026-04-30")["code"] == "PRICE_DATE_BEFORE_AS_OF_DATE"
    assert validate_indicator_date("2026-04-30", "2026-05-01")["code"] == "INDICATOR_DATE_MISMATCH"


def test_cash_net_debt_and_margin_consistency_checks():
    assert validate_cash_investments_separation(10, 10, 10, 0)["code"] == "CASH_INVESTMENTS_NOT_RECONCILED"
    assert validate_net_debt_sign(100, 10, 5)["code"] == "NET_DEBT_SIGN_CONFLICT"
    assert validate_margin("gross_margin", 50, 100, 0.40)["code"] == "MARGIN_MISMATCH"


def test_source_authority_warns_for_low_authority_hard_metric():
    issue = validate_source_authority("revenue", "yahoo_finance")
    assert issue["code"] == "LOW_AUTHORITY_SOURCE_FOR_HARD_METRIC"


def test_explicit_authority_rank_controls_derived_source_validation():
    assert validate_source_authority(
        "revenue_ttm",
        "deterministic_calculation",
        authority_rank=1,
    ) is None


def test_rating_action_consistency_detects_tactical_trim():
    assert infer_action_class(["Reduce 20-30%, hold core position"]) == "tactical_trim"
    issue = validate_rating_vs_actions("Sell", ["Reduce 20-30%, hold core position"])
    assert issue["code"] == "RATING_TOO_HARSH_FOR_ACTION"


def test_validation_report_blocks_critical_errors_and_report_generation():
    validation = run_all_validations(
        data_packet=_packet(),
        metrics_packet=_metrics(),
        source_registry=SourceRegistry(
            registry_id="MDB_2026_05_01",
            sources=[SourceRegistryEntry(source_id="vendor", ticker="MDB", source_type="yahoo_finance", used_for=["revenue"])],
        ),
        trade_setups=[{"position_type": "long", "entry": 132.0, "stop_loss": 140.0}],
    )

    assert validation.has_blocking_errors
    assert any(issue.code == "LONG_STOP_ABOVE_ENTRY" for issue in validation.issues)
    with pytest.raises(RuntimeError, match="LONG_STOP_ABOVE_ENTRY"):
        render_markdown_report(_packet(), _metrics(), validation)


def test_validation_report_blocks_evidence_after_as_of_date():
    validation = run_all_validations(
        data_packet=_packet(),
        metrics_packet=_metrics(),
        source_registry=SourceRegistry(
            registry_id="MDB_2026_05_01",
            sources=[
                SourceRegistryEntry(
                    source_id="MDB_IR",
                    ticker="MDB",
                    source_type="company_ir",
                    used_for=["revenue"],
                )
            ],
        ),
        evidence_ledger=EvidenceLedger(
            ticker="MDB",
            as_of_date="2026-05-01",
            evidence_items=[
                EvidenceItem(
                    evidence_id="MDB_FUTURE_NEWS",
                    ticker="MDB",
                    claim_type="news",
                    source_id="MDB_IR_FUTURE",
                    source_type="company_ir",
                    authority_rank=1,
                    statement="Future evidence must stop report generation.",
                    date="2026-05-02",
                )
            ],
        ),
    )

    assert validation.has_blocking_errors is True
    assert describe_blocking_validation_errors(validation).startswith(
        "EVIDENCE_DATE_AFTER_AS_OF_DATE:"
    )


def test_validation_blocks_insurer_without_primary_operating_kpi():
    packet = _packet().model_copy(
        update={
            "ticker": "CVS",
            "news_coverage": NewsCoverage(
                status="partial",
                material_events=[
                    MaterialNewsEvent(
                        date="2026-02-10",
                        headline="SEC Item 1 describes CVS's business",
                        event_type="business_context",
                        source_id="CVS_SEC_BUSINESS",
                        source_type="sec_filing",
                        summary=(
                            "The Health Care Benefits segment offers health "
                            "insurance products and related services."
                        ),
                    )
                ],
            ),
        }
    )
    registry = SourceRegistry(
        registry_id="CVS_2026_05_01",
        sources=[
            SourceRegistryEntry(
                source_id="CVS_SEC",
                ticker="CVS",
                source_type="sec_filing",
                used_for=["revenue", "operating_income", "net_income"],
            )
        ],
    )

    blocked = run_all_validations(packet, _metrics(), registry)
    complete_registry = registry.model_copy(
        update={
            "sources": [
                registry.sources[0].model_copy(
                    update={
                        "used_for": [
                            *registry.sources[0].used_for,
                            "medical_benefit_ratio",
                        ]
                    }
                )
            ]
        }
    )
    complete = run_all_validations(packet, _metrics(), complete_registry)
    vendor_only_registry = registry.model_copy(
        update={
            "sources": [
                registry.sources[0].model_copy(
                    update={
                        "source_type": "yahoo_finance",
                        "used_for": ["medical_benefit_ratio"],
                    }
                )
            ]
        }
    )
    vendor_only = run_all_validations(packet, _metrics(), vendor_only_registry)

    assert blocked.has_blocking_errors is True
    assert any(
        issue.code == "INSURER_OPERATING_KPI_CONTEXT_REQUIRED"
        for issue in blocked.issues
    )
    assert describe_blocking_validation_errors(blocked).startswith(
        "INSURER_OPERATING_KPI_CONTEXT_REQUIRED: A material insurance business"
    )
    assert not any(
        issue.code == "INSURER_OPERATING_KPI_CONTEXT_REQUIRED"
        for issue in complete.issues
    )
    assert any(
        issue.code == "INSURER_OPERATING_KPI_CONTEXT_REQUIRED"
        for issue in vendor_only.issues
    )


def test_report_discloses_prior_close_when_not_same_as_as_of_date():
    validation = run_all_validations(
        data_packet=_packet(),
        metrics_packet=_metrics(),
        source_registry=SourceRegistry(
            registry_id="MDB_2026_05_01",
            sources=[SourceRegistryEntry(source_id="ir", ticker="MDB", source_type="company_ir", used_for=["revenue"])],
        ),
    )
    report = render_markdown_report(_packet(), _metrics(), validation)
    assert "closing price from `2026-04-30`" in report
    assert "not on the report creation date `2026-05-01`" in report


def test_agent_payload_contains_only_validated_packets():
    validation = run_all_validations(
        data_packet=_packet(),
        metrics_packet=_metrics(),
        source_registry=SourceRegistry(
            registry_id="MDB_2026_05_01",
            sources=[SourceRegistryEntry(source_id="ir", ticker="MDB", source_type="company_ir", used_for=["revenue"])],
        ),
    )
    payload = build_agent_payload(_packet(), _metrics(), validation)
    assert set(payload) == {"data_packet", "metrics_packet", "validation_report"}
