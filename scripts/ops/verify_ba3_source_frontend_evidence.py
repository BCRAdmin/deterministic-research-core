#!/usr/bin/env python3
"""Verify a BA3 Source Front-End evidence directory, archive and sidecar."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

EXPECTED_FILES = {
    "00_EXECUTIVE_SUMMARY.md",
    "01_CONTRACTS_AND_BOUNDARIES.md",
    "02_TEST_RESULTS.md",
    "03_WM_COST_ABT_SHADOW_REPLAYS.json",
    "04_BA3_VERDICT.json",
    "RESULT_MANIFEST.json",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(directory: Path, archive: Path) -> dict[str, object]:
    directory = directory.resolve()
    archive = archive.resolve()
    actual = {path.name for path in directory.iterdir() if path.is_file()}
    if actual != EXPECTED_FILES:
        raise ValueError("ba3_evidence_file_set_invalid")
    manifest = json.loads((directory / "RESULT_MANIFEST.json").read_text(encoding="utf-8"))
    if (
        manifest.get("contract_id") != "room16.compiler.ba3_evidence_manifest"
        or manifest.get("contract_version") != 1
        or manifest.get("verdict") != "ba3_complete_shadow_strangler"
    ):
        raise ValueError("ba3_evidence_manifest_invalid")
    listed = manifest.get("files")
    if not isinstance(listed, list) or manifest.get("file_count_excluding_manifest") != len(listed):
        raise ValueError("ba3_evidence_manifest_count_invalid")
    for item in listed:
        target = directory / item["path"]
        if (
            item["path"] == "RESULT_MANIFEST.json"
            or not target.is_file()
            or target.stat().st_size != item["bytes"]
            or _sha256(target) != item["sha256"]
        ):
            raise ValueError(f"ba3_evidence_file_hash_invalid:{item['path']}")
    verdict = json.loads((directory / "04_BA3_VERDICT.json").read_text(encoding="utf-8"))
    required_true = {
        "ba3_source_frontend_implemented",
        "compiler_foundation_unchanged",
        "authority_bundle_v3_unchanged",
        "wm_cost_abt_shadow_replay_passed",
        "legacy_candidate_archives_unchanged",
        "product_parallel_truth_absent",
    }
    if any(verdict.get(key) is not True for key in required_true):
        raise ValueError("ba3_verdict_required_status_false")
    if (
        verdict.get("live_network_cutover_performed") is not False
        or verdict.get("ba4_started") is not False
        or verdict.get("release_ready") is not False
        or verdict.get("publication_allowed") is not False
    ):
        raise ValueError("ba3_verdict_boundary_invalid")

    archive_sha = _sha256(archive)
    sidecar = archive.with_suffix(".zip.sha256")
    expected_sidecar = f"{archive_sha}  {archive.name}\n"
    if sidecar.read_text(encoding="utf-8") != expected_sidecar:
        raise ValueError("ba3_archive_sidecar_invalid")
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        expected_names = {f"{directory.name}/{name}" for name in EXPECTED_FILES}
        if names != expected_names:
            raise ValueError("ba3_archive_file_set_invalid")
        for name in EXPECTED_FILES:
            if bundle.read(f"{directory.name}/{name}") != (directory / name).read_bytes():
                raise ValueError(f"ba3_archive_content_invalid:{name}")
    return {
        "status": "pass",
        "directory": str(directory),
        "archive": str(archive),
        "archive_sha256": archive_sha,
        "research_commit": manifest["research_commit"],
        "verdict": manifest["verdict"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.directory, args.archive)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
