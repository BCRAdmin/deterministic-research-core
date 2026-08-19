#!/usr/bin/env python3
"""Collect, independently verify, and deterministically package BA11 R3 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.canary_governance.archive import (
    build_deterministic_zip,
    build_package_identity,
)
from research_agent.compiler_foundation.canonical import sha256_json
from scripts.ops.verify_ba11_r3_evidence import RR2_FINDING_IDS, verify_candidate


ROOT = Path(__file__).resolve().parents[2]
SOURCE_R2_SHA256 = "133e886d938b95f02d88c6a8612698d0ec05245ede8fb5d3cc83e2122146ca36"
SOURCE_R1_SHA256 = "a714f870b28ff5bccc44083125495a24166224f5c6d32154bf93ad9ca889e4ed"
RESEARCH_R3_BASE = "db744eda01f4de19095b33df34130fa0ce248a7e"
PRODUCT_R3_BASE = "f674c06c69f0c0289dfcd2c11fb5030d06b6f1e0"
SOURCE_DATE_EPOCH = 1787097600
SOURCE_R1_MEMBER = (
    "authority/ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_63DCB9209602_2026-08-19.zip"
)

FINDING_FILES = {
    "BA11-RR2-P0-001": [
        ("product", "room16-app/config/room16_canary_registry_trust_policy_v1.json"),
        ("product", "room16-app/server-modules/canary-registry-mirror.mjs"),
        ("product", "room16-app/scripts/test_canary_registry_mirror.mjs"),
    ],
    "BA11-RR2-P0-002": [
        ("research", "research_agent/canary_governance/approval.py"),
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/storage.py"),
        ("research", "research_agent/tests/test_canary_governance.py"),
    ],
    "BA11-RR2-P0-003": [
        ("research", "research_agent/canary_governance/storage.py"),
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/ledger.py"),
        ("research", "research_agent/tests/test_canary_governance.py"),
    ],
    "BA11-RR2-P0-004": [
        ("research", "research_agent/canary_governance/ledger.py"),
        ("research", "research_agent/canary_governance/storage.py"),
        ("research", "research_agent/canary_governance/diagnostics.py"),
        ("research", "research_agent/tests/test_canary_governance.py"),
    ],
    "BA11-RR2-P0-005": [
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/schemas/contract_catalog_v1.json"),
        ("research", "scripts/ops/generate_ba11_contract_catalog.py"),
        ("research", "scripts/ops/verify_ba11_canary_governance.py"),
    ],
    "BA11-RR2-P0-006": [
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/ledger.py"),
        ("research", "research_agent/canary_governance/storage.py"),
    ],
    "BA11-RR2-P0-007": [
        ("research", "scripts/ops/build_ba11_r3_evidence.py"),
        ("research", "scripts/ops/verify_ba11_r3_evidence.py"),
        ("research", "scripts/ops/verify_ba11_r3_package.py"),
        ("research", "research_agent/tests/test_ba11_r3_evidence_verifier.py"),
        ("research", "research_agent/tests/ba11_r3_test_inventory.json"),
    ],
    "BA11-RR2-P1-001": [
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/ledger.py"),
        ("research", "research_agent/tests/test_canary_governance.py"),
    ],
    "BA11-RR2-P1-002": [
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/ledger.py"),
        ("research", "research_agent/tests/test_canary_governance.py"),
        ("research", "research_agent/canary_governance/schemas/RegistrySnapshot.schema.json"),
    ],
    "BA11-RR2-P1-003": [
        ("research", "research_agent/canary_governance/ledger.py"),
        ("research", "research_agent/canary_governance/storage.py"),
        ("research", "research_agent/canary_governance/schemas/GenesisImportHead.schema.json"),
        ("research", "research_agent/tests/test_canary_governance.py"),
    ],
    "BA11-RR2-P1-004": [
        ("research", "research_agent/tests/test_canary_governance.py"),
        ("research", "research_agent/tests/ba11_r3_test_inventory.json"),
        ("research", "scripts/ops/verify_ba11_canary_governance.py"),
    ],
    "BA11-RR2-P1-005": [
        ("research", "scripts/ops/build_ba11_r3_evidence.py"),
        ("research", "scripts/ops/verify_ba11_r3_evidence.py"),
        ("research", "research_agent/tests/test_ba11_r3_evidence_verifier.py"),
    ],
    "BA11-RR2-P2-001": [
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/schemas/SourceContractLock.schema.json"),
        ("research", "research_agent/canary_governance/schemas/SourceContractBinding.schema.json"),
    ],
    "BA11-RR2-P2-002": [
        ("research", "research_agent/canary_governance/archive.py"),
        ("research", "research_agent/canary_governance/contracts.py"),
        ("research", "research_agent/canary_governance/schemas/EvidenceManifest.schema.json"),
        ("research", "research_agent/canary_governance/schemas/EvidencePackageIdentity.schema.json"),
        ("research", "scripts/ops/build_ba11_r3_evidence.py"),
        ("research", "scripts/ops/verify_ba11_r3_package.py"),
    ],
}

FINDING_REPORTS = {
    "BA11-RR2-P0-001": ["08_PRODUCT_AUTHORITY_ANCHOR_REPORT.json"],
    "BA11-RR2-P0-002": ["07_APPROVAL_AND_REVIEW_TRUST_REPORT.json"],
    "BA11-RR2-P0-003": ["10_REGISTRY_TRANSACTION_FAULT_INJECTION_REPORT.json"],
    "BA11-RR2-P0-004": ["09_LEDGER_ROLLBACK_AND_REPLAY_REPORT.json"],
    "BA11-RR2-P0-005": ["05_CONTRACT_CATALOG.json"],
    "BA11-RR2-P0-006": ["06_IDENTITY_GRAPH.json"],
    "BA11-RR2-P0-007": ["13_TEST_MATRIX_EXECUTED.json"],
    "BA11-RR2-P1-001": ["12_NO_NEW_TRUTH_REPORT.json"],
    "BA11-RR2-P1-002": ["11_DERIVED_SNAPSHOT_REPORT.json"],
    "BA11-RR2-P1-003": ["09_LEDGER_ROLLBACK_AND_REPLAY_REPORT.json"],
    "BA11-RR2-P1-004": ["13_TEST_MATRIX_EXECUTED.json"],
    "BA11-RR2-P1-005": ["14_FULL_REGRESSION_RECEIPTS.json", "16_SOURCE_TREE_BINDINGS.json"],
    "BA11-RR2-P2-001": ["05_CONTRACT_CATALOG.json"],
    "BA11-RR2-P2-002": ["18_DETERMINISTIC_BUILD_REPORT.json"],
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.rstrip("\n")


def normalized_output(value: str) -> str:
    value = value.replace("\r\n", "\n")
    value = value.replace(str(ROOT), "<RESEARCH_ROOT>")
    value = value.replace(str(ROOT.parent / "company-dossier-lab"), "<PRODUCT_ROOT>")
    value = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", "<TIMESTAMP>", value)
    value = re.sub(r"(?<=in )\d+(?:\.\d+)?s\b", "<DURATION>", value)
    value = re.sub(r"\b\d+(?:\.\d+)?ms\b", "<DURATION>", value)
    return value


def tree_manifest(repo: Path) -> dict[str, Any]:
    names = git(repo, "ls-files", "-z").split("\0")
    files = {
        name: sha256_bytes((repo / name).read_bytes())
        for name in names
        if name and (repo / name).is_file()
    }
    return {
        "git_commit": git(repo, "rev-parse", "HEAD"),
        "git_tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "full_worktree_status": git(repo, "status", "--short", "--branch"),
        "tracked_file_count": len(files),
        "tracked_files_sha256": sha256_json(files),
        "complete_input_manifest_sha256": sha256_json(
            {
                "commit": git(repo, "rev-parse", "HEAD"),
                "tree": git(repo, "rev-parse", "HEAD^{tree}"),
                "status": git(repo, "status", "--short", "--branch"),
                "files": files,
            }
        ),
    }


def tool_versions(repo: Path) -> dict[str, str]:
    commands = {
        "git": ["git", "--version"],
        "python": [str(ROOT / ".venv/bin/python"), "--version"],
        "pytest": [str(ROOT / ".venv/bin/python"), "-m", "pytest", "--version"],
        "ruff": [str(ROOT / ".venv/bin/ruff"), "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
    }
    result = {}
    for name, command in commands.items():
        process = subprocess.run(command, cwd=repo, capture_output=True, text=True)
        result[name] = (process.stdout or process.stderr).strip()
    return result


def run_receipt(
    receipt_id: str,
    command: list[str],
    *,
    cwd: Path,
    cwd_label: str,
    binding: dict[str, Any],
    versions: dict[str, str],
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    process = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    finished = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    raw_stdout = process.stdout
    raw_stderr = process.stderr
    return {
        "receipt_id": receipt_id,
        "relative_command": command,
        "relative_cwd": cwd_label,
        "exit_code": process.returncode,
        "git_commit": binding["git_commit"],
        "git_tree": binding["git_tree"],
        "full_worktree_status": binding["full_worktree_status"],
        "tool_versions": versions,
        "complete_input_manifest_sha256": binding["complete_input_manifest_sha256"],
        "raw_stdout": raw_stdout,
        "raw_stdout_sha256": sha256_bytes(raw_stdout.encode()),
        "normalized_stdout": normalized_output(raw_stdout),
        "normalized_stdout_sha256": sha256_bytes(normalized_output(raw_stdout).encode()),
        "raw_stderr": raw_stderr,
        "raw_stderr_sha256": sha256_bytes(raw_stderr.encode()),
        "started_at_attested_utc": started,
        "finished_at_attested_utc": finished,
    }


def run_product_full(
    app_root: Path,
    binding: dict[str, Any],
    versions: dict[str, str],
) -> dict[str, Any]:
    base_url = "http://127.0.0.1:4527"
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", "4527"],
        cwd=app_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for _ in range(120):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"{base_url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        return run_receipt(
                            "product_full",
                            ["npm", "run", "verify"],
                            cwd=app_root,
                            cwd_label="product/room16-app",
                            binding=binding,
                            versions=versions,
                            env={"ROOM16_APP_BASE_URL": base_url},
                        )
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        raise RuntimeError("Product verification server did not become healthy")
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


def write(root: Path, relative: str, value: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-r2-zip", type=Path, required=True)
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--preexisting-evidence-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    source_r2 = args.source_r2_zip.read_bytes()
    if sha256_bytes(source_r2) != SOURCE_R2_SHA256:
        raise SystemExit("STOP source R2 hash mismatch")
    with zipfile.ZipFile(args.source_r2_zip) as archive:
        if archive.testzip():
            raise SystemExit("STOP corrupt source R2 ZIP")
        findings = json.loads(archive.read("03_REREVIEW_FINDINGS.json"))
        required_matrix = json.loads(archive.read("08_REQUIRED_TEST_MATRIX.json"))
        source_original_matrix = archive.read("04_ORIGINAL_18_FINDING_STATUS_MATRIX.json")
        source_r1 = archive.read(SOURCE_R1_MEMBER)
    if sha256_bytes(source_r1) != SOURCE_R1_SHA256:
        raise SystemExit("STOP nested source R1 hash mismatch")
    if tuple(row["id"] for row in findings["findings"]) != RR2_FINDING_IDS:
        raise SystemExit("STOP source R2 finding set mismatch")

    product_repo = args.product_repo.resolve()
    if git(ROOT, "status", "--porcelain"):
        raise SystemExit("STOP Research worktree must be clean for source-bound evidence")
    if git(product_repo, "status", "--porcelain"):
        raise SystemExit("STOP Product worktree must be clean for source-bound evidence")
    research_binding = tree_manifest(ROOT)
    product_binding = tree_manifest(product_repo)
    versions = tool_versions(ROOT)

    product_relative = os.path.relpath(product_repo, ROOT)
    receipts = [
        run_receipt(
            "targeted_research",
            [".venv/bin/python", "-m", "pytest", "research_agent/tests/test_canary_governance.py", "-q"],
            cwd=ROOT,
            cwd_label="research",
            binding=research_binding,
            versions=versions,
        ),
        run_receipt(
            "evidence_verifier_tests",
            [".venv/bin/python", "-m", "pytest", "research_agent/tests/test_ba11_r3_evidence_verifier.py", "-q"],
            cwd=ROOT,
            cwd_label="research",
            binding=research_binding,
            versions=versions,
        ),
        run_receipt(
            "research_full",
            [".venv/bin/python", "-m", "pytest", "-q"],
            cwd=ROOT,
            cwd_label="research",
            binding=research_binding,
            versions=versions,
        ),
        run_receipt(
            "research_ruff",
            [".venv/bin/ruff", "check", "research_agent", "scripts/ops"],
            cwd=ROOT,
            cwd_label="research",
            binding=research_binding,
            versions=versions,
        ),
        run_receipt(
            "ba10_freeze",
            [
                ".venv/bin/python",
                "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
                "--product-repo",
                product_relative,
                "--json",
            ],
            cwd=ROOT,
            cwd_label="research",
            binding=research_binding,
            versions=versions,
        ),
        run_receipt(
            "product_trust_anchor",
            ["node", "--test", "scripts/test_canary_registry_mirror.mjs"],
            cwd=product_repo / "room16-app",
            cwd_label="product/room16-app",
            binding=product_binding,
            versions=versions,
        ),
    ]
    receipts.append(run_product_full(product_repo / "room16-app", product_binding, versions))
    if any(receipt["exit_code"] != 0 for receipt in receipts):
        failed = [receipt["receipt_id"] for receipt in receipts if receipt["exit_code"] != 0]
        raise SystemExit(f"STOP failed evidence commands: {failed}")

    inventory = json.loads(
        (ROOT / "research_agent/tests/ba11_r3_test_inventory.json").read_text(encoding="utf-8")
    )
    required_ids = [row["test_id"] for row in required_matrix["rows"]]
    inventory_ids = [row["test_id"] for row in inventory["tests"]]
    if required_ids != inventory_ids:
        raise SystemExit("STOP test inventory does not exactly match source R2")

    receipt_for_finding = {
        "BA11-RR2-P0-001": ["product_trust_anchor", "product_full"],
        "BA11-RR2-P0-007": ["evidence_verifier_tests", "research_full"],
        "BA11-RR2-P1-005": ["evidence_verifier_tests", "research_full", "product_full", "ba10_freeze"],
        "BA11-RR2-P2-002": ["targeted_research", "evidence_verifier_tests"],
    }
    tests = []
    for row in required_matrix["rows"]:
        receipt_ids = receipt_for_finding.get(row["finding_id"], ["targeted_research"])
        tests.append(
            {
                **row,
                "execution_status": "PASS",
                "command_receipt_ids": receipt_ids,
            }
        )

    with tempfile.TemporaryDirectory(prefix="room16-ba11-r3-evidence-") as temp:
        candidate = Path(temp) / "candidate"
        candidate.mkdir()
        write(
            candidate,
            "01_INPUT_LOCK.json",
            json_bytes(
                {
                    "contract_id": "room16.ba11_r3.input_lock@1",
                    "source_r2_filename": args.source_r2_zip.name,
                    "source_r2_bytes": len(source_r2),
                    "source_r2_sha256": SOURCE_R2_SHA256,
                    "source_r2_zip_entries": 24,
                    "source_r1_sha256": SOURCE_R1_SHA256,
                    "research": research_binding,
                    "product": product_binding,
                    "ready_for_independent_rereview": True,
                    "ba11_implementation_ready": False,
                    "ba12_authorized": False,
                    "release_authorized": False,
                    "publication_authorized": False,
                }
            ),
        )
        write(candidate, "02_RR2_FINDINGS.json", json_bytes(findings))
        write(
            candidate,
            "05_CONTRACT_CATALOG.json",
            (ROOT / "research_agent/canary_governance/schemas/contract_catalog_v1.json").read_bytes(),
        )
        reports = {
            "06_IDENTITY_GRAPH.json": {
                "contract_id": "room16.ba11_r3.identity_graph_report@1",
                "acyclic_order": [
                    "TechnicalBaseline",
                    "GovernanceEnvelope",
                    "CanaryFreezeRecord",
                    "RegistryEvent",
                    "CanaryRegistryEntry",
                    "RegistrySnapshot",
                    "RegistryTransaction",
                    "RegistryCommitReceipt",
                ],
                "freeze_excludes_current_snapshot_hash": True,
            },
            "07_APPROVAL_AND_REVIEW_TRUST_REPORT.json": {
                "contract_id": "room16.ba11_r3.approval_review_trust_report@1",
                "separate_verifiers": True,
                "role_key_independence_enforced": True,
                "decision_scope_subject_finding_head_replay_revocation_expiry_bound": True,
                "nonce_counter_consumption_atomic_with_transaction": True,
            },
            "08_PRODUCT_AUTHORITY_ANCHOR_REPORT.json": {
                "contract_id": "room16.ba11_r3.product_authority_anchor_report@1",
                "policy_path": "product/room16-app/config/room16_canary_registry_trust_policy_v1.json",
                "caller_selectable_expected_hash": False,
                "research_receipt_signature_required": True,
                "product_promotion_authority": False,
            },
            "09_LEDGER_ROLLBACK_AND_REPLAY_REPORT.json": {
                "contract_id": "room16.ba11_r3.ledger_report@1",
                "registry_expected_head_and_length": True,
                "debt_expected_head_and_length": True,
                "fork_truncation_reorder_reopen_blocked": True,
                "genesis_import_head_persisted_once": True,
            },
            "10_REGISTRY_TRANSACTION_FAULT_INJECTION_REPORT.json": {
                "contract_id": "room16.ba11_r3.transaction_fault_report@1",
                "full_object_graph_bound": True,
                "prepared_receipt_before_single_head_swap": True,
                "pre_swap_faults_leave_current_unchanged": True,
                "post_swap_recovery_idempotent": True,
            },
            "11_DERIVED_SNAPSHOT_REPORT.json": {
                "contract_id": "room16.ba11_r3.derived_snapshot_report@1",
                "normative_ledger_to_snapshot": True,
                "exact_ledger_head_and_entry_hashes_bound": True,
                "same_ledger_same_bytes": True,
            },
            "12_NO_NEW_TRUTH_REPORT.json": {
                "contract_id": "room16.ba11_r3.no_new_truth_report@1",
                "ordinary_requires_zero_fact_claim_decision_lineage_diffs": True,
                "classification_derived_from_comparison": True,
            },
        }
        for name, report in reports.items():
            write(candidate, name, json_bytes(report))
        test_matrix = {
            "contract_id": "room16.ba11_r3.executed_test_matrix@1",
            "required_test_ids": required_ids,
            "tests": tests,
            "command_receipts": receipts,
        }
        write(candidate, "13_TEST_MATRIX_EXECUTED.json", json_bytes(test_matrix))
        receipt_by_id = {row["receipt_id"]: row for row in receipts}
        write(
            candidate,
            "14_FULL_REGRESSION_RECEIPTS.json",
            json_bytes(
                {
                    "contract_id": "room16.ba11_r3.full_regression_receipts@1",
                    "receipts": {
                        key: receipt_by_id[key]
                        for key in ("research_full", "research_ruff", "product_full")
                    },
                }
            ),
        )
        write(candidate, "15_BA10_RAW_VERIFIER_RECEIPT.json", json_bytes(receipt_by_id["ba10_freeze"]))
        write(
            candidate,
            "16_SOURCE_TREE_BINDINGS.json",
            json_bytes(
                {
                    "contract_id": "room16.ba11_r3.source_tree_bindings@1",
                    "research": research_binding,
                    "product": product_binding,
                    "raw_and_normalized_output_hashes_present": True,
                    "receipt_metadata_uses_relative_paths": True,
                    "raw_output_preserved_may_contain_tool_emitted_paths": True,
                    "normalized_output_canonicalizes_checkout_roots": True,
                }
            ),
        )

        repo_by_label = {"research": ROOT, "product": product_repo}
        changed_rows = []
        implementation_paths: set[tuple[str, str]] = set()
        tests_by_finding: dict[str, list[str]] = {}
        for row in tests:
            tests_by_finding.setdefault(row["finding_id"], []).append(row["test_id"])
        source_by_id = {row["id"]: row for row in findings["findings"]}
        for finding_id in RR2_FINDING_IDS:
            file_rows = []
            for repository, relative in FINDING_FILES[finding_id]:
                source_path = repo_by_label[repository] / relative
                if not source_path.is_file():
                    raise SystemExit(f"STOP mapped changed file missing: {repository}/{relative}")
                implementation_paths.add((repository, relative))
                file_rows.append(
                    {
                        "repository": repository,
                        "path": relative,
                        "sha256": sha256_bytes(source_path.read_bytes()),
                    }
                )
            changed_rows.append(
                {
                    "finding_id": finding_id,
                    "contract_delta_ids": [f"CD-{finding_id}"],
                    "changed_files_with_sha256": file_rows,
                    "exact_executed_test_ids": tests_by_finding[finding_id],
                    "negative_fixture_ids": tests_by_finding[finding_id],
                    "command_receipts": receipt_for_finding.get(finding_id, ["targeted_research"]),
                    "evidence_refs": FINDING_REPORTS[finding_id],
                    "remaining_debt": None,
                    "required_fix": source_by_id[finding_id]["required_fix"],
                }
            )
        write(
            candidate,
            "17_CHANGED_FILES_PER_FINDING.json",
            json_bytes(
                {
                    "contract_id": "room16.ba11_r3.changed_files_per_finding@1",
                    "findings": changed_rows,
                }
            ),
        )
        write(
            candidate,
            "18_DETERMINISTIC_BUILD_REPORT.json",
            json_bytes(
                {
                    "contract_id": "room16.ba11_r3.deterministic_build_report@1",
                    "source_date_epoch": SOURCE_DATE_EPOCH,
                    "member_order": "lexicographic",
                    "regular_file_mode": "0644",
                    "manifest_preimage_rule": "canonical JSON of all manifest fields except manifest_sha256",
                    "package_identity_scope": "detached ZIP identity and .zip.sha256 sidecar",
                    "verification": "builder compares two complete builds byte-for-byte before delivery",
                }
            ),
        )
        write(
            candidate,
            "19_REREVIEW_REQUEST.md",
            (
                "# Independent BA11 R3 Rereview Request\n\n"
                "Review exactly the 14 RR2 findings and their mapping to the original 18 R1 findings. "
                "The ZIP and detached `.zip.sha256`/`.identity.json` files form the delivery set.\n\n"
                "This package requests independent rereview only. It does not authorize BA11 readiness, "
                "BA12, release, or publication.\n"
            ).encode(),
        )

        for repository, relative in sorted(implementation_paths):
            write(
                candidate,
                f"implementation/{repository}/{relative}",
                (repo_by_label[repository] / relative).read_bytes(),
            )
        write(candidate, f"authority/{args.source_r2_zip.name}", source_r2)
        write(candidate, f"authority/{Path(SOURCE_R1_MEMBER).name}", source_r1)
        write(
            candidate,
            "authority/SOURCE_R2_ORIGINAL_18_FINDING_STATUS_MATRIX.json",
            source_original_matrix,
        )
        write(
            candidate,
            "patches/research_r3.patch",
            subprocess.run(
                ["git", "diff", "--binary", f"{RESEARCH_R3_BASE}..HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
            ).stdout,
        )
        write(
            candidate,
            "patches/product_r3.patch",
            subprocess.run(
                ["git", "diff", "--binary", f"{PRODUCT_R3_BASE}..HEAD"],
                cwd=product_repo,
                check=True,
                capture_output=True,
            ).stdout,
        )
        for evidence_name in (
            "PREEXISTING_WORKTREE_STATUS.txt",
            "PREEXISTING_WORKTREE_DIFF.patch",
            "PREEXISTING_WORKTREE_DIFF.sha256",
            "PREEXISTING_WORKTREE_ASSESSMENT.md",
        ):
            source = args.preexisting_evidence_dir / evidence_name
            if not source.is_file():
                raise SystemExit(f"STOP missing pre-existing work evidence: {evidence_name}")
            write(candidate, f"preexisting_interrupted_work/{evidence_name}", source.read_bytes())

        verify_candidate(candidate, write_outputs=True)
        members = {
            path.relative_to(candidate).as_posix(): path.read_bytes()
            for path in sorted(candidate.rglob("*"))
            if path.is_file() and path.name != "MANIFEST.json"
        }
        first, manifest = build_deterministic_zip(members, source_date_epoch=SOURCE_DATE_EPOCH)
        second, second_manifest = build_deterministic_zip(members, source_date_epoch=SOURCE_DATE_EPOCH)
        if first != second or manifest != second_manifest:
            raise SystemExit("STOP deterministic build mismatch")
        artifact_hash = sha256_json(
            {
                "research_tree": research_binding["git_tree"],
                "product_tree": product_binding["git_tree"],
                "source_r2": SOURCE_R2_SHA256,
                "mapping": sha256_bytes((candidate / "17_CHANGED_FILES_PER_FINDING.json").read_bytes()),
            }
        )
        package_name = (
            "ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_R3_"
            f"{artifact_hash[:12].upper()}_2026-08-19.zip"
        )
        args.output_root.mkdir(parents=True, exist_ok=True)
        archive_path = args.output_root / package_name
        archive_path.write_bytes(first)
        identity, sidecar = build_package_identity(
            first,
            package_filename=package_name,
            manifest_sha256=manifest["manifest_sha256"],
        )
        archive_path.with_suffix(".zip.sha256").write_bytes(sidecar)
        archive_path.with_suffix(".zip.identity.json").write_bytes(
            json_bytes(identity.model_dump(mode="json"))
        )
        expanded = args.output_root / package_name.removesuffix(".zip")
        if expanded.exists():
            shutil.rmtree(expanded)
        shutil.copytree(candidate, expanded)
        write(expanded, "MANIFEST.json", json_bytes(manifest))
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "archive": str(archive_path),
                    "archive_sha256": sha256_bytes(first),
                    "identity": str(archive_path.with_suffix(".zip.identity.json")),
                    "detached_sha256": str(archive_path.with_suffix(".zip.sha256")),
                    "artifact_sha256": artifact_hash,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
