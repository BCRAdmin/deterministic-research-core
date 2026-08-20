"""Role-separated Ed25519 attestations with fail-closed replay checks.

Verification is intentionally side-effect free. Nonce/counter consumption is
performed by the registry transaction's single atomic head swap.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from research_agent.compiler_foundation.canonical import canonical_bytes

from .contracts import (
    HashBoundModel,
    IndependentReviewAttestation,
    OperatorApprovalReceipt,
    ResearchSnapshotAuthorityReceipt,
    complete_model_body,
    domain_hash,
)
from .diagnostics import CanaryGovernanceError


@dataclass(frozen=True)
class TrustedRoleKeyPolicy:
    operator_keys: dict[str, VerifyKey]
    reviewer_keys: dict[str, VerifyKey]
    research_keys: dict[str, VerifyKey]

    def __post_init__(self) -> None:
        role_ids = [set(self.operator_keys), set(self.reviewer_keys), set(self.research_keys)]
        if role_ids[0] & role_ids[1] or role_ids[0] & role_ids[2] or role_ids[1] & role_ids[2]:
            raise CanaryGovernanceError("BA11_ROLE_KEY_OVERLAP", "key_id_overlap")
        operator_values = {bytes(key) for key in self.operator_keys.values()}
        reviewer_values = {bytes(key) for key in self.reviewer_keys.values()}
        research_values = {bytes(key) for key in self.research_keys.values()}
        if (
            operator_values & reviewer_values
            or operator_values & research_values
            or reviewer_values & research_values
        ):
            raise CanaryGovernanceError("BA11_ROLE_KEY_OVERLAP", "public_key_overlap")


def _signature_body(values: dict[str, Any], hash_field: str) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key not in {"signature", hash_field}}


def _sign(model_type: type[HashBoundModel], values: dict[str, Any], signing_key: SigningKey):
    body = complete_model_body(
        model_type,
        _signature_body(values, model_type.hash_field),
        model_type.hash_field,
    )
    signature = signing_key.sign(canonical_bytes(body)).signature.hex()
    signed = {**body, "signature": signature}
    signed[model_type.hash_field] = domain_hash(model_type.hash_domain, signed)
    return model_type(**signed)


def sign_approval(values: dict[str, Any], signing_key: SigningKey) -> OperatorApprovalReceipt:
    return _sign(OperatorApprovalReceipt, values, signing_key)


def sign_independent_review(
    values: dict[str, Any], signing_key: SigningKey
) -> IndependentReviewAttestation:
    return _sign(IndependentReviewAttestation, values, signing_key)


def sign_research_snapshot_receipt(
    values: dict[str, Any], signing_key: SigningKey
) -> ResearchSnapshotAuthorityReceipt:
    return _sign(ResearchSnapshotAuthorityReceipt, values, signing_key)


def _verify_signature(
    receipt: HashBoundModel,
    *,
    key: VerifyKey,
    signature_code: str,
) -> None:
    body = _signature_body(receipt.model_dump(mode="json"), receipt.hash_field)
    try:
        key.verify(canonical_bytes(body), bytes.fromhex(receipt.signature))
    except (BadSignatureError, ValueError) as exc:
        raise CanaryGovernanceError(signature_code) from exc


def _verify_time_and_replay(
    *,
    issued_at_utc: str,
    expires_at_utc: str | None,
    nonce: str,
    counter: int,
    consumed_nonces: set[str],
    minimum_counter: int,
    now_utc: str,
    replay_code: str,
    expired_code: str,
) -> None:
    now = datetime.fromisoformat(now_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    issued = datetime.fromisoformat(issued_at_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
    if issued > now:
        raise CanaryGovernanceError(expired_code, "issued_in_future")
    if expires_at_utc:
        expiry = datetime.fromisoformat(expires_at_utc.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        if now >= expiry:
            raise CanaryGovernanceError(expired_code)
    if nonce in consumed_nonces or counter <= minimum_counter:
        raise CanaryGovernanceError(replay_code)


def verify_approval(
    receipt: OperatorApprovalReceipt,
    *,
    trusted_role_key_policy: TrustedRoleKeyPolicy,
    revoked_key_ids: set[str],
    consumed_nonces: set[str],
    minimum_monotonic_counter: int,
    expected_decision: str,
    expected_scope: str,
    expected_subject_ids: tuple[str, ...],
    expected_subject_sha256s: tuple[str, ...],
    expected_finding_set_sha256: str,
    expected_previous_registry_head_sha256: str,
    fixed_now_utc: str,
) -> None:
    if receipt.approver_key_id in revoked_key_ids:
        raise CanaryGovernanceError("BA11_APPROVAL_REVOKED")
    key = trusted_role_key_policy.operator_keys.get(receipt.approver_key_id)
    if key is None:
        raise CanaryGovernanceError("BA11_APPROVAL_SIGNATURE", "unknown_operator_key")
    if receipt.decision != expected_decision or receipt.decision != "approve":
        raise CanaryGovernanceError("BA11_APPROVAL_DECISION")
    if receipt.scope != expected_scope:
        raise CanaryGovernanceError("BA11_APPROVAL_SCOPE")
    if (
        receipt.subject_ids != expected_subject_ids
        or receipt.subject_sha256s != expected_subject_sha256s
    ):
        raise CanaryGovernanceError("BA11_APPROVAL_SUBJECT")
    if receipt.review_finding_set_sha256 != expected_finding_set_sha256:
        raise CanaryGovernanceError("BA11_APPROVAL_FINDING_SET")
    if receipt.previous_registry_head_sha256 != expected_previous_registry_head_sha256:
        raise CanaryGovernanceError("BA11_APPROVAL_PREVIOUS_HEAD")
    _verify_time_and_replay(
        issued_at_utc=receipt.issued_at_utc,
        expires_at_utc=receipt.expires_at_utc,
        nonce=receipt.nonce,
        counter=receipt.monotonic_counter,
        consumed_nonces=consumed_nonces,
        minimum_counter=minimum_monotonic_counter,
        now_utc=fixed_now_utc,
        replay_code="BA11_APPROVAL_REPLAY",
        expired_code="BA11_APPROVAL_EXPIRED",
    )
    _verify_signature(receipt, key=key, signature_code="BA11_APPROVAL_SIGNATURE")


def verify_independent_review(
    receipt: IndependentReviewAttestation,
    *,
    trusted_role_key_policy: TrustedRoleKeyPolicy,
    revoked_key_ids: set[str],
    consumed_nonces: set[str],
    minimum_monotonic_counter: int,
    expected_decision: str,
    expected_scope: str,
    expected_subject_ids: tuple[str, ...],
    expected_subject_sha256s: tuple[str, ...],
    expected_finding_set_sha256: str,
    expected_previous_registry_head_sha256: str,
    fixed_now_utc: str,
) -> None:
    if receipt.reviewer_key_id in revoked_key_ids:
        raise CanaryGovernanceError("BA11_ATTESTATION_REVOKED")
    key = trusted_role_key_policy.reviewer_keys.get(receipt.reviewer_key_id)
    if key is None:
        raise CanaryGovernanceError("BA11_ATTESTATION_SIGNATURE", "unknown_reviewer_key")
    if receipt.decision != expected_decision or receipt.decision != "accepted":
        raise CanaryGovernanceError("BA11_ATTESTATION_DECISION")
    if receipt.scope != expected_scope:
        raise CanaryGovernanceError("BA11_ATTESTATION_SCOPE")
    if (
        receipt.subject_ids != expected_subject_ids
        or receipt.subject_sha256s != expected_subject_sha256s
    ):
        raise CanaryGovernanceError("BA11_ATTESTATION_SUBJECT")
    if receipt.finding_set_sha256 != expected_finding_set_sha256:
        raise CanaryGovernanceError("BA11_ATTESTATION_FINDING_SET")
    if receipt.previous_registry_head_sha256 != expected_previous_registry_head_sha256:
        raise CanaryGovernanceError("BA11_ATTESTATION_PREVIOUS_HEAD")
    _verify_time_and_replay(
        issued_at_utc=receipt.issued_at_utc,
        expires_at_utc=receipt.expires_at_utc,
        nonce=receipt.nonce,
        counter=receipt.monotonic_counter,
        consumed_nonces=consumed_nonces,
        minimum_counter=minimum_monotonic_counter,
        now_utc=fixed_now_utc,
        replay_code="BA11_ATTESTATION_REPLAY",
        expired_code="BA11_ATTESTATION_EXPIRED",
    )
    _verify_signature(receipt, key=key, signature_code="BA11_ATTESTATION_SIGNATURE")


def verify_research_snapshot_receipt(
    receipt: ResearchSnapshotAuthorityReceipt,
    *,
    trusted_role_key_policy: TrustedRoleKeyPolicy,
    expected_snapshot_sha256: str,
    expected_registry_head_sha256: str,
) -> None:
    key = trusted_role_key_policy.research_keys.get(receipt.research_key_id)
    if key is None:
        raise CanaryGovernanceError("BA11_RESEARCH_AUTHORITY_UNTRUSTED", "unknown_research_key")
    if (
        receipt.snapshot_sha256 != expected_snapshot_sha256
        or receipt.registry_head_sha256 != expected_registry_head_sha256
    ):
        raise CanaryGovernanceError("BA11_RESEARCH_AUTHORITY_UNTRUSTED", "authority_hash_mismatch")
    _verify_signature(receipt, key=key, signature_code="BA11_RESEARCH_AUTHORITY_UNTRUSTED")
