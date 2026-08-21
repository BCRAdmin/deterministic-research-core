#!/usr/bin/env python3
"""Independently verify a deterministic Room16 BA11 acceptance/freeze package."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import zipfile
from pathlib import Path
from typing import Any

from research_agent.canary_governance.archive import build_deterministic_zip
from research_agent.canary_governance.contracts import (
    EvidenceManifest,
    EvidencePackageIdentity,
)
from verify_ba11_canary_governance_freeze import freeze_sha256


REQUIRED = {
    "00_BA11_ACCEPTANCE_VERDICT.md",
    "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json",
    "02_BA11_FREEZE_RECORD.json",
    "03_STATUS_TRANSITION.json",
    "04_FREEZE_VERIFIER_RECEIPT.json",
    "05_R5_PACKAGE_BINDING.json",
    "06_BA10_FREEZE_RECEIPT.json",
    "07_FINAL_REGRESSION_RECEIPTS.json",
    "08_SOURCE_TREE_BINDINGS.json",
    "09_CHANGED_FILES.json",
    "10_FOREIGN_WORKTREE_BOUNDARY_REPORT.json",
    "11_NEXT_PHASE_GATE.md",
    "MANIFEST.json",
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json(members: dict[str, bytes], name: str) -> dict[str, Any]:
    value = json.loads(members[name])
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {name}")
    return value


def verify_package(archive_path: Path, sidecar_path: Path, identity_path: Path) -> dict[str, Any]:
    archive_bytes = archive_path.read_bytes()
    archive_sha = _sha256(archive_bytes)
    if sidecar_path.read_bytes() != f"{archive_sha}  {archive_path.name}\n".encode():
        raise ValueError("detached SHA-256 mismatch")
    identity = EvidencePackageIdentity.model_validate_json(
        identity_path.read_text(encoding="utf-8")
    )
    if (
        identity.package_filename != archive_path.name
        or identity.package_bytes != len(archive_bytes)
        or identity.package_sha256 != archive_sha
        or identity.detached_sha256_filename != sidecar_path.name
    ):
        raise ValueError("package identity mismatch")

    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise ValueError("corrupt ZIP member")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        if any(name.startswith("/") or posixpath.normpath(name).startswith("../") for name in names):
            raise ValueError("unsafe ZIP member")
        if REQUIRED - set(names):
            raise ValueError(f"missing required members: {sorted(REQUIRED - set(names))}")
        members = {name: archive.read(name) for name in names}

    manifest = EvidenceManifest.model_validate_json(members["MANIFEST.json"])
    if manifest.manifest_sha256 != identity.manifest_sha256:
        raise ValueError("manifest identity mismatch")
    listed = {row.path: row for row in manifest.files}
    payload = set(members) - {"MANIFEST.json"}
    if set(listed) != payload:
        raise ValueError("manifest payload scope mismatch")
    for name in payload:
        if listed[name].bytes != len(members[name]) or listed[name].sha256 != _sha256(
            members[name]
        ):
            raise ValueError(f"manifest member mismatch: {name}")
    rebuilt, rebuilt_manifest = build_deterministic_zip(
        {name: members[name] for name in payload},
        source_date_epoch=manifest.source_date_epoch,
    )
    if rebuilt != archive_bytes or rebuilt_manifest != manifest.model_dump(mode="json"):
        raise ValueError("deterministic ZIP rebuild mismatch")

    acceptance = _json(members, "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json")
    freeze = _json(members, "02_BA11_FREEZE_RECORD.json")
    transition = _json(members, "03_STATUS_TRANSITION.json")
    freeze_receipt = _json(members, "04_FREEZE_VERIFIER_RECEIPT.json")
    r5 = _json(members, "05_R5_PACKAGE_BINDING.json")
    ba10 = _json(members, "06_BA10_FREEZE_RECEIPT.json")
    regressions = _json(members, "07_FINAL_REGRESSION_RECEIPTS.json")
    changed = _json(members, "09_CHANGED_FILES.json")
    foreign = _json(members, "10_FOREIGN_WORKTREE_BOUNDARY_REPORT.json")

    if acceptance.get("verdict") != "ACCEPTED" or acceptance.get(
        "remaining_blocking_findings"
    ) != 0:
        raise ValueError("independent acceptance mismatch")
    if freeze.get("freeze_sha256") != freeze_sha256(freeze):
        raise ValueError("freeze self-hash mismatch")
    final = transition.get("after_successful_freeze", {})
    if not (
        final.get("ba11_implementation_ready") is True
        and final.get("ba11_frozen") is True
        and final.get("ba12_authorized") is False
        and final.get("release_authorized") is False
        and final.get("publication_authorized") is False
    ):
        raise ValueError("status transition mismatch")
    if freeze_receipt.get("status") != "PASS" or freeze_receipt.get("ba11_frozen") is not True:
        raise ValueError("freeze verifier receipt mismatch")
    if r5.get("status") != "PASS" or r5.get("source_r5", {}).get("sha256") != (
        "f81e08620fac195642291d279492c3751e86dbf5130697e3f8205e512023938c"
    ):
        raise ValueError("R5 package binding mismatch")
    if ba10.get("parsed_result", {}).get("status") != "PASS":
        raise ValueError("BA10 freeze receipt mismatch")
    required_receipts = {
        "freeze_verifier",
        "freeze_tests",
        "r5_collect",
        "r5_targeted",
        "r4_collect",
        "r4_targeted",
        "research_full",
        "research_ruff",
        "ba10_freeze",
        "product_pytest",
        "product_hardening",
        "product_full",
    }
    receipts = regressions.get("receipts", [])
    if required_receipts - {row.get("receipt_id") for row in receipts}:
        raise ValueError("final regression receipt set incomplete")
    if any(row.get("exit_code") != 0 for row in receipts):
        raise ValueError("one or more final regressions failed")
    if regressions.get("r5_exact_test_count") != 18 or regressions.get(
        "r4_exact_test_count"
    ) != 54:
        raise ValueError("exact R4/R5 collection count mismatch")
    if changed.get("ba11_runtime_files_changed") or changed.get("product_files_changed"):
        raise ValueError("runtime or Product files changed")
    if any(
        row.get("path", "").startswith("research_agent/canary_governance/")
        for row in changed.get("files", [])
    ):
        raise ValueError("BA11 runtime changed by freeze task")
    if foreign.get("unchanged") is not True or foreign.get(
        "foreign_scope_touched_by_room16_run"
    ) is not False:
        raise ValueError("foreign worktree boundary mismatch")
    return {
        "status": "PASS",
        "archive": archive_path.name,
        "archive_bytes": len(archive_bytes),
        "archive_sha256": archive_sha,
        "manifest_sha256": manifest.manifest_sha256,
        "member_count": len(members),
        "independent_rereview": "ACCEPTED",
        "ba11_implementation_ready": True,
        "ba11_frozen": True,
        "ba12_authorized": False,
        "deterministic_rebuild": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_package(args.archive, args.sidecar, args.identity)
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "STOP", "reason": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
