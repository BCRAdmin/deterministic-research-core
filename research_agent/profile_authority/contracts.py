"""Sector-neutral profile contract and selection receipt schema."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .integrity import SHA256_RE, canonical_sha256, validate_hashed_document, with_self_hash

CONTRACT_ID = "room16.sector_profile_contract@1"
RECEIPT_ID = "room16.sector_profile_selection_receipt@1"
ALLOWED_STATUS = {"CANDIDATE", "FROZEN", "HISTORICAL"}
ALLOWED_GRADES = {"A", "B", "C"}


def build_sector_profile_contract(
    *,
    family: str,
    version: int,
    archetype: str,
    status: str,
    metrics: Sequence[Mapping[str, Any]],
    period_freshness: Mapping[str, Any],
    candidate_integrity: Mapping[str, Any],
    runtime_authority: Mapping[str, Any],
) -> dict[str, Any]:
    body = {
        "contract_id": CONTRACT_ID,
        "contract_version": 1,
        "profile_identity": {
            "family": family,
            "version": version,
            "archetype": archetype,
            "status": status,
        },
        "metric_contracts": [dict(item) for item in metrics],
        "period_freshness_contract": dict(period_freshness),
        "candidate_integrity_contract": dict(candidate_integrity),
        "runtime_authority": dict(runtime_authority),
        "selection_receipt_contract": {
            "contract_id": RECEIPT_ID,
            "selected_candidate_hash_required": True,
            "source_lineage_required": True,
            "rejected_candidate_reasons_required": True,
            "receipt_self_hash_required": True,
        },
    }
    result = with_self_hash(body, "profile_contract_sha256")
    validate_sector_profile_contract(result)
    return result


def validate_sector_profile_contract(value: Mapping[str, Any]) -> str:
    if value.get("contract_id") != CONTRACT_ID or value.get("contract_version") != 1:
        raise ValueError("UNKNOWN_SECTOR_PROFILE_CONTRACT")
    identity = value.get("profile_identity")
    if not isinstance(identity, Mapping):
        raise ValueError("PROFILE_IDENTITY_MISSING")
    if not identity.get("family") or not isinstance(identity.get("version"), int):
        raise ValueError("PROFILE_IDENTITY_INVALID")
    if identity.get("status") not in ALLOWED_STATUS:
        raise ValueError("PROFILE_STATUS_INVALID")
    metrics = value.get("metric_contracts")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError("METRIC_CONTRACTS_MISSING")
    seen: set[str] = set()
    required = {
        "metric_id",
        "ordered_concept_scope_rules",
        "comparability_grade",
        "accepted_units",
        "accepted_period_bases",
        "source_lineage_required",
        "context_dimension_policy",
    }
    for metric in metrics:
        if not isinstance(metric, Mapping) or not required <= set(metric):
            raise ValueError("METRIC_CONTRACT_INVALID")
        metric_id = str(metric["metric_id"])
        if metric_id in seen:
            raise ValueError("DUPLICATE_METRIC_ID")
        seen.add(metric_id)
        if metric["comparability_grade"] not in ALLOWED_GRADES:
            raise ValueError("COMPARABILITY_GRADE_INVALID")
        if metric["source_lineage_required"] is not True:
            raise ValueError("SOURCE_LINEAGE_REQUIRED")
    integrity = value.get("candidate_integrity_contract")
    if not isinstance(integrity, Mapping) or not integrity.get("allowed_raw_candidate_contracts"):
        raise ValueError("CANDIDATE_INTEGRITY_INVALID")
    runtime = value.get("runtime_authority")
    if (
        not isinstance(runtime, Mapping)
        or runtime.get("full_contract_hash_authorization") is not True
    ):
        raise ValueError("FULL_CONTRACT_AUTHORITY_REQUIRED")
    return validate_hashed_document(value, hash_field="profile_contract_sha256")


def selection_receipt(
    *,
    profile: Mapping[str, Any],
    metric_id: str,
    status: str,
    selected_candidate: Mapping[str, Any] | None,
    rejected_candidates: Sequence[Mapping[str, Any]],
    period_basis: str | None,
    availability: str,
) -> dict[str, Any]:
    validate_sector_profile_contract(profile)
    metric = next(
        (item for item in profile["metric_contracts"] if item["metric_id"] == metric_id), None
    )
    if metric is None:
        raise ValueError("UNKNOWN_METRIC_ID")
    selected_hash = (
        None if selected_candidate is None else selected_candidate.get("candidate_sha256")
    )
    lineage = None if selected_candidate is None else selected_candidate.get("source_lineage")
    if selected_candidate is not None:
        if not isinstance(selected_hash, str) or not SHA256_RE.fullmatch(selected_hash):
            raise ValueError("SELECTED_CANDIDATE_HASH_INVALID")
        if not lineage:
            raise ValueError("SELECTED_CANDIDATE_LINEAGE_MISSING")
    body = {
        "contract_id": RECEIPT_ID,
        "contract_version": 1,
        "profile_family": profile["profile_identity"]["family"],
        "profile_version": profile["profile_identity"]["version"],
        "profile_contract_sha256": profile["profile_contract_sha256"],
        "metric_id": metric_id,
        "status": status,
        "counted": int(status == "SELECTED"),
        "selected_candidate_identity": None
        if selected_candidate is None
        else selected_candidate.get("candidate_id"),
        "selected_candidate_sha256": selected_hash,
        "source_lineage": lineage,
        "economic_scope_grade": metric["comparability_grade"],
        "context_scope_grade": selected_candidate.get("context_scope_grade")
        if selected_candidate
        else None,
        "period_basis": period_basis,
        "availability": availability,
        "rejected_candidates": [dict(item) for item in rejected_candidates],
    }
    return with_self_hash(body, "receipt_sha256")
