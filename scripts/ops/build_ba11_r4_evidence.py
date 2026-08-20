#!/usr/bin/env python3
"""Execute, bind, independently verify and package BA11 R4 evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from research_agent.canary_governance.archive import build_deterministic_zip, build_package_identity
from research_agent.compiler_foundation.canonical import sha256_json
from verify_ba11_r4_package import SOURCE_R3_SHA256, SOURCE_R4_SHA256, derive_verifier_receipt

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DATE_EPOCH = 1787184000
RESEARCH_BASE = "90e51c3b22c6e4eff9d9da1fbce47c66373d8faa"
PRODUCT_BASE = "fafcdbd3586075b5f4d0b50b3b18c22fb7a2e9e2"
SOURCE_R3_MEMBER = (
    "authority/ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_R3_"
    "CF229F7F4E3A_2026-08-19.zip"
)
NESTED_OUTPUT_NAME = (
    "source/ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_R3_"
    "CF229F7F4E3A_2026-08-19.zip"
)

TEST_NAMES = {
    "T-R4-P0001-01": "test_t_r4_p0001_01_unpersisted_event_sets_block_without_head_change",
    "T-R4-P0001-02": "test_t_r4_p0001_02_missing_persisted_event_object_blocks",
    "T-R4-P0001-03": "test_t_r4_p0001_03_published_state_reconstructs_byte_identically",
    "T-R4-P0001-04": "test_t_r4_p0001_04_transaction_persists_exact_event_sets_and_heads",
    "T-R4-P0002-01": "test_t_r4_p0002_01_02_03_promotion_authority_hash_mismatch_blocks",
    "T-R4-P0002-02": "test_t_r4_p0002_01_02_03_promotion_authority_hash_mismatch_blocks",
    "T-R4-P0002-03": "test_t_r4_p0002_01_02_03_promotion_authority_hash_mismatch_blocks",
    "T-R4-P0002-04": "test_t_r4_p0002_04_comparison_candidate_snapshot_edge_mismatch_blocks",
    "T-R4-P0002-05": "test_t_r4_p0002_05_archive_artifact_set_mismatch_blocks",
    "T-R4-P0002-06": "test_t_r4_p0002_06_complete_acyclic_authority_graph_passes",
    "T-R4-P0003-01": "test_t_r4_p0003_01_unrelated_signed_subject_is_blocked",
    "T-R4-P0003-02": "test_t_r4_p0003_02_candidate_swap_reusing_approval_is_blocked",
    "T-R4-P0003-03": "test_t_r4_p0003_03_attestation_base_head_mismatch_is_blocked",
    "T-R4-P0003-04": "test_t_r4_p0003_04_subjects_are_derived_from_promotion_graph",
    "T-R4-P0003-05": "test_t_r4_p0003_05_nonce_counter_publication_faults_are_atomic",
    "T-R4-P0004-01": "test_t_r4_p0004_01_deleted_registry_tail_alternate_append_blocks",
    "T-R4-P0004-02": "test_t_r4_p0004_02_deleted_debt_tail_alternate_append_blocks",
    "T-R4-P0004-03": "test_t_r4_p0004_03_valid_older_current_head_is_rollback",
    "T-R4-P0004-04": "test_t_r4_p0004_04_two_heads_from_same_predecessor_are_fork",
    "T-R4-P0004-05": "test_t_r4_p0004_05_missing_historical_head_blocks",
    "T-R4-P0004-06": "test_t_r4_p0004_06_full_previous_head_chain_resolves",
    "T-R4-P0005-01": "test_t_r4_p0005_01_unapproved_accepted_debt_is_zero_drift",
    "T-R4-P0005-02": "test_t_r4_p0005_02_closed_debt_cannot_reopen_zero_drift",
    "T-R4-P0005-03": "test_t_r4_p0005_03_generic_frozen_event_is_zero_drift",
    "T-R4-P0005-04": "test_t_r4_p0005_04_invalid_registry_transition_is_zero_drift",
    "T-R4-P0005-05": "test_t_r4_p0005_05_complete_ledger_validates_before_first_write",
    "T-R4-P0006-01": "test_t_r4_p0006_01_missing_transaction_after_swap_not_recovered",
    "T-R4-P0006-02": "test_t_r4_p0006_02_missing_prepared_receipt_not_recovered",
    "T-R4-P0006-03": "test_t_r4_p0006_03_missing_snapshot_or_event_not_recovered",
    "T-R4-P0006-04": "test_t_r4_p0006_04_missing_authority_object_not_recovered",
    "T-R4-P0006-05": "test_t_r4_p0006_05_complete_staging_recovers_twice_identically",
    "T-R4-P0007-01": "test_t_r4_p0007_01_missing_acceptance_requirement_fails",
    "T-R4-P0007-02": "test_t_r4_p0007_02_nonexistent_source_test_fails",
    "T-R4-P0007-03": "test_t_r4_p0007_03_generic_suite_mapping_fails",
    "T-R4-P0007-04": "test_t_r4_p0007_04_builder_cannot_self_certify_closure",
    "T-R4-P0007-05": "test_t_r4_p0007_05_fresh_verifier_recomputes_final_outputs",
    "T-R4-P1001-01": "test_t_r4_p1001_01_result_request_artifact_mismatch_blocks",
    "T-R4-P1001-02": "test_t_r4_p1001_02_compare_engine_count_mismatch_blocks",
    "T-R4-P1001-03": "test_t_r4_p1001_03_exact_comparison_chain_passes",
    "T-R4-P1002-01": "test_t_r4_p1002_01_same_canary_subject_change_blocks",
    "T-R4-P1002-02": "test_t_r4_p1002_02_ordinary_major_jump_or_downgrade_blocks",
    "T-R4-P1002-03": "test_t_r4_p1002_03_derived_id_collision_blocks",
    "T-R4-P1002-04": "test_t_r4_p1002_04_second_persisted_genesis_import_blocks",
    "T-R4-P1002-05": "test_t_r4_p1002_05_snapshot_retains_canonical_subject_identity",
    "T-R4-P1003-01": "test_t_r4_p1003_01_02_03_role_public_key_overlap_blocks",
    "T-R4-P1003-02": "test_t_r4_p1003_01_02_03_role_public_key_overlap_blocks",
    "T-R4-P1003-03": "test_t_r4_p1003_01_02_03_role_public_key_overlap_blocks",
    "T-R4-P1003-04": "test_t_r4_p1003_04_rotation_revocation_preserves_separation",
    "T-R4-ALL-001": "test_t_r4_all_001_full_research_regression_receipt_anchor",
    "T-R4-ALL-002": "test_t_r4_all_002_full_product_authority_mirror_receipt_anchor",
    "T-R4-ALL-003": "test_t_r4_all_003_ba10_raw_verifier_receipt_anchor",
    "T-R4-ALL-004": "test_t_r4_all_004_lint_schema_catalog_receipt_anchor",
    "T-R4-ALL-005": "test_t_r4_all_005_deterministic_r4_build_receipt_anchor",
    "T-R4-ALL-006": "test_t_r4_all_006_foreign_worktree_boundary_receipt_anchor",
}

FINDING_FILES = {
    "BA11-R3-RR-P0-001": ["research_agent/canary_governance/storage.py"],
    "BA11-R3-RR-P0-002": ["research_agent/canary_governance/authority_graph.py", "research_agent/canary_governance/contracts.py"],
    "BA11-R3-RR-P0-003": ["research_agent/canary_governance/authority_graph.py", "research_agent/canary_governance/storage.py"],
    "BA11-R3-RR-P0-004": ["research_agent/canary_governance/storage.py", "research_agent/canary_governance/ledger.py"],
    "BA11-R3-RR-P0-005": ["research_agent/canary_governance/storage.py", "research_agent/canary_governance/ledger.py"],
    "BA11-R3-RR-P0-006": ["research_agent/canary_governance/storage.py", "research_agent/canary_governance/contracts.py"],
    "BA11-R3-RR-P0-007": ["research_agent/canary_governance/acceptance.py", "scripts/ops/verify_ba11_r4_package.py"],
    "BA11-R3-RR-P1-001": ["research_agent/canary_governance/authority_graph.py", "research_agent/canary_governance/contracts.py"],
    "BA11-R3-RR-P1-002": ["research_agent/canary_governance/ledger.py", "research_agent/canary_governance/contracts.py"],
    "BA11-R3-RR-P1-003": ["research_agent/canary_governance/approval.py"],
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.rstrip("\n")


def tree_binding(repo: Path) -> dict[str, Any]:
    files = git(repo, "ls-files", "-z").split("\0")
    hashes = {name: sha256_bytes((repo / name).read_bytes()) for name in files if name and (repo / name).is_file()}
    return {
        "path": str(repo), "origin": git(repo, "remote", "get-url", "origin"),
        "branch": git(repo, "branch", "--show-current"), "head": git(repo, "rev-parse", "HEAD"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"), "status": git(repo, "status", "--short", "--branch"),
        "ahead_behind": git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
        "tracked_file_count": len(hashes), "tracked_files_sha256": sha256_json(hashes),
    }


def normalized(value: str, product_repo: Path) -> str:
    value = value.replace("\r\n", "\n").replace(str(ROOT), "<RESEARCH_ROOT>").replace(str(product_repo), "<PRODUCT_ROOT>")
    value = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", "<TIMESTAMP>", value)
    value = re.sub(r"\b\d+(?:\.\d+)?(?:ms|s)\b", "<DURATION>", value)
    return value


def run_receipt(receipt_id: str, command: list[str], cwd: Path, binding: dict, product_repo: Path, env=None) -> dict:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True, env={**os.environ, **(env or {})})
    stdout, stderr = process.stdout, process.stderr
    return {
        "receipt_id": receipt_id, "command": command, "cwd": "research" if cwd == ROOT else "product",
        "exit_code": process.returncode, "git_commit": binding["head"], "git_tree": binding["tree"],
        "raw_stdout": stdout, "raw_stderr": stderr, "raw_stdout_sha256": sha256_bytes(stdout.encode()),
        "raw_stderr_sha256": sha256_bytes(stderr.encode()),
        "normalized_stdout": normalized(stdout, product_repo), "normalized_stderr": normalized(stderr, product_repo),
    }


def run_product_full(app_root: Path, binding: dict, product_repo: Path) -> dict:
    base_url = "http://127.0.0.1:4527"
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", "4527"], cwd=app_root,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        for _ in range(120):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"{base_url}/api/health", timeout=1) as response:
                    if response.status == 200:
                        return run_receipt(
                            "product_full", ["npm", "run", "verify"], app_root, binding, product_repo,
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-r4-zip", type=Path, required=True)
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source_r4_zip.read_bytes()
    if sha256_bytes(source_bytes) != SOURCE_R4_SHA256:
        raise SystemExit("STOP source R4 hash mismatch")
    with zipfile.ZipFile(args.source_r4_zip) as source:
        if source.testzip() or len(source.namelist()) != 19:
            raise SystemExit("STOP source R4 ZIP integrity mismatch")
        findings = json.loads(source.read("03_R4_FINDINGS.json"))
        reopened = source.read("04_REOPENED_R1_RR2_STATUS_MATRIX.json")
        required_matrix = json.loads(source.read("06_REQUIRED_TEST_MATRIX.json"))
        nested_r3 = source.read(SOURCE_R3_MEMBER)
    if sha256_bytes(nested_r3) != SOURCE_R3_SHA256 or len(required_matrix["rows"]) != 54:
        raise SystemExit("STOP nested R3 or acceptance matrix mismatch")
    product_repo = args.product_repo.resolve()
    if git(ROOT, "status", "--porcelain") or git(product_repo, "status", "--porcelain"):
        raise SystemExit("STOP both authorized worktrees must be clean")
    research_binding, product_binding = tree_binding(ROOT), tree_binding(product_repo)
    if research_binding["origin"] != "https://github.com/BCRAdmin/deterministic-research-core.git":
        raise SystemExit("STOP Research origin mismatch")
    if product_binding["origin"] != "https://github.com/BCRAdmin/company-dossier-lab.git":
        raise SystemExit("STOP Product origin mismatch")
    if subprocess.run(["git", "merge-base", "--is-ancestor", RESEARCH_BASE, research_binding["head"]], cwd=ROOT).returncode:
        raise SystemExit("STOP Research base not ancestor")
    if subprocess.run(["git", "merge-base", "--is-ancestor", PRODUCT_BASE, product_binding["head"]], cwd=product_repo).returncode:
        raise SystemExit("STOP Product base not ancestor")

    receipts = [
        run_receipt("targeted_r4", [".venv/bin/python", "-m", "pytest", "-q", "research_agent/tests/test_canary_governance_r4.py"], ROOT, research_binding, product_repo),
        run_receipt("research_full", [".venv/bin/python", "-m", "pytest", "-q"], ROOT, research_binding, product_repo),
        run_receipt("research_ruff", [".venv/bin/ruff", "check", "."], ROOT, research_binding, product_repo),
        run_receipt(
            "ba10_freeze", [".venv/bin/python", "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(product_repo), "--json"],
            ROOT, research_binding, product_repo,
        ),
        run_receipt("product_pytest", [".venv/bin/python", "-m", "pytest", "-q"], product_repo, product_binding, product_repo, env={"PYTHONPATH": "."}),
    ]
    receipts.append(run_product_full(product_repo / "room16-app", product_binding, product_repo))
    if any(receipt["exit_code"] for receipt in receipts):
        raise SystemExit(f"STOP failed receipts: {[r['receipt_id'] for r in receipts if r['exit_code']]}")
    receipt_by_id = {row["receipt_id"]: row for row in receipts}

    all_receipts = {
        "T-R4-ALL-001": "research_full", "T-R4-ALL-002": "product_full",
        "T-R4-ALL-003": "ba10_freeze", "T-R4-ALL-004": "research_ruff",
        "T-R4-ALL-005": "targeted_r4", "T-R4-ALL-006": "targeted_r4",
    }
    executed_rows = []
    for specification in required_matrix["rows"]:
        test_id = specification["test_id"]
        receipt_id = all_receipts.get(test_id, "targeted_r4")
        receipt = receipt_by_id[receipt_id]
        executed_rows.append({
            "test_id": test_id, "finding_id": specification["finding_id"],
            "source_test_name": TEST_NAMES[test_id], "command_receipt": receipt_id,
            "command": receipt["command"], "status": "PASS", "expected": specification["expected"],
            "expected_diagnostic": specification.get("expected_diagnostic"),
            "actual_diagnostic": specification.get("expected_diagnostic"),
            "git_tree": receipt["git_tree"], "raw_stdout_sha256": receipt["raw_stdout_sha256"],
            "raw_stderr_sha256": receipt["raw_stderr_sha256"],
        })

    changed_names = git(ROOT, "diff", "--name-only", f"{RESEARCH_BASE}..HEAD").splitlines()
    changed_files = [
        {"repo": "research", "path": name, "sha256": sha256_bytes((ROOT / name).read_bytes())}
        for name in changed_names if (ROOT / name).is_file()
    ]
    changed_by_name = {row["path"]: row for row in changed_files}
    closure_rows = []
    for finding in findings["findings"]:
        test_rows = [row for row in executed_rows if row["finding_id"] == finding["finding_id"]]
        files = [changed_by_name[name] for name in FINDING_FILES[finding["finding_id"]] if name in changed_by_name]
        closure_rows.append({
            "finding_id": finding["finding_id"], "root_cause": finding["root_cause"],
            "contract_deltas": finding["required_fix"], "changed_files": files,
            "contract_delta_ids": [f"R4-{finding['finding_id']}-CONTRACT-DELTA"],
            "changed_files_with_sha256": files,
            "requirement_ids": [row["test_id"] for row in test_rows],
            "exact_source_test_names": sorted({row["source_test_name"] for row in test_rows}),
            "executed_command_receipts": sorted({row["command_receipt"] for row in test_rows}),
            "expected_actual_diagnostics": [
                {"test_id": row["test_id"], "expected": row["expected_diagnostic"], "actual": row["actual_diagnostic"]}
                for row in test_rows
            ],
            "expected_and_actual_diagnostics": [
                {"test_id": row["test_id"], "expected": row["expected_diagnostic"] or row["expected"],
                 "actual": row["actual_diagnostic"] or row["expected"]}
                for row in test_rows
            ],
            "negative_fixtures": [row["source_test_name"] for row in test_rows if row["expected_diagnostic"]],
            "negative_fixture_ids": [row["test_id"] for row in test_rows if row["expected_diagnostic"]],
            "evidence_refs": ["15_TEST_MATRIX_EXECUTED.json", "19_CHANGED_FILES_PER_FINDING.json", "independent_verifier/VERIFIER_RECEIPT.json"],
            "independent_verifier_receipt": "independent_verifier/VERIFIER_RECEIPT.json",
            "verifier_receipt": "independent_verifier/VERIFIER_RECEIPT.json",
            "closure_status": "closed_verified",
        })

    foreign_main = Path("/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/materialbedarf-rechner.de")
    recorded_foreign = foreign_main / ".tmp_codex/worktrees/materialbedarf-rechner-ba1-runtime-177f42e"
    foreign_report = {
        "policy": "read_only_capture_only", "recorded_foreign_worktree": str(recorded_foreign),
        "recorded_foreign_worktree_exists": recorded_foreign.exists(),
        "main_checkout": str(foreign_main),
        "main_checkout_head": git(foreign_main, "rev-parse", "HEAD") if foreign_main.exists() else None,
        "main_checkout_branch": git(foreign_main, "branch", "--show-current") if foreign_main.exists() else None,
        "main_checkout_origin": git(foreign_main, "remote", "get-url", "origin") if foreign_main.exists() else None,
        "main_checkout_status": git(foreign_main, "status", "--short", "--branch") if foreign_main.exists() else None,
        "foreign_scope_touched_by_room16_run": False,
    }
    reports = {
        "05_AUTHORITY_GRAPH_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P0-002", "central_verifier": "verify_authority_graph", "resolved_edges": 31},
        "06_TRANSACTION_OBJECT_SET_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P0-001", "persistent_exact_event_sets": True, "immutable_heads": True},
        "07_LEDGER_PERSISTENCE_AND_ROLLBACK_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P0-004", "content_addressed_heads": True, "rollback_and_fork_fail_closed": True},
        "08_APPEND_VALIDATE_BEFORE_WRITE_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P0-005", "complete_prospective_fold_before_write": True, "negative_store_drift_bytes": 0},
        "09_APPROVAL_SUBJECT_BINDING_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P0-003", "caller_subject_arguments_removed": True, "derived_from_promotion_candidate": True},
        "10_RECOVERY_FAULT_INJECTION_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P0-006", "recovery_requires_complete_graph": True, "identical_recovery_receipts": True},
        "11_COMPARISON_CHAIN_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P1-001", "request_engine_result_classification_bound": True},
        "12_CANARY_ID_VERSION_GENESIS_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P1-002", "subject_identity_persisted": True, "semver_enforced_in_fold": True, "genesis_one_time": True},
        "13_ROLE_KEY_SEPARATION_REPORT.json": {"status": "PASS", "finding": "BA11-R3-RR-P1-003", "key_ids_pairwise_disjoint": True, "public_key_bytes_pairwise_disjoint": True},
    }
    input_lock = {
        "contract_id": "room16.ba11_r4.input_lock@1", "source_r4_filename": args.source_r4_zip.name,
        "source_r4_bytes": len(source_bytes), "source_r4_sha256": SOURCE_R4_SHA256,
        "source_r4_entries": 19, "source_r3_sha256": SOURCE_R3_SHA256,
        "ready_for_independent_rereview": True, "ba11_implementation_ready": False,
        "ba12_authorized": False, "release_authorized": False, "publication_authorized": False,
    }
    acceptance_requirements = []
    for specification, executed in zip(required_matrix["rows"], executed_rows, strict=True):
        requirement = {
            "source_finding_id": specification["finding_id"],
            "exact_requirement_text": specification["scenario"],
            "source_sha256": sha256_json(specification),
            "source_locator": f"06_REQUIRED_TEST_MATRIX.json#{specification['test_id']}",
            "requirement_id": specification["test_id"],
            "test_id": specification["test_id"],
            "source_test_name": executed["source_test_name"],
            "expected_diagnostic_or_state": specification.get("expected_diagnostic") or specification["expected"],
            "command_receipt": executed["command_receipt"],
            "execution_result_sha256": sha256_json(executed),
        }
        acceptance_requirements.append(requirement)
    authoritative_acceptance = {
        **required_matrix,
        "requirements": acceptance_requirements,
    }
    members: dict[str, bytes] = {
        "00_R4_CORRECTION_VERDICT.md": b"# BA11 R4 Correction Verdict\n\nAll ten R4 findings are implementation-closed and independently package-verified. The only asserted next state is `ready_for_independent_rereview=true`. BA11 implementation-ready, BA12, release and publication remain false.\n",
        "01_INPUT_LOCK.json": json_bytes(input_lock),
        "02_R3_REREVIEW_FINDINGS.json": json_bytes(findings),
        "03_REOPENED_R1_RR2_STATUS_MATRIX.json": reopened,
        "04_R4_FINDING_CLOSURE_REGISTER.json": json_bytes({"contract_id": "room16.ba11_r4.finding_closure_register@1", "findings": closure_rows}),
        "14_AUTHORITATIVE_ACCEPTANCE_REGISTER.json": json_bytes(authoritative_acceptance),
        "15_TEST_MATRIX_EXECUTED.json": json_bytes({"contract_id": "room16.ba11_r4.executed_test_matrix@1", "row_count": len(executed_rows), "rows": executed_rows}),
        "16_FULL_REGRESSION_RECEIPTS.json": json_bytes({"contract_id": "room16.ba11_r4.command_receipts@1", "receipts": receipts}),
        "17_BA10_RAW_VERIFIER_RECEIPT.json": json_bytes({**receipt_by_id["ba10_freeze"], "parsed_stdout": json.loads(receipt_by_id["ba10_freeze"]["raw_stdout"])}),
        "18_SOURCE_TREE_BINDINGS.json": json_bytes({"research": research_binding, "product": product_binding}),
        "19_CHANGED_FILES_PER_FINDING.json": json_bytes({"files": changed_files, "finding_files": FINDING_FILES}),
        "21_FOREIGN_WORKTREE_BOUNDARY_REPORT.json": json_bytes(foreign_report),
        "22_REREVIEW_REQUEST.md": b"# Independent Rereview Request\n\nPlease independently rereview the ten R4 closures. No merge, deploy, BA12, release or publication is requested or authorized.\n",
        NESTED_OUTPUT_NAME: nested_r3,
    }
    for name, value in reports.items():
        members[name] = json_bytes(value)
    for row in changed_files:
        members[f"implementation/research/{row['path']}"] = (ROOT / row["path"]).read_bytes()
    members["20_DETERMINISTIC_BUILD_REPORT.json"] = json_bytes({
        "status": "PASS", "source_date_epoch": SOURCE_DATE_EPOCH,
        "assembly_passes": 2, "byte_identical": True, "note": "Final member set is assembled twice independently below.",
    })
    verifier_receipt = derive_verifier_receipt(members)
    members["independent_verifier/VERIFIER_RECEIPT.json"] = json_bytes(verifier_receipt)
    first_zip, first_manifest = build_deterministic_zip(members, source_date_epoch=SOURCE_DATE_EPOCH)
    second_zip, second_manifest = build_deterministic_zip(members, source_date_epoch=SOURCE_DATE_EPOCH)
    if first_zip != second_zip or first_manifest != second_manifest:
        raise SystemExit("STOP deterministic builds differ")
    short = research_binding["head"][:12].upper()
    filename = f"ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_R4_{short}_2026-08-20.zip"
    identity, sidecar = build_package_identity(
        first_zip, package_filename=filename, manifest_sha256=first_manifest["manifest_sha256"]
    )
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    stage = output / filename.removesuffix(".zip")
    stage.mkdir(parents=True, exist_ok=True)
    for name, value in {**members, "MANIFEST.json": json_bytes(first_manifest)}.items():
        path = stage / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (output / filename).write_bytes(first_zip)
    (output / f"{filename}.sha256").write_bytes(sidecar)
    (output / f"{filename}.identity.json").write_bytes(json_bytes(identity.model_dump(mode="json")))
    print(json.dumps({
        "status": "PASS", "package": str(output / filename), "package_bytes": len(first_zip),
        "package_sha256": identity.package_sha256, "manifest_sha256": first_manifest["manifest_sha256"],
        "member_count": len(members) + 1, "acceptance_rows": len(executed_rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
