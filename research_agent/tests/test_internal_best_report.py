from research_agent.content.publish_composer import (
    compose_early_commercial_manual_review_publish_stub,
    compose_internal_best_report,
    publish_report_quality,
)
from research_agent.decision.decision_packet import DecisionPacket, RatingPermission, SignalScores
from research_agent.decision.rating_taxonomy import Rating
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket, PriceBasis
from research_agent.research_core.models.metrics_packet import FundamentalMetrics, MetricsPacket, TechnicalMetrics, ValuationMetrics


def test_early_commercial_internal_best_report_is_readable_without_claim_ids_in_main_body():
    report = compose_internal_best_report(
        data_packet=DataPacket(
            ticker="RKLB",
            company_name="Rocket Lab Corporation",
            as_of_date="2026-05-15",
            price_basis=PriceBasis(close=124.77, date="2026-05-15", source="csv"),
            source_registry_id="RKLB_sources",
        ),
        metrics_packet=MetricsPacket(
            ticker="RKLB",
            as_of_date="2026-05-15",
            technical=TechnicalMetrics(indicator_date="2026-05-15", close=124.77, rsi_14=70.82),
            fundamentals=FundamentalMetrics(
                fiscal_period="TTM",
                revenue_ttm=622_495_000,
                operating_income_ttm=-250_000_000,
                free_cash_flow_ttm=-220_123_000,
                cash_and_equivalents=308_251_000,
                marketable_securities=1_168_594_000,
            ),
            valuation=ValuationMetrics(ev_to_sales=118.77771588516552),
        ),
        decision_packet=DecisionPacket(
            ticker="RKLB",
            as_of_date="2026-05-15",
            signal_scores=SignalScores(
                fundamental_score=1,
                technical_score=1,
                valuation_score=-2,
                risk_score=-2,
                composite_score=0,
            ),
            rating_permission=RatingPermission(
                allowed_ratings=[Rating.HOLD, Rating.TACTICAL_TRIM],
                blocked_ratings=[Rating.BUY, Rating.ACCUMULATE],
                preferred_rating=Rating.HOLD,
                reason="Manual review.",
            ),
        ),
        evidence_ledger=EvidenceLedger(ticker="RKLB", as_of_date="2026-05-15", evidence_items=[]),
        claims=_rklb_early_commercial_claims(),
        status="manual_review",
        publishable=False,
        external_display_rating="Manual Review / Hold Pending FCF and Execution Evidence",
        company_archetype="EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH",
        quality_score=65,
    )

    assert report.startswith("# Rocket Lab (RKLB) — Interne Research-Lesefassung")
    required_sections = [
        "## Statusbox",
        "## Executive Summary",
        "## Business Model Reality",
        "## Revenue Scale and Backlog",
        "## Contract / Backlog Materiality",
        "## Segment Mix",
        "## Execution Milestones",
        "## FCF Path",
        "## Capital Intensity",
        "## Valuation vs Revenue/Backlog",
        "## Valuation / Sensitivity",
        "## Technical Setup as Timing Only",
        "## Final Internal View",
        "## Follow-up Checklist",
    ]
    for section in required_sections:
        assert section in report

    main_body = report.split("## Evidence Appendix", 1)[0]
    # Stable lineage remains machine-readable without leaking implementation
    # identifiers into the reader-facing prose.
    assert "room16-lineage claim=RKLB_CLAIM_" in main_body
    assert "Claim `RKLB_CLAIM_" not in main_body
    assert "Manual Review / Hold Pending FCF and Execution Evidence" in main_body
    assert "Buy" in main_body and "Accumulate" in main_body
    assert "clean Buy" in main_body
    assert "revenue growth of 63.5%" not in main_body
    assert "The valuation becomes more plausible only if backlog converts into recognized revenue" in main_body
    assert "Downside risk rises if Neutron execution is delayed" in main_body

    for expected in [
        "$622.5M",
        "$200.3M",
        "$2.20B",
        "$127.5M",
        "$72.9M",
        "$-220.1M",
        "$1.48B",
        "118.78x",
        "Neutron execution risk",
        "Electron/HASTE",
    ]:
        assert expected in report


def test_early_commercial_publish_stub_is_not_public_style_and_has_sensitivity():
    report = compose_early_commercial_manual_review_publish_stub(
        data_packet=DataPacket(
            ticker="RKLB",
            company_name="Rocket Lab Corporation",
            as_of_date="2026-05-15",
            price_basis=PriceBasis(close=124.77, date="2026-05-15", source="csv"),
            source_registry_id="RKLB_sources",
        ),
        metrics_packet=MetricsPacket(
            ticker="RKLB",
            as_of_date="2026-05-15",
            technical=TechnicalMetrics(indicator_date="2026-05-15", close=124.77, rsi_14=70.82),
            fundamentals=FundamentalMetrics(
                fiscal_period="TTM",
                revenue_ttm=622_495_000,
                operating_income_ttm=-250_000_000,
                free_cash_flow_ttm=-220_123_000,
            ),
            valuation=ValuationMetrics(ev_to_sales=118.77771588516552),
        ),
        evidence_ledger=EvidenceLedger(ticker="RKLB", as_of_date="2026-05-15", evidence_items=[]),
        claims=_rklb_early_commercial_claims(),
    )

    quality = publish_report_quality(report)

    assert "not approved for public publication" in report
    assert "## Scenario / Sensitivity" in report
    assert "EV/Sales is 118.78x" in report
    assert quality["publish_mechanical_language_count"] == 0
    assert quality["publish_valuation_sensitivity_present"] == 1


def _claim(section: str, text: str, claim_id: str) -> ResearchClaim:
    return ResearchClaim(
        claim_id=claim_id,
        section=section,
        agent="test",
        claim=text,
        claim_text=text,
        evidence_metrics=["revenue_ttm"],
        evidence_ids=["SEC_TEST_REVENUE"],
        source_ids=["SEC_TEST"],
        confidence="high",
    )


def _rklb_early_commercial_claims() -> list[ResearchClaim]:
    return [
        _claim(
            "Business Model Reality",
            "RKLB is an early-commercial capital-intensive technology company: latest quarterly revenue of $200.3M and TTM revenue of $622.5M show real commercial scale, while FCF of $-220.1M keeps the report in manual-review territory.",
            "RKLB_CLAIM_001",
        ),
        _claim(
            "Revenue Scale and Backlog",
            "RKLB has TTM revenue of $622.5M, latest quarterly revenue of $200.3M, and backlog above $2.20B; backlog is material relative to the current revenue base.",
            "RKLB_CLAIM_002",
        ),
        _claim(
            "Contract / Backlog Materiality",
            "Backlog of $2.20B must be judged against annual revenue, market cap, delivery timing and recurring versus one-off programmatic revenue.",
            "RKLB_CLAIM_003",
        ),
        _claim(
            "Segment Mix",
            "Segment mix shows platform scaling: Space Systems revenue was $127.5M and Launch Services revenue was $72.9M in the latest quarter.",
            "RKLB_CLAIM_004",
        ),
        _claim(
            "Execution Milestones",
            "Execution milestones remain decisive: 31 Electron/HASTE contracts and Neutron execution risk should gate any cleaner rating.",
            "RKLB_CLAIM_005",
        ),
        _claim(
            "FCF Path",
            "The FCF path is still negative: TTM FCF is $-220.1M.",
            "RKLB_CLAIM_006",
        ),
        _claim(
            "Capital Intensity",
            "Capital intensity is visible despite cash and marketable securities of $1.48B.",
            "RKLB_CLAIM_007",
        ),
        _claim(
            "Valuation vs Revenue/Backlog",
            "Valuation is stretched versus current scale: EV/Sales is 118.78x, while backlog is not enough by itself to offset market-cap expectations.",
            "RKLB_CLAIM_008",
        ),
        _claim(
            "Technical Setup only as timing",
            "Technical setup is timing evidence only and should not dominate the fundamental classification.",
            "RKLB_CLAIM_009",
        ),
        _claim(
            "Final Internal View",
            "Final internal view for RKLB should remain Hold/manual review: revenue, backlog and contracts are real, but negative FCF and valuation intensity require more evidence.",
            "RKLB_CLAIM_010",
        ),
    ]
