from __future__ import annotations


UNIT_MAP = {
    "USD": "usd",
    "usd": "usd",
    "USD/shares": "usd_per_share",
    "USD/share": "usd_per_share",
    "usd/share": "usd_per_share",
    "usd/shares": "usd_per_share",
    "shares": "shares",
    "Shares": "shares",
    "pure": "ratio",
    "Pure": "ratio",
    "percent": "percent",
}


def normalize_unit(unit: str) -> str:
    return UNIT_MAP.get(unit, unit.lower())


def normalize_value(value: float, unit: str):
    return value, normalize_unit(unit)


def validate_unit_for_metric(metric_name: str, unit: str):
    normalized_unit = normalize_unit(unit)
    if metric_name in {"eps_diluted", "eps_basic", "guidance_eps", "company_guidance_eps", "consensus_forward_eps"}:
        if normalized_unit != "usd_per_share":
            return {
                "severity": "warning",
                "code": "SUSPICIOUS_EPS_UNIT",
                "metric": metric_name,
                "message": f"{metric_name} should use per-share unit, got {unit}.",
            }
    return None
