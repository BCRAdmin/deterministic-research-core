#!/usr/bin/env python3
"""Standalone verifier for the deterministic BA12 native-trust STOP evidence ZIP."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

DOMAIN = b"room16.ba12.native_trust_stop_evidence.manifest@1\0"
REQUIRED = {
    "00_STOP_VERDICT.md",
    "01_MACHINE_STOP_EVIDENCE.json",
    "02_NATIVE_TRUST_PROBE_RECEIPT.json",
    "03_RFC0008_FREEZE_VERIFIER_RECEIPT.json",
    "04_RFC_0007.md",
    "05_RFC0008_FREEZE_RECORD.json",
    "06_SOURCE_TREE_BINDINGS.json",
    "07_FOREIGN_REPOSITORY_BOUNDARY.json",
    "08_REQUIRED_RFC_DECISION.md",
    "MANIFEST.json",
    "changed_sources/research/docs/compiler_foundation/rfcs/BA12_R2_NATIVE_TRUST_CONFLICT_STOP.json",
    "changed_sources/research/docs/compiler_foundation/rfcs/RFC-0007_BA12_FINAL_STRANGLER_CUTOVER.md",
    "changed_sources/research/research_agent/tests/test_ba12_native_trust_stop.py",
    "changed_sources/research/scripts/ops/verify_ba12_rfc0008_native_trust_conflict.py",
}


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(DOMAIN + encoded).hexdigest()


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not REQUIRED <= set(names):
            raise ValueError("BA12_STOP_EVIDENCE_MEMBER_SET_INVALID")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest_hash(manifest) != manifest["manifest_sha256"]:
            raise ValueError("BA12_STOP_EVIDENCE_MANIFEST_HASH_INVALID")
        records = manifest["payloads"]
        if [item["path"] for item in records] != sorted(set(names) - {"MANIFEST.json"}):
            raise ValueError("BA12_STOP_EVIDENCE_MANIFEST_CLOSURE_INVALID")
        for item in records:
            payload = archive.read(item["path"])
            if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item[
                "sha256"
            ]:
                raise ValueError("BA12_STOP_EVIDENCE_PAYLOAD_HASH_INVALID")
        stop = json.loads(archive.read("01_MACHINE_STOP_EVIDENCE.json"))
        probe = json.loads(archive.read("02_NATIVE_TRUST_PROBE_RECEIPT.json"))
        freeze = json.loads(archive.read("03_RFC0008_FREEZE_VERIFIER_RECEIPT.json"))
        foreign = json.loads(archive.read("07_FOREIGN_REPOSITORY_BOUNDARY.json"))
        if (
            stop["status"] != "STOPPED_RFC_TRIGGER_REQUIRED"
            or stop["stop_conditions"] != [2, 6, 7, 8]
            or probe["diagnostic_code"] != "RFC8_TRUST_POLICY_MISMATCH"
            or probe["checks"]["truthful_native_bundle_rejected_by_frozen_verifier"] is not True
            or freeze["status"] != "PASS"
            or freeze["rfc0008_frozen"] is not True
            or foreign["unchanged"] is not True
        ):
            raise ValueError("BA12_STOP_EVIDENCE_SEMANTICS_INVALID")
        markers = (b"-----BEGIN " + b"PRIVATE KEY-----", b"OPENSSH " + b"PRIVATE KEY")
        if any(marker in archive.read(name) for name in names for marker in markers):
            raise ValueError("BA12_STOP_EVIDENCE_PRIVATE_KEY_MARKER")
    return {
        "contract_id": "room16.ba12.native_trust_stop_evidence_verifier@1",
        "status": "PASS",
        "package": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "zip_entries": len(names),
        "manifest_sha256": manifest["manifest_sha256"],
        "diagnostic_code": stop["diagnostic_code"],
        "stop_conditions": stop["stop_conditions"],
        "rfc_trigger_required": True,
    }


def main() -> int:
    result = verify_package(Path(sys.argv[1]).resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
