from __future__ import annotations

import json
from pathlib import Path
from typing import Union

from research_agent.batch.batch_manifest import BatchManifest
from research_agent.batch.display_policy import external_rating_payload


def build_dashboard_status(manifest: BatchManifest) -> dict:
    quality_scores = [item.quality_score for item in manifest.items if item.quality_score is not None]
    publish_quality_scores = _score_values(manifest, "publish_quality_score", fallback_to_legacy=True)
    internal_quality_scores = _score_values(manifest, "internal_research_quality_score")
    data_confidence_scores = _score_values(manifest, "data_confidence_score")
    counts = _aggregate_counts(manifest)
    summary = {
        "total": len(manifest.items),
        "batch_mode": getattr(manifest, "batch_mode", "current_research"),
        "pending": _count(manifest, "pending"),
        "running": _count(manifest, "running"),
        "passed": _count(manifest, "passed"),
        "repaired": _count(manifest, "repaired"),
        "manual_review": _count(manifest, "manual_review"),
        "data_unavailable": _count(manifest, "data_unavailable"),
        "failed": _count(manifest, "failed"),
        "avg_quality_score": (sum(quality_scores) / len(quality_scores)) if quality_scores else None,
        "avg_publish_quality_score": _avg(publish_quality_scores),
        "avg_internal_research_quality_score": _avg(internal_quality_scores),
        "avg_data_confidence_score": _avg(data_confidence_scores),
        "stale_price_basis_count": sum(1 for item in manifest.items if getattr(item, "stale_price_basis", False)),
        "current_report_allowed_count": sum(1 for item in manifest.items if getattr(item, "current_report_allowed", None) is True),
        "historical_qa_only_count": sum(1 for item in manifest.items if getattr(item, "historical_qa_only", False)),
        "speculative_deep_tech_profile_count": counts.get("speculative_deep_tech_profile_count", 0),
        "early_commercial_capital_intensive_tech_count": counts.get("early_commercial_capital_intensive_tech_count", 0),
        "accounting_gain_not_operating_turnaround_count": counts.get("accounting_gain_not_operating_turnaround_count", 0),
        "vendor_only_hard_metrics_count": counts.get("vendor_only_hard_metrics_count", 0),
        "order_materiality_missing_count": counts.get("order_materiality_missing_count", 0),
        "technical_overweight_in_thesis_count": counts.get("technical_overweight_in_thesis_count", 0),
    }
    return {
        "batch_id": manifest.batch_id,
        "as_of_date": manifest.as_of_date,
        "batch_mode": getattr(manifest, "batch_mode", "current_research"),
        "status": manifest.status,
        "started_at": manifest.started_at,
        "finished_at": manifest.finished_at,
        "summary": summary,
        "items": [_dashboard_item(item) for item in manifest.items],
        "manual_review_queue": [
            _dashboard_item(item)
            for item in manifest.items
            if item.status == "manual_review"
        ],
        "failure_groups": _failure_groups(manifest),
        "counts": counts,
    }


def save_dashboard_status(status: dict, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(status, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _count(manifest: BatchManifest, status: str) -> int:
    return sum(1 for item in manifest.items if item.status == status)


def _dashboard_item(item) -> dict:
    rating_payload = external_rating_payload(item)
    counts = item.counts or {}
    publish_quality_score = _score_value(item, "publish_quality_score", fallback_to_legacy=True)
    internal_research_quality_score = _score_value(item, "internal_research_quality_score")
    data_confidence_score = _score_value(item, "data_confidence_score")
    return {
        "ticker": item.ticker,
        "status": item.status,
        "display_status": rating_payload["display_status"],
        "output_path": item.output_path,
        "quality_score": item.quality_score,
        "price_basis_date": item.price_basis_date,
        "data_freshness_status": item.data_freshness_status,
        "stale_price_basis": item.stale_price_basis,
        "current_report_allowed": item.current_report_allowed,
        "historical_qa_only": item.historical_qa_only,
        "minimum_viable_report_possible": item.minimum_viable_report_possible,
        "current_report_possible": item.current_report_possible,
        "missing_minimum_inputs": item.missing_minimum_inputs,
        "publish_quality_score": publish_quality_score,
        "internal_research_quality_score": internal_research_quality_score,
        "data_confidence_score": data_confidence_score,
        "total_score_legacy": item.quality_score,
        "score_explanation_short": _score_explanation(item),
        "final_rating": rating_payload["external_final_rating"],
        "preferred_rating": rating_payload["external_preferred_rating"],
        "display_rating": rating_payload["display_rating"],
        "display_action": rating_payload["display_action"],
        "external_display_rating": rating_payload["display_rating"],
        "external_display_action": rating_payload["display_action"],
        "rating_display_reason": rating_payload["display_reason"],
        "company_archetype": _quality_value(item, "company_archetype", "UNKNOWN"),
        "archetype_confidence": _quality_value(item, "archetype_confidence", 0),
        "archetype_triggered_rules": _quality_value(item, "archetype_triggered_rules", []),
        "internal_final_rating": rating_payload["internal_final_rating"],
        "internal_preferred_rating": rating_payload["internal_preferred_rating"],
        "publishable": item.publishable,
        "error_message": item.error_message,
        "failure_type": item.failure_type,
        "manual_review_reasons": _manual_review_reasons(item),
        "evidence_warnings": counts.get("evidence_warnings", 0),
        "evidence_warning_codes": _evidence_warning_codes(item),
        "reconciliation_warnings": counts.get("reconciliation_warnings", 0),
        "reconciliation_warning_codes": _reconciliation_warning_codes(item),
        "true_source_disagreements": counts.get("true_source_disagreements", 0),
        "current_period_kpi_claim_count": counts.get("current_period_kpi_claim_count", 0),
        "current_period_kpi_metric_count": counts.get("current_period_kpi_metric_count", 0),
        "claim_coverage_complete": bool(counts.get("claim_coverage_complete", 0)),
        "ticker_specific_kpi_claim_count": counts.get("ticker_specific_kpi_claim_count", 0),
        "risk_specific_claim_count": counts.get("risk_specific_claim_count", 0),
        "substantive_claim_count": counts.get("substantive_claim_count", 0),
        "mechanical_rating_language_count": counts.get("mechanical_rating_language_count", 0),
        "valuation_sensitivity_present": bool(counts.get("publish_valuation_sensitivity_present", 0)),
        "action_plan_trigger_count": counts.get("publish_action_plan_trigger_count", 0),
        "counts": counts,
        "artifacts": item.artifacts,
    }


def _failure_groups(manifest: BatchManifest) -> dict[str, int]:
    groups: dict[str, int] = {}
    for item in manifest.items:
        if item.failure_type:
            groups[item.failure_type] = groups.get(item.failure_type, 0) + 1
    return groups


def _aggregate_counts(manifest: BatchManifest) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in manifest.items:
        for key, value in (item.counts or {}).items():
            totals[key] = totals.get(key, 0) + int(value or 0)
    return totals


def _score_values(manifest: BatchManifest, key: str, fallback_to_legacy: bool = False) -> list[float]:
    values: list[float] = []
    for item in manifest.items:
        value = _score_value(item, key, fallback_to_legacy=fallback_to_legacy)
        if value is not None:
            values.append(float(value))
    return values


def _score_value(item, key: str, fallback_to_legacy: bool = False):
    counts = item.counts or {}
    if key in counts:
        return counts[key]
    value = _quality_value(item, key, None)
    if value is not None:
        return value
    if fallback_to_legacy and item.quality_score is not None:
        return item.quality_score
    return None


def _avg(values: list[float]) -> float | None:
    return (sum(values) / len(values)) if values else None


def _score_explanation(item) -> str:
    value = _quality_value(item, "score_explanation_short", None)
    if value:
        return str(value)
    if getattr(item, "status", None) == "manual_review":
        return "Manual-review item; score split unavailable, legacy quality score remains for compatibility."
    if getattr(item, "publishable", None):
        return "Publishable item; score split unavailable, legacy quality score remains for compatibility."
    return "Score split unavailable; legacy quality score remains for compatibility."


def _manual_review_reasons(item) -> list[str]:
    if getattr(item, "status", None) != "manual_review":
        return []

    codes = []
    codes.extend(_issue_codes(item, "audit_report.json"))
    codes.extend(_issue_codes(item, "validation_report.json"))
    codes.extend(_reconciliation_warning_codes(item))
    codes.extend(_evidence_warning_codes(item))
    if getattr(item, "failure_type", None):
        codes.append(str(item.failure_type))
    return list(dict.fromkeys(code for code in codes if code))


def _quality_value(item, key: str, default):
    path = _artifact_path(item, "quality_score.json")
    if path is None:
        return default
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return payload.get(key, default)


def _issue_codes(item, artifact_name: str) -> list[str]:
    path = _artifact_path(item, artifact_name)
    if path is None:
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [
        str(issue.get("code"))
        for issue in payload.get("issues", [])
        if issue.get("code")
    ]


def _reconciliation_warning_codes(item) -> list[str]:
    path = _artifact_path(item, "reconciliation_warnings.json")
    if path is None:
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [
        str(warning.get("code"))
        for warning in payload
        if warning.get("code")
    ]


def _evidence_warning_codes(item) -> list[str]:
    path = _artifact_path(item, "evidence_report.md")
    if path is None:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    codes = []
    for code in {
        "MISSING_EVIDENCE_FOR_METRIC",
        "NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC",
        "VENDOR_SOURCE_USED_AS_PRIMARY",
        "MISSING_DATE_FOR_NEWS_EVENT",
        "GUIDANCE_CONSENSUS_CONFLATION",
    }:
        if code in text:
            codes.append(code)
    return codes


def _artifact_path(item, artifact_name: str) -> Path | None:
    artifact = (getattr(item, "artifacts", None) or {}).get(artifact_name)
    if not artifact:
        return None
    path = Path(artifact)
    if not path.exists():
        return None
    return path
