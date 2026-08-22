#!/usr/bin/env python3
"""Standalone verifier for the RFC-0008 acceptance/freeze evidence ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_DOMAIN = b"room16.rfc0008.v2_trust_freeze_evidence_manifest@1"
REQUIRED = {
    "00_FREEZE_VERDICT.md",
    "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json",
    "02_RFC0008_FREEZE_RECORD.json",
    "03_FREEZE_VERIFIER_RECEIPT.json",
    "04_FREEZE_MATRIX_EXECUTED.json",
    "05_FULL_REGRESSION_RECEIPTS.json",
    "06_SOURCE_TREE_BINDINGS.json",
    "07_PROTECTED_FILE_HASHES.json",
    "08_PRIVATE_KEY_ABSENCE.json",
    "09_FOREIGN_WORKTREE_BOUNDARY.json",
    "10_DETERMINISTIC_BUILD_REPORT.json",
    "11_BA12_RESUME_AUTHORIZATION.md",
    "MANIFEST.json",
}


class FreezeEvidenceError(RuntimeError):
    """Raised when the evidence package is not closed and deterministic."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def manifest_sha256(manifest: dict[str, Any]) -> str:
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    return hashlib.sha256(MANIFEST_DOMAIN + b"\0" + _canonical(body)).hexdigest()


def _json(data: bytes, name: str) -> dict[str, Any]:
    value = json.loads(data)
    if not isinstance(value, dict):
        raise FreezeEvidenceError(f"json_object_required:{name}")
    return value


def verify_package(package: Path) -> dict[str, Any]:
    package = package.resolve()
    if not package.is_file() or not zipfile.is_zipfile(package):
        raise FreezeEvidenceError("package_missing_or_not_zip")
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise FreezeEvidenceError("duplicate_member")
        for item in infos:
            member = PurePosixPath(item.filename)
            if member.is_absolute() or ".." in member.parts:
                raise FreezeEvidenceError(f"unsafe_member:{item.filename}")
            if stat.S_ISLNK(item.external_attr >> 16):
                raise FreezeEvidenceError(f"symlink_member:{item.filename}")
        if archive.testzip() is not None:
            raise FreezeEvidenceError("zip_crc_failure")
        missing = sorted(REQUIRED - set(names))
        if missing:
            raise FreezeEvidenceError(f"required_members_missing:{','.join(missing)}")

        manifest = _json(archive.read("MANIFEST.json"), "MANIFEST.json")
        if manifest.get("contract_id") != "room16.rfc0008.v2_trust_freeze_evidence@1":
            raise FreezeEvidenceError("manifest_contract")
        if manifest.get("manifest_sha256") != manifest_sha256(manifest):
            raise FreezeEvidenceError("manifest_self_hash")
        records = manifest.get("payloads")
        if not isinstance(records, list):
            raise FreezeEvidenceError("manifest_payloads")
        by_path = {row.get("path"): row for row in records if isinstance(row, dict)}
        expected_paths = set(names) - {"MANIFEST.json"}
        if set(by_path) != expected_paths:
            raise FreezeEvidenceError("payload_closure")
        for name in sorted(expected_paths):
            data = archive.read(name)
            row = by_path[name]
            if row.get("bytes") != len(data):
                raise FreezeEvidenceError(f"payload_size:{name}")
            if row.get("sha256") != hashlib.sha256(data).hexdigest():
                raise FreezeEvidenceError(f"payload_hash:{name}")

        freeze = _json(archive.read("02_RFC0008_FREEZE_RECORD.json"), "freeze")
        receipt = _json(archive.read("03_FREEZE_VERIFIER_RECEIPT.json"), "receipt")
        matrix = _json(archive.read("04_FREEZE_MATRIX_EXECUTED.json"), "matrix")
        regression = _json(archive.read("05_FULL_REGRESSION_RECEIPTS.json"), "regression")
        private = _json(archive.read("08_PRIVATE_KEY_ABSENCE.json"), "private")
        foreign = _json(archive.read("09_FOREIGN_WORKTREE_BOUNDARY.json"), "foreign")
        deterministic = _json(archive.read("10_DETERMINISTIC_BUILD_REPORT.json"), "determinism")

        if receipt.get("status") != "PASS" or receipt.get("rfc0008_frozen") is not True:
            raise FreezeEvidenceError("freeze_receipt")
        if matrix.get("row_count") != 20 or matrix.get("passed") != 20:
            raise FreezeEvidenceError("freeze_matrix")
        if regression.get("status") != "PASS":
            raise FreezeEvidenceError("full_regressions")
        if private.get("private_key_material_present") is not False:
            raise FreezeEvidenceError("private_key_material")
        if foreign.get("unchanged") is not True:
            raise FreezeEvidenceError("foreign_boundary")
        if deterministic.get("byte_identical") is not True:
            raise FreezeEvidenceError("determinism")
        if (
            freeze.get("rfc0008_frozen") is not True
            or freeze.get("ba12_resume_authorized") is not True
            or freeze.get("release_authorized") is not False
            or freeze.get("publication_authorized") is not False
            or freeze.get("deploy_authorized") is not False
        ):
            raise FreezeEvidenceError("frozen_status")

        private_markers = (b"-----BEGIN PRIVATE KEY-----\n", b"OPENSSH PRIVATE KEY")
        if any(marker in archive.read(name) for name in names for marker in private_markers):
            raise FreezeEvidenceError("private_key_marker")

    return {
        "contract_id": "room16.rfc0008.v2_trust_freeze_evidence_verifier@1",
        "status": "PASS",
        "package_name": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "zip_entries": len(names),
        "payload_count": len(records),
        "manifest_sha256": manifest["manifest_sha256"],
        "freeze_sha256": freeze["freeze_sha256"],
        "rfc0008_frozen": True,
        "ba12_resume_authorized": True,
        "private_key_material_present": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--receipt-output", type=Path)
    args = parser.parse_args()
    try:
        result = verify_package(args.package)
    except (OSError, KeyError, ValueError, json.JSONDecodeError, FreezeEvidenceError) as exc:
        result = {
            "contract_id": "room16.rfc0008.v2_trust_freeze_evidence_verifier@1",
            "status": "FAIL",
            "error": str(exc),
        }
    if args.receipt_output:
        args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
