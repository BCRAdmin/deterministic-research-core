#!/usr/bin/env python3
"""Generate v2 public trust mirrors from a Research-only local signing key."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from nacl.signing import SigningKey

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization_v2.contracts import (
    CompilerIdentityV2,
    ConsumerPolicyEnvelopeV2,
    PublicKeyPolicyEnvelopeV2,
)
from research_agent.productization_v2.schema_profile import manifest_schema_profile_v2
from research_agent.productization_v2.trust_root import sign_policy_envelope


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
RESEARCH_CONFIG = ROOT / "research_agent/productization_v2/config"
PRODUCT_CONFIG = PRODUCT / "room16-app/config"
PRIVATE_KEY = ROOT / ".runtime/rfc0008/signing_key_ed25519.bin"
ROOT_PRIVATE_KEY = ROOT / ".runtime/rfc0008/root_signing_key_ed25519.bin"
KEY_ID = "research.rfc0008.primary.2026-08-21"
ROOT_KEY_ID = "research.rfc0008.root.2026-08-21"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    def local_signing_key(path: Path, *, committed_authority_exists: bool) -> SigningKey:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raw = path.read_bytes()
            if len(raw) != 32:
                raise SystemExit(f"STOP invalid local RFC-0008 signing key:{path}")
            return SigningKey(raw)
        if committed_authority_exists:
            raise SystemExit(
                f"STOP local RFC-0008 signing key missing for committed authority:{path}"
            )
        value = SigningKey.generate()
        path.write_bytes(bytes(value))
        os.chmod(path, 0o600)
        return value

    signing_key = local_signing_key(
        PRIVATE_KEY,
        committed_authority_exists=(RESEARCH_CONFIG / "public_key_policy_v2.json").exists(),
    )
    root_signing_key = local_signing_key(
        ROOT_PRIVATE_KEY,
        committed_authority_exists=(RESEARCH_CONFIG / "trust_root_v2.json").exists(),
    )
    schema_profile = manifest_schema_profile_v2()
    root_body = {
        "artifact_bundle_contract_major": 2,
        "ba10_v1_freeze_sha256": "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e",
        "ba11_freeze_sha256": "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf",
        "canonicalization_profile": "room16.foundation.canonical_json@1",
        "consumer_policy_contract_id": "room16.compiler.consumer_policy_lock",
        "consumer_policy_contract_version": 2,
        "contract_id": "room16.compiler.v2_trust_root",
        "contract_version": 1,
        "hash_algorithm": "sha256",
        "issued_at_utc": "2026-08-21T00:00:00Z",
        "owner": "research_compiler",
        "public_key_policy_contract_id": "room16.compiler.public_key_policy",
        "public_key_policy_contract_version": 2,
        "root_id": "room16.compiler.v2_trust_root@1",
        "root_key_id": ROOT_KEY_ID,
        "root_public_key_hex": root_signing_key.verify_key.encode().hex(),
    }
    trust_root = {
        **root_body,
        "root_sha256": sha256_json(
            {"domain": "room16.compiler.v2_trust_root@1", "value": root_body}
        ),
    }
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
        "compiler_identity": CompilerIdentityV2(
            semantic_artifact_origin="frozen_v1_migration"
        ).model_dump(mode="json"),
        "manifest_schema_profile_sha256": schema_profile["profile_sha256"],
    }
    consumer_policy = {**policy_body, "policy_sha256": sha256_json(policy_body)}
    research_key = RESEARCH_CONFIG / "public_key_policy_v2.json"
    research_policy = RESEARCH_CONFIG / "consumer_policy_v2.json"
    write_json(research_key, key_policy)
    write_json(research_policy, consumer_policy)
    research_root = RESEARCH_CONFIG / "trust_root_v2.json"
    research_consumer_envelope = RESEARCH_CONFIG / "consumer_policy_envelope_v2.json"
    research_key_envelope = RESEARCH_CONFIG / "public_key_policy_envelope_v2.json"
    research_schema_profile = RESEARCH_CONFIG / "manifest_schema_profile_v2.json"
    write_json(research_root, trust_root)
    consumer_envelope = sign_policy_envelope(
        {
            "contract_id": "room16.compiler.consumer_policy_envelope",
            "contract_version": 2,
            "generation": 1,
            "previous_envelope_sha256": None,
            "root_id": trust_root["root_id"],
            "root_key_id": ROOT_KEY_ID,
            "issued_at_utc": "2026-08-21T00:00:00Z",
            "payload": consumer_policy,
        },
        signing_key=root_signing_key,
        model=ConsumerPolicyEnvelopeV2,
    )
    key_envelope = sign_policy_envelope(
        {
            "contract_id": "room16.compiler.public_key_policy_envelope",
            "contract_version": 2,
            "generation": 1,
            "previous_envelope_sha256": None,
            "root_id": trust_root["root_id"],
            "root_key_id": ROOT_KEY_ID,
            "issued_at_utc": "2026-08-21T00:00:00Z",
            "payload": key_policy,
        },
        signing_key=root_signing_key,
        model=PublicKeyPolicyEnvelopeV2,
    )
    write_json(research_consumer_envelope, consumer_envelope.model_dump(mode="json"))
    write_json(research_key_envelope, key_envelope.model_dump(mode="json"))
    write_json(research_schema_profile, schema_profile)
    chain_fixture_root = RESEARCH_CONFIG / "policy_chain_fixtures"
    consumer_generation_two = sign_policy_envelope(
        {
            **consumer_envelope.model_dump(mode="json", exclude={"signature", "envelope_sha256"}),
            "generation": 2,
            "previous_envelope_sha256": consumer_envelope.envelope_sha256,
            "issued_at_utc": "2026-08-21T00:01:00Z",
        },
        signing_key=root_signing_key,
        model=ConsumerPolicyEnvelopeV2,
    )
    key_generation_two = sign_policy_envelope(
        {
            **key_envelope.model_dump(mode="json", exclude={"signature", "envelope_sha256"}),
            "generation": 2,
            "previous_envelope_sha256": key_envelope.envelope_sha256,
            "issued_at_utc": "2026-08-21T00:01:00Z",
        },
        signing_key=root_signing_key,
        model=PublicKeyPolicyEnvelopeV2,
    )
    write_json(
        chain_fixture_root / "consumer_policy_envelope_v2_generation_2.json",
        consumer_generation_two.model_dump(mode="json"),
    )
    write_json(
        chain_fixture_root / "public_key_policy_envelope_v2_generation_2.json",
        key_generation_two.model_dump(mode="json"),
    )
    PRODUCT_CONFIG.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(research_key, PRODUCT_CONFIG / "room16_compiler_artifact_trusted_keys_v2.json")
    shutil.copyfile(
        research_policy, PRODUCT_CONFIG / "room16_compiler_artifact_consumer_policy_v2.json"
    )
    for source, name in (
        (research_root, "room16_compiler_v2_trust_root.json"),
        (
            research_consumer_envelope,
            "room16_compiler_artifact_consumer_policy_envelope_v2.json",
        ),
        (research_key_envelope, "room16_compiler_artifact_key_policy_envelope_v2.json"),
        (research_schema_profile, "room16_compiler_artifact_bundle_schema_profile_v2.json"),
    ):
        shutil.copyfile(source, PRODUCT_CONFIG / name)
    product_chain_fixtures = PRODUCT / "room16-app/fixtures/rfc0008-v2-policy-chain"
    product_chain_fixtures.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        chain_fixture_root / "consumer_policy_envelope_v2_generation_2.json",
        product_chain_fixtures / "consumer_policy_envelope_v2_generation_2.json",
    )
    shutil.copyfile(
        chain_fixture_root / "public_key_policy_envelope_v2_generation_2.json",
        product_chain_fixtures / "public_key_policy_envelope_v2_generation_2.json",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "private_key_path": str(PRIVATE_KEY),
                "private_key_git_ignored": True,
                "key_id": KEY_ID,
                "root_key_id": ROOT_KEY_ID,
                "root_sha256": trust_root["root_sha256"],
                "root_private_key_path": str(ROOT_PRIVATE_KEY),
                "key_policy_sha256": key_policy["policy_sha256"],
                "consumer_policy_sha256": consumer_policy["policy_sha256"],
                "consumer_envelope_sha256": consumer_envelope.envelope_sha256,
                "key_envelope_sha256": key_envelope.envelope_sha256,
                "consumer_generation_two_sha256": (consumer_generation_two.envelope_sha256),
                "key_generation_two_sha256": key_generation_two.envelope_sha256,
                "manifest_schema_profile_sha256": schema_profile["profile_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
