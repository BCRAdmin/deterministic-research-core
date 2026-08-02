import json
import subprocess
import sys
from pathlib import Path

import pytest

from research_agent.audit.markdown_numeric_extractor import extract_numeric_claims
from research_agent.audit.report_linter import audit_markdown_report
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.reconciliation.canonical_financials import CanonicalFinancials, CanonicalMetric
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import (
    DataPacket,
    EventInfo,
    FiscalContext,
    PriceBasis,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
)
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.research_core.reporting.report_builder import render_markdown_report


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name, filename):
    path = FIXTURES / name / filename
    if filename.endswith(".json"):
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


def audit_fixture(name):
    return audit_markdown_report(
        markdown=load_fixture(name, "bad_report.md"),
        metrics_packet=MetricsPacket(**load_fixture(name, "metrics_packet.json")),
        validation_report=ValidationReport(**load_fixture(name, "validation_report.json")),
        source_registry=SourceRegistry(**load_fixture(name, "source_registry.json")),
    )


def valuation_source_registry(ticker="RKLB"):
    return SourceRegistry(
        registry_id=f"{ticker}_sources",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker}_SEC",
                ticker=ticker,
                source_type="sec_filing",
                authority_rank=1,
                used_for=["revenue", "shares", "debt", "cash"],
            ),
            SourceRegistryEntry(
                source_id=f"{ticker}_IR",
                ticker=ticker,
                source_type="company_ir",
                authority_rank=1,
                used_for=["revenue", "cash", "debt"],
            ),
            SourceRegistryEntry(
                source_id=f"{ticker}_PRICE",
                ticker=ticker,
                source_type="exchange_ohlcv",
                authority_rank=2,
                used_for=["price", "price_data", "close"],
            ),
        ],
    )


def simple_metrics(
    *,
    ticker="RKLB",
    revenue_ttm=622_495_000,
    market_cap=75_540_078_249.93611,
    enterprise_value=73_938_534_249.93611,
    ev_to_sales=118.77771588516552,
):
    return MetricsPacket(
        ticker=ticker,
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=124.77),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=revenue_ttm,
            operating_income_ttm=-250_000_000,
            free_cash_flow_ttm=-220_123_000,
            cash_and_investments=1_654_697_000,
            total_debt=53_153_000,
            diluted_share_count=605_434_642,
        ),
        valuation=ValuationMetrics(
            market_cap=market_cap,
            enterprise_value=enterprise_value,
            ev_to_sales=ev_to_sales,
        ),
    )


def test_markdown_numeric_extractor_normalizes_german_cash_claim():
    claims = extract_numeric_claims("Der Free Cashflow TTM beträgt 58,1 Mrd. $.")
    claim = next(item for item in claims if item.unit == "usd")

    assert claim.normalized_value == 58100000000
    assert claim.possible_metric == "free_cash_flow_ttm"
    assert claim.period_hint == "ttm"

    huf_claim = extract_numeric_claims("Revenue TTM is 65.51B HUF.")[0]
    assert huf_claim.normalized_value == pytest.approx(65_510_000_000)
    assert huf_claim.unit == "huf"


def test_numeric_extractor_ignores_period_tokens_inside_evidence_metadata():
    claims = extract_numeric_claims(
        "Revenue TTM is 65.51B HUF. Evidence metrics: `revenue_ttm`. "
        "Evidence IDs: `ANY_REVENUE_FY2025_Q4`. Confidence: `high`."
    )
    claim = next(item for item in claims if item.unit == "huf")

    assert claim.period_hint == "ttm"
    assert "Q4" not in claim.nearby_text


def test_auditor_blocks_currency_that_conflicts_with_evidence_ledger():
    metrics = simple_metrics(ticker="ANY", revenue_ttm=65_510_000_000)
    ledger = EvidenceLedger(
        ticker="ANY",
        as_of_date="2026-05-15",
        evidence_items=[
            EvidenceItem(
                evidence_id="ANY_REVENUE",
                ticker="ANY",
                claim_type="financial_metric",
                source_id="BSE_ANY_FINANCIALS",
                source_type="company_ir",
                authority_rank=1,
                statement="Revenue was reported in HUF.",
                value=65_510_000_000,
                unit="HUF",
                supports_metrics=["revenue_ttm"],
            )
        ],
    )

    wrong = audit_markdown_report(
        "Revenue TTM is $65.51B.",
        metrics,
        evidence_ledger=ledger,
    )
    correct = audit_markdown_report(
        "Revenue TTM is 65.51B HUF.",
        metrics,
        evidence_ledger=ledger,
    )

    assert wrong.has_issue("CURRENCY_MISMATCH", metric="revenue_ttm")
    assert wrong.has_blocking_errors
    assert not correct.has_issue("CURRENCY_MISMATCH")
    assert not correct.has_issue("NUMERIC_MISMATCH", metric="revenue_ttm")


def test_auditor_compares_net_debt_with_the_signed_net_cash_position():
    metrics = simple_metrics(ticker="ANY")
    metrics.fundamentals.net_cash = -4_610_000_000

    correct = audit_markdown_report("Net debt is 4.61B HUF.", metrics)
    wrong_amount = audit_markdown_report("Net debt is 3.00B HUF.", metrics)

    metrics.fundamentals.net_cash = 4_610_000_000
    false_debt = audit_markdown_report("Net debt is 4.61B HUF.", metrics)

    assert not correct.has_issue("NUMERIC_MISMATCH", metric="net_debt")
    assert wrong_amount.has_issue("NUMERIC_MISMATCH", metric="net_debt")
    assert false_debt.has_issue("NUMERIC_MISMATCH", metric="net_debt")


def test_auditor_catches_nvda_fcf_ttm_mismatch():
    audit = audit_fixture("nvda_2026_05_01")

    assert audit.has_issue("NUMERIC_MISMATCH", metric="free_cash_flow_ttm")


def test_auditor_catches_q4_margin_labeled_as_ttm():
    audit = audit_fixture("nvda_2026_05_01")

    assert audit.has_issue("PERIOD_MISMATCH", metric="operating_margin")


def test_auditor_normalizes_large_percent_ratios():
    metrics = MetricsPacket(**load_fixture("mdb_2026_05_01", "metrics_packet.json"))
    metrics.fundamentals.sbc_to_revenue = 2.614

    audit = audit_markdown_report("SBC / Revenue: 261.4%.", metrics)

    assert not audit.has_issue("NUMERIC_MISMATCH", metric="sbc_to_revenue")


def test_auditor_treats_clean_sbc_over_revenue_as_true_anomaly_not_period_bug():
    metrics = simple_metrics(ticker="IONQ", revenue_ttm=132_800_000, market_cap=17_600_000_000, enterprise_value=17_580_000_000, ev_to_sales=132.41)
    metrics.fundamentals.sbc_to_revenue = 1.462

    audit = audit_markdown_report("## Executive Summary\nSBC/Revenue is extreme and must stay under review.", metrics, ticker="IONQ")

    assert audit.has_issue("TRUE_FINANCIAL_ANOMALY", metric="sbc_to_revenue")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="sbc_to_revenue")


def test_auditor_flags_absurd_ev_sales_as_extreme_valuation_review():
    metrics = simple_metrics(
        ticker="NVDA",
        revenue_ttm=1_000_000_000,
        market_cap=450_000_000_000,
        enterprise_value=435_860_000_000,
        ev_to_sales=435.86,
    )

    audit = audit_markdown_report("## Executive Summary\nValidated skeleton.", metrics, ticker="NVDA")

    assert audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")


def test_auditor_classifies_clean_rklb_extreme_ev_sales_as_review_not_period_bug():
    metrics = simple_metrics()

    audit = audit_markdown_report(
        "## Executive Summary\nBacklog and revenue growth partly support the valuation, but FCF remains negative.",
        metrics,
        source_registry=valuation_source_registry(),
        ticker="RKLB",
    )

    assert audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="ev_to_sales")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="market_cap_to_revenue")


def test_auditor_keeps_period_denominator_bug_for_quarterly_revenue_bucket():
    metrics = simple_metrics(
        revenue_ttm=200_348_000,
        market_cap=24_314_000_000,
        enterprise_value=23_800_000_000,
        ev_to_sales=118.79327670378641,
    )
    canonical = CanonicalFinancials(
        ticker="RKLB",
        as_of_date="2026-05-15",
        metrics=[
            CanonicalMetric(
                metric_name="revenue",
                value=200_348_000,
                unit="usd",
                period="Q1_FY2026_quarterly",
                period_bucket="quarterly",
                duration_days=90,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["RKLB_Q1_2026_IR"],
                confidence="high",
            )
        ],
    )

    audit = audit_markdown_report(
        "## Executive Summary\nValidated skeleton.",
        metrics,
        source_registry=valuation_source_registry(),
        canonical_financials=canonical,
        ticker="RKLB",
    )

    assert audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="ev_to_sales")
    assert not audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")


def test_auditor_does_not_flag_clean_mega_cap_ev_sales_below_30_as_valuation_anomaly():
    metrics = simple_metrics(
        ticker="MSFT",
        revenue_ttm=260_000_000_000,
        market_cap=3_100_000_000_000,
        enterprise_value=3_050_000_000_000,
        ev_to_sales=11.73,
    )

    audit = audit_markdown_report("## Executive Summary\nValidated skeleton.", metrics, ticker="MSFT")

    assert not audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")
    assert not audit.has_issue("TRUE_VALUATION_ANOMALY", metric="ev_to_sales")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="ev_to_sales")


def test_auditor_flags_mega_cap_fcf_margin_anomaly():
    metrics = MetricsPacket(**load_fixture("amzn_2026_05_01", "metrics_packet.json"))
    metrics.fundamentals.fcf_margin_ttm = 0.50

    audit = audit_markdown_report("## Executive Summary\nValidated skeleton.", metrics, ticker="AMZN")

    assert audit.has_issue("FINANCIAL_SANITY_FCF_MARGIN_ANOMALY", metric="fcf_margin_ttm")


def test_auditor_catches_long_stop_above_entry_in_markdown():
    audit = audit_fixture("ddog_2026_05_01")

    assert audit.has_issue("INVALID_TRADE_LEVEL")


def test_auditor_catches_overstated_news_causality():
    audit = audit_fixture("mdb_2026_05_01")

    assert audit.has_issue("OVERSTATED_CAUSALITY")


def test_auditor_catches_forward_eps_guidance_mismatch():
    audit = audit_fixture("mdb_2026_05_01")

    assert audit.has_issue("FORWARD_EPS_GUIDANCE_MISMATCH")


def test_auditor_catches_sell_when_actions_are_trim():
    audit = audit_fixture("mdb_2026_05_01")

    assert audit.has_issue("RATING_TOO_HARSH_FOR_ACTION")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "nvda_2026_05_01",
        "ddog_2026_05_01",
        "mdb_2026_05_01",
        "amzn_2026_05_01",
    ],
)
def test_golden_fixture_expected_audit_issues_are_found(fixture_name):
    audit = audit_fixture(fixture_name)
    expected = load_fixture(fixture_name, "expected_audit_issues.json")

    for issue in expected:
        assert audit.has_issue(issue["code"], metric=issue.get("metric"))


def test_auditor_catches_no_news_when_sources_exist():
    audit = audit_fixture("amzn_2026_05_01")

    assert audit.has_issue("NO_NEWS_WITH_AVAILABLE_SOURCES")


def test_report_linter_cli_runs_against_fixture():
    fixture_dir = FIXTURES / "amzn_2026_05_01"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_agent.audit.report_linter",
            "--report",
            str(fixture_dir / "bad_report.md"),
            "--metrics",
            str(fixture_dir / "metrics_packet.json"),
            "--validation",
            str(fixture_dir / "validation_report.json"),
            "--sources",
            str(fixture_dir / "source_registry.json"),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "NO_NEWS_WITH_AVAILABLE_SOURCES" in result.stdout


def test_report_builder_optional_audit_saves_failed_draft(tmp_path):
    data_packet = DataPacket(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        as_of_date="2026-05-01",
        price_basis=PriceBasis(close=900, date="2026-04-30", source="exchange_ohlcv"),
        fiscal_context=FiscalContext(),
        next_events=EventInfo(next_earnings_date="2026-05-21", confirmed=True, source="company_ir"),
        source_registry_id="NVDA_2026_05_01",
    )
    metrics_packet = MetricsPacket(
        ticker="NVDA",
        as_of_date="2026-05-01",
        technical=TechnicalMetrics(indicator_date="2026-04-30", close=900),
        fundamentals=FundamentalMetrics(fiscal_period="FY2026", free_cash_flow_ttm=96575000000),
        valuation=ValuationMetrics(),
    )
    validation_report = ValidationReport(
        ticker="NVDA",
        as_of_date="2026-05-01",
        has_blocking_errors=False,
        issues=[],
    )
    claims = [
        ResearchClaim(
            agent="fundamental",
            claim="FCF TTM is $58.1B.",
            evidence_metrics=["free_cash_flow_ttm"],
            source_ids=["NVDA_IR_FY2026"],
            confidence="high",
        )
    ]

    with pytest.raises(RuntimeError):
        render_markdown_report(
            data_packet,
            metrics_packet,
            validation_report,
            claims=claims,
            run_audit=True,
            audit_output_dir=str(tmp_path),
        )

    assert (tmp_path / "draft_failed_audit.md").exists()
    assert (tmp_path / "audit_report.json").exists()
