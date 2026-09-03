"""Additive Bank v2 shared-profile candidate preparation."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from research_agent.profile_authority.contracts import build_sector_profile_contract
from research_agent.profile_authority.integrity import canonical_sha256, with_self_hash

from .projection import FRESHNESS_POLICY, FORMULA_REGISTRY, MAPPING_REGISTRY, PERIOD_BASIS_POLICY
from .regulatory import REGULATORY_MAPPING_REGISTRY, REGULATORY_SOURCE_PROFILE


def _metrics() -> list[dict[str, Any]]:
    return [
        {
            "metric_id": metric_id,
            "ordered_concept_scope_rules": list(concepts),
            "comparability_grade": "A",
            "accepted_units": ["USD", "shares", "pure"],
            "accepted_period_bases": ["STANDALONE_QUARTER", "YEAR_TO_DATE", "INSTANT"],
            "source_lineage_required": True,
            "context_dimension_policy": "CONSOLIDATED_ONLY_FAIL_CLOSED",
        }
        for metric_id, concepts in sorted(MAPPING_REGISTRY["metrics"].items())
    ]


BANK_V2_PROFILE = build_sector_profile_contract(
    family="Bank",
    version=2,
    archetype="BANK",
    status="CANDIDATE",
    metrics=_metrics(),
    period_freshness={
        "policy": FRESHNESS_POLICY,
        "period_basis": PERIOD_BASIS_POLICY,
        "historical_behavior": "VISIBLE_NOT_COUNTED_AS_CURRENT",
    },
    candidate_integrity={
        "allowed_raw_candidate_contracts": ["room16.rfc0011.raw_fact_candidate_ir"],
        "hash_formula": "SHA256(CANONICAL_JSON(candidate_without_candidate_sha256))",
        "identity_formula": "candidate_id hash-bound",
        "required_lineage_hashes": ["source_artifact_sha256", "source_snapshot_sha256"],
    },
    runtime_authority={
        "full_contract_hash_authorization": True,
        "same_id_mutation_allowed": False,
        "frozen_profile_binding_required_if_frozen": True,
    },
)


def prepare_bank_v2_candidate(
    *, research_commit: str, research_tree: str, evidence_hashes: Sequence[str]
) -> dict[str, Any]:
    body = {
        "contract_id": "room16.bank_v2.candidate_preparation@1",
        "status": "BANK_V2_CANDIDATE_SEALED"
        if evidence_hashes
        else "BANK_V2_DEVELOPMENT_NOT_READY",
        "research_commit": research_commit,
        "research_tree": research_tree,
        "profile_contract_sha256": BANK_V2_PROFILE["profile_contract_sha256"],
        "mapping_registry_sha256": canonical_sha256(MAPPING_REGISTRY),
        "formula_registry_sha256": canonical_sha256(FORMULA_REGISTRY),
        "period_freshness_sha256": canonical_sha256(
            {"freshness": FRESHNESS_POLICY, "period": PERIOD_BASIS_POLICY}
        ),
        "regulatory_source_authority_sha256": canonical_sha256(REGULATORY_SOURCE_PROFILE),
        "regulatory_mapping_authority_sha256": canonical_sha256(REGULATORY_MAPPING_REGISTRY),
        "development_evidence_hashes": list(evidence_hashes),
        "provider_calls_on_untouched_cases": 0,
        "clean_validation_performed": False,
        "ticker_specific_rules": False,
    }
    field = "candidate_seal_sha256" if evidence_hashes else "preparation_sha256"
    return with_self_hash(body, field)


__all__ = ["BANK_V2_PROFILE", "prepare_bank_v2_candidate"]
