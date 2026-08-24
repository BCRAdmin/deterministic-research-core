#!/usr/bin/env python3
"""Fail-closed verifier for the accepted RFC-0009 native trust freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRODUCT = ROOT.parent / "company-dossier-lab"
DEFAULT_RECORD = ROOT / "docs/compiler_foundation/freezes/RFC0009_BA12_NATIVE_TRUST_EPOCH2_FREEZE_v1.json"
DEFAULT_ACCEPTANCE = ROOT / "docs/compiler_foundation/acceptance/RFC0009_R2_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
DEFAULT_HANDOFF = Path("/Users/BjornRosinger/Downloads/ROOM16_RFC0009_ACCEPTANCE_FREEZE_AND_BA12_FINAL_RESUME_EXECUTION_R1_B523B123796E_2026-08-24.zip")


class RFC0009FreezeError(RuntimeError):
    """Stable fail-closed RFC-0009 freeze diagnostic."""


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RFC0009FreezeError(f"json_object_required:{path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _ancestor(repo: Path, commit: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=repo).returncode == 0


def freeze_sha256(record: dict[str, Any]) -> str:
    body = dict(record)
    body.pop("freeze_sha256", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(str(record["freeze_hash_domain"]).encode() + b"\0" + canonical).hexdigest()


def _run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if process.returncode:
        raise RFC0009FreezeError(f"command_failed:{' '.join(command)}:{process.stdout}:{process.stderr}")
    value = json.loads(process.stdout)
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise RFC0009FreezeError(f"command_status_not_pass:{' '.join(command)}")
    return value


def _handoff(record: dict[str, Any], handoff: Path, acceptance: Path) -> tuple[bool, list[str]]:
    failures: list[str] = []
    expected = record["handoff"]
    if not handoff.is_file() or handoff.name != expected["filename"] or handoff.stat().st_size != expected["bytes"] or _sha(handoff) != expected["sha256"]:
        return False, ["handoff_identity"]
    try:
        with zipfile.ZipFile(handoff) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != expected["zip_entries"]:
                failures.append("handoff_zip")
            if archive.read("01_EXTERNAL_INDEPENDENT_RFC0009_ACCEPTANCE.json") != acceptance.read_bytes():
                failures.append("acceptance_not_byte_exact")
            sums = {}
            for line in archive.read("SHA256SUMS.txt").decode().splitlines():
                digest, name = line.split("  ", 1)
                sums[name] = digest
            for name, digest in sums.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    failures.append(f"handoff_member:{name}")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        failures.append(f"handoff_exception:{type(exc).__name__}")
    return not failures, failures


def verify(record_path: Path, acceptance_path: Path, handoff_path: Path, product_repo: Path) -> dict[str, Any]:
    record = _json(record_path)
    acceptance = _json(acceptance_path)
    checks: dict[str, bool] = {}
    checks["freeze_contract"] = record.get("contract_id") == "room16.rfc0009.ba12_native_trust_epoch2_freeze" and record.get("schema_version") == 1 and record.get("status") == "accepted_frozen"
    checks["freeze_self_hash"] = record.get("freeze_sha256") == freeze_sha256(record)
    accepted = record["external_independent_acceptance"]
    checks["external_acceptance"] = _sha(acceptance_path) == accepted["file_sha256"] and acceptance.get("verdict") == "ACCEPTED" and acceptance.get("remaining_blocking_findings") == 0 and acceptance.get("acceptance_receipt_sha256") == accepted["acceptance_receipt_sha256"]
    handoff_ok, handoff_failures = _handoff(record, handoff_path, acceptance_path)
    checks["handoff_integrity"] = handoff_ok

    rb = record["git_bindings"]["research"]
    pb = record["git_bindings"]["product"]
    checks["research_identity"] = _git(ROOT, "remote", "get-url", "origin") == rb["remote"] and _git(ROOT, "branch", "--show-current") == rb["branch"] and _git(ROOT, "rev-parse", f"{rb['implementation_commit']}^{{tree}}") == rb["implementation_tree"] and _git(ROOT, "rev-parse", f"{rb['evidence_commit']}^{{tree}}") == rb["evidence_tree"] and _ancestor(ROOT, rb["implementation_commit"]) and _ancestor(ROOT, rb["evidence_commit"])
    checks["product_identity"] = _git(product_repo, "remote", "get-url", "origin") == pb["remote"] and _git(product_repo, "branch", "--show-current") == pb["branch"] and _git(product_repo, "rev-parse", f"{pb['implementation_commit']}^{{tree}}") == pb["implementation_tree"] and _ancestor(product_repo, pb["implementation_commit"])

    protected_failures: list[str] = []
    for repo_name, repo in (("research", ROOT), ("product", product_repo)):
        for item in record["protected_files"][repo_name]:
            path = repo / item["path"]
            if not path.is_file() or _sha(path) != item["sha256"]:
                protected_failures.append(f"{repo_name}:{item['path']}")
    checks["frozen_files_exact"] = not protected_failures

    r2 = record["source_r2"]
    r2_path = ROOT / r2["package_path"]
    checks["r2_package_identity"] = r2_path.is_file() and r2_path.stat().st_size == r2["bytes"] and _sha(r2_path) == r2["package_sha256"]
    r2_result = _run_json([sys.executable, r2["verifier_path"], str(r2_path)], ROOT)
    checks["r2_standalone_verifier"] = r2_result.get("manifest_sha256") == r2["manifest_sha256"] and r2_result.get("zip_entries") == r2["zip_entries"] and r2_result.get("matrix_rows_passed") == 38

    from research_agent.productization_v2.native_trust import load_native_trust, verify_native_bundle_v2
    trust = load_native_trust()
    bindings = record["native_trust_bindings"]
    checks["native_trust_bindings"] = trust["root"]["root_sha256"] == bindings["trust_root_sha256"] and trust["gen1"]["envelope_sha256"] == bindings["gen1_consumer_envelope_sha256"] and trust["gen2"]["envelope_sha256"] == bindings["gen2_consumer_envelope_sha256"] and trust["policy"].policy_sha256 == bindings["gen2_consumer_policy_sha256"] and trust["native_profile"]["profile_sha256"] == bindings["native_schema_profile_sha256"] and trust["emitter_profile"]["profile_sha256"] == bindings["native_emitter_profile_sha256"] and trust["key_policy"].policy_sha256 == bindings["leaf_key_policy_sha256"]
    receipts = []
    for fixture in ("rfc0009-native-probe", "rfc0009-native-probe-alt"):
        root = ROOT / "research_agent/tests/fixtures" / fixture
        receipt = _json(root / "RECEIPT.json")
        verified = verify_native_bundle_v2(root, receipt=receipt)
        verified["implementation_sha256"] = _json(root / "BUNDLE_MANIFEST.json")["emitter_identity"]["implementation_sha256"]
        receipts.append(verified)
    checks["dynamic_emitter_rule"] = record["emitter_freeze"].get("implementation_sha256_rule") == "required_64_hex_dynamic" and "implementation_sha256" not in record["emitter_freeze"] and len({row["implementation_sha256"] for row in receipts}) == 2
    checks["dynamic_boolean_rules"] = set(record["state_boolean_rules"].values()) == {"strict_boolean_dynamic"} and record["eligibility_freeze"]["compile_allowed_type"] == "strict_boolean_dynamic" and record["eligibility_freeze"]["renderer_eligible_type"] == "strict_boolean_dynamic"

    ba10 = _run_json([sys.executable, "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py", "--product-repo", str(product_repo), "--json"], ROOT)
    ba11 = _run_json([sys.executable, "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"], ROOT)
    rfc8 = _run_json([sys.executable, "scripts/ops/verify_rfc0008_v2_trust_freeze.py", "--product-repo", str(product_repo), "--json"], ROOT)
    checks["ba10_freeze"] = ba10.get("freeze_lock_sha256") == record["ba10_freeze_sha256"]
    checks["ba11_freeze"] = ba11.get("freeze_sha256") == record["ba11_freeze_sha256"]
    checks["rfc0008_freeze"] = rfc8.get("freeze_sha256") == record["rfc0008_freeze_sha256"]
    checks["final_status"] = record.get("rfc0009_independent_rereview") == "ACCEPTED" and record.get("rfc0009_implementation_ready") is True and record.get("rfc0009_frozen") is True and record.get("ba12_resume_authorized") is True and record.get("release_authorized") is False and record.get("publication_authorized") is False and record.get("deploy_authorized") is False
    failed = sorted(key for key, value in checks.items() if not value)
    return {"contract_id": "room16.rfc0009.native_trust_freeze_verification@1", "status": "PASS" if not failed else "FAIL", "freeze_sha256": record.get("freeze_sha256"), "checks": checks, "failed_checks": failed, "handoff_failures": handoff_failures, "protected_file_failures": protected_failures, "rfc0009_frozen": record.get("rfc0009_frozen"), "ba12_resume_authorized": record.get("ba12_resume_authorized"), "release_authorized": record.get("release_authorized"), "publication_authorized": record.get("publication_authorized"), "deploy_authorized": record.get("deploy_authorized")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--acceptance", type=Path, default=DEFAULT_ACCEPTANCE)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--product-repo", type=Path, default=DEFAULT_PRODUCT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(args.record.resolve(), args.acceptance.resolve(), args.handoff.resolve(), args.product_repo.resolve())
    except Exception as exc:
        result = {"contract_id": "room16.rfc0009.native_trust_freeze_verification@1", "status": "FAIL", "error": f"{type(exc).__name__}:{exc}"}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
