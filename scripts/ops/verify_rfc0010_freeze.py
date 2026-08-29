#!/usr/bin/env python3
"""Fail-closed verifier for the accepted RFC-0010 live-capture freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRODUCT = ROOT.parent / "company-dossier-lab"
DEFAULT_RECORD = ROOT / "docs/compiler_foundation/freezes/RFC0010_BA12_LIVE_CAPTURE_TRANSPORT_FREEZE_v1.json"
DEFAULT_ACCEPTANCE = ROOT / "docs/compiler_foundation/acceptance/RFC0010_R2_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
HISTORICAL_INPUT_ROOT = Path(
    os.environ.get("ROOM16_HISTORICAL_REGRESSION_INPUT_ROOT", "/Users/BjornRosinger/Downloads")
)
DEFAULT_HANDOFF = HISTORICAL_INPUT_ROOT / (
    "ROOM16_RFC0010_ACCEPTANCE_FREEZE_AND_BA12_RESUME_EXECUTION_R1_"
    "B3C1F0A161CA_2026-08-25.zip"
)


class RFC0010FreezeError(RuntimeError):
    """Stable RFC-0010 freeze diagnostic."""


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RFC0010FreezeError(f"json_object_required:{path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _ancestor(repo: Path, commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=repo
        ).returncode
        == 0
    )


def freeze_sha256(record: dict[str, Any]) -> str:
    body = dict(record)
    body.pop("freeze_sha256", None)
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(
        str(record["freeze_hash_domain"]).encode() + b"\0" + canonical
    ).hexdigest()


def _run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if process.returncode:
        raise RFC0010FreezeError(
            f"command_failed:{' '.join(command)}:{process.stdout}:{process.stderr}"
        )
    value = json.loads(process.stdout)
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise RFC0010FreezeError(f"command_status_not_pass:{' '.join(command)}")
    return value


def _verify_embedded_r2(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(package) as archive:
        source = archive.read("independent_verifier/verify_rfc0010_r2_evidence.py")
    namespace: dict[str, Any] = {
        "__file__": "independent_verifier/verify_rfc0010_r2_evidence.py",
        "__name__": "rfc0010_r2_delivered_verifier",
    }
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    result = namespace["verify_package"](package)
    if not isinstance(result, dict) or result.get("status") != "PASS":
        raise RFC0010FreezeError("delivered_r2_verifier_status_not_pass")
    return result


def _handoff(
    record: dict[str, Any], handoff: Path, acceptance: Path
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    expected = record["handoff"]
    if (
        not handoff.is_file()
        or handoff.name != expected["filename"]
        or handoff.stat().st_size != expected["bytes"]
        or _sha(handoff) != expected["sha256"]
    ):
        return False, ["handoff_identity"]
    try:
        with zipfile.ZipFile(handoff) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != expected["zip_entries"]:
                failures.append("handoff_zip")
            if archive.read("01_EXTERNAL_INDEPENDENT_RFC0010_ACCEPTANCE.json") != acceptance.read_bytes():
                failures.append("acceptance_not_byte_exact")
            if hashlib.sha256(archive.read("authority/ROOM16_RFC0010_BA12_LIVE_CAPTURE_TRANSPORT_R2_6B2EFC3CB2FC_2026-08-25.zip")).hexdigest() != record["source_r2"]["package_sha256"]:
                failures.append("embedded_r2_identity")
            sums: dict[str, str] = {}
            for line in archive.read("SHA256SUMS.txt").decode().splitlines():
                digest, name = line.split("  ", 1)
                sums[name] = digest
            for name, digest in sums.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    failures.append(f"handoff_member:{name}")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        failures.append(f"handoff_exception:{type(exc).__name__}")
    return not failures, failures


def verify(
    record_path: Path,
    acceptance_path: Path,
    handoff_path: Path,
    product_repo: Path,
) -> dict[str, Any]:
    record = _json(record_path)
    acceptance = _json(acceptance_path)
    checks: dict[str, bool] = {}
    checks["freeze_contract"] = (
        record.get("contract_id") == "room16.rfc0010.ba12_live_capture_transport_freeze"
        and record.get("schema_version") == 1
        and record.get("status") == "accepted_frozen"
    )
    checks["freeze_self_hash"] = record.get("freeze_sha256") == freeze_sha256(record)
    accepted = record["external_independent_acceptance"]
    checks["external_acceptance"] = (
        _sha(acceptance_path) == accepted["file_sha256"]
        and acceptance.get("verdict") == "ACCEPTED"
        and acceptance.get("remaining_blocking_findings") == 0
        and acceptance.get("acceptance_receipt_sha256")
        == accepted["acceptance_receipt_sha256"]
    )
    checks["independent_review_closure"] = (
        acceptance.get("independent_checks", {}).get("r2_matrix_37_of_37") == "PASS"
        and acceptance.get("independent_checks", {}).get("r1_regression_47_of_47") == "PASS"
        and all(
            value == "PASS" for value in acceptance.get("independent_checks", {}).values()
        )
    )
    handoff_ok, handoff_failures = _handoff(
        record, handoff_path, acceptance_path
    )
    checks["handoff_integrity"] = handoff_ok

    research = record["git_bindings"]["research"]
    product = record["git_bindings"]["product"]
    checks["research_identity"] = (
        _git(ROOT, "remote", "get-url", "origin") == research["remote"]
        and _git(ROOT, "branch", "--show-current") == research["branch"]
        and _git(ROOT, "rev-parse", f"{research['implementation_commit']}^{{tree}}")
        == research["implementation_tree"]
        and _git(ROOT, "rev-parse", f"{research['evidence_commit_2']}^{{tree}}")
        == research["evidence_tree_2"]
        and all(
            _ancestor(ROOT, commit)
            for commit in (
                research["implementation_commit"],
                research["evidence_commit_1"],
                research["evidence_commit_2"],
            )
        )
    )
    product_head = _git(product_repo, "rev-parse", "HEAD")
    product_delta = tuple(
        line
        for line in _git(
            product_repo,
            "diff",
            "--name-only",
            f"{product['implementation_commit']}..{product_head}",
        ).splitlines()
        if line
    )
    allowed_ba12_product_prefixes = (
        "room16-app/ba12-",
        "room16-app/server-modules/ba12-",
        "room16-app/scripts/test_ba12_",
    )
    allowed_ba12_product_paths = {
        "room16-app/archive-server-launcher.mjs",
        "room16-app/package.json",
        "room16-app/scripts/ensure_room16_server.sh",
        "room16-app/scripts/room16_night_hardening_loop.mjs",
        "room16-app/scripts/run_ba12_product_verification.mjs",
        "room16-app/scripts/verify_ba12_canonical_runtime.mjs",
    }
    checks["product_identity"] = (
        _git(product_repo, "remote", "get-url", "origin") == product["remote"]
        and _git(product_repo, "branch", "--show-current") == product["branch"]
        and _git(product_repo, "rev-parse", f"{product['implementation_commit']}^{{tree}}")
        == product["implementation_tree"]
        and _ancestor(product_repo, product["implementation_commit"])
        and all(
            path in allowed_ba12_product_paths
            or path.startswith(allowed_ba12_product_prefixes)
            for path in product_delta
        )
    )

    runtime_failures: list[str] = []
    for item in record["rfc0010_runtime_files"]:
        path = ROOT / item["path"]
        if not path.is_file() or _sha(path) != item["sha256"]:
            runtime_failures.append(item["path"])
    checks["runtime_files_exact"] = not runtime_failures
    checks["phase_a_zero_runtime_diff"] = (
        _git(ROOT, "status", "--porcelain", "--", "research_agent/ba12_live_source") == ""
        and _git(product_repo, "status", "--porcelain", "--", "room16-app") == ""
    )

    source = record["source_r2"]
    source_path = ROOT / source["package_path"]
    checks["r2_package_identity"] = (
        source_path.is_file()
        and source_path.stat().st_size == source["bytes"]
        and _sha(source_path) == source["package_sha256"]
    )
    r2 = _verify_embedded_r2(source_path)
    checks["r2_standalone_verifier"] = (
        r2.get("manifest_sha256") == source["manifest_sha256"]
        and r2.get("zip_entries") == source["zip_entries"]
        and r2.get("matrix_rows_passed") == 37
    )

    ba3_path = ROOT / "research_agent/semantic_compiler/source_frontend/contracts.py"
    checks["ba3_contract"] = _sha(ba3_path) == "c37dd7847905f9113e5b50af9ba669cebf06f1520c2099de65cb5e4ce16fda2b"
    semantic = _run_json(
        [sys.executable, "scripts/ops/verify_semantic_compiler_wave_freeze.py", "--product-repo", str(product_repo), "--json"],
        ROOT,
    )
    ba10 = _run_json(
        [sys.executable, "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(product_repo), "--json"],
        ROOT,
    )
    ba11 = _run_json(
        [sys.executable, "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"], ROOT
    )
    rfc8 = _run_json(
        [sys.executable, "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--product-repo", str(product_repo), "--json"],
        ROOT,
    )
    rfc9 = _run_json(
        [sys.executable, "scripts/ops/verify_rfc0009_native_trust_freeze.py", "--product-repo", str(product_repo), "--json"],
        ROOT,
    )
    checks["semantic_wave_freeze"] = semantic.get("version_lock_sha256") == record["semantic_wave_v1_lock"]
    checks["ba10_freeze"] = ba10.get("freeze_lock_sha256") == record["ba10_freeze_sha256"]
    checks["ba11_freeze"] = ba11.get("freeze_sha256") == record["ba11_freeze_sha256"]
    checks["rfc0008_freeze"] = rfc8.get("freeze_sha256") == record["rfc0008_freeze_sha256"]
    checks["rfc0009_freeze"] = rfc9.get("freeze_sha256") == record["rfc0009_freeze_sha256"]
    boundary = record["foreign_boundary"]
    checks["foreign_boundary_binding"] = (
        acceptance.get("boundary", {}).get("snapshot_sha256")
        == boundary["accepted_r2_snapshot_sha256"]
        and acceptance.get("boundary", {}).get("previous_stop_sha256")
        == boundary["previous_stop_sha256"]
        and acceptance.get("boundary", {}).get("foreign_mutation_commands") == []
        and boundary.get("foreign_mutation_commands") == []
    )
    checks["final_status"] = (
        record.get("rfc0010_independent_rereview") == "ACCEPTED"
        and record.get("rfc0010_implementation_ready") is True
        and record.get("rfc0010_frozen") is True
        and record.get("ba12_resume_authorized") is True
        and record.get("release_authorized") is False
        and record.get("publication_authorized") is False
        and record.get("deploy_authorized") is False
    )
    failed = sorted(key for key, value in checks.items() if not value)
    return {
        "ba12_resume_authorized": record.get("ba12_resume_authorized"),
        "checks": checks,
        "contract_id": "room16.rfc0010.live_capture_transport_freeze_verification@1",
        "deploy_authorized": record.get("deploy_authorized"),
        "failed_checks": failed,
        "freeze_sha256": record.get("freeze_sha256"),
        "handoff_failures": handoff_failures,
        "publication_authorized": record.get("publication_authorized"),
        "release_authorized": record.get("release_authorized"),
        "rfc0010_frozen": record.get("rfc0010_frozen"),
        "runtime_file_failures": runtime_failures,
        "status": "PASS" if not failed else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--product-repo", type=Path, default=DEFAULT_PRODUCT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(
            args.record.resolve(),
            args.acceptance.resolve(),
            args.handoff.resolve(),
            args.product_repo.resolve(),
        )
    except Exception as exc:
        result = {
            "contract_id": "room16.rfc0010.live_capture_transport_freeze_verification@1",
            "error": f"{type(exc).__name__}:{exc}",
            "status": "FAIL",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
