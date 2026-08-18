#!/usr/bin/env python3
"""Print the Research-owned BA10 consumer policy lock as canonical JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research_agent.compiler_foundation.canonical import sha256_json

ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_PATHS = (
    "research_agent/productization/artifact_bundle.py",
    "research_agent/productization/contracts.py",
    "research_agent/productization/output_lineage.py",
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation-commit", required=True)
    args = parser.parse_args()
    if len(args.implementation_commit) != 40:
        raise SystemExit("full implementation commit required")
    files = [
        {"path": relative, "sha256": file_sha256(ROOT / relative)}
        for relative in IMPLEMENTATION_PATHS
    ]
    body = {
        "contract_id": "room16.compiler.consumer_policy_lock",
        "contract_version": 1,
        "owner": "research_compiler",
        "mirror_mode": "hash_verified_read_only",
        "product_may_edit_semantics": False,
        "artifact_bundle_contract_id": "room16.compiler_artifact_bundle",
        "artifact_bundle_contract_major": 1,
        "schema_version_min": "1.2.0",
        "schema_version_max": "1.2.0",
        "foundation_version": "1.0.0",
        "registry_foundation_version": "1.1.0",
        "semantic_wave_version": "1.0.0",
        "compiler_version": "1.0.0",
        "semantic_wave_version_lock": (
            "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
        ),
        "registry_authority_sha256": (
            "55585f2242f32da4cc401455cd3186a97bf74f2c4a7feb5078e00d6a6e1ea5fb"
        ),
        "pass_manifest_sha256": (
            "854abab7764f1a26a26ac2a97585171154aaac52c2eb8ecb848e800d2da02d33"
        ),
        "ir_schema_set_sha256": (
            "b7b6194ad05b023c1c1cb1fe2a5cba6d5f830dfd6ee400df954c35c997847f4c"
        ),
        "emitter_id": "room16.compiler_artifact_bundle_builder",
        "emitter_version": "1.2.0-rfc0005r2",
        "emitter_implementation_commit": args.implementation_commit,
        "emitter_implementation_files": files,
        "emitter_implementation_sha256": sha256_json(files),
        "emitter_schema_sha256": file_sha256(
            ROOT / "research_agent/productization/contracts.py"
        ),
        "producer_pass_id": "ba10.l11.emit_bundle",
        "canonicalization_profile": "room16.foundation.canonical_json@1",
        "hash_algorithm": "sha256",
        "bundle_required_compatibility_shadow": True,
        "legacy_bridge_active": True,
        "full_renderer_cutover": False,
        "product_parallel_truth_removed_in_canonical_path": True,
        "product_parallel_truth_removed_globally": False,
        "source_native_fact_generation": False,
        "authority_bundle_contract_id": "room16.research_authority_bundle",
        "authority_bundle_contract_version": 3,
        "bridge_contract_id": "room16.authority_v3_compatibility_view",
        "bridge_contract_version": 1,
        "renderer_cutover": False,
        "ba11_authorized": False,
        "ba12_authorized": False,
        "release_ready": False,
        "publication_allowed": False,
    }
    payload = {**body, "policy_sha256": sha256_json(body)}
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
