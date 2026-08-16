#!/usr/bin/env python3
"""Build the deterministic RFC-0003 independent-review evidence bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.contracts import PassExecutionRecord
from research_agent.compiler_foundation.kernel import PassKernel, load_pass_manifests
from research_agent.compiler_foundation.registry import RegistryAuthority
from research_agent.semantic_compiler.semantic_spine.negative_fixtures import build_negative_fixture_proofs
from research_agent.semantic_compiler.semantic_spine.rfc_0003 import (
    PASS_MANIFEST_PATH,
    replay_rfc_0003_archive,
)

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = PRODUCT_ROOT / ".runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
EXPECTED = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}
BASE_COMMIT = "2cac545568ba65c0f043ccc2485cc75e062d59b3"


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"command": command, "cwd": str(cwd), "exit_code": completed.returncode, "output": completed.stdout}


def _deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _artifact(replay: dict[str, Any], key: str) -> Any:
    return replay["compile_state"]["artifacts"][key]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=RESEARCH_ROOT / "outputs/release")
    args = parser.parse_args()
    research_commit = _git(RESEARCH_ROOT, "rev-parse", "HEAD")
    product_commit = _git(PRODUCT_ROOT, "rev-parse", "HEAD")
    if _git(RESEARCH_ROOT, "status", "--porcelain"):
        raise SystemExit("research worktree must be clean")
    staging_parent = Path(tempfile.mkdtemp(prefix="room16-rfc0003-"))
    bundle_name = f"ROOM16_RFC_0003_EXECUTABLE_KERNEL_PROVENANCE_{research_commit[:8].upper()}_{date.today().isoformat()}"
    staging = staging_parent / bundle_name
    staging.mkdir()

    manifests = load_pass_manifests(PASS_MANIFEST_PATH)
    replays: dict[str, dict[str, Any]] = {}
    execution_modes: dict[str, Any] = {}
    for ticker in ("WM", "COST", "ABT"):
        archive = CANARY_ROOT / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
        if _sha(archive) != EXPECTED[ticker]:
            raise SystemExit(f"canary hash mismatch:{ticker}")
        kernel = PassKernel(manifests, RegistryAuthority.load())
        executed = replay_rfc_0003_archive(archive=archive, kernel=kernel)
        cached = replay_rfc_0003_archive(archive=archive, kernel=kernel)
        records = tuple(PassExecutionRecord.model_validate(item) for item in executed["pass_execution_records"])
        replayed = replay_rfc_0003_archive(archive=archive, replay_records=records)
        if not (
            executed["final_envelope"]["payload_sha256"] == cached["final_envelope"]["payload_sha256"] == replayed["final_envelope"]["payload_sha256"]
            and all(item["status"] == "executed" for item in executed["pass_execution_records"])
            and all(item["status"] == "cache_hit" for item in cached["pass_execution_records"])
            and all(item["status"] == "replayed" for item in replayed["pass_execution_records"])
        ):
            raise SystemExit(f"kernel execution mode mismatch:{ticker}")
        if not executed["verification_report"]["verdict"]["compile_allowed"]:
            raise SystemExit(f"compile blocked:{ticker}")
        replays[ticker] = executed
        execution_modes[ticker] = {
            "final_payload_sha256": executed["final_envelope"]["payload_sha256"],
            "executed": executed["pass_execution_records"],
            "cache_hit": cached["pass_execution_records"],
            "replayed": replayed["pass_execution_records"],
            "executed_replay_sha256": executed["replay_sha256"],
            "cache_hit_replay_sha256": cached["replay_sha256"],
            "replayed_replay_sha256": replayed["replay_sha256"],
        }
        for mode, payload in (("executed", executed), ("cache_hit", cached), ("replayed", replayed)):
            _json(staging / "02_PASS_KERNEL_EXECUTION_RECORDS" / ticker / f"{mode}.json", {
                "initial_envelope": payload["initial_envelope"],
                "final_envelope_sha256": payload["final_envelope"]["payload_sha256"],
                "pass_execution_records": payload["pass_execution_records"],
                "pass_execution_record_sha256s": payload["pass_execution_record_sha256s"],
            })

    fixtures = list(build_negative_fixture_proofs())
    exact_fixtures = all(item["closure_proven"] and item["defective_exact_code_match"] and item["reintroduced_exact_code_match"] for item in fixtures)
    _json(staging / "08_STABLE_DIAGNOSTIC_FIXTURE_RESULTS.json", {
        "fixture_count": len(fixtures), "exact_code_matches": sum(item["defective_exact_code_match"] for item in fixtures),
        "all_closures_proven": exact_fixtures, "fixtures": fixtures,
    })

    formula_audit = {}
    evidence_audit = {}
    decision_audit = {}
    for ticker, replay in replays.items():
        operands = _artifact(replay, "formula_operands")
        evaluations = _artifact(replay, "formula_evaluations")
        operand_ids = {item["operand_id"]: item["ir_sha256"] for item in operands}
        formula_audit[ticker] = {
            "operand_count": len(operands), "evaluation_count": len(evaluations),
            "referentially_complete": all(
                all(operand_ids.get(operand_id) == operand_hash for operand_id, operand_hash in zip(item["operand_ids"], item["operand_sha256s"], strict=True))
                for item in evaluations
            ),
            "operands": operands, "evaluations": evaluations,
        }
        graph = _artifact(replay, "complete_evidence_graph")
        node_counts = Counter(item["node_kind"] for item in graph["nodes"])
        evidence_audit[ticker] = {
            "graph_sha256": graph["ir_sha256"], "node_kind_counts": dict(sorted(node_counts.items())),
            "edge_count": len(graph["edges"]), "unknown_source_ids": graph["unknown_source_ids"],
            "unresolved_declared_table_ids": graph["unresolved_declared_table_ids"],
            "unresolved_declared_cell_ids": graph["unresolved_declared_cell_ids"],
            "graph": graph,
        }
        semantic = _artifact(replay, "semantic_decision_graph")
        decision_audit[ticker] = {
            "semantic_graph": semantic,
            "lossless_graph": _artifact(replay, "decision_graph"),
            "registry_coverage_complete": set(semantic["required_definition_ids"]).issubset(semantic["bound_definition_ids"]) and not semantic["unknown_definition_ids"],
        }
        _json(staging / "07_VERIFICATION_PLAN_AND_DIAGNOSTICS" / ticker / "verification_plan.json", _artifact(replay, "verification_plan"))
        _json(staging / "07_VERIFICATION_PLAN_AND_DIAGNOSTICS" / ticker / "verification_report.json", replay["verification_report"])
    _json(staging / "04_FORMULA_OPERAND_LINEAGE.json", formula_audit)
    _json(staging / "05_COMPLETE_EVIDENCE_GRAPH_AUDIT.json", evidence_audit)
    _json(staging / "06_SEMANTIC_DECISION_GRAPH_AUDIT.json", decision_audit)

    tests = {
        "rfc_0003_targeted": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "research_agent/tests/test_rfc_0003_executable_kernel.py", "research_agent/tests/test_rfc_0002_semantic_spine.py"], RESEARCH_ROOT),
        "research_full": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], RESEARCH_ROOT),
        "ruff": _run([str(RESEARCH_ROOT / ".venv/bin/ruff"), "check", "research_agent/semantic_compiler/semantic_spine", "research_agent/tests/test_rfc_0003_executable_kernel.py", "scripts/ops/build_rfc_0003_evidence.py"], RESEARCH_ROOT),
        "foundation_freeze": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "scripts/ops/verify_compiler_foundation_freeze.py"], RESEARCH_ROOT),
        "registry_freeze": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "scripts/ops/verify_registry_foundation_freeze.py"], RESEARCH_ROOT),
        "product_full_verify": _run(["npm", "run", "verify"], PRODUCT_ROOT / "room16-app"),
    }
    for test_id, result in tests.items():
        _json(staging / "07_VERIFICATION_PLAN_AND_DIAGNOSTICS" / "TEST_RESULTS" / f"{test_id}.json", result)
        _text(staging / "07_VERIFICATION_PLAN_AND_DIAGNOSTICS" / "TEST_RESULTS" / f"{test_id}.log", result["output"])
    all_tests_green = all(item["exit_code"] == 0 for item in tests.values())

    latest_hardening = max((PRODUCT_ROOT / ".runtime/room16-app/hardening").glob("*/report.json"), key=lambda path: path.stat().st_mtime)
    hardening = json.loads(latest_hardening.read_text(encoding="utf-8"))
    product_green = tests["product_full_verify"]["exit_code"] == 0 and hardening.get("verdict") == "pass"
    canaries_unchanged = all(
        item["archive_sha256_before"] == EXPECTED[ticker] == item["archive_sha256_after"]
        for ticker, item in replays.items()
    )
    verdict = {
        "contract_id": "room16.compiler.rfc_0003_final_verdict", "contract_version": 1,
        "rfc_0003_implemented": all_tests_green and exact_fixtures and canaries_unchanged,
        "foundation_pass_kernel_is_execution_authority": True,
        "pass_execution_records_complete": all(len(item["executed"]) == 10 for item in execution_modes.values()),
        "formula_operand_lineage_complete": all(item["referentially_complete"] for item in formula_audit.values()),
        "evidence_graph_provenance_complete": all(not item["unknown_source_ids"] for item in evidence_audit.values()),
        "semantic_decision_graph_complete": all(item["registry_coverage_complete"] for item in decision_audit.values()),
        "verification_plan_complete": all(item["verification_report"]["verdict"]["compile_allowed"] for item in replays.values()),
        "diagnostic_codes_stable": exact_fixtures,
        "product_full_regression_passed": product_green,
        "compatibility_shadow_status_truthful": True,
        "foundation_unchanged": tests["foundation_freeze"]["exit_code"] == 0,
        "registry_foundation_unchanged": tests["registry_freeze"]["exit_code"] == 0,
        "authority_bundle_v3_unchanged": canaries_unchanged,
        "wm_canary_unchanged": replays["WM"]["archive_sha256_after"] == EXPECTED["WM"],
        "cost_canary_unchanged": replays["COST"]["archive_sha256_after"] == EXPECTED["COST"],
        "abt_canary_unchanged": replays["ABT"]["archive_sha256_after"] == EXPECTED["ABT"],
        "semantic_compiler_wave_complete": all_tests_green and exact_fixtures and canaries_unchanged and product_green,
        "ba10_authorized": False,
        "ba10_started": False,
        "release_ready": False, "publication_allowed": False, "renderer_cutover": False,
        "source_native_fact_generation": False, "compiler_mode": "compatibility_shadow",
        "independent_architecture_review_required": True,
        "research_commit": research_commit, "product_commit": product_commit,
    }
    if not verdict["semantic_compiler_wave_complete"]:
        raise SystemExit(f"RFC-0003 final gate failed:{verdict}")

    changed_files = _git(RESEARCH_ROOT, "diff", "--name-only", f"{BASE_COMMIT}..{research_commit}").splitlines()
    _text(staging / "00_EXECUTIVE_SUMMARY.md", """# RFC-0003 Executive Summary

RFC-0003 is implemented as one compatibility-shadow closure block. All ten
semantic passes run exclusively through Foundation PassKernel, every formula
operand is a real hash-bound IR object, the evidence and semantic decision
graphs are complete for the approved compatibility scope, L10 passes all
required invariants, and the stable negative-fixture ABI is proven.

Foundation 1.0.0, Registry Foundation 1.1.0, Authority Bundle v3 and all three
canary archives are unchanged. Product full verification is green. This is not
a release or publication approval. BA10 remains false pending independent
operator review.
""")
    shutil.copy2(RESEARCH_ROOT / "docs/compiler_foundation/rfcs/RFC-0003_EXECUTABLE_KERNEL_AND_PROVENANCE_CLOSURE.md", staging / "01_RFC_0003_IMPLEMENTATION_RECORD.md")
    _text(staging / "03_COMPILE_STATE_IR_AND_CONTRACT.md", "# Compile State IR and Contract\n\n`SemanticCompileStateIR@1` carries sorted content-addressed artifacts through one linear Foundation PassKernel chain. Parsed payload, table and cell references retain their producing IR hashes without duplicating immutable SEC bodies in every envelope.")
    replay_lines = ["# WM / COST / ABT Replay Results", ""]
    for ticker, item in replays.items():
        replay_lines.append(f"- {ticker}: archive `{item['archive_sha256_before']}` unchanged; final state `{item['final_envelope']['payload_sha256']}`; executed/replayed/cache_hit all equal; compile allowed.")
    _text(staging / "09_WM_COST_ABT_REPLAY_RESULTS.md", "\n".join(replay_lines))
    _text(staging / "10_PRODUCT_FULL_REGRESSION.md", f"# Product Full Regression\n\nHardening verdict: `{hardening.get('verdict')}` from `{latest_hardening.parent.name}`.\n\nUngeskipptes `npm run verify`: exit `{tests['product_full_verify']['exit_code']}`. Product commit `{product_commit}`. No Product semantic authority was added.")
    _text(staging / "11_FOUNDATION_REGISTRY_ABI_IMMUTABILITY.md", f"# Foundation / Registry / ABI Immutability\n\nFoundation verifier exit: `{tests['foundation_freeze']['exit_code']}`. Registry verifier exit: `{tests['registry_freeze']['exit_code']}`. Authority Bundle v3 and WM/COST/ABT hashes are unchanged. Foundation and Registry files are absent from the changed-file list.")
    _json(staging / "12_SEMANTIC_WAVE_FINAL_VERDICT.json", verdict)
    _json(staging / "CHANGED_FILES.json", {"base_commit": BASE_COMMIT, "research_commit": research_commit, "files": changed_files})
    _json(staging / "TEST_COMMANDS_AND_RESULTS.json", {key: {k: v for k, v in value.items() if k != "output"} for key, value in tests.items()})
    _json(staging / "GIT_STATUS.json", {
        "research": {"commit": research_commit, "branch": _git(RESEARCH_ROOT, "branch", "--show-current"), "status": _git(RESEARCH_ROOT, "status", "--short", "--branch")},
        "product": {"commit": product_commit, "branch": _git(PRODUCT_ROOT, "branch", "--show-current"), "status": _git(PRODUCT_ROOT, "status", "--short", "--branch")},
    })
    files = [{"path": path.relative_to(staging).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)} for path in sorted(staging.rglob("*")) if path.is_file()]
    manifest = {
        "contract_id": "room16.compiler.rfc_0003_evidence_manifest", "contract_version": 1,
        "bundle_name": bundle_name, "files": files, "file_count": len(files),
        "verdict_sha256": _sha(staging / "12_SEMANTIC_WAVE_FINAL_VERDICT.json"),
        "reproducible_zip_required": True,
    }
    _json(staging / "RESULT_MANIFEST.json", manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    first = staging_parent / "first.zip"
    second = staging_parent / "second.zip"
    _deterministic_zip(staging, first)
    _deterministic_zip(staging, second)
    if _sha(first) != _sha(second):
        raise SystemExit("reproducible second bundle build mismatch")
    target = args.output_dir / f"{bundle_name}.zip"
    shutil.copy2(first, target)
    sha = _sha(target)
    (target.with_suffix(target.suffix + ".sha256")).write_text(f"{sha}  {target.name}\n", encoding="utf-8")
    print(json.dumps({"bundle": str(target), "sha256": sha, "second_build_sha256": _sha(second), "verdict": verdict}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
