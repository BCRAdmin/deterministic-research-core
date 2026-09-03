"""Canonical external freeze authority and shadow adapter for Energy v3."""

from __future__ import annotations

from typing import Any

from research_agent.alpha_energy.v3 import (
    CANDIDATE_INTEGRITY_CONTRACT_V3,
    CAPEX_COMPARABILITY_CONTRACT_V3,
    CORE_SLOT_REGISTRY_V3,
    DEBT_COMPARABILITY_CONTRACT_V3,
    ENERGY_SEMANTIC_CONTRACT_V3,
    PERIOD_FRESHNESS_POLICY_V3,
    REVENUE_COMPARABILITY_CONTRACT_V3,
    select_metric_v3,
)
from research_agent.compiler_foundation.canonical import sha256_json

from .freeze_registry import FrozenProfileRegistry, build_freeze_authority, guard_frozen_profile

R13_RESEARCH_COMMIT = "47d4f93d9863b014422ca0e73748aa6a7d5353f1"
R13_RESEARCH_TREE = "51234d00690b23e2fd29a34551b8403c3da90352"
R12_CANDIDATE_SEAL_SHA256 = "cc5ed70dfa0c0b84943f64671d2ff92f8c671a0b8d3a23cd48f71902c52db7d3"
R12_CANDIDATE_SEMANTIC_SHA256 = "888dac95b998ec7d093bdccd781f1f0a7bf9166dd91450da61f92b8684a7da7d"
R13_COMPACT_SHA256 = "c972d851c69b615086bfdb8a90ea5f0814856dd907e23fa5932d68d06598bc6c"
R13_MANIFEST_SHA256 = "78bfd22626ec00d2ea43fe89f57afe5a43077527165ab55985e66b54e7d5bb9d"
INDEPENDENT_DECISION_SHA256 = "2f2c9a8ede99f195e9484ea3b58eae11ea3b507f6318e8704a5dbf607c82e045"

ENERGY_V3_BINDINGS = {
    "semantic_contract_sha256": sha256_json(ENERGY_SEMANTIC_CONTRACT_V3),
    "period_policy_sha256": sha256_json(PERIOD_FRESHNESS_POLICY_V3),
    "core_slot_registry_sha256": sha256_json(CORE_SLOT_REGISTRY_V3),
    "revenue_contract_sha256": sha256_json(REVENUE_COMPARABILITY_CONTRACT_V3),
    "capex_contract_sha256": sha256_json(CAPEX_COMPARABILITY_CONTRACT_V3),
    "debt_contract_sha256": sha256_json(DEBT_COMPARABILITY_CONTRACT_V3),
    "candidate_integrity_contract_sha256": sha256_json(CANDIDATE_INTEGRITY_CONTRACT_V3),
}

ENERGY_V3_FREEZE_AUTHORITY = build_freeze_authority(
    profile_family="Energy",
    profile_version=3,
    research_commit=R13_RESEARCH_COMMIT,
    research_tree=R13_RESEARCH_TREE,
    r12_candidate_seal_sha256=R12_CANDIDATE_SEAL_SHA256,
    r12_candidate_semantic_sha256=R12_CANDIDATE_SEMANTIC_SHA256,
    **ENERGY_V3_BINDINGS,
    r13_compact_sha256=R13_COMPACT_SHA256,
    r13_manifest_sha256=R13_MANIFEST_SHA256,
    independent_freeze_decision_sha256=INDEPENDENT_DECISION_SHA256,
    freeze_effective_date="2026-09-03",
    immutable=True,
    semantic_mutation_requires_new_profile_version=True,
    threshold_mutation_requires_new_profile_version=True,
    product_cutover_authorized=False,
    release_authorized=False,
)


def energy_v3_registry() -> FrozenProfileRegistry:
    registry = FrozenProfileRegistry()
    registry.register(ENERGY_V3_FREEZE_AUTHORITY)
    return registry


def validate_energy_v3_freeze(authority: dict[str, Any] | None = None) -> str:
    return guard_frozen_profile(
        ENERGY_V3_FREEZE_AUTHORITY if authority is None else authority,
        expected_bindings={
            "research_commit": R13_RESEARCH_COMMIT,
            "research_tree": R13_RESEARCH_TREE,
            "r12_candidate_seal_sha256": R12_CANDIDATE_SEAL_SHA256,
            "r12_candidate_semantic_sha256": R12_CANDIDATE_SEMANTIC_SHA256,
            "r13_compact_sha256": R13_COMPACT_SHA256,
            "r13_manifest_sha256": R13_MANIFEST_SHA256,
            "independent_freeze_decision_sha256": INDEPENDENT_DECISION_SHA256,
            **ENERGY_V3_BINDINGS,
        },
    )


def shadow_select_metric(
    metric_id: str, candidates: list[dict[str, Any]], *, as_of: str
) -> dict[str, Any]:
    """Validate the external freeze first, then delegate to the immutable oracle."""
    validate_energy_v3_freeze()
    return select_metric_v3(metric_id, candidates, as_of=as_of)
