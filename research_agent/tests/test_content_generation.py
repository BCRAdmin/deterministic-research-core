import json
from pathlib import Path

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.content.claim_generator import (
    _ClaimBuilder,
    _bear_case_claim_text,
    _current_period_claim_specs,
    _evidence_unit_is_compatible,
    _issuer_operating_result_specs,
    _money,
    claim_coverage_gaps,
    claim_quality_metrics,
    generate_research_claims,
)
from research_agent.content.report_composer import (
    _fmt_money as _report_money,
    compose_research_report,
)
from research_agent.content.publish_composer import (
    _cash_and_marketable_securities,
    _clean_text,
    _constructive_cash_conversion_trigger,
    _final_rating_section,
    _generic_investment_thesis,
    _current_kpi_claims,
    _operating_driver_claims,
    _fmt_money as _publish_money,
    _generic_publish_report,
    compose_internal_best_report,
)
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger, unit_for_metric
from research_agent.quality.quality_score import calculate_quality_score
from research_agent.reconciliation.canonical_financials import (
    CanonicalFinancials,
    CanonicalMetric,
)
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket, MaterialNewsEvent
from research_agent.research_core.models.metrics_packet import MetricsPacket, ValuationScenario
from research_agent.research_core.models.validation_report import ValidationReport


def _load_packet(ticker: str):
    base = Path("research_agent/data/packets") / ticker / "2026-05-05"
    return (
        DataPacket(**json.loads((base / "data_packet.json").read_text(encoding="utf-8"))),
        MetricsPacket(**json.loads((base / "metrics_packet.json").read_text(encoding="utf-8"))),
        ValidationReport(
            **json.loads((base / "validation_report.json").read_text(encoding="utf-8"))
        ),
        EvidenceLedger(**json.loads((base / "evidence_ledger.json").read_text(encoding="utf-8"))),
        DecisionPacket(**json.loads((base / "decision_packet.json").read_text(encoding="utf-8"))),
    )


def test_per_share_unit_normalization_accepts_sec_plural_form():
    assert _evidence_unit_is_compatible("USD/shares", "USD_per_share")


def test_claim_builder_resolves_dcf_terminal_value_share_for_rating_claims():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.valuation.sensitivity.scenarios = [
        ValuationScenario(
            name="base",
            starting_free_cash_flow=1_000_000_000,
            free_cash_flow_growth_rate=0.05,
            discount_rate=0.10,
            terminal_growth_rate=0.025,
            present_value_explicit_cash_flows=4_000_000_000,
            present_value_terminal_value=6_000_000_000,
            terminal_value_share=0.60,
            equity_value=10_000_000_000,
        )
    ]
    builder = _ClaimBuilder(data, metrics, ledger, decision, validation, None)

    assert builder._metric_value("dcf_base_terminal_value_share") == 0.60


def test_current_kpi_selection_deduplicates_catalyst_copy_with_same_evidence() -> None:
    shared = {
        "claim_type": "news",
        "agent": "deterministic_content_generator",
        "claim": "FY2026 guidance remains $3.75 billion.",
        "claim_text": "FY2026 guidance remains $3.75 billion.",
        "evidence_metrics": ["operating_kpi_free_cash_flow_guidance_01"],
        "metric_refs": ["operating_kpi_free_cash_flow_guidance_01"],
        "metric_values": {"operating_kpi_free_cash_flow_guidance_01": 3_750_000_000},
        "evidence_ids": ["TEST_GUIDANCE"],
        "source_ids": ["TEST_SEC"],
        "confidence": "high",
        "importance": "high",
    }
    context = ResearchClaim(
        claim_id="TEST_CLAIM_001",
        section="Business & Segment Context",
        **shared,
    )
    catalyst = ResearchClaim(
        claim_id="TEST_CLAIM_002",
        section="Catalysts & Triggers",
        **shared,
    )

    assert _current_kpi_claims([context, catalyst]) == [context]
    assert _current_kpi_claims([catalyst]) == []


def test_operating_driver_selection_is_generic_complete_and_prefers_specific_claims() -> None:
    def claim(
        claim_id: str,
        text: str,
        metrics: list[str],
    ) -> ResearchClaim:
        return ResearchClaim(
            claim_id=claim_id,
            section="Business & Segment Context",
            claim_type="news",
            agent="test",
            claim=text,
            claim_text=text,
            evidence_metrics=metrics,
            metric_refs=metrics,
            metric_values={metric: float(index + 1) for index, metric in enumerate(metrics)},
            evidence_ids=[f"{claim_id}_EVIDENCE"],
            source_ids=[f"{claim_id}_SOURCE"],
            confidence="high",
            importance="high",
        )

    mixed = claim(
        "MIXED",
        "Revenue rose 4.0% due to yield and volume.",
        [
            "operating_kpi_statement_context_01_01",
            "operating_kpi_collection_disposal_yield_01_02",
        ],
    )
    pricing = claim(
        "PRICING",
        "Average landfill yield was 5.2% in the latest quarter.",
        ["operating_kpi_collection_disposal_yield_02_01"],
    )
    volume = claim(
        "VOLUME",
        "Collection and disposal volume declined 1.8%.",
        ["operating_kpi_volume_03_01"],
    )
    margin = claim(
        "MARGIN",
        "Operating EBITDA margin was 30.4%.",
        ["operating_kpi_operating_ebitda_04_01"],
    )
    capital = claim(
        "CAPITAL",
        "The company returned $1.04 billion to shareholders through share repurchases and cash dividends.",
        ["operating_kpi_capital_allocation_05_01"],
    )

    selected = _operating_driver_claims([mixed, pricing, volume, margin, capital])

    assert [(label, item.claim_id) for label, item in selected] == [
        ("Pricing / yield", "PRICING"),
        ("Volume", "VOLUME"),
        ("Margin", "MARGIN"),
        ("Capital allocation", "CAPITAL"),
    ]

    _, metrics, _, ledger, decision = _load_packet("SNOW")
    report = _generic_publish_report(
        "TEST",
        "Hold",
        {"Business & Segment Context": [mixed, pricing, volume, margin, capital]},
        metrics,
        decision,
        [mixed, pricing, volume, margin, capital],
        ledger,
    )
    main_body = report.split("## Evidence Appendix", 1)[0]

    assert "## Operating Drivers & Capital Allocation" in main_body
    for label, item in selected:
        assert f"**{label}:**" in main_body
        assert main_body.count(item.claim) == 1
    assert mixed.claim in main_body


def _add_exact_metric_evidence(data, metrics, ledger):
    for section_name in ("fundamentals", "technical", "valuation"):
        section = getattr(metrics, section_name)
        for metric_name, value in section.model_dump().items():
            if not isinstance(value, (int, float)):
                continue
            is_technical = section_name == "technical"
            period = (
                metrics.fundamentals.fiscal_period
                if metric_name.endswith("_ttm")
                else f"as of {data.as_of_date}"
            )
            ledger.evidence_items.append(
                EvidenceItem(
                    evidence_id=f"TEST_EXACT_{metric_name.upper()}",
                    ticker=data.ticker,
                    claim_type=(
                        "technical_metric"
                        if is_technical
                        else "valuation_metric"
                        if section_name == "valuation"
                        else "financial_metric"
                    ),
                    source_id="TEST_EXACT_EVIDENCE",
                    source_type="deterministic_calculation",
                    authority_rank=1,
                    statement=f"Exact evidence for {metric_name}.",
                    value=float(value),
                    unit=unit_for_metric(
                        metric_name,
                        currency=data.price_basis.currency,
                    ),
                    period=period,
                    date=(metrics.technical.indicator_date if is_technical else data.as_of_date),
                    supports_metrics=[metric_name],
                    confidence="high",
                )
            )


def test_content_generator_keeps_only_evidence_mapped_substantive_claims():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    quality = claim_quality_metrics(claims)

    assert quality["analyst_claim_count"] < 15
    assert quality["evidence_mapped_claim_ratio"] >= 0.90
    assert quality["hard_claim_evidence_ratio"] == 1.0
    assert quality["generic_claim_count"] == 0
    assert quality["substantive_analyst_claim_count"] >= 10
    assert all(claim.evidence_ids for claim in claims)
    valuation_claim = next(
        claim
        for claim in claims
        if claim.section == "Valuation / Multiples" and claim.claim.startswith("EV/Sales is")
    )
    technical_claim = next(claim for claim in claims if "50-SMA" in claim.claim)
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


def test_sbc_claim_uses_matching_share_count_trend_when_available():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.sbc_to_revenue = 0.018
    metrics.fundamentals.diluted_share_count_yoy = -26 / 909
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    sbc_claim = next(claim for claim in claims if claim.claim.startswith("SBC/Revenue"))

    assert "diluted weighted-average share count decreased by 2.9%" in sbc_claim.claim
    assert "does not attribute the move solely to SBC or repurchases" in sbc_claim.claim
    assert sbc_claim.metric_refs == [
        "sbc_to_revenue",
        "diluted_share_count_yoy",
    ]


def test_content_generator_uses_trailing_pe_without_point_in_time_share_count():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.valuation.market_cap = None
    metrics.valuation.enterprise_value = None
    metrics.valuation.ev_to_sales = None
    metrics.valuation.price_to_fcf = None
    metrics.valuation.trailing_pe = 19.86
    metrics.fundamentals.trailing_eps = metrics.technical.close / 19.86
    decision.signal_scores.valuation_status = "unbenchmarked"
    decision.signal_scores.valuation_score = 0
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    quality = claim_quality_metrics(claims)
    report = compose_research_report(
        data,
        metrics,
        validation,
        decision,
        ledger,
        claims,
        reconciliation_warnings=[
            {
                "severity": "warning",
                "code": "MULTI_CLASS_PRICE_BASIS_UNAVAILABLE",
                "metric": "market_cap",
                "message": "Cross-class price equivalence is unverified.",
            }
        ],
    )
    valuation_claim = next(claim for claim in claims if claim.section == "Valuation / Multiples")

    assert valuation_claim.claim.startswith("For SNOW, trailing P/E is 19.86x")
    assert valuation_claim.metric_refs == ["trailing_pe", "close", "trailing_eps"]
    assert valuation_claim.metric_values["trailing_pe"] == 19.86
    assert "missing_valuation_analysis" not in claim_coverage_gaps(quality)
    assert "Valuation status: trailing P/E `19.86x` is an unbenchmarked observation" in report
    assert "EV/Sales `unavailable`" not in report
    assert (
        "Market-cap-derived multiples are unavailable because the filing "
        "reports multiple stock classes"
    ) in report


def test_content_generator_explains_extreme_positive_price_to_fcf():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.valuation.price_to_fcf = 213.32
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    valuation_claim = next(
        claim
        for claim in claims
        if claim.section == "Valuation / Multiples" and "P/FCF is 213.32x" in claim.claim
    )

    assert "highly sensitive to the durability and growth of cash flow" in (valuation_claim.claim)
    assert "requires explicit manual review before publication" in (valuation_claim.claim)
    audit = audit_markdown_report(
        valuation_claim.claim,
        metrics,
        decision_packet=decision,
        ticker=data.ticker,
    )
    assert not audit.has_issue("NUMERIC_MISMATCH")


def test_compact_claim_set_can_cover_every_required_dimension():
    metrics = {
        "analyst_claim_count": 9,
        "evidence_mapped_claim_ratio": 1.0,
        "hard_claim_evidence_ratio": 1.0,
        "substantive_claim_ratio": 7 / 9,
        "generic_claim_ratio": 0.0,
        "data_limitation_claim_count": 0,
        "current_period_kpi_claim_count": 3,
        "current_period_kpi_metric_count": 3,
        "ticker_specific_kpi_claim_count": 3,
        "final_rating_rationale_quality": 80,
        "company_specific_claim_count": 4,
        "valuation_specific_claim_count": 1,
        "technical_specific_claim_count": 1,
        "rating_rationale_claim_count": 1,
        "risk_specific_claim_count": 1,
    }

    assert claim_coverage_gaps(metrics) == []


def test_claim_coverage_names_missing_topics_instead_of_padding_count():
    metrics = {
        "analyst_claim_count": 30,
        "evidence_mapped_claim_ratio": 1.0,
        "hard_claim_evidence_ratio": 1.0,
        "substantive_claim_ratio": 0.80,
        "generic_claim_ratio": 0.0,
        "data_limitation_claim_count": 0,
        "current_period_kpi_claim_count": 4,
        "current_period_kpi_metric_count": 4,
        "ticker_specific_kpi_claim_count": 4,
        "final_rating_rationale_quality": 80,
        "company_specific_claim_count": 5,
        "valuation_specific_claim_count": 0,
        "technical_specific_claim_count": 2,
        "rating_rationale_claim_count": 1,
        "risk_specific_claim_count": 1,
    }

    assert claim_coverage_gaps(metrics) == ["missing_valuation_analysis"]


def test_claim_coverage_names_missing_risk_analysis_without_padding():
    metrics = {
        "analyst_claim_count": 12,
        "evidence_mapped_claim_ratio": 1.0,
        "hard_claim_evidence_ratio": 1.0,
        "substantive_claim_ratio": 0.75,
        "generic_claim_ratio": 0.0,
        "data_limitation_claim_count": 0,
        "current_period_kpi_metric_count": 4,
        "final_rating_rationale_quality": 80,
        "company_specific_claim_count": 5,
        "valuation_specific_claim_count": 2,
        "technical_specific_claim_count": 2,
        "rating_rationale_claim_count": 1,
        "risk_specific_claim_count": 0,
    }

    assert claim_coverage_gaps(metrics) == ["missing_risk_analysis"]


def test_content_generator_turns_primary_risk_evidence_into_qualitative_claims():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    ledger.evidence_items.append(
        EvidenceItem(
            evidence_id="SNOW_SEC_RISK_001",
            ticker="SNOW",
            claim_type="risk",
            source_id="SEC_SNOW_10K",
            source_type="sec_filing",
            authority_rank=1,
            statement="Service interruptions could adversely affect customer demand",
            period="10-K period ended 2026-01-31",
            date="2026-03-20",
            supports_claims=["company_risk_analysis"],
            confidence="high",
        )
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    risk_claim = next(claim for claim in claims if claim.claim_type == "risk")

    assert risk_claim.section == "Key Risks"
    assert "customer demand. This identifies an exposure" in risk_claim.claim
    assert risk_claim.metric_refs == []
    assert risk_claim.evidence_ids == ["SNOW_SEC_RISK_001"]
    assert claim_quality_metrics(claims)["risk_specific_claim_count"] == 1


def test_content_generator_preserves_issuer_risk_order():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    ledger.evidence_items = [item for item in ledger.evidence_items if item.claim_type != "risk"]
    ledger.evidence_items.extend(
        EvidenceItem(
            evidence_id=f"SNOW_SEC_RISK_{index:03d}",
            ticker="SNOW",
            claim_type="risk",
            source_id="SEC_SNOW_10K",
            source_type="sec_filing",
            authority_rank=1,
            statement=f"Issuer-ordered risk {index}",
            period="10-K period ended 2026-01-31",
            date="2026-03-20",
            supports_claims=["company_risk_analysis"],
            confidence="high",
        )
        for index in range(1, 7)
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    risk_claims = [claim for claim in claims if claim.claim_type == "risk"]

    assert [claim.evidence_ids[0] for claim in risk_claims] == [
        "SNOW_SEC_RISK_001",
        "SNOW_SEC_RISK_002",
        "SNOW_SEC_RISK_003",
        "SNOW_SEC_RISK_004",
    ]


def test_content_generator_avoids_repeating_one_risk_theme_when_alternatives_exist():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    ledger.evidence_items = [item for item in ledger.evidence_items if item.claim_type != "risk"]
    statements = [
        "A serious aircraft accident could damage our operations and reputation.",
        "A breach of our technology systems could disrupt operations.",
        "Information technology infrastructure failures could disrupt operations.",
        "Failure of the technology we use could materially harm the business.",
        "Aircraft fuel price increases could reduce profitability.",
        "Strategic airline investments may not produce the expected returns.",
    ]
    ledger.evidence_items.extend(
        EvidenceItem(
            evidence_id=f"SNOW_SEC_RISK_{index:03d}",
            ticker="SNOW",
            claim_type="risk",
            source_id="SEC_SNOW_10K",
            source_type="sec_filing",
            authority_rank=1,
            statement=statement,
            period="10-K period ended 2026-01-31",
            date="2026-03-20",
            supports_claims=["company_risk_analysis"],
            confidence="high",
        )
        for index, statement in enumerate(statements, start=1)
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    risk_claims = [claim for claim in claims if claim.claim_type == "risk"]

    assert [claim.evidence_ids[0] for claim in risk_claims] == [
        "SNOW_SEC_RISK_001",
        "SNOW_SEC_RISK_002",
        "SNOW_SEC_RISK_005",
        "SNOW_SEC_RISK_006",
    ]


def test_content_generator_avoids_repeating_pharma_ip_risks():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    ledger.evidence_items = [item for item in ledger.evidence_items if item.claim_type != "risk"]
    statements = [
        "Loss of patent protection and competition from generics may reduce revenues.",
        "Major products could lose patent protection earlier than expected.",
        "Third-party intellectual property may prevent sales of our products.",
        "Research and development efforts may not produce commercial products.",
        "Regulatory approvals may be delayed or denied.",
        "Supply chain failures could disrupt product availability.",
    ]
    ledger.evidence_items.extend(
        EvidenceItem(
            evidence_id=f"SNOW_SEC_RISK_{index:03d}",
            ticker="SNOW",
            claim_type="risk",
            source_id="SEC_SNOW_10K",
            source_type="sec_filing",
            authority_rank=1,
            statement=statement,
            period="10-K period ended 2026-01-31",
            date="2026-03-20",
            supports_claims=["company_risk_analysis"],
            confidence="high",
        )
        for index, statement in enumerate(statements, start=1)
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    risk_claims = [claim for claim in claims if claim.claim_type == "risk"]

    assert [claim.evidence_ids[0] for claim in risk_claims] == [
        "SNOW_SEC_RISK_001",
        "SNOW_SEC_RISK_004",
        "SNOW_SEC_RISK_005",
        "SNOW_SEC_RISK_006",
    ]


def test_bear_case_uses_balance_sheet_constraint_and_primary_risk_evidence():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.equity = -5_935_000_000
    metrics.fundamentals.current_ratio = 0.81
    metrics.fundamentals.free_cash_flow_ttm = 18_210_000_000
    metrics.technical.close = 243.80
    metrics.technical.sma_50 = 239.32
    metrics.technical.sma_200 = 224.86
    ledger.evidence_items = [item for item in ledger.evidence_items if item.claim_type != "risk"]
    ledger.evidence_items.append(
        EvidenceItem(
            evidence_id="SNOW_SEC_RISK_PATENT",
            ticker="SNOW",
            claim_type="risk",
            source_id="SEC_SNOW_10K",
            source_type="sec_filing",
            authority_rank=1,
            statement=(
                "The expiration or loss of patent protection may adversely affect "
                "revenues and operating earnings."
            ),
            period="10-K period ended 2026-01-31",
            date="2026-03-20",
            supports_claims=["company_risk_analysis"],
            confidence="high",
        )
    )
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    bear = next(claim for claim in claims if claim.section == "Bear Case")

    assert "Separate balance-sheet or issuer-disclosed downside evidence anchors" in bear.claim
    assert "does not by itself prove current operating deterioration" in bear.claim
    assert "Book equity of -$5.93B" in bear.claim
    assert "current ratio of 0.81x" in bear.claim
    assert "expiration or loss of patent protection" in bear.claim
    assert {"equity", "current_ratio"}.issubset(set(bear.metric_refs))
    assert "SNOW_SEC_RISK_PATENT" in bear.evidence_ids


def test_positive_fcf_is_qualified_by_sbc_to_fcf():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.free_cash_flow_ttm = 1_169_702_000
    metrics.fundamentals.sbc_to_fcf = 1.387
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    fcf_claim = next(
        claim
        for claim in claims
        if claim.section == "Fundamental Analysis" and claim.claim.startswith("FCF TTM is")
    )
    thesis = _generic_investment_thesis("SNOW", "Hold", metrics, decision)

    assert "SBC equals 138.7% of that FCF" in fcf_claim.claim
    assert "sbc_to_fcf" in fcf_claim.metric_refs
    assert "SBC equals 138.7% of FCF" in thesis
    assert "qualifies shareholder-level cash conversion" in thesis


def test_cash_and_marketable_helper_includes_current_and_noncurrent_securities():
    _data, metrics, _validation, _ledger, _decision = _load_packet("SNOW")
    metrics.fundamentals.cash_and_investments = None
    metrics.fundamentals.cash_and_equivalents = 2_084_715_000
    metrics.fundamentals.short_term_investments = 870_283_000
    metrics.fundamentals.marketable_securities = 1_432_494_000

    assert _cash_and_marketable_securities(metrics.fundamentals) == 4_387_492_000


def test_money_formatters_place_negative_sign_before_usd_symbol():
    assert _money(-11_625_000_000, "USD") == "-$11.62B"
    assert _report_money(-11_625_000_000, "USD") == "-$11.62B"
    assert _publish_money(-11_625_000_000, "USD") == "-$11.62B"
    assert _money(-11_625_000_000, "HUF") == "-11.62B HUF"


def test_bear_case_with_unadjusted_prices_never_states_direction():
    _, metrics, _, _, _ = _load_packet("SNOW")
    metrics.technical.close = 120.0
    metrics.technical.sma_50 = 110.0
    metrics.technical.sma_200 = 100.0
    bullish = _bear_case_claim_text("TEST", metrics, "USD")

    metrics.technical.close = 80.0
    metrics.technical.sma_50 = 90.0
    bearish = _bear_case_claim_text("TEST", metrics, "USD")

    metrics.technical.close = 105.0
    mixed = _bear_case_claim_text("TEST", metrics, "USD")

    for text in (bullish, bearish, mixed):
        assert "unscored raw moving-average observations" in text
        assert "no bullish or bearish technical conclusion is activated" in text
        assert "does not establish operating deterioration" in text
        assert "fundamental, valuation or issuer-risk evidence" in text


def test_bear_case_with_adjusted_prices_retains_directional_timing_context():
    _, metrics, _, _, _ = _load_packet("SNOW")
    metrics.technical.price_series_basis = "corporate_action_adjusted"
    metrics.technical.close = 120.0
    metrics.technical.sma_50 = 110.0
    metrics.technical.sma_200 = 100.0

    text = _bear_case_claim_text("TEST", metrics, "USD")

    assert "a bullish long-term trend state" in text
    assert "unscored raw moving-average observations" not in text


def test_unadjusted_claim_surfaces_withhold_direction_and_numeric_reference_levels():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.technical.price_series_basis = "unadjusted_or_provider_default"
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
    )
    technical_surfaces = "\n".join(
        claim.claim
        for claim in claims
        if claim.section
        in {
            "Executive Summary",
            "Technical Setup",
            "Bull Case",
            "Bear Case",
            "Catalysts & Triggers",
        }
    ).lower()

    assert "provisional bullish" not in technical_surfaces
    assert "provisional bearish" not in technical_surfaces
    assert "combined long-term trend state is" not in technical_surfaces
    assert "a constructive technical bull path" not in technical_surfaces
    assert "no constructive technical bull path is activated" in technical_surfaces
    assert "validated technical reference levels" not in technical_surfaces
    assert "no bullish or bearish technical conclusion is activated" in technical_surfaces
    assert "not validated support, resistance, risk or trigger levels" in technical_surfaces

    internal_report = compose_internal_best_report(
        data,
        metrics,
        decision,
        ledger,
        claims,
        status="manual_review",
        publishable=False,
    ).lower()
    assert "timing remains part of the rating debate" not in internal_report
    assert "partial technical evidence" not in internal_report
    assert "technical inputs are unscored raw observations" in internal_report
    assert "they do not enter the rating or timing" in internal_report
    assert "technical inputs are excluded from rating and timing" in internal_report
    assert "technical evidence remains a timing overlay" not in internal_report
    assert "stronger verified technical" not in internal_report
    assert "scenario_measured" not in internal_report
    assert "low_financial_risk" not in internal_report


def test_adjusted_claim_surfaces_retain_validated_direction_and_reference_levels():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.technical.price_series_basis = "corporate_action_adjusted"
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
    )
    claim_text = "\n".join(claim.claim for claim in claims).lower()

    assert "combined long-term trend state is bearish" in claim_text
    assert "constructive technical bull path" in claim_text
    assert "validated technical reference levels" in claim_text


def test_ytd_cash_flow_claim_binds_ytd_capex_instead_of_same_date_quarter():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    data.as_of_date = "2026-08-07"
    metrics.as_of_date = "2026-08-07"
    _add_exact_metric_evidence(data, metrics, ledger)
    canonical = CanonicalFinancials(
        ticker=data.ticker,
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name="operating_cash_flow",
                value=7_543_000_000,
                unit="USD",
                period="FY2026_Q2",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="ytd",
                start_date="2026-01-01",
                end_date="2026-07-03",
                duration_days=184,
                basis="gaap",
                statement_type="cash_flow",
                source_ids=["SEC_Q2"],
                evidence_ids=["OCF_YTD"],
                confidence="high",
            ),
            CanonicalMetric(
                metric_name="capex",
                value=684_000_000,
                unit="USD",
                period="FY2026_Q2",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="ytd",
                start_date="2026-01-01",
                end_date="2026-07-03",
                duration_days=184,
                basis="gaap",
                statement_type="cash_flow",
                source_ids=["SEC_Q2"],
                evidence_ids=["CAPEX_YTD"],
                confidence="high",
            ),
            CanonicalMetric(
                metric_name="capex",
                value=418_000_000,
                unit="USD",
                period="FY2026_Q2",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="quarterly",
                start_date="2026-04-04",
                end_date="2026-07-03",
                duration_days=91,
                basis="gaap",
                statement_type="cash_flow",
                source_ids=["SEC_Q2"],
                evidence_ids=["CAPEX_QUARTER"],
                confidence="high",
            ),
        ],
    )
    ledger.evidence_items.extend(
        [
            EvidenceItem(
                evidence_id="OCF_YTD",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="SEC_Q2",
                source_type="sec_filing",
                authority_rank=1,
                statement="YTD operating cash flow.",
                value=7_543_000_000,
                raw_value=7_543_000_000,
                normalized_value=7_543_000_000,
                unit="USD",
                period="FY2026_Q2",
                date="2026-07-03",
                period_start="2026-01-01",
                period_end="2026-07-03",
                duration_days=184,
                supports_metrics=["operating_cash_flow"],
                confidence="high",
            ),
            EvidenceItem(
                evidence_id="CAPEX_YTD",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="SEC_Q2",
                source_type="sec_filing",
                authority_rank=1,
                statement="YTD capital expenditure.",
                value=684_000_000,
                raw_value=684_000_000,
                normalized_value=684_000_000,
                unit="USD",
                period="FY2026_Q2",
                date="2026-07-03",
                period_start="2026-01-01",
                period_end="2026-07-03",
                duration_days=184,
                supports_metrics=["capex"],
                confidence="high",
            ),
            EvidenceItem(
                evidence_id="CAPEX_QUARTER",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="SEC_Q2",
                source_type="sec_filing",
                authority_rank=1,
                statement="Second-quarter capital expenditure.",
                value=418_000_000,
                raw_value=418_000_000,
                normalized_value=418_000_000,
                unit="USD",
                period="FY2026_Q2",
                date="2026-07-03",
                period_start="2026-04-04",
                period_end="2026-07-03",
                duration_days=91,
                supports_metrics=["capex"],
                confidence="high",
            ),
        ]
    )

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    cash_flow_claim = next(
        claim for claim in claims if "latest reported period (year to date)" in claim.claim
    )

    assert cash_flow_claim.metric_values["operating_cash_flow"] == 7_543_000_000
    assert cash_flow_claim.metric_values["capex"] == 684_000_000
    assert "OCF_YTD" in cash_flow_claim.evidence_ids
    assert "CAPEX_YTD" in cash_flow_claim.evidence_ids
    assert "CAPEX_QUARTER" not in cash_flow_claim.evidence_ids


def test_full_year_cash_flow_claim_uses_latest_annual_pair():
    _, metrics, _, _, _ = _load_packet("SNOW")

    def cash_metric(name, value, start, end, bucket, fiscal_year):
        return CanonicalMetric(
            metric_name=name,
            value=value,
            unit="USD",
            period=f"FY{fiscal_year}",
            fiscal_year=fiscal_year,
            fiscal_period="FY",
            period_bucket=bucket,
            start_date=start,
            end_date=end,
            basis="gaap",
            statement_type="cash_flow",
            source_ids=[f"SEC_FY{fiscal_year}"],
            confidence="high",
        )

    canonical = CanonicalFinancials(
        ticker="MSFT",
        as_of_date="2026-08-07",
        metrics=[
            cash_metric(
                "operating_cash_flow",
                127_490_000_000,
                "2024-07-01",
                "2025-06-30",
                "ytd",
                2025,
            ),
            cash_metric(
                "capex",
                80_150_000_000,
                "2024-07-01",
                "2025-06-30",
                "ytd",
                2025,
            ),
            cash_metric(
                "operating_cash_flow",
                182_935_000_000,
                "2025-07-01",
                "2026-06-30",
                "annual",
                2026,
            ),
            cash_metric(
                "capex",
                115_948_000_000,
                "2025-07-01",
                "2026-06-30",
                "annual",
                2026,
            ),
        ],
    )

    specs = _current_period_claim_specs("MSFT", metrics, canonical)
    cash_spec = next(
        spec for spec in specs if spec.get("metrics") == ["operating_cash_flow", "capex"]
    )

    assert "latest reported fiscal year" in str(cash_spec["text"])
    assert cash_spec["metric_values"] == {
        "operating_cash_flow": 182_935_000_000,
        "capex": 115_948_000_000,
    }


def test_bear_case_treats_negative_fcf_as_downside_not_counterevidence():
    _, metrics, _, _, _ = _load_packet("SNOW")
    metrics.fundamentals.free_cash_flow_ttm = -11_625_000_000
    metrics.technical.close = 120.0
    metrics.technical.sma_50 = 110.0
    metrics.technical.sma_200 = 100.0

    bullish = _bear_case_claim_text("TEST", metrics, "USD")

    assert "Negative FCF TTM of -$11.62B" in bullish
    assert "current fundamental downside evidence" in bullish
    assert "does not establish operating deterioration" in bullish
    assert "counterevidence" not in bullish


def test_bull_case_does_not_present_negative_fcf_as_cash_generation():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.free_cash_flow_ttm = -11_625_000_000
    ledger.evidence_items = [
        item for item in ledger.evidence_items if "free_cash_flow_ttm" not in item.supports_metrics
    ]
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    bull_claim = next(
        claim
        for claim in claims
        if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
    )

    assert "negative FCF is a cash-conversion constraint" in bull_claim.claim
    assert "scale and cash generation" not in bull_claim.claim
    assert "reconciliation anomalies" not in bull_claim.counterargument
    assert "unbenchmarked valuation" in bull_claim.counterargument

    bear_claim = next(claim for claim in claims if claim.section == "Bear Case")
    assert (
        bear_claim.investment_implication
        == "Treat the bear case as evidence to monitor, not as proof of permanent "
        "business deterioration."
    )


def test_capex_driven_negative_fcf_is_not_called_weak_operations():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    fundamentals = metrics.fundamentals
    fundamentals.revenue_ttm = 33_166_000_000
    fundamentals.current_period_revenue_growth_yoy = 0.1126
    fundamentals.current_period_operating_income_growth_yoy = 0.1630
    fundamentals.current_period_net_income_growth_yoy = 0.1240
    fundamentals.operating_cash_flow_ttm = 11_665_000_000
    fundamentals.capex_ttm = 14_964_000_000
    fundamentals.free_cash_flow_ttm = -3_299_000_000
    ledger.evidence_items = [
        item
        for item in ledger.evidence_items
        if not set(item.supports_metrics).intersection(
            {
                "revenue_ttm",
                "current_period_revenue_growth_yoy",
                "current_period_operating_income_growth_yoy",
                "current_period_net_income_growth_yoy",
                "operating_cash_flow_ttm",
                "capex_ttm",
                "free_cash_flow_ttm",
            }
        )
    ]
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    fundamental = next(claim for claim in claims if claim.section == "Fundamental Analysis")
    bull = next(claim for claim in claims if claim.section == "Bull Case")
    bear = next(claim for claim in claims if claim.section == "Bear Case")

    assert "investment funding gap" in fundamental.claim
    assert "maintenance-versus-growth split" in fundamental.claim
    assert set(fundamental.metric_refs) == {
        "free_cash_flow_ttm",
        "capex_ttm",
        "operating_cash_flow_ttm",
    }
    assert "funding requirement rather than proving weak operations" in bull.claim
    assert "does not by itself establish weak operations" in bear.claim
    assert "Technical timing context is" in bear.claim
    assert "does not establish operating deterioration" in bear.claim
    assert all("weak cash conversion" not in claim.claim for claim in (fundamental, bull, bear))


def test_bull_case_does_not_call_extreme_profit_divergence_business_direction():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.current_period_revenue_growth_yoy = -0.014
    metrics.fundamentals.current_period_operating_income_growth_yoy = 1.314
    metrics.fundamentals.current_period_net_income_growth_yoy = 0.872
    canonical = CanonicalFinancials(
        ticker=data.ticker,
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="FY2026_Q2",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="quarterly",
                start_date="2026-03-22",
                end_date="2026-06-13",
                duration_days=84,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_Q2"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 24_180_000_000),
                ("operating_income", 4_023_000_000),
                ("net_income", 2_981_000_000),
            )
        ],
    )
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    bull_claim = next(
        claim
        for claim in claims
        if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
    )
    final_claim = next(
        claim
        for claim in claims
        if claim.section == "Final Rating & Action Plan" and claim.claim_type == "rating"
    )

    assert "require base-effect or one-off review" in bull_claim.claim
    assert "do not establish operating business direction" in bull_claim.claim
    assert "profit comparisons" in bull_claim.claim
    assert "diverge from revenue growth and require" in bull_claim.claim
    assert "guarded profit comparisons" in bull_claim.claim
    assert "establishes current business direction" not in bull_claim.claim
    assert "extreme current-period profit comparisons" in final_claim.claim
    assert "measured fundamental signal is constructive" not in final_claim.claim


def test_extreme_negative_profit_divergence_is_not_operating_downside_evidence():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.free_cash_flow_ttm = 20_440_000_000
    metrics.fundamentals.current_period_revenue_growth_yoy = -0.012
    metrics.fundamentals.current_period_operating_income_growth_yoy = -0.139
    metrics.fundamentals.current_period_net_income_growth_yoy = -0.683
    canonical = CanonicalFinancials(
        ticker=data.ticker,
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="FY2026_Q2",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="quarterly",
                start_date="2026-04-01",
                end_date="2026-06-30",
                duration_days=90,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_Q2"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 29_940_000_000),
                ("operating_income", 5_160_000_000),
                ("net_income", 3_526_000_000),
            )
        ],
    )
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    bull = next(
        claim
        for claim in claims
        if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
    )
    bear = next(claim for claim in claims if claim.section == "Bear Case")
    final_claim = next(
        claim
        for claim in claims
        if claim.section == "Final Rating & Action Plan" and claim.claim_type == "rating"
    )
    final_section = _final_rating_section(
        "TEST",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )

    assert "requires base-effect or one-off review" in bull.claim
    assert (
        "without causal filing evidence in the current packet, that comparison "
        "does not establish operating business direction"
    ) in bull.claim
    assert (
        "Separately, operating-income decline 13.9% remains measured "
        "current-period downside evidence"
    ) in bull.claim
    assert "operating-income decline" in bear.claim
    assert "net-income decline" not in bear.claim
    assert "operating-income decline" in final_claim.claim
    assert "net-income declines" not in final_claim.claim
    assert "Current-period operating-income decline" in final_section
    assert "net-income declines" not in final_section


def test_bull_case_calls_mixed_growth_mixed_not_business_direction():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.current_period_revenue_growth_yoy = 0.002
    metrics.fundamentals.current_period_operating_income_growth_yoy = None
    metrics.fundamentals.current_period_net_income_growth_yoy = -0.034
    canonical = CanonicalFinancials(
        ticker=data.ticker,
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="FY2026",
                fiscal_year=2026,
                fiscal_period="FY",
                period_bucket="annual",
                start_date="2025-06-01",
                end_date="2026-05-31",
                duration_days=364,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_FY2026"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 46_398_000_000),
                ("gross_profit", 19_911_000_000),
                ("net_income", 3_108_000_000),
            )
        ],
    )
    adjusted_eps = CanonicalMetric(
        metric_name="adjusted_eps_diluted",
        value=3.03,
        unit="USD_per_share",
        period="FY2026",
        fiscal_year=2026,
        fiscal_period="FY",
        period_bucket="annual",
        start_date="2025-06-01",
        end_date="2026-05-31",
        duration_days=364,
        basis="non_gaap",
        statement_type="income_statement",
        source_ids=["GENERIC_SEC_RESULTS"],
        evidence_ids=["GENERIC_ADJUSTED_EPS"],
        confidence="high",
    )
    canonical.metrics.append(adjusted_eps)
    _add_exact_metric_evidence(data, metrics, ledger)
    ledger.evidence_items.append(
        EvidenceItem(
            evidence_id="GENERIC_ADJUSTED_EPS",
            ticker=data.ticker,
            claim_type="financial_metric",
            source_id="GENERIC_SEC_RESULTS",
            source_type="sec_filing",
            authority_rank=1,
            statement="Adjusted EPS was $3.03.",
            normalized_value=3.03,
            value=3.03,
            unit="USD_per_share",
            period="FY2026",
            date="2026-05-31",
            supports_metrics=["adjusted_eps_diluted"],
            confidence="high",
        )
    )

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    bull_claim = next(
        claim
        for claim in claims
        if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
    )

    assert "revenue growth 0.2%" in bull_claim.claim
    assert "net-income decline 3.4%" in bull_claim.claim
    assert "Issuer-filed adjusted-result context is present" in bull_claim.claim
    assert "the negative GAAP comparison" in bull_claim.claim
    assert "segment, margin" not in bull_claim.claim
    assert "profit declines" not in bull_claim.claim
    assert "broad-based operating improvement" in bull_claim.claim
    assert "current business direction" not in bull_claim.claim
    assert all("net-income declines" not in claim.claim for claim in claims)
    assert any("net-income decline" in claim.claim for claim in claims)
    report = compose_research_report(
        data,
        metrics,
        validation,
        decision,
        ledger,
        claims,
    )
    assert "Current-period net-income decline is current downside evidence" in report
    assert "The net-income decline is not dismissed" in report
    assert "net-income declines" not in report


def test_non_positive_equity_is_visible_with_liquidity_and_lease_context():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.equity = -7_674_300_000
    metrics.fundamentals.current_ratio = 0.7597
    metrics.fundamentals.total_lease_liabilities = 9_155_500_000
    metrics.fundamentals.debt_to_equity = None
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    constraint = next(
        claim for claim in claims if "debt/equity is not a meaningful leverage ratio" in claim.claim
    )

    assert "Book equity is -$7.67B" in constraint.claim
    assert "current ratio is 0.76x" in constraint.claim
    assert "lease liabilities total $9.16B" in constraint.claim
    assert "does not by itself establish insolvency" in constraint.claim
    assert constraint.metric_refs == [
        "equity",
        "current_ratio",
        "total_lease_liabilities",
    ]


def test_sub_one_current_ratio_is_visible_without_claiming_distress():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.equity = 94_330_000_000
    metrics.fundamentals.current_ratio = 0.7714
    metrics.fundamentals.total_lease_liabilities = 22_723_000_000
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    constraint = next(claim for claim in claims if "current ratio below 1.0x" in claim.claim)

    assert "current ratio is 0.77x" in constraint.claim
    assert "lease liabilities total $22.72B" in constraint.claim
    assert "does not by itself establish an inability" in constraint.claim
    assert "recurring receipts or rapid working-capital turnover" in constraint.counterargument
    assert "Retail" not in constraint.counterargument
    assert constraint.metric_refs == [
        "current_ratio",
        "total_lease_liabilities",
    ]


def test_partial_lease_context_stays_partial_in_liquidity_claim():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.equity = 16_395_000_000
    metrics.fundamentals.current_ratio = 0.932
    metrics.fundamentals.lease_liability_current = None
    metrics.fundamentals.lease_liability_noncurrent = 3_416_000_000
    metrics.fundamentals.total_lease_liabilities = None
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    constraint = next(
        claim for claim in claims if "complete lease-liability total is unavailable" in claim.claim
    )

    assert "available noncurrent lease liabilities are $3.42B" in constraint.claim
    assert "lease liabilities total $3.42B" not in constraint.claim
    assert constraint.metric_refs == [
        "current_ratio",
        "lease_liability_noncurrent",
    ]


def test_complete_lease_obligations_remain_visible_above_one_current_ratio():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.equity = 15_763_000_000
    metrics.fundamentals.current_ratio = 1.2126
    metrics.fundamentals.total_lease_liabilities = 4_276_000_000
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    lease_claim = next(
        claim for claim in claims if "Finance-lease amounts can overlap" in claim.claim
    )

    assert "Separately disclosed lease liabilities total $4.28B" in lease_claim.claim
    assert "not added to total debt or enterprise value" in lease_claim.claim
    assert "In addition to reported debt" not in lease_claim.claim
    assert lease_claim.metric_refs == ["total_lease_liabilities"]
    assert "debt, lease obligations, liquidity" in lease_claim.investment_implication


def test_aligned_positive_quarter_is_direction_not_durability_or_cause():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.current_period_revenue_growth_yoy = 0.073
    metrics.fundamentals.current_period_operating_income_growth_yoy = 0.050
    metrics.fundamentals.current_period_net_income_growth_yoy = 0.188
    metrics.fundamentals.free_cash_flow_ttm = 12_552_000_000
    canonical = CanonicalFinancials(
        ticker=data.ticker,
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="FY2027_Q1",
                fiscal_year=2027,
                fiscal_period="Q1",
                period_bucket="quarterly",
                start_date="2026-02-01",
                end_date="2026-04-30",
                duration_days=89,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_Q1"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 177_751_000_000),
                ("operating_income", 7_493_000_000),
                ("net_income", 5_330_000_000),
            )
        ],
    )
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    bull_claim = next(
        claim
        for claim in claims
        if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
    )

    assert "records aligned current-period direction" in bull_claim.claim
    assert "does not establish durability or cause" in bull_claim.claim
    assert "establishes current business direction" not in bull_claim.claim


def test_bull_case_does_not_call_revenue_growth_operating_improvement_during_loss():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.current_period_revenue_growth_yoy = 0.08
    metrics.fundamentals.current_period_operating_income_growth_yoy = None
    metrics.fundamentals.current_period_net_income_growth_yoy = None
    metrics.fundamentals.free_cash_flow_ttm = -210_000_000
    canonical = CanonicalFinancials(
        ticker=data.ticker,
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="FY2026_Q2",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="quarterly",
                start_date="2026-04-01",
                end_date="2026-06-30",
                duration_days=91,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_Q2"],
                evidence_ids=[evidence_id],
                confidence="high",
            )
            for metric_name, value, evidence_id in (
                ("revenue", 24_560_000_000, "GENERIC_REVENUE_Q2"),
                ("operating_income", 156_000_000, "GENERIC_OPERATING_INCOME_Q2"),
                ("net_income", -444_000_000, "GENERIC_NET_INCOME_Q2"),
            )
        ],
    )
    _add_exact_metric_evidence(data, metrics, ledger)
    ledger.evidence_items.append(
        EvidenceItem(
            evidence_id="GENERIC_NET_INCOME_Q2",
            ticker=data.ticker,
            claim_type="financial_metric",
            source_id="GENERIC_SEC_Q2",
            source_type="regulatory_filing",
            authority_rank=1,
            statement="Current-period net income was a loss.",
            value=-444_000_000,
            unit="USD",
            period="FY2026_Q2",
            date="2026-06-30",
            supports_metrics=["net_income"],
            confidence="high",
        )
    )

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    bull_claim = next(
        claim
        for claim in claims
        if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
    )

    assert "latest reported period still contains a net loss" in bull_claim.claim
    assert "do not establish operating improvement" in bull_claim.claim
    assert "net_income" in bull_claim.metric_refs
    assert "establishes current business direction" not in bull_claim.claim


def test_generic_report_routes_claims_without_repeating_main_body_paragraphs():
    _, metrics, _, ledger, decision = _load_packet("SNOW")

    def claim(
        claim_id: str,
        section: str,
        text: str,
        metric_refs: list[str],
    ) -> ResearchClaim:
        return ResearchClaim(
            claim_id=claim_id,
            section=section,
            agent="test",
            claim=text,
            claim_text=text,
            evidence_metrics=metric_refs,
            metric_refs=metric_refs,
            evidence_ids=["SEC_TEST"],
            source_ids=["SEC_TEST"],
            confidence="high",
        )

    claims = [
        claim("EXEC", "Executive Summary", "Executive summary marker 101.", []),
        claim(
            "BUSINESS",
            "Business & Segment Context",
            "Business context marker 202.",
            [],
        ),
        claim(
            "CURRENT",
            "Fundamental Analysis",
            "Current revenue growth marker 303.",
            ["current_period_revenue_growth_yoy"],
        ),
        claim(
            "FCF",
            "Fundamental Analysis",
            "Free cash flow marker 404.",
            ["free_cash_flow_ttm"],
        ),
        claim(
            "BALANCE_SHEET",
            "Fundamental Analysis",
            "Current ratio balance-sheet marker 406.",
            ["equity", "current_ratio", "total_lease_liabilities"],
        ),
        claim(
            "BULL",
            "Bull Case",
            "Bull case current-period marker 405.",
            ["current_period_revenue_growth_yoy"],
        ),
        claim(
            "VALUATION",
            "Valuation / Multiples",
            "Valuation marker 505.",
            ["ev_to_sales"],
        ),
    ]
    grouped = {
        section: [item for item in claims if item.section == section]
        for section in {item.section for item in claims}
    }

    report = _generic_publish_report(
        "TEST",
        "Hold",
        grouped,
        metrics,
        decision,
        claims,
        ledger,
    )
    main_body = report.split("## Evidence Appendix", 1)[0]
    current_section = main_body.split("## Current Period KPIs", 1)[1].split(
        "## Fundamental Analysis",
        1,
    )[0]
    fundamental_section = main_body.split("## Fundamental Analysis", 1)[1].split(
        "## Valuation / Risk-Reward",
        1,
    )[0]

    for item in claims:
        assert main_body.count(item.claim) == 1
    assert claims[2].claim in current_section
    assert claims[4].claim not in current_section
    assert claims[5].claim not in current_section
    assert claims[6].claim not in current_section
    assert claims[2].claim not in fundamental_section
    assert claims[3].claim in fundamental_section
    assert claims[4].claim in fundamental_section


def test_final_rating_acknowledges_negative_fcf_before_defending_hold():
    _, metrics, _, _, decision = _load_packet("SNOW")
    metrics.fundamentals.free_cash_flow_ttm = -210_000_000
    decision.signal_scores.fundamental_score = -1
    decision.signal_scores.fundamental_status = "measured"
    decision.signal_scores.technical_status = "partial"
    decision.signal_scores.valuation_status = "unbenchmarked"

    section = _final_rating_section(
        "TEST",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )

    assert "Negative FCF and the cautious measured fundamental signal" in section
    assert "Negative FCF is already fundamental downside evidence" in section
    assert "valuation is unbenchmarked" in section
    assert "raw technical observations include RSI" in section
    assert "Technical timing remains unavailable" in section
    assert "A raw multiple or an isolated price signal" not in section


def test_final_rating_preserves_measured_unbenchmarked_trailing_pe():
    _, metrics, _, _, decision = _load_packet("SNOW")
    metrics.valuation.ev_to_sales = None
    metrics.valuation.price_to_fcf = None
    metrics.valuation.trailing_pe = 7.68
    decision.signal_scores.valuation_status = "unbenchmarked"

    section = _final_rating_section(
        "TEST",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )

    assert "trailing P/E of 7.68x is an unbenchmarked observation" in section
    assert "No measured valuation multiple is available" not in section


def test_final_rating_balances_non_positive_equity_against_positive_fcf():
    _, metrics, _, _, decision = _load_packet("SNOW")
    metrics.fundamentals.equity = -7_674_300_000
    metrics.fundamentals.free_cash_flow_ttm = 3_642_100_000
    decision.signal_scores.fundamental_score = 0
    decision.signal_scores.fundamental_status = "measured"

    section = _final_rating_section(
        "TEST",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )

    assert "Non-positive book equity is a material balance-sheet constraint" in section
    assert "positive FCF does not remove that constraint" in section
    assert "positive FCF is measured counterevidence" in section
    assert "does not establish insolvency or business deterioration" in section
    assert "A raw multiple or an isolated price signal" not in section


def test_final_rating_keeps_bearish_technical_state_outside_company_rating():
    _, metrics, _, _, decision = _load_packet("SNOW")
    metrics.fundamentals.equity = 94_330_000_000
    metrics.fundamentals.free_cash_flow_ttm = 12_552_000_000
    decision.signal_scores.fundamental_score = 1
    decision.signal_scores.fundamental_status = "measured"
    decision.signal_scores.technical_score = -1
    decision.signal_scores.technical_status = "measured"
    decision.signal_scores.valuation_status = "unbenchmarked"
    metrics.technical.price_series_basis = "corporate_action_adjusted"

    section = _final_rating_section(
        "TEST",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )

    assert "not enough without calibrated valuation support" in section
    assert "Verified technical direction can affect timing confidence" in section
    assert "Positive FCF and the constructive fundamental signal" in section
    assert "fundamental, valuation or issuer-risk deterioration" in section
    assert "A raw multiple or an isolated price signal" not in section


def test_mixed_profit_declines_remain_visible_across_thesis_bear_and_rating():
    _, metrics, _, _, decision = _load_packet("SNOW")
    metrics.fundamentals.free_cash_flow_ttm = 3_031_000_000
    metrics.fundamentals.current_period_revenue_growth_yoy = 0.067
    metrics.fundamentals.current_period_operating_income_growth_yoy = -0.229
    metrics.fundamentals.current_period_net_income_growth_yoy = -0.246
    metrics.technical.close = 144.49
    metrics.technical.sma_50 = 132.61
    metrics.technical.sma_200 = 114.31
    decision.signal_scores.fundamental_score = 1
    decision.signal_scores.technical_score = 1
    decision.signal_scores.technical_status = "partial"
    decision.signal_scores.valuation_status = "unbenchmarked"

    thesis = _generic_investment_thesis(
        "TEST",
        "Hold",
        metrics,
        decision,
    )
    bear = _bear_case_claim_text("TEST", metrics, "USD")
    rating = _final_rating_section(
        "TEST",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )

    assert "mixed fundamental picture" in thesis
    assert "constructive fundamental signal" not in thesis
    assert "operating-income and net-income declines are current downside evidence" in bear
    assert "Positive FCF TTM of $3.03B" in bear
    assert "does not erase the profit weakness" in bear
    assert "Current-period operating-income and net-income declines" in rating
    assert "positive FCF is measured counterevidence" in rating
    assert "profit weakness to persist" in rating
    assert "A raw multiple or an isolated price signal" not in rating

    data, _, validation, ledger, _ = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
    )
    final_claim = next(
        claim
        for claim in claims
        if claim.claim_type == "rating" and claim.section == "Final Rating & Action Plan"
    )
    assert "measured fundamental picture is mixed" in final_claim.claim
    assert "operating-income and net-income declines" in final_claim.claim
    assert "fundamental signal is constructive" not in final_claim.claim
    assert "current_period_operating_income_growth_yoy" in final_claim.metric_refs
    assert "current_period_net_income_growth_yoy" in final_claim.metric_refs
    assert "is measured counterevidence" in rating
    research_report = compose_research_report(
        data,
        metrics,
        validation,
        decision,
        ledger,
        claims,
    )
    assert "Current-period operating-income and net-income declines" in research_report
    assert "positive FCF does not erase" in research_report
    assert "raw technical observations indicate" in research_report
    assert "excluded from rating and timing" in research_report
    assert "A raw multiple or an isolated price signal" not in research_report


def test_missing_fcf_keeps_profit_declines_visible_across_complete_report_logic():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    metrics.fundamentals.free_cash_flow_ttm = None
    metrics.fundamentals.current_period_revenue_growth_yoy = -0.007
    metrics.fundamentals.current_period_operating_income_growth_yoy = -0.122
    metrics.fundamentals.current_period_net_income_growth_yoy = -0.233
    metrics.technical.close = 46.81
    metrics.technical.sma_50 = 45.47
    metrics.technical.sma_200 = 44.62
    decision.signal_scores.fundamental_score = 0
    decision.signal_scores.technical_score = 1
    decision.signal_scores.technical_status = "partial"
    decision.signal_scores.valuation_status = "unbenchmarked"
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
    )
    financial_bull = next(
        claim
        for claim in claims
        if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
    )
    bear = next(claim for claim in claims if claim.section == "Bear Case")
    final_claim = next(
        claim
        for claim in claims
        if claim.section == "Final Rating & Action Plan" and claim.claim_type == "rating"
    )
    thesis = _generic_investment_thesis("TEST", "Hold", metrics, decision)
    rating = _final_rating_section(
        "TEST",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )
    research_report = compose_research_report(
        data,
        metrics,
        validation,
        decision,
        ledger,
        claims,
    )

    assert "unavailable FCF" in financial_bull.claim
    assert "free_cash_flow_ttm" not in financial_bull.metric_refs
    assert "operating-income and net-income declines" in bear.claim
    assert "FCF is unavailable" in bear.claim
    assert "Technical timing context is" in bear.claim
    assert "does not establish operating deterioration" in bear.claim
    assert "pressured but incomplete" in thesis
    assert "weaker current-period profit comparisons" in thesis
    assert "pressured but incomplete" in final_claim.claim
    assert "operating-income and net-income declines" in final_claim.claim
    assert "Current-period operating-income and net-income declines" in rating
    assert "FCF is unavailable" in rating
    assert "FCF of not available" not in rating
    assert "P/FCF of not available" not in rating
    assert "raw technical observations include RSI" in rating
    assert "Technical timing remains unavailable" in rating
    assert "A raw multiple or an isolated price signal" not in rating
    assert "Current-period operating-income and net-income declines" in research_report
    assert "FCF is unavailable" in research_report
    assert "raw technical observations indicate" in research_report
    assert "excluded from rating and timing" in research_report
    assert "A raw multiple or an isolated price signal" not in research_report


def test_missing_fcf_never_enters_bull_case_as_a_formatted_value():
    growth_scenarios = (
        (0.02, 0.08, 0.03),
        (0.02, 0.90, 0.85),
        (None, None, None),
    )

    for revenue_growth, operating_growth, net_growth in growth_scenarios:
        data, metrics, validation, ledger, decision = _load_packet("SNOW")
        metrics.fundamentals.free_cash_flow_ttm = None
        metrics.fundamentals.current_period_revenue_growth_yoy = revenue_growth
        metrics.fundamentals.current_period_operating_income_growth_yoy = operating_growth
        metrics.fundamentals.current_period_net_income_growth_yoy = net_growth
        _add_exact_metric_evidence(data, metrics, ledger)

        claims = generate_research_claims(
            data,
            metrics,
            ledger,
            decision,
            validation,
        )
        bull_claim = next(
            claim
            for claim in claims
            if claim.section == "Bull Case" and claim.claim_type == "financial_metric"
        )

        assert "not available in evidence set" not in bull_claim.claim
        assert "FCF" in bull_claim.claim
        assert "unavailable" in bull_claim.claim


def test_final_rating_does_not_promote_direction_from_unadjusted_price_basis():
    _, metrics, _, _, decision = _load_packet("SNOW")
    decision.signal_scores.technical_status = "partial"
    decision.signal_scores.technical_score = 1

    section = _final_rating_section(
        "SNOW",
        "Hold",
        metrics.fundamentals,
        metrics.valuation,
        metrics.technical,
        decision,
    )

    assert "raw technical observations include RSI" in section
    assert "direction and timing are not activated" in section
    assert "raw indicators remain provisional observations" in section
    assert "Technical timing remains unavailable" in section
    assert "neutral or incomplete" not in section
    assert (
        _constructive_cash_conversion_trigger(-11_625_000_000)
        == "Current-period KPIs improve while free-cash-flow conversion improves"
    )
    assert (
        _constructive_cash_conversion_trigger(11_625_000_000)
        == "Current-period KPIs improve while free-cash-flow conversion holds"
    )
    assert (
        _clean_text("Manual review remains appropriate.") == "Further review remains appropriate."
    )


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
    claim = next(item for item in claims if "arithmetic comparison" in item.claim)

    assert claim.metric_values == {
        "shareholder_distributions_ttm": 90.0,
        "shareholder_distributions_minus_fcf_ttm": 10.0,
    }
    assert "does not identify a funding source" in claim.claim
    assert (
        "shareholder distributions exceed FCF; the signed "
        "distributions-minus-FCF comparison is $10.00"
    ) in claim.claim
    assert "The excess does not by itself prove" in claim.counterargument

    metrics.fundamentals.shareholder_distributions_minus_fcf_ttm = -10.0
    difference_evidence = next(
        item
        for item in ledger.evidence_items
        if "shareholder_distributions_minus_fcf_ttm" in item.supports_metrics
    )
    difference_evidence.value = -10.0
    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    claim = next(item for item in claims if "arithmetic comparison" in item.claim)

    assert (
        "FCF exceeds shareholder distributions; the signed "
        "distributions-minus-FCF comparison is -$10.00"
    ) in claim.claim
    assert "$-10.00" not in claim.claim
    assert "This period surplus does not prove" in claim.counterargument
    audit = audit_markdown_report(
        claim.claim,
        metrics,
        decision_packet=decision,
        ticker=data.ticker,
    )
    assert not audit.has_issue("NUMERIC_MISMATCH")


def test_generic_report_surfaces_use_the_packet_currency_instead_of_dollars():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    data.ticker = "GENERIC"
    data.price_basis.currency = "HUF"
    metrics.fundamentals.revenue_growth_yoy = None
    metrics.fundamentals.sbc_to_revenue = None
    metrics.fundamentals.net_cash = -4_610_000_000
    metrics.fundamentals.total_debt = 13_460_000_000
    decision.signal_scores.valuation_status = "unbenchmarked"
    decision.signal_scores.valuation_score = 0
    _add_exact_metric_evidence(data, metrics, ledger)

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
        manual_review_reasons=["EARNINGS_DATE_UNAVAILABLE"],
        review_issue_details=[{
            "code": "EARNINGS_DATE_UNAVAILABLE",
            "message": "Next earnings date is unavailable; no event-risk claim is made.",
        }],
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
    balance_sheet_claim = next(claim for claim in claims if "balance-sheet position" in claim.claim)
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
    assert "raw moving-average observations" in catalyst_text
    assert "not validated support, resistance, risk or trigger levels" in catalyst_text
    assert "$" not in research_report
    assert "## Data Limits & Review Status" in internal_report
    assert "`EARNINGS_DATE_UNAVAILABLE`" in internal_report
    assert "Next earnings date is unavailable" in internal_report
    assert internal_report.index("## Data Limits & Review Status") < internal_report.index("## Evidence Appendix")
    assert "$" not in internal_report
    assert "4.34B HUF" in research_report
    assert "4.34B HUF" in internal_report
    assert "| Close | 141.71 HUF |" in research_report
    assert "| FCF TTM | 1,120,000,000 HUF |" in research_report
    assert "unbenchmarked observations" in research_report
    assert "unbenchmarked observations" in internal_report
    assert "no direction or numeric timing level is activated" in research_report
    assert (
        "technical timing remains unavailable until the price-series basis is confirmed"
        in research_report.lower()
    )
    assert (
        "reassess timing separately when the technical trend changes" not in research_report.lower()
    )
    directional_valuation_language = (
        "valuation constraint",
        "valuation and timing constraints",
        "argue against chasing",
        "better entry point",
        "position discipline",
        "valuation expands further",
    )
    assert not any(
        phrase in f"{research_report}\n{internal_report}".lower()
        for phrase in directional_valuation_language
    )
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
        phrase in claim.claim.lower() for claim in claims for phrase in unsupported_language
    )
    quality_metrics = claim_quality_metrics(claims)
    assert quality_metrics["generic_claim_count"] == 0
    assert quality_metrics["risk_specific_claim_count"] == 0
    assert "missing_risk_analysis" in claim_coverage_gaps(quality_metrics)
    rating_claim = next(claim for claim in claims if claim.section == "Final Rating & Action Plan")
    assert rating_claim.metric_refs == [
        "close",
        "revenue_ttm",
        "free_cash_flow_ttm",
        "ev_to_sales",
        "sma_50",
        "sma_200",
        "rsi_14",
        "price_to_fcf",
    ]
    assert "revenue TTM of 4.34B HUF" in rating_claim.claim
    assert "FCF TTM of 1.12B HUF" in rating_claim.claim
    assert "Valuation multiples are unbenchmarked" in rating_claim.claim
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


def test_named_ticker_uses_generic_authority_report_without_legacy_copy():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    data.ticker = "CRM"
    data.company_name = "Salesforce, Inc."
    metrics.ticker = "CRM"
    ledger.ticker = "CRM"
    decision.ticker = "CRM"
    metrics.fundamentals.revenue_ttm = 12_345_678_901
    metrics.fundamentals.free_cash_flow_ttm = 2_345_678_901
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
    )
    report = compose_internal_best_report(
        data,
        metrics,
        decision,
        ledger,
        claims,
        status="manual_review",
        publishable=False,
    )

    assert report.startswith("# CRM Research Report")
    assert "## Final Rating & Review Conditions" in report
    assert "$12.35B" in report
    assert "$2.35B" in report
    assert "FY2026 revenue of $41.5B" not in report
    assert "Move toward Accumulate" not in report
    assert "before adding aggressively" not in report
    assert "appropriately sized exposure" not in report


def test_content_generator_does_not_render_missing_values_as_claims():
    data, metrics, validation, ledger, decision = _load_packet("CRWD")
    _add_exact_metric_evidence(data, metrics, ledger)

    claims = generate_research_claims(data, metrics, ledger, decision, validation)

    assert claims
    assert claim_quality_metrics(claims)["company_specific_claim_count"] == 0
    assert all("not available in evidence set" not in claim.claim for claim in claims)
    assert not any("revenue TTM of" in claim.claim for claim in claims)


def test_material_company_events_create_real_context_not_generic_finance_padding():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    data.news_coverage.material_events = [
        MaterialNewsEvent(
            date="2026-05-01",
            headline="Company explains operating model",
            event_type="business_context",
            source_id="SNOW_IR_CONTEXT",
            source_type="company_ir",
            summary="The company describes a consumption-based platform model.",
        ),
        MaterialNewsEvent(
            date="2026-05-02",
            headline="Company announces platform strategy",
            event_type="strategy",
            source_id="SNOW_IR_STRATEGY",
            source_type="company_ir",
            summary="The company announced a strategy focused on platform adoption.",
        ),
    ]
    ledger.evidence_items.extend(
        [
            EvidenceItem(
                evidence_id="SNOW_CONTEXT_EVENT",
                ticker="SNOW",
                claim_type="news",
                source_id="SNOW_IR_CONTEXT",
                source_type="company_ir",
                authority_rank=1,
                statement="The company describes a consumption-based platform model.",
                date="2026-05-01",
                supports_claims=["material_news_coverage"],
                confidence="high",
            ),
            EvidenceItem(
                evidence_id="SNOW_STRATEGY_EVENT",
                ticker="SNOW",
                claim_type="news",
                source_id="SNOW_IR_STRATEGY",
                source_type="company_ir",
                authority_rank=1,
                statement="The company announced a strategy focused on platform adoption.",
                date="2026-05-02",
                supports_claims=["material_news_coverage"],
                confidence="high",
            ),
        ]
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    context = next(claim for claim in claims if claim.source_ids == ["SNOW_IR_CONTEXT"])
    strategy = next(claim for claim in claims if claim.source_ids == ["SNOW_IR_STRATEGY"])

    assert context.section == "Business & Segment Context"
    assert context.claim.startswith("Issuer-filed business context:")
    assert strategy.section == "Catalysts & Triggers"
    assert "execution and financial contribution remain unproven" in strategy.counterargument
    assert claim_quality_metrics(claims)["company_specific_claim_count"] >= 2


def test_current_filing_legal_event_is_rendered_as_specific_risk():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    statement = (
        "On April 26, 2026, the environmental authority issued an administrative "
        "cleanup order; the issuer's appeal remains pending."
    )
    data.news_coverage.material_events = [
        MaterialNewsEvent(
            date="2026-07-29",
            headline="Current filing contains a legal or contingency disclosure",
            event_type="filing_legal_contingencies",
            source_id="SNOW_SEC_CURRENT_LEGAL",
            source_type="sec_filing",
            summary=statement,
        )
    ]
    ledger.evidence_items.append(
        EvidenceItem(
            evidence_id="SNOW_CURRENT_LEGAL_EVENT",
            ticker="SNOW",
            claim_type="news",
            source_id="SNOW_SEC_CURRENT_LEGAL",
            source_type="sec_filing",
            authority_rank=1,
            statement=statement,
            date="2026-07-29",
            supports_claims=["material_news_coverage"],
            confidence="high",
        )
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    risk = next(claim for claim in claims if claim.source_ids == ["SNOW_SEC_CURRENT_LEGAL"])

    assert risk.section == "Key Risks"
    assert risk.claim_type == "risk"
    assert risk.claim.startswith("Current issuer-filed risk context:")


def test_issuer_operating_spread_keeps_segments_and_regions_taxonomically_distinct():
    canonical = CanonicalFinancials(
        ticker="ROK",
        as_of_date="2026-08-04",
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="percent",
                period="FY2026_Q3",
                fiscal_year=2026,
                fiscal_period="Q3",
                period_bucket="quarterly",
                end_date="2026-06-30",
                basis="company_defined",
                statement_type="income_statement",
                source_ids=["ROK_SEC_RESULTS"],
                evidence_ids=[f"ROK_{metric_name.upper()}"],
                confidence="high",
            )
            for metric_name, value in (
                ("segment_organic_sales_growth_latin_america", -0.03),
                ("segment_organic_sales_growth_software_control", 0.18),
            )
        ],
    )

    specs = _issuer_operating_result_specs("ROK", canonical, "USD")
    spread = next(spec for spec in specs if len(spec["metrics"]) == 2)

    assert "across reported segments and regions" in spread["text"]
    assert "division-level" not in spread["text"]
    assert "without treating unlike reporting dimensions as one taxonomy" in spread["implication"]


def test_issuer_results_claim_counts_reported_growth_and_adjusted_eps_as_current_context():
    canonical = CanonicalFinancials(
        ticker="PFE",
        as_of_date="2026-08-04",
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD_per_share" if "eps" in metric_name else "percent",
                period="FY2026_Q2",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="quarterly",
                end_date="2026-06-28",
                basis="non_gaap" if "eps" in metric_name else "company_defined",
                statement_type="income_statement",
                source_ids=["PFE_SEC_RESULTS"],
                evidence_ids=[f"PFE_{metric_name.upper()}"],
                confidence="high",
            )
            for metric_name, value in (
                ("reported_revenue_growth", 0.03),
                ("adjusted_eps_diluted", 0.77),
                ("adjusted_eps_growth_yoy", 0.0),
            )
        ],
    )

    spec = next(
        item
        for item in _issuer_operating_result_specs("PFE", canonical, "USD")
        if "reported-revenue growth" in item["text"]
    )
    claim = ResearchClaim(
        agent="deterministic",
        claim=spec["text"],
        claim_text=spec["text"],
        claim_type="financial_metric",
        section=spec["section"],
        evidence_metrics=spec["metrics"],
        metric_refs=spec["metrics"],
        metric_values={metric.metric_name: metric.value for metric in canonical.metrics},
        evidence_ids=["PFE_RESULTS"],
        source_ids=["PFE_SEC_RESULTS"],
        confidence="high",
    )

    assert "3.0%" in spec["text"]
    assert "$0.77" in spec["text"]
    assert "approximately flat" in spec["text"]
    assert claim_quality_metrics([claim])["current_period_kpi_metric_count"] == 3


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
                ("gross_profit", 9_790_000_000),
                ("net_income", 2_680_000_000),
            )
        ],
    )
    _add_exact_metric_evidence(data, metrics, ledger)
    for metric in canonical.metrics:
        ledger.evidence_items.append(
            EvidenceItem(
                evidence_id=metric.evidence_ids[0],
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id=metric.source_ids[0],
                source_type="company_ir",
                authority_rank=1,
                statement=f"{metric.metric_name} exact current-period evidence.",
                value=metric.value,
                unit=metric.unit,
                period=metric.period,
                date=metric.end_date,
                supports_metrics=[metric.metric_name],
                confidence="high",
            )
        )

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    current = next(claim for claim in claims if "latest reported period" in claim.claim)

    assert " HUF" in current.claim
    assert "without a matching prior-year quarter" in current.claim
    assert current.metric_refs == [
        "revenue",
        "gross_profit",
        "net_income",
    ]


def test_q1_cashflow_claim_uses_current_quarter_as_year_to_date():
    def cashflow_metric(
        metric_name,
        value,
        *,
        period,
        fiscal_period,
        period_bucket,
        start_date,
        end_date,
    ):
        return CanonicalMetric(
            metric_name=metric_name,
            value=value,
            unit="USD",
            period=period,
            fiscal_year=2026,
            fiscal_period=fiscal_period,
            period_bucket=period_bucket,
            start_date=start_date,
            end_date=end_date,
            basis="gaap",
            statement_type="cash_flow",
            source_ids=[f"SEC_{period}"],
            confidence="high",
        )

    canonical = CanonicalFinancials(
        ticker="GENERIC",
        as_of_date="2026-08-03",
        metrics=[
            cashflow_metric(
                "operating_cash_flow",
                1_800_000_000,
                period="Q3_FY2025_ytd",
                fiscal_period="Q3",
                period_bucket="ytd",
                start_date="2025-01-01",
                end_date="2025-09-30",
            ),
            cashflow_metric(
                "capex",
                741_000_000,
                period="Q3_FY2025_ytd",
                fiscal_period="Q3",
                period_bucket="ytd",
                start_date="2025-01-01",
                end_date="2025-09-30",
            ),
            cashflow_metric(
                "operating_cash_flow",
                745_000_000,
                period="CY2026Q1",
                fiscal_period="Q1",
                period_bucket="quarterly",
                start_date="2026-01-01",
                end_date="2026-03-31",
            ),
            cashflow_metric(
                "capex",
                424_000_000,
                period="CY2026Q1",
                fiscal_period="Q1",
                period_bucket="quarterly",
                start_date="2026-01-01",
                end_date="2026-03-31",
            ),
        ],
    )

    spec = next(
        item
        for item in _issuer_operating_result_specs("GENERIC", canonical, "USD")
        if "operating cash flow" in item["text"]
    )

    assert "$745.0" in spec["text"]
    assert "$424.0" in spec["text"]
    assert "$1.80B" not in spec["text"]


def test_generic_current_period_claim_uses_evidenced_yoy_comparison():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    data.ticker = "GENERIC"
    data.price_basis.currency = "USD"
    current_values = {
        "revenue": 110.0,
        "operating_income": 24.0,
        "gross_profit": 60.0,
        "net_income": 15.0,
    }
    growth_values = {
        "current_period_revenue_growth_yoy": 0.10,
        "current_period_operating_income_growth_yoy": 0.20,
        "current_period_net_income_growth_yoy": 0.25,
    }
    for metric_name, value in growth_values.items():
        setattr(metrics.fundamentals, metric_name, value)
    canonical = CanonicalFinancials(
        ticker="GENERIC",
        as_of_date=data.as_of_date,
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="Q3_FY2026_ytd",
                fiscal_year=2026,
                fiscal_period="Q3",
                period_bucket="ytd",
                start_date="2025-09-01",
                end_date="2026-05-10",
                duration_days=251,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_Q3_2026"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 330.0),
                ("operating_income", 72.0),
                ("net_income", 45.0),
            )
        ]
        + [
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="CY2026Q1",
                fiscal_year=2026,
                fiscal_period="Q3",
                period_bucket="quarterly",
                start_date="2026-02-16",
                end_date="2026-05-10",
                duration_days=83,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_Q1_2026"],
                confidence="high",
            )
            for metric_name, value in current_values.items()
        ],
    )
    _add_exact_metric_evidence(data, metrics, ledger)
    for metric in canonical.metrics:
        ledger.evidence_items.append(
            EvidenceItem(
                evidence_id=(
                    f"GENERIC_{metric.metric_name.upper()}_{metric.period_bucket.upper()}"
                ),
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="GENERIC_SEC_Q1_2026",
                source_type="sec_filing",
                authority_rank=1,
                statement=f"Exact evidence for {metric.metric_name}.",
                value=metric.value,
                normalized_value=metric.value,
                raw_value=metric.value,
                unit="USD",
                period=metric.period,
                date=metric.end_date,
                duration_days=metric.duration_days,
                supports_metrics=[metric.metric_name],
                confidence="high",
            )
        )
    for metric_name, value in growth_values.items():
        ledger.evidence_items.append(
            EvidenceItem(
                evidence_id=f"GENERIC_{metric_name.upper()}",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="GENERIC_DETERMINISTIC_CALCULATIONS",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=f"Exact evidence for {metric_name}.",
                value=value,
                normalized_value=value,
                unit="percent",
                period="CY2025Q1..CY2026Q1",
                date="2026-05-10",
                supports_metrics=[metric_name],
                formula_id="matching_quarter_yoy_growth",
                formula_operands={"current": 1.0, "prior": 1.0},
                confidence="high",
            )
        )

    claims = generate_research_claims(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )
    current = next(claim for claim in claims if "latest reported period" in claim.claim)

    assert "latest reported period FY2026_Q3" in current.claim
    assert "latest reported period CY2026Q1" not in current.claim
    assert "revenue increased by 10.0%" in current.claim
    assert "operating income increased by 20.0%" in current.claim
    assert "net income increased by 25.0%" in current.claim
    assert set(growth_values) <= set(current.metric_refs)
    assert current.metric_values["revenue"] == 110.0
    assert current.metric_values["operating_income"] == 24.0
    assert current.metric_values["net_income"] == 15.0
    assert "GENERIC_REVENUE_QUARTERLY" in current.evidence_ids
    assert "GENERIC_REVENUE_YTD" not in current.evidence_ids


def test_missing_ticker_specific_metrics_fall_back_to_latest_fiscal_year():
    _, metrics, _, _, _ = _load_packet("SNOW")
    metrics.fundamentals.current_period_revenue_growth_yoy = 0.18
    metrics.fundamentals.current_period_operating_income_growth_yoy = 0.21
    metrics.fundamentals.current_period_net_income_growth_yoy = 0.31
    canonical = CanonicalFinancials(
        ticker="MSFT",
        as_of_date="2026-07-31",
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="FY2026",
                fiscal_year=2026,
                fiscal_period="FY",
                period_bucket="annual",
                start_date="2025-07-01",
                end_date="2026-06-30",
                duration_days=364,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["GENERIC_SEC_FY2026"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 331_839.0),
                ("operating_income", 155_237.0),
                ("net_income", 133_749.0),
            )
        ],
    )

    specs = _current_period_claim_specs(
        "MSFT",
        metrics,
        canonical,
        currency="USD",
    )
    current = next(spec for spec in specs if "latest reported period" in spec["text"])

    assert "FY2026" in current["text"]
    assert "matching prior-year fiscal year" in current["text"]
    assert current["comparison_period"] == "fiscal_year"
    assert current["metrics"] == [
        "revenue",
        "operating_income",
        "net_income",
        "current_period_revenue_growth_yoy",
        "current_period_operating_income_growth_yoy",
        "current_period_net_income_growth_yoy",
    ]


def test_netflix_uses_generic_current_quarter_when_legacy_aliases_are_absent():
    _, metrics, _, _, _ = _load_packet("SNOW")
    metrics.fundamentals.current_period_revenue_growth_yoy = 0.13
    metrics.fundamentals.current_period_operating_income_growth_yoy = 0.11
    metrics.fundamentals.current_period_net_income_growth_yoy = 0.09
    canonical = CanonicalFinancials(
        ticker="NFLX",
        as_of_date="2026-07-31",
        metrics=[
            CanonicalMetric(
                metric_name=metric_name,
                value=value,
                unit="USD",
                period="Q2_FY2026_quarterly",
                fiscal_year=2026,
                fiscal_period="Q2",
                period_bucket="quarterly",
                start_date="2026-04-01",
                end_date="2026-06-30",
                duration_days=90,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["NFLX_SEC_Q2_2026"],
                confidence="high",
            )
            for metric_name, value in (
                ("revenue", 11_533_000_000),
                ("operating_income", 3_682_000_000),
                ("net_income", 3_125_000_000),
            )
        ],
    )

    current = next(
        spec
        for spec in _current_period_claim_specs("NFLX", metrics, canonical)
        if "latest reported period" in spec["text"]
    )

    assert "FY2026_Q2" in current["text"]
    assert current["metrics"] == [
        "revenue",
        "operating_income",
        "net_income",
        "current_period_revenue_growth_yoy",
        "current_period_operating_income_growth_yoy",
        "current_period_net_income_growth_yoy",
    ]


def test_annual_claim_matches_same_dates_across_sec_period_labels():
    _, metrics, _, _, _ = _load_packet("SNOW")
    metrics.fundamentals.current_period_revenue_growth_yoy = 0.002
    metrics.fundamentals.current_period_operating_income_growth_yoy = None
    metrics.fundamentals.current_period_net_income_growth_yoy = -0.034
    common = {
        "unit": "USD",
        "fiscal_year": 2026,
        "fiscal_period": "FY",
        "period_bucket": "annual",
        "start_date": "2025-06-01",
        "end_date": "2026-05-31",
        "duration_days": 364,
        "basis": "gaap",
        "statement_type": "income_statement",
        "source_ids": ["GENERIC_SEC_FY2026"],
        "confidence": "high",
    }
    canonical = CanonicalFinancials(
        ticker="GENERIC",
        as_of_date="2026-07-31",
        metrics=[
            CanonicalMetric(
                metric_name="revenue",
                value=46_398.0,
                period="CY2025",
                **common,
            ),
            CanonicalMetric(
                metric_name="gross_profit",
                value=19_911.0,
                period="CY2025",
                **common,
            ),
            CanonicalMetric(
                metric_name="net_income",
                value=3_108.0,
                period="FY2026",
                **common,
            ),
        ],
    )

    current = next(
        spec
        for spec in _current_period_claim_specs(
            "GENERIC",
            metrics,
            canonical,
            currency="USD",
        )
        if "latest reported period" in spec["text"]
    )

    assert "FY2026" in current["text"]
    assert "matching prior-year fiscal year" in current["text"]
    assert "revenue increased by 0.2%" in current["text"]
    assert "net income declined by 3.4%" in current["text"]
    assert "prior-year quarter" not in current["text"]
    assert current["metrics"] == [
        "revenue",
        "gross_profit",
        "net_income",
        "current_period_revenue_growth_yoy",
        "current_period_net_income_growth_yoy",
    ]


def test_guidance_claim_prioritizes_comparable_sales_adjusted_margin_and_eps():
    _, metrics, _, _, _ = _load_packet("SNOW")
    definitions = {
        "revenue": (92_000_000_000.0, 94_000_000_000.0, "USD", "company_defined"),
        "comparable_sales_growth": (0.0, 0.02, "percent", "company_defined"),
        "operating_margin": (0.112, 0.114, "percent", "gaap"),
        "adjusted_operating_margin": (0.116, 0.118, "percent", "non_gaap"),
        "eps_diluted": (11.75, 12.25, "USD_per_share", "gaap"),
        "adjusted_eps": (12.25, 12.75, "USD_per_share", "non_gaap"),
    }
    canonical_metrics = []
    for base, (low, high, unit, basis) in definitions.items():
        for bound, value in (("low", low), ("high", high)):
            canonical_metrics.append(
                CanonicalMetric(
                    metric_name=f"guidance_{base}_{bound}",
                    value=value,
                    unit=unit,
                    period="FY2026",
                    fiscal_year=2026,
                    fiscal_period="FY",
                    period_bucket="guidance",
                    end_date="2026-05-20",
                    basis=basis,
                    statement_type="guidance",
                    source_ids=["GENERIC_SEC_RESULTS"],
                    confidence="high",
                )
            )
    canonical = CanonicalFinancials(
        ticker="GENERIC",
        as_of_date="2026-08-03",
        metrics=canonical_metrics,
    )

    guidance = next(
        spec
        for spec in _current_period_claim_specs(
            "GENERIC",
            metrics,
            canonical,
            currency="USD",
        )
        if spec["kind"] == "guidance"
    )

    assert "sales of $92.00B to $94.00B" in guidance["text"]
    assert "comparable-sales growth of 0.0% to 2.0%" in guidance["text"]
    assert "adjusted operating margin of 11.6% to 11.8%" in guidance["text"]
    assert "adjusted EPS of $12.25 to $12.75" in guidance["text"]
    assert "$11.75" not in guidance["text"]
    assert guidance["metrics"] == [
        "guidance_revenue_low",
        "guidance_revenue_high",
        "guidance_comparable_sales_growth_low",
        "guidance_comparable_sales_growth_high",
        "guidance_adjusted_operating_margin_low",
        "guidance_adjusted_operating_margin_high",
        "guidance_adjusted_eps_low",
        "guidance_adjusted_eps_high",
    ]


def test_direct_annual_claim_prefers_canonical_sec_fact_over_equal_ttm_formula():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    data.ticker = "DIRECT"
    annual = CanonicalMetric(
        metric_name="revenue",
        value=331_839.0,
        unit="USD",
        period="FY2026",
        fiscal_year=2026,
        fiscal_period="FY",
        period_bucket="annual",
        start_date="2025-07-01",
        end_date="2026-06-30",
        duration_days=364,
        basis="gaap",
        statement_type="income_statement",
        source_ids=["SEC_DIRECT_FY2026"],
        evidence_ids=["DIRECT_SEC_REVENUE_FY2026"],
        confidence="high",
    )
    canonical = CanonicalFinancials(
        ticker="DIRECT",
        as_of_date="2026-07-31",
        metrics=[annual],
    )
    ledger.evidence_items = [
        EvidenceItem(
            evidence_id="DIRECT_SEC_REVENUE_FY2026",
            ticker="DIRECT",
            claim_type="financial_metric",
            source_id="SEC_DIRECT_FY2026",
            source_type="sec_filing",
            authority_rank=1,
            statement="Fiscal 2026 revenue.",
            raw_value=annual.value,
            normalized_value=annual.value,
            value=annual.value,
            unit="USD",
            period="FY2026",
            date="2026-06-30",
            duration_days=364,
            supports_metrics=["revenue"],
            confidence="high",
        ),
        EvidenceItem(
            evidence_id="DIRECT_DETERMINISTIC_REVENUE_TTM",
            ticker="DIRECT",
            claim_type="financial_metric",
            source_id="DIRECT_DETERMINISTIC_CALCULATIONS",
            source_type="deterministic_calculation",
            authority_rank=1,
            statement="TTM revenue equals fiscal-year revenue.",
            normalized_value=annual.value,
            value=annual.value,
            unit="USD",
            period="TTM through FY2026",
            date="2026-07-31",
            supports_metrics=["revenue"],
            formula_id="annual_fallback",
            formula_operands={"annual": annual.value},
            confidence="high",
        ),
    ]
    builder = _ClaimBuilder(
        data,
        metrics,
        ledger,
        decision,
        validation,
        canonical,
    )

    selected = builder._compatible_evidence_for_metric("revenue")

    assert [item.evidence_id for item in selected] == ["DIRECT_SEC_REVENUE_FY2026"]


def test_claim_evidence_selection_excludes_conflicting_units_and_values():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    fcf_value = metrics.fundamentals.free_cash_flow_ttm
    ledger.evidence_items.extend(
        [
            EvidenceItem(
                evidence_id="CONFLICTING_FCF_UNIT",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="CONFLICTING_SOURCE",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement="Same number in the wrong currency.",
                value=fcf_value,
                unit="EUR",
                period=metrics.fundamentals.fiscal_period,
                date=data.as_of_date,
                supports_metrics=["free_cash_flow_ttm"],
            ),
            EvidenceItem(
                evidence_id="CONFLICTING_FCF_VALUE",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="CONFLICTING_SOURCE",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement="Wrong value in the right currency.",
                value=fcf_value + 1,
                unit=data.price_basis.currency,
                period=metrics.fundamentals.fiscal_period,
                date=data.as_of_date,
                supports_metrics=["free_cash_flow_ttm"],
            ),
        ]
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    fcf_claim = next(claim for claim in claims if claim.claim.startswith("FCF TTM is"))

    assert "CONFLICTING_FCF_UNIT" not in fcf_claim.evidence_ids
    assert "CONFLICTING_FCF_VALUE" not in fcf_claim.evidence_ids


def test_claim_prefers_formula_lineage_over_equal_stale_raw_evidence():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    expected_fcf = metrics.fundamentals.free_cash_flow_ttm
    ledger.evidence_items.extend(
        [
            EvidenceItem(
                evidence_id="STALE_EQUAL_FCF",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="OLD_SEC_FILING",
                source_type="sec_filing",
                authority_rank=1,
                statement="An older filing reported the same FCF value.",
                raw_value=expected_fcf,
                value=expected_fcf,
                unit="USD",
                period="FY2022",
                date="2022-12-31",
                supports_metrics=["free_cash_flow_ttm"],
                confidence="high",
            ),
            EvidenceItem(
                evidence_id="CURRENT_DERIVED_FCF",
                ticker=data.ticker,
                claim_type="financial_metric",
                source_id="CURRENT_DETERMINISTIC_CALCULATIONS",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement="Current FCF was derived from current SEC operands.",
                normalized_value=expected_fcf,
                value=expected_fcf,
                unit="USD",
                period=metrics.fundamentals.fiscal_period,
                date=data.as_of_date,
                supports_metrics=["free_cash_flow_ttm"],
                formula_id="operating_cash_flow_minus_capex",
                formula_operands={"operating_cash_flow": 2.0, "capex": 1.0},
                confidence="high",
            ),
        ]
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    fcf_claim = next(claim for claim in claims if claim.claim.startswith("FCF TTM is"))

    assert fcf_claim.evidence_ids == [
        "CURRENT_DERIVED_FCF",
        "TEST_EXACT_SBC_TO_FCF",
    ]


def test_claim_is_dropped_when_only_conflicting_metric_evidence_remains():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    conflicting_ids = {item.evidence_id for item in ledger.find_by_metric("free_cash_flow_ttm")}
    ledger.evidence_items = [
        item for item in ledger.evidence_items if item.evidence_id not in conflicting_ids
    ]
    ledger.evidence_items.append(
        EvidenceItem(
            evidence_id="ONLY_WRONG_FCF_CURRENCY",
            ticker=data.ticker,
            claim_type="financial_metric",
            source_id="CONFLICTING_SOURCE",
            source_type="deterministic_calculation",
            authority_rank=1,
            statement="Only wrong-currency FCF evidence remains.",
            value=metrics.fundamentals.free_cash_flow_ttm,
            unit="EUR",
            period=metrics.fundamentals.fiscal_period,
            date=data.as_of_date,
            supports_metrics=["free_cash_flow_ttm"],
        )
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)

    assert not any("free_cash_flow_ttm" in claim.metric_refs for claim in claims)


def test_claim_is_dropped_when_its_only_evidence_id_is_ambiguous():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    existing_ids = {item.evidence_id for item in ledger.find_by_metric("free_cash_flow_ttm")}
    ledger.evidence_items = [
        item for item in ledger.evidence_items if item.evidence_id not in existing_ids
    ]
    common = {
        "evidence_id": "AMBIGUOUS_FCF_ID",
        "ticker": data.ticker,
        "claim_type": "financial_metric",
        "source_id": "DUPLICATE_SOURCE",
        "source_type": "sec_filing",
        "authority_rank": 1,
        "unit": data.price_basis.currency,
        "period": metrics.fundamentals.fiscal_period,
        "date": data.as_of_date,
        "supports_metrics": ["free_cash_flow_ttm"],
    }
    ledger.evidence_items.extend(
        [
            EvidenceItem(
                **common,
                statement="Correct value under an ambiguous identifier.",
                value=metrics.fundamentals.free_cash_flow_ttm,
            ),
            EvidenceItem(
                **common,
                statement="Different value under the same identifier.",
                value=metrics.fundamentals.free_cash_flow_ttm + 1,
            ),
        ]
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)

    assert not any("free_cash_flow_ttm" in claim.metric_refs for claim in claims)


def test_claim_evidence_excludes_value_injected_source_placeholders():
    data, metrics, validation, ledger, decision = _load_packet("SNOW")
    _add_exact_metric_evidence(data, metrics, ledger)
    ledger.evidence_items.append(
        EvidenceItem(
            evidence_id="VALUE_INJECTED_FCF_PLACEHOLDER",
            ticker=data.ticker,
            claim_type="financial_metric",
            source_id="REGISTERED_SOURCE_WITHOUT_PROVENANCE",
            source_type="sec_filing",
            authority_rank=1,
            statement="Registered source placeholder with a copied metric value.",
            value=metrics.fundamentals.free_cash_flow_ttm,
            unit=data.price_basis.currency,
            supports_metrics=["free_cash_flow_ttm"],
        )
    )

    claims = generate_research_claims(data, metrics, ledger, decision, validation)
    fcf_claim = next(claim for claim in claims if claim.claim.startswith("FCF TTM is"))

    assert "VALUE_INJECTED_FCF_PLACEHOLDER" not in fcf_claim.evidence_ids


def test_claimless_report_stays_rejected_when_evidence_gate_fails():
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
    assert quality.content_score == 40
    assert "No LLM claims attached" not in report
    assert "## Evidence Appendix" in report
    assert claim_quality["analyst_claim_count"] == 0
    assert claim_quality["substantive_analyst_claim_count"] == 0
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
