from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict

from research_agent.calibration.outcome_quality import (
    CalibrationStabilityReview,
    calculate_stability_review_sha256,
)
from research_agent.calibration.valuation_calibration import ValuationCalibrationReadiness


CONTRACT_ID = "room16.p6_human_promotion_gate@1"
_HUMAN_BLOCKLIST = re.compile(
    r"^(?:ai|agent|automation|bot|chatgpt|claude|codex|deepseek|gemini|llm|"
    r"model|openai|room\s*16|system|vega|vivi)(?:\b|[-_])",
    re.IGNORECASE,
)


class P6HumanPromotionGate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    contract_id: Literal["room16.p6_human_promotion_gate@1"] = CONTRACT_ID
    status: Literal["blocked", "human_gate_complete_manual_install_required"]
    readiness_sha256: str
    stability_review_sha256: str
    methodology_review_evidence_sha256: Optional[str]
    independent_methodology_reviewer: Optional[str]
    operator_signoff_evidence_sha256: Optional[str]
    operator_identity: Optional[str]
    operator_decision: Optional[Literal["approve_manual_shadow_promotion_review"]]
    blockers: list[str]
    automatic_actions: dict[str, Literal[False]]
    live_activation_allowed: Literal[False] = False
    manual_code_promotion_required: Literal[True] = True
    gate_sha256: str


def build_p6_human_promotion_gate(
    readiness: ValuationCalibrationReadiness,
    stability: CalibrationStabilityReview,
    *,
    methodology_review_evidence_sha256: Optional[str] = None,
    independent_methodology_reviewer: Optional[str] = None,
    operator_signoff_evidence_sha256: Optional[str] = None,
    operator_identity: Optional[str] = None,
    operator_decision: Optional[str] = None,
) -> P6HumanPromotionGate:
    blockers: list[str] = []
    readiness_hash = _model_sha256(readiness)
    if readiness.status != "shadow_ready":
        blockers.append("valuation_calibration_not_shadow_ready")
    if readiness.live_activation_allowed is not False:
        blockers.append("readiness_auto_activation_contract_invalid")
    if stability.status != "human_review_required" or stability.blockers:
        blockers.append("stability_review_not_ready")
    if not _is_sha256(stability.report_sha256) or (
        stability.report_sha256 != calculate_stability_review_sha256(stability)
    ):
        blockers.append("stability_review_hash_invalid")
    if not _is_sha256(methodology_review_evidence_sha256):
        blockers.append("independent_methodology_review_evidence_missing")
    if not _is_human_identity(independent_methodology_reviewer):
        blockers.append("independent_methodology_reviewer_invalid")
    if not _is_sha256(operator_signoff_evidence_sha256):
        blockers.append("operator_signoff_evidence_missing")
    if not _is_human_identity(operator_identity):
        blockers.append("operator_identity_invalid")
    if _same_identity(independent_methodology_reviewer, operator_identity):
        blockers.append("operator_must_differ_from_methodology_reviewer")
    if operator_decision != "approve_manual_shadow_promotion_review":
        blockers.append("operator_decision_missing_or_invalid")
    blockers = sorted(set(blockers))
    payload: dict[str, Any] = {
        "contract_id": CONTRACT_ID,
        "status": "blocked" if blockers else "human_gate_complete_manual_install_required",
        "readiness_sha256": readiness_hash,
        "stability_review_sha256": stability.report_sha256,
        "methodology_review_evidence_sha256": methodology_review_evidence_sha256,
        "independent_methodology_reviewer": independent_methodology_reviewer,
        "operator_signoff_evidence_sha256": operator_signoff_evidence_sha256,
        "operator_identity": operator_identity,
        "operator_decision": (
            operator_decision
            if operator_decision == "approve_manual_shadow_promotion_review"
            else None
        ),
        "blockers": blockers,
        "automatic_actions": {
            "ratingChange": False,
            "weightChange": False,
            "methodChange": False,
            "configurationWrite": False,
            "gitWrite": False,
            "publicClaim": False,
        },
        "live_activation_allowed": False,
        "manual_code_promotion_required": True,
    }
    payload["gate_sha256"] = _payload_sha256(payload)
    return P6HumanPromotionGate.model_validate(payload)


def _model_sha256(model: BaseModel) -> str:
    return _payload_sha256(model.model_dump(mode="json"))


def _payload_sha256(payload: dict[str, Any]) -> str:
    normalized = {key: value for key, value in payload.items() if key != "gate_sha256"}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_sha256(value: Optional[str]) -> bool:
    normalized = str(value or "").removeprefix("sha256:")
    return len(normalized) == 64 and all(character in "0123456789abcdef" for character in normalized)


def _is_human_identity(value: Optional[str]) -> bool:
    identity = str(value or "").strip()
    return bool(identity) and _HUMAN_BLOCKLIST.search(identity) is None


def _same_identity(left: Optional[str], right: Optional[str]) -> bool:
    def normalize(value: Optional[str]) -> str:
        decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
        return re.sub(r"[^a-z0-9]+", "", decomposed.encode("ascii", "ignore").decode())

    left_value = normalize(left)
    return bool(left_value and left_value == normalize(right))
