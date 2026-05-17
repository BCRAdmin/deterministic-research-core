from __future__ import annotations

from typing import Optional


def classify_metric_basis(source_type: str, metric_name: str, source_text: Optional[str] = None):
    text = (source_text or "").lower()
    metric = metric_name.lower()

    if source_type in {"consensus", "market_data_provider"} or "consensus" in metric:
        return "consensus"
    if "non-gaap" in text or "non gaap" in text or "adjusted" in text:
        return "non_gaap"
    if "guidance" in metric:
        return "non_gaap" if "non-gaap" in text or "non gaap" in text else "company_defined"
    if source_type in {"sec_filing", "companyfacts"}:
        return "gaap"
    return "company_defined"


def validate_no_gaap_nongaap_conflation(metric_name: str, canonical_metrics) -> list[dict]:
    bases = {metric.basis for metric in canonical_metrics}
    if "gaap" in bases and "non_gaap" in bases and len(canonical_metrics) == 1:
        return [{
            "severity": "error",
            "code": "GAAP_NONGAAP_CONFLATION",
            "metric": metric_name,
            "message": f"{metric_name} has GAAP and non-GAAP evidence merged into one metric.",
        }]
    return []
