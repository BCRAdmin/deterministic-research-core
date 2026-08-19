#!/usr/bin/env python3
"""Fail-closed BA11 governance verifier for contracts, schemas and BA10 freeze."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from research_agent.canary_governance.contracts import CONTRACT_MODELS
from research_agent.compiler_foundation.canonical import sha256_json

ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> dict:
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return {
        "command": command,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-repo", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks = {}
    schema_root = ROOT / "research_agent/canary_governance/schemas"
    catalog_path = schema_root / "contract_catalog_v1.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_body = {key: value for key, value in catalog.items() if key != "catalog_sha256"}
    expected_ids = {model.model_fields["contract_id"].default for model in CONTRACT_MODELS}
    checks["contract_catalog_complete"] = {
        "pass": {item["contract_id"] for item in catalog["contracts"]} == expected_ids,
        "count": len(catalog["contracts"]),
    }
    checks["contract_catalog_hash"] = {
        "pass": catalog.get("catalog_sha256") == sha256_json(catalog_body),
        "actual": catalog.get("catalog_sha256"),
    }
    schema_errors = []
    for item in catalog["contracts"]:
        path = schema_root / item["schema_file"]
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            schema_errors.append(f"{path.name}:{exc}")
            continue
        if document.get("additionalProperties") is not False:
            schema_errors.append(f"{path.name}:unknown_fields_not_blocked")
        if sha256(path) != item.get("schema_file_sha256"):
            schema_errors.append(f"{path.name}:catalog_hash_mismatch")
        required_catalog_fields = {
            "authority_owner", "canonicalization_profile", "contract_id", "diagnostics",
            "hash_domain", "hash_excluded_fields", "hash_preimage_fields",
            "negative_fixture_refs", "positive_fixture_refs", "schema_file",
            "schema_file_sha256", "schema_version", "unknown_field_policy",
        }
        if not required_catalog_fields <= set(item):
            schema_errors.append(f"{path.name}:catalog_fields_incomplete")
    checks["schemas_strict"] = {"pass": not schema_errors, "errors": schema_errors}
    ba10 = run(
        [
            str(ROOT / ".venv/bin/python"),
            str(ROOT / "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py"),
            "--product-repo",
            str(args.product_repo),
            "--json",
        ]
    )
    checks["ba10_freeze_unchanged"] = {"pass": ba10["exit_code"] == 0, "receipt": ba10}
    tests = run(
        [
            str(ROOT / ".venv/bin/python"),
            "-m",
            "pytest",
            "research_agent/tests/test_canary_governance.py",
            "-q",
        ]
    )
    checks["ba11_tests"] = {"pass": tests["exit_code"] == 0, "receipt": tests}
    # The shared run helper uses the Research cwd; execute Product explicitly.
    process = subprocess.run(
        ["node", "--test", "scripts/test_canary_registry_mirror.mjs"],
        cwd=args.product_repo / "room16-app",
        capture_output=True,
        text=True,
    )
    product_tests = {
        "command": ["node", "--test", "scripts/test_canary_registry_mirror.mjs"],
        "cwd": str(args.product_repo / "room16-app"),
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    checks["product_trust_anchor_tests"] = {
        "pass": product_tests["exit_code"] == 0,
        "receipt": product_tests,
    }
    result = {
        "contract_id": "room16.ba11_canary_governance_verifier@1",
        "status": "PASS" if all(item["pass"] for item in checks.values()) else "FAIL",
        "checks": checks,
        "source_state": {
            "research_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
            ).stdout.strip(),
            "product_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=args.product_repo, check=True, capture_output=True, text=True
            ).stdout.strip(),
            "catalog_file_sha256": sha256(catalog_path),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
