#!/usr/bin/env python3
"""Fail-closed verifier for the accepted Room16 BA10 v1 freeze."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization.contracts import CompilerArtifactBundleManifest


RESEARCH_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORD = (
    RESEARCH_ROOT
    / "research_agent/productization/freeze/ba10_artifact_abi_renderer_freeze_v1.json"
)


class BA10FreezeError(RuntimeError):
    """Raised when any accepted BA10 freeze coordinate differs."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _is_ancestor(repo: Path, ancestor: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, "HEAD"],
        cwd=repo,
        capture_output=True,
    ).returncode == 0


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BA10FreezeError(f"json_object_required:{path}")
    return value


def _run_freeze_verifier(script: str, product_repo: Path) -> bool:
    command = [sys.executable, str(RESEARCH_ROOT / script)]
    if script.endswith("verify_compiler_foundation_freeze.py") or script.endswith(
        "verify_semantic_compiler_wave_freeze.py"
    ):
        command.extend(["--product-repo", str(product_repo)])
    if script.endswith("verify_semantic_compiler_wave_freeze.py"):
        command.append("--json")
    process = subprocess.run(
        command,
        cwd=RESEARCH_ROOT,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise BA10FreezeError(
            f"upstream_freeze_verifier_failed:{script}:{process.stdout}:{process.stderr}"
        )
    payload = json.loads(process.stdout)
    return str(payload.get("status", "")).lower() == "pass"


def _verify_self_hash(document: dict[str, Any], key: str, expected: str) -> bool:
    body = dict(document)
    body.pop(key, None)
    return sha256_json(body) == expected


def verify(record_path: Path, product_repo: Path) -> dict[str, Any]:
    record = _read_json(record_path)
    checks: dict[str, bool] = {}

    checks["freeze_record_contract"] = (
        record.get("contract_id")
        == "room16.compiler.ba10_artifact_abi_renderer_freeze_record"
        and record.get("contract_version") == 1
        and record.get("status") == "accepted_frozen"
        and record.get("freeze_version") == "1.0.0"
    )
    acceptance = record["independent_acceptance"]
    checks["r3_independent_acceptance"] = (
        acceptance.get("status") == "pass"
        and acceptance.get("rfc_0005_accepted") is True
        and acceptance.get("rfc_0005_r3_accepted") is True
        and acceptance.get("closed_findings")
        == [
            "BA10-R2-AR-001",
            "BA10-R2-AR-002",
            "BA10-R2-AR-003",
            "BA10-R2-AR-004",
        ]
    )

    git = record["git"]
    tag = git["tag"]
    checks["ba10_tag_is_annotated"] = _git(RESEARCH_ROOT, "cat-file", "-t", tag) == "tag"
    checks["ba10_tag_object"] = _git(RESEARCH_ROOT, "rev-parse", tag) == git["tag_object"]
    checks["ba10_tag_target"] = (
        _git(RESEARCH_ROOT, "rev-parse", f"{tag}^{{}}") == git["research_commit"]
    )
    checks["research_commit_exists"] = (
        _git(RESEARCH_ROOT, "cat-file", "-t", git["research_commit"]) == "commit"
        and _is_ancestor(RESEARCH_ROOT, git["research_commit"])
    )
    checks["product_commit_exists"] = (
        _git(product_repo, "cat-file", "-t", git["product_commit"]) == "commit"
        and _is_ancestor(product_repo, git["product_commit"])
    )

    versions = record["versions"]
    checks["foundation_freeze_verifier"] = _run_freeze_verifier(
        "scripts/ops/verify_compiler_foundation_freeze.py", product_repo
    )
    checks["registry_freeze_verifier"] = _run_freeze_verifier(
        "scripts/ops/verify_registry_foundation_freeze.py", product_repo
    )
    checks["semantic_wave_freeze_verifier"] = _run_freeze_verifier(
        "scripts/ops/verify_semantic_compiler_wave_freeze.py", product_repo
    )

    foundation = _read_json(RESEARCH_ROOT / record["foundation"]["manifest_path"])
    checks["foundation_lock"] = (
        versions["compiler_foundation"] == "1.0.0"
        and foundation.get("compiler_foundation_version") == "1.0.0"
        and foundation.get("version_lock_sha256")
        == record["foundation"]["version_lock_sha256"]
        and _sha256(RESEARCH_ROOT / record["foundation"]["manifest_path"])
        == record["foundation"]["manifest_file_sha256"]
        and record["foundation"]["unchanged"] is True
    )
    registry = _read_json(RESEARCH_ROOT / record["registry"]["manifest_path"])
    checks["registry_lock"] = (
        versions["registry_foundation"] == "1.1.0"
        and registry.get("registry_foundation_version") == "1.1.0"
        and registry.get("authority", {}).get("authority_sha256")
        == record["registry"]["authority_sha256"]
        and _sha256(RESEARCH_ROOT / record["registry"]["manifest_path"])
        == record["registry"]["manifest_file_sha256"]
        and record["registry"]["unchanged"] is True
    )
    semantic = _read_json(RESEARCH_ROOT / record["semantic_wave"]["freeze_record_path"])
    checks["semantic_wave_lock"] = (
        versions["semantic_compiler_wave"] == "1.0.0"
        and semantic.get("versions", {}).get("semantic_compiler_wave") == "1.0.0"
        and semantic.get("version_lock_sha256")
        == record["semantic_wave"]["version_lock_sha256"]
        and semantic.get("pass_manifest", {}).get("effective_pass_manifest_sha256")
        == record["semantic_wave"]["pass_manifest_sha256"]
        and semantic.get("ir_schema", {}).get("schema_set_sha256")
        == record["semantic_wave"]["ir_schema_set_sha256"]
        and record["semantic_wave"]["unchanged"] is True
    )

    abi = record["artifact_abi"]
    checks["artifact_abi_contract"] = (
        abi.get("public_contract") == "room16.compiler_artifact_bundle@1"
        and abi.get("contract_id") == "room16.compiler_artifact_bundle"
        and abi.get("contract_major") == 1
        and abi.get("schema_version") == "1.2.0"
        and CompilerArtifactBundleManifest.model_fields["contract_id"].default
        == "room16.compiler_artifact_bundle"
        and CompilerArtifactBundleManifest.model_fields["schema_version"].default == "1.2.0"
    )

    locks = record["locks"]
    documents: dict[str, dict[str, Any]] = {}
    for name, lock in locks.items():
        research_path = RESEARCH_ROOT / lock["research_path"]
        product_path = product_repo / lock["product_path"]
        checks[f"{name}_file_lock"] = (
            _sha256(research_path) == lock["file_sha256"]
            and _sha256(product_path) == lock["file_sha256"]
            and research_path.read_bytes() == product_path.read_bytes()
        )
        documents[name] = _read_json(research_path)

    policy = documents["consumer_policy"]
    checks["consumer_policy_lock"] = (
        policy.get("policy_sha256") == locks["consumer_policy"]["policy_sha256"]
        and _verify_self_hash(policy, "policy_sha256", policy["policy_sha256"])
        and policy.get("semantic_wave_version_lock")
        == record["semantic_wave"]["version_lock_sha256"]
        and policy.get("foundation_version") == "1.0.0"
        and policy.get("registry_foundation_version") == "1.1.0"
        and policy.get("schema_version_min") == "1.2.0"
        and policy.get("schema_version_max") == "1.2.0"
    )
    receipt_set = documents["receipt_set"]
    checks["receipt_set_lock"] = (
        receipt_set.get("receipt_set_sha256") == locks["receipt_set"]["receipt_set_sha256"]
        and _verify_self_hash(
            receipt_set, "receipt_set_sha256", receipt_set["receipt_set_sha256"]
        )
    )
    pass_profile = documents["pass_execution_profile"]
    expected_pass_ids = semantic["pass_manifest"]["pass_ids"]
    checks["exact_pass_execution_profile"] = (
        pass_profile.get("contract_id") == "room16.compiler.pass_execution_profile"
        and len(pass_profile.get("passes", [])) == locks["pass_execution_profile"]["pass_count"]
        and [item.get("ordinal") for item in pass_profile["passes"]] == list(range(4, 14))
        and [item.get("pass_id") for item in pass_profile["passes"]] == expected_pass_ids
        and all(item.get("pass_version") == 3 for item in pass_profile["passes"])
        and all(item.get("status") == "executed" for item in pass_profile["passes"])
    )
    artifact_profile = documents["required_artifact_profile"]
    artifact_entries = artifact_profile.get("entries", [])
    bridge_entries = [
        item for item in artifact_entries if item.get("artifact_kind") == "authority_v3_bridge"
    ]
    checks["required_artifact_profile"] = (
        artifact_profile.get("contract_id") == "room16.compiler.required_artifact_profile"
        and len(artifact_entries)
        == locks["required_artifact_profile"]["required_artifact_kind_count"]
        and len(bridge_entries) == 1
        and bridge_entries[0].get("authoritative") is False
        and bridge_entries[0].get("compatibility_only") is True
        and bridge_entries[0].get("compatibility_rule")
        == "byte_identical_compatibility_view"
    )

    boundary = record["authority_v3_compatibility_boundary"]
    checks["authority_v3_compatibility_boundary"] = (
        versions["authority_bundle"] == 3
        and boundary.get("authority_bundle_contract_version") == 3
        and boundary.get("direction")
        == "compiler_artifact_bundle_to_authority_v3_compatibility_view"
        and boundary.get("inverse_authority_allowed") is False
        and boundary.get("compatibility_only") is True
        and boundary.get("unchanged") is True
        and policy.get("authority_bundle_contract_version") == 3
        and policy.get("bridge_contract_id") == "room16.authority_v3_compatibility_view"
    )

    for relative, expected in record["frozen_source_files"]["research"].items():
        checks[f"research_source:{relative}"] = _sha256(RESEARCH_ROOT / relative) == expected
    for relative, expected in record["frozen_source_files"]["product"].items():
        checks[f"product_source:{relative}"] = _sha256(product_repo / relative) == expected

    evidence_path = RESEARCH_ROOT / record["accepted_evidence"]["archive"]
    checks["accepted_r3_evidence_archive"] = (
        evidence_path.is_file()
        and _sha256(evidence_path) == record["accepted_evidence"]["archive_sha256"]
    )
    with zipfile.ZipFile(evidence_path) as evidence:
        verdict = json.loads(
            evidence.read(record["accepted_evidence"]["machine_verdict_path"])
        )
        replay = json.loads(
            evidence.read(record["accepted_evidence"]["replay_results_path"])
        )
        trust_scan = json.loads(evidence.read("PRODUCTION_TRUST_API_SCAN.json"))
        checks["r3_machine_verdict"] = (
            verdict.get("ba10_final_acceptance_candidate") is True
            and verdict.get("ba10_r2_ar_001_closed") is True
            and verdict.get("ba10_r2_ar_002_closed") is True
            and verdict.get("ba10_r2_ar_003_closed") is True
            and verdict.get("ba10_r2_ar_004_closed") is True
            and verdict.get("full_unskipped_regression_passed") is True
            and verdict.get("release_ready") is False
            and verdict.get("publication_allowed") is False
            and verdict.get("ba11_authorized") is False
            and verdict.get("ba12_authorized") is False
        )
        checks["production_trust_api_closure"] = (
            trust_scan.get("status") == "PASS"
            and trust_scan.get("alternative_trust_argument_calls") == 0
        )
        receipt_bundles = {
            item["compile_identity"]["ticker"]: item["bundle_sha256"]
            for item in receipt_set["receipts"]
        }
        baseline = _read_json(product_repo / record["canaries"]["product_baseline_path"])
        checks["canary_baseline_file"] = (
            _sha256(product_repo / record["canaries"]["product_baseline_path"])
            == record["canaries"]["product_baseline_file_sha256"]
        )
        for ticker in ("WM", "COST", "ABT"):
            canary = record["canaries"][ticker]
            checks[f"{ticker}_source_hash"] = (
                _sha256(product_repo / canary["source_archive_path"])
                == canary["source_sha256"]
                and baseline["candidate_sha256"][ticker] == canary["source_sha256"]
                and replay[ticker]["source_canary_sha256"] == canary["source_sha256"]
            )
            checks[f"{ticker}_bundle_hash"] = (
                replay[ticker]["bundle_sha256"] == canary["accepted_bundle_sha256"]
                and replay[ticker]["bundle_zip_sha256"]
                == canary["accepted_bundle_zip_sha256"]
                and receipt_bundles[ticker] == canary["accepted_bundle_sha256"]
            )
            checks[f"{ticker}_renderer_acceptance"] = (
                replay[ticker]["rendered_artifact_set_accepted"] is True
                and replay[ticker]["rendered_zip_sha256"]
                == canary["accepted_renderer_zip_sha256"]
                and canary["renderer_accepted"] is True
            )
            bundle_zip = evidence.read(
                f"NESTED_BUNDLES/{ticker}_COMPILER_ARTIFACT_BUNDLE.zip"
            )
            renderer_zip = evidence.read(
                f"NESTED_RENDERED_ARTIFACTS/{ticker}_RENDERED_ARTIFACTS.zip"
            )
            checks[f"{ticker}_nested_bundle_zip"] = (
                _sha256_bytes(bundle_zip) == canary["accepted_bundle_zip_sha256"]
            )
            checks[f"{ticker}_nested_renderer_zip"] = (
                _sha256_bytes(renderer_zip) == canary["accepted_renderer_zip_sha256"]
            )
            with zipfile.ZipFile(io.BytesIO(bundle_zip)) as nested_bundle:
                manifest = json.loads(nested_bundle.read("BUNDLE_MANIFEST.json"))
                checks[f"{ticker}_nested_bundle_manifest"] = (
                    manifest.get("bundle_sha256") == canary["accepted_bundle_sha256"]
                )
            with zipfile.ZipFile(io.BytesIO(renderer_zip)) as nested_renderer:
                rendered = json.loads(nested_renderer.read("rendered_artifact_set.json"))
                checks[f"{ticker}_nested_renderer_truth_boundary"] = (
                    rendered.get("source_bundle_sha256") == canary["accepted_bundle_sha256"]
                    and rendered.get("renderer_generated_facts") == 0
                    and rendered.get("renderer_generated_claims") == 0
                    and rendered.get("renderer_generated_decisions") == 0
                    and rendered.get("no_new_truth_verified") is True
                    and rendered.get("release_ready") is False
                    and rendered.get("publication_allowed") is False
                )

    closures = record["closures"]
    checks["all_r3_closures"] = all(value is True for value in closures.values())
    migration = record["migration_state"]
    checks["truthful_migration_state"] = (
        migration.get("product_parallel_truth_removed_in_canonical_path") is True
        and migration.get("legacy_bridge_active") is True
        and migration.get("full_renderer_cutover") is False
        and migration.get("source_native_fact_generation") is False
        and policy.get("product_parallel_truth_removed_in_canonical_path") is True
        and policy.get("legacy_bridge_active") is True
        and policy.get("full_renderer_cutover") is False
        and policy.get("source_native_fact_generation") is False
    )
    flags = record["status_flags"]
    checks["frozen_status"] = all(
        flags.get(name) is True
        for name in (
            "ba10_frozen",
            "rfc_0005_accepted",
            "rfc_0005_r3_accepted",
            "artifact_bundle_v1_frozen",
            "renderer_truth_boundary_frozen",
            "product_consumer_boundary_frozen",
        )
    )
    checks["release_and_next_phases_closed"] = all(
        flags.get(name) is False
        for name in (
            "release_ready",
            "publication_allowed",
            "ba11_authorized",
            "ba12_authorized",
        )
    ) and all(
        policy.get(name) is False
        for name in (
            "release_ready",
            "publication_allowed",
            "ba11_authorized",
            "ba12_authorized",
        )
    )
    checks["freeze_rule"] = (
        record["freeze_rule"].get("rfc_required") is True
        and record["freeze_rule"].get("versioning_decision_required") is True
        and len(record["freeze_rule"].get("protected_surfaces", [])) == 6
    )
    checks["freeze_lock"] = (
        sha256_json(record["freeze_lock_inputs"]) == record["freeze_lock_sha256"]
    )

    failed = sorted(name for name, passed in checks.items() if not passed)
    return {
        "contract_id": "room16.compiler.ba10_artifact_abi_renderer_freeze_verification",
        "contract_version": 1,
        "status": "PASS" if not failed else "FAIL",
        "freeze_version": record["freeze_version"],
        "git_tag": tag,
        "tag_object": git["tag_object"],
        "tag_target": git["research_commit"],
        "product_commit": git["product_commit"],
        "freeze_lock_sha256": record["freeze_lock_sha256"],
        "checks": checks,
        "failed_checks": failed,
        "ba10_frozen": not failed,
        "ba11_authorized": False,
        "ba12_authorized": False,
        "release_ready": False,
        "publication_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument(
        "--product-repo",
        type=Path,
        default=RESEARCH_ROOT.parent / "company-dossier-lab",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(args.record.resolve(), args.product_repo.resolve())
    except (
        BA10FreezeError,
        KeyError,
        OSError,
        ValueError,
        zipfile.BadZipFile,
        subprocess.CalledProcessError,
    ) as exc:
        result = {
            "contract_id": "room16.compiler.ba10_artifact_abi_renderer_freeze_verification",
            "contract_version": 1,
            "status": "FAIL",
            "error": str(exc),
            "ba10_frozen": False,
            "ba11_authorized": False,
            "ba12_authorized": False,
            "release_ready": False,
            "publication_allowed": False,
        }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["status"])
        for name, passed in result.get("checks", {}).items():
            print(f"{'PASS' if passed else 'FAIL'} {name}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
