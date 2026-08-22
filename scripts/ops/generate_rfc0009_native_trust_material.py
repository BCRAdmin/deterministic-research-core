#!/usr/bin/env python3
"""Generate additive RFC-0009 public trust objects and Product mirrors."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nacl.signing import SigningKey

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization_v2.native_trust import (
    NATIVE_EMITTER_ID,
    NATIVE_EMITTER_VERSION,
    NATIVE_PRODUCER_PASS_ID,
)
from research_agent.productization_v2.trust_root import (
    envelope_domain_hash,
    envelope_signature_preimage,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
RESEARCH_CONFIG = ROOT / "research_agent/productization_v2/config"
PRODUCT_CONFIG = PRODUCT / "room16-app/config"
ROOT_KEY_PATH = ROOT / ".runtime/rfc0008/root_signing_key_ed25519.bin"
NATIVE_MODULE = ROOT / "research_agent/productization_v2/native_trust.py"
CONTRACTS = ROOT / "research_agent/productization_v2/contracts.py"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not ROOT_KEY_PATH.is_file() or len(ROOT_KEY_PATH.read_bytes()) != 32:
        raise SystemExit("STOP RFC-0008 root signing key unavailable")
    root_key = SigningKey(ROOT_KEY_PATH.read_bytes())
    root = json.loads((RESEARCH_CONFIG / "trust_root_v2.json").read_text())
    gen1 = json.loads((RESEARCH_CONFIG / "consumer_policy_envelope_v2.json").read_text())
    gen1_profile = json.loads((RESEARCH_CONFIG / "manifest_schema_profile_v2.json").read_text())
    if root_key.verify_key.encode().hex() != root["root_public_key_hex"]:
        raise SystemExit("STOP RFC-0008 root signing key mismatch")
    if gen1["envelope_sha256"] != "7f16189fdfd6b676fd3cb58acf9c6c51a9a1b66671dbb7c1f76156dffc5cd8c9":
        raise SystemExit("STOP RFC-0008 Gen1 envelope drift")

    emitter_identity = {
        "emitter_id": NATIVE_EMITTER_ID,
        "emitter_version": NATIVE_EMITTER_VERSION,
        "producer_pass_id": NATIVE_PRODUCER_PASS_ID,
        "implementation_sha256": sha_file(NATIVE_MODULE),
        "schema_sha256": sha_file(CONTRACTS),
    }
    emitter_body = {
        "contract_id": "room16.compiler.native_emitter_profile",
        "contract_version": 1,
        "emitter_identity": emitter_identity,
        "compatibility_lock": {
            "mode": "bundle_native",
            "compiler_mode": "source_native",
            "source_native_fact_generation": True,
            "native_source_production": True,
            "legacy_semantic_input_allowed": False,
            "authority_v3_semantic_input_allowed": False,
            "authority_v3_bridge_direction": "bundle_to_authority_v3_only",
        },
        "eligibility_lock": {
            "release_ready": False,
            "publication_allowed": False,
            "deploy_allowed": False,
        },
    }
    emitter_profile = {**emitter_body, "profile_sha256": sha256_json(emitter_body)}

    native_profile_body = {
        key: value for key, value in gen1_profile.items() if key != "profile_sha256"
    }
    native_profile_body["compiler_identity_lock"] = {
        **native_profile_body["compiler_identity_lock"],
        "semantic_artifact_origin": "source_native",
    }
    native_profile_body["native_emitter_lock"] = emitter_identity
    native_profile = {
        **native_profile_body,
        "profile_sha256": sha256_json(native_profile_body),
    }

    policy_body = {
        key: value for key, value in gen1["payload"].items() if key != "policy_sha256"
    }
    policy_body["trusted_emitter_id"] = NATIVE_EMITTER_ID
    policy_body["manifest_schema_profile_sha256"] = native_profile["profile_sha256"]
    policy_body["compiler_identity"] = {
        **policy_body["compiler_identity"],
        "semantic_artifact_origin": "source_native",
    }
    policy = {**policy_body, "policy_sha256": sha256_json(policy_body)}
    envelope_unsigned = {
        "contract_id": gen1["contract_id"],
        "contract_version": gen1["contract_version"],
        "generation": 2,
        "previous_envelope_sha256": gen1["envelope_sha256"],
        "root_id": gen1["root_id"],
        "root_key_id": gen1["root_key_id"],
        "issued_at_utc": "2026-08-22T00:00:00Z",
        "payload": policy,
        "signature_algorithm": "ed25519",
    }
    signature = root_key.sign(
        __import__("research_agent.compiler_foundation.canonical", fromlist=["canonical_bytes"]).canonical_bytes(
            envelope_signature_preimage(envelope_unsigned)
        )
    ).signature.hex()
    envelope_signed = {**envelope_unsigned, "signature": signature}
    envelope = {
        **envelope_signed,
        "envelope_sha256": envelope_domain_hash(envelope_signed),
    }
    delta = {
        "contract_id": "room16.rfc0009.consumer_policy_generation_delta@1",
        "generation_from": 1,
        "generation_to": 2,
        "allowed_changes": {
            "compiler_identity.semantic_artifact_origin": ["frozen_v1_migration", "source_native"],
            "manifest_schema_profile_sha256": [gen1["payload"]["manifest_schema_profile_sha256"], native_profile["profile_sha256"]],
            "trusted_emitter_id": [gen1["payload"]["trusted_emitter_id"], NATIVE_EMITTER_ID],
            "policy_sha256": [gen1["payload"]["policy_sha256"], policy["policy_sha256"]],
        },
        "unchanged_key_policy_sha256": policy["key_policy_sha256"],
        "previous_envelope_sha256": gen1["envelope_sha256"],
        "generation_2_envelope_sha256": envelope["envelope_sha256"],
    }

    files = {
        "consumer_policy_v2_generation_2_native.json": policy,
        "consumer_policy_envelope_v2_generation_2_native.json": envelope,
        "manifest_schema_profile_v2_generation_2_native.json": native_profile,
        "native_emitter_profile_v2.json": emitter_profile,
        "consumer_policy_v2_generation_2_native_delta.json": delta,
    }
    product_names = {
        "consumer_policy_v2_generation_2_native.json": "room16_compiler_artifact_consumer_policy_v2_generation_2_native.json",
        "consumer_policy_envelope_v2_generation_2_native.json": "room16_compiler_artifact_consumer_policy_envelope_v2_generation_2_native.json",
        "manifest_schema_profile_v2_generation_2_native.json": "room16_compiler_artifact_bundle_schema_profile_v2_generation_2_native.json",
        "native_emitter_profile_v2.json": "room16_compiler_native_emitter_profile_v2.json",
        "consumer_policy_v2_generation_2_native_delta.json": "room16_compiler_artifact_consumer_policy_v2_generation_2_native_delta.json",
    }
    for name, value in files.items():
        source = RESEARCH_CONFIG / name
        write_json(source, value)
        destination = PRODUCT_CONFIG / product_names[name]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    print(json.dumps({
        "status": "PASS",
        "root_sha256": root["root_sha256"],
        "gen1_envelope_sha256": gen1["envelope_sha256"],
        "gen2_envelope_sha256": envelope["envelope_sha256"],
        "gen2_policy_sha256": policy["policy_sha256"],
        "native_schema_profile_sha256": native_profile["profile_sha256"],
        "native_emitter_profile_sha256": emitter_profile["profile_sha256"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
