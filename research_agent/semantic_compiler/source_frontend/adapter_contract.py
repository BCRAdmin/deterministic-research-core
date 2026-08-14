"""Executable conformance contract for existing SEC/BSE/Nasdaq/Massive adapters."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

ADAPTER_CONTRACT_PATH = Path(__file__).with_name("config") / "source_adapter_implementations.json"


class SourceAdapterContractError(ValueError):
    """Raised when an adapter implementation violates BA3's bound interface."""


def load_adapter_contract(path: Path = ADAPTER_CONTRACT_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract_id") != "room16.compiler.ba3_source_adapter_implementations":
        raise SourceAdapterContractError("adapter_contract_id_invalid")
    if payload.get("contract_version") != 1:
        raise SourceAdapterContractError("adapter_contract_version_unsupported")
    if (
        payload.get("live_execution_authority")
        != "existing_current_runner_until_strangler_cutover"
        or payload.get("ba3_authoritative_execution_mode") != "offline_receipt_replay"
        or payload.get("implicit_fallback_allowed") is not False
    ):
        raise SourceAdapterContractError("adapter_execution_boundary_invalid")
    adapters = payload.get("adapters")
    if not isinstance(adapters, list) or not adapters:
        raise SourceAdapterContractError("adapter_contract_empty")
    ids = [item.get("provider_id") for item in adapters]
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise SourceAdapterContractError("adapter_contract_order_invalid")
    for item in adapters:
        methods = item.get("required_methods")
        if (
            not isinstance(item.get("implementation_ref"), str)
            or not isinstance(methods, list)
            or methods != sorted(set(methods))
            or item.get("raw_bytes_must_be_staged") is not True
            or item.get("retrieval_receipt_required") is not True
            or not item.get("network_side_effect")
        ):
            raise SourceAdapterContractError("adapter_contract_shape_invalid")
    return payload


def adapter_descriptor(provider_id: str, *, path: Path = ADAPTER_CONTRACT_PATH) -> dict[str, Any]:
    for item in load_adapter_contract(path)["adapters"]:
        if item["provider_id"] == provider_id:
            return item
    raise SourceAdapterContractError(f"adapter_contract_unknown:{provider_id}")


def verify_adapter_implementation(
    provider_id: str,
    *,
    path: Path = ADAPTER_CONTRACT_PATH,
) -> dict[str, Any]:
    descriptor = adapter_descriptor(provider_id, path=path)
    module_name, class_name = descriptor["implementation_ref"].split(":", 1)
    implementation = getattr(importlib.import_module(module_name), class_name, None)
    if implementation is None:
        raise SourceAdapterContractError(f"adapter_implementation_missing:{provider_id}")
    missing = [
        method
        for method in descriptor["required_methods"]
        if not callable(getattr(implementation, method, None))
    ]
    if missing:
        raise SourceAdapterContractError(
            f"adapter_methods_missing:{provider_id}:{','.join(missing)}"
        )
    return descriptor
