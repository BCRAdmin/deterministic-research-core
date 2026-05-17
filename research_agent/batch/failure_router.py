from __future__ import annotations


def classify_failure(error_message: str) -> str:
    msg = (error_message or "").lower()

    if any(token in msg for token in ["missing price", "data packet", "no data", "data_error"]):
        return "data_error"
    if "validation" in msg or "ttm_sum_mismatch" in msg or "margin_mismatch" in msg:
        return "validation_error"
    if "audit" in msg or "numeric_mismatch" in msg or "period_mismatch" in msg:
        return "audit_error"
    if "repair" in msg:
        return "repair_failed"
    if "decision" in msg or "blocked rating" in msg or "rating permission" in msg:
        return "decision_blocked"
    if "source" in msg or "sec" in msg or "edgar" in msg or "companyfacts" in msg:
        return "source_ingestion_error"
    if "llm" in msg or "model" in msg or "token" in msg:
        return "llm_error"

    return "unknown_error"
