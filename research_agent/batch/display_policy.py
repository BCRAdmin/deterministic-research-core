from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FCF_SUPPORT_FOR_ACCUMULATE_CODE = "MISSING_FCF_SUPPORT_FOR_ACCUMULATE"
SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE = "SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE"
EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE = "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE"
MANUAL_REVIEW_PRELIMINARY_UNDERWEIGHT = "Manual Review / Preliminary Underweight"
MANUAL_REVIEW_HOLD_PENDING_FCF_EXECUTION = "Manual Review / Hold Pending FCF and Execution Evidence"
HOLD_PENDING_FCF_SUPPORT = "Hold Pending FCF Support"
ACCUMULATE_AFTER_FCF_SUPPORT = "Accumulate only after FCF support"
HOLD_WITH_UNDERWEIGHT_BIAS = "Hold with Underweight Bias"


def audit_issue_codes_for_item(item: Any) -> list[str]:
    """Return audit issue codes for a batch item without making display code fragile."""
    audit_path = (getattr(item, "artifacts", None) or {}).get("audit_report.json")
    if not audit_path:
        return []

    path = Path(audit_path)
    if not path.exists():
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


def needs_fcf_support_accumulate_display_override(item: Any) -> bool:
    if getattr(item, "status", None) != "manual_review":
        return False
    return FCF_SUPPORT_FOR_ACCUMULATE_CODE in audit_issue_codes_for_item(item)


def needs_hold_underweight_bias_display_override(item: Any) -> bool:
    if getattr(item, "status", None) not in {"passed", "repaired"}:
        return False

    internal_final = (getattr(item, "final_rating", None) or "").strip()
    internal_preferred = (getattr(item, "preferred_rating", None) or internal_final).strip()
    if internal_final != "Hold" and internal_preferred != "Hold":
        return False

    publish_path = (getattr(item, "artifacts", None) or {}).get("publish_report.md")
    if not publish_path:
        return False

    path = Path(publish_path)
    if not path.exists():
        return False

    try:
        text = path.read_text(encoding="utf-8").lower()
    except OSError:
        return False

    return "hold with underweight bias" in text or "underweight bias" in text


def needs_speculative_deeptech_display_override(item: Any) -> bool:
    if getattr(item, "status", None) != "manual_review":
        return False
    return SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE in audit_issue_codes_for_item(item) or (getattr(item, "counts", {}) or {}).get("speculative_deep_tech_profile_count", 0) > 0


def needs_early_commercial_capital_intensive_display_override(item: Any) -> bool:
    if getattr(item, "status", None) != "manual_review":
        return False
    return (
        EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE in audit_issue_codes_for_item(item)
        or (getattr(item, "counts", {}) or {}).get("early_commercial_capital_intensive_tech_count", 0) > 0
    )


def external_rating_payload(item: Any) -> dict[str, str | None]:
    """Map internal ratings to safe external display language.

    Internal DecisionPackets may still preserve the original preferred rating. The
    external surface must not show plain Accumulate when the report is blocked
    specifically because FCF support for that Accumulate is missing.
    """
    internal_final = getattr(item, "final_rating", None)
    internal_preferred = getattr(item, "preferred_rating", None)
    display_status = _external_status_label(getattr(item, "status", None))

    if needs_early_commercial_capital_intensive_display_override(item):
        return {
            "display_status": "Manual Review",
            "display_rating": MANUAL_REVIEW_HOLD_PENDING_FCF_EXECUTION,
            "display_action": "Hold pending FCF path and execution evidence",
            "display_reason": EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE,
            "external_final_rating": MANUAL_REVIEW_HOLD_PENDING_FCF_EXECUTION,
            "external_preferred_rating": MANUAL_REVIEW_HOLD_PENDING_FCF_EXECUTION,
            "internal_final_rating": internal_final,
            "internal_preferred_rating": internal_preferred,
        }

    if needs_speculative_deeptech_display_override(item):
        return {
            "display_status": "Manual Review",
            "display_rating": MANUAL_REVIEW_PRELIMINARY_UNDERWEIGHT,
            "display_action": "Underweight only as preliminary manual-review view",
            "display_reason": SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE,
            "external_final_rating": MANUAL_REVIEW_PRELIMINARY_UNDERWEIGHT,
            "external_preferred_rating": MANUAL_REVIEW_PRELIMINARY_UNDERWEIGHT,
            "internal_final_rating": internal_final,
            "internal_preferred_rating": internal_preferred,
        }

    if needs_fcf_support_accumulate_display_override(item):
        return {
            "display_status": "Manual Review",
            "display_rating": HOLD_PENDING_FCF_SUPPORT,
            "display_action": ACCUMULATE_AFTER_FCF_SUPPORT,
            "display_reason": FCF_SUPPORT_FOR_ACCUMULATE_CODE,
            "external_final_rating": HOLD_PENDING_FCF_SUPPORT,
            "external_preferred_rating": HOLD_PENDING_FCF_SUPPORT,
            "internal_final_rating": internal_final,
            "internal_preferred_rating": internal_preferred,
        }

    if needs_hold_underweight_bias_display_override(item):
        return {
            "display_status": display_status,
            "display_rating": HOLD_WITH_UNDERWEIGHT_BIAS,
            "display_action": None,
            "display_reason": "UNDERWEIGHT_BIAS",
            "external_final_rating": HOLD_WITH_UNDERWEIGHT_BIAS,
            "external_preferred_rating": HOLD_WITH_UNDERWEIGHT_BIAS,
            "internal_final_rating": internal_final,
            "internal_preferred_rating": internal_preferred,
        }

    display_rating = internal_preferred or internal_final
    return {
        "display_status": display_status,
        "display_rating": display_rating,
        "display_action": None,
        "display_reason": None,
        "external_final_rating": internal_final,
        "external_preferred_rating": internal_preferred,
        "internal_final_rating": internal_final,
        "internal_preferred_rating": internal_preferred,
    }


def external_rating_label(item: Any) -> str:
    payload = external_rating_payload(item)
    return str(payload.get("display_rating") or "")


def external_action_label(item: Any) -> str:
    payload = external_rating_payload(item)
    return str(payload.get("display_action") or "")


def _external_status_label(status: Any) -> str | None:
    if status is None:
        return None
    label = str(status)
    mapping = {
        "manual_review": "Manual Review",
        "data_unavailable": "Data unavailable",
        "passed": "Passed",
        "repaired": "Repaired",
        "failed": "Failed",
        "running": "Running",
        "pending": "Pending",
    }
    return mapping.get(label, label)
