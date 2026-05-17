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

    if f.revenue_growth_yoy is not None:
        score = _apply_rule(score, "REVENUE_GROWTH_GT_30", f.revenue_growth_yoy >= 0.30, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "REVENUE_GROWTH_GT_15", 0.15 <= f.revenue_growth_yoy < 0.30, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "REVENUE_GROWTH_LT_5", f.revenue_growth_yoy < 0.05, weights, triggered_rules, calibration_mode)

    score = _apply_rule(
        score,
        "FCF_TTM_POSITIVE",
        f.free_cash_flow_ttm is not None and f.free_cash_flow_ttm > 0,
        weights,
        triggered_rules,
        calibration_mode,
    )

    if f.fcf_margin_ttm is not None:
        score = _apply_rule(score, "FCF_MARGIN_GT_25", f.fcf_margin_ttm >= 0.25, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "FCF_MARGIN_NEGATIVE", f.fcf_margin_ttm < 0, weights, triggered_rules, calibration_mode)

    if f.operating_margin_ttm is not None:
        score = _apply_rule(score, "OPERATING_MARGIN_GT_10", f.operating_margin_ttm > 0.10, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "OPERATING_MARGIN_NEGATIVE", f.operating_margin_ttm < 0, weights, triggered_rules, calibration_mode)

    score = _apply_rule(
        score,
        "SBC_TO_REVENUE_GT_20",
        f.sbc_to_revenue is not None and f.sbc_to_revenue > 0.20,
        weights,
        triggered_rules,
        calibration_mode,
    )

    score = _apply_rule(
        score,
        "NET_CASH_POSITIVE",
        f.net_cash is not None and f.net_cash > 0,
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
    t = metrics.technical

    if t.sma_200 is not None:
        score = _apply_rule(score, "PRICE_ABOVE_200SMA", t.close > t.sma_200, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "PRICE_BELOW_200SMA", t.close <= t.sma_200, weights, triggered_rules, calibration_mode)

    if t.sma_50 is not None and t.sma_200 is not None:
        score = _apply_rule(score, "GOLDEN_CROSS", t.sma_50 > t.sma_200, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "DEATH_CROSS", t.sma_50 <= t.sma_200, weights, triggered_rules, calibration_mode)

    if t.ema_10 is not None:
        score = _apply_rule(score, "PRICE_ABOVE_EMA10", t.close > t.ema_10, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "PRICE_BELOW_EMA10", t.close <= t.ema_10, weights, triggered_rules, calibration_mode)

    if t.rsi_14 is not None:
        score = _apply_rule(score, "RSI_GT_75", t.rsi_14 > 75, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "RSI_LT_30", t.rsi_14 < 30, weights, triggered_rules, calibration_mode)

    if t.macd_histogram is not None:
        score = _apply_rule(score, "MACD_HISTOGRAM_POSITIVE", t.macd_histogram > 0, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "MACD_HISTOGRAM_NEGATIVE", t.macd_histogram <= 0, weights, triggered_rules, calibration_mode)

    return _clamp(score)


def score_valuation(
    metrics: MetricsPacket,
    weights: Optional[RuleWeightConfig] = None,
    triggered_rules: Optional[list[str]] = None,
    calibration_mode: str = "live",
) -> float:
    weights = weights or DEFAULT_RULE_WEIGHTS
    score = 0.0
    v = metrics.valuation
    f = metrics.fundamentals

    if v.forward_pe_consensus is not None:
        score = _apply_rule(score, "FORWARD_PE_LT_25", v.forward_pe_consensus < 25, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "FORWARD_PE_GT_60", v.forward_pe_consensus > 60, weights, triggered_rules, calibration_mode)

    if v.price_to_fcf is not None:
        score = _apply_rule(score, "PRICE_TO_FCF_LT_30", v.price_to_fcf < 30, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "PRICE_TO_FCF_GT_60", v.price_to_fcf > 60, weights, triggered_rules, calibration_mode)

    if v.peg_ratio is not None:
        score = _apply_rule(score, "PEG_LT_1", v.peg_ratio < 1, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "PEG_GT_2", v.peg_ratio > 2, weights, triggered_rules, calibration_mode)

    score = _apply_rule(
        score,
        "SBC_TO_FCF_GT_100",
        f.sbc_to_fcf is not None and f.sbc_to_fcf > 1,
        weights,
        triggered_rules,
        calibration_mode,
    )

    return _clamp(score)


def score_risk(
    metrics: MetricsPacket,
    validation_report: Optional[ValidationReport] = None,
    audit_report: Optional[AuditReport] = None,
    weights: Optional[RuleWeightConfig] = None,
    triggered_rules: Optional[list[str]] = None,
    calibration_mode: str = "live",
) -> float:
    weights = weights or DEFAULT_RULE_WEIGHTS
    score = 0.0
    f = metrics.fundamentals
    t = metrics.technical

    if t.atr_14 and t.close:
        atr_pct = t.atr_14 / t.close
        score = _apply_rule(score, "ATR_PCT_GT_8", atr_pct > 0.08, weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "ATR_PCT_GT_5", 0.05 < atr_pct <= 0.08, weights, triggered_rules, calibration_mode)

    score = _apply_rule(
        score,
        "SBC_TO_REVENUE_GT_20",
        f.sbc_to_revenue is not None and f.sbc_to_revenue > 0.20,
        weights,
        triggered_rules,
        calibration_mode,
    )

    if validation_report:
        errors = [issue for issue in validation_report.issues if issue.severity == "error"]
        warnings = [issue for issue in validation_report.issues if issue.severity == "warning"]

        score = _apply_rule(score, "VALIDATION_ERROR", bool(errors), weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "VALIDATION_WARNINGS_GE_3", not errors and len(warnings) >= 3, weights, triggered_rules, calibration_mode)
        score = _apply_rule(
            score,
            "FORWARD_EPS_GUIDANCE_MISMATCH",
            any(issue.code == "FORWARD_EPS_GUIDANCE_MISMATCH" for issue in validation_report.issues),
            weights,
            triggered_rules,
            calibration_mode,
        )

    if audit_report:
        blocking = [issue for issue in audit_report.issues if issue.severity == "error"]
        warnings = [issue for issue in audit_report.issues if issue.severity == "warning"]
        score = _apply_rule(score, "AUDIT_ERROR", bool(blocking), weights, triggered_rules, calibration_mode)
        score = _apply_rule(score, "AUDIT_WARNINGS_GE_2", not blocking and len(warnings) >= 2, weights, triggered_rules, calibration_mode)

    return _clamp(score)


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
    composite = _clamp(fundamental + technical + valuation + risk)
    scores = SignalScores(
        fundamental_score=fundamental,
        technical_score=technical,
        valuation_score=valuation,
        risk_score=risk,
        composite_score=composite,
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
