"""Additive REIT v2 candidate built on the shared sector-profile contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from research_agent.alpha_shared.core_slots import required_core_slots
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.profile_authority.contracts import build_sector_profile_contract
from research_agent.profile_authority.integrity import SHA256_RE, canonical_sha256, with_self_hash

from .primary_text import PRIMARY_TEXT_SOURCE_PROFILE
from .projection import FRESHNESS_POLICY, FORMULA_REGISTRY, MAPPING_REGISTRY

REIT_V2_METRIC_IDS = (
    "revenue",
    "net_income",
    "reported_ffo",
    "reported_core_ffo",
    "reported_affo",
    "operating_cash_flow",
    "total_debt",
)


def _metric(metric_id: str) -> dict[str, Any]:
    primary = metric_id.startswith("reported_")
    concepts = MAPPING_REGISTRY["metrics"].get(metric_id, [])
    return {
        "metric_id": metric_id,
        "ordered_concept_scope_rules": list(concepts)
        if concepts
        else ["EXPLICIT_PRIMARY_TEXT_AUTHORITY"],
        "comparability_grade": "A"
        if metric_id
        in {"revenue", "net_income", "operating_cash_flow", "total_debt", "reported_ffo"}
        else "C",
        "accepted_units": ["USD"],
        "accepted_period_bases": ["EXPLICIT_REPORTED_PERIOD"]
        if primary
        else ["STANDALONE_QUARTER", "YEAR_TO_DATE", "INSTANT"],
        "source_lineage_required": True,
        "context_dimension_policy": "CONSOLIDATED_ONLY_FAIL_CLOSED",
        "primary_text_required": primary,
    }


REIT_V2_PROFILE = build_sector_profile_contract(
    family="REIT",
    version=2,
    archetype="REIT",
    status="CANDIDATE",
    metrics=[_metric(metric_id) for metric_id in REIT_V2_METRIC_IDS],
    period_freshness={
        "current_max_age_days": FRESHNESS_POLICY["thresholds_days"],
        "aging_max_age_days": FRESHNESS_POLICY["thresholds_days"],
        "historical_behavior": "VISIBLE_NOT_COUNTED_AS_CURRENT",
        "synthesis_prohibitions": [
            "MISSING_PERIOD_YEAR",
            "QUARTER_FROM_YTD",
            "NON_GAAP_LABEL_SIMILARITY",
        ],
    },
    candidate_integrity={
        "allowed_raw_candidate_contracts": [
            "room16.rfc0011.raw_fact_candidate_ir",
            "room16.reit.v2.primary_text_candidate@1",
        ],
        "hash_formula": "SHA256(CANONICAL_JSON(candidate_without_candidate_sha256))",
        "identity_formula": "candidate_id binds full candidate_sha256",
        "required_lineage_hashes": ["source_artifact_sha256", "source_snapshot_sha256"],
    },
    runtime_authority={
        "full_contract_hash_authorization": True,
        "same_id_mutation_allowed": False,
        "frozen_profile_binding_required_if_frozen": True,
    },
)

REIT_V2_DESCRIPTOR_HASH = REIT_V2_PROFILE["profile_contract_sha256"]
REIT_V2_SOURCE_HASHES = {
    "mapping_registry_sha256": sha256_json(MAPPING_REGISTRY),
    "formula_registry_sha256": sha256_json(FORMULA_REGISTRY),
    "freshness_policy_sha256": sha256_json(FRESHNESS_POLICY),
    "primary_text_source_profile_sha256": sha256_json(PRIMARY_TEXT_SOURCE_PROFILE),
    "core_slot_policy_sha256": sha256_json(
        [item.model_dump(mode="json") for item in required_core_slots("reit", REIT_V2_METRIC_IDS)]
    ),
}

ACCEPTANCE_THRESHOLDS_V2 = {
    "contract_id": "room16.alpha.fixed_batch_acceptance_thresholds@2",
    "minimum_company_core_coverage_percent": 60,
    "minimum_archetype_median_core_coverage_percent": 80,
    "minimum_section_completeness_percent": 90,
    "required_surfaced_fact_lineage_percent": 100,
    "maximum_stale_primary_metric_count": 0,
    "required_replay_identity_percent": 100,
    "maximum_replay_provider_calls": 0,
    "maximum_P0": 0,
    "maximum_P1": 0,
    "maximum_manual_semantic_interventions": 0,
    "maximum_ticker_specific_semantic_patches": 0,
    "no_waiver": True,
}
ACCEPTANCE_THRESHOLDS_V2_SHA256 = canonical_sha256(ACCEPTANCE_THRESHOLDS_V2)


def validate_raw_candidate(candidate: Mapping[str, Any]) -> str:
    allowed = REIT_V2_PROFILE["candidate_integrity_contract"]["allowed_raw_candidate_contracts"]
    if candidate.get("contract_id") not in allowed:
        raise ValueError("REIT_V2_UNKNOWN_RAW_CANDIDATE_CONTRACT")
    supplied = candidate.get("candidate_sha256")
    if not isinstance(supplied, str) or not SHA256_RE.fullmatch(supplied):
        raise ValueError("REIT_V2_CANDIDATE_HASH_INVALID")
    if (
        canonical_sha256(
            {key: value for key, value in candidate.items() if key != "candidate_sha256"}
        )
        != supplied
    ):
        raise ValueError("REIT_V2_CANDIDATE_HASH_MISMATCH")
    if str(candidate.get("candidate_id", "")).split(".")[-1] != supplied:
        raise ValueError("REIT_V2_CANDIDATE_ID_MISMATCH")
    lineage = candidate.get("source_lineage")
    if not isinstance(lineage, Mapping):
        raise ValueError("REIT_V2_LINEAGE_MISSING")
    for field in REIT_V2_PROFILE["candidate_integrity_contract"]["required_lineage_hashes"]:
        if not SHA256_RE.fullmatch(str(lineage.get(field, ""))):
            raise ValueError(f"REIT_V2_LINEAGE_HASH_MISSING:{field}")
    return supplied


def seal_reit_v2_candidate(
    *,
    research_commit: str,
    research_tree: str,
    development_evidence_hashes: Sequence[str],
    full_tests_sha256: str,
) -> dict[str, Any]:
    body = {
        "contract_id": "room16.reit_v2.candidate_seal@1",
        "profile_family": "REIT",
        "profile_version": 2,
        "research_commit": research_commit,
        "research_tree": research_tree,
        "shared_profile_contract_sha256": REIT_V2_DESCRIPTOR_HASH,
        **REIT_V2_SOURCE_HASHES,
        "acceptance_threshold_sha256": ACCEPTANCE_THRESHOLDS_V2_SHA256,
        "development_evidence_hashes": list(development_evidence_hashes),
        "full_tests_sha256": full_tests_sha256,
        "semantic_changes_after_seal": 0,
        "formula_changes_after_seal": 0,
        "threshold_changes_after_seal": 0,
        "profile_changes_after_seal": 0,
    }
    return with_self_hash(body, "candidate_seal_sha256")


def guard_reit_validation_action(action: Mapping[str, Any]) -> None:
    """Fail closed on selection/validation actions that violate the sealed protocol."""
    if action.get("exposed_identity"):
        raise ValueError("REIT_EXPOSED_IDENTITY_BLOCKED")
    if action.get("result_fields_used_for_selection"):
        raise ValueError("REIT_RESULT_BASED_SELECTION_BLOCKED")
    if int(action.get("provider_calls_before_selection_seal", 0)):
        raise ValueError("REIT_PROVIDER_CALL_BEFORE_SELECTION_SEAL_BLOCKED")
    if action.get("replacement_authorized"):
        raise ValueError("REIT_REPLACEMENT_BLOCKED")
    if int(action.get("case_count", 12)) != 12:
        raise ValueError("REIT_BATCH_CARDINALITY_BLOCKED")
    for field in (
        "semantic_changes_after_seal",
        "formula_changes_after_seal",
        "threshold_changes_after_seal",
        "profile_changes_after_seal",
    ):
        if int(action.get(field, 0)):
            raise ValueError(f"REIT_POST_SEAL_MUTATION_BLOCKED:{field}")
    if action.get("primary_text_without_lineage"):
        raise ValueError("REIT_PRIMARY_TEXT_LINEAGE_BLOCKED")
    if action.get("unsupported_non_gaap_label"):
        raise ValueError("REIT_NON_GAAP_LABEL_AUTHORITY_BLOCKED")
    if action.get("period_mismatch"):
        raise ValueError("REIT_PERIOD_MISMATCH_BLOCKED")
    if int(action.get("stale_primary_metric_count", 0)):
        raise ValueError("REIT_STALE_PRIMARY_BLOCKED")
    if int(action.get("manual_semantic_interventions", 0)):
        raise ValueError("REIT_MANUAL_SEMANTIC_INTERVENTION_BLOCKED")
    if int(action.get("ticker_specific_semantic_patches", 0)):
        raise ValueError("REIT_TICKER_SPECIFIC_RULE_BLOCKED")
    if action.get("historical_only_counted_as_current"):
        raise ValueError("REIT_HISTORICAL_AS_CURRENT_BLOCKED")
    if action.get("product_mutation"):
        raise ValueError("REIT_PRODUCT_MUTATION_BLOCKED")
    if action.get("claim_reit_frozen"):
        raise ValueError("REIT_PREMATURE_FREEZE_CLAIM_BLOCKED")
