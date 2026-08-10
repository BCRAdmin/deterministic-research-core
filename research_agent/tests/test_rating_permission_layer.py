import pytest

from research_agent.decision.decision_packet import DecisionPacket, SignalScores
from research_agent.decision.decision_packet import RatingPermission
from research_agent.decision.rating_permission import enforce_rating_permission, extract_rating_from_text
from research_agent.decision.rating_taxonomy import Rating
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


def _permission():
    return RatingPermission(
        allowed_ratings=[Rating.HOLD, Rating.TACTICAL_TRIM],
        blocked_ratings=[Rating.STRONG_BUY, Rating.BUY, Rating.SELL],
        preferred_rating=Rating.TACTICAL_TRIM,
        reason="Action implies trim, not full exit.",
    )


def test_extract_rating_from_final_committee_text():
    assert extract_rating_from_text("Final Rating: Tactical Trim") == Rating.TACTICAL_TRIM
    assert extract_rating_from_text("Recommendation: **Sell**") == Rating.SELL


def test_blocked_rating_cannot_be_final_output():
    with pytest.raises(RuntimeError):
        enforce_rating_permission("Final Rating: Sell", _permission())


def test_allowed_rating_passes_permission_gate():
    enforce_rating_permission("Final Rating: Tactical Trim", _permission())


def test_safety_fallback_cannot_be_rendered_as_analytical_rating():
    permission = _permission().model_copy(
        update={
            "permission_type": "safety_fallback",
            "display_rating": "Unrated",
            "publication_allowed": False,
            "fallback_only": True,
        }
    )

    with pytest.raises(RuntimeError, match="safety fallback"):
        enforce_rating_permission("Final Rating: Tactical Trim", permission)

    enforce_rating_permission("Final Rating: Unrated", permission)


def test_report_builder_blocks_final_decision_with_disallowed_rating():
    decision_packet = DecisionPacket(
        ticker="TEST",
        as_of_date="2026-05-01",
        signal_scores=SignalScores(
            fundamental_score=1,
            technical_score=-1,
            valuation_score=0,
            risk_score=-1,
            composite_score=-1,
        ),
        rating_permission=_permission(),
        action_policy={"primary_action": "Trim partial exposure"},
        key_reasons=[],
        key_risks=[],
    )
    data_packet = DataPacket(
        ticker="TEST",
        company_name="Test Inc.",
        as_of_date="2026-05-01",
        price_basis=PriceBasis(close=100, date="2026-05-01", source="exchange_ohlcv"),
        fiscal_context=FiscalContext(),
        next_events=EventInfo(),
        source_registry_id="TEST_2026_05_01",
    )
    metrics_packet = MetricsPacket(
        ticker="TEST",
        as_of_date="2026-05-01",
        technical=TechnicalMetrics(indicator_date="2026-05-01", close=100),
        fundamentals=FundamentalMetrics(fiscal_period="FY2026"),
        valuation=ValuationMetrics(),
    )
    validation_report = ValidationReport(
        ticker="TEST",
        as_of_date="2026-05-01",
        has_blocking_errors=False,
        issues=[],
    )

    with pytest.raises(RuntimeError):
        render_markdown_report(
            data_packet=data_packet,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            decision_packet=decision_packet,
            final_decision="Final Rating: Sell",
        )
