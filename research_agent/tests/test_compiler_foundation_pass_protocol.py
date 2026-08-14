from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_agent.compiler_foundation.contracts import (
    CompilerLayer,
    ContractError,
    IREnvelope,
    PassExecutionRecord,
    PassManifest,
    PassStatus,
)
from research_agent.compiler_foundation.kernel import (
    PassKernel,
    PassProtocolError,
    identity_shadow_pass,
    load_pass_manifests,
)
from research_agent.compiler_foundation.registry import RegistryAuthority


def initial() -> IREnvelope:
    return IREnvelope.create(
        ir_type="legacy.frozen_candidate",
        layer=CompilerLayer.L0_COMPILE_INTAKE,
        producer_pass_id="fixture.input",
        payload={"ticker": "FIX", "frozen": True},
    )


def implementations(manifests: tuple[PassManifest, ...]) -> dict:
    return {item.pass_id: identity_shadow_pass for item in manifests}


def test_all_passes_execute_cache_and_replay_without_payload_change() -> None:
    manifests = load_pass_manifests()
    kernel = PassKernel(manifests, RegistryAuthority.load())
    result, first = kernel.execute(initial(), implementations(manifests))
    cached_result, cached = kernel.execute(initial(), implementations(manifests))
    replay_result, replayed = PassKernel(manifests, RegistryAuthority.load()).execute(
        initial(), implementations(manifests), replay=first
    )
    assert len(first) == len(cached) == len(replayed) == 12
    assert all(item.status == PassStatus.EXECUTED for item in first)
    assert all(item.status == PassStatus.CACHE_HIT for item in cached)
    assert all(item.status == PassStatus.REPLAYED for item in replayed)
    assert result.payload == cached_result.payload == replay_result.payload == initial().payload


@pytest.mark.parametrize("pass_index", range(12))
def test_each_pass_missing_implementation_fails_closed(pass_index: int) -> None:
    manifests = load_pass_manifests()
    impl = implementations(manifests)
    del impl[manifests[pass_index].pass_id]
    with pytest.raises(ContractError, match="missing pass implementation"):
        PassKernel(manifests, RegistryAuthority.load()).execute(initial(), impl)


@pytest.mark.parametrize("pass_index", range(12))
def test_each_pass_skip_contract(pass_index: int) -> None:
    manifests = load_pass_manifests()
    target = manifests[pass_index]
    kernel = PassKernel(manifests, RegistryAuthority.load())
    if target.skippable:
        _, records = kernel.execute(initial(), implementations(manifests), skip=frozenset({target.pass_id}))
        assert records[pass_index].status == PassStatus.SKIPPED
    else:
        with pytest.raises(ContractError, match="not skippable"):
            kernel.execute(initial(), implementations(manifests), skip=frozenset({target.pass_id}))


@pytest.mark.parametrize("pass_index", range(12))
def test_each_pass_replay_tamper_is_detected(pass_index: int) -> None:
    manifests = load_pass_manifests()
    _, records = PassKernel(manifests, RegistryAuthority.load()).execute(
        initial(), implementations(manifests)
    )
    changed = list(records)
    changed[pass_index] = changed[pass_index].model_copy(update={"output_payload_sha256": "0" * 64})
    with pytest.raises(ContractError, match="replay output mismatch"):
        PassKernel(manifests, RegistryAuthority.load()).execute(
            initial(), implementations(manifests), replay=tuple(changed)
        )


@pytest.mark.parametrize("pass_index", range(12))
def test_each_pass_version_contract(pass_index: int) -> None:
    manifests = load_pass_manifests()
    payload = manifests[pass_index].model_dump(mode="json")
    payload["pass_version"] = 0
    with pytest.raises(Exception):
        PassManifest.model_validate(payload)


@pytest.mark.parametrize("pass_index", range(12))
def test_each_pass_unknown_registry_dependency_fails_closed(pass_index: int) -> None:
    manifests = list(load_pass_manifests())
    manifests[pass_index] = manifests[pass_index].model_copy(
        update={"registry_dependencies": (f"unknown.registry.{pass_index}",)}
    )
    with pytest.raises(ContractError, match="unknown registry"):
        PassKernel(tuple(manifests), RegistryAuthority.load()).execute(
            initial(), implementations(tuple(manifests))
        )


@pytest.mark.parametrize("pass_index", range(12))
def test_each_pass_order_mutation_fails_closed(pass_index: int, tmp_path: Path) -> None:
    config = Path(__file__).parents[1] / "compiler_foundation/config/pass_manifests.json"
    payload = json.loads(config.read_text(encoding="utf-8"))
    neighbor = 1 if pass_index == 0 else pass_index - 1
    payload["passes"][pass_index], payload["passes"][neighbor] = (
        payload["passes"][neighbor],
        payload["passes"][pass_index],
    )
    target = tmp_path / f"order-{pass_index}.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ContractError, match="order"):
        load_pass_manifests(target)


def test_order_unknown_registry_input_tamper_and_manifest_version_fail_closed(tmp_path: Path) -> None:
    config = Path(__file__).parents[1] / "compiler_foundation/config/pass_manifests.json"
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["passes"] = list(reversed(payload["passes"]))
    target = tmp_path / "order.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ContractError, match="order"):
        load_pass_manifests(target)

    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["contract_version"] = 2
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ContractError, match="unsupported"):
        load_pass_manifests(target)

    manifests = load_pass_manifests()
    changed = list(manifests)
    changed[0] = changed[0].model_copy(update={"registry_dependencies": ("unknown.registry",)})
    with pytest.raises(ContractError, match="unknown registry"):
        PassKernel(tuple(changed), RegistryAuthority.load()).execute(initial(), implementations(tuple(changed)))

    tampered = initial().model_copy(update={"payload": {"ticker": "BAD"}})
    with pytest.raises(ContractError, match="IR payload hash mismatch"):
        PassKernel(manifests, RegistryAuthority.load()).execute(tampered, implementations(manifests))

    with pytest.raises(ContractError, match="unknown pass id"):
        PassKernel(manifests, RegistryAuthority.load()).execute(
            initial(), implementations(manifests), skip=frozenset({"unknown.pass"})
        )


def test_pass_failure_exposes_canonical_blocking_diagnostic() -> None:
    manifests = load_pass_manifests()
    impl = implementations(manifests)
    del impl[manifests[0].pass_id]
    with pytest.raises(PassProtocolError) as caught:
        PassKernel(manifests, RegistryAuthority.load()).execute(initial(), impl)
    diagnostic = caught.value.diagnostic
    assert diagnostic.code == "PASS_IMPLEMENTATION_MISSING"
    assert diagnostic.release_effect.value == "compile_block"
    assert diagnostic.layer == manifests[0].layer
    assert diagnostic.pass_id == manifests[0].pass_id
    assert diagnostic.root_cause_ref
    assert diagnostic.fixture_refs
