from __future__ import annotations

from copy import deepcopy

import pytest

from research_agent.alpha_shared.execution_authority import (
    BatchExecutionAuthorityIR,
    ExecutionAuthorityError,
    RuntimeIdentityIR,
    SharedFreezeBindingIR,
    authorize_case_before_network,
    fixed_company_list_sha256,
    ordered_cases_from_fixed_company_list,
    threshold_authority_sha256,
)
from research_agent.compiler_foundation.canonical import sha256_json


def _legacy() -> dict[str, object]:
    return {
        "contract_id": "room16.alpha.fixed_24_batch_acceptance_thresholds@1",
        "batch_size": 3,
        "hard_fail": [{"metric": "P0_count", "threshold": "=0"}],
    }


def _v2() -> dict[str, object]:
    return {
        "contract_id": "room16.alpha.fixed_batch_acceptance_thresholds@2",
        "scope": "vlo_infrastructure_correction_plus_untouched_psx_dvn",
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


def _fixed_list() -> dict[str, object]:
    return {
        "companies": [
            {
                "sequence": 1,
                "ticker": "VLO",
                "company_name": "Valero Energy Corporation",
                "archetype": "Integrated Energy",
            },
            {
                "sequence": 2,
                "ticker": "PSX",
                "company_name": "Phillips 66",
                "archetype": "Integrated Energy",
            },
            {
                "sequence": 3,
                "ticker": "DVN",
                "company_name": "Devon Energy Corporation",
                "archetype": "Integrated Energy",
            },
        ]
    }


def test_legacy_fixed24_threshold_hash_uses_exact_historical_path() -> None:
    document = _legacy()
    assert threshold_authority_sha256(document) == sha256_json(document)


def test_valid_v2_constructs_authority_freeze_and_three_zero_call_receipts() -> None:
    runtime = RuntimeIdentityIR(
        research_commit="1" * 40,
        research_tree="2" * 40,
        product_commit="3" * 40,
        product_tree="4" * 40,
        as_of_date="2026-08-31",
    )
    fixed = _fixed_list()
    thresholds = _v2()
    fixed_sha = fixed_company_list_sha256(fixed)
    threshold_sha = threshold_authority_sha256(thresholds)
    freeze_sha = "5" * 64
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=runtime.as_of_date,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=freeze_sha,
        fixed_company_list_sha256=fixed_sha,
        threshold_sha256=threshold_sha,
        ordered_cases=ordered_cases_from_fixed_company_list(fixed),
        network_live_authorized=True,
    )
    freeze = SharedFreezeBindingIR.create(
        freeze_sha256=freeze_sha,
        fixed_company_list_sha256=fixed_sha,
        threshold_sha256=threshold_sha,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
    )
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
            shared_freeze=freeze,
            fixed_company_list=fixed,
            threshold_authority=thresholds,
        )
        for case in authority.ordered_cases
    ]
    assert len(receipts) == 3
    assert all(receipt.live_network_query_count == 0 for receipt in receipts)
    assert all(
        receipt.receipt_sha256
        == sha256_json(receipt.model_dump(mode="json", exclude={"receipt_sha256"}))
        for receipt in receipts
    )


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("required_surfaced_fact_lineage_percent", 99, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("maximum_stale_primary_metric_count", 1, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("required_replay_identity_percent", 99, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("maximum_replay_provider_calls", 1, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("maximum_P0", 1, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("maximum_P1", 1, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("maximum_manual_semantic_interventions", 1, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("maximum_ticker_specific_semantic_patches", 1, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("no_waiver", False, "EXEC_AUTH_THRESHOLD_V2_SAFETY_INVALID"),
        ("minimum_company_core_coverage_percent", -1, "EXEC_AUTH_THRESHOLD_V2_RANGE_INVALID"),
        ("minimum_archetype_median_core_coverage_percent", 101, "EXEC_AUTH_THRESHOLD_V2_RANGE_INVALID"),
        ("minimum_section_completeness_percent", True, "EXEC_AUTH_THRESHOLD_V2_TYPE_INVALID"),
    ),
)
def test_v2_weakening_or_malformed_scalar_blocks(
    field: str, value: object, code: str
) -> None:
    document = deepcopy(_v2())
    document[field] = value
    with pytest.raises(ExecutionAuthorityError, match=code):
        threshold_authority_sha256(document)


def test_v2_missing_required_field_blocks() -> None:
    document = _v2()
    document.pop("maximum_P1")
    with pytest.raises(
        ExecutionAuthorityError, match="EXEC_AUTH_THRESHOLD_V2_MISSING_FIELD"
    ):
        threshold_authority_sha256(document)


@pytest.mark.parametrize(
    "contract_id",
    (
        "room16.alpha.fixed_batch_acceptance_thresholds@3",
        "room16.alpha.fixed_batch_acceptance_thresholds@2-weakened",
        "room16.energy_recovery_r3.acceptance_thresholds@1",
    ),
)
def test_unknown_or_masquerading_contract_id_blocks(contract_id: str) -> None:
    document = _v2()
    document["contract_id"] = contract_id
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_THRESHOLD_INVALID"):
        threshold_authority_sha256(document)


def test_v2_unexpected_field_blocks() -> None:
    document = _v2()
    document["allow_waiver_for_energy"] = True
    with pytest.raises(
        ExecutionAuthorityError, match="EXEC_AUTH_THRESHOLD_V2_UNEXPECTED_FIELD"
    ):
        threshold_authority_sha256(document)
