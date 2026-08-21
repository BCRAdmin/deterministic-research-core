#!/usr/bin/env python3
"""Standalone fail-closed verifier for the RFC-0008 R2 evidence ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

MANIFEST_DOMAIN = "room16.rfc0008.v2_trust_migration_evidence_manifest@2"
RESEARCH_BASE = "add974e6d93c095a3aa7ca607c0d85acf60058e0"
PRODUCT_BASE = "874e3f02f758f90e8fe9cb6394dda9fa884bbd0c"
BA10_FREEZE = "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e"
BA11_FREEZE = "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf"
REQUIRED_MEMBERS = {
    "00_R1_INDEPENDENT_VERDICT.md",
    "01_R2_FINDINGS.json",
    "02_BASELINE_LOCK.json",
    "03_TRUST_ROOT.json",
    "04_CONSUMER_POLICY_ENVELOPE.json",
    "05_KEY_POLICY_ENVELOPE.json",
    "06_ROTATION_REPORT.json",
    "07_COMPILER_IDENTITY_REPORT.json",
    "08_SCHEMA_PARITY_REPORT.json",
    "09_CANARY_REPORT.json",
    "10_R2_EXECUTED_ACCEPTANCE_MATRIX.json",
    "11_R1_REGRESSION_MATRIX.json",
    "12_BA10_V1_FREEZE.json",
    "13_BA11_FREEZE.json",
    "14_FULL_REGRESSION_RECEIPTS.json",
    "15_SOURCE_TREE_BINDINGS.json",
    "16_CHANGED_FILES_BY_FINDING.json",
    "17_PRIVATE_KEY_ABSENCE.json",
    "18_FOREIGN_REPOSITORY_BOUNDARY.json",
    "19_DETERMINISTIC_BUILD.json",
    "20_INDEPENDENT_REREVIEW_REQUEST.md",
    "independent_verifier/VERIFIER_RECEIPT.json",
}
FORBIDDEN_PATH_RE = re.compile(
    r"(?:^|/)(?:\.runtime|private(?:_key)?|signing_key|root_signing_key)(?:[./_-]|$)|\.(?:pem|key|p12)$",
    re.IGNORECASE,
)
FORBIDDEN_CONTENT = (b"-----BEGIN PRIVATE KEY-----", b"-----BEGIN OPENSSH PRIVATE KEY-----")


class EvidenceVerificationError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        bool(name)
        and not name.startswith("/")
        and "\\" not in name
        and ".." not in path.parts
        and path.as_posix() == name
        and not name.endswith("/")
    )


def verify_package(package: Path) -> dict[str, Any]:
    package = package.resolve()
    if not package.is_file():
        raise EvidenceVerificationError("RFC8_R2_EVIDENCE_PACKAGE_MISSING")
    package_bytes = package.read_bytes()
    try:
        archive = zipfile.ZipFile(package)
    except zipfile.BadZipFile as exc:
        raise EvidenceVerificationError("RFC8_R2_EVIDENCE_ZIP_INVALID") from exc
    with archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_DUPLICATE_MEMBER")
        if not all(safe_member(name) for name in names):
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_UNSAFE_MEMBER")
        if archive.testzip() is not None:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_ZIP_CRC_INVALID")
        if "MANIFEST.json" not in names:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_MANIFEST_MISSING")
        manifest = json.loads(archive.read("MANIFEST.json"))
        expected_manifest_fields = {
            "acceptance",
            "baseline_lock",
            "contract_id",
            "contract_version",
            "files",
            "final_state",
            "generated_date",
            "manifest_hash_domain",
            "manifest_hash_preimage_rule",
            "manifest_sha256",
            "payload_rule",
        }
        if set(manifest) != expected_manifest_fields:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_MANIFEST_SCHEMA_INVALID")
        if (
            manifest["contract_id"] != "room16.rfc0008.v2_trust_migration_evidence_manifest"
            or manifest["contract_version"] != 2
            or manifest["manifest_hash_domain"] != MANIFEST_DOMAIN
            or manifest["manifest_hash_preimage_rule"]
            != "sha256(canonical_json({domain,value:manifest_without_manifest_sha256}))"
            or manifest["payload_rule"] != "all ZIP members except MANIFEST.json"
        ):
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_MANIFEST_CONTRACT_INVALID")
        manifest_body = dict(manifest)
        manifest_body.pop("manifest_sha256")
        expected_manifest_sha = sha256_bytes(
            canonical_bytes({"domain": MANIFEST_DOMAIN, "value": manifest_body})
        )
        if manifest["manifest_sha256"] != expected_manifest_sha:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_MANIFEST_SELF_HASH_INVALID")
        file_records = manifest["files"]
        if not isinstance(file_records, list):
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_FILE_INDEX_INVALID")
        indexed_names = [item.get("path") for item in file_records]
        expected_names = sorted(name for name in names if name != "MANIFEST.json")
        if indexed_names != expected_names or len(indexed_names) != len(set(indexed_names)):
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_PAYLOAD_CLOSURE_INVALID")
        if not REQUIRED_MEMBERS.issubset(set(indexed_names)):
            missing = sorted(REQUIRED_MEMBERS - set(indexed_names))
            raise EvidenceVerificationError(
                "RFC8_R2_EVIDENCE_REQUIRED_MEMBER_MISSING:" + ",".join(missing)
            )
        private_key_material_present = False
        for record in file_records:
            if set(record) != {"bytes", "path", "sha256"}:
                raise EvidenceVerificationError("RFC8_R2_EVIDENCE_FILE_RECORD_INVALID")
            payload = archive.read(record["path"])
            if record["bytes"] != len(payload) or record["sha256"] != sha256_bytes(payload):
                raise EvidenceVerificationError(
                    "RFC8_R2_EVIDENCE_PAYLOAD_HASH_INVALID:" + record["path"]
                )
            if FORBIDDEN_PATH_RE.search(record["path"]) or any(
                marker in payload for marker in FORBIDDEN_CONTENT
            ):
                private_key_material_present = True
        if private_key_material_present:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_PRIVATE_KEY_MATERIAL_PRESENT")
        baseline = manifest["baseline_lock"]
        if baseline != {
            "ba10_v1_freeze_sha256": BA10_FREEZE,
            "ba11_freeze_sha256": BA11_FREEZE,
            "product_base": PRODUCT_BASE,
            "research_base": RESEARCH_BASE,
        }:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_BASELINE_DRIFT")
        acceptance = manifest["acceptance"]
        if acceptance != {
            "r1_matrix_passed": 45,
            "r1_matrix_total": 45,
            "r2_matrix_passed": 45,
            "r2_matrix_total": 45,
        }:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_ACCEPTANCE_INCOMPLETE")
        if manifest["final_state"] != {
            "ba12_implementation_ready": False,
            "ba12_resume_authorized": False,
            "deploy_allowed": False,
            "publication_allowed": False,
            "ready_for_independent_rereview": True,
            "release_allowed": False,
            "rfc0008_frozen": False,
            "rfc0008_implementation_ready": False,
        }:
            raise EvidenceVerificationError("RFC8_R2_EVIDENCE_FINAL_GATE_INVALID")
    return {
        "contract_id": "room16.rfc0008.v2_trust_migration_verifier_receipt",
        "contract_version": 1,
        "status": "PASS",
        "package_name": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": sha256_bytes(package_bytes),
        "manifest_sha256": manifest["manifest_sha256"],
        "payload_count": len(file_records),
        "required_members_verified": len(REQUIRED_MEMBERS),
        "private_key_material_present": False,
        "ready_for_independent_rereview": True,
        "rfc0008_implementation_ready": False,
        "rfc0008_frozen": False,
        "ba12_resume_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--receipt-output", type=Path)
    args = parser.parse_args()
    try:
        receipt = verify_package(args.package)
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "diagnostic": str(exc)}, indent=2))
        return 1
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt_output:
        args.receipt_output.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
