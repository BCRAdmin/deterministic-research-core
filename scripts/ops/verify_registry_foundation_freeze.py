#!/usr/bin/env python3
"""Verify the immutable Registry Foundation 1.1.0 and Product mirror."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_bytes
from research_agent.semantic_compiler.registry_foundation.authority import (
    SemanticRegistryAuthority,
    verify_product_mirror,
)
from research_agent.semantic_compiler.semantic_wave.pass_protocol import (
    load_semantic_pass_contracts,
)

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
DEFAULT_MANIFEST = (
    RESEARCH_ROOT
    / "research_agent/semantic_compiler/registry_foundation/freeze/registry_foundation_manifest_v1_1.json"
)


class RegistryFreezeError(ValueError):
    """Raised when the frozen v1.1.0 surface differs from its manifest."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def verify_registry_foundation_freeze(
    manifest_path: Path = DEFAULT_MANIFEST,
    product_repo: Path = PRODUCT_ROOT,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("contract_id") != "room16.compiler.registry_foundation_freeze_manifest":
        raise RegistryFreezeError("registry_freeze_manifest_contract_invalid")
    if manifest.get("registry_foundation_version") != "1.1.0":
        raise RegistryFreezeError("registry_freeze_version_invalid")
    authority_path = (
        RESEARCH_ROOT
        / "research_agent/semantic_compiler/registry_foundation/config/registry_foundation_v1_1.json"
    )
    pass_path = (
        RESEARCH_ROOT
        / "research_agent/semantic_compiler/semantic_wave/config/semantic_wave_pass_contracts.json"
    )
    mirror_path = product_repo / "config/room16_semantic_registry_mirror_v1_1.json"
    lock_path = product_repo / "config/room16_semantic_registry_mirror_v1_1.lock.json"
    authority = SemanticRegistryAuthority.load(authority_path)
    _, pass_result = load_semantic_pass_contracts(pass_path)
    mirror_result = verify_product_mirror(
        authority_path=authority_path,
        mirror_path=mirror_path,
        lock_path=lock_path,
    )
    expected_hashes = {
        authority_path: manifest["authority"]["authority_file_sha256"],
        pass_path: manifest["pass_protocol"]["pass_contracts_file_sha256"],
        mirror_path: manifest["product_mirror"]["mirror_file_sha256"],
        lock_path: manifest["product_mirror"]["lock_file_sha256"],
    }
    changed = [str(path) for path, expected in expected_hashes.items() if _sha256(path) != expected]
    if changed:
        raise RegistryFreezeError(f"registry_foundation_frozen_file_changed:{changed}")
    checks = {
        "authority_hash": authority.authority_sha256
        == manifest["authority"]["authority_sha256"],
        "canonical_hash": authority.canonical_document_sha256()
        == manifest["authority"]["canonical_document_sha256"],
        "pass_hash": pass_result["pass_contracts_sha256"]
        == manifest["pass_protocol"]["pass_contracts_sha256"],
        "research_tag_commit": _git(
            RESEARCH_ROOT, "rev-parse", f"{manifest['git']['tag']}^{{}}"
        )
        == manifest["git"]["research_commit"],
        "product_tag_commit": _git(
            product_repo, "rev-parse", f"{manifest['git']['tag']}^{{}}"
        )
        == manifest["git"]["product_commit"],
        "product_mirror": mirror_result["status"] == "pass",
        "ba10_unauthorized": manifest["pass_protocol"]["ba10_authorized"] is False,
        "authority_bundle_v3_unchanged": manifest["authority"]["authority_bundle_changed"]
        is False,
    }
    if not all(checks.values()):
        raise RegistryFreezeError(f"registry_foundation_freeze_check_failed:{checks}")
    return {
        "status": "pass",
        "registry_foundation_version": "1.1.0",
        "authority_sha256": authority.authority_sha256,
        "pass_contracts_sha256": pass_result["pass_contracts_sha256"],
        "manifest_sha256": sha256_bytes(canonical_bytes(manifest)),
        "checks": checks,
    }


if __name__ == "__main__":
    print(json.dumps(verify_registry_foundation_freeze(), indent=2, sort_keys=True))
