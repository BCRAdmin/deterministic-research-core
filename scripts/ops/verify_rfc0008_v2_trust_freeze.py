#!/usr/bin/env python3
"""Fail-closed verifier for the accepted RFC-0008 Bundle@2 trust freeze."""

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
DEFAULT_RECORD = (
    ROOT
    / "docs/compiler_foundation/freezes/"
    "RFC0008_COMPILER_ARTIFACT_BUNDLE_V2_TRUST_FREEZE_v1.json"
)
DEFAULT_ACCEPTANCE = (
    ROOT
    / "docs/compiler_foundation/acceptance/"
    "RFC0008_R2_EXTERNAL_INDEPENDENT_ACCEPTANCE.json"
)
HISTORICAL_INPUT_ROOT = Path(
    os.environ.get("ROOM16_HISTORICAL_REGRESSION_INPUT_ROOT", "/Users/BjornRosinger/Downloads")
)
DEFAULT_HANDOFF = HISTORICAL_INPUT_ROOT / (
    "ROOM16_RFC0008_ACCEPTANCE_FREEZE_AND_BA12_RESUME_EXECUTION_R1_"
    "2A718E7656C6_2026-08-22.zip"
)


class RFC0008FreezeError(RuntimeError):
    """Raised when an RFC-0008 freeze dependency is invalid."""


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RFC0008FreezeError(f"json_object_required:{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def freeze_sha256(record: dict[str, Any]) -> str:
    body = dict(record)
    body.pop("freeze_sha256", None)
    domain = str(record["freeze_hash_domain"]).encode("utf-8")
    return hashlib.sha256(domain + b"\0" + _canonical_bytes(body)).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _is_ancestor(repo: Path, commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=repo,
            capture_output=True,
        ).returncode
        == 0
    )


def _run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if process.returncode:
        raise RFC0008FreezeError(
            f"command_failed:{' '.join(command)}:{process.stdout}:{process.stderr}"
        )
    try:
        value = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RFC0008FreezeError(f"command_json_invalid:{' '.join(command)}") from exc
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise RFC0008FreezeError(f"command_status_not_pass:{' '.join(command)}")
    return value


def _protected_files(
    record: dict[str, Any], product_repo: Path
) -> tuple[bool, list[str]]:
    failed: list[str] = []
    for repo_name, repo in (("research", ROOT), ("product", product_repo)):
        for item in record["protected_files"][repo_name]:
            path = repo / item["path"]
            if not path.is_file() or _sha256(path) != item["sha256"]:
                failed.append(f"{repo_name}:{item['path']}")
    return not failed, failed


def _verify_handoff(
    record: dict[str, Any], handoff: Path, acceptance_path: Path
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    expected = record["handoff"]
    if (
        not handoff.is_file()
        or handoff.name != expected["filename"]
        or handoff.stat().st_size != expected["bytes"]
        or _sha256(handoff) != expected["sha256"]
    ):
        return False, ["handoff_identity"]
    try:
        with zipfile.ZipFile(handoff) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != expected["zip_entries"]:
                failures.append("handoff_zip")
            if (
                archive.read("01_EXTERNAL_INDEPENDENT_RFC0008_ACCEPTANCE.json")
                != acceptance_path.read_bytes()
            ):
                failures.append("acceptance_not_byte_exact")
            if hashlib.sha256(
                archive.read(
                    "authority/ROOM16_RFC0008_V2_TRUST_MIGRATION_R2_"
                    "939AF5294285_2026-08-21.zip"
                )
            ).hexdigest() != record["source_r2"]["package_sha256"]:
                failures.append("embedded_r2_hash")
            sums: dict[str, str] = {}
            for line in archive.read("SHA256SUMS.txt").decode("utf-8").splitlines():
                digest, name = line.split("  ", 1)
                sums[name] = digest
            for name, digest in sums.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    failures.append(f"handoff_member:{name}")
    except (OSError, zipfile.BadZipFile, KeyError, ValueError) as exc:
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
        record.get("contract_id")
        == "room16.rfc0008.compiler_artifact_bundle_v2_trust_freeze"
        and record.get("schema_version") == 1
        and record.get("status") == "accepted_frozen"
        and record.get("bundle_contract") == "room16.compiler_artifact_bundle@2"
        and record.get("bundle_schema") == "2.0.0"
    )
    checks["freeze_self_hash"] = record.get("freeze_sha256") == freeze_sha256(record)

    accepted = record["external_independent_acceptance"]
    checks["external_acceptance"] = (
        _sha256(acceptance_path) == accepted["file_sha256"]
        and acceptance.get("contract_id")
        == "room16.rfc0008.r2.external_independent_acceptance@1"
        and acceptance.get("verdict") == "ACCEPTED"
        and acceptance.get("remaining_blocking_findings") == 0
        and acceptance.get("acceptance_receipt_sha256")
        == accepted["acceptance_receipt_sha256"]
    )

    handoff_ok, handoff_failures = _verify_handoff(record, handoff_path, acceptance_path)
    checks["handoff_integrity"] = handoff_ok

    research_binding = record["git_bindings"]["research"]
    product_binding = record["git_bindings"]["product"]
    checks["research_identity"] = (
        _git(ROOT, "remote", "get-url", "origin") == research_binding["remote"]
        and _git(ROOT, "branch", "--show-current") == research_binding["branch"]
        and _git(
            ROOT,
            "rev-parse",
            f"{research_binding['implementation_commit']}^{{tree}}",
        )
        == research_binding["implementation_tree"]
        and _git(ROOT, "rev-parse", f"{research_binding['evidence_commit']}^{{tree}}")
        == research_binding["evidence_tree"]
        and _is_ancestor(ROOT, research_binding["implementation_commit"])
        and _is_ancestor(ROOT, research_binding["evidence_commit"])
    )
    checks["product_identity"] = (
        _git(product_repo, "remote", "get-url", "origin")
        == product_binding["remote"]
        and _git(product_repo, "branch", "--show-current") == product_binding["branch"]
        and _git(
            product_repo,
            "rev-parse",
            f"{product_binding['implementation_commit']}^{{tree}}",
        )
        == product_binding["implementation_tree"]
        and _is_ancestor(product_repo, product_binding["implementation_commit"])
    )

    protected_ok, protected_failures = _protected_files(record, product_repo)
    checks["frozen_files_exact"] = protected_ok

    trust_root = _json(ROOT / "research_agent/productization_v2/config/trust_root_v2.json")
    consumer = _json(
        ROOT / "research_agent/productization_v2/config/consumer_policy_envelope_v2.json"
    )
    key_policy = _json(
        ROOT
        / "research_agent/productization_v2/config/public_key_policy_envelope_v2.json"
    )
    schema = _json(
        ROOT / "research_agent/productization_v2/config/manifest_schema_profile_v2.json"
    )
    bindings = record["trust_bindings"]
    checks["trust_bindings"] = (
        trust_root.get("root_sha256") == bindings["trust_root_sha256"]
        and trust_root.get("root_public_key_hex") == bindings["root_public_key_hex"]
        and consumer.get("envelope_sha256")
        == bindings["consumer_policy_envelope_sha256"]
        and key_policy.get("envelope_sha256")
        == bindings["key_policy_envelope_sha256"]
        and schema.get("profile_sha256") == record["schema_profile_sha256"]
        and consumer.get("generation") == 1
        and key_policy.get("generation") == 1
    )

    catalog = _json(
        ROOT / "research_agent/productization_v2/config/migration_canary_catalog_v2.json"
    )
    actual_canaries = {row["ticker"]: row for row in catalog["canaries"]}
    checks["migration_canaries"] = all(
        actual_canaries.get(ticker, {}).get("v2_bundle_sha256")
        == expected["v2_bundle_sha256"]
        and actual_canaries.get(ticker, {}).get("receipt_file_sha256")
        == expected["receipt_file_sha256"]
        for ticker, expected in record["migration_canaries"].items()
    )

    r2_path = ROOT / record["source_r2"]["package_path"]
    checks["r2_package_identity"] = (
        r2_path.is_file()
        and r2_path.stat().st_size == record["source_r2"]["bytes"]
        and _sha256(r2_path) == record["source_r2"]["package_sha256"]
    )
    r2_receipt = _run_json(
        [sys.executable, record["source_r2"]["verifier_path"], str(r2_path)], ROOT
    )
    checks["r2_standalone_verifier"] = (
        r2_receipt.get("manifest_sha256") == record["source_r2"]["manifest_sha256"]
        and r2_receipt.get("payload_count") == 78
        and r2_receipt.get("private_key_material_present") is False
    )

    ba10 = _run_json(
        [
            sys.executable,
            "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
            "--product-repo",
            str(product_repo),
            "--json",
        ],
        ROOT,
    )
    ba11 = _run_json(
        [sys.executable, "scripts/ops/verify_ba11_canary_governance_freeze.py", "--json"],
        ROOT,
    )
    checks["ba10_freeze"] = (
        ba10.get("freeze_lock_sha256") == record["ba10_v1_freeze_sha256"]
        and ba10.get("ba10_frozen") is True
    )
    checks["ba11_freeze"] = (
        ba11.get("freeze_sha256") == record["ba11_freeze_sha256"]
        and ba11.get("ba11_frozen") is True
    )

    tracked = _git(ROOT, "ls-files").splitlines() + _git(product_repo, "ls-files").splitlines()
    checks["private_keys_absent"] = not any(
        "root_signing_key" in path or "signing_key_ed25519.bin" in path for path in tracked
    ) and r2_receipt.get("private_key_material_present") is False

    semantics = record["freeze_semantics"]
    checks["final_status"] = (
        all(semantics.values())
        and record.get("rfc0008_implementation_ready") is True
        and record.get("rfc0008_frozen") is True
        and record.get("ba12_resume_authorized") is True
        and record.get("release_authorized") is False
        and record.get("publication_authorized") is False
        and record.get("deploy_authorized") is False
    )

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "contract_id": "room16.rfc0008.v2_trust_freeze_verification",
        "schema_version": 1,
        "status": "PASS" if not failed else "FAIL",
        "freeze_sha256": record.get("freeze_sha256"),
        "checks": checks,
        "failed_checks": failed,
        "handoff_failures": handoff_failures,
        "protected_file_failures": protected_failures,
        "rfc0008_frozen": record.get("rfc0008_frozen"),
        "ba12_resume_authorized": record.get("ba12_resume_authorized"),
        "release_authorized": record.get("release_authorized"),
        "publication_authorized": record.get("publication_authorized"),
        "deploy_authorized": record.get("deploy_authorized"),
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
    except (OSError, KeyError, ValueError, RFC0008FreezeError) as exc:
        result = {
            "contract_id": "room16.rfc0008.v2_trust_freeze_verification",
            "schema_version": 1,
            "status": "FAIL",
            "error": str(exc),
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
