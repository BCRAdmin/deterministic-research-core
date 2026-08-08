from __future__ import annotations

from typing import Optional

from research_agent.audit.audit_report import AuditReport
from research_agent.calibration.rule_weight_config import DEFAULT_RULE_WEIGHTS, RuleWeightConfig
from research_agent.decision.decision_packet import SignalScores
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


def score_fundamentals(
    metrics: MetricsPacket,
    weights: Optional[RuleWeightConfig] = None,
    triggered_rules: Optional[list[str]] = None,
    calibration_mode: str = "live",
) -> float:
    weights = weights or DEFAULT_RULE_WEIGHTS
    score = 0.0
    f = metrics.fundamentals

    score = _apply_rule(
        score,
        "FCF_TTM_POSITIVE",
        f.free_cash_flow_ttm is not None and f.free_cash_flow_ttm > 0,
        weights,
        triggered_rules,
        calibration_mode,
    )

    if f.fcf_margin_ttm is not None:
        score = _apply_rule(score, "FCF_MARGIN_NEGATIVE", f.fcf_margin_ttm < 0, weights, triggered_rules, calibration_mode)

    if f.operating_margin_ttm is not None:
        score = _apply_rule(score, "OPERATING_MARGIN_NEGATIVE", f.operating_margin_ttm < 0, weights, triggered_rules, calibration_mode)

    score = _apply_rule(
        score,
        "EQUITY_NON_POSITIVE",
        f.equity is not None and f.equity <= 0,
        weights,
        triggered_rules,
        calibration_mode,
    )

    return _clamp(score)


def score_technicals(
    metrics: MetricsPacket,
    weights: Optional[RuleWeightConfig] = None,
    triggered_rules: Optional[list[str]] = None,
    calibration_mode: str = "live",
) -> float:
    weights = weights or DEFAULT_RULE_WEIGHTS
    score = 0.0
    trend_state = classify_technical_trend(metrics)
    score = _apply_rule(
        score,
        "TREND_STATE_BULLISH",
        trend_state == "bullish",
        weights,
        triggered_rules,
        calibration_mode,
    )
    score = _apply_rule(
        score,
        "TREND_STATE_BEARISH",
        trend_state == "bearish",
        weights,
        triggered_rules,
        calibration_mode,
    )

    return _clamp(score)


def classify_technical_trend(metrics: MetricsPacket) -> str:
    technical = metrics.technical
    if technical.sma_50 is None or technical.sma_200 is None:
        return "not_measured"
    price_above_long_term = technical.close > technical.sma_200
    averages_bullish = technical.sma_50 > technical.sma_200
    if price_above_long_term and averages_bullish:
        return "bullish"
    if not price_above_long_term and not averages_bullish:
        return "bearish"
    return "mixed"


def score_valuation(
    metrics: MetricsPacket,
    weights: Optional[RuleWeightConfig] = None,
    triggered_rules: Optional[list[str]] = None,
    calibration_mode: str = "live",
) -> float:
    # Absolute multiples are observations, not relative valuation evidence.
    # Until a peer, history or cycle benchmark is present in the authority
    # packet, valuation must not add a rating bonus or penalty.
    return 0.0


def score_risk(
    metrics: MetricsPacket,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    weights: Optional[RuleWeightConfig] = None,
    triggered_rules: Optional[list[str]] = None,
    calibration_mode: str = "live",
) -> float:
    """Apply only the deterministic financial-risk screen as downside weight.

    Validation and audit findings remain separate quality/publication gates.
    Qualitative business risks remain human-review evidence and cannot create a
    positive score or be inferred from disclosure volume.
    """

    score = metrics.risk.financial_risk_score
    if score is None:
        return 0.0
    if score >= 75:
        return -2.0
    if score >= 50:
        return -1.0
    if score >= 25:
        return -0.5
    return 0.0


def calculate_signal_scores(
    metrics: MetricsPacket,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    weights: Optional[RuleWeightConfig] = None,
    calibration_mode: str = "live",
) -> SignalScores:
    scores, _, _, _ = calculate_signal_scores_with_rules(
        metrics=metrics,
        validation_report=validation_report,
        audit_report=audit_report,
        weights=weights,
        calibration_mode=calibration_mode,
    )
    return scores


def calculate_signal_scores_with_rules(
    metrics: MetricsPacket,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    weights: Optional[RuleWeightConfig] = None,
    calibration_mode: str = "live",
) -> tuple[SignalScores, list[str], str, str]:
    weights = weights or DEFAULT_RULE_WEIGHTS
    triggered_rules: list[str] = []
    fundamental = score_fundamentals(metrics, weights, triggered_rules, calibration_mode)
    technical = score_technicals(metrics, weights, triggered_rules, calibration_mode)
    valuation = score_valuation(metrics, weights, triggered_rules, calibration_mode)
    risk = score_risk(metrics, validation_report, audit_report, weights, triggered_rules, calibration_mode)
    # The composite is the long-term analytical score. Technicals remain a
    # separate timing overlay and must not rewrite the company conclusion.
    composite = _clamp(fundamental + valuation + risk)
    scores = SignalScores(
        fundamental_score=fundamental,
        technical_score=technical,
        valuation_score=valuation,
        risk_score=risk,
        composite_score=composite,
        fundamental_status=_coverage_status([
            metrics.fundamentals.revenue_ttm,
            metrics.fundamentals.operating_income_ttm,
            metrics.fundamentals.net_income_ttm,
            metrics.fundamentals.operating_cash_flow_ttm,
            metrics.fundamentals.total_debt,
        ]),
        technical_status=(
            "measured"
            if metrics.technical.price_series_basis == "corporate_action_adjusted"
            else "partial"
            if metrics.technical.close is not None
            else "not_measured"
        ),
        valuation_status=_valuation_status(metrics),
        risk_status=metrics.risk.status,
    )
    return scores, _ordered_unique(triggered_rules), weights.version, calibration_mode


def _apply_rule(
    score: float,
    rule_id: str,
    condition: bool,
    weights: RuleWeightConfig,
    triggered_rules: Optional[list[str]],
    calibration_mode: str,
) -> float:
    if not condition:
        return score
    if triggered_rules is not None:
        triggered_rules.append(rule_id)
    return score + weights.get_weight(rule_id, calibration_mode)


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _clamp(score: float) -> float:
    return max(-3, min(3, score))


def _coverage_status(values: list[object]) -> str:
    measured = sum(value is not None for value in values)
    if measured == len(values):
        return "measured"
    if measured:
        return "partial"
    return "not_measured"


def _valuation_status(metrics: MetricsPacket) -> str:
    sensitivity_status = metrics.valuation.sensitivity.status
    if sensitivity_status == "measured":
        return "scenario_measured"
    if sensitivity_status == "illustrative_only":
        return "illustrative_only"
    values = [
        metrics.valuation.market_cap,
        metrics.valuation.trailing_pe,
        metrics.valuation.forward_pe_consensus,
        metrics.valuation.ev_to_sales,
        metrics.valuation.ev_to_ebitda,
        metrics.valuation.price_to_fcf,
        metrics.valuation.peg_ratio,
    ]
    return "unbenchmarked" if any(value is not None for value in values) else "not_measured"
