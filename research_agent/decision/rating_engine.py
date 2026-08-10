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
        display_rating=preferred.value,
    )


def determine_unconstrained_analytical_rating(
    scores: SignalScores,
) -> tuple[Rating, str]:
    """Reach the long-term research conclusion before publication policy.

    Fundamentals, valuation and issuer risk form the conclusion. Technicals
    remain an explicitly separate timing overlay and therefore neither unlock
    nor block a long-term rating.
    """

    fundamental = scores.fundamental_score
    technical_boundary = (
        "verified technical evidence remains a separate timing overlay"
        if scores.technical_status == "measured"
        else "unverified technical inputs are excluded from rating and timing"
    )
    if scores.fundamental_status != "measured":
        return (
            Rating.HOLD,
            "Core fundamental coverage is incomplete. The neutral label is a "
            f"safety fallback, while {technical_boundary}.",
        )
    if fundamental <= -1 and (
        scores.risk_score <= -1 or scores.valuation_score <= -1
    ):
        return (
            Rating.UNDERWEIGHT,
            "Negative fundamental direction is confirmed by measured valuation "
            f"or financial-risk downside; {technical_boundary}.",
        )
    if fundamental >= 1 and scores.valuation_score >= 1:
        return (
            Rating.ACCUMULATE,
            "Constructive fundamentals and calibrated valuation evidence support "
            f"an accumulate analytical stance; {technical_boundary}.",
        )
    if fundamental >= 1 and scores.valuation_status in {
        "unbenchmarked",
        "scenario_measured",
        "illustrative_only",
        "not_measured",
    }:
        return (
            Rating.HOLD,
            "Constructive fundamentals are not enough for an overweight rating "
            f"without calibrated valuation evidence; {technical_boundary}.",
        )
    return (
        Rating.HOLD,
        "The measured long-term evidence supports a neutral analytical stance; "
        f"{technical_boundary}.",
    )


def build_decision_packet(
    metrics_packet: MetricsPacket,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    action_class: Optional[str] = None,
    rule_weights: Optional[RuleWeightConfig] = None,
    calibration_mode: str = "live",
    research_scope_complete: Optional[bool] = None,
    research_scope_gaps: Optional[list[str]] = None,
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
    base_analytical_rating, analytical_reason = (
        determine_unconstrained_analytical_rating(scores)
    )
    conclusion_status, conclusion_status_reason = _conclusion_status(
        scores=scores,
        validation_report=validation_report,
        audit_report=audit_report,
        research_scope_complete=research_scope_complete,
        research_scope_gaps=research_scope_gaps,
    )
    analytical_rating: Optional[Rating] = base_analytical_rating
    if conclusion_status in {"not_rated", "blocked"}:
        analytical_rating = None
        permission = permission.model_copy(
            update={
                "permission_type": "safety_fallback",
                "display_rating": "Unrated",
                "publication_allowed": False,
                "fallback_only": True,
                "reason": (
                    "Hold is retained only as an internal fail-closed fallback; "
                    "it is not an analytical rating. " + conclusion_status_reason
                ),
            }
        )
    elif conclusion_status == "provisional":
        permission = permission.model_copy(
            update={
                "permission_type": "provisional",
                "display_rating": f"Provisional — {base_analytical_rating.value}",
                "publication_allowed": False,
                "fallback_only": False,
            }
        )
    evidence_maturity = {
        "rated": "complete",
        "provisional": "partial",
        "not_rated": "incomplete",
        "blocked": "blocked",
    }[conclusion_status]
    publication_permission = (
        "eligible"
        if conclusion_status == "rated"
        else "manual_review"
        if conclusion_status == "provisional"
        else "blocked"
    )
    action_policy = build_action_policy(permission.preferred_rating, metrics_packet)
    if conclusion_status in {"not_rated", "blocked"}:
        action_policy = {
            key: value
            for key, value in action_policy.items()
            if key in {"technical_boundary"}
        }
        action_policy.update(
            {
                "research_stance": "No analytical stance: required evidence is incomplete.",
                "actionability": "blocked",
                "internal_fallback_rating": permission.preferred_rating.value,
                "reason": conclusion_status_reason,
            }
        )
    elif conclusion_status == "provisional":
        action_policy = {
            **action_policy,
            "actionability": "manual_review_only",
            "reason": conclusion_status_reason,
        }
    else:
        action_policy = {**action_policy, "actionability": "eligible"}

    return DecisionPacket(
        ticker=metrics_packet.ticker,
        as_of_date=metrics_packet.as_of_date,
        signal_scores=scores,
        analytical_rating_unconstrained=analytical_rating,
        analytical_rating_reason=analytical_reason,
        conclusion_status=conclusion_status,
        conclusion_status_reason=conclusion_status_reason,
        evidence_maturity=evidence_maturity,
        publication_permission=publication_permission,
        rating_permission=permission,
        action_policy=action_policy,
        key_reasons=_build_key_reasons(scores),
        key_risks=_build_key_risks(metrics_packet),
        triggered_rules=triggered_rules,
        score_version=score_version,
        calibration_mode=mode,
    )


def _conclusion_status(
    *,
    scores: SignalScores,
    validation_report: Optional[ValidationReport],
    audit_report: Optional[AuditReport],
    research_scope_complete: Optional[bool],
    research_scope_gaps: Optional[list[str]],
) -> tuple[str, str]:
    """Separate an analytical direction from its review/publication maturity."""

    if validation_report and validation_report.has_blocking_errors:
        return "blocked", "Blocking validation errors prevent a usable conclusion."
    if audit_report and audit_report.has_blocking_errors:
        return "blocked", "Blocking audit errors prevent a usable conclusion."
    if research_scope_complete is False:
        gaps = ", ".join(research_scope_gaps or []) or "unspecified source scopes"
        return (
            "not_rated",
            "Required research-source scopes are incomplete: " + gaps + ".",
        )

    evidence_status = _evidence_status(scores)
    if evidence_status == "incomplete":
        return (
            "not_rated",
            "Core evidence is incomplete; the neutral rating is only a safety fallback.",
        )
    if evidence_status == "partial":
        return (
            "provisional",
            "The analytical direction is provisional because one or more evidence dimensions are partial, unbenchmarked, or not measured.",
        )
    return "rated", "All decision-model evidence dimensions are measured."


def _evidence_status(scores: SignalScores) -> str:
    if scores.fundamental_status == "not_measured":
        return "incomplete"
    all_states = {
        scores.fundamental_status,
        scores.technical_status,
        scores.valuation_status,
        scores.risk_status,
    }
    if all_states & {
        "partial",
        "unbenchmarked",
        "scenario_measured",
        "illustrative_only",
        "not_measured",
    }:
        return "partial"
    return "complete"


def _build_key_reasons(scores: SignalScores) -> list[str]:
    reasons = [
        f"Fundamental score: {scores.fundamental_score}",
        (
            f"Technical timing score: {scores.technical_score} "
            f"(measurement status: {scores.technical_status}; excluded from "
            "the long-term rating)"
        ),
        (
            f"Valuation score: {scores.valuation_score} "
            f"(measurement status: {scores.valuation_status})"
        ),
        (
            f"Financial-risk downside contribution: {scores.risk_score} "
            f"(measurement status: {scores.risk_status}; zero is not a "
            "low-risk conclusion)"
        ),
    ]
    return reasons


def _build_key_risks(metrics: MetricsPacket) -> list[str]:
    assessment = metrics.risk
    if assessment.financial_risk_score is None:
        return ["Company risk score: not measured by the current decision model."]
    risks = [
        (
            f"Financial risk screen: {assessment.financial_risk_score:.2f}/100 "
            f"({assessment.financial_risk_band}; coverage {assessment.coverage_ratio:.0%})."
        )
    ]
    risks.extend(f"Risk flag: {flag}." for flag in assessment.risk_flags)
    risks.append(
        "Qualitative business-risk severity remains subject to independent human review."
    )
    return risks
