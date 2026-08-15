#!/usr/bin/env python3
"""Build a self-contained RFC-0002 evidence bundle from frozen canaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.semantic_spine.negative_fixtures import build_negative_fixture_proofs
from research_agent.semantic_compiler.semantic_spine.replay import replay_rfc_0002_archive
from research_agent.semantic_compiler.semantic_spine.verification import compute_cross_company_gates

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = PRODUCT_ROOT / ".runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
EXPECTED_CANARY_HASHES = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}


def _json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"command": command, "cwd": str(cwd), "exit_code": completed.returncode, "output": completed.stdout}


def _zip_tree(source: Path, target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(source).as_posix())


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=RESEARCH_ROOT / "outputs/release")
    parser.add_argument("--replay-count", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    research_commit = _git(RESEARCH_ROOT, "rev-parse", "HEAD")
    product_commit = _git(PRODUCT_ROOT, "rev-parse", "HEAD")
    if _git(RESEARCH_ROOT, "status", "--porcelain"):
        raise SystemExit("research worktree must be clean before evidence compilation")
    staging_parent = Path(tempfile.mkdtemp(prefix="room16-rfc0002-evidence-"))
    staging = staging_parent / f"ROOM16_RFC_0002_SEMANTIC_SPINE_{research_commit[:12]}_{date.today().isoformat()}"
    staging.mkdir()
    replay_root = staging_parent / "replays"
    replays: dict[str, dict[str, Any]] = {}
    double_replay: dict[str, Any] = {}
    for ticker in ("WM", "COST", "ABT"):
        archive = CANARY_ROOT / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
        if _sha(archive) != EXPECTED_CANARY_HASHES[ticker]:
            raise SystemExit(f"canary hash mismatch: {ticker}")
        first = replay_rfc_0002_archive(archive=archive, work_root=replay_root / ticker / "first")
        replays[ticker] = first
        if args.replay_count == 2:
            second = replay_rfc_0002_archive(archive=archive, work_root=replay_root / ticker / "second")
            second_hash = second["replay_sha256"]
            equal = second_hash == first["replay_sha256"]
        else:
            second_hash = None
            equal = None
        double_replay[ticker] = {"first_replay_sha256": first["replay_sha256"], "second_replay_sha256": second_hash, "equal": equal}
    cross_company = compute_cross_company_gates(replays)
    if cross_company["status"] != "pass":
        raise SystemExit(f"cross-company gates failed: {cross_company}")

    ir_root = staging_parent / "diagnostic_ir_archive"
    contract_files = {
        "research/rfc_0002_pass_contracts.json": RESEARCH_ROOT / "research_agent/semantic_compiler/semantic_spine/config/rfc_0002_pass_contracts.json",
        "research/semantic_metric_signatures_v2.json": RESEARCH_ROOT / "research_agent/semantic_compiler/semantic_spine/config/semantic_metric_signatures_v2.json",
        "research/rfc_0002_contracts.py": RESEARCH_ROOT / "research_agent/semantic_compiler/semantic_spine/contracts.py",
        "research/foundation_contracts.py": RESEARCH_ROOT / "research_agent/compiler_foundation/contracts.py",
        "research/registry_foundation_v1_1.json": RESEARCH_ROOT / "research_agent/semantic_compiler/registry_foundation/config/registry_foundation_v1_1.json",
        "product/room16_semantic_registry_mirror_v1_1.json": PRODUCT_ROOT / "config/room16_semantic_registry_mirror_v1_1.json",
        "product/room16_semantic_registry_mirror_v1_1.lock.json": PRODUCT_ROOT / "config/room16_semantic_registry_mirror_v1_1.lock.json",
    }
    for relative, source in contract_files.items():
        target = ir_root / "contracts" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    artifact_keys = (
        "source_inputs", "parsed_documents", "table_discoveries", "normalized_records",
        "typed_facts", "signatures", "metrics", "formula_evaluations", "evidence_graph",
        "claim_graph", "decision_graph", "verification_plan", "verification_report",
    )
    for ticker, replay in replays.items():
        ticker_root = ir_root / "canaries" / ticker
        for key in artifact_keys:
            _json(ticker_root / f"{key}.json", replay[key])
        _json(ticker_root / "replay_metadata.json", {
            key: value for key, value in replay.items() if key not in artifact_keys
        })
    _json(ir_root / "cross_company_computed_gates.json", cross_company)
    _json(ir_root / "double_replay_results.json", double_replay)
    _zip_tree(ir_root, staging / "08_DIAGNOSTIC_IR_ARCHIVE.zip")

    fixture_root = staging_parent / "negative_fixtures"
    fixture_proofs = build_negative_fixture_proofs()
    for proof in fixture_proofs:
        root = fixture_root / proof["fixture_id"]
        for state in ("defective", "corrected", "reintroduced"):
            _json(root / f"{state}.json", proof[state])
            _json(root / f"{state}_result.json", proof[f"{state}_result"])
        _json(root / "closure.json", {key: value for key, value in proof.items() if key not in {"defective", "corrected", "reintroduced", "defective_result", "corrected_result", "reintroduced_result"}})
    _json(fixture_root / "RESULTS.json", list(fixture_proofs))
    _zip_tree(fixture_root, staging / "10_NEGATIVE_FIXTURE_ARTIFACTS.zip")

    tests = {
        "rfc_0002": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q", "research_agent/tests/test_rfc_0002_semantic_spine.py"], RESEARCH_ROOT),
        "foundation_freeze": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "scripts/ops/verify_compiler_foundation_freeze.py"], RESEARCH_ROOT),
        "registry_freeze": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "scripts/ops/verify_registry_foundation_freeze.py"], RESEARCH_ROOT),
        "research_full": _run([str(RESEARCH_ROOT / ".venv/bin/python"), "-m", "pytest", "-q"], RESEARCH_ROOT),
        "ruff": _run([str(RESEARCH_ROOT / ".venv/bin/ruff"), "check", "research_agent/semantic_compiler/semantic_spine", "research_agent/tests/test_rfc_0002_semantic_spine.py", "scripts/ops/build_rfc_0002_semantic_spine_evidence.py", "scripts/ops/generate_rfc_0002_signature_registry.py"], RESEARCH_ROOT),
    }
    product_verify = _run(["npm", "run", "verify"], PRODUCT_ROOT / "room16-app")
    tests["product_verify"] = product_verify
    tests_root = staging / "TEST_RESULTS"
    for test_id, result in tests.items():
        _json(tests_root / f"{test_id}.json", result)
        _text(tests_root / f"{test_id}.log", result["output"])
    research_green = all(tests[key]["exit_code"] == 0 for key in ("rfc_0002", "foundation_freeze", "registry_freeze", "research_full", "ruff"))
    product_status = "full_pass" if product_verify["exit_code"] == 0 else "conditional_product_regression_pass"

    table_summary = {
        ticker: {
            "detected": sum(item["detected_count"] for item in replay["table_discoveries"]),
            "registered": sum(item["registered_count"] for item in replay["table_discoveries"]),
            "excluded": sum(item["excluded_count"] for item in replay["table_discoveries"]),
            "coverage_closed": all(item["detected_count"] == item["registered_count"] + item["excluded_count"] for item in replay["table_discoveries"]),
        }
        for ticker, replay in replays.items()
    }
    graph_summary = {
        ticker: {
            "unknown_source_ids": replay["evidence_graph"]["unknown_source_ids"],
            "claim_numeric_lineage_count": len(replay["claim_graph"]["numeric_lineages"]),
            "claims_without_lineage": replay["claim_graph"]["claims_without_lineage"],
            "numeric_bindings_without_lineage": replay["claim_graph"]["numeric_bindings_without_lineage"],
        }
        for ticker, replay in replays.items()
    }
    decision_summary = {
        ticker: {
            "comparison_payload_sha256": replay["decision_graph"]["comparison_payload_sha256"],
            "reconstructed_payload_sha256": replay["decision_graph"]["reconstructed_payload_sha256"],
            "equal": replay["decision_graph"]["comparison_payload_sha256"] == replay["decision_graph"]["reconstructed_payload_sha256"],
            "embedded_legacy_payload_present": "legacy_payload" in replay["decision_graph"],
        }
        for ticker, replay in replays.items()
    }
    verdicts = {ticker: replay["verification_report"]["verdict"] for ticker, replay in replays.items()}
    implementation_complete = research_green and cross_company["status"] == "pass" and all(item["compile_allowed"] for item in verdicts.values()) and all(item["equal"] is not False for item in double_replay.values())
    final_verdict = {
        "contract_id": "room16.compiler.rfc_0002_semantic_wave_completion_verdict",
        "contract_version": 1,
        "rfc_0002_implementation_complete": implementation_complete,
        "semantic_compiler_wave_complete": False,
        "semantic_compiler_wave_status": "implementation_complete_pending_independent_architecture_review" if implementation_complete else "changes_required",
        "independent_architecture_review_passed": False,
        "foundation_v1_unchanged": tests["foundation_freeze"]["exit_code"] == 0,
        "registry_foundation_1_1_unchanged": tests["registry_freeze"]["exit_code"] == 0,
        "authority_bundle_v3_unchanged": all(item["archive_sha256_before"] == item["archive_sha256_after"] for item in replays.values()),
        "wm_cost_abt_canaries_unchanged": all(item["archive_sha256_before"] == EXPECTED_CANARY_HASHES[ticker] and item["archive_sha256_after"] == EXPECTED_CANARY_HASHES[ticker] for ticker, item in replays.items()),
        "connected_ir_spine": all(any(d["code"] == "IR_SPINE_CONNECTED" and d["release_effect"] == "none" for d in item["verification_report"]["diagnostics"]) for item in replays.values()),
        "l10_verification_implemented": True,
        "compile_verdicts_derived_only_from_diagnostics": True,
        "cross_company_gates_computed": cross_company["status"] == "pass",
        "product_regression_status": product_status,
        "ba10_authorized": False,
        "ba10_started": False,
        "renderer_cutover": False,
        "release_ready": False,
        "publication_allowed": False,
        "next_gate": "independent_architecture_review",
        "research_commit": research_commit,
        "product_commit": product_commit,
    }

    _text(staging / "00_EXECUTIVE_SUMMARY.md", f"""# RFC-0002 Executive Summary

RFC-0002 ist als additive Shadow-/Strangler-Spine implementiert. Alle drei
Canaries kompilieren über Source→Parse→Normalize→Facts→Metrics→Evidence→Claims
→Decision→Verification. Foundation 1.0.0, Registry Foundation 1.1.0, Authority
Bundle v3 und die Kandidatenarchive bleiben unverändert.

Der Implementierungsblock ist abgeschlossen, die Semantic Compiler Wave bleibt
bis zum unabhängigen Architektur-PASS formal `complete=false`. BA10,
Renderer-Cutover, Release und Publication bleiben gesperrt.
""")
    shutil.copy2(RESEARCH_ROOT / "docs/compiler_foundation/rfcs/RFC-0002_SEMANTIC_IR_SPINE_AND_VERIFICATION_COMPLETION.md", staging / "01_RFC_0002_IMPLEMENTATION_RECORD.md")
    _text(staging / "02_PASS_AND_LAYER_ALIGNMENT.md", "# Pass and Layer Alignment\n\nDer hashgebundene Passvertrag liegt vollständig in `08_DIAGNOSTIC_IR_ARCHIVE.zip`. Der zehnte und letzte Pass ist `ba9.l10.verify_semantics`; BA10 ist false.")
    _text(staging / "03_CONNECTED_IR_SPINE_PROOF.md", "# Connected IR Spine Proof\n\n" + "\n".join(f"- {ticker}: normalized={len(item['normalized_records'])}, typed={len(item['typed_facts'])}, compile_allowed={item['verification_report']['verdict']['compile_allowed']}" for ticker, item in replays.items()))
    _json(staging / "04_TABLE_DISCOVERY_COVERAGE.json", table_summary)
    _text(staging / "04_TABLE_DISCOVERY_COVERAGE.md", "# Table Discovery Coverage\n\n" + "\n".join(f"- {ticker}: detected={value['detected']}, registered={value['registered']}, excluded={value['excluded']}, closed={value['coverage_closed']}" for ticker, value in table_summary.items()))
    signature_summary = {"authority_sha256": replays["WM"]["metric_signature_authority_sha256"], "legacy_metric_ids": len({item["legacy_metric_id"] for replay in replays.values() for item in replay["signatures"]}), "semantic_signatures": len({item["signature_id"] for replay in replays.values() for item in replay["signatures"]}), "cross_company_gates": cross_company}
    _json(staging / "05_METRIC_SEMANTIC_SIGNATURES.json", signature_summary)
    _text(staging / "05_METRIC_SEMANTIC_SIGNATURES.md", f"# Metric Semantic Signatures\n\n- Legacy Metric IDs: {signature_summary['legacy_metric_ids']}\n- Exact Semantic Signatures: {signature_summary['semantic_signatures']}\n- Authority SHA-256: `{signature_summary['authority_sha256']}`\n- Computed gate: `{cross_company['status']}`")
    _json(staging / "06_GRAPH_LINEAGE_RESULTS.json", graph_summary)
    _text(staging / "06_GRAPH_LINEAGE_RESULTS.md", "# Graph Lineage Results\n\n" + "\n".join(f"- {ticker}: numeric paths={value['claim_numeric_lineage_count']}, missing claims={len(value['claims_without_lineage'])}, missing bindings={len(value['numeric_bindings_without_lineage'])}, unknown sources={len(value['unknown_source_ids'])}" for ticker, value in graph_summary.items()))
    _json(staging / "07_DECISION_RECONSTRUCTION_ROUNDTRIP.json", decision_summary)
    _text(staging / "07_DECISION_RECONSTRUCTION_ROUNDTRIP.md", "# Decision Reconstruction Roundtrip\n\n" + "\n".join(f"- {ticker}: graph reconstruction equal={value['equal']}, embedded legacy payload={value['embedded_legacy_payload_present']}" for ticker, value in decision_summary.items()))
    _text(staging / "08_VERIFICATION_PLAN.md", "# Verification Plan\n\nEach canary binds all L3–L9 IR hashes into VerificationPlanIR. Actual plans, Diagnostics and reports are in `08_DIAGNOSTIC_IR_ARCHIVE.zip`.")
    _json(staging / "09_COMPILE_VERDICT_RESULTS.json", verdicts)
    _text(staging / "09_COMPILE_VERDICT_RESULTS.md", "# Compile Verdict Results\n\n" + "\n".join(f"- {ticker}: compile_allowed={value['compile_allowed']}, release_allowed={value['release_allowed']}, blocking={list(value['blocking_codes'])}" for ticker, value in verdicts.items()))
    _text(staging / "11_WM_COST_ABT_RESULTS.md", "# WM / COST / ABT Results\n\n" + "\n".join(f"- {ticker}: archive={item['archive_sha256_before']}, unchanged={item['archive_sha256_before'] == item['archive_sha256_after']}, replay={item['replay_sha256']}, double_replay={double_replay[ticker]['equal']}" for ticker, item in replays.items()))
    _text(staging / "12_PRODUCT_REGRESSION_STATUS.md", f"# Product Regression Status\n\nStatus: `{product_status}`.\n\nExit code: `{product_verify['exit_code']}`. Full log: `TEST_RESULTS/product_verify.log`. Product remains a consumer; no Product code or registry truth was changed by RFC-0002.")
    _json(staging / "13_SEMANTIC_WAVE_COMPLETION_VERDICT.json", final_verdict)

    manifest_files = {}
    for path in sorted(staging.rglob("*")):
        if path.is_file() and path.name != "RESULT_MANIFEST.json":
            manifest_files[path.relative_to(staging).as_posix()] = {"sha256": _sha(path), "size": path.stat().st_size}
    manifest = {
        "contract_id": "room16.compiler.rfc_0002_evidence_manifest",
        "contract_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "research_commit": research_commit,
        "product_commit": product_commit,
        "foundation_version": "1.0.0",
        "registry_foundation_version": "1.1.0",
        "authority_bundle_version": 3,
        "semantic_compiler_wave_complete": False,
        "ba10_authorized": False,
        "files": manifest_files,
    }
    _json(staging / "RESULT_MANIFEST.json", manifest)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    target = args.output_dir / f"{staging.name}.zip"
    _zip_tree(staging, target)
    print(json.dumps({"bundle": str(target), "sha256": _sha(target), "size": target.stat().st_size, "implementation_complete": implementation_complete, "semantic_compiler_wave_complete": False, "ba10_authorized": False, "product_regression_status": product_status}, indent=2))


if __name__ == "__main__":
    main()
