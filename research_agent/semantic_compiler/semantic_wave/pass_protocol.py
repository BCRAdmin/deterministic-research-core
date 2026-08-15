"""Validation and canonical hashing for the BA4-BA9 pass chain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

PASS_CONTRACT_PATH = Path(__file__).with_name("config") / "semantic_wave_pass_contracts.json"

KNOWN_REGISTRY_DEPENDENCIES = {
    "room16.registry.evidence_policy",
    "room16.registry.source",
    "room16.registry.table",
    "room16.registry.typed_fact",
    "semantic.claim_kind_definition",
    "semantic.decision_node_definition",
    "semantic.formula_definition",
    "semantic.metric_definition",
    "semantic.permission_corridor_definition",
    "semantic.risk_definition",
}


class SemanticPassProtocolError(ValueError):
    """Raised when a semantic-wave pass contract cannot execute safely."""


def validate_semantic_pass_contracts(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("contract_id") != "room16.compiler.semantic_wave_pass_contracts":
        raise SemanticPassProtocolError("invalid_semantic_pass_contract")
    if payload.get("contract_version") != 1:
        raise SemanticPassProtocolError("unsupported_semantic_pass_contract_version")
    if payload.get("foundation_version") != "1.0.0":
        raise SemanticPassProtocolError("foundation_version_lock_mismatch")
    if payload.get("registry_foundation_version") != "1.1.0":
        raise SemanticPassProtocolError("registry_foundation_version_lock_mismatch")
    if payload.get("authority_bundle_version") != 3:
        raise SemanticPassProtocolError("authority_bundle_abi_mismatch")
    if payload.get("ba10_authorized") is not False:
        raise SemanticPassProtocolError("ba10_not_authorized")
    passes = payload.get("passes")
    if not isinstance(passes, list) or len(passes) != 9:
        raise SemanticPassProtocolError("semantic_pass_count_invalid")
    ordinals = [item.get("ordinal") for item in passes]
    if ordinals != list(range(4, 13)):
        raise SemanticPassProtocolError("semantic_pass_order_invalid")
    pass_ids = [item.get("pass_id") for item in passes]
    if len(pass_ids) != len(set(pass_ids)) or not all(
        isinstance(value, str) and value.startswith("ba") for value in pass_ids
    ):
        raise SemanticPassProtocolError("semantic_pass_id_invalid")
    for item in passes:
        pass_id = item["pass_id"]
        required = {
            "layer",
            "input_ir_types",
            "output_ir_type",
            "side_effect_contract",
            "determinism_contract",
            "cache_contract",
            "replay_contract",
            "failure_contract",
            "skippable",
            "registry_dependencies",
        }
        if not required.issubset(item):
            raise SemanticPassProtocolError(f"semantic_pass_contract_incomplete:{pass_id}")
        if not item["input_ir_types"] or not item["output_ir_type"]:
            raise SemanticPassProtocolError(f"semantic_pass_io_missing:{pass_id}")
        if item["side_effect_contract"] != "none":
            raise SemanticPassProtocolError(f"semantic_pass_side_effect_forbidden:{pass_id}")
        if item["determinism_contract"] != "pure_same_input_same_output":
            raise SemanticPassProtocolError(f"semantic_pass_nondeterministic:{pass_id}")
        if item["cache_contract"] != "content_addressed":
            raise SemanticPassProtocolError(f"semantic_pass_cache_invalid:{pass_id}")
        if item["replay_contract"] != "hash_verified":
            raise SemanticPassProtocolError(f"semantic_pass_replay_invalid:{pass_id}")
        if item["failure_contract"] != "fail_closed_diagnostic":
            raise SemanticPassProtocolError(f"semantic_pass_failure_contract_invalid:{pass_id}")
        if item["skippable"] is not False:
            raise SemanticPassProtocolError(f"semantic_pass_skip_forbidden:{pass_id}")
        unknown = sorted(set(item["registry_dependencies"]) - KNOWN_REGISTRY_DEPENDENCIES)
        if unknown:
            raise SemanticPassProtocolError(
                f"semantic_pass_unknown_registry:{pass_id}:{','.join(unknown)}"
            )
    return {
        "status": "pass",
        "pass_count": len(passes),
        "pass_ids": pass_ids,
        "pass_contracts_sha256": sha256_json(payload),
        "ba10_authorized": False,
    }


def load_semantic_pass_contracts(
    path: Path = PASS_CONTRACT_PATH,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, validate_semantic_pass_contracts(payload)
