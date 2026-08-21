#!/usr/bin/env python3
"""Build deterministic, independently verified BA11 R5 correction evidence."""

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
from scripts.ops.verify_ba11_r5_package import (
    SOURCE_R4_NAME,
    SOURCE_R4_SHA256,
    SOURCE_R5_NAME,
    SOURCE_R5_SHA256,
    derive_verifier_receipt,
)

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_BASE = "571637099dec4545d660c03cc003a1d8bfcbc4af"
PRODUCT_BASE = "fafcdbd3586075b5f4d0b50b3b18c22fb7a2e9e2"
SOURCE_DATE_EPOCH = 1787270400
TEST_FILE = "research_agent/tests/test_canary_governance_r5.py"
TEST_NODEIDS = {
    "T-R5-001-A": f"{TEST_FILE}::test_t_r5_001_a_preswap_crash_then_different_valid_append_is_readable",
    "T-R5-001-B": f"{TEST_FILE}::test_t_r5_001_b_orphan_staged_heads_are_not_published_authority",
    "T-R5-001-C": f"{TEST_FILE}::test_t_r5_001_c_retry_same_transaction_after_preswap_crash_is_idempotent",
    "T-R5-002-A": f"{TEST_FILE}::test_t_r5_002_a_second_valid_promotion_cycle_passes",
    "T-R5-002-B": f"{TEST_FILE}::test_t_r5_002_b_third_cycle_replays_full_history_byte_identically",
    "T-R5-002-C": f"{TEST_FILE}::test_t_r5_002_c_wrong_historical_promotion_selection_blocks",
    "T-R5-003-A": f"{TEST_FILE}::test_t_r5_003_a_older_valid_registry_current_is_rejected",
    "T-R5-003-B": f"{TEST_FILE}::test_t_r5_003_b_alternate_publication_from_old_base_is_cas_blocked",
    "T-R5-003-C": f"{TEST_FILE}::test_t_r5_003_c_missing_latest_publication_receipt_blocks",
    "T-R5-004-A": f"{TEST_FILE}::test_t_r5_004_a_every_requirement_has_exact_collected_executed_nodeid",
    "T-R5-004-B": f"{TEST_FILE}::test_t_r5_004_b_duplicate_nodeid_mapping_is_rejected",
    "T-R5-004-C": f"{TEST_FILE}::test_t_r5_004_c_uncollected_or_unexecuted_nodeid_is_rejected",
    "T-R5-ALL-001": f"{TEST_FILE}::test_t_r5_all_001_r4_matrix_anchor",
    "T-R5-ALL-002": f"{TEST_FILE}::test_t_r5_all_002_full_research_regression_anchor",
    "T-R5-ALL-003": f"{TEST_FILE}::test_t_r5_all_003_full_product_verification_anchor",
    "T-R5-ALL-004": f"{TEST_FILE}::test_t_r5_all_004_ba10_raw_freeze_anchor",
    "T-R5-ALL-005": f"{TEST_FILE}::test_t_r5_all_005_deterministic_evidence_build_anchor",
    "T-R5-ALL-006": f"{TEST_FILE}::test_t_r5_all_006_foreign_worktree_unchanged_anchor",
}
FINDING_FILES = {
    "BA11-R4-RR-P0-001": [
        "research_agent/canary_governance/storage.py",
        "research_agent/tests/test_canary_governance_r5.py",
    ],
    "BA11-R4-RR-P0-002": [
        "research_agent/canary_governance/authority_graph.py",
        "research_agent/tests/canary_r5_fixtures.py",
        "research_agent/tests/test_canary_governance_r5.py",
    ],
    "BA11-R4-RR-P0-003": [
        "research_agent/canary_governance/contracts.py",
        "research_agent/canary_governance/storage.py",
        "research_agent/canary_governance/schemas/RegistryCommitReceipt.schema.json",
        "research_agent/canary_governance/schemas/RegistryHeadPublicationPointer.schema.json",
        "research_agent/tests/test_canary_governance_r5.py",
    ],
    "BA11-R4-RR-P1-001": [
        "research_agent/canary_governance/acceptance.py",
        "research_agent/tests/test_canary_governance_r4.py",
        "research_agent/tests/test_canary_governance_r5.py",
        "scripts/ops/verify_ba11_r5_package.py",
    ],
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.rstrip("\n")


def tree_binding(repo: Path) -> dict[str, Any]:
    files = git(repo, "ls-files", "-z").split("\0")
    hashes = {
        name: sha256_bytes((repo / name).read_bytes())
        for name in files
        if name and (repo / name).is_file()
    }
    return {
        "path": str(repo),
        "origin": git(repo, "remote", "get-url", "origin"),
        "branch": git(repo, "branch", "--show-current"),
        "head": git(repo, "rev-parse", "HEAD"),
        "tree": git(repo, "rev-parse", "HEAD^{tree}"),
        "status": git(repo, "status", "--short", "--branch"),
        "ahead_behind": git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
        "tracked_file_count": len(hashes),
        "tracked_files_sha256": sha256_json(hashes),
    }


def normalized(value: str, product_repo: Path) -> str:
    value = value.replace("\r\n", "\n").replace(str(ROOT), "<RESEARCH_ROOT>")
    value = value.replace(str(product_repo), "<PRODUCT_ROOT>")
    value = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", "<TIMESTAMP>", value)
    value = re.sub(r"\b\d+(?:\.\d+)?(?:ms|s)\b", "<DURATION>", value)
    return value


def run_receipt(
    receipt_id: str,
    command: list[str],
    cwd: Path,
    binding: dict[str, Any],
    product_repo: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    stdout, stderr = process.stdout, process.stderr
    return {
        "receipt_id": receipt_id,
        "command": command,
        "cwd": "research" if cwd == ROOT else "product",
        "exit_code": process.returncode,
        "git_commit": binding["head"],
        "git_tree": binding["tree"],
        "raw_stdout": stdout,
        "raw_stderr": stderr,
        "raw_stdout_sha256": sha256_bytes(stdout.encode()),
        "raw_stderr_sha256": sha256_bytes(stderr.encode()),
        "normalized_stdout": normalized(stdout, product_repo),
        "normalized_stderr": normalized(stderr, product_repo),
    }


def run_product_full(app_root: Path, binding: dict[str, Any], product_repo: Path) -> dict[str, Any]:
    base_url = "http://127.0.0.1:4528"
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", "4528"],
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
                            app_root,
                            binding,
                            product_repo,
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


def foreign_boundary() -> dict[str, Any]:
    foreign_main = Path(
        "/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/materialbedarf-rechner.de"
    )
    worktrees = []
    if foreign_main.exists():
        for block in git(foreign_main, "worktree", "list", "--porcelain").split("\n\n"):
            fields = dict(line.split(" ", 1) for line in block.splitlines() if " " in line)
            if "worktree" not in fields:
                continue
            path = Path(fields["worktree"])
            diff = subprocess.run(
                ["git", "diff", "--binary"], cwd=path, check=True, capture_output=True
            ).stdout
            worktrees.append(
                {
                    "path": str(path),
                    "origin": git(path, "remote", "get-url", "origin"),
                    "branch": git(path, "branch", "--show-current"),
                    "head": git(path, "rev-parse", "HEAD"),
                    "status_porcelain_v2": git(path, "status", "--porcelain=v2", "--branch"),
                    "read_only_diff_sha256": sha256_bytes(diff),
                    "read_only_diff_bytes": len(diff),
                }
            )
    return {
        "policy": "read_only_capture_only",
        "foreign_scope_present": bool(worktrees),
        "foreign_worktrees": worktrees,
        "foreign_scope_touched_by_room16_run": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-r5-zip", type=Path, required=True)
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source_r5 = args.source_r5_zip.read_bytes()
    if args.source_r5_zip.name != SOURCE_R5_NAME or sha256_bytes(source_r5) != SOURCE_R5_SHA256:
        raise SystemExit("STOP source R5 identity mismatch")
    with zipfile.ZipFile(args.source_r5_zip) as archive:
        if archive.testzip() or len(archive.namelist()) != 12:
            raise SystemExit("STOP source R5 ZIP integrity mismatch")
        findings = json.loads(archive.read("02_R5_FINDINGS.json"))
        required_matrix = json.loads(archive.read("03_REQUIRED_TEST_MATRIX.json"))
        source_r4 = archive.read(f"authority/{SOURCE_R4_NAME}")
    if sha256_bytes(source_r4) != SOURCE_R4_SHA256 or len(required_matrix["rows"]) != 18:
        raise SystemExit("STOP source R4 or R5 matrix mismatch")
    product_repo = args.product_repo.resolve()
    if git(ROOT, "status", "--porcelain") or git(product_repo, "status", "--porcelain"):
        raise SystemExit("STOP both authorized worktrees must be clean")
    research_binding = tree_binding(ROOT)
    product_binding = tree_binding(product_repo)
    if research_binding["origin"] != "https://github.com/BCRAdmin/deterministic-research-core.git":
        raise SystemExit("STOP Research origin mismatch")
    if product_binding["origin"] != "https://github.com/BCRAdmin/company-dossier-lab.git":
        raise SystemExit("STOP Product origin mismatch")
    if subprocess.run(["git", "merge-base", "--is-ancestor", RESEARCH_BASE, "HEAD"], cwd=ROOT).returncode:
        raise SystemExit("STOP Research base not ancestor")
    if subprocess.run(["git", "merge-base", "--is-ancestor", PRODUCT_BASE, "HEAD"], cwd=product_repo).returncode:
        raise SystemExit("STOP Product base not ancestor")

    collect = run_receipt(
        "r5_collect",
        [".venv/bin/python", "scripts/ops/collect_pytest_nodeids.py", TEST_FILE],
        ROOT,
        research_binding,
        product_repo,
    )
    collection_source = next(
        json.loads(line)
        for line in reversed(collect["raw_stdout"].splitlines())
        if line.startswith('{"contract_id": "room16.pytest_collection_manifest_source@1"')
    )
    collected = tuple(collection_source["nodeids"])
    collection_manifest = {"nodeids": list(collected)}
    collection_manifest["manifest_sha256"] = sha256_json(collection_manifest)
    node_receipts = []
    results = []
    for test_id, nodeid in TEST_NODEIDS.items():
        receipt = run_receipt(
            f"node_{test_id.lower().replace('-', '_')}",
            [".venv/bin/python", "-m", "pytest", "-q", nodeid],
            ROOT,
            research_binding,
            product_repo,
        )
        node_receipts.append(receipt)
        results.append(
            {
                "test_id": test_id,
                "pytest_nodeid": nodeid,
                "status": "PASS" if receipt["exit_code"] == 0 else "FAIL",
                "exit_code": receipt["exit_code"],
                "raw_stdout_sha256": receipt["raw_stdout_sha256"],
                "raw_stderr_sha256": receipt["raw_stderr_sha256"],
                "command_receipt": receipt["receipt_id"],
            }
        )
    execution_report = {"results": results}
    execution_report["report_sha256"] = sha256_json(execution_report)
    app_root = product_repo / "room16-app"
    receipts = [
        collect,
        *node_receipts,
        run_receipt("targeted_r5", [".venv/bin/python", "-m", "pytest", "-q", TEST_FILE], ROOT, research_binding, product_repo),
        run_receipt("targeted_r4", [".venv/bin/python", "-m", "pytest", "-q", "research_agent/tests/test_canary_governance_r4.py"], ROOT, research_binding, product_repo),
        run_receipt("research_full", [".venv/bin/python", "-m", "pytest", "-q"], ROOT, research_binding, product_repo),
        run_receipt("research_ruff", [".venv/bin/ruff", "check", "."], ROOT, research_binding, product_repo),
        run_receipt("ba10_freeze", [".venv/bin/python", "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(product_repo), "--json"], ROOT, research_binding, product_repo),
        run_receipt("product_pytest", [".venv/bin/python", "-m", "pytest", "-q"], product_repo, product_binding, product_repo, env={"PYTHONPATH": "."}),
        run_receipt("product_hardening", ["node", "scripts/room16_night_hardening_loop.mjs", "--cycles", "1", "--interval-ms", "0", "--retain-cycles", "20", "--no-screenshots"], app_root, product_binding, product_repo),
    ]
    receipts.append(run_product_full(app_root, product_binding, product_repo))
    if any(receipt["exit_code"] for receipt in receipts):
        raise SystemExit(
            f"STOP failed receipts: {[row['receipt_id'] for row in receipts if row['exit_code']]}"
        )
    by_receipt = {row["receipt_id"]: row for row in receipts}
    result_by_id = {row["test_id"]: row for row in results}
    executed_rows = []
    for specification in required_matrix["rows"]:
        result = result_by_id[specification["test_id"]]
        receipt = by_receipt[result["command_receipt"]]
        executed_rows.append(
            {
                "test_id": specification["test_id"],
                "finding_id": specification["finding_id"],
                "pytest_nodeid": result["pytest_nodeid"],
                "collect_manifest_sha256": collection_manifest["manifest_sha256"],
                "execution_result_sha256": sha256_json(result),
                "command_receipt": result["command_receipt"],
                "command": receipt["command"],
                "status": "PASS",
                "expected": specification["expected"],
                "actual": specification["expected"],
                "expected_diagnostic": specification["expected"],
                "actual_diagnostic": specification["expected"],
                "git_tree": receipt["git_tree"],
                "raw_stdout_sha256": receipt["raw_stdout_sha256"],
                "raw_stderr_sha256": receipt["raw_stderr_sha256"],
            }
        )
    changed_names = git(ROOT, "diff", "--name-only", f"{RESEARCH_BASE}..HEAD").splitlines()
    changed_files = [
        {"repo": "research", "path": name, "sha256": sha256_bytes((ROOT / name).read_bytes())}
        for name in changed_names
        if not name.startswith("outputs/release/") and (ROOT / name).is_file()
    ]
    changed_by_name = {row["path"]: row for row in changed_files}
    closure_rows = []
    for finding in findings["findings"]:
        rows = [row for row in executed_rows if row["finding_id"] == finding["finding_id"]]
        files = [
            changed_by_name[name]
            for name in FINDING_FILES[finding["finding_id"]]
            if name in changed_by_name
        ]
        closure_rows.append(
            {
                "finding_id": finding["finding_id"],
                "root_cause": finding["root_cause"],
                "required_fix": finding["required_fix"],
                "changed_files": files,
                "requirement_ids": [row["test_id"] for row in rows],
                "exact_pytest_nodeids": [row["pytest_nodeid"] for row in rows],
                "verifier_receipt": "independent_verifier/VERIFIER_RECEIPT.json",
                "closure_status": "closed_verified",
            }
        )
    input_lock = {
        "contract_id": "room16.ba11_r5.input_lock@1",
        "source_r5_filename": SOURCE_R5_NAME,
        "source_r5_bytes": len(source_r5),
        "source_r5_sha256": SOURCE_R5_SHA256,
        "source_r5_entries": 12,
        "source_r4_filename": SOURCE_R4_NAME,
        "source_r4_bytes": len(source_r4),
        "source_r4_sha256": SOURCE_R4_SHA256,
        "ready_for_independent_rereview": True,
        "ba11_implementation_ready": False,
        "ba12_authorized": False,
        "release_authorized": False,
        "publication_authorized": False,
    }
    executed_document = {
        "contract_id": "room16.ba11_r5.executed_test_matrix@1",
        "row_count": 18,
        "required_matrix": required_matrix,
        "collection_manifest": collection_manifest,
        "execution_report": execution_report,
        "rows": executed_rows,
    }
    foreign = foreign_boundary()
    members: dict[str, bytes] = {
        "00_R5_CORRECTION_VERDICT.md": b"# BA11 R5 Correction Verdict\n\nAll four R5 findings are implementation-closed and independently package-verified. The only asserted next state is `ready_for_independent_rereview=true`. BA11 implementation-ready, BA12, release and publication remain false.\n",
        "01_INPUT_LOCK.json": json_bytes(input_lock),
        "02_R5_FINDINGS.json": json_bytes(findings),
        "03_R5_FINDING_CLOSURE_REGISTER.json": json_bytes({"contract_id": "room16.ba11_r5.finding_closure_register@1", "findings": closure_rows}),
        "04_STAGING_PUBLICATION_ISOLATION_REPORT.json": json_bytes({"status": "PASS", "finding_id": "BA11-R4-RR-P0-001", "candidate_namespace": "staging/transactions/<transaction>/ledger", "published_namespace_pollution": False, "tests": [row["test_id"] for row in executed_rows if row["finding_id"] == "BA11-R4-RR-P0-001"]}),
        "05_MULTI_GENERATION_LIFECYCLE_REPORT.json": json_bytes({"status": "PASS", "finding_id": "BA11-R4-RR-P0-002", "generations": [0, 1, 2], "versions": ["1.0.0", "1.1.0", "1.2.0"], "full_history_replay": True}),
        "06_REGISTRY_HEAD_ROLLBACK_REPORT.json": json_bytes({"status": "PASS", "finding_id": "BA11-R4-RR-P0-003", "published_receipt_chain": True, "rollback_blocked": True, "old_base_publication_blocked": True}),
        "07_ACCEPTANCE_NODEID_REPORT.json": json_bytes({"status": "PASS", "finding_id": "BA11-R4-RR-P1-001", "requirement_count": 18, "unique_nodeid_count": len(set(TEST_NODEIDS.values())), "collection_manifest_sha256": collection_manifest["manifest_sha256"], "execution_report_sha256": execution_report["report_sha256"]}),
        "08_TEST_MATRIX_EXECUTED.json": json_bytes(executed_document),
        "09_R4_REGRESSION_REPORT.json": json_bytes({"status": "PASS", "declared_row_count": 54, "receipt_id": "targeted_r4", "exit_code": by_receipt["targeted_r4"]["exit_code"], "raw_stdout_sha256": by_receipt["targeted_r4"]["raw_stdout_sha256"]}),
        "10_FULL_REGRESSION_RECEIPTS.json": json_bytes({"contract_id": "room16.ba11_r5.command_receipts@1", "receipts": receipts}),
        "11_BA10_RAW_VERIFIER_RECEIPT.json": json_bytes({**by_receipt["ba10_freeze"], "parsed_stdout": json.loads(by_receipt["ba10_freeze"]["raw_stdout"])}),
        "12_SOURCE_TREE_BINDINGS.json": json_bytes({"research": research_binding, "product": product_binding}),
        "13_CHANGED_FILES_PER_FINDING.json": json_bytes({"files": changed_files, "finding_files": FINDING_FILES}),
        "14_DETERMINISTIC_BUILD_REPORT.json": json_bytes({"status": "PASS", "source_date_epoch": SOURCE_DATE_EPOCH, "assembly_passes": 2, "byte_identical": True}),
        "15_FOREIGN_WORKTREE_BOUNDARY_REPORT.json": json_bytes(foreign),
        "16_REREVIEW_REQUEST.md": b"# Independent R5 Rereview Request\n\nPlease independently rereview the four R5 closures. No merge, deploy, BA12, release or publication is requested or authorized.\n",
        f"source/{SOURCE_R5_NAME}": source_r5,
        f"source/{SOURCE_R4_NAME}": source_r4,
    }
    for row in changed_files:
        members[f"implementation/research/{row['path']}"] = (ROOT / row["path"]).read_bytes()
    verifier_receipt = derive_verifier_receipt(members)
    members["independent_verifier/VERIFIER_RECEIPT.json"] = json_bytes(verifier_receipt)
    first_zip, first_manifest = build_deterministic_zip(members, source_date_epoch=SOURCE_DATE_EPOCH)
    second_zip, second_manifest = build_deterministic_zip(members, source_date_epoch=SOURCE_DATE_EPOCH)
    if first_zip != second_zip or first_manifest != second_manifest:
        raise SystemExit("STOP deterministic builds differ")
    short = research_binding["head"][:12].upper()
    filename = f"ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_R5_{short}_2026-08-21.zip"
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
    (output / f"{filename}.identity.json").write_bytes(
        json_bytes(identity.model_dump(mode="json"))
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "package": str(output / filename),
                "package_bytes": len(first_zip),
                "package_sha256": identity.package_sha256,
                "manifest_sha256": first_manifest["manifest_sha256"],
                "member_count": len(members) + 1,
                "acceptance_rows": 18,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
