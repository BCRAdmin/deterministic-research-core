from __future__ import annotations

from typing import Iterable

from research_agent.batch.batch_manifest import BatchRunItem

PENDING = "pending"
RUNNING = "running"
PASSED = "passed"
REPAIRED = "repaired"
MANUAL_REVIEW = "manual_review"
DATA_UNAVAILABLE = "data_unavailable"
FAILED = "failed"

COMPLETED = "completed"
COMPLETED_WITH_ISSUES = "completed_with_issues"

TERMINAL_ITEM_STATUSES = {PASSED, REPAIRED, MANUAL_REVIEW, DATA_UNAVAILABLE, FAILED}


def status_from_result(result) -> str:
    if _get_bool(result, "manual_review_required") or _get_value(result, "final_status") == MANUAL_REVIEW:
        return MANUAL_REVIEW
    if _get_bool(result, "repaired") or _get_value(result, "final_status") == "repaired_publishable":
        return REPAIRED
    if _get_bool(result, "publishable") or _quality_publishable(result):
        return PASSED
    if _get_value(result, "final_status") == "publishable":
        return PASSED
    return FAILED


def final_batch_status(items: Iterable[BatchRunItem]) -> str:
    items = list(items)
    if any(item.status in {PENDING, RUNNING} for item in items):
        return RUNNING
    if not items or all(item.status == FAILED for item in items):
        return FAILED
    if any(item.status in {FAILED, MANUAL_REVIEW, DATA_UNAVAILABLE} for item in items):
        return COMPLETED_WITH_ISSUES
    return COMPLETED


def _get_bool(obj, name: str) -> bool:
    value = _get_value(obj, name)
    return bool(value)


def _quality_publishable(result) -> bool:
    quality = _get_value(result, "quality_score") or _get_value(result, "quality_report")
    if quality is None:
        return False
    return bool(_get_value(quality, "publishable"))


def _get_value(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
