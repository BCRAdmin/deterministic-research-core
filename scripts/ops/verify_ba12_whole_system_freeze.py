#!/usr/bin/env python3
"""Fail-closed verifier for the accepted Room16 BA0-BA12 system freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
DEFAULT_RECORD = ROOT / "docs/compiler_foundation/freezes/BA12_WHOLE_SYSTEM_FREEZE_v1.json"
DEFAULT_ACCEPTANCE = ROOT / "docs/compiler_foundation/acceptance/BA12_R5_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
DEFAULT_HANDOFF = Path(
    "/Users/BjornRosinger/Downloads/"
    "ROOM16_BA12_WHOLE_SYSTEM_ACCEPTANCE_FREEZE_EXECUTION_R1_CB3CF2FA346A_2026-08-25.zip"
)


class BA12WholeSystemFreezeError(RuntimeError):
    """Stable whole-system freeze diagnostic."""


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BA12WholeSystemFreezeError(f"BA12_FREEZE_JSON_OBJECT_REQUIRED:{path}")
    return value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def freeze_sha256(record: dict[str, Any]) -> str:
    body = dict(record)
    body.pop("freeze_sha256", None)
    return hashlib.sha256(str(record["freeze_hash_domain"]).encode() + b"\0" + _canonical(body)).hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True)
    if result.returncode:
        raise BA12WholeSystemFreezeError(
            f"BA12_FREEZE_GIT_FAILED:{repo}:{' '.join(args)}:{result.stderr.strip()}"
        )
    return result.stdout.strip()


def _ancestor(repo: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=repo,
        capture_output=True,
    ).returncode == 0


def _run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise BA12WholeSystemFreezeError(
            f"BA12_FREEZE_COMMAND_FAILED:{' '.join(command)}:{result.stdout}:{result.stderr}"
        )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BA12WholeSystemFreezeError(
            f"BA12_FREEZE_COMMAND_JSON_INVALID:{' '.join(command)}"
        ) from exc
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise BA12WholeSystemFreezeError(
            f"BA12_FREEZE_COMMAND_STATUS:{' '.join(command)}"
        )
    return value


def _verify_handoff(record: dict[str, Any], handoff: Path) -> dict[str, Any]:
    expected = record["handoff"]
    if (
        not handoff.is_file()
        or handoff.stat().st_size != expected["bytes"]
        or _sha256(handoff) != expected["sha256"]
    ):
        raise BA12WholeSystemFreezeError("BA12_FREEZE_HANDOFF_IDENTITY")
    with zipfile.ZipFile(handoff) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != expected["zip_entries"]:
            raise BA12WholeSystemFreezeError("BA12_FREEZE_HANDOFF_ZIP")
        manifest_bytes = archive.read("MANIFEST.json")
        manifest = json.loads(manifest_bytes)
        if _sha256_bytes(manifest_bytes) != expected["manifest_raw_sha256"]:
            raise BA12WholeSystemFreezeError("BA12_FREEZE_HANDOFF_MANIFEST_RAW")
        if manifest.get("manifest_sha256") != expected["declared_manifest_sha256"]:
            raise BA12WholeSystemFreezeError("BA12_FREEZE_HANDOFF_MANIFEST_METADATA")
        files = manifest.get("files")
        if not isinstance(files, list) or len(files) != manifest.get("file_count"):
            raise BA12WholeSystemFreezeError("BA12_FREEZE_HANDOFF_MANIFEST_FILES")
        for item in files:
            payload = archive.read(item["path"])
            if len(payload) != item["bytes"] or _sha256_bytes(payload) != item["sha256"]:
                raise BA12WholeSystemFreezeError(
                    f"BA12_FREEZE_HANDOFF_PAYLOAD:{item['path']}"
                )
        sums = archive.read("SHA256SUMS.txt").decode()
        if f"{expected['manifest_raw_sha256']}  MANIFEST.json" not in sums:
            raise BA12WholeSystemFreezeError("BA12_FREEZE_HANDOFF_SUMS_MANIFEST")
        acceptance_bytes = archive.read("01_EXTERNAL_INDEPENDENT_BA12_ACCEPTANCE.json")
        r5_bytes = archive.read(
            "authority/ROOM16_BA12_FINAL_STRANGLER_CUTOVER_R5_A92C6D9_2026-08-25.zip"
        )
    return {
        "acceptance_bytes": acceptance_bytes,
        "manifest": manifest,
        "r5_bytes": r5_bytes,
    }


def _verify_r5(record: dict[str, Any], payload: bytes) -> dict[str, Any]:
    expected = record["r5_package"]
    local = ROOT / expected["path"]
    if (
        _sha256_bytes(payload) != expected["sha256"]
        or len(payload) != expected["bytes"]
        or not local.is_file()
        or local.read_bytes() != payload
    ):
        raise BA12WholeSystemFreezeError("BA12_FREEZE_R5_IDENTITY")
    with zipfile.ZipFile(local) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != expected["zip_entries"]:
            raise BA12WholeSystemFreezeError("BA12_FREEZE_R5_ZIP")
        source = archive.read("independent_verifier/verify.py")
        r5_matrix = json.loads(archive.read("12_R5_ACCEPTANCE_MATRIX_EXECUTED.json"))
        r4_matrix = json.loads(archive.read("13_R4_BA12_MATRIX_REGRESSION.json"))
        rfc10_matrix = json.loads(archive.read("14_R4_RFC0010_DELTA_REGRESSION.json"))
        canaries = json.loads(archive.read("11_WM_COST_ABT_R4_NATIVE_REVERIFY.json"))
        static_runtime = json.loads(archive.read("06_STATIC_RUNTIME_HTTP_REPORT.json"))
        dev_runtime = json.loads(archive.read("07_DEV_RUNTIME_HTTP_REPORT.json"))
    with tempfile.TemporaryDirectory(prefix="room16-ba12-freeze-r5-") as temporary:
        verifier = Path(temporary) / "verify.py"
        verifier.write_bytes(source)
        result = _run_json([sys.executable, str(verifier), str(local)], ROOT)
    if (
        result.get("manifest_sha256") != expected["manifest_sha256"]
        or result.get("verified_file_count") != expected["verified_payload_count"]
    ):
        raise BA12WholeSystemFreezeError("BA12_FREEZE_R5_VERIFIER_BINDING")
    return {
        **result,
        "r5_matrix_rows": r5_matrix.get("row_count"),
        "r4_matrix_rows": r4_matrix.get("row_count"),
        "rfc0010_delta_rows": rfc10_matrix.get("row_count"),
        "canary_bundle_count": len(canaries.get("bundles", [])),
        "canary_tickers": sorted(item.get("ticker") for item in canaries.get("bundles", [])),
        "static_runtime_status": static_runtime.get("status"),
        "dev_runtime_status": dev_runtime.get("status"),
    }


def _runtime_diff(
    repo: Path,
    base: str,
    pathspec: list[str],
) -> tuple[list[str], list[str]]:
    committed = _git(repo, "diff", "--name-only", f"{base}..HEAD", "--", *pathspec)
    worktree = _git(
        repo,
        "status",
        "--porcelain",
        "--untracked-files=all",
        "--",
        *pathspec,
    )
    return (
        committed.splitlines() if committed else [],
        worktree.splitlines() if worktree else [],
    )


def verify(
    record_path: Path = DEFAULT_RECORD,
    acceptance_path: Path = DEFAULT_ACCEPTANCE,
    handoff_path: Path = DEFAULT_HANDOFF,
    product_repo: Path = PRODUCT,
) -> dict[str, Any]:
    record = _json(record_path)
    acceptance = _json(acceptance_path)
    checks: dict[str, bool] = {}

    checks["freeze_contract"] = (
        record.get("contract_id") == "room16.ba12.whole_system_freeze"
        and record.get("schema_version") == 1
        and record.get("status") == "accepted_frozen"
        and record.get("roadmap") == "BA0-BA12"
    )
    checks["freeze_self_hash"] = record.get("freeze_sha256") == freeze_sha256(record)
    handoff = _verify_handoff(record, handoff_path)
    checks["handoff_identity"] = True
    checks["handoff_payload_hashes"] = True
    checks["handoff_manifest_raw_binding"] = True

    independent = record["independent_acceptance"]
    checks["independent_acceptance"] = (
        acceptance_path.is_file()
        and _sha256(acceptance_path) == independent["file_sha256"]
        and acceptance_path.read_bytes() == handoff["acceptance_bytes"]
        and acceptance.get("contract_id") == "room16.ba12.r5.external_independent_acceptance@1"
        and acceptance.get("verdict") == "ACCEPTED"
        and acceptance.get("blocking_findings") == 0
        and acceptance.get("acceptance_receipt_sha256")
        == independent["acceptance_receipt_sha256"]
    )
    r5_result = _verify_r5(record, handoff["r5_bytes"])
    checks["r5_package_identity"] = True
    checks["r5_standalone_verifier"] = r5_result.get("status") == "PASS"
    checks["accepted_matrices"] = (
        r5_result.get("r5_matrix_rows") == 33
        and r5_result.get("r4_matrix_rows") == 50
        and r5_result.get("rfc0010_delta_rows") == 14
    )
    checks["accepted_canaries"] = (
        r5_result.get("canary_bundle_count") == 3
        and r5_result.get("canary_tickers") == ["ABT", "COST", "WM"]
    )
    checks["accepted_ui_runtime"] = (
        r5_result.get("static_runtime_status") == "PASS"
        and r5_result.get("dev_runtime_status") == "PASS"
    )

    bindings = record["git_bindings"]
    research = bindings["research"]
    product = bindings["product"]
    checks["research_identity"] = (
        _git(ROOT, "remote", "get-url", "origin") == research["remote"]
        and _git(ROOT, "branch", "--show-current") == research["branch"]
        and _git(ROOT, "rev-parse", f"{research['implementation_commit']}^{{tree}}")
        == research["implementation_tree"]
        and _git(ROOT, "rev-parse", f"{research['evidence_commit']}^{{tree}}")
        == research["evidence_tree"]
        and _ancestor(ROOT, research["implementation_commit"])
        and _ancestor(ROOT, research["evidence_commit"])
    )
    checks["product_identity"] = (
        _git(product_repo, "remote", "get-url", "origin") == product["remote"]
        and _git(product_repo, "branch", "--show-current") == product["branch"]
        and _git(product_repo, "rev-parse", "HEAD") == product["implementation_commit"]
        and _git(product_repo, "rev-parse", "HEAD^{tree}") == product["implementation_tree"]
    )

    protection = record["runtime_protection"]
    research_committed, research_worktree = _runtime_diff(
        ROOT,
        protection["accepted_research_implementation_commit"],
        protection["research_pathspec"],
    )
    product_committed, product_worktree = _runtime_diff(
        product_repo,
        protection["accepted_product_commit"],
        protection["product_pathspec"],
    )
    checks["research_runtime_unchanged"] = not research_committed and not research_worktree
    checks["product_runtime_unchanged"] = not product_committed and not product_worktree

    py = sys.executable
    prior_commands = {
        "semantic_wave_freeze": [py, "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--product-repo", str(product_repo), "--json"],
        "ba10_freeze": [py, "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(product_repo), "--json"],
        "ba11_freeze": [py, "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"],
        "rfc0008_freeze": [py, "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--json"],
        "rfc0009_freeze": [py, "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(product_repo), "--json"],
        "rfc0010_freeze": [py, "scripts/ops/verify_rfc0010_freeze.py", "--product-repo", str(product_repo), "--json"],
    }
    prior_results = {name: _run_json(command, ROOT) for name, command in prior_commands.items()}
    checks.update({name: result.get("status") == "PASS" for name, result in prior_results.items()})
    launch = _run_json(
        ["node", "scripts/verify_ba12_canonical_runtime.mjs"],
        product_repo / "room16-app",
    )
    checks["canonical_launch_graph"] = (
        launch.get("canonical_runtime_count") == 1
        and launch.get("canonical_legacy_semantic_readers") == 0
        and launch.get("legacy_fallback_edges") == 0
        and launch.get("normal_launcher_targets_legacy_server") is False
    )
    expected_prior = {
        "ba10_freeze": record["ba10_freeze_sha256"],
        "ba11_freeze": record["ba11_freeze_sha256"],
        "rfc0008_freeze": record["rfc0008_freeze_sha256"],
        "rfc0009_freeze": record["rfc0009_freeze_sha256"],
        "rfc0010_freeze": record["rfc0010_freeze_sha256"],
    }
    for name, expected in expected_prior.items():
        observed = prior_results[name].get("freeze_sha256") or prior_results[name].get("freeze_lock_sha256")
        checks[f"{name}_identity"] = observed == expected

    checks["final_status"] = (
        record.get("ba0_ba12_rebuild_complete") is True
        and record.get("ba12_implementation_ready") is True
        and record.get("ba12_frozen") is True
        and record.get("ba12_independent_rereview") == "ACCEPTED"
        and record.get("release_ready") is True
        and all(
            record.get(field) is False
            for field in (
                "release_authorized",
                "deploy_authorized",
                "publication_authorized",
                "public_member_visibility_authorized",
                "commerce_authorized",
                "payment_authorized",
                "external_communication_authorized",
            )
        )
    )
    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "contract_id": "room16.ba12.whole_system_freeze_verification@1",
        "status": "PASS" if not failed else "FAIL",
        "freeze_sha256": record.get("freeze_sha256"),
        "checks": checks,
        "failed_checks": failed,
        "research_runtime_committed_diff": research_committed,
        "research_runtime_worktree_diff": research_worktree,
        "product_runtime_committed_diff": product_committed,
        "product_runtime_worktree_diff": product_worktree,
        "canonical_launch_graph": launch,
        "r5_verifier": r5_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--product-repo", type=Path, default=PRODUCT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(
            args.record.resolve(),
            args.acceptance.resolve(),
            args.handoff.resolve(),
            args.product_repo.resolve(),
        )
    except (BA12WholeSystemFreezeError, OSError, ValueError, zipfile.BadZipFile) as exc:
        result = {
            "contract_id": "room16.ba12.whole_system_freeze_verification@1",
            "status": "FAIL",
            "error": str(exc),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
