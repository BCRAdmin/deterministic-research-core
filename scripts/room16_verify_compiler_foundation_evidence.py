#!/usr/bin/env python3
"""Independent fail-closed verifier for a Room16 BA0-BA2 evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

REQUIRED = {
    "00_EXECUTIVE_SUMMARY.md",
    "01_ARCHITECTURE_DECISION_RECORDS.md",
    "02_LAYER_AND_OWNERSHIP_CONSTITUTION.md",
    "03_IR_CONTRACTS.md",
    "04_PASS_PROTOCOL.md",
    "05_REGISTRY_AUTHORITY.md",
    "06_DIAGNOSTIC_AND_VERDICT_CONTRACT.md",
    "07_COMPATIBILITY_AND_VERSIONING_POLICY.md",
    "08_CHANGED_FILES.md",
    "09_TEST_RESULTS.md",
    "10_SHADOW_REPLAY_RESULTS.md",
    "11_WM_COST_ABT_CANARY_DIFFS.md",
    "12_PRODUCT_MIRROR_CONFORMANCE.md",
    "13_FOUNDATION_WAVE_VERDICT.json",
    "RESULT_MANIFEST.json",
}
REQUIRED_STATUSES = {
    "architecture_frozen",
    "compiler_kernel_implemented",
    "registry_authority_established",
    "shadow_replay_passed",
    "legacy_output_unchanged",
    "canaries_unchanged",
    "product_parallel_truth_absent",
    "semantic_compiler_wave_ready",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_directory(root: Path) -> dict:
    actual = {item.name for item in root.iterdir() if item.is_file()}
    if actual != REQUIRED:
        raise ValueError(f"evidence inventory mismatch: missing={sorted(REQUIRED-actual)} extra={sorted(actual-REQUIRED)}")
    manifest = json.loads((root / "RESULT_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("contract_id") != "room16.compiler.foundation_evidence_manifest":
        raise ValueError("manifest contract invalid")
    if manifest.get("all_required_files_present") is not True:
        raise ValueError("manifest required-file verdict invalid")
    declared = manifest.get("files")
    if not isinstance(declared, list) or len(declared) != 14:
        raise ValueError("manifest file list invalid")
    for item in declared:
        path = root / item["path"]
        data = path.read_bytes()
        if len(data) != item["bytes"] or sha256(data) != item["sha256"]:
            raise ValueError(f"evidence file hash mismatch: {item['path']}")
    verdict = json.loads((root / "13_FOUNDATION_WAVE_VERDICT.json").read_text(encoding="utf-8"))
    if verdict.get("verdict") != "pass" or verdict.get("scope") != ["BA0", "BA1", "BA2"]:
        raise ValueError("Foundation verdict invalid")
    if any(verdict.get(status) is not True for status in REQUIRED_STATUSES):
        raise ValueError("one or more Foundation statuses are not true")
    if verdict.get("ba3_started") is not False:
        raise ValueError("BA3 must not be started")
    if verdict.get("release_ready") is not False or verdict.get("publication_allowed") is not False:
        raise ValueError("Foundation evidence must not claim release/publication readiness")
    return {"foundation_id": verdict["foundation_id"], "file_count": len(actual)}


def verify_archive(archive_path: Path, directory: Path) -> dict:
    with zipfile.ZipFile(archive_path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"archive CRC failure: {bad}")
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names}
        if roots != {directory.name}:
            raise ValueError("archive root mismatch")
        if {PurePosixPath(name).name for name in names} != REQUIRED:
            raise ValueError("archive evidence inventory mismatch")
        for name in names:
            local = directory / PurePosixPath(name).name
            if archive.read(name) != local.read_bytes():
                raise ValueError(f"archive/directory byte mismatch: {name}")
    return {"archive_sha256": sha256(archive_path.read_bytes()), "archive_file_count": len(names)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    if args.bundle.suffix == ".zip":
        archive = args.bundle.resolve()
        directory = archive.with_suffix("")
    else:
        directory = args.bundle.resolve()
        archive = directory.with_suffix(".zip")
    result = {"status": "PASS", **verify_directory(directory), **verify_archive(archive, directory)}
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
