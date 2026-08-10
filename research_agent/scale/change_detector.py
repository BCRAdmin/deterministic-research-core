from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CONTRACT_ID = "room16.authority_change_review"
_SEMANTIC_KEYS = (
    "contract_id",
    "contract_version",
    "ticker",
    "as_of_date",
    "pipeline_version",
    "analysis_allowed",
    "blocking_failures",
    "rating_permission",
    "artifacts",
)


class ChangeDetectorError(RuntimeError):
    """Raised when supplied authority manifests are not comparable."""


def detect_authority_changes(previous: Any, current: Any) -> dict[str, Any]:
    before = _load_manifest(previous)
    after = _load_manifest(current)
    for label, manifest in (("previous", before), ("current", after)):
        if manifest.get("contract_id") != "room16.research_authority_bundle":
            raise ChangeDetectorError(f"{label}_authority_contract_invalid")
        if not manifest.get("ticker") or not manifest.get("as_of_date"):
            raise ChangeDetectorError(f"{label}_authority_identity_invalid")
    if before["ticker"] != after["ticker"]:
        raise ChangeDetectorError("authority_ticker_mismatch")
    changes = []
    for key in _SEMANTIC_KEYS:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            changes.append(
                {
                    "field": key,
                    "previousSha256": _value_sha256(old),
                    "currentSha256": _value_sha256(new),
                }
            )
    review_required = bool(changes)
    return {
        "contractId": CONTRACT_ID,
        "contractVersion": 1,
        "ticker": after["ticker"],
        "previousAsOfDate": before["as_of_date"],
        "currentAsOfDate": after["as_of_date"],
        "reviewRequired": review_required,
        "reviewTask": (
            {
                "type": "human_authority_change_review",
                "changedFields": [item["field"] for item in changes],
                "reason": "Ein deterministischer Authority-Bestand hat sich geändert.",
            }
            if review_required
            else None
        ),
        "changes": changes,
        "automaticActions": {
            "analysisRun": False,
            "modelRun": False,
            "reportGeneration": False,
            "reportPublish": False,
            "codexTask": False,
            "gitWrite": False,
        },
    }


def _load_manifest(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    path = Path(value).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ChangeDetectorError("authority_manifest_unreadable") from exc
    if not isinstance(payload, dict):
        raise ChangeDetectorError("authority_manifest_shape_invalid")
    return payload


def _value_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
