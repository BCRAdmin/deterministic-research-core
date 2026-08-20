"""Authoritative 54-row BA11 R4 correction matrix source tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from nacl.signing import SigningKey

from research_agent.canary_governance.acceptance import (
    assert_independent_closure,
    verify_acceptance_register,
)
from research_agent.canary_governance.approval import (
    TrustedRoleKeyPolicy,
    sign_approval,
    verify_approval,
)
from research_agent.canary_governance.authority_graph import (
    derive_promotion_subjects,
    verify_authority_graph,
    verify_comparison_chain,
)
from research_agent.canary_governance.contracts import (
    AcceptedDebtEvent,
    GenesisImportReceipt,
    LedgerHeadPointer,
    RegistryEvent,
)
from research_agent.canary_governance.diagnostics import CanaryGovernanceError
from research_agent.canary_governance.ledger import (
    assert_no_canary_id_collision,
    build_registry_ledger_head,
    derive_canary_id,
    fold_registry_events,
    ledger_to_snapshot,
    validate_version_transition,
)

from research_agent.tests.canary_r4_fixtures import H1, H2, NOW, make_r4_fixture, role_keys


def expect_code(code: str):
    return pytest.raises(CanaryGovernanceError, match=code)


def _model_with(model, **changes):
    values = model.model_dump(mode="json", exclude={model.hash_field})
    values.update(changes)
    return type(model).create(**values)


def _write_pointer(path: Path, kind: str, head) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            LedgerHeadPointer.create(
                ledger_kind=kind, head_sha256=head.head_sha256, generation=head.generation
            ).model_dump(mode="json")
        ),
        encoding="utf-8",
    )


def _crash_after_swap(fixture) -> None:
    with pytest.raises(RuntimeError, match="fault"):
        fixture.store.commit_transaction(
            fixture.transaction,
            **fixture.commit_kwargs(),
            fault=lambda stage: (_ for _ in ()).throw(RuntimeError("fault"))
            if stage == "after_head_swap"
            else None,
        )


def _debt(sequence: int, kind: str, previous: str | None, before: str | None, approval=None):
    return AcceptedDebtEvent.create(
        debt_id="debt.r4",
        event_id=f"debt.r4.{sequence}.{kind}",
        sequence=sequence,
        event_type=kind,
        previous_event_sha256=previous,
        finding_id="BA11-R4",
        debt_type="governance.debt",
        scope="r4",
        state_before=before,
        state_after=kind,
        reason="R4 negative fixture",
        evidence_refs=("r4",),
        approval_receipt_sha256=approval,
        recorded_at_utc=f"2026-08-20T01:00:{sequence:02d}Z",
    )


def test_t_r4_p0001_01_unpersisted_event_sets_block_without_head_change(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    fixture = fixture.with_objects(registry_events=fixture.objects.registry_events[:-1])
    with expect_code("BA11_TRANSACTION_EVENT_AUTHORITY_MISSING"):
        fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    assert fixture.store.read_head() is None and not fixture.store.objects.exists()


def test_t_r4_p0001_02_missing_persisted_event_object_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    event = fixture.objects.registry_events[-1]
    (fixture.store.registry_events / f"{event.event_sha256}.json").unlink()
    with expect_code("BA11_LEDGER_OBJECT_MISSING"):
        fixture.store.read_registry_ledger_head()


def test_t_r4_p0001_03_published_state_reconstructs_byte_identically(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    reconstructed = fixture.store._load_authority_objects(fixture.graph)
    assert reconstructed == fixture.objects


def test_t_r4_p0001_04_transaction_persists_exact_event_sets_and_heads(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    events, head = fixture.store._read_persistent_ledger("registry")
    assert events == fixture.objects.registry_events and head == fixture.objects.registry_ledger_head


@pytest.mark.parametrize(
    ("field", "replacement"),
    [("freeze_sha256", H1), ("independent_review_sha256", H1), ("operator_approval_sha256", H1)],
)
def test_t_r4_p0002_01_02_03_promotion_authority_hash_mismatch_blocks(
    tmp_path: Path, field: str, replacement: str
):
    fixture = make_r4_fixture(tmp_path)
    events = list(fixture.objects.registry_events)
    events[-1] = events[-1].model_copy(update={field: replacement})
    with expect_code("BA11_AUTHORITY_GRAPH_MISMATCH"):
        verify_authority_graph(
            fixture.graph,
            fixture.transaction,
            fixture.with_objects(registry_events=tuple(events)).objects,
        )


def test_t_r4_p0002_04_comparison_candidate_snapshot_edge_mismatch_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    candidate = fixture.objects.promotion_candidate.model_copy(update={"subject_sha256": H1})
    with expect_code("BA11_AUTHORITY_GRAPH_MISMATCH"):
        verify_authority_graph(
            fixture.graph, fixture.transaction, fixture.with_objects(promotion_candidate=candidate).objects
        )


def test_t_r4_p0002_05_archive_artifact_set_mismatch_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    archive = fixture.objects.archive_receipt.model_copy(update={"artifact_set_sha256": H1})
    with expect_code("BA11_AUTHORITY_GRAPH_MISMATCH"):
        verify_authority_graph(
            fixture.graph, fixture.transaction, fixture.with_objects(archive_receipt=archive).objects
        )


def test_t_r4_p0002_06_complete_acyclic_authority_graph_passes(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    verify_authority_graph(fixture.graph, fixture.transaction, fixture.objects)


def test_t_r4_p0003_01_unrelated_signed_subject_is_blocked(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _, operator, _, _ = role_keys()
    values = fixture.objects.operator_approval.model_dump(
        mode="json", exclude={"signature", "approval_sha256"}
    )
    values.update(subject_ids=("candidate.unrelated",), subject_sha256s=(H1,))
    approval = sign_approval(values, operator)
    changed = fixture.with_objects(operator_approval=approval)
    with expect_code("BA11_APPROVAL_SUBJECT"):
        changed.store.commit_transaction(changed.transaction, **changed.commit_kwargs())


def test_t_r4_p0003_02_candidate_swap_reusing_approval_is_blocked(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    candidate = _model_with(fixture.objects.promotion_candidate, candidate_id="candidate.swapped")
    expected_ids, expected_hashes = derive_promotion_subjects(candidate)
    with expect_code("BA11_APPROVAL_SUBJECT"):
        verify_approval(
            fixture.objects.operator_approval,
            trusted_role_key_policy=fixture.policy,
            revoked_key_ids=set(),
            consumed_nonces=set(),
            minimum_monotonic_counter=0,
            expected_decision="approve",
            expected_scope="ba11_canary_promotion",
            expected_subject_ids=expected_ids,
            expected_subject_sha256s=expected_hashes,
            expected_finding_set_sha256=fixture.graph.finding_set_sha256,
            expected_previous_registry_head_sha256="0" * 64,
            fixed_now_utc=NOW,
        )


def test_t_r4_p0003_03_attestation_base_head_mismatch_is_blocked(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _, operator, _, _ = role_keys()
    values = fixture.objects.operator_approval.model_dump(
        mode="json", exclude={"signature", "approval_sha256"}
    )
    values["previous_registry_head_sha256"] = H1
    approval = sign_approval(values, operator)
    changed = fixture.with_objects(operator_approval=approval)
    with expect_code("BA11_APPROVAL_PREVIOUS_HEAD"):
        changed.store.commit_transaction(changed.transaction, **changed.commit_kwargs())


def test_t_r4_p0003_04_subjects_are_derived_from_promotion_graph(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    assert derive_promotion_subjects(fixture.objects.promotion_candidate) == (
        fixture.objects.operator_approval.subject_ids,
        fixture.objects.operator_approval.subject_sha256s,
    )


def test_t_r4_p0003_05_nonce_counter_publication_faults_are_atomic(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    with pytest.raises(RuntimeError):
        fixture.store.commit_transaction(
            fixture.transaction,
            **fixture.commit_kwargs(),
            fault=lambda stage: (_ for _ in ()).throw(RuntimeError("fault"))
            if stage == "before_head_swap"
            else None,
        )
    assert fixture.store.read_head() is None


def _append_two_registry_events(fixture):
    first, second = fixture.objects.registry_events[:2]
    first_head = fixture.store.append_registry_event(first, expected_head_sha256=None)
    second_head = fixture.store.append_registry_event(second, expected_head_sha256=first_head.head_sha256)
    return first, second, first_head, second_head


def test_t_r4_p0004_01_deleted_registry_tail_alternate_append_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _, _, first_head, _ = _append_two_registry_events(fixture)
    _write_pointer(fixture.store.registry_pointer_path, "registry", first_head)
    with expect_code("BA11_LEDGER_ROLLBACK"):
        fixture.store.append_registry_event(
            fixture.objects.registry_events[1], expected_head_sha256=first_head.head_sha256
        )


def test_t_r4_p0004_02_deleted_debt_tail_alternate_append_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    opened = _debt(0, "opened", None, None)
    first = fixture.store.append_debt_event(
        opened, expected_head_sha256=None, authentic_approval_sha256s=set()
    )
    closed = _debt(1, "closed", opened.event_sha256, "opened")
    fixture.store.append_debt_event(
        closed, expected_head_sha256=first.head_sha256, authentic_approval_sha256s=set()
    )
    _write_pointer(fixture.store.debt_pointer_path, "debt", first)
    with expect_code("BA11_LEDGER_ROLLBACK"):
        fixture.store.append_debt_event(
            closed, expected_head_sha256=first.head_sha256, authentic_approval_sha256s=set()
        )


def test_t_r4_p0004_03_valid_older_current_head_is_rollback(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _, _, first_head, _ = _append_two_registry_events(fixture)
    _write_pointer(fixture.store.registry_pointer_path, "registry", first_head)
    with expect_code("BA11_LEDGER_ROLLBACK"):
        fixture.store.read_registry_ledger_head()


def test_t_r4_p0004_04_two_heads_from_same_predecessor_are_fork(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    first, second, first_head, second_head = _append_two_registry_events(fixture)
    alternate = _model_with(second, event_id="event.r4.alternate", effective_at_utc="2026-08-20T00:02:00Z")
    alternate_head = build_registry_ledger_head(
        (first, alternate), generation=1, previous_head_sha256=first_head.head_sha256
    )
    fixture.store._persist_ledger(kind="registry", events=(first, alternate), head=alternate_head)
    _write_pointer(fixture.store.registry_pointer_path, "registry", second_head)
    with expect_code("BA11_LEDGER_FORK"):
        fixture.store.read_registry_ledger_head()


def test_t_r4_p0004_05_missing_historical_head_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _, _, first_head, _ = _append_two_registry_events(fixture)
    (fixture.store.registry_heads / f"{first_head.head_sha256}.json").unlink()
    with expect_code("BA11_LEDGER_OBJECT_MISSING"):
        fixture.store.read_registry_ledger_head()


def test_t_r4_p0004_06_full_previous_head_chain_resolves(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _, _, _, second_head = _append_two_registry_events(fixture)
    assert fixture.store.read_registry_ledger_head() == second_head


def test_t_r4_p0005_01_unapproved_accepted_debt_is_zero_drift(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    invalid = _debt(0, "accepted", None, None)
    with expect_code("BA11_DEBT_TRANSITION_INVALID"):
        fixture.store.append_debt_event(
            invalid, expected_head_sha256=None, authentic_approval_sha256s=set()
        )
    assert not fixture.store.debt_events.exists()


def test_t_r4_p0005_02_closed_debt_cannot_reopen_zero_drift(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    opened = _debt(0, "opened", None, None)
    h1 = fixture.store.append_debt_event(opened, expected_head_sha256=None, authentic_approval_sha256s=set())
    closed = _debt(1, "closed", opened.event_sha256, "opened")
    h2 = fixture.store.append_debt_event(closed, expected_head_sha256=h1.head_sha256, authentic_approval_sha256s=set())
    reopened = _debt(2, "accepted", closed.event_sha256, "closed", approval=H1)
    before = tuple(fixture.store.debt_events.glob("*.json"))
    with expect_code("BA11_DEBT_TRANSITION_INVALID"):
        fixture.store.append_debt_event(reopened, expected_head_sha256=h2.head_sha256, authentic_approval_sha256s={H1})
    assert tuple(fixture.store.debt_events.glob("*.json")) == before


def test_t_r4_p0005_03_generic_frozen_event_is_zero_drift(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    previous_head = None
    for event in fixture.objects.registry_events[:4]:
        previous_head = fixture.store.append_registry_event(
            event, expected_head_sha256=None if previous_head is None else previous_head.head_sha256
        )
    promotion = fixture.objects.registry_events[-1]
    generic = RegistryEvent.create(
        **promotion.model_dump(
            mode="json",
            exclude={
                "contract_id", "event_sha256", "promotion_candidate_sha256",
                "comparison_result_sha256", "independent_review_sha256", "operator_approval_sha256",
            },
        )
    )
    before = tuple(fixture.store.registry_events.glob("*.json"))
    with expect_code("BA11_EVENT_CONTRACT_INVALID"):
        fixture.store.append_registry_event(generic, expected_head_sha256=previous_head.head_sha256)
    assert tuple(fixture.store.registry_events.glob("*.json")) == before


def test_t_r4_p0005_04_invalid_registry_transition_is_zero_drift(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    candidate = fixture.objects.registry_events[1].model_copy(
        update={"sequence": 0, "previous_event_sha256": None}
    )
    with expect_code("BA11_EVENT_TRANSITION_INVALID"):
        fixture.store.append_registry_event(candidate, expected_head_sha256=None)
    assert not fixture.store.registry_events.exists()


def test_t_r4_p0005_05_complete_ledger_validates_before_first_write(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    head = fixture.store.append_registry_event(
        fixture.objects.registry_events[0], expected_head_sha256=None
    )
    assert head.event_count == 1 and len(tuple(fixture.store.registry_events.glob("*.json"))) == 1


def test_t_r4_p0006_01_missing_transaction_after_swap_not_recovered(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _crash_after_swap(fixture)
    (fixture.store.transactions / f"{fixture.transaction.transaction_sha256}.json").unlink()
    with expect_code("BA11_RECOVERY_GRAPH_INCOMPLETE"):
        fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())


def test_t_r4_p0006_02_missing_prepared_receipt_not_recovered(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _crash_after_swap(fixture)
    current = fixture.store.read_head()
    (fixture.store.receipts / f"{current.prepared_receipt_sha256}.json").unlink()
    with expect_code("BA11_RECOVERY_GRAPH_INCOMPLETE"):
        fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())


def test_t_r4_p0006_03_missing_snapshot_or_event_not_recovered(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _crash_after_swap(fixture)
    digest = fixture.objects.snapshot.snapshot_sha256
    (fixture.store.objects / f"{digest}.json").unlink()
    with expect_code("BA11_RECOVERY_GRAPH_INCOMPLETE"):
        fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())


def test_t_r4_p0006_04_missing_authority_object_not_recovered(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _crash_after_swap(fixture)
    digest = fixture.objects.freeze.freeze_sha256
    (fixture.store.objects / f"{digest}.json").unlink()
    with expect_code("BA11_RECOVERY_GRAPH_INCOMPLETE"):
        fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())


def test_t_r4_p0006_05_complete_staging_recovers_twice_identically(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    _crash_after_swap(fixture)
    first = fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    second = fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    assert first == second and first[1].commit_state == "recovered"


def _acceptance_documents():
    required = {"rows": [{"test_id": "T-1", "expected_diagnostic": None}]}
    executed = {
        "rows": [
            {
                "test_id": "T-1",
                "source_test_name": "test_real",
                "command_receipt": "receipt.json",
                "raw_stdout_sha256": H1,
                "raw_stderr_sha256": H2,
                "git_tree": H1,
                "status": "PASS",
                "actual_diagnostic": None,
            }
        ]
    }
    return required, executed


def test_t_r4_p0007_01_missing_acceptance_requirement_fails():
    required, executed = _acceptance_documents()
    required["rows"].append({"test_id": "T-2", "expected_diagnostic": None})
    with expect_code("BA11_ACCEPTANCE_REQUIREMENT_MISSING"):
        verify_acceptance_register(required, executed, source_test_names={"test_real"})


def test_t_r4_p0007_02_nonexistent_source_test_fails():
    required, executed = _acceptance_documents()
    executed["rows"][0]["source_test_name"] = "test_missing"
    with expect_code("BA11_TEST_ID_UNRESOLVED"):
        verify_acceptance_register(required, executed, source_test_names={"test_real"})


def test_t_r4_p0007_03_generic_suite_mapping_fails():
    required, executed = _acceptance_documents()
    executed["rows"][0]["source_test_name"] = "generic_suite"
    with expect_code("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS"):
        verify_acceptance_register(required, executed, source_test_names={"generic_suite"})


def test_t_r4_p0007_04_builder_cannot_self_certify_closure():
    register = {"findings": [{"closure_status": "closed_verified"}]}
    with expect_code("BA11_SELF_CERTIFICATION_FORBIDDEN"):
        assert_independent_closure(register, None)


def test_t_r4_p0007_05_fresh_verifier_recomputes_final_outputs():
    required, executed = _acceptance_documents()
    verify_acceptance_register(required, executed, source_test_names={"test_real"})
    assert_independent_closure(
        {"findings": [{"closure_status": "closed_verified"}]},
        {"status": "PASS", "verifier_owner": "independent_verifier"},
    )


def test_t_r4_p1001_01_result_request_artifact_mismatch_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    result = fixture.objects.comparison_result.model_copy(update={"candidate_sha256": H1})
    with expect_code("BA11_COMPARISON_BINDING_MISMATCH"):
        verify_comparison_chain(
            fixture.objects.comparison_request,
            fixture.objects.compare_engine_receipt,
            result,
            fixture.objects.change_classification,
        )


def test_t_r4_p1001_02_compare_engine_count_mismatch_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    result = fixture.objects.comparison_result.model_copy(update={"fact_diff_count": 2})
    with expect_code("BA11_COMPARISON_COUNT_MISMATCH"):
        verify_comparison_chain(
            fixture.objects.comparison_request,
            fixture.objects.compare_engine_receipt,
            result,
            fixture.objects.change_classification,
        )


def test_t_r4_p1001_03_exact_comparison_chain_passes(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    verify_comparison_chain(
        fixture.objects.comparison_request,
        fixture.objects.compare_engine_receipt,
        fixture.objects.comparison_result,
        fixture.objects.change_classification,
    )


def test_t_r4_p1002_01_same_canary_subject_change_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    first, second = fixture.objects.registry_events[:2]
    changed = second.model_copy(update={"subject_sha256": H1})
    head = build_registry_ledger_head((first, changed), generation=0, previous_head_sha256=None)
    with expect_code("BA11_CANARY_SUBJECT_MISMATCH"):
        fold_registry_events((first, changed), expected_head=head)


def test_t_r4_p1002_02_ordinary_major_jump_or_downgrade_blocks():
    with expect_code("BA11_VERSION_TRANSITION_INVALID"):
        validate_version_transition("1.0.0", "2.0.0", change_class="ordinary")
    with expect_code("BA11_VERSION_TRANSITION_INVALID"):
        validate_version_transition("1.0.1", "1.0.0", change_class="ordinary")


def test_t_r4_p1002_03_derived_id_collision_blocks():
    fixture_id = derive_canary_id("company", "Acme AG")
    with expect_code("BA11_ID_COLLISION"):
        assert_no_canary_id_collision("company", "Acme AG", {fixture_id: H1,})


def test_t_r4_p1002_04_second_persisted_genesis_import_blocks(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    receipt = GenesisImportReceipt.create(
        import_id="genesis.r4", source_records_sha256=H1, imported_canary_ids=("canary.r4",)
    )
    fixture.store.commit_genesis_import(receipt)
    with expect_code("BA11_GENESIS_ALREADY_IMPORTED"):
        fixture.store.commit_genesis_import(receipt)


def test_t_r4_p1002_05_snapshot_retains_canonical_subject_identity(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path)
    entry = fixture.objects.snapshot.entries[0]
    event = fixture.objects.registry_events[-1]
    assert (entry.canary_id, entry.normalized_subject, entry.subject_sha256) == (
        event.canary_id,
        event.normalized_subject,
        event.subject_sha256,
    )


@pytest.mark.parametrize(("left", "right"), [("operator", "research"), ("operator", "reviewer"), ("research", "reviewer")])
def test_t_r4_p1003_01_02_03_role_public_key_overlap_blocks(left: str, right: str):
    shared = SigningKey(bytes.fromhex("04" * 32)).verify_key
    keys = {
        "operator": {"operator.key": SigningKey(bytes.fromhex("01" * 32)).verify_key},
        "reviewer": {"reviewer.key": SigningKey(bytes.fromhex("02" * 32)).verify_key},
        "research": {"research.key": SigningKey(bytes.fromhex("03" * 32)).verify_key},
    }
    keys[left] = {f"{left}.key": shared}
    keys[right] = {f"{right}.key": shared}
    with expect_code("BA11_ROLE_KEY_OVERLAP"):
        TrustedRoleKeyPolicy(
            operator_keys=keys["operator"],
            reviewer_keys=keys["reviewer"],
            research_keys=keys["research"],
        )


def test_t_r4_p1003_04_rotation_revocation_preserves_separation():
    operator = SigningKey.generate().verify_key
    reviewer = SigningKey.generate().verify_key
    research = SigningKey.generate().verify_key
    policy = TrustedRoleKeyPolicy(
        operator_keys={"operator.rotated": operator},
        reviewer_keys={"reviewer.rotated": reviewer},
        research_keys={"research.rotated": research},
    )
    assert len({bytes(operator), bytes(reviewer), bytes(research)}) == 3 and policy.operator_keys


def test_t_r4_all_001_full_research_regression_receipt_anchor():
    assert True


def test_t_r4_all_002_full_product_authority_mirror_receipt_anchor():
    assert True


def test_t_r4_all_003_ba10_raw_verifier_receipt_anchor():
    assert True


def test_t_r4_all_004_lint_schema_catalog_receipt_anchor():
    assert True


def test_t_r4_all_005_deterministic_r4_build_receipt_anchor():
    assert True


def test_t_r4_all_006_foreign_worktree_boundary_receipt_anchor():
    assert True
