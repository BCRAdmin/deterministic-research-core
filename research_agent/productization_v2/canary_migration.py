"""Truthful WM/COST/ABT v2 dual-read migration canary builder."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from nacl.signing import SigningKey

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization.artifact_bundle import build_compiler_artifact_bundle
from research_agent.semantic_compiler.semantic_spine.rfc_0004 import replay_rfc_0004_archive

from .artifact_bundle import build_migration_bundle_v2, verify_compiler_artifact_bundle_v2
from .contracts import ConsumerPolicyV2, PublicKeyPolicyV2
from .trust_receipt import sign_bundle_receipt_v2, verify_bundle_receipt_v2

CANARY_STAMP = "8cf064d75c8c-20260814-115448"
CANARY_HASHES = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_identity(root: Path) -> str:
    files = [
        {"path": str(path.relative_to(root)), "bytes": path.stat().st_size, "sha256": _sha(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return sha256_json(files)


def build_migration_canary(
    *,
    ticker: str,
    archive: Path,
    output_root: Path,
    signing_key: SigningKey,
    key_id: str,
    counter: int,
    consumer_policy: ConsumerPolicyV2,
    key_policy: PublicKeyPolicyV2,
) -> dict[str, Any]:
    ticker = ticker.upper()
    if _sha(archive) != CANARY_HASHES[ticker]:
        raise ValueError(f"RFC8_CANARY_ARCHIVE_HASH_MISMATCH:{ticker}")
    first_v1 = output_root / "build_one/v1"
    second_v1 = output_root / "build_two/v1"
    first_v2 = output_root / "build_one/v2"
    second_v2 = output_root / "build_two/v2"
    if output_root.exists():
        shutil.rmtree(output_root)
    replay = replay_rfc_0004_archive(archive=archive)
    build_compiler_artifact_bundle(archive=archive, output_root=first_v1, replay=replay)
    build_compiler_artifact_bundle(archive=archive, output_root=second_v1, replay=replay)
    first = build_migration_bundle_v2(
        v1_bundle_root=first_v1,
        output_root=first_v2,
        consumer_policy=consumer_policy,
    )
    second = build_migration_bundle_v2(
        v1_bundle_root=second_v1,
        output_root=second_v2,
        consumer_policy=consumer_policy,
    )
    if first.bundle_sha256 != second.bundle_sha256 or _tree_identity(first_v2) != _tree_identity(
        second_v2
    ):
        raise ValueError(f"RFC8_CANARY_NONDETERMINISTIC:{ticker}")
    receipt_values = {
        "contract_id": "room16.compiler_artifact_bundle_receipt",
        "contract_version": 2,
        "receipt_id": f"rfc0008.{ticker.lower()}.migration",
        "bundle_sha256": first.bundle_sha256,
        "compile_identity_sha256": sha256_json(first.compile_identity),
        "compiler_identity_sha256": sha256_json(first.compiler_identity),
        "emitter_identity_sha256": sha256_json(first.emitter_identity),
        "policy_sha256": consumer_policy.policy_sha256,
        "ba10_v1_freeze_sha256": first.ba10_v1_freeze_sha256,
        "ba11_freeze_sha256": first.ba11_freeze_sha256,
        "research_key_id": key_id,
        "issued_at_utc": "2026-08-21T12:00:00Z",
        "not_after_utc": None,
        "monotonic_counter": counter,
        "nonce": f"rfc0008-{ticker.lower()}-migration-20260821",
        "signature_algorithm": "ed25519",
    }
    receipt = sign_bundle_receipt_v2(receipt_values, signing_key=signing_key)
    verify_bundle_receipt_v2(
        receipt,
        manifest=first,
        consumer_policy=consumer_policy,
        key_policy=key_policy,
        now_utc="2026-08-21T13:00:00Z",
    )
    verify_compiler_artifact_bundle_v2(first_v2, consumer_policy=consumer_policy)
    receipt_path = output_root / "receipt_v2.json"
    receipt_path.write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "ticker": ticker,
        "archive_sha256": _sha(archive),
        "v1_bundle_sha256": first.compile_identity.migration_v1_bundle_sha256,
        "v2_bundle_sha256": first.bundle_sha256,
        "v2_bundle_tree_sha256": _tree_identity(first_v2),
        "receipt": receipt.model_dump(mode="json"),
        "receipt_file_sha256": _sha(receipt_path),
        "semantic_artifact_index_sha256": first.artifact_index_sha256,
        "native_source_production": first.compatibility.native_source_production,
        "source_native_fact_generation": first.compatibility.source_native_fact_generation,
        "mode": first.compatibility.mode,
        "deterministic": True,
        "bundle_root": str(first_v2),
    }
