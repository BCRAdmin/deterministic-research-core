"""Alpha Software/SaaS successor emitter without changing frozen BA12 files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from nacl.signing import SigningKey

from research_agent.ba12_native.compiler import (
    BA11_GOVERNANCE_SNAPSHOT_SHA256,
    KINDS,
    SIGNING_KEY,
    NativeCompileResult,
    _read_snapshot_payloads,
    build_native_bundle,
)
from research_agent.ba12_native.contracts import NativeRunReceipt, create_record
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization_v2.native_trust import (
    load_native_trust,
    verify_native_bundle_v2,
)
from research_agent.productization_v2.trust_receipt import sign_bundle_receipt_v2
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR

from .projection import build_saas_semantic_artifacts


def _write_json(path: Path, value: object) -> bytes:
    payload = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _refresh_manifest(
    *, bundle_root: Path, artifacts: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    manifest = json.loads((bundle_root / "BUNDLE_MANIFEST.json").read_text())
    artifact_hashes: dict[str, str] = {}
    by_kind = {item["artifact_kind"]: item for item in manifest["artifacts"]}
    for kind in sorted(KINDS):
        payload = _write_json(bundle_root / "artifacts" / f"{kind}.json", artifacts[kind])
        digest = hashlib.sha256(payload).hexdigest()
        artifact_hashes[kind] = digest
        entry = by_kind[kind]
        entry["sha256"] = digest
        entry["byte_length"] = len(payload)
        entry["contract_id"] = artifacts[kind]["contract_id"]
        entry["contract_version"] = artifacts[kind]["contract_version"]
    manifest["emitter_identity"]["implementation_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    manifest["compile_identity"]["final_compile_state_sha256"] = artifact_hashes[
        "compile_state"
    ]
    manifest["compile_identity"]["verification_report_sha256"] = artifact_hashes[
        "verification_report"
    ]
    manifest["compile_identity"]["replay_sha256"] = artifacts["verification_report"][
        "replay_sha256"
    ]
    manifest["extensions"]["alpha_saas_development_successor"] = {
        "contract_id": "room16.alpha.saas_development_contract",
        "contract_version": 1,
        "architecture_reopened": False,
        "ticker_specific_rules": False,
    }
    for section in manifest["sections"]:
        if section["section_id"] in artifact_hashes:
            section["sha256"] = artifact_hashes[section["section_id"]]
    manifest["artifact_index_sha256"] = sha256_json(manifest["artifacts"])
    manifest["section_index_sha256"] = sha256_json(manifest["sections"])
    manifest["bundle_sha256"] = sha256_json(
        {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    )
    _write_json(bundle_root / "BUNDLE_MANIFEST.json", manifest)
    return manifest


def build_alpha_saas_bundle(
    *,
    snapshot: SourceSnapshotIR,
    snapshot_root: Path,
    output_root: Path,
    research_commit: str,
    research_tree: str,
    monotonic_counter: int,
) -> NativeCompileResult:
    """Emit a signed Alpha SaaS Bundle@2 using only additive successor code."""

    bundle_root = output_root.resolve()
    if bundle_root.exists():
        raise ValueError("ALPHA_SAAS_OUTPUT_ALREADY_EXISTS")
    build_native_bundle(
        snapshot=snapshot,
        snapshot_root=snapshot_root,
        output_root=bundle_root,
        research_commit=research_commit,
        research_tree=research_tree,
        monotonic_counter=monotonic_counter,
    )
    payloads = _read_snapshot_payloads(snapshot, snapshot_root)
    artifacts = build_saas_semantic_artifacts(snapshot=snapshot, payloads=payloads)
    if set(artifacts) != set(KINDS):
        raise ValueError("ALPHA_SAAS_ARTIFACT_CLOSURE_INVALID")
    manifest = _refresh_manifest(bundle_root=bundle_root, artifacts=artifacts)

    trust = load_native_trust()
    key_policy = trust["key_policy"]
    signing_key = SigningKey(SIGNING_KEY.read_bytes())
    if signing_key.verify_key.encode().hex() != key_policy.keys[0].public_key_hex:
        raise ValueError("ALPHA_SAAS_SIGNING_KEY_POLICY_MISMATCH")
    receipt_set_sha = sha256_json(
        [item.model_dump(mode="json") for item in snapshot.retrieval_receipts]
    )
    receipt_model = sign_bundle_receipt_v2(
        {
            "contract_id": "room16.compiler_artifact_bundle_receipt",
            "contract_version": 2,
            "receipt_id": (
                f"rfc0008.alpha.saas.{snapshot.ticker.lower()}.{manifest['bundle_sha256'][:16]}"
            ),
            "bundle_sha256": manifest["bundle_sha256"],
            "compile_identity_sha256": sha256_json(manifest["compile_identity"]),
            "compiler_identity_sha256": sha256_json(manifest["compiler_identity"]),
            "emitter_identity_sha256": sha256_json(manifest["emitter_identity"]),
            "policy_sha256": trust["policy"].policy_sha256,
            "ba10_v1_freeze_sha256": manifest["ba10_v1_freeze_sha256"],
            "ba11_freeze_sha256": manifest["ba11_freeze_sha256"],
            "research_key_id": key_policy.keys[0].key_id,
            "issued_at_utc": f"{snapshot.as_of_date}T23:00:00Z",
            "not_after_utc": None,
            "monotonic_counter": monotonic_counter,
            "nonce": f"alpha.saas.{snapshot.ticker.lower()}.{manifest['bundle_sha256'][:24]}",
            "signature_algorithm": "ed25519",
        },
        signing_key=signing_key,
    )
    receipt = receipt_model.model_dump(mode="json")
    _write_json(bundle_root / "RECEIPT.json", receipt)
    verification = verify_native_bundle_v2(
        bundle_root,
        receipt=receipt,
        now_utc=f"{snapshot.as_of_date}T23:30:00Z",
    )
    run_receipt = create_record(
        NativeRunReceipt,
        ticker=snapshot.ticker,
        as_of_date=snapshot.as_of_date,
        compile_request_sha256=snapshot.request_sha256,
        source_acquisition_sha256=snapshot.acquisition_plan_sha256,
        retrieval_receipt_set_sha256=receipt_set_sha,
        source_snapshot_sha256=snapshot.snapshot_sha256,
        pass_execution_profile_sha256=sha256_json(artifacts["pass_execution_records"]),
        compiler_artifact_bundle_sha256=manifest["bundle_sha256"],
        ba11_governance_snapshot_sha256=BA11_GOVERNANCE_SNAPSHOT_SHA256,
        research_commit=research_commit,
        research_tree=research_tree,
        semantic_input="source_snapshot_ir_only",
        legacy_semantic_input_allowed=False,
        status="PASS",
    )
    _write_json(bundle_root / "NATIVE_RUN_RECEIPT.json", run_receipt.model_dump(mode="json"))
    return NativeCompileResult(bundle_root, manifest, receipt, run_receipt, verification)
