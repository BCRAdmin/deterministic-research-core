"""Frozen-archive shadow replay; never invokes a research or product run."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .canonical import sha256_bytes
from .contracts import ContractError, CompilerLayer, IREnvelope, ProvenanceRef
from .kernel import PassKernel, identity_shadow_pass, load_pass_manifests
from .registry import RegistryAuthority


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _root_manifest_name(names: list[str]) -> str:
    candidates = [name for name in names if len(PurePosixPath(name).parts) == 2 and name.endswith("/MANIFEST.json")]
    if len(candidates) != 1:
        raise ContractError("candidate ZIP must contain exactly one root MANIFEST.json")
    return candidates[0]


def shadow_replay_candidate(
    zip_path: Path,
    *,
    ticker: str,
    expected_zip_sha256: str,
    expected_authority_contract_version: int = 3,
) -> dict[str, Any]:
    before = file_sha256(zip_path)
    if before != expected_zip_sha256:
        raise ContractError(f"frozen candidate hash mismatch for {ticker}")
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad:
            raise ContractError(f"ZIP CRC failure: {bad}")
        names = archive.namelist()
        root_manifest_name = _root_manifest_name(names)
        root = root_manifest_name.rsplit("/", 1)[0]
        manifest = json.loads(archive.read(root_manifest_name))
        if manifest.get("ticker") != ticker:
            raise ContractError(f"candidate ticker mismatch: expected {ticker}")
        if manifest.get("contract_version") != expected_authority_contract_version:
            raise ContractError("candidate contract version mismatch")
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise ContractError("candidate manifest has no file inventory")
        verified = 0
        for item in files:
            relative = item.get("path")
            if not isinstance(relative, str) or relative.startswith("/") or ".." in PurePosixPath(relative).parts:
                raise ContractError("unsafe manifest path")
            data = archive.read(f"{root}/{relative}")
            if len(data) != item.get("bytes") or sha256_bytes(data) != item.get("sha256"):
                raise ContractError(f"manifest entry mismatch: {relative}")
            verified += 1
        authority_manifest_path = f"{root}/case/research/authority_bundle/authority_manifest.json"
        authority_manifest = json.loads(archive.read(authority_manifest_path))
        if (
            authority_manifest.get("contract_id") != "room16.research_authority_bundle"
            or authority_manifest.get("contract_version") != expected_authority_contract_version
        ):
            raise ContractError("Authority Bundle v3 contract mismatch")

    provenance = ProvenanceRef(
        source_id=f"frozen_candidate:{ticker}",
        artifact_path=str(zip_path),
        sha256=before,
        locator=root_manifest_name,
    )
    payload = {
        "ticker": ticker,
        "candidate_zip_sha256": before,
        "candidate_manifest_sha256": sha256_bytes(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()),
        "verified_manifest_entries": verified,
        "authority_contract_version": expected_authority_contract_version,
        "authority_contract_id": authority_manifest["contract_id"],
        "shadow_mode": True,
        "legacy_execution_invoked": False,
        "renderer_invoked": False,
        "llm_invoked": False,
    }
    initial = IREnvelope.create(
        ir_type="legacy.frozen_candidate",
        layer=CompilerLayer.L0_COMPILE_INTAKE,
        producer_pass_id="legacy.frozen_input",
        payload=payload,
        provenance_refs=(provenance,),
    )
    manifests = load_pass_manifests()
    kernel = PassKernel(manifests, RegistryAuthority.load())
    implementations = {item.pass_id: identity_shadow_pass for item in manifests}
    final_ir, first = kernel.execute(initial, implementations)
    cached_ir, cached = kernel.execute(initial, implementations)
    replay_ir, replayed = PassKernel(manifests, RegistryAuthority.load()).execute(
        initial, implementations, replay=first
    )
    after = file_sha256(zip_path)
    pass_count = len(manifests)
    checks = {
        "archive_hash_verified": before == expected_zip_sha256,
        "archive_unchanged": before == after,
        "all_manifest_entries_verified": verified == len(files),
        "authority_bundle_v3_verified": authority_manifest["contract_version"] == 3,
        "all_layers_observed": len(first) == 12,
        "first_run_executed": all(item.status.value == "executed" for item in first),
        "second_run_cache_hit": all(item.status.value == "cache_hit" for item in cached),
        "replay_hash_verified": all(item.status.value == "replayed" for item in replayed),
        "payload_unchanged_across_passes": final_ir.payload_sha256 == initial.payload_sha256,
        "cache_output_equal": cached_ir.payload_sha256 == final_ir.payload_sha256,
        "replay_output_equal": replay_ir.payload_sha256 == final_ir.payload_sha256,
        "no_legacy_execution": payload["legacy_execution_invoked"] is False,
        "no_renderer_execution": payload["renderer_invoked"] is False,
        "no_llm_execution": payload["llm_invoked"] is False,
    }
    if pass_count != 12 or not all(checks.values()):
        raise ContractError(f"shadow replay failed for {ticker}: {checks}")
    return {
        "contract_id": "room16.compiler.shadow_replay_result",
        "contract_version": 1,
        "ticker": ticker,
        "status": "pass",
        "input_zip": str(zip_path),
        "input_zip_sha256_before": before,
        "input_zip_sha256_after": after,
        "verified_manifest_entries": verified,
        "pass_records": [item.model_dump(mode="json") for item in first],
        "cache_records": [item.model_dump(mode="json") for item in cached],
        "replay_records": [item.model_dump(mode="json") for item in replayed],
        "checks": checks,
    }
