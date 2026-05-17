from __future__ import annotations


def validate_ttm_sum(
    metric_name: str,
    quarterly_values: list[float],
    reported_ttm: float,
    tolerance: float = 0.01,
):
    if len(quarterly_values) != 4:
        return {
            "severity": "error",
            "code": "TTM_REQUIRES_FOUR_QUARTERS",
            "metric": metric_name,
            "message": f"{metric_name} TTM requires exactly 4 quarterly values.",
        }

    computed = sum(quarterly_values)

    if abs(computed - reported_ttm) > max(abs(computed) * tolerance, 1e-6):
        return {
            "severity": "error",
            "code": "TTM_SUM_MISMATCH",
            "metric": metric_name,
            "computed": computed,
            "reported": reported_ttm,
            "message": f"{metric_name} TTM mismatch. Computed {computed}, reported {reported_ttm}.",
        }

    return None


def validate_margin(
    metric_name: str,
    numerator: float,
    revenue: float,
    reported_margin: float,
    tolerance: float = 0.005,
):
    computed = numerator / revenue if revenue else None

    if computed is None:
        return {
            "severity": "error",
            "code": "MARGIN_DIVIDE_BY_ZERO",
            "metric": metric_name,
            "message": f"{metric_name} cannot be computed because revenue is zero or missing.",
        }

    if abs(computed - reported_margin) > tolerance:
        return {
            "severity": "error",
            "code": "MARGIN_MISMATCH",
            "metric": metric_name,
            "computed": computed,
            "reported": reported_margin,
            "message": f"{metric_name} margin mismatch.",
        }

    return None


def validate_forward_eps_vs_guidance(
    consensus_eps,
    guidance_low,
    guidance_high,
    threshold=0.10,
):
    guidance_mid = (guidance_low + guidance_high) / 2
    diff = abs(consensus_eps - guidance_mid) / guidance_mid

    if diff > threshold:
        return {
            "severity": "warning",
            "code": "FORWARD_EPS_GUIDANCE_MISMATCH",
            "message": f"Consensus EPS differs from company guidance midpoint by {diff:.1%}.",
        }

    return None

