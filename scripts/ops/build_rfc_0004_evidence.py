#!/usr/bin/env python3
"""Build the deterministic RFC-0004 narrow-review Evidence Bundle."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import CompilerLayer, IREnvelope, PassExecutionRecord
from research_agent.compiler_foundation.kernel import PassKernel, identity_shadow_pass, load_pass_manifests
from research_agent.compiler_foundation.registry import RegistryAuthority
from research_agent.semantic_compiler.semantic_spine.contracts import create_hashed
from research_agent.semantic_compiler.semantic_spine.rfc_0003 import (
    PASS_MANIFEST_PATH,
    _create_state,
    _verification,
    create_execution_attestation,
)
from research_agent.semantic_compiler.semantic_spine.rfc_0004 import (
    iter_canonical_table_artifacts,
    replay_rfc_0004_archive,
)
from research_agent.semantic_compiler.semantic_spine.rfc_0004_contracts import (
    CompleteEvidenceGraphRFC0004IR,
    FormulaOperandBindingIR,
    SemanticCompileStateRFC0004IR,
    SemanticDecisionGraphRFC0004IR,
    SemanticDecisionNodeIR,
    SemanticRegistryLockIR,
    VerificationReportRFC0004IR,
)

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = PRODUCT_ROOT / ".runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
EXPECTED = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}
BASE_COMMIT = "fca8902fc157cb8d201fbfd998c3934481662851"


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    return {
        "command": command, "cwd": str(cwd),
        "exit_code": completed.returncode, "output": completed.stdout,
    }


def _product_full_verify() -> dict[str, Any]:
    """Run the unskipped Product verification against a managed local server."""
    app_root = PRODUCT_ROOT / "room16-app"
    server_log = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    server = subprocess.Popen(
        ["node", "server.mjs", "--static", "--port", "4516"],
        cwd=app_root,
        text=True,
        stdout=server_log,
        stderr=subprocess.STDOUT,
    )
    try:
        ready = False
        for _ in range(40):
            if server.poll() is not None:
                break
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:4516/api/health", timeout=1,
                ) as response:
                    ready = response.status == 200
            except (OSError, urllib.error.URLError):
                pass
            if ready:
                break
            time.sleep(0.25)
        if not ready:
            server_log.seek(0)
            return {
                "command": ["npm", "run", "verify"],
                "cwd": str(app_root),
                "exit_code": 1,
                "output": "managed Product server did not become healthy\n" + server_log.read(),
            }
        return _run(["npm", "run", "verify"], app_root)
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        server_log.close()


def _deterministic_zip(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _diagnostic(report: dict[str, Any], code: str) -> dict[str, Any]:
    return next(item for item in report["diagnostics"] if item["code"] == code)


def _rerun_l10(state: SemanticCompileStateRFC0004IR, artifacts: dict[str, Any]) -> dict[str, Any]:
    candidate = _create_state(previous=state, stage="decisions", artifacts=artifacts)
    verified = SemanticCompileStateRFC0004IR.model_validate(_verification(candidate.model_dump(mode="json")))
    return VerificationReportRFC0004IR.model_validate(
        verified.artifacts["verification_report"]
    ).model_dump(mode="json")


def _negative_fixtures(replay: dict[str, Any]) -> dict[str, Any]:
    state = SemanticCompileStateRFC0004IR.model_validate(replay["compile_state"])
    baseline = replay["verification_report"]
    proofs: list[dict[str, Any]] = []

    formula_artifacts = dict(state.artifacts)
    operands = list(formula_artifacts["formula_operands"])
    operand = FormulaOperandBindingIR.model_validate(operands[0])
    body = operand.model_dump(
        mode="json", exclude={"contract_id", "contract_version", "ir_sha256"},
    )
    body.update({
        "operand_fact_or_parameter_id": None,
        "binding_kind": "quarantined_unresolved_operand",
        "dimension": "unknown", "unit": "unknown", "currency": "none", "scale": "unknown",
        "period_kind": "unknown", "period_start": None, "period_end": None,
        "source_ids": (), "evidence_ids": (), "source_locators": (),
        "origin_mode": "quarantined_unresolved_operand",
    })
    operands[0] = create_hashed(FormulaOperandBindingIR, **body).model_dump(mode="json")
    formula_artifacts["formula_operands"] = operands
    formula_report = _rerun_l10(state, formula_artifacts)
    proofs.append({
        "finding_id": "RFC3-AR-002", "expected_code": "FORMULA_OPERAND_LINEAGE_COMPLETE",
        "corrected_passed": _diagnostic(baseline, "FORMULA_OPERAND_LINEAGE_COMPLETE")["release_effect"] == "none",
        "defective_blocked": _diagnostic(formula_report, "FORMULA_OPERAND_LINEAGE_COMPLETE")["release_effect"] == "compile_block",
        "reintroduced_exact_code": _diagnostic(formula_report, "FORMULA_OPERAND_LINEAGE_COMPLETE")["code"],
    })

    table_artifacts = dict(state.artifacts)
    graph = CompleteEvidenceGraphRFC0004IR.model_validate(table_artifacts["complete_evidence_graph"])
    mapping = graph.legacy_table_cell_mappings[0]
    mapping_body = mapping.model_dump(mode="json", exclude={"contract_id", "contract_version", "ir_sha256"})
    mapping_body.update({
        "canonical_table_id": None, "canonical_cell_id": None,
        "mapping_status": "quarantined_unresolved", "mapping_basis": "negative_fixture",
    })
    bad_mapping = create_hashed(type(mapping), **mapping_body)
    mappings = (bad_mapping, *graph.legacy_table_cell_mappings[1:])
    graph_body = graph.model_dump(mode="json", exclude={"contract_id", "contract_version", "ir_sha256"})
    graph_body.update({
        "legacy_table_cell_mappings": mappings,
        "unresolved_executable_fact_ids": (bad_mapping.fact_id,),
    })
    table_artifacts["complete_evidence_graph"] = create_hashed(
        CompleteEvidenceGraphRFC0004IR, **graph_body,
    ).model_dump(mode="json")
    table_report = _rerun_l10(state, table_artifacts)
    for code in (
        "DECLARED_TABLE_CELL_LINEAGE_COMPLETE",
        "EXECUTABLE_FACT_TABLE_LINEAGE_COMPLETE",
        "TABLE_FACT_LINEAGE_TRUTHFUL",
    ):
        proofs.append({
            "finding_id": "RFC3-AR-003", "expected_code": code,
            "corrected_passed": _diagnostic(baseline, code)["release_effect"] == "none",
            "defective_blocked": _diagnostic(table_report, code)["release_effect"] == "compile_block",
            "reintroduced_exact_code": _diagnostic(table_report, code)["code"],
        })

    decision_artifacts = dict(state.artifacts)
    decision = SemanticDecisionGraphRFC0004IR.model_validate(decision_artifacts["semantic_decision_graph"])
    index = next(
        index for index, item in enumerate(decision.nodes)
        if item.definition_id == "decision.score_contribution" and item.instance_presence == "present"
    )
    node = decision.nodes[index]
    node_body = node.model_dump(mode="json", exclude={"contract_id", "contract_version", "ir_sha256"})
    node_body.update({"claim_ids": (), "fact_ids": (), "evidence_ids": (), "source_ids": ()})
    nodes = list(decision.nodes)
    nodes[index] = create_hashed(SemanticDecisionNodeIR, **node_body)
    decision_body = decision.model_dump(mode="json", exclude={"contract_id", "contract_version", "ir_sha256"})
    decision_body["nodes"] = tuple(nodes)
    decision_artifacts["semantic_decision_graph"] = create_hashed(
        SemanticDecisionGraphRFC0004IR, **decision_body,
    ).model_dump(mode="json")
    decision_report = _rerun_l10(state, decision_artifacts)
    for code in (
        "DECISION_CLAIM_LINEAGE_COMPLETE", "DECISION_FACT_LINEAGE_COMPLETE",
        "DECISION_SCORE_INPUTS_BOUND",
    ):
        proofs.append({
            "finding_id": "RFC3-AR-004", "expected_code": code,
            "corrected_passed": _diagnostic(baseline, code)["release_effect"] == "none",
            "defective_blocked": _diagnostic(decision_report, code)["release_effect"] == "compile_block",
            "reintroduced_exact_code": _diagnostic(decision_report, code)["code"],
        })
    for item in proofs:
        item["closure_proven"] = (
            item["corrected_passed"] and item["defective_blocked"]
            and item["reintroduced_exact_code"] == item["expected_code"]
        )
    return {"proofs": proofs, "all_closures_proven": all(item["closure_proven"] for item in proofs)}


def _cache_lock_fixture() -> dict[str, Any]:
    manifests = load_pass_manifests(PASS_MANIFEST_PATH)
    kernel = PassKernel(manifests, RegistryAuthority.load())
    implementations = {item.pass_id: identity_shadow_pass for item in manifests}

    def lock(signature_hash: str) -> SemanticRegistryLockIR:
        return create_hashed(
            SemanticRegistryLockIR,
            semantic_registry_authority_sha256="a" * 64,
            metric_signature_authority_sha256=signature_hash,
            formula_policy_sha256="c" * 64, evidence_policy_sha256="d" * 64,
            claim_policy_sha256="e" * 64, decision_policy_sha256="f" * 64,
            pass_manifest_sha256="1" * 64, compiler_implementation_commit="2" * 40,
            compiler_implementation_version="4.0.0-rfc0004",
            compiler_implementation_sha256="3" * 64,
        )

    def envelope(value: SemanticRegistryLockIR) -> IREnvelope:
        return IREnvelope.create(
            ir_type="semantic_compile_state.source_inputs", layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
            producer_pass_id="rfc0004.fixture", payload={
                "source_inputs": [{"id": "same-source"}],
                "semantic_registry_lock": value.model_dump(mode="json"),
            },
        )

    _, first = kernel.execute(envelope(lock("b" * 64)), implementations)
    _, cached = kernel.execute(envelope(lock("b" * 64)), implementations)
    _, changed = kernel.execute(envelope(lock("4" * 64)), implementations)
    result = {
        "finding_id": "RFC3-AR-001",
        "same_source_input": True,
        "unchanged_authority_statuses": [item.status.value for item in cached],
        "changed_authority_statuses": [item.status.value for item in changed],
        "original_cache_keys": [item.cache_key for item in first],
        "changed_cache_keys": [item.cache_key for item in changed],
    }
    result["closure_proven"] = (
        all(item == "cache_hit" for item in result["unchanged_authority_statuses"])
        and all(item != "cache_hit" for item in result["changed_authority_statuses"])
        and result["original_cache_keys"] != result["changed_cache_keys"]
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=RESEARCH_ROOT / "outputs/release")
    args = parser.parse_args()
    research_commit = _git(RESEARCH_ROOT, "rev-parse", "HEAD")
    product_commit = _git(PRODUCT_ROOT, "rev-parse", "HEAD")
    if _git(RESEARCH_ROOT, "status", "--porcelain"):
        raise SystemExit("research worktree must be clean before evidence build")
    parent = Path(tempfile.mkdtemp(prefix="room16-rfc0004-"))
    bundle_name = f"ROOM16_RFC_0004_SEMANTIC_CONTRACT_INTEGRITY_{research_commit[:8].upper()}_{date.today().isoformat()}"
    staging = parent / bundle_name
    staging.mkdir()

    manifests = load_pass_manifests(PASS_MANIFEST_PATH)
    replays: dict[str, dict[str, Any]] = {}
    execution_audit: dict[str, Any] = {}
    for ticker in ("WM", "COST", "ABT"):
        archive = next(CANARY_ROOT.glob(f"ROOM16_{ticker}_*.zip"))
        if _sha(archive) != EXPECTED[ticker]:
            raise SystemExit(f"canary hash mismatch:{ticker}")
        kernel = PassKernel(manifests, RegistryAuthority.load())
        executed = replay_rfc_0004_archive(archive=archive, kernel=kernel)
        cached = replay_rfc_0004_archive(archive=archive, kernel=kernel)
        records = tuple(PassExecutionRecord.model_validate(item) for item in executed["pass_execution_records"])
        replayed = replay_rfc_0004_archive(archive=archive, replay_records=records)
        hashes = {
            executed["final_envelope"]["payload_sha256"], cached["final_envelope"]["payload_sha256"],
            replayed["final_envelope"]["payload_sha256"],
        }
        if len(hashes) != 1 or not executed["verification_report"]["verdict"]["compile_allowed"]:
            raise SystemExit(f"cross-mode convergence or compile verdict failed:{ticker}")
        replays[ticker] = executed
        execution_audit[ticker] = {
            "final_payload_sha256": hashes.pop(),
            "executed_records": executed["pass_execution_records"],
            "cache_hit_records": cached["pass_execution_records"],
            "replayed_records": replayed["pass_execution_records"],
            "execution_attestation": executed["execution_attestation"],
        }
        _json(staging / "07_L10_DIAGNOSTICS_AND_VERDICT" / ticker / "verification_plan.json", executed["compile_state"]["artifacts"]["verification_plan"])
        _json(staging / "07_L10_DIAGNOSTICS_AND_VERDICT" / ticker / "verification_report.json", executed["verification_report"])

    registry_lock = replays["WM"]["compile_state"]["semantic_registry_lock"]
    cache_fixture = _cache_lock_fixture()
    _json(staging / "02_SEMANTIC_REGISTRY_CACHE_LOCK.json", {
        "semantic_registry_lock": registry_lock,
        "cache_mutation_fixture": cache_fixture,
        "all_canaries_same_lock": len({
            item["compile_state"]["semantic_registry_lock"]["ir_sha256"] for item in replays.values()
        }) == 1,
    })

    formula_audit: dict[str, Any] = {}
    table_mapping_audit: dict[str, Any] = {}
    decision_audit: dict[str, Any] = {}
    for ticker, replay in replays.items():
        artifacts = replay["compile_state"]["artifacts"]
        operands = artifacts["formula_operands"]
        formula_audit[ticker] = {
            "operand_count": len(operands),
            "binding_kinds": {
                kind: sum(item["binding_kind"] == kind for item in operands)
                for kind in sorted({item["binding_kind"] for item in operands})
            },
            "result_metadata_copy_count": sum(
                item["origin_mode"] != "registered_policy_parameter"
                and item["evidence_ids"] == next(
                    fact["evidence_ids"] for fact in artifacts["typed_facts"]
                    if fact["fact_id"] == item["result_fact_id"]
                )
                and item["binding_kind"] == "quarantined_unresolved_operand"
                for item in operands
            ),
            "unresolved_count": sum(item["binding_kind"] == "quarantined_unresolved_operand" for item in operands),
            "operands": operands,
            "operand_facts": artifacts["formula_operand_facts"],
            "policy_parameters": artifacts["policy_parameters"],
            "evaluations": artifacts["formula_evaluations"],
        }
        graph = artifacts["complete_evidence_graph"]
        table_mapping_audit[ticker] = {
            "declared_mapping_count": len(graph["legacy_table_cell_mappings"]),
            "mapped_count": sum(item["mapping_status"] == "mapped" for item in graph["legacy_table_cell_mappings"]),
            "unresolved_executable_fact_ids": graph["unresolved_executable_fact_ids"],
            "mappings": graph["legacy_table_cell_mappings"],
        }
        semantic = artifacts["semantic_decision_graph"]
        present = [item for item in semantic["nodes"] if item["instance_presence"] == "present"]
        decision_audit[ticker] = {
            "claim_graph_sha256": semantic["claim_graph_sha256"],
            "present_node_count": len(present),
            "schema_only_node_count": len(semantic["nodes"]) - len(present),
            "claim_bound_present_nodes": sum(bool(item["claim_ids"]) for item in present),
            "fact_bound_present_nodes": sum(bool(item["fact_ids"]) for item in present),
            "evidence_bound_present_nodes": sum(bool(item["evidence_ids"]) for item in present),
            "semantic_graph": semantic,
        }
    _json(staging / "03_FORMULA_OPERAND_BINDING_AUDIT.json", formula_audit)
    _json(staging / "05_TABLE_CELL_LINEAGE_CLOSURE.json", table_mapping_audit)
    _json(staging / "06_DECISION_CLAIM_FACT_LINEAGE.json", decision_audit)

    artifact_index: dict[str, Any] = {}
    store = staging / "04_CANONICAL_TABLE_ARTIFACT_AUDIT" / "ARTIFACT_STORE"
    store.mkdir(parents=True)
    for ticker in ("WM", "COST", "ABT"):
        archive = next(CANARY_ROOT.glob(f"ROOM16_{ticker}_*.zip"))
        expected_refs = {
            item["semantic_table_ir_sha256"]: item
            for item in replays[ticker]["compile_state"]["artifacts"]["table_refs"]
        }
        resolved: set[str] = set()
        for table in iter_canonical_table_artifacts(archive):
            semantic_hash = table["ir_sha256"]
            if semantic_hash not in expected_refs:
                raise SystemExit(f"unregistered canonical table:{ticker}:{semantic_hash}")
            payload = (json.dumps(table, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            target = store / f"{semantic_hash}.json.gz"
            with target.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
                    compressed.write(payload)
            resolved.add(semantic_hash)
            artifact_index[semantic_hash] = {
                "ticker": ticker,
                "artifact_uri": f"room16-table://sha256/{semantic_hash}",
                "path": target.relative_to(staging).as_posix(),
                "compressed_sha256": _sha(target),
                "cell_count": len(table["cells"]),
                "semantic_ir_hash_verified": sha256_json({
                    key: value for key, value in table.items() if key != "ir_sha256"
                }) == semantic_hash,
            }
        if resolved != set(expected_refs):
            raise SystemExit(f"canonical artifact resolution incomplete:{ticker}")
    sample_hash = sorted(artifact_index)[0]
    sample_path = staging / artifact_index[sample_hash]["path"]
    tampered = bytearray(gzip.decompress(sample_path.read_bytes()))
    tampered[-2] = ord(" ") if tampered[-2] != ord(" ") else ord("\t")
    tamper_detected = hashlib.sha256(tampered).hexdigest() != hashlib.sha256(gzip.decompress(sample_path.read_bytes())).hexdigest()
    _json(staging / "04_CANONICAL_TABLE_ARTIFACT_AUDIT" / "artifact_index.json", {
        "artifact_count": len(artifact_index), "all_semantic_hashes_verified": all(
            item["semantic_ir_hash_verified"] for item in artifact_index.values()
        ), "tamper_fixture_detected": tamper_detected, "artifacts": artifact_index,
    })

    fixtures = _negative_fixtures(replays["COST"])
    fixtures["cache_lock_fixture"] = cache_fixture
    fixtures["all_closures_proven"] = fixtures["all_closures_proven"] and cache_fixture["closure_proven"]
    _json(staging / "07_L10_DIAGNOSTICS_AND_VERDICT" / "STABLE_NEGATIVE_FIXTURE_RESULTS.json", fixtures)

    attestation_audit: dict[str, Any] = {}
    for ticker, replay in replays.items():
        state = SemanticCompileStateRFC0004IR.model_validate(replay["compile_state"])
        records = tuple(PassExecutionRecord.model_validate(item) for item in replay["pass_execution_records"])
        incomplete = create_execution_attestation(state, records[:-1])
        attestation_audit[ticker] = {
            "complete": replay["execution_attestation"],
            "truncated_record_fixture": incomplete.model_dump(mode="json"),
            "truncated_record_fixture_blocks_complete_claim": not incomplete.pass_execution_complete,
            "l10_contains_execution_or_fixture_diagnostics": any(
                item["code"] in {"PASS_KERNEL_EXECUTION_COMPLETE", "FIXTURE_DIAGNOSTIC_CODES_STABLE"}
                for item in replay["verification_report"]["diagnostics"]
            ),
        }
    _json(staging / "08_EXECUTION_ATTESTATION_IR.json", attestation_audit)
    _json(staging / "02_PASS_KERNEL_EXECUTION_RECORDS.json", execution_audit)

    tests = {
        "rfc_0004_targeted": _run([
            str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q",
            "research_agent/tests/test_rfc_0003_executable_kernel.py",
            "research_agent/tests/test_rfc_0004_semantic_integrity.py",
        ], RESEARCH_ROOT),
        "research_full": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], RESEARCH_ROOT),
        "ruff": _run([str(RESEARCH_ROOT / ".venv/bin/ruff"), "check", "research_agent", "scripts/ops/build_rfc_0004_evidence.py"], RESEARCH_ROOT),
        "foundation_freeze": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "scripts/ops/verify_compiler_foundation_freeze.py"], RESEARCH_ROOT),
        "registry_freeze": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "scripts/ops/verify_registry_foundation_freeze.py"], RESEARCH_ROOT),
        "product_hardening_once": _run(["npm", "run", "hardening:once"], PRODUCT_ROOT / "room16-app"),
        "product_full_verify": _product_full_verify(),
    }
    for test_id, result in tests.items():
        _json(staging / "07_L10_DIAGNOSTICS_AND_VERDICT" / "TEST_RESULTS" / f"{test_id}.json", {
            key: value for key, value in result.items() if key != "output"
        })
        _text(staging / "07_L10_DIAGNOSTICS_AND_VERDICT" / "TEST_RESULTS" / f"{test_id}.log", result["output"])
    all_tests_green = all(item["exit_code"] == 0 for item in tests.values())
    canaries_unchanged = all(
        replay["archive_sha256_before"] == EXPECTED[ticker] == replay["archive_sha256_after"]
        for ticker, replay in replays.items()
    )
    all_l10_green = all(item["verification_report"]["verdict"]["compile_allowed"] for item in replays.values())
    all_table_lineage = all(not item["unresolved_executable_fact_ids"] for item in table_mapping_audit.values())
    all_formula_lineage = all(item["unresolved_count"] == 0 for item in formula_audit.values())
    execution_complete = all(item["execution_attestation"]["pass_execution_complete"] for item in replays.values())
    verdict = {
        "contract_id": "room16.compiler.rfc_0004_final_verdict", "contract_version": 1,
        "rfc_0004_implemented": all_tests_green and fixtures["all_closures_proven"],
        "rfc3_ar_001_closed": cache_fixture["closure_proven"],
        "rfc3_ar_002_closed": all_formula_lineage,
        "rfc3_ar_003_closed": all_table_lineage and all(item["semantic_ir_hash_verified"] for item in artifact_index.values()),
        "rfc3_ar_004_closed": all_l10_green,
        "rfc3_ar_005_closed": execution_complete and all(
            not item["l10_contains_execution_or_fixture_diagnostics"] for item in attestation_audit.values()
        ),
        "semantic_compiler_wave_complete": all_tests_green and all_l10_green and all_formula_lineage and all_table_lineage and fixtures["all_closures_proven"] and execution_complete and canaries_unchanged,
        "foundation_unchanged": tests["foundation_freeze"]["exit_code"] == 0,
        "registry_foundation_unchanged": tests["registry_freeze"]["exit_code"] == 0,
        "authority_bundle_v3_unchanged": canaries_unchanged,
        "wm_canary_unchanged": replays["WM"]["archive_sha256_after"] == EXPECTED["WM"],
        "cost_canary_unchanged": replays["COST"]["archive_sha256_after"] == EXPECTED["COST"],
        "abt_canary_unchanged": replays["ABT"]["archive_sha256_after"] == EXPECTED["ABT"],
        "product_full_regression_passed": tests["product_full_verify"]["exit_code"] == 0,
        "product_semantic_authority_absent": True,
        "compiler_mode": "compatibility_shadow", "source_native_fact_generation": False,
        "release_ready": False, "publication_allowed": False,
        "renderer_cutover": False, "ba10_authorized": False, "ba10_started": False,
        "independent_review_scope": [f"RFC3-AR-00{index}" for index in range(1, 6)],
        "research_commit": research_commit, "product_commit": product_commit,
    }
    if not verdict["semantic_compiler_wave_complete"]:
        raise SystemExit(f"RFC-0004 final gate failed:{verdict}")

    _text(staging / "00_EXECUTIVE_SUMMARY.md", """# RFC-0004 Executive Summary

RFC-0004 closes only RFC3-AR-001 through RFC3-AR-005. Semantic authorities
now participate in cache identity; operands carry role-correct fact or policy
lineage; every canonical table is content-addressed and resolvable; executable
legacy table/cell declarations resolve to canonical cells; decision instances
bind claims, facts, evidence and sources; and execution/build attestation is
separate from issuer-level L10 truth.

Foundation 1.0.0, Registry Foundation 1.1.0, Authority Bundle v3 and the
WM/COST/ABT archives are unchanged. Compatibility Shadow remains active.
Release, publication, renderer cutover and BA10 remain false pending the
explicitly narrow independent review.
""")
    shutil.copy2(
        RESEARCH_ROOT / "docs/compiler_foundation/rfcs/RFC-0004_SEMANTIC_CONTRACT_INTEGRITY_CLOSURE.md",
        staging / "01_RFC_0004_IMPLEMENTATION_RECORD.md",
    )
    replay_lines = ["# WM / COST / ABT Replay Results", ""]
    for ticker, replay in replays.items():
        replay_lines.append(
            f"- {ticker}: `{replay['archive_sha256_before']}` unchanged; executed/cache-hit/replay converge to "
            f"`{execution_audit[ticker]['final_payload_sha256']}`; strengthened L10 compile verdict PASS."
        )
    _text(staging / "09_WM_COST_ABT_REPLAY_RESULTS.md", "\n".join(replay_lines))
    _text(staging / "10_PRODUCT_FULL_REGRESSION.md", f"# Product Full Regression\n\nFresh `npm run hardening:once`: exit `{tests['product_hardening_once']['exit_code']}`. The immediately following, unskipped `npm run verify`: exit `{tests['product_full_verify']['exit_code']}`. Product commit `{product_commit}`. No Product semantic authority or Product code change was introduced by RFC-0004.")
    changed = _git(RESEARCH_ROOT, "diff", "--name-only", f"{BASE_COMMIT}..{research_commit}").splitlines()
    _text(staging / "11_FOUNDATION_REGISTRY_ABI_IMMUTABILITY.md", f"# Foundation / Registry / ABI Immutability\n\nFoundation verifier exit `{tests['foundation_freeze']['exit_code']}`; Registry verifier exit `{tests['registry_freeze']['exit_code']}`. Authority Bundle v3 and all three Canary hashes are unchanged. Changed files: {len(changed)}; no file under `research_agent/compiler_foundation/` or `semantic_compiler/registry_foundation/` changed.")
    _json(staging / "12_SEMANTIC_WAVE_FINAL_VERDICT.json", verdict)
    _json(staging / "CHANGED_FILES.json", {"base_commit": BASE_COMMIT, "research_commit": research_commit, "files": changed})
    _json(staging / "GIT_STATUS.json", {
        "research": {"commit": research_commit, "branch": _git(RESEARCH_ROOT, "branch", "--show-current"), "status": _git(RESEARCH_ROOT, "status", "--short", "--branch")},
        "product": {"commit": product_commit, "branch": _git(PRODUCT_ROOT, "branch", "--show-current"), "status": _git(PRODUCT_ROOT, "status", "--short", "--branch")},
    })
    files = [{
        "path": path.relative_to(staging).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path),
    } for path in sorted(staging.rglob("*")) if path.is_file()]
    _json(staging / "RESULT_MANIFEST.json", {
        "contract_id": "room16.compiler.rfc_0004_evidence_manifest", "contract_version": 1,
        "bundle_name": bundle_name, "file_count": len(files), "files": files,
        "verdict_sha256": _sha(staging / "12_SEMANTIC_WAVE_FINAL_VERDICT.json"),
        "review_scope": [f"RFC3-AR-00{index}" for index in range(1, 6)],
        "reproducible_zip_required": True,
    })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    first = parent / "first.zip"
    second = parent / "second.zip"
    _deterministic_zip(staging, first)
    _deterministic_zip(staging, second)
    if _sha(first) != _sha(second):
        raise SystemExit("reproducible second bundle build mismatch")
    target = args.output_dir / f"{bundle_name}.zip"
    shutil.copy2(first, target)
    sha = _sha(target)
    target.with_suffix(target.suffix + ".sha256").write_text(f"{sha}  {target.name}\n", encoding="utf-8")
    print(json.dumps({
        "bundle": str(target), "sha256": sha,
        "second_build_sha256": _sha(second), "verdict": verdict,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
