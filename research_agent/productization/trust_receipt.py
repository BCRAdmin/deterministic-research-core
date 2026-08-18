"""Research-owned detached receipts for BA10 consumer bundle trust.

The receipt set lives outside CompilerArtifactBundle bytes.  Product may mirror
it read-only, but accepts the mirror only when its canonical hash is pinned in
Product code.  This is the RFC-0005-R2 permitted detached-hash alternative to
operator-managed signing keys.
"""

from __future__ import annotations

from typing import Any, Iterable

from research_agent.compiler_foundation.canonical import sha256_json


RECEIPT_CONTRACT = "room16.compiler_artifact_bundle_receipt"
RECEIPT_SET_CONTRACT = "room16.compiler_artifact_bundle_receipt_set"
SIGNATURE_ALGORITHM = "research_owned_detached_sha256_pin"


def build_bundle_receipt(manifest: dict[str, Any], *, issued_by_key_id: str) -> dict[str, Any]:
    body = {
        "contract_id": RECEIPT_CONTRACT,
        "contract_version": 1,
        "bundle_sha256": manifest["bundle_sha256"],
        "compiler_identity": manifest["compiler_identity"],
        "emitter_identity": manifest["emitter_identity"],
        "policy_identity": {
            "contract_id": "room16.compiler.consumer_policy_lock",
            "contract_version": 1,
            "policy_sha256": manifest["emitter_identity"]["consumer_policy_sha256"],
        },
        "compile_identity": manifest["compile_identity"],
        "issued_by_key_id": issued_by_key_id,
        "signature_algorithm": SIGNATURE_ALGORITHM,
    }
    signed = {**body, "signature": sha256_json(body)}
    return {**signed, "receipt_sha256": sha256_json(signed)}


def build_receipt_set(
    manifests: Iterable[dict[str, Any]], *, issued_by_key_id: str, research_commit: str
) -> dict[str, Any]:
    receipts = sorted(
        (build_bundle_receipt(item, issued_by_key_id=issued_by_key_id) for item in manifests),
        key=lambda item: item["bundle_sha256"],
    )
    body = {
        "contract_id": RECEIPT_SET_CONTRACT,
        "contract_version": 1,
        "owner": "research_compiler",
        "mirror_mode": "hash_pinned_read_only",
        "research_commit": research_commit,
        "receipts": receipts,
    }
    return {**body, "receipt_set_sha256": sha256_json(body)}


def verify_receipt_set(payload: dict[str, Any]) -> None:
    body = dict(payload)
    declared = body.pop("receipt_set_sha256", None)
    if (
        body.get("contract_id") != RECEIPT_SET_CONTRACT
        or body.get("contract_version") != 1
        or body.get("owner") != "research_compiler"
        or body.get("mirror_mode") != "hash_pinned_read_only"
        or sha256_json(body) != declared
    ):
        raise ValueError("ABI_BUNDLE_RECEIPT_SET_INVALID")
    for receipt in body.get("receipts", []):
        receipt_body = dict(receipt)
        receipt_hash = receipt_body.pop("receipt_sha256", None)
        signature = receipt_body.pop("signature", None)
        if (
            receipt_body.get("contract_id") != RECEIPT_CONTRACT
            or receipt_body.get("contract_version") != 1
            or receipt_body.get("signature_algorithm") != SIGNATURE_ALGORITHM
            or sha256_json(receipt_body) != signature
            or sha256_json({**receipt_body, "signature": signature}) != receipt_hash
        ):
            raise ValueError("ABI_BUNDLE_RECEIPT_INVALID")
