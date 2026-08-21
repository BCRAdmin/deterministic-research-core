#!/usr/bin/env python3
"""Generate v2 public trust mirrors from a Research-only local signing key."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from nacl.signing import SigningKey

from research_agent.compiler_foundation.canonical import sha256_json


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
RESEARCH_CONFIG = ROOT / "research_agent/productization_v2/config"
PRODUCT_CONFIG = PRODUCT / "room16-app/config"
PRIVATE_KEY = ROOT / ".runtime/rfc0008/signing_key_ed25519.bin"
KEY_ID = "research.rfc0008.primary.2026-08-21"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    PRIVATE_KEY.parent.mkdir(parents=True, exist_ok=True)
    if PRIVATE_KEY.exists():
        raw = PRIVATE_KEY.read_bytes()
        if len(raw) != 32:
            raise SystemExit("STOP invalid local RFC-0008 signing key")
        signing_key = SigningKey(raw)
    else:
        signing_key = SigningKey.generate()
        PRIVATE_KEY.write_bytes(bytes(signing_key))
        os.chmod(PRIVATE_KEY, 0o600)
    key_body = {
        "contract_id": "room16.compiler.public_key_policy",
        "contract_version": 2,
        "owner": "research_compiler",
        "signature_algorithm": "ed25519",
        "keys": [
            {
                "key_id": KEY_ID,
                "not_after_utc": None,
                "not_before_utc": "2026-08-21T00:00:00Z",
                "public_key_hex": signing_key.verify_key.encode().hex(),
                "state": "active",
            }
        ],
        "rotation_sequence": [
            "active",
            "grace_verify_only",
            "revoked",
        ],
    }
    key_policy = {**key_body, "policy_sha256": sha256_json(key_body)}
    policy_body = {
        "allowed_authority_v3_bridge_directions": [
            "bundle_to_authority_v3_only",
            "disabled",
        ],
        "artifact_bundle_contract_major": 2,
        "ba10_v1_freeze_sha256": "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e",
        "ba11_freeze_sha256": "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf",
        "canonicalization_profile": "room16.foundation.canonical_json@1",
        "contract_id": "room16.compiler.consumer_policy_lock",
        "contract_version": 2,
        "hash_algorithm": "sha256",
        "key_policy_sha256": key_policy["policy_sha256"],
        "legacy_semantic_input_allowed": False,
        "mutable_bundle_hash_allowlist_allowed": False,
        "owner": "research_compiler",
        "product_may_edit_semantics": False,
        "schema_version_max": "2.x",
        "schema_version_min": "2.0.0",
        "source_native_fact_generation_required_for_native": True,
        "trusted_emitter_id": "room16.compiler_artifact_bundle_builder_v2",
    }
    consumer_policy = {**policy_body, "policy_sha256": sha256_json(policy_body)}
    research_key = RESEARCH_CONFIG / "public_key_policy_v2.json"
    research_policy = RESEARCH_CONFIG / "consumer_policy_v2.json"
    write_json(research_key, key_policy)
    write_json(research_policy, consumer_policy)
    PRODUCT_CONFIG.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(research_key, PRODUCT_CONFIG / "room16_compiler_artifact_trusted_keys_v2.json")
    shutil.copyfile(
        research_policy, PRODUCT_CONFIG / "room16_compiler_artifact_consumer_policy_v2.json"
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "private_key_path": str(PRIVATE_KEY),
                "private_key_git_ignored": True,
                "key_id": KEY_ID,
                "key_policy_sha256": key_policy["policy_sha256"],
                "consumer_policy_sha256": consumer_policy["policy_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
