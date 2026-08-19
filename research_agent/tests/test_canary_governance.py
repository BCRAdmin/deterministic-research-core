from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from nacl.signing import SigningKey
from pydantic import ValidationError

from research_agent.canary_governance.approval import sign_approval, verify_approval
from research_agent.canary_governance.archive import build_deterministic_zip
from research_agent.canary_governance.contracts import (
    CONTRACT_MODELS,
    AcceptedDebtEvent,
    CanaryFreezeRecord,
    ChangeClassification,
    DebtMembership,
    GenesisImportReceipt,
    GovernanceEnvelope,
    RegistryEvent,
    RegistrySnapshot,
    SourceContractLock,
    TechnicalBaseline,
)
from research_agent.canary_governance.diagnostics import CanaryGovernanceError
from research_agent.canary_governance.ledger import (
    derive_canary_id,
    fold_registry_events,
    mirror_receipt,
    validate_version_transition,
    verify_debt_ledger,
)
from research_agent.canary_governance.storage import ContentAddressedRegistryStore

H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
H5 = "5" * 64
H6 = "6" * 64
H7 = "7" * 64
H8 = "8" * 64


def _event(*, sequence: int, event_type: str, previous: str | None, subject: str = H1):
    return RegistryEvent.create(
        event_id=f"event.{sequence}",
        canary_id="canary.company.test",
        sequence=sequence,
        event_type=event_type,
        subject_sha256=subject,
        previous_event_sha256=previous,
        effective_at_utc=f"2026-08-19T00:00:{sequence:02d}Z",
    )


def _debt(*, sequence: int, event_type: str, previous: str | None, before: str | None, after: str):
    return AcceptedDebtEvent.create(
        debt_id="debt.test",
        event_id=f"debt.event.{sequence}",
        sequence=sequence,
        event_type=event_type,
        previous_event_sha256=previous,
        finding_id="RC1FE5-015",
        debt_type="ux.nonblocking",
        scope="renderer",
        state_before=before,
        state_after=after,
        reason="accepted historical debt",
        evidence_refs=("evidence.test",),
        approval_receipt_sha256=H2 if event_type == "accepted" else None,
        recorded_at_utc=f"2026-08-19T00:01:{sequence:02d}Z",
    )


def test_freeze_is_immutable_and_rejects_future_state_fields():
    freeze = CanaryFreezeRecord.create(
        freeze_id="freeze.test",
        canary_id="canary.company.test",
        technical_baseline_sha256=H1,
        governance_envelope_sha256=H2,
        registry_snapshot_sha256=H3,
        effective_at_utc="2026-08-19T00:00:00Z",
    )
    assert freeze.contract_id == "room16.canary_freeze"
    assert freeze.compatibility == "first_contract_no_predecessor"
    with pytest.raises(ValidationError):
        CanaryFreezeRecord(**{**freeze.model_dump(), "stale_state": "stale"})
    with pytest.raises(ValidationError, match="freeze_sha256 mismatch"):
        CanaryFreezeRecord(**{**freeze.model_dump(), "technical_baseline_sha256": H4})


def test_technical_identity_is_separate_from_governance_identity():
    technical = TechnicalBaseline.create(
        canary_id="canary.company.test",
        baseline_version="1.0.0",
        foundation_version_lock_sha256=H1,
        registry_authority_sha256=H2,
        semantic_wave_version_lock_sha256=H3,
        ba10_freeze_identity_sha256=H4,
        compiler_artifact_bundle_contract="room16.compiler_artifact_bundle@1",
        source_contract_lock_sha256=H5,
        consumer_semantic_lock_sha256=H6,
        presentation_contract_sha256=H7,
        renderer_artifact_sha256=H8,
        artifact_set_sha256=H1,
        semantic_output_sha256=H2,
    )
    first = GovernanceEnvelope.create(
        technical_baseline_sha256=technical.technical_baseline_sha256,
        accepted_debt_set_sha256=H1,
        change_classification_sha256=H2,
        independent_review_sha256=H3,
        operator_approval_sha256=H4,
        previous_registry_head_sha256=None,
    )
    second = GovernanceEnvelope.create(
        technical_baseline_sha256=technical.technical_baseline_sha256,
        accepted_debt_set_sha256=H1,
        change_classification_sha256=H2,
        independent_review_sha256=H5,
        operator_approval_sha256=H6,
        previous_registry_head_sha256=None,
    )
    assert first.technical_baseline_sha256 == second.technical_baseline_sha256
    assert first.governance_envelope_sha256 != second.governance_envelope_sha256


def test_source_contract_lock_is_required_and_hash_bound():
    lock = SourceContractLock.create(
        source_contract_ids=("room16.source.alpha", "room16.source.beta"),
        source_contract_sha256s=(H1, H2),
    )
    assert len(lock.lock_sha256) == 64
    with pytest.raises(ValidationError):
        SourceContractLock.create(
            source_contract_ids=("room16.source.beta", "room16.source.alpha"),
            source_contract_sha256s=(H1, H2),
        )


def test_registry_fold_is_append_only_and_transition_checked():
    genesis = _event(sequence=0, event_type="genesis", previous=None)
    candidate = _event(sequence=1, event_type="candidate", previous=genesis.event_sha256)
    reviewed = _event(sequence=2, event_type="review_accepted", previous=candidate.event_sha256)
    approved = _event(sequence=3, event_type="operator_approved", previous=reviewed.event_sha256)
    frozen = _event(sequence=4, event_type="frozen", previous=approved.event_sha256)
    stale = _event(sequence=5, event_type="stale", previous=frozen.event_sha256)
    assert fold_registry_events((genesis, candidate, reviewed, approved, frozen, stale)) == {
        "canary.company.test": "stale"
    }
    with pytest.raises(CanaryGovernanceError, match="BA11_EVENT_TRANSITION_INVALID"):
        fold_registry_events((genesis, _event(sequence=1, event_type="frozen", previous=genesis.event_sha256)))
    with pytest.raises(CanaryGovernanceError, match="BA11_DUPLICATE_ID"):
        fold_registry_events((genesis, genesis))
    forked = _event(sequence=2, event_type="review_accepted", previous=genesis.event_sha256)
    with pytest.raises(CanaryGovernanceError, match="BA11_EVENT_CHAIN_BROKEN"):
        fold_registry_events((genesis, candidate, forked))


def test_product_mirror_failure_never_changes_research_state():
    receipt = mirror_receipt(
        research_snapshot_sha256=H1,
        mirrored_snapshot_sha256=H2,
        product_commit="a" * 40,
    )
    assert receipt.receipt_state == "consumer_mirror_invalid"
    genesis = _event(sequence=0, event_type="genesis", previous=None)
    assert fold_registry_events((genesis,))["canary.company.test"] == "genesis"


def test_debt_events_are_append_only_and_membership_is_separate():
    opened = _debt(sequence=0, event_type="opened", previous=None, before=None, after="opened")
    accepted = _debt(
        sequence=1,
        event_type="accepted",
        previous=opened.event_sha256,
        before="opened",
        after="accepted",
    )
    closed = _debt(
        sequence=2,
        event_type="closed",
        previous=accepted.event_sha256,
        before="accepted",
        after="closed",
    )
    assert verify_debt_ledger((opened, accepted, closed))["debt.test"] == "closed"
    membership = DebtMembership.create(freeze_sha256=H1, debt_ids=("debt.test",))
    assert membership.debt_ids == ("debt.test",)
    with pytest.raises(CanaryGovernanceError, match="BA11_EVENT_CHAIN_BROKEN"):
        verify_debt_ledger((opened, closed))
    with pytest.raises(ValidationError, match="event_sha256 mismatch"):
        AcceptedDebtEvent(**{**accepted.model_dump(), "reason": "mutated history"})


def test_deterministic_canary_id_and_semver_rules():
    assert derive_canary_id("company", "WM") == derive_canary_id("company", "WM")
    validate_version_transition(None, "1.0.0", genesis=True)
    validate_version_transition("1.0.0", "1.0.1")
    validate_version_transition("1.0.1", "1.1.0")
    with pytest.raises(CanaryGovernanceError, match="BA11_VERSION_TRANSITION_INVALID"):
        validate_version_transition("1.0.0", "1.0.2")


def test_ordinary_change_requires_independent_no_new_truth():
    ChangeClassification.create(
        classification_id="change.presentation",
        change_class="ordinary",
        semantic_lock_changed=False,
        presentation_contract_changed=False,
        renderer_artifact_changed=True,
        source_contract_changed=False,
        new_truth_count=0,
        lineage_diff_count=0,
        independent_compare_sha256=H1,
    )
    with pytest.raises(ValidationError):
        ChangeClassification.create(
            classification_id="change.forged",
            change_class="ordinary",
            semantic_lock_changed=False,
            presentation_contract_changed=False,
            renderer_artifact_changed=True,
            source_contract_changed=False,
            new_truth_count=1,
            lineage_diff_count=0,
            independent_compare_sha256=H1,
        )


def test_ed25519_approval_replay_scope_expiry_and_tamper():
    key = SigningKey.generate()
    values = {
        "approval_id": "approval.test",
        "decision": "approve",
        "scope": "ba11_correction_execution",
        "subject_ids": ("subject.test",),
        "subject_sha256s": (H1,),
        "review_finding_set_sha256": H2,
        "previous_registry_head_sha256": H3,
        "approver_key_id": "operator.primary",
        "issued_at_utc": "2026-08-19T00:00:00Z",
        "expires_at_utc": "2026-08-20T00:00:00Z",
        "nonce": "0123456789abcdef",
        "monotonic_counter": 7,
    }
    receipt = sign_approval(values, key)
    verify_approval(
        receipt,
        trusted_keys={"operator.primary": key.verify_key},
        revoked_key_ids=set(),
        consumed_nonces=set(),
        minimum_counter=6,
        expected_scope="ba11_correction_execution",
        expected_subject_sha256s=(H1,),
        now_utc="2026-08-19T12:00:00Z",
    )
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_REPLAY"):
        verify_approval(
            receipt,
            trusted_keys={"operator.primary": key.verify_key},
            revoked_key_ids=set(),
            consumed_nonces={receipt.nonce},
            minimum_counter=6,
            expected_scope="ba11_correction_execution",
            expected_subject_sha256s=(H1,),
            now_utc="2026-08-19T12:00:00Z",
        )
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_SCOPE"):
        verify_approval(
            receipt,
            trusted_keys={"operator.primary": key.verify_key},
            revoked_key_ids=set(),
            consumed_nonces=set(),
            minimum_counter=6,
            expected_scope="ba11_canary_promotion",
            expected_subject_sha256s=(H1,),
            now_utc="2026-08-19T12:00:00Z",
        )
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_EXPIRED"):
        verify_approval(
            receipt,
            trusted_keys={"operator.primary": key.verify_key},
            revoked_key_ids=set(),
            consumed_nonces=set(),
            minimum_counter=6,
            expected_scope="ba11_correction_execution",
            expected_subject_sha256s=(H1,),
            now_utc="2026-08-20T00:00:00Z",
        )
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_SIGNATURE"):
        verify_approval(
            receipt.model_copy(update={"signature": "0" * 128}),
            trusted_keys={"operator.primary": key.verify_key},
            revoked_key_ids=set(),
            consumed_nonces=set(),
            minimum_counter=6,
            expected_scope="ba11_correction_execution",
            expected_subject_sha256s=(H1,),
            now_utc="2026-08-19T12:00:00Z",
        )
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_SIGNATURE"):
        verify_approval(
            receipt,
            trusted_keys={"operator.primary": SigningKey.generate().verify_key},
            revoked_key_ids=set(),
            consumed_nonces=set(),
            minimum_counter=6,
            expected_scope="ba11_correction_execution",
            expected_subject_sha256s=(H1,),
            now_utc="2026-08-19T12:00:00Z",
        )
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_REVOKED"):
        verify_approval(
            receipt,
            trusted_keys={"operator.primary": key.verify_key},
            revoked_key_ids={"operator.primary"},
            consumed_nonces=set(),
            minimum_counter=6,
            expected_scope="ba11_correction_execution",
            expected_subject_sha256s=(H1,),
            now_utc="2026-08-19T12:00:00Z",
        )
    with pytest.raises(CanaryGovernanceError, match="BA11_APPROVAL_SCOPE"):
        verify_approval(
            receipt,
            trusted_keys={"operator.primary": key.verify_key},
            revoked_key_ids=set(),
            consumed_nonces=set(),
            minimum_counter=6,
            expected_scope="ba11_correction_execution",
            expected_subject_sha256s=(H2,),
            now_utc="2026-08-19T12:00:00Z",
        )


def test_registry_commit_is_atomic_and_compare_and_swap(tmp_path: Path):
    store = ContentAddressedRegistryStore(tmp_path / "registry")
    first = RegistrySnapshot.create(
        registry_generation=0,
        previous_registry_sha256=None,
        ledger_head_sha256=H1,
        entries=(),
    )
    with pytest.raises(RuntimeError, match="crash"):
        store.commit_snapshot(
            first,
            expected_head_sha256=None,
            fault=lambda step: (_ for _ in ()).throw(RuntimeError("crash"))
            if step == "before_pointer_swap"
            else None,
        )
    assert store.read_head() is None
    head = store.commit_snapshot(first, expected_head_sha256=None)
    second = RegistrySnapshot.create(
        registry_generation=1,
        previous_registry_sha256=first.snapshot_sha256,
        ledger_head_sha256=H2,
        entries=(),
    )
    with pytest.raises(CanaryGovernanceError, match="BA11_REGISTRY_CAS_CONFLICT"):
        store.commit_snapshot(second, expected_head_sha256=H3)
    assert store.read_head() == head
    stale_snapshot = RegistrySnapshot.create(
        registry_generation=1,
        previous_registry_sha256=H4,
        ledger_head_sha256=H2,
        entries=(),
    )
    with pytest.raises(CanaryGovernanceError, match="BA11_REGISTRY_PREDECESSOR_INVALID"):
        store.commit_snapshot(stale_snapshot, expected_head_sha256=head.head_sha256)
    assert store.read_head() == head


def test_schema_downgrade_unknown_fields_and_genesis_duplicates_fail_closed():
    freeze = CanaryFreezeRecord.create(
        freeze_id="freeze.schema",
        canary_id="canary.company.schema",
        technical_baseline_sha256=H1,
        governance_envelope_sha256=H2,
        registry_snapshot_sha256=H3,
        effective_at_utc="2026-08-19T00:00:00Z",
    )
    with pytest.raises(ValidationError):
        CanaryFreezeRecord(**{**freeze.model_dump(), "schema_version": 0})
    with pytest.raises(ValidationError):
        CanaryFreezeRecord(**{**freeze.model_dump(), "unknown": True})
    with pytest.raises(ValidationError, match="unique and sorted"):
        GenesisImportReceipt.create(
            import_id="genesis.import",
            source_records_sha256=H1,
            imported_canary_ids=("canary.company.same", "canary.company.same"),
        )
    with pytest.raises(ValidationError):
        GenesisImportReceipt.create(
            import_id="genesis.second",
            source_records_sha256=H1,
            imported_canary_ids=("canary.company.one",),
            second_import_allowed=True,
        )


def test_deterministic_archive_and_manifest_self_exclusion():
    members = {"b.txt": b"b\n", "a.txt": b"a\n"}
    first, manifest = build_deterministic_zip(members, source_date_epoch=1787097600)
    second, other = build_deterministic_zip(members, source_date_epoch=1787097600)
    assert first == second
    assert manifest == other
    assert manifest["self_excluded"] is True
    assert manifest["payload_rule"] == "all members except MANIFEST.json"
    changed, _ = build_deterministic_zip(
        {"b.txt": b"different bytes\n", "a.txt": b"a\n"},
        source_date_epoch=1787097600,
    )
    assert changed != first
    with zipfile.ZipFile(io.BytesIO(first)) as z:
        assert z.namelist() == ["MANIFEST.json", "a.txt", "b.txt"]
        assert all(((i.external_attr >> 16) & 0o777) == 0o644 for i in z.infolist())


def test_contract_catalog_has_all_required_machine_contracts():
    ids = {model.model_fields["contract_id"].default for model in CONTRACT_MODELS}
    required = {
        "room16.canary_registry_entry",
        "room16.canary_registry_snapshot",
        "room16.canary_registry_head",
        "room16.canary_genesis_import",
        "room16.canary_change_classification",
        "room16.canary_comparison_request",
        "room16.canary_comparison_result",
        "room16.canary_promotion_candidate",
        "room16.canary_independent_review_attestation",
        "room16.canary_operator_approval",
        "room16.canary_registry_event",
        "room16.canary_freeze",
        "room16.canary_accepted_debt_event",
        "room16.canary_debt_membership",
        "room16.canary_debt_resolution",
        "room16.canary_archive_receipt",
        "room16.canary_registry_transaction",
    }
    assert required <= ids
    assert "release_candidate" not in json.dumps(
        [model.model_json_schema() for model in CONTRACT_MODELS], sort_keys=True
    )
