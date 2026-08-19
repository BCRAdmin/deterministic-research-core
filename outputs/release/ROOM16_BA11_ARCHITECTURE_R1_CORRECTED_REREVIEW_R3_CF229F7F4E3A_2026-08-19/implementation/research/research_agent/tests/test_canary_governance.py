from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from nacl.signing import SigningKey
from pydantic import ValidationError

from research_agent.canary_governance.approval import (
    TrustedRoleKeyPolicy,
    sign_approval,
    sign_independent_review,
    sign_research_snapshot_receipt,
    verify_approval,
    verify_independent_review,
    verify_research_snapshot_receipt,
)
from research_agent.canary_governance.archive import (
    build_deterministic_zip,
    build_package_identity,
)
from research_agent.canary_governance.contracts import (
    CONTRACT_MODELS,
    AcceptedDebtEvent,
    ArchiveReceipt,
    CanaryFreezeRecord,
    CanaryRegistryEntry,
    ChangeClassification,
    ComparisonResult,
    EvidenceManifest,
    IndependentReviewAttestation,
    OperatorApprovalReceipt,
    PromotionEvent,
    RecoveryEvent,
    RegistryEvent,
    RegistrySnapshot,
    RegistryTransaction,
    RejectionEvent,
    SourceContractBinding,
    SourceContractLock,
    StaleEvent,
    SupersessionEvent,
    domain_hash,
)
from research_agent.canary_governance.diagnostics import CanaryGovernanceError
from research_agent.canary_governance.ledger import (
    assert_no_canary_id_collision,
    build_debt_ledger_head,
    build_registry_ledger_head,
    derive_canary_id,
    derive_canary_identity,
    fold_registry_events,
    ledger_to_snapshot,
    normalize_subject_key,
    validate_version_transition,
    verify_debt_ledger,
    verify_derived_snapshot,
)
from research_agent.canary_governance.storage import ContentAddressedRegistryStore

H1, H2, H3, H4, H5, H6, H7, H8 = (str(index) * 64 for index in range(1, 9))
ZERO = "0" * 64


def role_keys() -> tuple[TrustedRoleKeyPolicy, SigningKey, SigningKey, SigningKey]:
    operator = SigningKey(bytes.fromhex("01" * 32))
    reviewer = SigningKey(bytes.fromhex("02" * 32))
    research = SigningKey(bytes.fromhex("03" * 32))
    policy = TrustedRoleKeyPolicy(
        operator_keys={"operator.primary": operator.verify_key},
        reviewer_keys={"reviewer.primary": reviewer.verify_key},
        research_keys={"research.primary": research.verify_key},
    )
    return policy, operator, reviewer, research


def event_values(sequence: int, kind: str, previous: str | None) -> dict:
    return {
        "event_id": f"event.{sequence}",
        "canary_id": "canary.company.test",
        "sequence": sequence,
        "event_type": kind,
        "subject_sha256": H1,
        "canary_type": "company_regression",
        "baseline_version": "1.0.0",
        "technical_baseline_sha256": H2,
        "governance_envelope_sha256": H3,
        "freeze_sha256": H4 if kind in {"frozen", "stale", "recovered", "superseded"} else None,
        "previous_event_sha256": previous,
        "effective_at_utc": f"2026-08-20T00:00:{sequence:02d}Z",
    }


def make_event(sequence: int, kind: str, previous: str | None) -> RegistryEvent:
    values = event_values(sequence, kind, previous)
    if kind == "frozen":
        return PromotionEvent.create(
            **values, independent_review_sha256=H5, operator_approval_sha256=H6
        )
    if kind == "rejected":
        return RejectionEvent.create(**values, rejection_reason="review failed", review_sha256=H5)
    if kind == "stale":
        return StaleEvent.create(**values, stale_reason="baseline drift", detected_baseline_sha256=H5)
    if kind == "recovered":
        return RecoveryEvent.create(**values, recovery_review_sha256=H5)
    if kind == "superseded":
        return SupersessionEvent.create(
            **values,
            superseding_canary_id="canary.company.next",
            superseding_freeze_sha256=H5,
        )
    return RegistryEvent.create(**values)


def registry_chain() -> tuple[RegistryEvent, ...]:
    events: list[RegistryEvent] = []
    previous = None
    for sequence, kind in enumerate(
        ("genesis", "candidate", "review_accepted", "operator_approved", "frozen")
    ):
        current = make_event(sequence, kind, previous)
        events.append(current)
        previous = current.event_sha256
    return tuple(events)


def debt_event(
    sequence: int,
    kind: str,
    previous: str | None,
    before: str | None,
    *,
    approval: str | None = None,
) -> AcceptedDebtEvent:
    return AcceptedDebtEvent.create(
        debt_id="debt.test",
        event_id=f"debt.event.{sequence}",
        sequence=sequence,
        event_type=kind,
        previous_event_sha256=previous,
        finding_id="BA11-AR-013",
        debt_type="ux.debt",
        scope="appendix",
        state_before=before,
        state_after=kind,
        reason="test transition",
        evidence_refs=("evidence.test",),
        approval_receipt_sha256=approval,
        recorded_at_utc=f"2026-08-20T00:01:{sequence:02d}Z",
    )


def approval_values(*, decision: str = "approve", nonce: str = "operator-nonce-0001", counter: int = 1):
    return {
        "approval_id": f"approval.{counter}",
        "decision": decision,
        "scope": "ba11_canary_promotion",
        "subject_ids": ("canary.company.test",),
        "subject_sha256s": (H1,),
        "review_finding_set_sha256": H2,
        "previous_registry_head_sha256": ZERO,
        "approver_key_id": "operator.primary",
        "issued_at_utc": "2026-08-20T00:00:00Z",
        "expires_at_utc": "2026-08-21T00:00:00Z",
        "nonce": nonce,
        "monotonic_counter": counter,
    }


def review_values(*, decision: str = "accepted", nonce: str = "reviewer-nonce-0001", counter: int = 1):
    return {
        "review_id": f"review.{counter}",
        "reviewer_key_id": "reviewer.primary",
        "reviewer_role": "independent_architecture_reviewer",
        "scope": "ba11_canary_promotion",
        "subject_ids": ("canary.company.test",),
        "subject_sha256s": (H1,),
        "finding_set_sha256": H2,
        "previous_registry_head_sha256": ZERO,
        "decision": decision,
        "nonce": nonce,
        "monotonic_counter": counter,
        "issued_at_utc": "2026-08-20T00:00:00Z",
        "expires_at_utc": "2026-08-21T00:00:00Z",
    }


def verify_operator(receipt: OperatorApprovalReceipt, **changes) -> None:
    policy, *_ = role_keys()
    values = {
        "trusted_role_key_policy": policy,
        "revoked_key_ids": set(),
        "consumed_nonces": set(),
        "minimum_monotonic_counter": 0,
        "expected_decision": "approve",
        "expected_scope": "ba11_canary_promotion",
        "expected_subject_ids": ("canary.company.test",),
        "expected_subject_sha256s": (H1,),
        "expected_finding_set_sha256": H2,
        "expected_previous_registry_head_sha256": ZERO,
        "fixed_now_utc": "2026-08-20T12:00:00Z",
    }
    values.update(changes)
    verify_approval(receipt, **values)


def verify_reviewer(receipt: IndependentReviewAttestation, **changes) -> None:
    policy, *_ = role_keys()
    values = {
        "trusted_role_key_policy": policy,
        "revoked_key_ids": set(),
        "consumed_nonces": set(),
        "minimum_monotonic_counter": 0,
        "expected_decision": "accepted",
        "expected_scope": "ba11_canary_promotion",
        "expected_subject_ids": ("canary.company.test",),
        "expected_subject_sha256s": (H1,),
        "expected_finding_set_sha256": H2,
        "expected_previous_registry_head_sha256": ZERO,
        "fixed_now_utc": "2026-08-20T12:00:00Z",
    }
    values.update(changes)
    verify_independent_review(receipt, **values)


def test_t_rr2_013_a_source_contract_hashes_are_typed_and_bijective():
    first = SourceContractBinding.create(source_contract_id="room16.source.alpha", source_contract_sha256=H1)
    second = SourceContractBinding.create(source_contract_id="room16.source.beta", source_contract_sha256=H2)
    lock = SourceContractLock.create(bindings=(first, second))
    assert lock.bindings[0].source_contract_sha256 == H1
    with pytest.raises(ValidationError):
        SourceContractBinding.create(source_contract_id="room16.source.bad", source_contract_sha256="not-a-hash")
    with pytest.raises(ValidationError):
        SourceContractLock.create(bindings=(second, first))


def test_t_rr2_006_a_identity_dependency_graph_is_acyclic():
    assert "registry_snapshot_sha256" not in CanaryFreezeRecord.model_fields
    assert "freeze_sha256" in CanaryRegistryEntry.model_fields
    assert "candidate_snapshot_sha256" in RegistryTransaction.model_fields


def test_t_rr2_006_b_real_promotion_graph_uses_no_placeholder_cycle():
    freeze = CanaryFreezeRecord.create(
        freeze_id="freeze.test", canary_id="canary.company.test",
        technical_baseline_sha256=H2, governance_envelope_sha256=H3,
        effective_at_utc="2026-08-20T00:00:00Z",
    )
    events = list(registry_chain())
    promoted = events[-1]
    events[-1] = PromotionEvent.create(
        **{**promoted.model_dump(exclude={"event_sha256", "freeze_sha256"}), "freeze_sha256": freeze.freeze_sha256}
    )
    head = build_registry_ledger_head(events, generation=0, previous_head_sha256=None)
    snapshot = ledger_to_snapshot(events, expected_head=head, registry_generation=0, previous_registry_sha256=None)
    assert snapshot.entries[0].freeze_sha256 == freeze.freeze_sha256
    assert snapshot.snapshot_sha256 not in freeze.model_dump_json()


def test_t_rr2_005_a_record_specific_contract_set_and_entry_hash():
    ids = {model.model_fields["contract_id"].default for model in CONTRACT_MODELS}
    assert {
        "room16.canary_promotion_event", "room16.canary_rejection_event",
        "room16.canary_stale_event", "room16.canary_recovery_event",
        "room16.canary_supersession_event", "room16.canary_evidence_manifest",
    } <= ids
    event = make_event(0, "genesis", None)
    entry = CanaryRegistryEntry.create(
        canary_id=event.canary_id, canary_type=event.canary_type,
        baseline_version=event.baseline_version, technical_baseline_sha256=H2,
        governance_envelope_sha256=H3, freeze_sha256=None,
        derived_state="candidate", latest_event_sha256=event.event_sha256,
    )
    with pytest.raises(ValidationError):
        CanaryRegistryEntry(**{**entry.model_dump(), "baseline_version": "1.0.1"})


def test_t_rr2_002_a_signed_reject_cannot_authorize_promotion():
    policy, operator, *_ = role_keys()
    receipt = sign_approval(approval_values(decision="reject"), operator)
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_DECISION"):
        verify_operator(receipt, trusted_role_key_policy=policy)


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"expected_finding_set_sha256": H3}, "BA11_APPROVAL_FINDING_SET"),
        ({"expected_previous_registry_head_sha256": H3}, "BA11_APPROVAL_PREVIOUS_HEAD"),
        ({"expected_subject_ids": ("canary.company.other",)}, "BA11_APPROVAL_SUBJECT"),
    ],
)
def test_t_rr2_002_b_c_wrong_approval_bindings_are_blocked(changes, code):
    _, operator, *_ = role_keys()
    receipt = sign_approval(approval_values(), operator)
    with pytest.raises(CanaryGovernanceError, match=code):
        verify_operator(receipt, **changes)


def test_t_rr2_002_d_reviewer_must_be_role_independent():
    operator = SigningKey(bytes.fromhex("01" * 32))
    with pytest.raises(CanaryGovernanceError, match="BA11_REVIEWER_NOT_INDEPENDENT"):
        TrustedRoleKeyPolicy(
            operator_keys={"operator.primary": operator.verify_key},
            reviewer_keys={"reviewer.primary": operator.verify_key},
            research_keys={},
        )


def test_t_rr2_002_e_review_replay_revocation_expiry_and_signature_block():
    policy, _, reviewer, _ = role_keys()
    receipt = sign_independent_review(review_values(), reviewer)
    verify_reviewer(receipt, trusted_role_key_policy=policy)
    for changes, code in (
        ({"consumed_nonces": {receipt.nonce}}, "BA11_ATTESTATION_REPLAY"),
        ({"revoked_key_ids": {receipt.reviewer_key_id}}, "BA11_ATTESTATION_REVOKED"),
        ({"fixed_now_utc": "2026-08-21T00:00:00Z"}, "BA11_ATTESTATION_EXPIRED"),
    ):
        with pytest.raises(CanaryGovernanceError, match=code):
            verify_reviewer(receipt, trusted_role_key_policy=policy, **changes)
    with pytest.raises(CanaryGovernanceError, match="BA11_ATTESTATION_SIGNATURE"):
        verify_reviewer(receipt.model_copy(update={"signature": "0" * 128}), trusted_role_key_policy=policy)


def test_research_snapshot_receipt_has_separate_sign_and_verify_path():
    policy, *_, research = role_keys()
    receipt = sign_research_snapshot_receipt(
        {
            "receipt_id": "receipt.research", "research_key_id": "research.primary",
            "snapshot_sha256": H1, "registry_head_sha256": H2,
            "issued_at_utc": "2026-08-20T00:00:00Z",
        },
        research,
    )
    verify_research_snapshot_receipt(
        receipt, trusted_role_key_policy=policy,
        expected_snapshot_sha256=H1, expected_registry_head_sha256=H2,
    )


def test_t_rr2_004_a_registry_valid_prefix_rollback_is_blocked():
    events = registry_chain()
    full_head = build_registry_ledger_head(events, generation=0, previous_head_sha256=None)
    assert fold_registry_events(events, expected_head=full_head)["canary.company.test"] == "frozen"
    with pytest.raises(CanaryGovernanceError, match="BA11_LEDGER_ROLLBACK"):
        fold_registry_events(events[:-1], expected_head=full_head)


def test_t_rr2_004_b_debt_valid_prefix_rollback_is_blocked():
    opened = debt_event(0, "opened", None, None)
    accepted = debt_event(1, "accepted", opened.event_sha256, "opened", approval=H1)
    closed = debt_event(2, "closed", accepted.event_sha256, "accepted")
    events = (opened, accepted, closed)
    head = build_debt_ledger_head(events, generation=0, previous_head_sha256=None)
    assert verify_debt_ledger(events, expected_head=head, authentic_approval_sha256s={H1})["debt.test"] == "closed"
    with pytest.raises(CanaryGovernanceError, match="BA11_LEDGER_ROLLBACK"):
        verify_debt_ledger(events[:-1], expected_head=head, authentic_approval_sha256s={H1})


def test_t_rr2_004_c_d_e_persistent_ledgers_block_fork_bad_approval_and_reopen(tmp_path: Path):
    store = ContentAddressedRegistryStore(tmp_path / "registry")
    genesis = make_event(0, "genesis", None)
    first = store.append_registry_event(genesis, expected_head_sha256=None)
    candidate = make_event(1, "candidate", genesis.event_sha256)
    with pytest.raises(CanaryGovernanceError, match="BA11_LEDGER_FORK"):
        store.append_registry_event(candidate, expected_head_sha256=H8)
    assert store.read_registry_ledger_head() == first
    opened = debt_event(0, "opened", None, None)
    accepted = debt_event(1, "accepted", opened.event_sha256, "opened", approval=H1)
    head = build_debt_ledger_head((opened, accepted), generation=0, previous_head_sha256=None)
    with pytest.raises(CanaryGovernanceError, match="BA11_DEBT_APPROVAL_REQUIRED"):
        verify_debt_ledger((opened, accepted), expected_head=head, authentic_approval_sha256s=set())
    closed = debt_event(2, "closed", accepted.event_sha256, "accepted")
    reopened = debt_event(3, "accepted", closed.event_sha256, "closed", approval=H1)
    reopen_head = build_debt_ledger_head((opened, accepted, closed, reopened), generation=0, previous_head_sha256=None)
    with pytest.raises(CanaryGovernanceError, match="BA11_DEBT_CHAIN_BROKEN"):
        verify_debt_ledger(
            (opened, accepted, closed, reopened), expected_head=reopen_head,
            authentic_approval_sha256s={H1},
        )


def test_t_rr2_009_a_b_snapshot_is_normatively_derived_and_deterministic():
    events = registry_chain()
    head = build_registry_ledger_head(events, generation=0, previous_head_sha256=None)
    first = ledger_to_snapshot(events, expected_head=head, registry_generation=0, previous_registry_sha256=None)
    second = ledger_to_snapshot(events, expected_head=head, registry_generation=0, previous_registry_sha256=None)
    assert first == second
    forged = RegistrySnapshot.create(
        registry_generation=0, previous_registry_sha256=None,
        ledger_head_sha256=head.head_sha256, entries=(),
    )
    with pytest.raises(CanaryGovernanceError, match="BA11_SNAPSHOT_NOT_DERIVED"):
        verify_derived_snapshot(forged, events, expected_head=head)


def test_t_rr2_008_a_b_no_new_truth_and_classification_counts_are_bound():
    with pytest.raises(ValidationError, match="zero semantic diffs"):
        ComparisonResult.create(
            request_sha256=H1, baseline_sha256=H2, candidate_sha256=H3,
            verdict="ordinary_change", fact_diff_count=1, claim_diff_count=0,
            decision_diff_count=0, lineage_diff_count=0, diagnostic_codes=(),
        )
    result = ComparisonResult.create(
        request_sha256=H1, baseline_sha256=H2, candidate_sha256=H3,
        verdict="ordinary_change", fact_diff_count=0, claim_diff_count=0,
        decision_diff_count=0, lineage_diff_count=0, diagnostic_codes=(),
    )
    classification = ChangeClassification.from_comparison(
        classification_id="change.presentation", change_class="ordinary", result=result,
        semantic_lock_changed=False, presentation_contract_changed=True,
        renderer_artifact_changed=True, source_contract_changed=False,
    )
    assert classification.comparison_result_sha256 == result.result_sha256
    with pytest.raises(ValidationError):
        ChangeClassification(**{**classification.model_dump(), "fact_diff_count": 1})


def test_t_rr2_010_a_subject_normalization_and_collision_gate():
    assert normalize_subject_key(" Straße ") == normalize_subject_key("STRASSE")
    canary_id, _, subject_hash = derive_canary_identity("company", "WM")
    assert derive_canary_id("company", " WM ") == canary_id
    with pytest.raises(CanaryGovernanceError, match="BA11_ID_COLLISION"):
        assert_no_canary_id_collision("company", "WM", {canary_id: H8})
    assert assert_no_canary_id_collision("company", "WM", {canary_id: subject_hash}) == canary_id


def test_t_rr2_010_b_semver_is_derived_from_change_class():
    validate_version_transition(None, "1.0.0", genesis=True)
    validate_version_transition("1.0.0", "1.0.1", change_class="ordinary")
    validate_version_transition("1.0.1", "1.1.0", change_class="governance")
    validate_version_transition("1.1.0", "2.0.0", change_class="breaking")
    with pytest.raises(CanaryGovernanceError, match="BA11_VERSION_TRANSITION_INVALID"):
        validate_version_transition("1.0.0", "2.0.0", change_class="ordinary")


def test_t_rr2_010_c_genesis_import_is_persistently_one_time(tmp_path: Path):
    from research_agent.canary_governance.contracts import GenesisImportReceipt

    store = ContentAddressedRegistryStore(tmp_path / "registry")
    receipt = GenesisImportReceipt.create(
        import_id="genesis.one", source_records_sha256=H1,
        imported_canary_ids=("canary.company.test",),
    )
    store.commit_genesis_import(receipt)
    with pytest.raises(CanaryGovernanceError, match="BA11_GENESIS_ALREADY_IMPORTED"):
        store.commit_genesis_import(receipt)


def transaction_fixture(tmp_path: Path):
    policy, operator_key, reviewer_key, _ = role_keys()
    approval = sign_approval(approval_values(), operator_key)
    review = sign_independent_review(review_values(), reviewer_key)
    freeze = CanaryFreezeRecord.create(
        freeze_id="freeze.test", canary_id="canary.company.test",
        technical_baseline_sha256=H2, governance_envelope_sha256=H3,
        effective_at_utc="2026-08-20T00:00:00Z",
    )
    events = list(registry_chain())
    previous = events[-2].event_sha256
    promotion_values = event_values(4, "frozen", previous)
    promotion_values["freeze_sha256"] = freeze.freeze_sha256
    events[-1] = PromotionEvent.create(
        **promotion_values,
        independent_review_sha256=review.attestation_sha256,
        operator_approval_sha256=approval.approval_sha256,
    )
    events = tuple(events)
    registry_head = build_registry_ledger_head(events, generation=0, previous_head_sha256=None)
    snapshot = ledger_to_snapshot(
        events, expected_head=registry_head, registry_generation=0, previous_registry_sha256=None
    )
    debt_events: tuple[AcceptedDebtEvent, ...] = ()
    debt_head = build_debt_ledger_head(debt_events, generation=0, previous_head_sha256=None)
    comparison = ComparisonResult.create(
        request_sha256=H5, baseline_sha256=H6, candidate_sha256=H7,
        verdict="promotion_required", fact_diff_count=1, claim_diff_count=0,
        decision_diff_count=0, lineage_diff_count=0, diagnostic_codes=(),
    )
    archive = ArchiveReceipt.create(
        archive_content_sha256=H1, archive_member_manifest_sha256=H2,
        source_date_epoch=1787184000, retention_class="governance_record",
    )
    event_set_sha = domain_hash(
        "room16.canary_registry_event_set@1", [event.model_dump(mode="json") for event in events]
    )
    transaction = RegistryTransaction.create(
        transaction_id="transaction.test", registry_generation=0, base_head_sha256=None,
        candidate_snapshot_sha256=snapshot.snapshot_sha256,
        registry_event_set_sha256=event_set_sha,
        registry_ledger_head_sha256=registry_head.head_sha256,
        freeze_sha256=freeze.freeze_sha256,
        comparison_result_sha256=comparison.result_sha256,
        independent_review_sha256=review.attestation_sha256,
        operator_approval_sha256=approval.approval_sha256,
        debt_ledger_head_sha256=debt_head.head_sha256,
        archive_receipt_sha256=archive.receipt_sha256,
        artifact_set_sha256=H8,
        consumed_nonces=tuple(sorted((approval.nonce, review.nonce))),
        operator_counter=approval.monotonic_counter,
        reviewer_counter=review.monotonic_counter,
    )
    store = ContentAddressedRegistryStore(tmp_path / "registry")
    kwargs = {
        "snapshot": snapshot, "registry_events": events,
        "registry_ledger_head": registry_head, "debt_events": debt_events,
        "debt_ledger_head": debt_head, "freeze": freeze,
        "comparison_result": comparison, "independent_review": review,
        "operator_approval": approval, "archive_receipt": archive,
        "artifact_set_sha256": H8, "trusted_role_key_policy": policy,
        "revoked_key_ids": set(), "expected_subject_ids": ("canary.company.test",),
        "expected_subject_sha256s": (H1,), "expected_finding_set_sha256": H2,
        "fixed_now_utc": "2026-08-20T12:00:00Z",
    }
    return store, transaction, kwargs


def test_t_rr2_003_a_transaction_binds_full_authority_graph(tmp_path: Path):
    store, transaction, kwargs = transaction_fixture(tmp_path)
    head, receipt = store.commit_transaction(transaction, **kwargs)
    assert head.transaction_sha256 == transaction.transaction_sha256
    assert receipt.published_head_sha256 == head.head_sha256
    assert receipt.commit_state == "committed"


@pytest.mark.parametrize(
    "fault_stage",
    ["before_immutable_staging", "after_immutable_staging", "after_prepared_receipt", "before_head_swap"],
)
def test_t_rr2_003_b_crash_before_head_swap_leaves_current_unchanged(tmp_path: Path, fault_stage: str):
    store, transaction, kwargs = transaction_fixture(tmp_path)
    with pytest.raises(RuntimeError, match="crash"):
        store.commit_transaction(
            transaction, **kwargs,
            fault=lambda stage: (_ for _ in ()).throw(RuntimeError("crash")) if stage == fault_stage else None,
        )
    assert store.read_head() is None


def test_t_rr2_003_c_crash_after_swap_recovers_idempotently(tmp_path: Path):
    store, transaction, kwargs = transaction_fixture(tmp_path)
    with pytest.raises(RuntimeError, match="crash"):
        store.commit_transaction(
            transaction, **kwargs,
            fault=lambda stage: (_ for _ in ()).throw(RuntimeError("crash")) if stage == "after_head_swap" else None,
        )
    swapped = store.read_head()
    assert swapped is not None
    recovered, receipt = store.commit_transaction(transaction, **kwargs)
    assert recovered == swapped
    assert receipt.commit_state == "recovered"


def test_t_rr2_003_d_stale_writer_and_unbound_transaction_are_blocked(tmp_path: Path):
    store, transaction, kwargs = transaction_fixture(tmp_path)
    bad = RegistryTransaction.create(
        **{
            **transaction.model_dump(exclude={"transaction_sha256", "base_head_sha256", "artifact_set_sha256"}),
            "base_head_sha256": H1,
            "artifact_set_sha256": H2,
        }
    )
    with pytest.raises(CanaryGovernanceError, match="BA11_REGISTRY_CAS_CONFLICT"):
        store.commit_transaction(bad, **kwargs)
    with pytest.raises(CanaryGovernanceError, match="BA11_TRANSACTION_BINDING_INVALID"):
        store.commit_transaction(
            RegistryTransaction.create(
                **{
                    **transaction.model_dump(exclude={"transaction_sha256", "artifact_set_sha256"}),
                    "artifact_set_sha256": H2,
                }
            ),
            **kwargs,
        )


def test_t_rr2_014_a_manifest_preimage_and_detached_package_identity():
    first, manifest = build_deterministic_zip(
        {"b.txt": b"b\n", "a.txt": b"a\n"}, source_date_epoch=1787184000
    )
    second, other = build_deterministic_zip(
        {"b.txt": b"b\n", "a.txt": b"a\n"}, source_date_epoch=1787184000
    )
    assert first == second and manifest == other
    EvidenceManifest.model_validate(manifest)
    identity, sidecar = build_package_identity(
        first, package_filename="ROOM16_TEST.zip", manifest_sha256=manifest["manifest_sha256"]
    )
    assert identity.package_sha256.encode() in sidecar
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert archive.namelist() == ["MANIFEST.json", "a.txt", "b.txt"]
        assert all(((item.external_attr >> 16) & 0o777) == 0o644 for item in archive.infolist())


def test_contracts_reject_unknown_fields_and_hash_mutation():
    freeze = CanaryFreezeRecord.create(
        freeze_id="freeze.schema", canary_id="canary.company.schema",
        technical_baseline_sha256=H1, governance_envelope_sha256=H2,
        effective_at_utc="2026-08-20T00:00:00Z",
    )
    with pytest.raises(ValidationError):
        CanaryFreezeRecord(**{**freeze.model_dump(), "unknown": True})
    with pytest.raises(ValidationError):
        CanaryFreezeRecord(**{**freeze.model_dump(), "technical_baseline_sha256": H3})


def test_required_test_ids_are_materialized_for_evidence_mapping():
    required = {
        "T-RR2-001-A", "T-RR2-001-B", "T-RR2-001-C", "T-RR2-002-A",
        "T-RR2-002-B", "T-RR2-002-C", "T-RR2-002-D", "T-RR2-002-E",
        "T-RR2-003-A", "T-RR2-003-B", "T-RR2-003-C", "T-RR2-003-D",
        "T-RR2-004-A", "T-RR2-004-B", "T-RR2-004-C", "T-RR2-004-D",
        "T-RR2-004-E", "T-RR2-005-A", "T-RR2-005-B", "T-RR2-005-C",
        "T-RR2-006-A", "T-RR2-006-B", "T-RR2-007-A", "T-RR2-007-B",
        "T-RR2-007-C", "T-RR2-008-A", "T-RR2-008-B", "T-RR2-009-A",
        "T-RR2-009-B", "T-RR2-010-A", "T-RR2-010-B", "T-RR2-010-C",
        "T-RR2-011-A", "T-RR2-012-A", "T-RR2-012-B", "T-RR2-013-A",
        "T-RR2-014-A",
    }
    inventory = Path("research_agent/tests/ba11_r3_test_inventory.json")
    data = json.loads(inventory.read_text(encoding="utf-8"))
    assert {row["test_id"] for row in data["tests"]} == required
    assert all(row["diagnostic_or_expected"] for row in data["tests"])
