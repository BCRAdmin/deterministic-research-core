from __future__ import annotations

import inspect

import pytest

from research_agent.alpha_shared.execution_authority import (
    AuthorizationReceiptIR,
    BatchExecutionAuthorityIR,
    BatchExecutionCaseIR,
    ExecutionAuthorityError,
    RuntimeIdentityIR,
    SharedFreezeBindingIR,
    authorize_case_before_network,
    fixed_company_list_sha256,
    threshold_authority_sha256,
    verify_receipt_for_live_case,
)
from research_agent.alpha_shared import runner
from research_agent.compiler_foundation.canonical import sha256_json


def _runtime(**updates: str) -> RuntimeIdentityIR:
    values = {
        "research_commit": "1" * 40,
        "research_tree": "2" * 40,
        "product_commit": "3" * 40,
        "product_tree": "4" * 40,
        "as_of_date": "2026-08-28",
    }
    values.update(updates)
    return RuntimeIdentityIR(**values)


def _list_document() -> dict[str, object]:
    return {
        "companies": [
            {
                "sequence": 1,
                "ticker": "ORCL",
                "company_name": "Oracle Corporation",
                "archetype": "Software/SaaS",
            },
            {
                "sequence": 2,
                "ticker": "ADBE",
                "company_name": "Adobe Inc.",
                "archetype": "Software/SaaS",
            },
            {
                "sequence": 3,
                "ticker": "MTDR",
                "company_name": "Matador Resources Company",
                "archetype": "Integrated Energy",
            },
        ]
    }


def _threshold_document() -> dict[str, object]:
    return {
        "contract_id": "room16.alpha.fixed_24_batch_acceptance_thresholds@1",
        "batch_size": 3,
        "hard_fail": [{"metric": "P0_count", "threshold": "=0"}],
    }


def _cases() -> tuple[BatchExecutionCaseIR, ...]:
    return (
        BatchExecutionCaseIR(
            sequence=1,
            ticker="ORCL",
            company_name="Oracle Corporation",
            archetype_profile_id="saas",
        ),
        BatchExecutionCaseIR(
            sequence=2,
            ticker="ADBE",
            company_name="Adobe Inc.",
            archetype_profile_id="saas",
        ),
        BatchExecutionCaseIR(
            sequence=3,
            ticker="MTDR",
            company_name="Matador Resources Company",
            archetype_profile_id="energy",
        ),
    )


def _fixed_authority(
    *,
    runtime: RuntimeIdentityIR | None = None,
    network_live_authorized: bool = False,
    shared_freeze_sha256: str | None = None,
    list_sha256: str | None = None,
    threshold_sha256: str | None = None,
) -> BatchExecutionAuthorityIR:
    identity = runtime or _runtime()
    return BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=identity.as_of_date,
        research_commit=identity.research_commit,
        research_tree=identity.research_tree,
        product_commit=identity.product_commit,
        product_tree=identity.product_tree,
        shared_freeze_sha256=shared_freeze_sha256,
        fixed_company_list_sha256=list_sha256 or fixed_company_list_sha256(_list_document()),
        threshold_sha256=threshold_sha256 or threshold_authority_sha256(
            _threshold_document()
        ),
        ordered_cases=_cases(),
        network_live_authorized=network_live_authorized,
    )


def _authorize(
    *,
    ticker: str = "ORCL",
    profile: str = "saas",
    sequence: int = 1,
    authority: BatchExecutionAuthorityIR | None = None,
    runtime: RuntimeIdentityIR | None = None,
    shared_freeze: SharedFreezeBindingIR | None = None,
    list_document: dict[str, object] | None = None,
    threshold_document: dict[str, object] | None = None,
) -> AuthorizationReceiptIR:
    return authorize_case_before_network(
        ticker=ticker,
        archetype_profile_id=profile,
        sequence=sequence,
        authority=authority or _fixed_authority(),
        runtime_identity=runtime or _runtime(),
        shared_freeze=shared_freeze,
        fixed_company_list=list_document or _list_document(),
        threshold_authority=threshold_document or _threshold_document(),
    )


@pytest.mark.parametrize(
    ("ticker", "profile", "sequence"),
    (("ORCL", "saas", 1), ("ADBE", "saas", 2), ("MTDR", "energy", 3)),
)
def test_fixed_batch_exact_ordered_cases_preflight_without_network(
    ticker: str, profile: str, sequence: int
):
    receipt = _authorize(ticker=ticker, profile=profile, sequence=sequence)
    assert receipt.status == "PASS"
    assert receipt.authorization_mode == "PREFLIGHT_ONLY"
    assert receipt.authorization_preflight_count == 1
    assert receipt.case_attempt_count == 0
    assert receipt.live_network_query_count == 0
    assert receipt.completed_case_count == 0


@pytest.mark.parametrize(
    ("ticker", "profile", "sequence", "code"),
    (
        ("UNKNOWN", "saas", 1, "EXEC_AUTH_CASE_NOT_ORDERED"),
        ("ORCL", "saas", 2, "EXEC_AUTH_CASE_NOT_ORDERED"),
        ("ORCL", "energy", 1, "EXEC_AUTH_PROFILE_MISMATCH"),
    ),
)
def test_unknown_order_or_profile_blocks_before_network(
    ticker: str, profile: str, sequence: int, code: str
):
    with pytest.raises(ExecutionAuthorityError, match=code):
        _authorize(ticker=ticker, profile=profile, sequence=sequence)


@pytest.mark.parametrize(
    "runtime",
    (
        _runtime(research_commit="a" * 40),
        _runtime(research_tree="b" * 40),
        _runtime(product_commit="c" * 40),
        _runtime(product_tree="d" * 40),
        _runtime(as_of_date="2026-08-27"),
    ),
)
def test_wrong_runtime_identity_blocks_before_network(runtime: RuntimeIdentityIR):
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_RUNTIME_MISMATCH"):
        _authorize(runtime=runtime)


def test_wrong_fixed_list_hash_blocks_before_network():
    authority = _fixed_authority(list_sha256="a" * 64)
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_FIXED_LIST_HASH_MISMATCH"):
        _authorize(authority=authority)


def test_wrong_threshold_hash_blocks_before_network():
    authority = _fixed_authority(threshold_sha256="b" * 64)
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_THRESHOLD_HASH_MISMATCH"):
        _authorize(authority=authority)


def test_live_fixed_batch_requires_shared_freeze():
    authority = _fixed_authority(
        network_live_authorized=True,
        shared_freeze_sha256="c" * 64,
    )
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_SHARED_FREEZE_MISSING"):
        _authorize(authority=authority)


@pytest.mark.parametrize(
    "field",
    (
        "semantic_changes_authorized",
        "company_replacement_authorized",
        "ticker_specific_rules_authorized",
    ),
)
def test_forbidden_execution_capabilities_block(field: str):
    authority = _fixed_authority()
    values = authority.model_dump(mode="json", exclude={"authority_sha256"})
    values[field] = True
    tampered = authority.model_copy(
        update={field: True, "authority_sha256": sha256_json(values)}
    )
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_FORBIDDEN_CAPABILITY"):
        _authorize(authority=tampered)


def test_tampered_authority_selfhash_blocks():
    tampered = _fixed_authority().model_copy(update={"authority_sha256": "0" * 64})
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_SELFHASH_MISMATCH"):
        _authorize(authority=tampered)


def test_failed_and_successful_preflight_never_increment_provider_counters():
    receipt = _authorize()
    assert receipt.live_network_query_count == 0
    with pytest.raises(ExecutionAuthorityError):
        _authorize(ticker="UNKNOWN")
    assert receipt.live_network_query_count == 0


def test_canonical_runner_requires_verified_receipt_instead_of_ticker_hardcode():
    source = inspect.getsource(runner.run_canonical_alpha_case)
    assert "DEVELOPMENT_LIVE_TICKERS" not in inspect.getsource(runner)
    assert "verify_receipt_for_live_case" in source
    assert "R4_LIVE_TICKER_NOT_AUTHORIZED" not in source


def test_development_validation_uses_external_authority():
    runtime = _runtime(as_of_date="2026-08-27")
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="DEVELOPMENT_VALIDATION",
        as_of_date=runtime.as_of_date,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=None,
        fixed_company_list_sha256=None,
        threshold_sha256=None,
        ordered_cases=(
            BatchExecutionCaseIR(
                sequence=1,
                ticker="XOM",
                company_name="Exxon Mobil Corporation",
                archetype_profile_id="energy",
            ),
        ),
        network_live_authorized=True,
    )
    receipt = authorize_case_before_network(
        ticker="XOM",
        archetype_profile_id="energy",
        sequence=1,
        authority=authority,
        runtime_identity=runtime,
    )
    assert receipt.authorization_mode == "LIVE_AUTHORIZED"
    assert receipt.live_network_query_count == 0


def test_preflight_only_receipt_cannot_reach_live_runner():
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_LIVE_NOT_AUTHORIZED"):
        verify_receipt_for_live_case(
            receipt=_authorize(),
            ticker="ORCL",
            archetype_profile_id="saas",
            as_of_date="2026-08-28",
            research_commit="1" * 40,
            research_tree="2" * 40,
        )


def test_live_fixed_batch_accepts_exact_verified_freeze_binding():
    freeze_hash = "c" * 64
    authority = _fixed_authority(
        network_live_authorized=True,
        shared_freeze_sha256=freeze_hash,
    )
    runtime = _runtime()
    freeze = SharedFreezeBindingIR.create(
        freeze_sha256=freeze_hash,
        fixed_company_list_sha256=authority.fixed_company_list_sha256,
        threshold_sha256=authority.threshold_sha256,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
    )
    receipt = _authorize(authority=authority, shared_freeze=freeze)
    assert receipt.authorization_mode == "LIVE_AUTHORIZED"
    assert receipt.network_live_authorized is True
    assert receipt.live_network_query_count == 0


def test_wrong_shared_freeze_binding_blocks_before_network():
    authority = _fixed_authority(
        network_live_authorized=True,
        shared_freeze_sha256="c" * 64,
    )
    runtime = _runtime()
    freeze = SharedFreezeBindingIR.create(
        freeze_sha256="d" * 64,
        fixed_company_list_sha256=authority.fixed_company_list_sha256,
        threshold_sha256=authority.threshold_sha256,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
    )
    with pytest.raises(ExecutionAuthorityError, match="EXEC_AUTH_SHARED_FREEZE_MISMATCH"):
        _authorize(authority=authority, shared_freeze=freeze)


def test_authorization_receipt_selfhash_is_verified():
    tampered = _authorize().model_copy(update={"receipt_sha256": "0" * 64})
    with pytest.raises(
        ExecutionAuthorityError, match="EXEC_AUTH_RECEIPT_SELFHASH_MISMATCH"
    ):
        verify_receipt_for_live_case(
            receipt=tampered,
            ticker="ORCL",
            archetype_profile_id="saas",
            as_of_date="2026-08-28",
            research_commit="1" * 40,
            research_tree="2" * 40,
        )
