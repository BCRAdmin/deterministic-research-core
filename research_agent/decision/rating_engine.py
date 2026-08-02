from __future__ import annotations

from typing import Optional

from research_agent.audit.audit_report import AuditReport
from research_agent.calibration.rule_weight_config import RuleWeightConfig
from research_agent.decision.action_policy import build_action_policy
from research_agent.decision.decision_packet import DecisionPacket, RatingPermission, SignalScores
from research_agent.decision.rating_taxonomy import Rating
from research_agent.decision.signal_scores import calculate_signal_scores_with_rules
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


def determine_rating_permission(
    scores: SignalScores,
    action_class: Optional[str] = None,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
) -> RatingPermission:
    """Apply a fail-closed policy after the independent analytical rating.

    ``action_class`` and the reports remain accepted for API compatibility,
    but they must not feed a conclusion back into the evidence layer.  Report
    wording and validation quality can constrain publication separately; they
    cannot create a different company rating.
    """

    preferred, reason = determine_unconstrained_analytical_rating(scores)
    # There is no independent policy model that justifies alternative ratings
    # today.  Keep the compatibility layer fail-closed to the analytical result
    # instead of inventing a corridor around it.
    allowed = [preferred]

    all_ratings = list(Rating)
    blocked = [rating for rating in all_ratings if rating not in allowed]

    return RatingPermission(
        allowed_ratings=allowed,
        blocked_ratings=blocked,
        preferred_rating=preferred,
        reason=reason,
        evidence_status=_evidence_status(scores),
    )


def determine_unconstrained_analytical_rating(
    scores: SignalScores,
) -> tuple[Rating, str]:
    """Reach the research conclusion before any action or publication policy."""

    fundamental = scores.fundamental_score
    technical = scores.technical_score
    if fundamental <= -1 and technical <= -1:
        return (
            Rating.UNDERWEIGHT,
            "Negative fundamental direction and a bearish long-term trend support an underweight analytical stance.",
        )
    if fundamental >= 1 and technical <= -1:
        return (
            Rating.HOLD,
            "Positive cash-flow direction is offset by a bearish long-term trend.",
        )
    if fundamental >= 1 and technical >= 1:
        return (
            Rating.HOLD,
            "Constructive directional evidence is not enough for an overweight rating without benchmarked valuation evidence.",
        )
    return (
        Rating.HOLD,
        "Mixed evidence supports a neutral analytical stance.",
    )


def build_decision_packet(
    metrics_packet: MetricsPacket,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    action_class: Optional[str] = None,
    rule_weights: Optional[RuleWeightConfig] = None,
    calibration_mode: str = "live",
) -> DecisionPacket:
    scores, triggered_rules, score_version, mode = calculate_signal_scores_with_rules(
        metrics=metrics_packet,
        validation_report=validation_report,
        audit_report=audit_report,
        weights=rule_weights,
        calibration_mode=calibration_mode,
    )
    permission = determine_rating_permission(
        scores=scores,
        action_class=action_class,
        validation_report=validation_report,
        audit_report=audit_report,
    )
    analytical_rating, analytical_reason = (
        determine_unconstrained_analytical_rating(scores)
    )
    return DecisionPacket(
        ticker=metrics_packet.ticker,
        as_of_date=metrics_packet.as_of_date,
        signal_scores=scores,
        analytical_rating_unconstrained=analytical_rating,
        analytical_rating_reason=analytical_reason,
        rating_permission=permission,
        action_policy=build_action_policy(permission.preferred_rating, metrics_packet),
        key_reasons=_build_key_reasons(scores),
        key_risks=_build_key_risks(scores, validation_report, audit_report),
        triggered_rules=triggered_rules,
        score_version=score_version,
        calibration_mode=mode,
    )


def _evidence_status(scores: SignalScores) -> str:
    core_states = {scores.fundamental_status, scores.technical_status}
    all_states = core_states | {scores.valuation_status, scores.risk_status}
    if "not_measured" in core_states:
        return "incomplete"
    if all_states & {"partial", "unbenchmarked", "not_measured"}:
        return "partial"
    return "complete"


def _build_key_reasons(scores: SignalScores) -> list[str]:
    reasons = [
        f"Fundamental score: {scores.fundamental_score}",
        f"Technical score: {scores.technical_score}",
        (
            f"Valuation score: {scores.valuation_score} "
            f"(measurement status: {scores.valuation_status})"
        ),
    ]
    return reasons


def _build_key_risks(
    scores: SignalScores,
    validation_report: Optional[ValidationReport],
    audit_report: Optional[AuditReport],
) -> list[str]:
    risks = ["Company risk score: not measured by the current decision model."]
    if validation_report and validation_report.issues:
        risks.append(f"Validation issues: {len(validation_report.issues)}")
    if audit_report and audit_report.issues:
        risks.append(f"Audit issues: {len(audit_report.issues)}")
    return risks
