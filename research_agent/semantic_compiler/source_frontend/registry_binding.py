"""Validated BA3 view over the existing Research market capability registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from research_agent.capabilities.market_registry import REGISTRY_PATH
from research_agent.compiler_foundation.registry import RegistryAuthority

BINDING_PATH = Path(__file__).with_name("config") / "source_adapter_registry_binding.json"


class SourceAdapterBindingError(ValueError):
    """Raised when the BA3 adapter binding is invalid or unknown."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_source_adapter_binding(path: Path = BINDING_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract_id") != "room16.compiler.ba3_source_adapter_registry_binding":
        raise SourceAdapterBindingError("source_adapter_binding_contract_invalid")
    if payload.get("contract_version") != 1:
        raise SourceAdapterBindingError("source_adapter_binding_version_unsupported")
    source = payload.get("source_registry") or {}
    if (
        source.get("contract_id") != "room16.market_capability_registry"
        or source.get("contract_version") != 1
        or source.get("owner") != "research"
        or source.get("sha256") != _sha256(REGISTRY_PATH)
    ):
        raise SourceAdapterBindingError("source_adapter_registry_hash_mismatch")
    foundation = payload.get("foundation_source_registry") or {}
    authority = RegistryAuthority.load()
    if (
        foundation.get("registry_id") != "room16.registry.source"
        or foundation.get("registry_version") != 1
        or foundation.get("authority_sha256") != authority.authority_sha256
    ):
        raise SourceAdapterBindingError("foundation_source_registry_binding_invalid")
    allowed = foundation.get("allowed_source_type_ids")
    if not isinstance(allowed, list) or allowed != sorted(set(allowed)):
        raise SourceAdapterBindingError("foundation_source_type_ids_invalid")
    for source_type in allowed:
        authority.resolve("room16.registry.source", source_type)
    bindings = payload.get("provider_source_type_bindings")
    if not isinstance(bindings, dict) or not bindings:
        raise SourceAdapterBindingError("provider_source_type_bindings_invalid")
    for provider_id, source_types in bindings.items():
        if (
            not isinstance(provider_id, str)
            or not isinstance(source_types, list)
            or source_types != sorted(set(source_types))
            or not set(source_types) <= set(allowed)
        ):
            raise SourceAdapterBindingError("provider_source_type_bindings_invalid")
    if (
        payload.get("unknown_provider_policy") != "fail_closed"
        or payload.get("unknown_source_type_policy") != "fail_closed"
        or payload.get("automatic_paid_provider_selection_allowed") is not False
        or payload.get("automatic_provider_fallback_allowed") is not False
    ):
        raise SourceAdapterBindingError("source_adapter_binding_policy_invalid")
    return payload


def source_types_for_provider(provider_id: str, *, path: Path = BINDING_PATH) -> tuple[str, ...]:
    payload = load_source_adapter_binding(path)
    value = payload["provider_source_type_bindings"].get(provider_id)
    if value is None:
        raise SourceAdapterBindingError(f"provider_binding_unknown:{provider_id}")
    return tuple(value)
