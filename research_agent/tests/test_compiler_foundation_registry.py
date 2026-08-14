from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import ContractError, RegistryEnvelope
from research_agent.compiler_foundation.registry import AUTHORITY_PATH, RegistryAuthority


def raw_authority() -> dict:
    return json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))


def rehash(payload: dict) -> dict:
    body = {key: value for key, value in payload.items() if key != "authority_sha256"}
    payload["authority_sha256"] = sha256_json(body)
    return payload


def test_registry_authority_has_one_research_owner_and_all_required_kinds() -> None:
    authority = RegistryAuthority.load()
    assert len(authority.registries) == 10
    assert {item.registry_kind for item in authority.registries} == {
        "source", "typed_fact", "metric", "table", "formula", "evidence_policy",
        "claim", "decision", "diagnostic", "verdict",
    }
    assert authority.payload["legacy_behavior_changed"] is False


@pytest.mark.parametrize("registry_index", range(10))
def test_each_registry_positive_unknown_id_and_tamper(registry_index: int) -> None:
    authority = RegistryAuthority.load()
    registry = authority.registries[registry_index]
    registry.verify_hash()
    assert registry.resolve(registry.entries[0].entry_id).entry_version == 1
    with pytest.raises(ContractError, match="unknown or reserved"):
        registry.resolve("unknown.fixture.id")
    tampered = registry.model_copy(update={"entries": tuple([
        registry.entries[0].model_copy(update={"definition": {"tampered": True}}),
        *registry.entries[1:],
    ])})
    with pytest.raises(ContractError, match="hash mismatch"):
        tampered.verify_hash()


@pytest.mark.parametrize("registry_index", range(10))
def test_each_registry_version_and_order_fail_closed(registry_index: int) -> None:
    raw = raw_authority()["registries"][registry_index]
    with pytest.raises(Exception):
        RegistryEnvelope.model_validate({**raw, "contract_version": 2})
    if len(raw["entries"]) > 1:
        changed = copy.deepcopy(raw)
        changed["entries"] = list(reversed(changed["entries"]))
        with pytest.raises(Exception, match="sorted"):
            RegistryEnvelope.model_validate(changed)


@pytest.mark.parametrize("registry_index", range(10))
def test_each_registry_replay_and_skip_removal_are_deterministic(registry_index: int) -> None:
    original = raw_authority()
    authority = RegistryAuthority(copy.deepcopy(original))
    registry = authority.registries[registry_index]
    replay = RegistryEnvelope.model_validate(registry.model_dump(mode="json"))
    assert replay.content_sha256 == registry.content_sha256
    replay.verify_hash()

    removed = copy.deepcopy(original)
    removed_id = removed["registries"].pop(registry_index)["registry_id"]
    removed = rehash(removed)
    reduced = RegistryAuthority(removed)
    with pytest.raises(ContractError, match="unknown registry"):
        reduced.registry(removed_id)


def test_authority_top_level_tamper_and_unknown_registry_fail_closed() -> None:
    payload = raw_authority()
    payload["legacy_behavior_changed"] = True
    with pytest.raises(ContractError, match="Authority hash mismatch"):
        RegistryAuthority(payload)
    authority = RegistryAuthority.load()
    with pytest.raises(ContractError, match="unknown registry"):
        authority.registry("room16.registry.unknown")


def test_authority_version_owner_and_duplicate_registry_fail_closed() -> None:
    for key, value in [("contract_version", 2), ("owner", "product")]:
        payload = rehash({**raw_authority(), key: value})
        with pytest.raises(ContractError, match="version or owner"):
            RegistryAuthority(payload)
    payload = raw_authority()
    payload["registries"].append(copy.deepcopy(payload["registries"][0]))
    payload = rehash(payload)
    with pytest.raises(ContractError, match="unique and sorted"):
        RegistryAuthority(payload)
