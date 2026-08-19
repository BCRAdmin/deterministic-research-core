from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from scripts.ops.verify_ba11_r3_evidence import (
    EvidenceVerificationError,
    ORIGINAL_FINDING_IDS,
    RR2_FINDING_IDS,
    verify_candidate,
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _write_json(root: Path, relative: str, value: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _candidate(root: Path) -> Path:
    findings = []
    for index, finding_id in enumerate(RR2_FINDING_IDS):
        findings.append(
            {
                "id": finding_id,
                "problem": f"root cause {index}",
                "required_fix": f"required fix {index}",
                "severity": finding_id.split("-")[2],
            }
        )
    _write_json(root, "02_RR2_FINDINGS.json", {"findings": findings, "counts": {"total": 14}})

    original_rows = []
    for index, original_id in enumerate(ORIGINAL_FINDING_IDS):
        original_rows.append(
            {
                "finding_id": original_id,
                "rr2_findings": [] if original_id in {"BA11-AR-015", "BA11-AR-017"} else [
                    RR2_FINDING_IDS[index % len(RR2_FINDING_IDS)]
                ],
                "status": "CLOSED_VERIFIED" if original_id in {"BA11-AR-015", "BA11-AR-017"} else "PARTIAL",
            }
        )
    _write_json(
        root,
        "authority/SOURCE_R2_ORIGINAL_18_FINDING_STATUS_MATRIX.json",
        {"findings": original_rows},
    )

    raw_stdout = "all tests passed\n"
    raw_stderr = ""
    receipt = {
        "receipt_id": "suite",
        "relative_command": ["python", "-m", "pytest"],
        "relative_cwd": "research",
        "exit_code": 0,
        "git_commit": "a" * 40,
        "git_tree": "b" * 40,
        "full_worktree_status": "## main...origin/main",
        "tool_versions": {"python": "3.12"},
        "complete_input_manifest_sha256": "c" * 64,
        "raw_stdout": raw_stdout,
        "raw_stdout_sha256": _sha(raw_stdout),
        "normalized_stdout": raw_stdout,
        "normalized_stdout_sha256": _sha(raw_stdout),
        "raw_stderr": raw_stderr,
        "raw_stderr_sha256": _sha(raw_stderr),
        "started_at_attested_utc": "2026-08-20T00:00:00Z",
        "finished_at_attested_utc": "2026-08-20T00:00:01Z",
    }
    tests = []
    mappings = []
    for index, finding_id in enumerate(RR2_FINDING_IDS):
        test_id = f"T-SYNTHETIC-{index:03d}"
        relative = f"finding-{index}.txt"
        contents = f"implementation for {finding_id}\n"
        path = root / "implementation/research" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        evidence_ref = f"reports/{index}.json"
        _write_json(root, evidence_ref, {"finding": finding_id})
        tests.append(
            {
                "test_id": test_id,
                "finding_id": finding_id,
                "execution_status": "PASS",
                "command_receipt_ids": ["suite"],
            }
        )
        mappings.append(
            {
                "finding_id": finding_id,
                "contract_delta_ids": [f"CD-{index}"],
                "changed_files_with_sha256": [
                    {"repository": "research", "path": relative, "sha256": _sha(contents)}
                ],
                "exact_executed_test_ids": [test_id],
                "negative_fixture_ids": [test_id],
                "command_receipts": ["suite"],
                "evidence_refs": [evidence_ref],
                "remaining_debt": None,
            }
        )
    _write_json(
        root,
        "13_TEST_MATRIX_EXECUTED.json",
        {
            "required_test_ids": [row["test_id"] for row in tests],
            "tests": tests,
            "command_receipts": [receipt],
        },
    )
    _write_json(root, "17_CHANGED_FILES_PER_FINDING.json", {"findings": mappings})
    return root


def _load(root: Path, relative: str) -> dict:
    return json.loads((root / relative).read_text(encoding="utf-8"))


def test_t_rr2_007_a_nonexistent_test_id_fails_bundle(tmp_path: Path):
    root = _candidate(tmp_path)
    mapping = _load(root, "17_CHANGED_FILES_PER_FINDING.json")
    mapping["findings"][0]["exact_executed_test_ids"] = ["DOES-NOT-EXIST"]
    _write_json(root, "17_CHANGED_FILES_PER_FINDING.json", mapping)
    with pytest.raises(EvidenceVerificationError, match="nonexistent test ID"):
        verify_candidate(root, write_outputs=False)


def test_t_rr2_007_b_generic_changed_file_set_fails_bundle(tmp_path: Path):
    root = _candidate(tmp_path)
    mapping = _load(root, "17_CHANGED_FILES_PER_FINDING.json")
    shared = copy.deepcopy(mapping["findings"][0]["changed_files_with_sha256"])
    for row in mapping["findings"]:
        row["changed_files_with_sha256"] = copy.deepcopy(shared)
    _write_json(root, "17_CHANGED_FILES_PER_FINDING.json", mapping)
    with pytest.raises(EvidenceVerificationError, match="generic identical"):
        verify_candidate(root, write_outputs=False)


def test_t_rr2_007_c_collector_cannot_write_final_closure(tmp_path: Path):
    root = _candidate(tmp_path)
    _write_json(root, "04_RR2_FINDING_CLOSURE_REGISTER.json", {"hardcoded": True})
    with pytest.raises(EvidenceVerificationError, match="collector attempted"):
        verify_candidate(root, write_outputs=False)


def test_missing_actual_implementation_file_fails_finding_closure(tmp_path: Path):
    root = _candidate(tmp_path)
    (root / "implementation/research/finding-3.txt").unlink()
    with pytest.raises(EvidenceVerificationError, match="missing actual implementation"):
        verify_candidate(root, write_outputs=False)


def test_t_rr2_012_a_failed_or_tampered_receipt_invalidates_closure(tmp_path: Path):
    root = _candidate(tmp_path)
    matrix = _load(root, "13_TEST_MATRIX_EXECUTED.json")
    matrix["command_receipts"][0]["raw_stdout"] = "tampered\n"
    _write_json(root, "13_TEST_MATRIX_EXECUTED.json", matrix)
    with pytest.raises(EvidenceVerificationError, match="output hash mismatch"):
        verify_candidate(root, write_outputs=False)


def test_t_rr2_012_b_verifier_derives_closure_and_receipt(tmp_path: Path):
    root = _candidate(tmp_path)
    result = verify_candidate(root, write_outputs=True)
    assert result["verdict"] == "PASS"
    assert len(result["rr2_closure"]["findings"]) == 14
    assert len(result["original_closure"]["findings"]) == 18
    assert (root / "independent_verifier/VERIFIER_RECEIPT.json").is_file()
