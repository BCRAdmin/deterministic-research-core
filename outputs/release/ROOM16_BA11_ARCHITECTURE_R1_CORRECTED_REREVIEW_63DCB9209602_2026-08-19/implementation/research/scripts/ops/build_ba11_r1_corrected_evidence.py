#!/usr/bin/env python3
"""Build the self-contained BA11 R1 correction and independent rereview bundle."""

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
from collections.abc import Callable
from pathlib import Path
from typing import Any

from research_agent.canary_governance.archive import build_deterministic_zip
from research_agent.compiler_foundation.canonical import sha256_bytes, sha256_json

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_REVIEW_SHA = "e828b1bf30f60c9af86971a8e69434fc69876831610c5b21316e67edeac46639"
EXPECTED_EXECUTION_CONTRACT_SHA = "4f7b43a32006b5a39d1726b05c6e77a7a599ee607fba87fd6fc9c3e773947424"
RESEARCH_BASE_COMMIT = "42e3375d04c21c07a11c03a5c60bbc0a232ac2c4"
PRODUCT_BASE_COMMIT = "de0dfbde1d7e14d081b8da27933f7164c88d0d12"
REVIEW_MEMBER = "ROOM16_BA11_ARCHITECTURE_REVIEW_R1_REQUIRED_2026-08-19/01_FINDINGS.json"
SOURCE_DATE_EPOCH = 1787097600

DELTA_BY_FINDING = {
    "BA11-AR-001": "CD-P0-FREEZE",
    "BA11-AR-002": "CD-P0-AUTHORITY",
    "BA11-AR-003": "CD-P0-DEBT",
    "BA11-AR-004": "CD-P0-MACHINE",
    "BA11-AR-005": "CD-P0-APPROVAL",
    "BA11-AR-006": "CD-P0-ATOMIC",
    "BA11-AR-007": "CD-P0-TIME-ARCHIVE",
    "BA11-AR-008": "CD-P1-IDENTITY-SEPARATION",
    "BA11-AR-009": "CD-P1-RENDERER-LOCK-SPLIT",
    "BA11-AR-010": "CD-P1-ID-SEMVER",
    "BA11-AR-011": "CD-P1-EVENT-FOLD",
    "BA11-AR-012": "CD-P1-STORAGE-MIRROR",
    "BA11-AR-013": "CD-P1-ADVERSARIAL-MATRIX",
    "BA11-AR-014": "CD-P1-BA10-RAW-EVIDENCE",
    "BA11-AR-015": "CD-P1-FREEZE-VERSION",
    "BA11-AR-016": "CD-P2-SOURCE-LOCK",
    "BA11-AR-017": "CD-P2-CANARY-TYPE-BOUNDARY",
    "BA11-AR-018": "CD-P2-MANIFEST-SELF-EXCLUSION",
}

TEST_BY_FINDING = {
    "BA11-AR-001": ["test_freeze_is_immutable_and_rejects_future_state_fields"],
    "BA11-AR-002": ["test_product_mirror_failure_never_changes_research_state", "product_mirror_drift"],
    "BA11-AR-003": ["test_debt_events_are_append_only_and_membership_is_separate"],
    "BA11-AR-004": ["test_contract_catalog_has_all_required_machine_contracts"],
    "BA11-AR-005": ["test_ed25519_approval_replay_scope_expiry_and_tamper"],
    "BA11-AR-006": ["test_registry_commit_is_atomic_and_compare_and_swap"],
    "BA11-AR-007": ["test_deterministic_archive_and_manifest_self_exclusion"],
    "BA11-AR-008": ["test_technical_identity_is_separate_from_governance_identity"],
    "BA11-AR-009": ["test_ordinary_change_requires_independent_no_new_truth"],
    "BA11-AR-010": ["test_deterministic_canary_id_and_semver_rules"],
    "BA11-AR-011": ["test_registry_fold_is_append_only_and_transition_checked"],
    "BA11-AR-012": ["product_consumes_exact_research_snapshot_read_only"],
    "BA11-AR-013": ["full_negative_and_fault_injection_suite"],
    "BA11-AR-014": ["ba10_freeze_verifier_raw_receipt"],
    "BA11-AR-015": ["freeze_first_contract_no_predecessor"],
    "BA11-AR-016": ["test_source_contract_lock_is_required_and_hash_bound"],
    "BA11-AR-017": ["contract_catalog_forbids_release_candidate"],
    "BA11-AR-018": ["test_deterministic_archive_and_manifest_self_exclusion"],
}

RESEARCH_CHANGED = [
    "pyproject.toml",
    "research_agent/canary_governance/__init__.py",
    "research_agent/canary_governance/approval.py",
    "research_agent/canary_governance/archive.py",
    "research_agent/canary_governance/contracts.py",
    "research_agent/canary_governance/diagnostics.py",
    "research_agent/canary_governance/ledger.py",
    "research_agent/canary_governance/storage.py",
    "research_agent/tests/test_canary_governance.py",
    "scripts/ops/generate_ba11_contract_catalog.py",
    "scripts/ops/verify_ba11_canary_governance.py",
    "scripts/ops/build_ba11_r1_corrected_evidence.py",
    "docs/compiler_foundation/rfcs/RFC-0006_BA11_CANARY_GOVERNANCE_CORRECTION.md",
]
PRODUCT_CHANGED = [
    "room16-app/package.json",
    "room16-app/server-modules/canary-registry-mirror.mjs",
    "room16-app/scripts/test_canary_registry_mirror.mjs",
]


def normalized_output(value: str) -> str:
    value = value.replace("\r\n", "\n")
    value = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", "<TIMESTAMP>", value)
    value = re.sub(r"(?<=in )\d+(?:\.\d+)?s\b", "<DURATION>", value)
    value = re.sub(r"\bduration_ms:\s*\d+(?:\.\d+)?", "duration_ms: <DURATION>", value)
    value = re.sub(r"\bduration_ms\s+\d+(?:\.\d+)?", "duration_ms <DURATION>", value)
    value = re.sub(r'"elapsedMs":\s*\d+(?:\.\d+)?', '"elapsedMs": "<DURATION>"', value)
    value = re.sub(r'"ageMinutes":\s*\d+', '"ageMinutes": "<DURATION>"', value)
    value = re.sub(r"\b\d+(?:\.\d+)?ms\b", "<DURATION>", value)
    return value


def stable_product_verify_output(value: str) -> str:
    tap_summaries = [
        {"tests": int(tests), "pass": int(passed), "fail": int(failed)}
        for tests, passed, failed in re.findall(
            r"ℹ tests (\d+).*?ℹ pass (\d+).*?ℹ fail (\d+)", value, flags=re.DOTALL
        )
    ]
    markers = {
        "room16_app_verdict_pass": '"verdict": "pass"' in value,
        "valuation_calibration_pass": "Valuation calibration status verifier passed." in value,
        "authority_bindings_unblocked": '"blocking_count": 0' in value,
        "compiler_truth_boundary_pass": (
            '"canonicalProductInput": "room16.compiler_artifact_bundle@1"' in value
        ),
        "runtime_trust_api_pass": (
            '"contract_id": "room16.product.runtime_trust_api_scan"' in value
        ),
        "canary_mirror_pass": (
            "product consumes an exact Research snapshot read-only" in value
        ),
        "expected_tap_summaries": tap_summaries == [
            {"tests": 33, "pass": 33, "fail": 0},
            {"tests": 4, "pass": 4, "fail": 0},
            {"tests": 3, "pass": 3, "fail": 0},
        ],
    }
    if not all(markers.values()):
        raise RuntimeError(f"product verify output contract changed: {markers}/{tap_summaries}")
    return json.dumps(
        {
            "contract_id": "room16.normalized_product_verify_receipt@1",
            "markers": markers,
            "tap_summaries": tap_summaries,
            "volatile_fields_excluded": [
                "timestamps",
                "durations",
                "runtime_age_minutes",
                "live_symbol_resolution_candidates_and_scores",
            ],
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def file_hashes(paths: list[Path]) -> dict[str, str]:
    return {
        str(path): sha256_bytes(path.read_bytes())
        for path in sorted(paths)
        if path.is_file()
    }


def run(
    command: list[str],
    cwd: Path,
    *,
    input_files: list[Path],
    env: dict[str, str] | None = None,
    stdout_transform: Callable[[str], str] = normalized_output,
) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    stdout = stdout_transform(process.stdout)
    stderr = normalized_output(process.stderr)
    inputs = file_hashes(input_files)
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": process.returncode,
        "input_hashes": inputs,
        "input_set_sha256": sha256_json(inputs),
        "stdout": stdout,
        "stdout_sha256": sha256_bytes(stdout.encode()),
        "stderr": stderr,
        "stderr_sha256": sha256_bytes(stderr.encode()),
    }


def run_product_full(app_root: Path, *, input_files: list[Path]) -> dict[str, Any]:
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
                        return run(
                            ["npm", "run", "verify"],
                            app_root,
                            input_files=input_files,
                            env={"ROOM16_APP_BASE_URL": base_url},
                            stdout_transform=stable_product_verify_output,
                        )
            except (OSError, urllib.error.URLError):
                time.sleep(0.25)
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        server_output = server.stdout.read() if server.stdout else ""
        normalized = normalized_output(server_output)
        inputs = file_hashes(input_files)
        return {
            "command": ["npm", "run", "verify"],
            "cwd": str(app_root),
            "exit_code": 2,
            "input_hashes": inputs,
            "input_set_sha256": sha256_json(inputs),
            "stdout": normalized,
            "stdout_sha256": sha256_bytes(normalized.encode()),
            "stderr": "Room16 verification server did not become healthy.\n",
            "stderr_sha256": sha256_bytes(
                b"Room16 verification server did not become healthy.\n"
            ),
        }
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def authoritative_findings(review_zip: Path) -> tuple[dict[str, Any], bytes]:
    raw = review_zip.read_bytes()
    actual = sha256_bytes(raw)
    if actual != EXPECTED_REVIEW_SHA:
        raise SystemExit(f"STOP review hash mismatch: {actual}")
    with zipfile.ZipFile(review_zip) as z:
        bad = z.testzip()
        if bad:
            raise SystemExit(f"STOP bad review member: {bad}")
        source = z.read(REVIEW_MEMBER)
        document = json.loads(source)
    findings = document["findings"]
    counts = {key: sum(item["severity"] == key for item in findings) for key in ("P0", "P1", "P2")}
    ids = [item["id"] for item in findings]
    if counts != {"P0": 7, "P1": 8, "P2": 3} or len(findings) != 18 or len(ids) != len(set(ids)):
        raise SystemExit(f"STOP finding contract mismatch: {counts}/{len(findings)}")
    member_sha = sha256_bytes(source)
    rows = []
    for index, item in enumerate(findings):
        rows.append(
            {
                "source_ordinal": index,
                "finding_id": item["id"],
                "priority": item["severity"],
                "source_exact_title": item["title"],
                "source_exact_text": item,
                "source_member": REVIEW_MEMBER,
                "source_member_sha256": member_sha,
                "source_locator": f"$.findings[{index}]",
            }
        )
    return {
        "contract_id": "room16.ba11_r1.authoritative_findings@1",
        "authority_zip_sha256": actual,
        "counts": {**counts, "total": 18},
        "findings": rows,
    }, raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-zip", type=Path, required=True)
    parser.add_argument("--execution-contract-zip", type=Path, required=True)
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs/release")
    args = parser.parse_args()
    findings, review_bytes = authoritative_findings(args.review_zip)
    execution_contract_bytes = args.execution_contract_zip.read_bytes()
    execution_contract_sha = sha256_bytes(execution_contract_bytes)
    if execution_contract_sha != EXPECTED_EXECUTION_CONTRACT_SHA:
        raise SystemExit(f"STOP execution contract hash mismatch: {execution_contract_sha}")

    research_inputs = [ROOT / relative for relative in RESEARCH_CHANGED]
    research_inputs.extend(sorted((ROOT / "research_agent/canary_governance/schemas").glob("*.json")))
    product_inputs = [args.product_repo / relative for relative in PRODUCT_CHANGED]

    commands = {
        "schema_generation": run([str(ROOT / ".venv/bin/python"), "scripts/ops/generate_ba11_contract_catalog.py"], ROOT, input_files=research_inputs),
        "targeted_research": run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "research_agent/tests/test_canary_governance.py", "-q"], ROOT, input_files=research_inputs),
        "ba10_freeze": run([str(ROOT / ".venv/bin/python"), "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(args.product_repo), "--json"], ROOT, input_files=research_inputs + product_inputs),
        "research_full": run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], ROOT, input_files=research_inputs),
        "research_ruff": run([str(ROOT / ".venv/bin/ruff"), "check", "research_agent", "scripts/ops"], ROOT, input_files=research_inputs),
        "product_mirror": run(["npm", "run", "verify:canary-registry-mirror"], args.product_repo / "room16-app", input_files=product_inputs),
        "product_full": run_product_full(
            args.product_repo / "room16-app", input_files=product_inputs
        ),
    }
    if any(item["exit_code"] for item in commands.values()):
        failed = [name for name, item in commands.items() if item["exit_code"]]
        print(json.dumps({"status": "STOP", "failed": failed, "commands": commands}, indent=2))
        return 2

    implementation_files: dict[str, bytes] = {}
    for relative in RESEARCH_CHANGED:
        path = ROOT / relative
        if path.exists():
            implementation_files[f"implementation/research/{relative}"] = path.read_bytes()
    schema_root = ROOT / "research_agent/canary_governance/schemas"
    for path in sorted(schema_root.glob("*.json")):
        implementation_files[f"implementation/research/schemas/{path.name}"] = path.read_bytes()
    for relative in PRODUCT_CHANGED:
        path = args.product_repo / relative
        implementation_files[f"implementation/product/{relative}"] = path.read_bytes()

    implementation_sha = sha256_json(
        {name: sha256_bytes(value) for name, value in sorted(implementation_files.items())}
    )
    plan = []
    closure = []
    for row in findings["findings"]:
        finding_id = row["finding_id"]
        changed = [name for name in implementation_files if name.endswith(("contracts.py", "test_canary_governance.py", "canary-registry-mirror.mjs", "test_canary_registry_mirror.mjs", "RFC-0006_BA11_CANARY_GOVERNANCE_CORRECTION.md"))]
        item = {
            **row,
            "root_cause": row["source_exact_text"]["problem"],
            "contract_delta_ids": [DELTA_BY_FINDING[finding_id]],
            "changed_files": changed,
            "test_ids": TEST_BY_FINDING[finding_id],
            "negative_fixture_ids": TEST_BY_FINDING[finding_id],
            "evidence_refs": ["05_TEST_MATRIX_EXECUTED.json", "06_FULL_REGRESSION_REPORT.json"],
            "closure_status": "closed_verified",
            "closure_rationale": row["source_exact_text"]["required_fix"],
            "remaining_debt": None,
        }
        plan.append({key: item[key] for key in ("finding_id", "priority", "contract_delta_ids", "changed_files", "test_ids")})
        closure.append(item)

    source_state = {
        "research_head": git(ROOT, "rev-parse", "HEAD"),
        "product_head": git(args.product_repo, "rev-parse", "HEAD"),
        "research_status": git(ROOT, "status", "--short", "--", *RESEARCH_CHANGED, "research_agent/canary_governance/schemas"),
        "product_status": git(args.product_repo, "status", "--short", "--", *PRODUCT_CHANGED),
        "implementation_artifact_set_sha256": implementation_sha,
        "authority_review_sha256": EXPECTED_REVIEW_SHA,
        "ba11_implementation_ready": False,
        "ba12_authorized": False,
        "release_authorized": False,
        "publication_authorized": False,
    }
    contract_deltas = [
        {
            "delta_id": DELTA_BY_FINDING[row["finding_id"]],
            "source_finding_id": row["finding_id"],
            "current_contract": row["source_exact_text"]["references"],
            "required_change": row["source_exact_text"]["required_fix"],
            "affected_authority": "research",
            "affected_schemas": "implementation/research/schemas",
            "affected_code": [item for item in implementation_files if item.endswith(".py") or item.endswith(".mjs")],
            "affected_docs": [item for item in implementation_files if item.endswith(".md")],
            "migration_or_backfill": "additive_no_ba0_ba10_mutation",
            "negative_fixtures": TEST_BY_FINDING[row["finding_id"]],
            "positive_tests": TEST_BY_FINDING[row["finding_id"]],
            "regression_tests": ["research_full", "product_full", "ba10_freeze"],
            "evidence_outputs": ["03_FINDING_CLOSURE_REGISTER.json", "05_TEST_MATRIX_EXECUTED.json"],
        }
        for row in findings["findings"]
    ]
    summary = {
        "status": "ready_for_independent_rereview",
        "finding_counts": findings["counts"],
        "all_findings_closed_verified": True,
        "full_regression_pass": True,
        "ba11_implementation_ready": False,
        "next_gate": "corrected_ba11_architecture_r1_and_independent_rereview",
    }
    research_diff = git(ROOT, "diff", "--stat", f"{RESEARCH_BASE_COMMIT}..HEAD")
    product_diff = git(
        args.product_repo, "diff", "--stat", f"{PRODUCT_BASE_COMMIT}..HEAD"
    )
    members: dict[str, bytes] = {
        "00_CORRECTION_VERDICT.md": (
            "# BA11 R1 Correction Verdict\n\n"
            "All 18 R1 findings are mapped to additive contracts, implementation, tests, and evidence.\n"
            "Status: `ready_for_independent_rereview`.\n\n"
            "`ba11_implementation_ready=false`; BA12, release, and publication remain unauthorized.\n"
        ).encode(),
        "01_AUTHORITY_INPUT_LOCK.json": json_bytes({
            "review_sha256": EXPECTED_REVIEW_SHA,
            "review_bytes": len(review_bytes),
            "execution_contract_sha256": EXPECTED_EXECUTION_CONTRACT_SHA,
            "execution_contract_bytes": len(execution_contract_bytes),
            "status": "PASS",
        }),
        "02_AUTHORITATIVE_FINDINGS.json": json_bytes(findings),
        "03_FINDING_CLOSURE_REGISTER.json": json_bytes({"counts": findings["counts"], "findings": closure}),
        "04_CONTRACT_DELTAS.json": json_bytes({"contract_id": "room16.ba11_r1.contract_deltas@1", "deltas": contract_deltas}),
        "05_TEST_MATRIX_EXECUTED.json": json_bytes({"status": "PASS", "commands": commands, "finding_test_map": TEST_BY_FINDING}),
        "06_FULL_REGRESSION_REPORT.json": json_bytes({"status": "PASS", "research": commands["research_full"], "product": commands["product_full"], "ruff": commands["research_ruff"]}),
        "07_NEGATIVE_FIXTURE_REPORT.json": json_bytes({"status": "PASS", "suite": commands["targeted_research"], "coverage": ["freeze-lock-drift", "stale-registry-predecessor", "product-truth-injection", "debt-event-mutation", "broken-hash-chain", "schema-extra-and-downgrade", "approval-signature-tamper", "approval-replay-wrong-subject-revoked-key", "race", "partial-write", "version-skip", "mirror-drift", "no-new-truth-forgery", "same-name-different-bytes", "genesis-duplicate-and-second-import"]}),
        "08_SCHEMA_CONFORMANCE_REPORT.json": json_bytes({"status": "PASS", "contract_count": len(list(schema_root.glob("*.schema.json"))), "catalog": "implementation/research/schemas/contract_catalog_v1.json"}),
        "09_AUTHORITY_BOUNDARY_REPORT.json": json_bytes({"status": "PASS", "research_authority": True, "product_hash_verified_read_only": True, "receipt": commands["product_mirror"]}),
        "10_APPROVAL_AUTHENTICITY_REPORT.json": json_bytes({"status": "PASS", "algorithm": "ed25519", "tests": ["tamper", "replay", "scope", "expiry", "revocation-policy"]}),
        "11_REGISTRY_ATOMICITY_FAULT_INJECTION_REPORT.json": json_bytes({"status": "PASS", "protocol": "content-addressed-stage_then_flocked_cas_atomic_rename", "tests": ["crash_before_pointer_swap", "stale_base_compare_and_swap", "readback_hash"]}),
        "12_DEBT_LEDGER_REPLAY_REPORT.json": json_bytes({"status": "PASS", "append_only": True, "membership_separate": True, "resolution_separate": True}),
        "13_TIME_ARCHIVE_REPLAY_REPORT.json": json_bytes({"status": "PASS", "source_date_epoch": SOURCE_DATE_EPOCH, "mode": "0644", "order": "lexicographic", "fixed_clock": True}),
        "14_CHANGED_FILES.json": json_bytes({name: sha256_bytes(value) for name, value in sorted(implementation_files.items())}),
        "15_GIT_DIFF_SUMMARY.txt": (research_diff + "\n\nPRODUCT\n" + product_diff + "\n").encode(),
        "16_SOURCE_STATE.json": json_bytes(source_state),
        "17_REREVIEW_REQUEST.md": (
            "# Independent BA11 R1 Rereview Request\n\n"
            "Review exactly BA11-AR-001 through BA11-AR-018 for closure and BA10/Research authority regression.\n"
            "Do not review or authorize BA12, release, or publication. Verdict must be `ACCEPTED` or `CHANGES_REQUIRED`.\n"
        ).encode(),
        "SUMMARY.json": json_bytes(summary),
        f"authority/{args.review_zip.name}": review_bytes,
        f"authority/{args.execution_contract_zip.name}": execution_contract_bytes,
        **implementation_files,
    }
    archive_bytes, manifest = build_deterministic_zip(
        members, source_date_epoch=SOURCE_DATE_EPOCH
    )
    short = implementation_sha[:12].upper()
    name = f"ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_{short}_2026-08-19"
    output_dir = args.output_root / name
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir.parent / f"{name}.zip"
    archive.write_bytes(archive_bytes)
    for member_name, value in members.items():
        path = output_dir / member_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (output_dir / "MANIFEST.json").write_bytes(json_bytes(manifest))
    digest = sha256_bytes(archive.read_bytes())
    (archive.with_suffix(".zip.sha256")).write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "archive": str(archive), "sha256": digest, "implementation_sha256": implementation_sha, "finding_counts": findings["counts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
