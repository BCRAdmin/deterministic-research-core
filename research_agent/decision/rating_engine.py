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
    fundamental = scores.fundamental_score
    technical = scores.technical_score
    valuation = scores.valuation_score
    risk = scores.risk_score
    coverage_states = {
        scores.fundamental_status,
        scores.technical_status,
        scores.valuation_status,
        scores.risk_status,
    }
    evidence_status = (
        "incomplete"
        if "not_measured" in {
            scores.fundamental_status,
            scores.technical_status,
        }
        else "partial" if "partial" in coverage_states
        else "complete"
    )

    if fundamental >= 2 and technical >= 1 and valuation >= 0 and risk >= -1:
        allowed = [Rating.BUY, Rating.ACCUMULATE, Rating.HOLD]
        preferred = Rating.ACCUMULATE
        reason = "Strong business quality and constructive technical setup support staged accumulation."
    elif fundamental >= 1 and technical <= -1:
        allowed = [Rating.HOLD, Rating.TACTICAL_TRIM, Rating.TACTICAL_UNDERWEIGHT]
        preferred = Rating.TACTICAL_UNDERWEIGHT if risk <= -2 else Rating.HOLD
        reason = "Business quality is positive, but technical trend is weak and risk controls matter."
    elif fundamental <= -1 and technical <= -1:
        allowed = [Rating.TACTICAL_UNDERWEIGHT, Rating.UNDERWEIGHT, Rating.SELL]
        preferred = Rating.UNDERWEIGHT
        reason = "Weak business score and weak technicals restrict the rating to underweight or sell territory."
    elif fundamental >= 1 and technical >= 1 and risk <= -2:
        allowed = [Rating.HOLD, Rating.ACCUMULATE, Rating.TACTICAL_TRIM]
        preferred = Rating.HOLD
        reason = "Fundamentals and trend are constructive, but elevated risk prevents an aggressive rating."
    else:
        allowed = [Rating.HOLD, Rating.ACCUMULATE, Rating.TACTICAL_TRIM]
        preferred = Rating.HOLD
        reason = "Mixed signals require a neutral-to-tactical rating corridor."

    if action_class == "tactical_trim":
        allowed = _ordered_unique(allowed + [Rating.TACTICAL_TRIM, Rating.HOLD])
        allowed = [rating for rating in allowed if rating != Rating.SELL]
        preferred = Rating.TACTICAL_TRIM
        reason = "Operative action implies partial trim and core hold, not a full exit."
    elif action_class == "staged_entry":
        allowed = _ordered_unique(allowed + [Rating.ACCUMULATE, Rating.BUY])
        allowed = [rating for rating in allowed if rating != Rating.STRONG_BUY]
        preferred = Rating.ACCUMULATE
        reason = "Operative action implies staged accumulation rather than an immediate full buy."
    elif action_class == "sell":
        allowed = _ordered_unique(allowed + [Rating.SELL, Rating.UNDERWEIGHT])
        preferred = Rating.SELL if fundamental <= -1 and technical <= -1 else preferred

    if _has_material_warnings(validation_report, audit_report) and Rating.STRONG_BUY in allowed:
        allowed.remove(Rating.STRONG_BUY)
        if preferred == Rating.STRONG_BUY:
            preferred = Rating.BUY if Rating.BUY in allowed else Rating.ACCUMULATE

    all_ratings = list(Rating)
    blocked = [rating for rating in all_ratings if rating not in allowed]

    return RatingPermission(
        allowed_ratings=allowed,
        blocked_ratings=blocked,
        preferred_rating=preferred,
        reason=reason,
        evidence_status=evidence_status,
    )


def determine_unconstrained_analytical_rating(
    scores: SignalScores,
) -> tuple[Rating, str]:
    """Reach the research conclusion before any action or publication policy."""

    fundamental = scores.fundamental_score
    technical = scores.technical_score
    valuation = scores.valuation_score
    risk = scores.risk_score
    if fundamental >= 2 and technical >= 1 and valuation >= 0 and risk >= -1:
        return (
            Rating.ACCUMULATE,
            "Strong business quality and constructive technical evidence support an overweight analytical stance.",
        )
    if fundamental >= 1 and technical <= -1:
        rating = Rating.TACTICAL_UNDERWEIGHT if risk <= -2 else Rating.HOLD
        return (
            rating,
            "Positive business quality is offset by weak technical evidence and measured risk.",
        )
    if fundamental <= -1 and technical <= -1:
        return (
            Rating.UNDERWEIGHT,
            "Weak fundamental and technical evidence support an underweight analytical stance.",
        )
    if fundamental >= 1 and technical >= 1 and risk <= -2:
        return (
            Rating.HOLD,
            "Constructive fundamentals and trend are offset by elevated measured risk.",
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
        key_reasons=_build_key_reasons(scores, action_class),
        key_risks=_build_key_risks(scores, validation_report, audit_report),
        triggered_rules=triggered_rules,
        score_version=score_version,
        calibration_mode=mode,
    )


def _ordered_unique(ratings: list[Rating]) -> list[Rating]:
    return [rating for rating in Rating if rating in ratings]


def _has_material_warnings(
    validation_report: Optional[ValidationReport],
    audit_report: Optional[AuditReport],
) -> bool:
    validation_warnings = validation_report.issues if validation_report else []
    audit_warnings = audit_report.issues if audit_report else []
    return bool(validation_warnings or audit_warnings)


def _build_key_reasons(scores: SignalScores, action_class: Optional[str]) -> list[str]:
    reasons = [
        f"Fundamental score: {scores.fundamental_score}",
        f"Technical score: {scores.technical_score}",
        f"Valuation score: {scores.valuation_score}",
    ]
    if action_class:
        reasons.append(f"Operative action class: {action_class}")
    return reasons


def _build_key_risks(
    scores: SignalScores,
    validation_report: Optional[ValidationReport],
    audit_report: Optional[AuditReport],
) -> list[str]:
    risks = [
        f"Risk score: {scores.risk_score} (measurement status: {scores.risk_status})"
    ]
    if scores.risk_status != "measured":
        risks.append("Missing risk evidence is not equivalent to low risk.")
    if validation_report and validation_report.issues:
        risks.append(f"Validation issues: {len(validation_report.issues)}")
    if audit_report and audit_report.issues:
        risks.append(f"Audit issues: {len(audit_report.issues)}")
    return risks
