#!/usr/bin/env python3
"""Verify the accepted Room16 Compiler Foundation v1 freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json
from research_agent.compiler_foundation.registry import RegistryAuthority, verify_product_mirror

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    RESEARCH_ROOT
    / "research_agent/compiler_foundation/freeze/compiler_foundation_manifest_v1.json"
)


class FreezeVerificationError(RuntimeError):
    """Raised when any frozen Foundation reference differs."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_value(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise FreezeVerificationError(code)


def verify_foundation_freeze(*, manifest_path: Path, product_repo: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _require(manifest.get("contract_id") == "room16.compiler.foundation_manifest", "manifest_contract")
    _require(manifest.get("contract_version") == 1, "manifest_version")
    _require(manifest.get("compiler_foundation_version") == "1.0.0", "foundation_version")
    _require(manifest.get("status") == "accepted_frozen", "foundation_status")

    lock_inputs = manifest.get("version_lock_inputs")
    _require(isinstance(lock_inputs, dict), "version_lock_inputs")
    _require(
        sha256_json(lock_inputs) == manifest.get("version_lock_sha256"),
        "foundation_version_lock",
    )

    for relative, expected in manifest.get("foundation_source_files", {}).items():
        _require(_sha256_file(RESEARCH_ROOT / relative) == expected, f"foundation_source:{relative}")

    git = manifest["git"]
    tag = git["tag"]
    _require(
        _git_value(RESEARCH_ROOT, "rev-list", "-n", "1", tag) == git["research_commit"],
        "research_tag_target",
    )
    _require(
        _git_value(RESEARCH_ROOT, "rev-parse", f"refs/tags/{tag}") == git["research_tag_object"],
        "research_tag_object",
    )
    _require(
        _git_value(product_repo, "rev-list", "-n", "1", tag) == git["product_commit"],
        "product_tag_target",
    )
    _require(
        _git_value(product_repo, "rev-parse", f"refs/tags/{tag}") == git["product_tag_object"],
        "product_tag_object",
    )

    registry_path = RESEARCH_ROOT / "research_agent/compiler_foundation/config/registry_authority.json"
    authority = RegistryAuthority.load(registry_path)
    registry = manifest["registry_authority"]
    _require(authority.authority_sha256 == registry["authority_sha256"], "registry_authority_hash")
    _require(
        hashlib.sha256(canonical_bytes(authority.payload)).hexdigest()
        == registry["canonical_document_sha256"],
        "registry_canonical_hash",
    )
    _require(_sha256_file(registry_path) == registry["source_file_sha256"], "registry_file_hash")

    mirror_result = verify_product_mirror(
        registry_path,
        product_repo / "config/room16_compiler_registry_mirror.json",
        product_repo / "config/room16_compiler_registry_mirror.lock.json",
    )
    baseline_path = product_repo / "config/room16_canary_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    canary = manifest["canary_freeze"]
    _require(_sha256_file(baseline_path) == canary["baseline_file_sha256"], "canary_baseline_hash")
    _require(baseline.get("version_lock_sha256") == canary["version_lock_sha256"], "canary_lock")
    _require(baseline.get("candidate_sha256") == canary["candidate_sha256"], "canary_candidates")

    evidence = manifest["foundation_evidence"]
    evidence_path = RESEARCH_ROOT / evidence["archive"]
    _require(_sha256_file(evidence_path) == evidence["archive_sha256"], "foundation_evidence_hash")
    _require(manifest["development_boundary"]["foundation_changes_without_rfc_allowed"] is False, "rfc_boundary")
    _require(manifest["development_boundary"]["company_specific_architecture_changes_allowed"] is False, "company_boundary")

    return {
        "status": "pass",
        "compiler_foundation_version": manifest["compiler_foundation_version"],
        "foundation_version_lock_sha256": manifest["version_lock_sha256"],
        "research_commit": git["research_commit"],
        "product_commit": git["product_commit"],
        "git_tag": tag,
        "registry_authority_sha256": authority.authority_sha256,
        "product_mirror": mirror_result["status"],
        "canaries": "unchanged",
        "authority_bundle_version": manifest["authority_bundle"]["version"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--product-repo",
        type=Path,
        default=RESEARCH_ROOT.parent / "company-dossier-lab",
    )
    args = parser.parse_args()
    try:
        result = verify_foundation_freeze(
            manifest_path=args.manifest.resolve(),
            product_repo=args.product_repo.resolve(),
        )
    except (FreezeVerificationError, OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
