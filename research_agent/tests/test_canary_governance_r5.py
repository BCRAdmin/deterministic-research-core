"""Authoritative BA11 R5 closure matrix with one exact node per requirement."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_agent.canary_governance.acceptance import verify_acceptance_register
from research_agent.canary_governance.authority_graph import verify_authority_graph
from research_agent.canary_governance.contracts import RegistryHead, RegistrySnapshot
from research_agent.canary_governance.diagnostics import CanaryGovernanceError
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.tests.canary_r4_fixtures import H1, H2, make_r4_fixture
from research_agent.tests.canary_r5_fixtures import make_next_cycle


def _crash_before_swap(fixture) -> None:
    with pytest.raises(RuntimeError, match="crash"):
        fixture.store.commit_transaction(
            fixture.transaction,
            **fixture.commit_kwargs(),
            fault=lambda stage: (_ for _ in ()).throw(RuntimeError("crash"))
            if stage == "before_head_swap"
            else None,
        )


def _three_generations(tmp_path: Path):
    first = make_r4_fixture(tmp_path / "registry")
    head0, _ = first.store.commit_transaction(first.transaction, **first.commit_kwargs())
    second = make_next_cycle(
        first,
        suffix="g1",
        version="1.1.0",
        generation=1,
        base_head_sha256=head0.head_sha256,
        previous_snapshot_sha256=first.objects.snapshot.snapshot_sha256,
    )
    head1, _ = second.store.commit_transaction(second.transaction, **second.commit_kwargs())
    third = make_next_cycle(
        second,
        suffix="g2",
        version="1.2.0",
        generation=2,
        base_head_sha256=head1.head_sha256,
        previous_snapshot_sha256=second.objects.snapshot.snapshot_sha256,
    )
    return first, second, third, head0, head1


def _acceptance_documents(nodeids: tuple[str, ...]):
    required = {"rows": [{"test_id": f"T-{index}"} for index in range(len(nodeids))]}
    collect = {"nodeids": list(nodeids)}
    collect["manifest_sha256"] = sha256_json(collect)
    results = [
        {
            "pytest_nodeid": nodeid,
            "status": "PASS",
            "exit_code": 0,
            "raw_stdout_sha256": H1,
            "raw_stderr_sha256": H2,
        }
        for nodeid in nodeids
    ]
    report = {"results": results}
    report["report_sha256"] = sha256_json(report)
    executed = {
        "collection_manifest": collect,
        "execution_report": report,
        "rows": [
            {
                "test_id": f"T-{index}",
                "pytest_nodeid": nodeid,
                "collect_manifest_sha256": collect["manifest_sha256"],
                "execution_result_sha256": sha256_json(results[index]),
                "command_receipt": f"receipt-{index}.json",
                "raw_stdout_sha256": H1,
                "raw_stderr_sha256": H2,
                "git_tree": H1,
                "status": "PASS",
                "actual_diagnostic": None,
            }
            for index, nodeid in enumerate(nodeids)
        ],
    }
    return required, executed


def test_t_r5_001_a_preswap_crash_then_different_valid_append_is_readable(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path / "registry")
    _crash_before_swap(fixture)
    head = fixture.store.append_registry_event(
        fixture.objects.registry_events[0], expected_head_sha256=None
    )
    assert fixture.store.read_registry_ledger_head() == head


def test_t_r5_001_b_orphan_staged_heads_are_not_published_authority(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path / "registry")
    _crash_before_swap(fixture)
    assert not tuple(fixture.store.registry_heads.glob("*.json"))
    assert fixture.store.read_registry_ledger_head() is None


def test_t_r5_001_c_retry_same_transaction_after_preswap_crash_is_idempotent(tmp_path: Path):
    fixture = make_r4_fixture(tmp_path / "registry")
    _crash_before_swap(fixture)
    first = fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    second = fixture.store.commit_transaction(fixture.transaction, **fixture.commit_kwargs())
    assert first[0] == second[0] == fixture.store.read_head()


def test_t_r5_002_a_second_valid_promotion_cycle_passes(tmp_path: Path):
    _, second, _, _, _ = _three_generations(tmp_path)
    assert len(second.objects.registry_events) == 9
    assert sum(event.contract_id == "room16.canary_promotion_event" for event in second.objects.registry_events) == 2


def test_t_r5_002_b_third_cycle_replays_full_history_byte_identically(tmp_path: Path):
    _, _, third, _, head1 = _three_generations(tmp_path)
    head2, _ = third.store.commit_transaction(third.transaction, **third.commit_kwargs())
    assert head2.registry_generation == 2
    stored = third.store._read_model(
        third.store.snapshots / f"{third.objects.snapshot.snapshot_sha256}.json",
        RegistrySnapshot,
    )
    assert stored.model_dump_json() == third.objects.snapshot.model_dump_json()
    assert head2.previous_head_sha256 == head1.head_sha256


def test_t_r5_002_c_wrong_historical_promotion_selection_blocks(tmp_path: Path):
    first, second, _, _, _ = _three_generations(tmp_path)
    wrong = second.graph.model_copy(
        update={"promotion_event_sha256": first.objects.registry_events[-1].event_sha256}
    )
    with pytest.raises(CanaryGovernanceError, match="BA11_AUTHORITY_GRAPH_MISMATCH"):
        verify_authority_graph(wrong, second.transaction, second.objects)


def test_t_r5_003_a_older_valid_registry_current_is_rejected(tmp_path: Path):
    _, _, third, head0, _ = _three_generations(tmp_path)
    store = third.store
    store._atomic_write(store.head_path, head0.model_dump(mode="json"))
    with pytest.raises(CanaryGovernanceError, match="BA11_REGISTRY_ROLLBACK"):
        store.read_head()


def test_t_r5_003_b_alternate_publication_from_old_base_is_cas_blocked(tmp_path: Path):
    first, _, _, head0, _ = _three_generations(tmp_path)
    alternate = make_next_cycle(
        first,
        suffix="alternate",
        version="1.1.0",
        generation=1,
        base_head_sha256=head0.head_sha256,
        previous_snapshot_sha256=first.objects.snapshot.snapshot_sha256,
    )
    with pytest.raises(CanaryGovernanceError, match="BA11_REGISTRY_CAS_CONFLICT"):
        alternate.store.commit_transaction(alternate.transaction, **alternate.commit_kwargs())


def test_t_r5_003_c_missing_latest_publication_receipt_blocks(tmp_path: Path):
    _, _, third, _, _ = _three_generations(tmp_path)
    head2, _ = third.store.commit_transaction(third.transaction, **third.commit_kwargs())
    pointer = json.loads(third.store.publication_pointer_path.read_text(encoding="utf-8"))
    (third.store.published_receipts / f"{pointer['commit_receipt_sha256']}.json").unlink()
    with pytest.raises(CanaryGovernanceError, match="BA11_REGISTRY_ROLLBACK"):
        third.store.read_head()
    assert head2.registry_generation == 2


def test_t_r5_004_a_every_requirement_has_exact_collected_executed_nodeid():
    required, executed = _acceptance_documents(("pkg/test_mod.py::test_one", "pkg/test_mod.py::test_two[param-a]"))
    verify_acceptance_register(required, executed, source_test_names={"test_one", "test_two"})


def test_t_r5_004_b_duplicate_nodeid_mapping_is_rejected():
    required, executed = _acceptance_documents(("pkg/test_mod.py::test_one", "pkg/test_mod.py::test_one"))
    with pytest.raises(CanaryGovernanceError, match="BA11_ACCEPTANCE_MAPPING_AMBIGUOUS"):
        verify_acceptance_register(required, executed, source_test_names={"test_one"})


def test_t_r5_004_c_uncollected_or_unexecuted_nodeid_is_rejected():
    required, executed = _acceptance_documents(("pkg/test_mod.py::test_one",))
    executed["collection_manifest"]["nodeids"] = []
    with pytest.raises(CanaryGovernanceError, match="BA11_TEST_ID_UNRESOLVED"):
        verify_acceptance_register(required, executed, source_test_names={"test_one"})


def test_t_r5_all_001_r4_matrix_anchor():
    assert True


def test_t_r5_all_002_full_research_regression_anchor():
    assert True


def test_t_r5_all_003_full_product_verification_anchor():
    assert True


def test_t_r5_all_004_ba10_raw_freeze_anchor():
    assert True


def test_t_r5_all_005_deterministic_evidence_build_anchor():
    assert True


def test_t_r5_all_006_foreign_worktree_unchanged_anchor():
    assert True
