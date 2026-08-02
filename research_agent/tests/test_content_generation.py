import json
from pathlib import Path

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.content.claim_generator import claim_quality_metrics, generate_research_claims
from research_agent.content.report_composer import compose_research_report
from research_agent.content.publish_composer import compose_internal_best_report
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.quality.quality_score import calculate_quality_score
from research_agent.reconciliation.canonical_financials import (
    CanonicalFinancials,
    CanonicalMetric,
)
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


def _load_packet(ticker: str):
    base = Path("research_agent/data/packets") / ticker / "2026-05-05"
    return (
        DataPacket(**json.loads((base / "data_packet.json").read_text(encoding="utf-8"))),
        MetricsPacket(**json.loads((base / "metrics_packet.json").read_text(encoding="utf-8"))),
        ValidationReport(**json.loads((base / "validation_report.json").read_text(encoding="utf-8"))),
        EvidenceLedger(**json.loads((base / "evidence_ledger.json").read_text(encoding="utf-8"))),
        DecisionPacket(**json.loads((base / "decision_packet.json").read_text(encoding="utf-8"))),
    )


def test_content_generator_keeps_only_evidence_mapped_substantive_claims():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    quality = claim_quality_metrics(claims)

    assert quality["analyst_claim_count"] < 15
    assert quality["evidence_mapped_claim_ratio"] >= 0.90
    assert quality["hard_claim_evidence_ratio"] == 1.0
    assert quality["generic_claim_count"] == 0
    assert quality["substantive_analyst_claim_count"] == 11
    assert all(claim.evidence_ids for claim in claims)
    valuation_claim = next(
        claim
        for claim in claims
        if claim.section == "Valuation / Multiples"
        and claim.claim.startswith("Valuation is framed by EV/Sales")
    )
    technical_claim = next(
        claim for claim in claims if "50-SMA" in claim.claim
    )
    assert valuation_claim.metric_refs == [
        "ev_to_sales",
        "enterprise_value",
        "revenue_ttm",
    ]
    assert valuation_claim.metric_values["ev_to_sales"] == metrics.valuation.ev_to_sales
    assert technical_claim.metric_refs == [
        "close",
        "sma_50",
        "sma_200",
        "rsi_14",
    ]
    assert technical_claim.metric_values["sma_200"] == metrics.technical.sma_200


def test_content_generator_uses_precomputed_distribution_comparison():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.shareholder_distributions_ttm = 90.0
    metrics.fundamentals.shareholder_distributions_minus_fcf_ttm = 10.0
    ledger.evidence_items.extend(
        [
            EvidenceItem(
                evidence_id=f"SNOW_{metric.upper()}",
                ticker="SNOW",
                claim_type="financial_metric",
                source_id="SEC_SNOW_DERIVED_TTM",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=f"{metric} was precomputed.",
                value=value,
                unit="usd",
                period="TTM",
                date=data.as_of_date,
                supports_metrics=[metric],
                formula_id=formula_id,
                formula_operands=operands,
            )
            for metric, value, formula_id, operands in [
                (
                    "shareholder_distributions_ttm",
                    90.0,
                    "buybacks_ttm_plus_dividends_paid_ttm",
                    {"buybacks": 30.0, "dividends_paid": 60.0},
                ),
                (
                    "shareholder_distributions_minus_fcf_ttm",
                    10.0,
                    "shareholder_distributions_ttm_minus_free_cash_flow_ttm",
                    {
                        "shareholder_distributions_ttm": 90.0,
                        "free_cash_flow_ttm": 80.0,
                    },
                ),
            ]
        ]
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    claim = next(
        item for item in claims
        if "arithmetic comparison" in item.claim
    )

    assert claim.metric_values == {
        "shareholder_distributions_ttm": 90.0,
        "shareholder_distributions_minus_fcf_ttm": 10.0,
    }
    assert "does not identify a funding source" in claim.claim


def test_generic_report_surfaces_use_the_packet_currency_instead_of_dollars():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    data.ticker = "GENERIC"
    data.price_basis.currency = "HUF"
    metrics.fundamentals.revenue_growth_yoy = None
    metrics.fundamentals.sbc_to_revenue = None
    metrics.fundamentals.net_cash = -4_610_000_000
    metrics.fundamentals.total_debt = 13_460_000_000

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
    )
    research_report = compose_research_report(
        data,
        metrics,
        validation,
        decision,
        ledger,
        claims,
    )
    internal_report = compose_internal_best_report(
        data,
        metrics,
        decision,
        ledger,
        claims,
        status="manual_review",
        publishable=False,
    )
    monetary_claims = [
        claim
        for claim in claims
        if any(
            phrase in claim.claim
            for phrase in (
                "revenue TTM of",
                "FCF TTM is",
                "net cash of",
                "net debt of",
                "bull case combines revenue of",
                "where revenue ",
            )
        )
    ]

    assert monetary_claims
    assert all("$" not in claim.claim for claim in monetary_claims)
    assert all("HUF" in claim.claim for claim in monetary_claims)
    balance_sheet_claim = next(
        claim for claim in claims if "balance-sheet position" in claim.claim
    )
    assert "net debt of 4.61B HUF" in balance_sheet_claim.claim
    assert "Balance-sheet flexibility" not in balance_sheet_claim.claim
    assert "holding corridor" not in balance_sheet_claim.investment_implication
    technical_text = "\n".join(
        claim.claim for claim in claims if claim.section == "Technical Setup"
    )
    catalyst_text = "\n".join(
        claim.claim for claim in claims if claim.section == "Catalysts & Triggers"
    )
    assert "close 141.71 HUF" in technical_text
    assert f"50-SMA {metrics.technical.sma_50:.2f} HUF" in technical_text
    assert f"200-SMA {metrics.technical.sma_200:.2f} HUF" in technical_text
    assert "validated technical reference levels" in catalyst_text
    assert "$" not in research_report
    assert "$" not in internal_report
    assert "4.34B HUF" in research_report
    assert "4.34B HUF" in internal_report
    assert "| Close | 141.71 HUF |" in research_report
    assert "| FCF TTM | 1,120,000,000 HUF |" in research_report
    unsupported_language = (
        "company-specific growth",
        "margin quality",
        "validated growth",
        "fcf quality",
        "cash conversion quality",
        "not available in evidence set",
        "business discussion should focus",
        "should be read against",
        "should not be translated into a blocked rating",
        "validation and audit issues are part of",
        "source disagreement or current-period mismatch",
        "should be limited to confirmed packet inputs",
        "trigger language should use",
    )
    assert not any(
        phrase in claim.claim.lower()
        for claim in claims
        for phrase in unsupported_language
    )
    assert claim_quality_metrics(claims)["generic_claim_count"] == 0
    rating_claim = next(
        claim
        for claim in claims
        if claim.section == "Final Rating & Action Plan"
    )
    assert rating_claim.metric_refs == [
        "close",
        "revenue_ttm",
        "free_cash_flow_ttm",
        "ev_to_sales",
    ]
    assert "revenue TTM of 4.34B HUF" in rating_claim.claim
    assert "FCF TTM of 1.12B HUF" in rating_claim.claim
    personal_action_language = (
        "entries should be",
        "staged entries",
        "maintain core exposure",
        "existing holders",
        "new capital",
        "below target weight",
        "before adding",
        "add on pullbacks",
    )
    rendered_text = "\n".join(
        [
            research_report,
            internal_report,
            *(claim.claim for claim in claims),
            *(claim.investment_implication or "" for claim in claims),
        ]
    ).lower()
    assert not any(phrase in rendered_text for phrase in personal_action_language)


def test_content_generator_does_not_render_missing_values_as_claims():
    data, metrics, validation, ledger, decision = _load_packet("CRWD")

    claims = generate_research_claims(data, metrics, ledger, decision, validation)

    assert claims
    assert all("not available in evidence set" not in claim.claim for claim in claims)
    assert not any("revenue TTM of" in claim.claim for claim in claims)


def test_generic_company_gets_latest_reported_period_claim():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    data.ticker = "GENERIC"
    data.price_basis.currency = "HUF"
    canonical = CanonicalFinancials(
        ticker="GENERIC",
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="HUF",
                period="FY2026_Q1",
                fiscal_year=2026,
                fiscal_period="Q1",
                period_bucket="quarterly",
                start_date="2026-01-01",
                end_date="2026-03-31",
                duration_days=89,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_IR_FY2026_Q1"],
                evidence_ids=[f"GENERIC_{metric_name}_FY2026_Q1"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 17_190_000_000),
                ("operating_income", 3_790_000_000),
                ("net_income", 2_680_000_000),
            )
        ],
    )

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    current = next(
        claim for claim in claims if "latest reported period" in claim.claim
    )

    assert " HUF" in current.claim
    assert "do not by themselves establish growth" in current.claim
    assert current.metric_refs == [
        "current_q_revenue",
        "operating_income",
        "net_income",
    ]


def test_unpadded_claim_report_stays_internal_when_substance_gate_fails():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    report = compose_research_report(data, metrics, validation, decision, ledger, claims)

    audit = audit_markdown_report(
        report,
        metrics_packet=metrics,
        validation_report=validation,
        decision_packet=decision,
        evidence_ledger=ledger,
        ticker=data.ticker,
    )
    claim_quality = claim_quality_metrics(claims)
    quality = calculate_quality_score(
        validation_report=validation,
        audit_report=audit,
        decision_packet=decision,
        final_markdown=report,
        analyst_claim_count=claim_quality["analyst_claim_count"],
        evidence_mapped_claim_ratio=claim_quality["evidence_mapped_claim_ratio"],
        hard_claim_evidence_ratio=claim_quality["hard_claim_evidence_ratio"],
        substantive_analyst_claim_count=claim_quality["substantive_analyst_claim_count"],
        substantive_claim_ratio=claim_quality["substantive_claim_ratio"],
        generic_claim_count=claim_quality["generic_claim_count"],
        generic_claim_ratio=claim_quality["generic_claim_ratio"],
        data_limitation_claim_count=claim_quality["data_limitation_claim_count"],
        current_period_kpi_claim_count=claim_quality["current_period_kpi_claim_count"],
        ticker_specific_kpi_claim_count=claim_quality["ticker_specific_kpi_claim_count"],
        final_rating_rationale_quality=claim_quality["final_rating_rationale_quality"],
        mechanical_rating_language_count=claim_quality["mechanical_rating_language_count"],
        company_specific_claim_count=claim_quality["company_specific_claim_count"],
        valuation_specific_claim_count=claim_quality["valuation_specific_claim_count"],
        technical_specific_claim_count=claim_quality["technical_specific_claim_count"],
        rating_rationale_claim_count=claim_quality["rating_rationale_claim_count"],
    )

    assert not audit.has_blocking_errors
    assert not quality.publishable
    assert quality.content_score == 60
    assert "No LLM claims attached" not in report
    assert "## Evidence Appendix" in report
    assert claim_quality["analyst_claim_count"] < 15
    assert claim_quality["substantive_analyst_claim_count"] < 12
    assert claim_quality["generic_claim_count"] == 0


def test_financial_sanity_errors_still_block_claim_rich_reports():
    data, metrics, validation, ledger, decision = _load_packet("NVDA")
    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    report = compose_research_report(data, metrics, validation, decision, ledger, claims)

    audit = audit_markdown_report(
        report,
        metrics_packet=metrics,
        validation_report=validation,
        decision_packet=decision,
        evidence_ledger=ledger,
        ticker=data.ticker,
    )
    claim_quality = claim_quality_metrics(claims)
    quality = calculate_quality_score(
        validation_report=validation,
        audit_report=audit,
        decision_packet=decision,
        final_markdown=report,
        analyst_claim_count=claim_quality["analyst_claim_count"],
        evidence_mapped_claim_ratio=claim_quality["evidence_mapped_claim_ratio"],
        hard_claim_evidence_ratio=claim_quality["hard_claim_evidence_ratio"],
        substantive_analyst_claim_count=claim_quality["substantive_analyst_claim_count"],
        generic_claim_ratio=claim_quality["generic_claim_ratio"],
        company_specific_claim_count=claim_quality["company_specific_claim_count"],
        valuation_specific_claim_count=claim_quality["valuation_specific_claim_count"],
        technical_specific_claim_count=claim_quality["technical_specific_claim_count"],
        rating_rationale_claim_count=claim_quality["rating_rationale_claim_count"],
    )

    assert any(issue.code.startswith("FINANCIAL_SANITY_") for issue in audit.issues)
    assert not quality.publishable
