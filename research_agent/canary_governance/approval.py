"""Detached Ed25519 approval authenticity and replay protection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from research_agent.compiler_foundation.canonical import canonical_bytes

from .contracts import OperatorApprovalReceipt, complete_model_body, domain_hash
from .diagnostics import CanaryGovernanceError


def _signature_body(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key not in {"signature", "approval_sha256"}}


def sign_approval(values: dict[str, Any], signing_key: SigningKey) -> OperatorApprovalReceipt:
    body = complete_model_body(
        OperatorApprovalReceipt,
        _signature_body(values),
        OperatorApprovalReceipt.hash_field,
    )
    signature = signing_key.sign(canonical_bytes(body)).signature.hex()
    signed = {**body, "signature": signature}
    signed["approval_sha256"] = domain_hash(
        OperatorApprovalReceipt.hash_domain, signed
    )
    return OperatorApprovalReceipt(**signed)


def verify_approval(
    receipt: OperatorApprovalReceipt,
    *,
    trusted_keys: dict[str, VerifyKey],
    revoked_key_ids: set[str],
    consumed_nonces: set[str],
    minimum_counter: int,
    expected_scope: str,
    expected_subject_sha256s: tuple[str, ...],
    now_utc: str,
) -> None:
    if receipt.approver_key_id in revoked_key_ids:
        raise CanaryGovernanceError("BA11_APPROVAL_REVOKED")
    key = trusted_keys.get(receipt.approver_key_id)
    if key is None:
        raise CanaryGovernanceError("BA11_APPROVAL_SIGNATURE", "unknown_key")
    if receipt.nonce in consumed_nonces or receipt.monotonic_counter <= minimum_counter:
        raise CanaryGovernanceError("BA11_APPROVAL_REPLAY")
    if receipt.scope != expected_scope or receipt.subject_sha256s != expected_subject_sha256s:
        raise CanaryGovernanceError("BA11_APPROVAL_SCOPE")
    now = datetime.fromisoformat(now_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    if receipt.expires_at_utc:
        expiry = datetime.fromisoformat(receipt.expires_at_utc.replace("Z", "+00:00"))
        if now >= expiry:
            raise CanaryGovernanceError("BA11_APPROVAL_EXPIRED")
    body = _signature_body(receipt.model_dump(mode="json"))
    try:
        key.verify(canonical_bytes(body), bytes.fromhex(receipt.signature))
    except (BadSignatureError, ValueError) as exc:
        raise CanaryGovernanceError("BA11_APPROVAL_SIGNATURE") from exc
