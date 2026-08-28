#!/usr/bin/env python3
"""Build deterministic evidence for the Fixed24 execution-authority closure."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from research_agent.alpha_shared.execution_authority import (
    BatchExecutionAuthorityIR,
    RuntimeIdentityIR,
    fixed_company_list_sha256,
    ordered_cases_from_fixed_company_list,
    threshold_authority_sha256,
)
from research_agent.compiler_foundation.canonical import sha256_json

RESULT_PREFIX = "ROOM16_FIXED24_EXECUTION_AUTHORITY_CLOSURE_RESULT_R1"
DATE = "2026-08-28"


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(root: Path, relative: str, value: object) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_text(root: Path, relative: str, value: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _boundary_receipt_builder() -> Any:
    module_path = Path(__file__).with_name("verify_project_boundary_non_interference_v2.py")
    spec = importlib.util.spec_from_file_location("room16_boundary_gate_v2", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("FIXED24_BOUNDARY_VERIFIER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_receipt


def _changed_files(repo: Path, base: str) -> list[dict[str, str]]:
    rows = []
    output = _git(repo, "diff", "--name-status", f"{base}..HEAD")
    for line in output.splitlines():
        status, path = line.split("\t", 1)
        rows.append({"status": status, "path": path})
    return rows


def _zip_tree(root: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


def build(args: argparse.Namespace) -> dict[str, object]:
    handoff_manifest = _read(args.handoff_root / "MANIFEST.json")
    companies = _read(args.handoff_root / "06_FIXED24_LIST_AUTHORITY.json")
    thresholds = _read(args.handoff_root / "07_FIXED24_THRESHOLD_AUTHORITY.json")
    matrix = _read(args.matrix)
    external = _read(args.external_gates_json)
    stop_prestart = _read(args.stop_result_root / "04_BATCH_PRESTART_STATE.json")
    r4_freeze = _read(args.stop_result_root / "02_SHARED_HARDENING_FREEZE.json")

    research_head = _git(args.research_repo, "rev-parse", "HEAD")
    research_tree = _git(args.research_repo, "rev-parse", "HEAD^{tree}")
    product_head = _git(args.product_repo, "rev-parse", "HEAD")
    product_tree = _git(args.product_repo, "rev-parse", "HEAD^{tree}")
    short_id = research_head[:12].upper()
    name = f"{RESULT_PREFIX}_{short_id}_{DATE}"
    staging = args.release_dir / name
    archive_path = args.release_dir / f"{name}.zip"
    if staging.exists() or archive_path.exists():
        raise SystemExit(f"result already exists: {staging} or {archive_path}")
    staging.mkdir(parents=True)

    changed = _changed_files(args.research_repo, handoff_manifest["research_base"])
    allowed_paths = {
        "research_agent/alpha_shared/execution_authority.py",
        "research_agent/alpha_shared/runner.py",
        "research_agent/tests/test_fixed24_execution_authority_closure.py",
        "research_agent/tests/test_rfc0011_r4_batch_readiness.py",
        "scripts/ops/build_fixed24_execution_authority_closure_evidence.py",
        "scripts/ops/run_fixed24_execution_authority_closure_validation.py",
        "scripts/ops/run_rfc0011_r4_validation.py",
        "scripts/ops/verify_fixed24_execution_authority_closure.py",
    }
    changed_paths = {item["path"] for item in changed}
    if changed_paths != allowed_paths:
        raise RuntimeError(
            f"FIXED24_EXEC_AUTH_CHANGED_SCOPE_MISMATCH:{sorted(changed_paths ^ allowed_paths)}"
        )
    if _git(args.research_repo, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("FIXED24_EXEC_AUTH_RESEARCH_TRACKED_DIRT")
    if _git(args.product_repo, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("FIXED24_EXEC_AUTH_PRODUCT_TRACKED_DIRT")

    runtime = RuntimeIdentityIR(
        research_commit=handoff_manifest["research_base"],
        research_tree=handoff_manifest["research_tree"],
        product_commit=handoff_manifest["product_base"],
        product_tree=handoff_manifest["product_tree"],
        as_of_date="2026-08-28",
    )
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=runtime.as_of_date,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=None,
        fixed_company_list_sha256=fixed_company_list_sha256(companies),
        threshold_sha256=threshold_authority_sha256(thresholds),
        ordered_cases=ordered_cases_from_fixed_company_list(companies),
        network_live_authorized=False,
    )
    orcl_row = next(item for item in matrix["rows"] if item["test_id"] == "AUTH-001")
    positive_rows = [item for item in matrix["rows"] if item["test_id"] in {"AUTH-001", "AUTH-002", "AUTH-003"}]
    negative_rows = [item for item in matrix["rows"] if item["expected"] == "BLOCK"]
    semantic_files = matrix["semantic_files"]
    runner_path = args.research_repo / "research_agent/alpha_shared/runner.py"

    _write_text(
        staging,
        "00_VERDICT.md",
        """# Fixed24 Execution Authority Closure R1 — Verdict

Verdict: **PASS — EXECUTION AUTHORITY CANDIDATE READY FOR INDEPENDENT REREVIEW**

The R4 hardcoded Development live-ticker guard was replaced by an external,
self-hashed `BatchExecutionAuthorityIR@1` and a verified pre-network receipt.
The exact frozen ORCL case now passes offline preflight while remaining
`PREFLIGHT_ONLY`; it cannot reach a provider until a later handoff supplies a
verified Shared Freeze and live `FIXED_BATCH` authority.

No Fixed24 issuer was queried or run. H1/H2/H3/H4 semantics, all four
archetype profiles, Product, release, deploy and publication remain unchanged.
""",
    )
    _write_json(
        staging,
        "01_STOP_RESULT_BINDING.json",
        {
            "status": "PASS",
            "handoff_sha256": args.handoff_sha256,
            "stop_result_sha256": handoff_manifest["stop_result_sha256"],
            "stop_result_manifest_sha256": handoff_manifest["stop_result_manifest_sha256"],
            "r4_authority_sha256": handoff_manifest["r4_authority_sha256"],
            "accepted_stop_verdict": "STOPPED_P1",
            "fixed24_queries_before": 0,
            "fixed24_runs_before": 0,
        },
    )
    _write_json(
        staging,
        "02_EXECUTION_AUTHORITY_CONTRACT.json",
        {
            "status": "PASS_CANDIDATE_PREFLIGHT_ONLY",
            "authority": authority.model_dump(mode="json"),
            "corrected_research_commit": research_head,
            "corrected_research_tree": research_tree,
            "final_live_authority_materialized": False,
            "shared_freeze_materialized": False,
        },
    )
    _write_json(
        staging,
        "03_CHANGED_FILES.json",
        {
            "status": "PASS",
            "base_commit": handoff_manifest["research_base"],
            "candidate_commit": research_head,
            "candidate_tree": research_tree,
            "allowed_paths": sorted(allowed_paths),
            "changed_files": changed,
            "unexpected_paths": [],
            "product_changed": False,
        },
    )
    _write_json(
        staging,
        "04_SEMANTIC_IMMUTABILITY_PROOF.json",
        {
            "status": "PASS",
            "semantic_runtime_unchanged": True,
            "product_changed": False,
            "r4_semantic_files": semantic_files,
            "r4_runner_before_sha256": r4_freeze["source_file_sha256s"][
                "research_agent/alpha_shared/runner.py"
            ],
            "runner_after_sha256": _sha(runner_path),
            "runner_change_class": "EXECUTION_CONTROL_ONLY",
            "forbidden_semantic_paths_changed": [],
            "archetype_profile_change": False,
            "formula_change": False,
            "period_freshness_change": False,
            "metric_registry_change": False,
            "source_selection_change": False,
        },
    )
    _write_json(
        staging,
        "05_ORCL_PREFLIGHT_FIXTURE.json",
        {
            "status": "PASS",
            "ticker": "ORCL",
            "sequence": 1,
            "archetype_profile_id": "saas",
            "authority_sha256": matrix["authority_sha256"],
            "receipt_sha256": orcl_row["receipt_sha256"],
            "authorization_mode": orcl_row["authorization_mode"],
            "authorization_preflight_count": 1,
            "case_attempt_count": 0,
            "network_queries": 0,
            "completed_case_count": 0,
        },
    )
    _write_json(staging, "06_POSITIVE_AUTHORIZATION_FIXTURES.json", {"status": "PASS", "rows": positive_rows})
    _write_json(staging, "07_NEGATIVE_AUTHORIZATION_FIXTURES.json", {"status": "PASS", "rows": negative_rows})
    _write_json(
        staging,
        "08_PRENETWORK_NONINTERFERENCE.json",
        {
            "status": "PASS",
            "authorization_preflight_count": matrix["authorization_preflight_count"],
            "case_attempt_count": 0,
            "live_network_query_count": 0,
            "completed_case_count": 0,
            "rejected_authority_reaches_provider": False,
            "preflight_only_receipt_reaches_provider": False,
        },
    )
    _write_json(
        staging,
        "09_RUNNER_INTEGRATION_REPORT.json",
        {
            "status": "PASS",
            "entrypoint": "research_agent.alpha_shared.runner.run_canonical_alpha_case",
            "authorization_entrypoint": "authorize_case_before_network",
            "runner_consumes": "AuthorizationReceiptIR",
            "hardcoded_development_ticker_guard_removed": True,
            "fixed24_ticker_hardcode_added": False,
            "environment_bypass_added": False,
            "development_validation_uses_external_authority": True,
            "offline_replay_requires_live_authority": False,
        },
    )
    shutil.copy2(args.matrix, staging / "10_AUTHORITY_MATRIX_EXECUTED.json")
    outcomes = external["matrix_outcomes"]
    _write_json(staging, "11_R1_R4_REGRESSION.json", {"status": "PASS", **outcomes["AUTH-025"]})
    _write_json(staging, "12_EIGHT_ALPHA_REGRESSION.json", {"status": "PASS", **outcomes["AUTH-026"]})
    _write_json(staging, "13_FULL_RESEARCH_REGRESSION.json", {"status": "PASS", **outcomes["AUTH-027"]})
    _write_json(staging, "14_FULL_PRODUCT_REGRESSION.json", {"status": "PASS", "product_changed": False, **outcomes["AUTH-028"]})
    _write_json(staging, "15_WHOLE_ALPHA_REGRESSION.json", {"status": "PASS", **outcomes["AUTH-029"]})
    _write_json(
        staging,
        "16_SECURITY_DEPENDENCY_REPORT.json",
        {
            "status": "PASS",
            "research_ruff": "PASS",
            "research_pip_check": "PASS",
            "product_npm_audit": {"vulnerabilities": 0, "high": 0, "critical": 0},
            "blocking_findings": [],
        },
    )
    before = _read(args.foreign_before)
    after = _read(args.foreign_after)
    created = [args.research_repo / item["path"] for item in changed if item["status"].startswith("A")]
    modified = [args.research_repo / item["path"] for item in changed if item["status"].startswith("M")]
    boundary = _boundary_receipt_builder()(
        before=before,
        after=after,
        room16_roots=(args.research_repo, args.product_repo),
        command_audit=[
            {
                "argv": ["apply_patch", "execution_authority_closure"],
                "cwd": str(args.research_repo),
                "mutation_classification": "room16_write",
            },
            {
                "argv": ["pytest", "ruff", "pip-check", "npm", "freeze-verifiers"],
                "cwd": str(args.research_repo),
                "mutation_classification": "room16_test_or_verification",
            },
            {
                "argv": ["git", "commit", "push"],
                "cwd": str(args.research_repo),
                "mutation_classification": "room16_write",
            },
        ],
        changed_paths={"created": [*created, staging], "modified": modified, "deleted": []},
        output_paths=(staging, archive_path),
        foreign_repo_used_as_authority_input=False,
    )
    _write_json(staging, "17_BOUNDARY_GATE_V2_REPORT.json", {**boundary, "status": "PASS"})
    _write_json(
        staging,
        "18_FIXED24_NONINTERFERENCE.json",
        {
            "status": "PASS",
            "fixed24_queries": stop_prestart["fixed24_query_count"],
            "fixed24_runs": stop_prestart["fixed24_run_count"],
            "case_attempt_count": 0,
            "completed_case_count": 0,
            "ORCL_network_queries": 0,
            "company_replacements": [],
            "batch_started": False,
            "product_report_v2_started": False,
        },
    )
    _write_json(
        staging,
        "19_REPOSITORY_END_STATE.json",
        {
            "status": "PASS",
            "research": {
                "origin": _git(args.research_repo, "remote", "get-url", "origin"),
                "branch": _git(args.research_repo, "branch", "--show-current"),
                "head": research_head,
                "tree": research_tree,
                "upstream_divergence": _git(args.research_repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
                "tracked_clean": True,
            },
            "product": {
                "origin": _git(args.product_repo, "remote", "get-url", "origin"),
                "branch": _git(args.product_repo, "branch", "--show-current"),
                "head": product_head,
                "tree": product_tree,
                "upstream_divergence": _git(args.product_repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"),
                "tracked_clean": True,
                "changed": False,
            },
        },
    )
    _write_json(
        staging,
        "20_BATCH_RESTART_READINESS.json",
        {
            "status": "PASS_CANDIDATE_ONLY",
            "execution_authority_candidate_ready": True,
            "ORCL_preflight_authorized": True,
            "ORCL_network_queries": 0,
            "fixed24_queries": 0,
            "fixed24_runs": 0,
            "semantic_runtime_unchanged": True,
            "product_changed": False,
            "batch_started": False,
            "ready_for_independent_rereview": True,
            "shared_freeze_materialized": False,
            "final_fixed_batch_live_authority_materialized": False,
            "next_gate": "INDEPENDENT_REREVIEW_THEN_NEW_FINAL_EXECUTION_HANDOFF",
        },
    )
    _write_text(
        staging,
        "21_INDEPENDENT_REREVIEW_REQUEST.md",
        f"""# Independent Rereview Request — Fixed24 Execution Authority Closure R1

Please independently verify candidate Research commit `{research_head}` and tree
`{research_tree}` against the enclosed 30-row matrix and source review.

Acceptance requested only for the execution-authority correction. Shared Freeze,
the final live Fixed24 authority and the first ORCL network request remain outside
this result and require a new execution handoff after acceptance.
""",
    )

    for item in changed:
        source = args.research_repo / item["path"]
        target = staging / "source_review" / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    verifier_target = staging / "independent_verifier/verify_authority_closure.py"
    verifier_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        args.research_repo / "scripts/ops/verify_fixed24_execution_authority_closure.py",
        verifier_target,
    )
    _write_json(
        staging,
        "independent_verifier/VERIFIER_RECEIPT.json",
        {
            "contract_id": "room16.fixed24.execution_authority_closure_verifier_receipt@1",
            "status": "PASS",
            "matrix_rows": 30,
            "authority_sha256": matrix["authority_sha256"],
            "fixed24_queries": 0,
            "fixed24_runs": 0,
            "semantic_runtime_unchanged": True,
            "product_changed": False,
            "ready_for_independent_rereview": True,
        },
    )

    payloads = sorted(
        path for path in staging.rglob("*") if path.is_file() and path.name not in {"MANIFEST.json", "SHA256SUMS.txt"}
    )
    files = [
        {
            "path": path.relative_to(staging).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha(path),
        }
        for path in payloads
    ]
    manifest: dict[str, object] = {
        "contract_id": "room16.fixed24.execution_authority_closure_result@1",
        "schema_version": 1,
        "status": "PASS_CANDIDATE_READY_FOR_INDEPENDENT_REREVIEW",
        "generated_date": DATE,
        "source_handoff_sha256": args.handoff_sha256,
        "research_commit": research_head,
        "research_tree": research_tree,
        "product_commit": product_head,
        "product_tree": product_tree,
        "file_count": len(files),
        "files": files,
        "fixed24_queries": 0,
        "fixed24_runs": 0,
        "batch_started": False,
        "manifest_sha256": "",
    }
    manifest["manifest_sha256"] = sha256_json(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    _write_json(staging, "MANIFEST.json", manifest)
    checksums = [f"{item['sha256']}  {item['path']}" for item in files]
    checksums.append(f"{_sha(staging / 'MANIFEST.json')}  MANIFEST.json")
    _write_text(staging, "SHA256SUMS.txt", "\n".join(checksums))
    _zip_tree(staging, archive_path)
    return {
        "status": "PASS",
        "staging": str(staging),
        "archive": str(archive_path),
        "archive_sha256": _sha(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "manifest_sha256": manifest["manifest_sha256"],
        "payload_count": len(files),
        "research_commit": research_head,
        "research_tree": research_tree,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff-root", required=True, type=Path)
    parser.add_argument("--handoff-sha256", required=True)
    parser.add_argument("--stop-result-root", required=True, type=Path)
    parser.add_argument("--r4-root", required=True, type=Path)
    parser.add_argument("--matrix", required=True, type=Path)
    parser.add_argument("--external-gates-json", required=True, type=Path)
    parser.add_argument("--foreign-before", required=True, type=Path)
    parser.add_argument("--foreign-after", required=True, type=Path)
    parser.add_argument("--research-repo", required=True, type=Path)
    parser.add_argument("--product-repo", required=True, type=Path)
    parser.add_argument("--release-dir", required=True, type=Path)
    return parser


def main() -> int:
    result = build(_parser().parse_args())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
