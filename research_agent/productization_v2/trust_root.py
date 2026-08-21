"""Research-owned RFC-0008 trust root and signed policy-chain verification."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json

from .contracts import (
    ConsumerPolicyEnvelopeV2,
    PublicKeyPolicyEnvelopeV2,
    TrustRootV2,
)

Envelope = TypeVar("Envelope", ConsumerPolicyEnvelopeV2, PublicKeyPolicyEnvelopeV2)
CONFIG_ROOT = Path(__file__).resolve().parent / "config"
TRUST_ROOT_PATH = CONFIG_ROOT / "trust_root_v2.json"
CONSUMER_ENVELOPE_PATH = CONFIG_ROOT / "consumer_policy_envelope_v2.json"
KEY_ENVELOPE_PATH = CONFIG_ROOT / "public_key_policy_envelope_v2.json"


class TrustRootV2Error(ValueError):
    """Stable fail-closed trust-root diagnostic."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code = code
        self.detail = detail


def envelope_signature_body(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in values.items() if key not in {"signature", "envelope_sha256"}
    }


def envelope_signature_preimage(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": f"{values['contract_id']}@{values['contract_version']}",
        "value": envelope_signature_body(values),
    }


def envelope_domain_hash(values: dict[str, Any]) -> str:
    return sha256_json(
        {
            "domain": f"{values['contract_id']}.envelope_hash@{values['contract_version']}",
            "value": {key: value for key, value in values.items() if key != "envelope_sha256"},
        }
    )


def sign_policy_envelope(
    values: dict[str, Any],
    *,
    signing_key: SigningKey,
    model: type[Envelope],
) -> Envelope:
    unsigned = envelope_signature_body(
        {**values, "signature_algorithm": values.get("signature_algorithm", "ed25519")}
    )
    signature = signing_key.sign(
        canonical_bytes(envelope_signature_preimage(unsigned))
    ).signature.hex()
    signed = {**unsigned, "signature": signature}
    signed["envelope_sha256"] = envelope_domain_hash(signed)
    return model.model_validate(signed)


def verify_policy_envelope(envelope: Envelope, *, root: TrustRootV2) -> None:
    root.verify_self_hash()
    values = envelope.model_dump(mode="json")
    if envelope.root_id != root.root_id or envelope.root_key_id != root.root_key_id:
        raise TrustRootV2Error("RFC8_R2_POLICY_ROOT_MISMATCH")
    expected_contract = {
        "room16.compiler.consumer_policy_envelope": (
            root.consumer_policy_contract_id,
            root.consumer_policy_contract_version,
        ),
        "room16.compiler.public_key_policy_envelope": (
            root.public_key_policy_contract_id,
            root.public_key_policy_contract_version,
        ),
    }.get(envelope.contract_id)
    payload = envelope.payload
    if (
        expected_contract is None
        or (
            payload.contract_id,
            payload.contract_version,
        )
        != expected_contract
    ):
        raise TrustRootV2Error("RFC8_R2_POLICY_CONTRACT_MISMATCH")
    payload.verify_self_hash()
    if envelope_domain_hash(values) != envelope.envelope_sha256:
        raise TrustRootV2Error("RFC8_R2_POLICY_ENVELOPE_HASH_MISMATCH")
    try:
        VerifyKey(bytes.fromhex(root.root_public_key_hex)).verify(
            canonical_bytes(envelope_signature_preimage(values)),
            bytes.fromhex(envelope.signature),
        )
    except (BadSignatureError, ValueError) as exc:
        raise TrustRootV2Error("RFC8_R2_POLICY_ROOT_SIGNATURE_INVALID") from exc


def verify_policy_envelope_chain(envelopes: list[Envelope], *, root: TrustRootV2) -> Envelope:
    if not envelopes:
        raise TrustRootV2Error("RFC8_R2_POLICY_CHAIN_EMPTY")
    seen_hashes: set[str] = set()
    previous: Envelope | None = None
    for envelope in envelopes:
        verify_policy_envelope(envelope, root=root)
        if envelope.envelope_sha256 in seen_hashes:
            raise TrustRootV2Error("RFC8_R2_POLICY_CHAIN_FORK")
        seen_hashes.add(envelope.envelope_sha256)
        if previous is None:
            if envelope.generation != 1 or envelope.previous_envelope_sha256 is not None:
                raise TrustRootV2Error("RFC8_R2_POLICY_CHAIN_GENESIS_INVALID")
        elif (
            envelope.generation != previous.generation + 1
            or envelope.previous_envelope_sha256 != previous.envelope_sha256
        ):
            raise TrustRootV2Error("RFC8_R2_POLICY_CHAIN_ROLLBACK_OR_FORK")
        previous = envelope
    assert previous is not None
    return previous
