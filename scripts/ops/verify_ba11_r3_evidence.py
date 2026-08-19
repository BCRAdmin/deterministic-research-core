#!/usr/bin/env python3
"""Independently derive BA11 R3 finding closure from a collected evidence directory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


RR2_FINDING_IDS = (
    "BA11-RR2-P0-001",
    "BA11-RR2-P0-002",
    "BA11-RR2-P0-003",
    "BA11-RR2-P0-004",
    "BA11-RR2-P0-005",
    "BA11-RR2-P0-006",
    "BA11-RR2-P0-007",
    "BA11-RR2-P1-001",
    "BA11-RR2-P1-002",
    "BA11-RR2-P1-003",
    "BA11-RR2-P1-004",
    "BA11-RR2-P1-005",
    "BA11-RR2-P2-001",
    "BA11-RR2-P2-002",
)
ORIGINAL_FINDING_IDS = tuple(f"BA11-AR-{index:03d}" for index in range(1, 19))
FORBIDDEN_COLLECTOR_OUTPUTS = (
    "00_R3_CORRECTION_VERDICT.md",
    "03_ORIGINAL_18_CLOSURE_MATRIX.json",
    "04_RR2_FINDING_CLOSURE_REGISTER.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
)


class EvidenceVerificationError(RuntimeError):
    """A fail-closed evidence verification failure."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def read_json(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise EvidenceVerificationError(f"missing evidence file: {relative}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceVerificationError(f"invalid JSON: {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceVerificationError(f"JSON root must be object: {relative}")
    return value


def _assert_collector_did_not_self_certify(root: Path) -> None:
    present = [relative for relative in FORBIDDEN_COLLECTOR_OUTPUTS if (root / relative).exists()]
    if present:
        raise EvidenceVerificationError(
            "collector attempted to write verifier-owned closure outputs: " + ", ".join(present)
        )


def _validate_receipts(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = document.get("command_receipts")
    if not isinstance(rows, list) or not rows:
        raise EvidenceVerificationError("test matrix has no command receipts")
    required = {
        "receipt_id",
        "relative_command",
        "relative_cwd",
        "exit_code",
        "git_commit",
        "git_tree",
        "full_worktree_status",
        "tool_versions",
        "complete_input_manifest_sha256",
        "raw_stdout",
        "raw_stdout_sha256",
        "normalized_stdout",
        "normalized_stdout_sha256",
        "raw_stderr",
        "raw_stderr_sha256",
        "started_at_attested_utc",
        "finished_at_attested_utc",
    }
    receipts: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not required <= set(row):
            raise EvidenceVerificationError("command receipt is incomplete")
        receipt_id = row["receipt_id"]
        if not isinstance(receipt_id, str) or receipt_id in receipts:
            raise EvidenceVerificationError("duplicate or invalid command receipt ID")
        if row["exit_code"] != 0:
            raise EvidenceVerificationError(f"command failed: {receipt_id}")
        for field in ("raw_stdout", "normalized_stdout", "raw_stderr"):
            expected = row[f"{field}_sha256"]
            if sha256_bytes(row[field].encode()) != expected:
                raise EvidenceVerificationError(f"receipt output hash mismatch: {receipt_id}/{field}")
        if Path(row["relative_cwd"]).is_absolute():
            raise EvidenceVerificationError(f"absolute cwd in receipt: {receipt_id}")
        command = row["relative_command"]
        if not isinstance(command, list) or not command:
            raise EvidenceVerificationError(f"invalid command in receipt: {receipt_id}")
        if any(isinstance(part, str) and Path(part).is_absolute() for part in command):
            raise EvidenceVerificationError(f"absolute command path in receipt: {receipt_id}")
        receipts[receipt_id] = row
    return receipts


def _validate_tests(
    document: dict[str, Any], receipts: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    rows = document.get("tests")
    if not isinstance(rows, list):
        raise EvidenceVerificationError("test matrix has no tests")
    tests: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise EvidenceVerificationError("invalid test row")
        test_id = row.get("test_id")
        if not isinstance(test_id, str) or test_id in tests:
            raise EvidenceVerificationError("duplicate or invalid test ID")
        if row.get("execution_status") != "PASS":
            raise EvidenceVerificationError(f"test not passed: {test_id}")
        receipt_ids = row.get("command_receipt_ids")
        if not isinstance(receipt_ids, list) or not receipt_ids:
            raise EvidenceVerificationError(f"test has no command receipt: {test_id}")
        if any(receipt_id not in receipts for receipt_id in receipt_ids):
            raise EvidenceVerificationError(f"test references missing command receipt: {test_id}")
        tests[test_id] = row
    return tests


def _validate_changed_file(root: Path, row: dict[str, Any]) -> None:
    repository = row.get("repository")
    relative = row.get("path")
    expected = row.get("sha256")
    if repository not in {"research", "product"} or not isinstance(relative, str):
        raise EvidenceVerificationError("invalid changed-file binding")
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise EvidenceVerificationError(f"unsafe changed-file path: {relative}")
    evidence_path = root / "implementation" / repository / relative
    if not evidence_path.is_file():
        raise EvidenceVerificationError(f"missing actual implementation file: {repository}/{relative}")
    if sha256_bytes(evidence_path.read_bytes()) != expected:
        raise EvidenceVerificationError(f"changed-file hash mismatch: {repository}/{relative}")


def verify_candidate(root: Path, *, write_outputs: bool) -> dict[str, Any]:
    """Verify collected evidence and optionally write verifier-owned closure outputs."""

    _assert_collector_did_not_self_certify(root)
    findings_document = read_json(root, "02_RR2_FINDINGS.json")
    source_findings = findings_document.get("findings")
    if not isinstance(source_findings, list):
        raise EvidenceVerificationError("source findings missing")
    source_by_id = {row.get("id"): row for row in source_findings if isinstance(row, dict)}
    if tuple(source_by_id) != RR2_FINDING_IDS:
        raise EvidenceVerificationError("RR2 finding set/order mismatch")
    source_original_matrix = read_json(
        root, "authority/SOURCE_R2_ORIGINAL_18_FINDING_STATUS_MATRIX.json"
    )
    source_original_rows = source_original_matrix.get("findings")
    if not isinstance(source_original_rows, list):
        raise EvidenceVerificationError("source original finding matrix missing")
    source_original_by_id = {
        row.get("finding_id"): row for row in source_original_rows if isinstance(row, dict)
    }
    if tuple(source_original_by_id) != ORIGINAL_FINDING_IDS:
        raise EvidenceVerificationError("source original finding set/order mismatch")

    test_document = read_json(root, "13_TEST_MATRIX_EXECUTED.json")
    receipts = _validate_receipts(test_document)
    tests = _validate_tests(test_document, receipts)
    required_test_ids = test_document.get("required_test_ids")
    if not isinstance(required_test_ids, list) or set(required_test_ids) != set(tests):
        raise EvidenceVerificationError("required/executed test ID set mismatch")

    mapping_document = read_json(root, "17_CHANGED_FILES_PER_FINDING.json")
    mappings = mapping_document.get("findings")
    if not isinstance(mappings, list):
        raise EvidenceVerificationError("finding mapping missing")
    mapping_by_id = {row.get("finding_id"): row for row in mappings if isinstance(row, dict)}
    if tuple(mapping_by_id) != RR2_FINDING_IDS:
        raise EvidenceVerificationError("finding mapping set/order mismatch")

    file_sets: list[tuple[str, ...]] = []
    closure_rows = []
    for finding_id in RR2_FINDING_IDS:
        source = source_by_id[finding_id]
        row = mapping_by_id[finding_id]
        changed_files = row.get("changed_files_with_sha256")
        executed_test_ids = row.get("exact_executed_test_ids")
        command_receipts = row.get("command_receipts")
        evidence_refs = row.get("evidence_refs")
        if not isinstance(changed_files, list) or not changed_files:
            raise EvidenceVerificationError(f"finding has no changed files: {finding_id}")
        if not isinstance(executed_test_ids, list) or not executed_test_ids:
            raise EvidenceVerificationError(f"finding has no tests: {finding_id}")
        if not isinstance(command_receipts, list) or not command_receipts:
            raise EvidenceVerificationError(f"finding has no command receipts: {finding_id}")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            raise EvidenceVerificationError(f"finding has no evidence refs: {finding_id}")
        if any(test_id not in tests for test_id in executed_test_ids):
            raise EvidenceVerificationError(f"finding references nonexistent test ID: {finding_id}")
        if any(tests[test_id].get("finding_id") != finding_id for test_id in executed_test_ids):
            raise EvidenceVerificationError(f"finding/test mapping mismatch: {finding_id}")
        if any(receipt_id not in receipts for receipt_id in command_receipts):
            raise EvidenceVerificationError(f"finding references missing receipt: {finding_id}")
        for relative in evidence_refs:
            if not isinstance(relative, str) or not (root / relative).is_file():
                raise EvidenceVerificationError(f"finding references missing evidence: {finding_id}")
        for changed_file in changed_files:
            if not isinstance(changed_file, dict):
                raise EvidenceVerificationError(f"invalid changed file: {finding_id}")
            _validate_changed_file(root, changed_file)
        file_sets.append(
            tuple(sorted(f"{item['repository']}:{item['path']}" for item in changed_files))
        )
        closure_rows.append(
            {
                **row,
                "source_finding_ids": [
                    original_id
                    for original_id, original in source_original_by_id.items()
                    if finding_id in original.get("rr2_findings", [])
                ],
                "exact_root_cause": source.get("problem"),
                "verifier_derived_status": "closed_verified",
                "closure_status": "closed_verified",
                "verifier_receipt": "independent_verifier/VERIFIER_RECEIPT.json",
            }
        )

    if len(set(file_sets)) != len(file_sets):
        raise EvidenceVerificationError("generic identical changed-file set reused across findings")

    original_rows = []
    for original_id in ORIGINAL_FINDING_IDS:
        source_original = source_original_by_id[original_id]
        sources = source_original.get("rr2_findings")
        if not isinstance(sources, list):
            raise EvidenceVerificationError(f"invalid original finding mapping: {original_id}")
        if not sources and source_original.get("status") != "CLOSED_VERIFIED":
            raise EvidenceVerificationError(
                f"unmapped original finding was not previously closed: {original_id}"
            )
        if any(source not in RR2_FINDING_IDS for source in sources):
            raise EvidenceVerificationError(f"unknown RR2 source for original finding: {original_id}")
        original_rows.append(
            {
                "finding_id": original_id,
                "derived_from_rr2_findings": sources,
                "status": "CLOSED_VERIFIED",
                "prior_independent_status": source_original.get("status"),
                "verifier_receipt": "independent_verifier/VERIFIER_RECEIPT.json",
            }
        )

    receipt_preimage = {
        "contract_id": "room16.ba11_r3.independent_evidence_verifier@1",
        "verdict": "PASS",
        "rr2_findings_sha256": sha256_bytes((root / "02_RR2_FINDINGS.json").read_bytes()),
        "test_matrix_sha256": sha256_bytes((root / "13_TEST_MATRIX_EXECUTED.json").read_bytes()),
        "mapping_sha256": sha256_bytes((root / "17_CHANGED_FILES_PER_FINDING.json").read_bytes()),
        "verified_rr2_finding_ids": list(RR2_FINDING_IDS),
        "verified_original_finding_ids": list(ORIGINAL_FINDING_IDS),
        "derivation_rules": [
            "collector_must_not_write_verifier_owned_outputs",
            "exact_source_finding_set_and_order",
            "exact_executed_test_set",
            "all_bound_command_receipts_exit_zero_and_hash_verify",
            "finding_specific_changed_file_sets_resolve_and_hash_verify",
            "all_evidence_refs_resolve",
            "all_original_findings_are_covered",
        ],
    }
    receipt = {**receipt_preimage, "verifier_receipt_sha256": sha256_bytes(canonical_json(receipt_preimage))}
    result = {
        "verdict": "PASS",
        "rr2_closure": {
            "contract_id": "room16.ba11_r3.rr2_finding_closure@1",
            "counts": findings_document.get("counts"),
            "findings": closure_rows,
        },
        "original_closure": {
            "contract_id": "room16.ba11_r3.original_18_closure@1",
            "findings": original_rows,
        },
        "receipt": receipt,
    }
    if write_outputs:
        verifier_dir = root / "independent_verifier"
        verifier_dir.mkdir(parents=True, exist_ok=True)
        (root / "04_RR2_FINDING_CLOSURE_REGISTER.json").write_bytes(
            canonical_json(result["rr2_closure"])
        )
        (root / "03_ORIGINAL_18_CLOSURE_MATRIX.json").write_bytes(
            canonical_json(result["original_closure"])
        )
        (verifier_dir / "VERIFIER_RECEIPT.json").write_bytes(canonical_json(receipt))
        (root / "00_R3_CORRECTION_VERDICT.md").write_text(
            "# BA11 R3 Correction Verdict\n\n"
            "The independent evidence verifier derived closure for all 14 RR2 findings and "
            "all 18 original R1 findings. The correction candidate is ready for independent "
            "rereview.\n\n"
            "`ba11_implementation_ready=false`; BA12, release, and publication remain "
            "unauthorized.\n",
            encoding="utf-8",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence_dir", type=Path)
    parser.add_argument("--write-outputs", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_candidate(args.evidence_dir, write_outputs=args.write_outputs)
    except EvidenceVerificationError as exc:
        print(json.dumps({"verdict": "STOP", "reason": str(exc)}, indent=2))
        return 1
    print(json.dumps({"verdict": result["verdict"], "receipt": result["receipt"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
