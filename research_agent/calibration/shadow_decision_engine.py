from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from research_agent.audit.audit_report import AuditReport
from research_agent.calibration.rule_weight_config import DEFAULT_RULE_WEIGHTS, RuleWeightConfig
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.outcomes.benchmark_outcome import BenchmarkOutcome
from research_agent.outcomes.price_outcome import WindowOutcome
from research_agent.outcomes.rating_evaluator import evaluate_rating_success
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


class ShadowDecisionComparison(BaseModel):
    report_id: str
    live_preferred_rating: str
    shadow_preferred_rating: str
    live_success_60d: Optional[bool] = None
    shadow_success_60d: Optional[bool] = None
    shadow_would_have_helped: Optional[bool] = None


def build_shadow_decision_packet(
    metrics_packet: MetricsPacket,
    shadow_rule_weights: RuleWeightConfig,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    action_class: Optional[str] = None,
) -> DecisionPacket:
    return build_decision_packet(
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        action_class=action_class,
        rule_weights=shadow_rule_weights,
        calibration_mode="shadow",
    )


def compare_live_vs_shadow_decision(
    report_id: str,
    metrics_packet: MetricsPacket,
    outcome_20d: Optional[WindowOutcome],
    outcome_60d: Optional[WindowOutcome],
    benchmark_60d: Optional[BenchmarkOutcome] = None,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    action_class: Optional[str] = None,
    live_rule_weights: RuleWeightConfig = DEFAULT_RULE_WEIGHTS,
    shadow_rule_weights: Optional[RuleWeightConfig] = None,
) -> ShadowDecisionComparison:
    shadow_rule_weights = shadow_rule_weights or live_rule_weights
    live_packet = build_decision_packet(
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        action_class=action_class,
        rule_weights=live_rule_weights,
        calibration_mode="live",
    )
    shadow_packet = build_shadow_decision_packet(
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        action_class=action_class,
        shadow_rule_weights=shadow_rule_weights,
    )
    return compare_decision_packets(
        report_id=report_id,
        live_packet=live_packet,
        shadow_packet=shadow_packet,
        outcome_20d=outcome_20d,
        outcome_60d=outcome_60d,
        benchmark_60d=benchmark_60d,
    )


def compare_decision_packets(
    report_id: str,
    live_packet: DecisionPacket,
    shadow_packet: DecisionPacket,
    outcome_20d: Optional[WindowOutcome],
    outcome_60d: Optional[WindowOutcome],
    benchmark_60d: Optional[BenchmarkOutcome] = None,
) -> ShadowDecisionComparison:
    live_rating = live_packet.rating_permission.preferred_rating.value
    shadow_rating = shadow_packet.rating_permission.preferred_rating.value
    live_success = evaluate_rating_success(live_rating, outcome_20d, outcome_60d, benchmark_60d)
    shadow_success = evaluate_rating_success(shadow_rating, outcome_20d, outcome_60d, benchmark_60d)
    return ShadowDecisionComparison(
        report_id=report_id,
        live_preferred_rating=live_rating,
        shadow_preferred_rating=shadow_rating,
        live_success_60d=live_success,
        shadow_success_60d=shadow_success,
        shadow_would_have_helped=_shadow_helped(live_success, shadow_success),
    )


def _shadow_helped(live_success: Optional[bool], shadow_success: Optional[bool]) -> Optional[bool]:
    if live_success is None or shadow_success is None:
        return None
    return shadow_success and not live_success
