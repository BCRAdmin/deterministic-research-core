from __future__ import annotations

from copy import deepcopy

import pytest

from research_agent.alpha_reit.v2 import (
    REIT_V2_PROFILE,
    guard_reit_validation_action,
    validate_raw_candidate,
)
from research_agent.profile_authority.contracts import (
    selection_receipt,
    validate_sector_profile_contract,
)
from research_agent.profile_authority.energy_v3 import (
    ENERGY_V3_FREEZE_AUTHORITY,
    energy_v3_registry,
    validate_energy_v3_freeze,
)
from research_agent.profile_authority.freeze_registry import build_freeze_authority
from research_agent.profile_authority.integrity import canonical_sha256


def _resign(value, field):
    value[field] = canonical_sha256({key: item for key, item in value.items() if key != field})
    return value


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("semantic_contract_sha256", "a" * 64),
        ("core_slot_registry_sha256", "b" * 64),
        ("period_policy_sha256", "c" * 64),
        ("candidate_integrity_contract_sha256", "d" * 64),
        ("independent_freeze_decision_sha256", "e" * 64),
        ("r13_compact_sha256", "f" * 64),
        ("r13_manifest_sha256", "0" * 64),
        ("research_tree", "1" * 40),
        ("threshold_mutation_requires_new_profile_version", False),
        ("product_cutover_authorized", True),
    ],
    ids=[f"R14-ENERGY-{index:02d}" for index in range(1, 11)],
)
def test_frozen_energy_attacks_block(field, value):
    attack = deepcopy(ENERGY_V3_FREEZE_AUTHORITY)
    attack[field] = value
    _resign(attack, "freeze_authority_sha256")
    with pytest.raises(ValueError):
        validate_energy_v3_freeze(attack)


@pytest.mark.parametrize(
    "attack",
    [
        "same_family_version",
        "semantic_registry_mutation",
        "period_policy_mutation",
        "candidate_integrity_mutation",
        "receipt_lineage_removal",
        "grade_promotion",
        "unknown_raw_contract",
        "forged_candidate_hash",
        "frozen_profile_replacement",
        "cross_profile_substitution",
    ],
    ids=[f"R14-SHARED-{index:02d}" for index in range(11, 21)],
)
def test_shared_profile_attacks_block(attack):
    if attack == "same_family_version":
        registry = energy_v3_registry()
        changed = deepcopy(ENERGY_V3_FREEZE_AUTHORITY)
        changed["freeze_effective_date"] = "2026-09-04"
        _resign(changed, "freeze_authority_sha256")
        with pytest.raises(ValueError, match="FROZEN_FAMILY_VERSION_MUTATION_BLOCKED"):
            registry.register(changed)
        return
    if attack in {
        "semantic_registry_mutation",
        "period_policy_mutation",
        "candidate_integrity_mutation",
        "grade_promotion",
        "cross_profile_substitution",
    }:
        profile = deepcopy(REIT_V2_PROFILE)
        if attack == "semantic_registry_mutation":
            profile["metric_contracts"][0]["ordered_concept_scope_rules"] = [
                "IssuerExtensionRevenue"
            ]
        elif attack == "period_policy_mutation":
            profile["period_freshness_contract"]["historical_behavior"] = "COUNT_AS_CURRENT"
        elif attack == "candidate_integrity_mutation":
            profile["candidate_integrity_contract"]["allowed_raw_candidate_contracts"].append(
                "unknown"
            )
        elif attack == "grade_promotion":
            profile["metric_contracts"][3]["comparability_grade"] = "A"
        else:
            profile["profile_identity"]["family"] = "Bank"
        with pytest.raises(ValueError, match="SELF_HASH_MISMATCH"):
            validate_sector_profile_contract(profile)
        return
    if attack == "receipt_lineage_removal":
        candidate = {"candidate_id": "raw." + "a" * 64, "candidate_sha256": "a" * 64}
        with pytest.raises(ValueError, match="LINEAGE"):
            selection_receipt(
                profile=REIT_V2_PROFILE,
                metric_id="revenue",
                status="SELECTED",
                selected_candidate=candidate,
                rejected_candidates=[],
                period_basis="STANDALONE_QUARTER",
                availability="CURRENT",
            )
        return
    candidate = {
        "contract_id": "unknown"
        if attack == "unknown_raw_contract"
        else "room16.reit.v2.primary_text_candidate@1",
        "candidate_id": "raw." + "a" * 64,
        "source_lineage": {"source_artifact_sha256": "b" * 64, "source_snapshot_sha256": "c" * 64},
        "candidate_sha256": "a" * 64,
    }
    if attack == "frozen_profile_replacement":
        authority = build_freeze_authority(
            profile_family="Energy",
            profile_version=3,
            semantic_contract_sha256="a" * 64,
            immutable=True,
            semantic_mutation_requires_new_profile_version=True,
            threshold_mutation_requires_new_profile_version=True,
            product_cutover_authorized=False,
            release_authorized=False,
        )
        with pytest.raises(ValueError):
            validate_energy_v3_freeze(authority)
    else:
        with pytest.raises(ValueError):
            validate_raw_candidate(candidate)


REIT_ATTACKS = [
    {"exposed_identity": "ticker"},
    {"exposed_identity": "alias"},
    {"exposed_identity": "cik"},
    {"result_fields_used_for_selection": ["coverage"]},
    {"result_fields_used_for_selection": ["pass_fail"]},
    {"provider_calls_before_selection_seal": 1},
    {"replacement_authorized": True},
    {"case_count": 13},
    {"semantic_changes_after_seal": 1},
    {"formula_changes_after_seal": 1},
    {"threshold_changes_after_seal": 1},
    {"primary_text_without_lineage": True},
    {"unsupported_non_gaap_label": True},
    {"period_mismatch": True},
    {"stale_primary_metric_count": 1},
    {"manual_semantic_interventions": 1},
    {"ticker_specific_semantic_patches": 1},
    {"historical_only_counted_as_current": True},
    {"product_mutation": True},
    {"claim_reit_frozen": True},
]


@pytest.mark.parametrize(
    "attack", REIT_ATTACKS, ids=[f"R14-REIT-{index:02d}" for index in range(21, 41)]
)
def test_reit_attacks_block(attack):
    with pytest.raises(ValueError):
        guard_reit_validation_action(attack)


def test_frozen_energy_authority_is_registered_by_full_hash():
    registry = energy_v3_registry()
    digest = validate_energy_v3_freeze()
    assert registry.resolve(digest) == ENERGY_V3_FREEZE_AUTHORITY


def test_future_energy_version_is_additive_and_historical_version_remains_addressable():
    registry = energy_v3_registry()
    future = deepcopy(ENERGY_V3_FREEZE_AUTHORITY)
    future["profile_version"] = 4
    _resign(future, "freeze_authority_sha256")
    registry.register(future)
    assert registry.resolve_version("Energy", 3) == ENERGY_V3_FREEZE_AUTHORITY
    assert registry.resolve_version("Energy", 4) == future
