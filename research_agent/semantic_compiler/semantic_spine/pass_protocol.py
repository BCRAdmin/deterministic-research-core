"""Validation for the additive RFC-0002 pass protocol."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

PASS_CONTRACT_PATH = Path(__file__).with_name("config") / "rfc_0002_pass_contracts.json"


class RFC0002PassProtocolError(ValueError):
    pass


def validate_pass_contracts(payload: dict[str, Any]) -> dict[str, Any]:
    locks = {
        "contract_id": "room16.compiler.rfc_0002_pass_contracts",
        "contract_version": 1,
        "rfc_id": "RFC-0002",
        "foundation_version": "1.0.0",
        "registry_foundation_version": "1.1.0",
        "authority_bundle_version": 3,
        "migration_mode": "shadow_strangler",
        "ba10_authorized": False,
    }
    for key, expected in locks.items():
        if payload.get(key) != expected:
            raise RFC0002PassProtocolError(f"pass_contract_lock_mismatch:{key}")
    passes = payload.get("passes")
    if not isinstance(passes, list) or len(passes) != 10:
        raise RFC0002PassProtocolError("rfc_0002_pass_count_invalid")
    if [item.get("ordinal") for item in passes] != list(range(4, 14)):
        raise RFC0002PassProtocolError("rfc_0002_pass_order_invalid")
    ids = [str(item.get("pass_id")) for item in passes]
    if len(ids) != len(set(ids)) or ids[-1] != "ba9.l10.verify_semantics":
        raise RFC0002PassProtocolError("l10_verification_pass_missing_or_misordered")
    for item in passes:
        if not item.get("input_ir_types") or not item.get("output_ir_type"):
            raise RFC0002PassProtocolError(f"pass_io_missing:{item.get('pass_id')}")
        expected = {
            "side_effect_contract": "none",
            "determinism_contract": "pure_same_input_same_output",
            "cache_contract": "content_addressed",
            "replay_contract": "hash_verified",
            "failure_contract": "fail_closed_diagnostic",
            "skippable": False,
        }
        for key, value in expected.items():
            if item.get(key) != value:
                raise RFC0002PassProtocolError(f"pass_contract_invalid:{item.get('pass_id')}:{key}")
    return {"status": "pass", "pass_count": len(passes), "pass_ids": ids, "pass_contracts_sha256": sha256_json(payload), "ba10_authorized": False}


def load_pass_contracts(path: Path = PASS_CONTRACT_PATH) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload, validate_pass_contracts(payload)
