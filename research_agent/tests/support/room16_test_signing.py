"""Room16 R16 TEST-ONLY Ed25519 signing helper.

This module is forbidden for production trust. The deterministic seed is public test data.
"""

from __future__ import annotations

import hashlib

from nacl.signing import SigningKey, VerifyKey

from research_agent.ba12_native.compiler import BundleSigningAuthority
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization_v2.contracts import PublicKeyPolicyV2


PRODUCTION_PUBLIC_KEY_HEX = "7287a555bbd5bb0302cc45d5b716c94ead99ed1a41840999e7d3c1aa7d889a2d"
TEST_KEY_ID = "room16.test_only.r16.ed25519.v1"
TEST_SEED_LABEL = b"room16-r16-hermetic-test-signing-key-v1"
TEST_SEED = hashlib.sha256(TEST_SEED_LABEL).digest()
TEST_SIGNING_KEY = SigningKey(TEST_SEED)
TEST_PUBLIC_KEY_HEX = TEST_SIGNING_KEY.verify_key.encode().hex()
EXPECTED_TEST_PUBLIC_KEY_HEX = "02437909a09e0c26aab1628ad1d80a18c005faf8d59beaf027bb0cc145e6fc09"

assert TEST_PUBLIC_KEY_HEX == EXPECTED_TEST_PUBLIC_KEY_HEX
assert TEST_PUBLIC_KEY_HEX != PRODUCTION_PUBLIC_KEY_HEX


def r16_test_key_policy() -> PublicKeyPolicyV2:
    body = {
        "contract_id": "room16.compiler.public_key_policy",
        "contract_version": 2,
        "owner": "research_compiler",
        "signature_algorithm": "ed25519",
        "keys": [
            {
                "key_id": TEST_KEY_ID,
                "public_key_hex": TEST_PUBLIC_KEY_HEX,
                "state": "active",
                "not_before_utc": "2000-01-01T00:00:00Z",
                "not_after_utc": None,
            }
        ],
        "rotation_sequence": ["active", "grace_verify_only", "revoked"],
    }
    return PublicKeyPolicyV2.model_validate({**body, "policy_sha256": sha256_json(body)})


def r16_test_signing_authority() -> BundleSigningAuthority:
    return BundleSigningAuthority(
        signing_key=TEST_SIGNING_KEY,
        key_id=TEST_KEY_ID,
        verification_key_policy=r16_test_key_policy(),
    )


def sign_test_payload(payload: bytes) -> bytes:
    return TEST_SIGNING_KEY.sign(payload).signature


def verify_test_payload(payload: bytes, signature: bytes) -> None:
    VerifyKey(bytes.fromhex(TEST_PUBLIC_KEY_HEX)).verify(payload, signature)


def r16_test_key_id() -> str:
    return "ROOM16_TEST_ONLY_R16_ED25519_V1"


def assert_not_production_key(public_key_hex: str) -> None:
    if public_key_hex.lower() == PRODUCTION_PUBLIC_KEY_HEX:
        raise AssertionError("TEST_SIGNER_MUST_NOT_EQUAL_PRODUCTION_TRUST_KEY")
