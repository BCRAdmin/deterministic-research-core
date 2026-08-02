import json
from pathlib import Path

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.audit.rating_action_extractor import (
    extract_action_lines,
    infer_report_action_class,
)
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.decision.rating_taxonomy import Rating
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(fixture_name, filename):
    return json.loads((FIXTURES / fixture_name / filename).read_text(encoding="utf-8"))


def _load_text(fixture_name, filename):
    return (FIXTURES / fixture_name / filename).read_text(encoding="utf-8")


def _metrics(fixture_name):
    return MetricsPacket(**_load_json(fixture_name, "metrics_packet.json"))


def _validation(fixture_name):
    return ValidationReport(**_load_json(fixture_name, "validation_report.json"))


def _audit(fixture_name):
    return audit_markdown_report(
        markdown=_load_text(fixture_name, "bad_report.md"),
        metrics_packet=_metrics(fixture_name),
        validation_report=_validation(fixture_name),
        source_registry=SourceRegistry(**_load_json(fixture_name, "source_registry.json")),
    )


def _action_class(fixture_name):
    actions = extract_action_lines(_load_text(fixture_name, "bad_report.md"))
    return infer_report_action_class(actions)


def test_amzn_decision_prefers_hold_and_blocks_sell_strong_buy():
    packet = build_decision_packet(
        metrics_packet=_metrics("amzn_2026_05_01"),
        validation_report=_validation("amzn_2026_05_01"),
        audit_report=_audit("amzn_2026_05_01"),
    )

    assert packet.rating_permission.preferred_rating == Rating.HOLD
    assert Rating.SELL in packet.rating_permission.blocked_ratings
    assert Rating.STRONG_BUY in packet.rating_permission.blocked_ratings


def test_nvda_decision_stays_hold_without_valuation_benchmark():
    packet = build_decision_packet(
        metrics_packet=_metrics("nvda_2026_05_01"),
        validation_report=_validation("nvda_2026_05_01"),
    )

    assert Rating.SELL in packet.rating_permission.blocked_ratings
    assert Rating.UNDERWEIGHT in packet.rating_permission.blocked_ratings
    assert packet.rating_permission.preferred_rating == Rating.HOLD
    assert Rating.ACCUMULATE in packet.rating_permission.blocked_ratings


def test_ddog_trim_not_sell():
    packet = build_decision_packet(
        metrics_packet=_metrics("ddog_2026_05_01"),
        validation_report=_validation("ddog_2026_05_01"),
        audit_report=_audit("ddog_2026_05_01"),
        action_class=_action_class("ddog_2026_05_01"),
    )

    assert packet.rating_permission.preferred_rating == Rating.TACTICAL_TRIM
    assert Rating.SELL in packet.rating_permission.blocked_ratings


def test_mdb_blocks_strong_buy_and_sell():
    packet = build_decision_packet(
        metrics_packet=_metrics("mdb_2026_05_01"),
        validation_report=_validation("mdb_2026_05_01"),
        action_class=None,
    )

    assert Rating.STRONG_BUY in packet.rating_permission.blocked_ratings
    assert Rating.SELL in packet.rating_permission.blocked_ratings
    assert packet.rating_permission.preferred_rating in {
        Rating.TACTICAL_UNDERWEIGHT,
        Rating.TACTICAL_TRIM,
        Rating.HOLD,
    }
