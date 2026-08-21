"""Research-owned Ed25519 receipts and fail-closed rotation verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json

from .contracts import (
    BundleReceiptV2,
    CompilerArtifactBundleManifestV2,
    ConsumerPolicyV2,
    PublicKeyPolicyV2,
    receipt_domain_hash,
    receipt_signature_body,
)


class ReceiptV2Error(ValueError):
    """Stable fail-closed v2 trust diagnostic."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass
class ReceiptVerificationState:
    consumed_nonces: set[str] = field(default_factory=set)
    minimum_counter_by_key: dict[str, int] = field(default_factory=dict)

    def consume(self, receipt: BundleReceiptV2) -> None:
        self.consumed_nonces.add(receipt.nonce)
        self.minimum_counter_by_key[receipt.research_key_id] = receipt.monotonic_counter


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def sign_bundle_receipt_v2(values: dict[str, Any], *, signing_key: SigningKey) -> BundleReceiptV2:
    body = receipt_signature_body(values)
    signature = signing_key.sign(canonical_bytes(body)).signature.hex()
    signed = {**body, "signature": signature}
    signed["receipt_sha256"] = receipt_domain_hash(signed)
    return BundleReceiptV2.model_validate(signed)


def verify_bundle_receipt_v2(
    receipt: BundleReceiptV2,
    *,
    manifest: CompilerArtifactBundleManifestV2,
    consumer_policy: ConsumerPolicyV2,
    key_policy: PublicKeyPolicyV2,
    now_utc: str,
    state: ReceiptVerificationState | None = None,
    consume: bool = False,
) -> None:
    consumer_policy.verify_self_hash()
    key_policy.verify_self_hash()
    expected = {
        "bundle_sha256": manifest.bundle_sha256,
        "compile_identity_sha256": sha256_json(manifest.compile_identity),
        "compiler_identity_sha256": sha256_json(manifest.compiler_identity),
        "emitter_identity_sha256": sha256_json(manifest.emitter_identity),
        "policy_sha256": consumer_policy.policy_sha256,
        "ba10_v1_freeze_sha256": manifest.ba10_v1_freeze_sha256,
        "ba11_freeze_sha256": manifest.ba11_freeze_sha256,
    }
    actual = receipt.model_dump(mode="json")
    for field_name, expected_value in expected.items():
        if actual[field_name] != expected_value:
            raise ReceiptV2Error("RFC8_RECEIPT_BINDING_MISMATCH", field_name)
    if receipt_domain_hash(actual) != receipt.receipt_sha256:
        raise ReceiptV2Error("RFC8_RECEIPT_HASH_MISMATCH")
    key_record = next(
        (item for item in key_policy.keys if item.key_id == receipt.research_key_id), None
    )
    if key_record is None:
        raise ReceiptV2Error("RFC8_RECEIPT_UNKNOWN_KEY")
    if key_record.state == "revoked":
        raise ReceiptV2Error("RFC8_RECEIPT_REVOKED_KEY")
    now = _utc(now_utc)
    if now < _utc(key_record.not_before_utc):
        raise ReceiptV2Error("RFC8_RECEIPT_KEY_NOT_ACTIVE")
    if key_record.not_after_utc and now >= _utc(key_record.not_after_utc):
        raise ReceiptV2Error("RFC8_RECEIPT_KEY_EXPIRED")
    if now < _utc(receipt.issued_at_utc):
        raise ReceiptV2Error("RFC8_RECEIPT_ISSUED_IN_FUTURE")
    if receipt.not_after_utc and now >= _utc(receipt.not_after_utc):
        raise ReceiptV2Error("RFC8_RECEIPT_EXPIRED")
    verification_state = state or ReceiptVerificationState()
    if receipt.nonce in verification_state.consumed_nonces:
        raise ReceiptV2Error("RFC8_RECEIPT_NONCE_REPLAY")
    if receipt.monotonic_counter <= verification_state.minimum_counter_by_key.get(
        receipt.research_key_id, 0
    ):
        raise ReceiptV2Error("RFC8_RECEIPT_COUNTER_REPLAY")
    try:
        VerifyKey(bytes.fromhex(key_record.public_key_hex)).verify(
            canonical_bytes(receipt_signature_body(actual)),
            bytes.fromhex(receipt.signature),
        )
    except (BadSignatureError, ValueError) as exc:
        raise ReceiptV2Error("RFC8_RECEIPT_SIGNATURE_INVALID") from exc
    if consume:
        verification_state.consume(receipt)
