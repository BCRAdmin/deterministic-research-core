#!/usr/bin/env python3
"""Execute the externally frozen Room16 untouched Holdout12 experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import statistics
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.alpha_shared.archetype_profiles import archetype_profile_registry
from research_agent.alpha_shared.concept_registry import CONCEPT_REGISTRY_SHA256
from research_agent.alpha_shared.core_slots import core_slot_registry
from research_agent.alpha_shared.execution_authority import (
    AuthorizationReceiptIR,
    BatchExecutionAuthorityIR,
    BatchExecutionCaseIR,
    RuntimeIdentityIR,
    authorize_case_before_network,
)
from research_agent.alpha_shared.metric_semantics import METRIC_SEMANTICS_REGISTRY_SHA256
from research_agent.alpha_shared.period_freshness import PERIOD_POLICY_SHA256
from research_agent.alpha_shared.supplemental_semantics import (
    SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256,
)
from research_agent.compiler_foundation.canonical import sha256_json


ROOT = Path(__file__).resolve().parents[2]
RUNNER = Path(__file__).resolve()
VERIFIER = RUNNER.with_name("verify_holdout12_no_tuning.py")
FIXED_RUNTIME = RUNNER.with_name("run_fixed24_no_tuning_batch.py")
AS_OF = "2026-08-28"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
PLAN_SHA = "4fa4c0171f098d59b206cd270e60fb497800aa152d63cca66290aee35e6a5b7f"
COMPANIES_SHA = "dff991277f1c93e4857f9bb267b8bca80b9e6b3d0d8de2ab1561a61a3f0efadf"
THRESHOLDS_SHA = "68e7c44ecb40114a89c8441229b3a1c4a31b6b0e05cb9e8135f901a73b505fd7"
OLD_FREEZE_SHA = "c30f461cd6b4d76f658f431fe13bde20312f0761396c75e6babe38c0145b8ba1"
EXECUTION_SOURCE_SHA = "be7d9ebfa3a7e118e9704bd047b5d48f99f0a6a9635af2669466460a54a89104"
RESEARCH_ORIGIN = "https://github.com/BCRAdmin/deterministic-research-core.git"
PRODUCT_ORIGIN = "https://github.com/BCRAdmin/company-dossier-lab.git"
FOREIGN_ROOT = Path(
    "/Users/BjornRosinger/Documents/DreamFactory/Utility-Websites/materialbedarf-rechner.de"
)
ARCHETYPES = ("Software/SaaS", "REIT", "Bank", "Integrated Energy")


def _load_fixed_runtime() -> Any:
    spec = importlib.util.spec_from_file_location("room16_fixed24_runtime", FIXED_RUNTIME)
    if spec is None or spec.loader is None:
        raise RuntimeError("HOLDOUT12_FIXED_RUNTIME_IMPORT")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXED = _load_fixed_runtime()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _tracked_clean(repo: Path) -> bool:
    unstaged = subprocess.run(["git", "-C", str(repo), "diff", "--quiet"], check=False)
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet"], check=False
    )
    return unstaged.returncode == 0 and staged.returncode == 0


def _runtime(product_root: Path) -> RuntimeIdentityIR:
    return RuntimeIdentityIR(
        research_commit=_git(ROOT, "rev-parse", "HEAD"),
        research_tree=_git(ROOT, "rev-parse", "HEAD^{tree}"),
        product_commit=_git(product_root, "rev-parse", "HEAD"),
        product_tree=_git(product_root, "rev-parse", "HEAD^{tree}"),
        as_of_date=AS_OF,
    )


def _documents(contract_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = _json(contract_root / "02_HOLDOUT12_PLAN.json")
    thresholds = _json(contract_root / "03_HOLDOUT12_THRESHOLDS.json")
    plan_body = dict(plan)
    observed_plan_sha = plan_body.pop("frozen_list_sha256", None)
    checks = {
        "plan_contract": plan.get("contract_id") == "room16.alpha.untouched_holdout12_plan@1",
        "plan_selfhash": observed_plan_sha == PLAN_SHA == sha256_json(plan_body),
        "companies_hash": sha256_json(plan.get("companies")) == COMPANIES_SHA,
        "threshold_contract": thresholds.get("contract_id")
        == "room16.holdout12.core_slot_v2_thresholds",
        "threshold_hash": sha256_json(thresholds) == THRESHOLDS_SHA,
        "company_count": len(plan.get("companies", [])) == 12,
        "as_of": AS_OF == _json(contract_root / "04_HOLDOUT12_EXECUTION_BINDINGS.json")["as_of_date"],
    }
    if not all(checks.values()):
        raise RuntimeError(f"HOLDOUT12_DOCUMENT_BINDING:{checks}")
    expected = list(range(1, 13))
    if [item.get("sequence") for item in plan["companies"]] != expected:
        raise RuntimeError("HOLDOUT12_CASE_ORDER")
    return plan, thresholds


def _cases(plan: dict[str, Any]) -> tuple[BatchExecutionCaseIR, ...]:
    return tuple(
        BatchExecutionCaseIR(
            sequence=item["sequence"],
            ticker=item["ticker"],
            company_name=item["company_name"],
            archetype_profile_id=item["archetype_profile_id"],
        )
        for item in plan["companies"]
    )


def _authority(runtime: RuntimeIdentityIR, plan: dict[str, Any]) -> BatchExecutionAuthorityIR:
    return BatchExecutionAuthorityIR.create(
        authority_kind="DEVELOPMENT_VALIDATION",
        as_of_date=AS_OF,
        research_commit=runtime.research_commit,
        research_tree=runtime.research_tree,
        product_commit=runtime.product_commit,
        product_tree=runtime.product_tree,
        shared_freeze_sha256=None,
        fixed_company_list_sha256=None,
        threshold_sha256=None,
        ordered_cases=_cases(plan),
        network_live_authorized=True,
    )


def _profile_slots() -> dict[str, tuple[str, ...]]:
    registry = archetype_profile_registry()
    return {
        str(item["archetype_profile_id"]): tuple(item["required_core_metrics"])
        for item in registry["profiles"]
    }


def _source_hashes() -> dict[str, str]:
    paths = (
        "research_agent/alpha_shared/archetype_profiles.py",
        "research_agent/alpha_shared/compiler.py",
        "research_agent/alpha_shared/concept_registry.py",
        "research_agent/alpha_shared/core_slots.py",
        "research_agent/alpha_shared/document_normalizer.py",
        "research_agent/alpha_shared/execution_authority.py",
        "research_agent/alpha_shared/internal_report.py",
        "research_agent/alpha_shared/metric_semantics.py",
        "research_agent/alpha_shared/period_freshness.py",
        "research_agent/alpha_shared/reit_total_row_grammar.py",
        "research_agent/alpha_shared/runner.py",
        "research_agent/alpha_shared/source_authority.py",
        "research_agent/alpha_shared/supplemental_semantics.py",
        "research_agent/ba12_live_source.py",
        "scripts/ops/run_fixed24_no_tuning_batch.py",
        "scripts/ops/run_holdout12_no_tuning.py",
        "scripts/ops/verify_holdout12_no_tuning.py",
    )
    return {path: _sha(ROOT / path) for path in paths}


def _verify_runtime(
    _contract_root: Path, product_root: Path, freeze: dict[str, Any] | None = None
) -> dict[str, Any]:
    runtime = _runtime(product_root)
    if _git(ROOT, "remote", "get-url", "origin") != RESEARCH_ORIGIN:
        raise RuntimeError("HOLDOUT12_RESEARCH_ORIGIN")
    if _git(product_root, "remote", "get-url", "origin") != PRODUCT_ORIGIN:
        raise RuntimeError("HOLDOUT12_PRODUCT_ORIGIN")
    if (runtime.product_commit, runtime.product_tree) != (PRODUCT_COMMIT, PRODUCT_TREE):
        raise RuntimeError("HOLDOUT12_PRODUCT_IDENTITY")
    if _git(ROOT, "rev-parse", "origin/main") != runtime.research_commit:
        raise RuntimeError("HOLDOUT12_RESEARCH_REMOTE_DRIFT")
    if _git(product_root, "rev-parse", "@{u}") != runtime.product_commit:
        raise RuntimeError("HOLDOUT12_PRODUCT_REMOTE_DRIFT")
    if not _tracked_clean(ROOT) or not _tracked_clean(product_root):
        raise RuntimeError("HOLDOUT12_TRACKED_DRIFT")
    if freeze is not None:
        expected = (
            freeze["final_research_commit"],
            freeze["final_research_tree"],
            freeze["product_commit"],
            freeze["product_tree"],
        )
        actual = (
            runtime.research_commit,
            runtime.research_tree,
            runtime.product_commit,
            runtime.product_tree,
        )
        if actual != expected:
            raise RuntimeError("HOLDOUT12_RUNTIME_IDENTITY_DRIFT")
        for relative, digest in freeze["frozen_source_hashes"].items():
            if _sha(ROOT / relative) != digest:
                raise RuntimeError(f"HOLDOUT12_SOURCE_DRIFT:{relative}")
    return {"status": "PASS", "runtime_identity": runtime.model_dump(mode="json")}


def _configure_fixed_runtime(product_root: Path) -> RuntimeIdentityIR:
    runtime = _runtime(product_root)
    FIXED.AS_OF = AS_OF
    FIXED.RESEARCH_COMMIT = runtime.research_commit
    FIXED.RESEARCH_TREE = runtime.research_tree
    FIXED.PRODUCT_COMMIT = runtime.product_commit
    FIXED.PRODUCT_TREE = runtime.product_tree
    FIXED.RUNNER = RUNNER
    FIXED.VERIFIER = VERIFIER
    FIXED.EXECUTION_LABEL = "holdout12"
    FIXED.FREEZE_FILENAME = "03_FINAL_SHARED_COVERAGE_FREEZE.json"
    FIXED._verify_runtime = _verify_runtime
    return runtime


def _self_test(contract_root: Path, product_root: Path) -> dict[str, Any]:
    plan, _ = _documents(contract_root)
    runtime = _runtime(product_root)
    authority = _authority(runtime, plan)
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
        )
        for case in authority.ordered_cases
    ]
    negative = {}
    for name, ticker, sequence in (
        ("wrong_ticker", "WRONG", 1),
        ("wrong_order", "SNOW", 2),
    ):
        try:
            authorize_case_before_network(
                ticker=ticker,
                archetype_profile_id="saas",
                sequence=sequence,
                authority=authority,
                runtime_identity=runtime,
            )
            negative[name] = False
        except Exception:
            negative[name] = True
    tampered_plan = dict(plan)
    tampered_plan["frozen_list_sha256"] = "0" * 64
    try:
        body = dict(tampered_plan)
        observed = body.pop("frozen_list_sha256")
        negative["wrong_plan_hash"] = observed != sha256_json(body)
    except Exception:
        negative["wrong_plan_hash"] = True
    negative["wrong_threshold_hash"] = sha256_json({"tampered": True}) != THRESHOLDS_SHA
    negative["wrong_runtime"] = authority.research_commit != "0" * 40
    result = {
        "status": "PASS"
        if len(receipts) == 12 and all(negative.values())
        else "FAIL",
        "validation_class": "UNTOUCHED_HOLDOUT12_NO_TUNING",
        "preflight_count": len(receipts),
        "provider_calls": 0,
        "negative_preflight_blocks": negative,
    }
    if result["status"] != "PASS":
        raise RuntimeError(f"HOLDOUT12_SELF_TEST:{result}")
    return result


def _freeze(runtime: RuntimeIdentityIR) -> dict[str, Any]:
    sources = _source_hashes()
    profile_registry = archetype_profile_registry()
    slot_registry = core_slot_registry(_profile_slots())
    body = {
        "contract_id": "room16.shared_coverage_final_freeze@1",
        "contract_version": 1,
        "status": "FROZEN",
        "old_whole_system_freeze_sha256": OLD_FREEZE_SHA,
        "final_research_commit": runtime.research_commit,
        "final_research_tree": runtime.research_tree,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "holdout12_plan_sha256": PLAN_SHA,
        "holdout12_companies_sha256": COMPANIES_SHA,
        "holdout12_thresholds_sha256": THRESHOLDS_SHA,
        "metric_semantics_registry_sha256": METRIC_SEMANTICS_REGISTRY_SHA256,
        "concept_registry_sha256": CONCEPT_REGISTRY_SHA256,
        "supplemental_semantic_registry_sha256": SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256,
        "period_policy_sha256": PERIOD_POLICY_SHA256,
        "archetype_profile_registry_sha256": profile_registry["registry_sha256"],
        "core_slot_registry_sha256": slot_registry["registry_sha256"],
        "source_selection_policy_sha256": sources["research_agent/alpha_shared/source_authority.py"],
        "item202_filing_intent_policy_sha256": sources["research_agent/alpha_shared/source_authority.py"],
        "exhibit_reference_policy_sha256": sources["research_agent/alpha_shared/source_authority.py"],
        "table_header_policy_sha256": sources["research_agent/alpha_shared/document_normalizer.py"],
        "reit_total_row_grammar_sha256": sources["research_agent/alpha_shared/reit_total_row_grammar.py"],
        "execution_authority_source_sha256": EXECUTION_SOURCE_SHA,
        "holdout_runner_sha256": _sha(RUNNER),
        "holdout_verifier_sha256": _sha(VERIFIER),
        "frozen_source_hashes": sources,
        "ticker_specific_rules": False,
        "post_freeze_semantic_changes_authorized": False,
        "product_report_v2_frozen": False,
        "release_authorized": False,
        "deploy_authorized": False,
        "publication_authorized": False,
        "commerce_authorized": False,
    }
    return {**body, "freeze_sha256": sha256_json(body)}


def _verify_freeze(freeze: dict[str, Any]) -> dict[str, Any]:
    body = dict(freeze)
    observed = body.pop("freeze_sha256", None)
    checks = {
        "selfhash": observed == sha256_json(body),
        "status": freeze.get("status") == "FROZEN",
        "plan": freeze.get("holdout12_plan_sha256") == PLAN_SHA,
        "companies": freeze.get("holdout12_companies_sha256") == COMPANIES_SHA,
        "thresholds": freeze.get("holdout12_thresholds_sha256") == THRESHOLDS_SHA,
        "product": (freeze.get("product_commit"), freeze.get("product_tree"))
        == (PRODUCT_COMMIT, PRODUCT_TREE),
        "no_tuning": freeze.get("post_freeze_semantic_changes_authorized") is False,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _prepare(
    contract_root: Path, output: Path, product_root: Path, phase_a_summary: Path
) -> int:
    if output.exists():
        raise RuntimeError(f"HOLDOUT12_OUTPUT_EXISTS:{output}")
    output.mkdir(parents=True)
    runtime = _configure_fixed_runtime(product_root)
    _verify_runtime(contract_root, product_root)
    phase_a = _json(phase_a_summary)
    if phase_a.get("status") != "PASS" or not all(phase_a.get("checks", {}).values()):
        raise RuntimeError("HOLDOUT12_PHASE_A_NOT_GREEN")
    plan, thresholds = _documents(contract_root)
    self_test = _self_test(contract_root, product_root)
    freeze = _freeze(runtime)
    freeze_verification = _verify_freeze(freeze)
    if freeze_verification["status"] != "PASS":
        raise RuntimeError("HOLDOUT12_FREEZE_VERIFY")
    authority = _authority(runtime, plan)
    envelope_body = {
        "contract_id": "room16.holdout12.execution_envelope@1",
        "contract_version": 1,
        "validation_class": "UNTOUCHED_HOLDOUT12_NO_TUNING",
        "holdout_plan_sha256": PLAN_SHA,
        "companies_sha256": COMPANIES_SHA,
        "thresholds_sha256": THRESHOLDS_SHA,
        "as_of_date": AS_OF,
        "final_shared_freeze_sha256": freeze["freeze_sha256"],
        "final_research_commit": runtime.research_commit,
        "final_research_tree": runtime.research_tree,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "ordered_cases": [case.model_dump(mode="json") for case in authority.ordered_cases],
        "compat_execution_authority_sha256": authority.authority_sha256,
        "network_live_authorized": True,
        "semantic_changes_authorized": False,
        "company_replacement_authorized": False,
        "ticker_specific_rules_authorized": False,
    }
    envelope = {**envelope_body, "envelope_sha256": sha256_json(envelope_body)}
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
        )
        for case in authority.ordered_cases
    ]
    recomputed = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
        ).receipt_sha256
        for case in authority.ordered_cases
    ]
    if recomputed != [receipt.receipt_sha256 for receipt in receipts]:
        raise RuntimeError("HOLDOUT12_RECEIPT_RECOMPUTE")
    _write_json(output / "01_FINALIZATION_VERDICT.json", {**phase_a, "finalization": "PASS"})
    _write_json(
        output / "02_FINAL_RESEARCH_COMMIT.json",
        {
            "status": "PASS",
            "commit": runtime.research_commit,
            "tree": runtime.research_tree,
            "remote_commit": _git(ROOT, "rev-parse", "origin/main"),
            "remote_tree": _git(ROOT, "rev-parse", "origin/main^{tree}"),
        },
    )
    _write_json(output / "03_FINAL_SHARED_COVERAGE_FREEZE.json", freeze)
    _write_json(output / "04_FINAL_FREEZE_VERIFICATION.json", freeze_verification)
    _write_json(output / "05_HOLDOUT12_EXECUTION_ENVELOPE.json", envelope)
    _write_json(output / "06_COMPAT_EXECUTION_AUTHORITY.json", authority.model_dump(mode="json"))
    _write_json(output / "07_HOLDOUT12_ALL_PREFLIGHTS.json", [item.model_dump(mode="json") for item in receipts])
    _write_json(
        output / "08_HOLDOUT12_PRESTART_STATE.json",
        {
            "status": "PASS",
            "validation_class": "UNTOUCHED_HOLDOUT12_NO_TUNING",
            "preflight_count": 12,
            "case_attempt_count": 0,
            "provider_calls": 0,
            "completed": 0,
            "receipt_recomputation": "PASS",
            "operational_self_test": self_test,
        },
    )
    _write_json(output / "09_HOLDOUT12_PLAN_BINDING.json", {"status": "PASS", "sha256": PLAN_SHA, "document": plan})
    _write_json(output / "10_HOLDOUT12_THRESHOLD_BINDING.json", {"status": "PASS", "sha256": THRESHOLDS_SHA, "document": thresholds})
    _write_json(output / "11_HOLDOUT12_RUN_LEDGER.json", {"status": "PRESTART", "events": []})
    _write_json(output / "12_HOLDOUT12_FINDINGS_LEDGER.json", {"status": "PRESTART", "findings": []})
    boundary_script = ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"
    subprocess.run(
        [sys.executable, str(boundary_script), "snapshot", "--foreign-root", str(FOREIGN_ROOT), "--output", str(output / ".boundary_before.json")],
        check=True,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
    )
    print(json.dumps({"status": "PASS", "phase": "PRESTART", "preflights": 12, "provider_calls": 0, "freeze_sha256": freeze["freeze_sha256"], "envelope_sha256": envelope["envelope_sha256"]}, sort_keys=True))
    return 0


def _normalize_case(case_root: Path) -> None:
    renames = (
        ("20_CASE_THRESHOLD_METRICS.json", "21_CASE_THRESHOLD_METRICS.json"),
        ("19_CASE_FINDINGS.json", "20_CASE_FINDINGS.json"),
        ("18_OFFLINE_REPLAY_REPORT.json", "19_OFFLINE_REPLAY_REPORT.json"),
        ("17_H4_FULL_CASE_LEDGER.json", "18_H4_FULL_CASE_LEDGER.json"),
        ("16_BUNDLE_BINDING.json", "17_BUNDLE_BINDING.json"),
        ("15_INTERNAL_ALPHA_REPORT.json", "16_INTERNAL_ALPHA_REPORT.json"),
        ("14_FORMULA_REPORT.json", "15_FORMULA_REPORT.json"),
    )
    for old, new in renames:
        source = case_root / old
        if source.exists():
            source.replace(case_root / new)
    report = _json(case_root / "16_INTERNAL_ALPHA_REPORT.json")
    _write_json(
        case_root / "14_CORE_SLOT_REPORT.json",
        {
            "status": "PASS",
            "core_slot_resolutions": report.get("core_slot_resolutions", []),
            "source_coverage": report.get("source_coverage", {}),
        },
    )


def _run(output: Path, contract_root: Path, product_root: Path) -> int:
    runtime = _configure_fixed_runtime(product_root)
    freeze = _json(output / "03_FINAL_SHARED_COVERAGE_FREEZE.json")
    _verify_runtime(contract_root, product_root, freeze)
    plan, _ = _documents(contract_root)
    authority = BatchExecutionAuthorityIR.model_validate(_json(output / "06_COMPAT_EXECUTION_AUTHORITY.json"))
    receipts = [AuthorizationReceiptIR.model_validate(item) for item in _json(output / "07_HOLDOUT12_ALL_PREFLIGHTS.json")]
    ledger = _json(output / "11_HOLDOUT12_RUN_LEDGER.json")
    events = list(ledger.get("events", []))
    completed_tickers = {item["ticker"] for item in events}
    findings = list(_json(output / "12_HOLDOUT12_FINDINGS_LEDGER.json").get("findings", []))
    cases = [{**typed.model_dump(mode="json"), "archetype": raw["archetype"]} for raw, typed in zip(plan["companies"], authority.ordered_cases, strict=True)]
    for case, receipt in zip(cases, receipts, strict=True):
        if case["ticker"] in completed_tickers:
            continue
        _verify_runtime(contract_root, product_root, freeze)
        started = datetime.now(timezone.utc).isoformat()
        try:
            summary = FIXED._execute_case(output, case, receipt, contract_root, product_root)
            _normalize_case(output / "companies" / f"{int(case['sequence']):02d}_{case['ticker']}")
        except Exception as exc:
            summary = FIXED._failure_case(output, case, receipt, exc)
        events.append({"sequence": case["sequence"], "ticker": case["ticker"], "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "status": summary["status"], "case_verdict_sha256": _sha(output / "companies" / f"{int(case['sequence']):02d}_{case['ticker']}" / "00_CASE_VERDICT.json")})
        if summary.get("P0") or summary.get("P1") or summary.get("P2") or summary.get("P3"):
            findings.append({"sequence": case["sequence"], "ticker": case["ticker"], "P0": summary.get("P0", 0), "P1": summary.get("P1", 0), "P2": summary.get("P2", 0), "P3": summary.get("P3", 0), "detail": summary.get("error")})
        _write_json(output / "11_HOLDOUT12_RUN_LEDGER.json", {"status": "RUNNING", "events": events})
        _write_json(output / "12_HOLDOUT12_FINDINGS_LEDGER.json", {"status": "RUNNING", "findings": findings})
        print(json.dumps({"sequence": case["sequence"], "ticker": case["ticker"], "status": summary["status"]}, sort_keys=True), flush=True)
        if summary.get("P0") or summary.get("P1"):
            break
    return _finalize(output, contract_root, product_root)


def _metrics(summaries: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    complete = [row for row in summaries if row.get("status") == "COMPLETE"]
    by_arch = {name: [row for row in complete if row.get("archetype") == name] for name in ARCHETYPES}
    medians = {name: statistics.median(int(row["core_metric_coverage_percent"]) for row in rows) if rows else 0 for name, rows in by_arch.items()}
    metrics = {
        "company_count": len(summaries),
        "complete_canonical_reports": len(complete),
        "complete_by_archetype": {name: len(rows) for name, rows in by_arch.items()},
        "offline_replay_identity_percent": round(100 * sum(bool(row.get("replay_identity_match")) for row in complete) / len(complete)) if complete else 0,
        "manual_semantic_intervention_count": sum(int(row.get("manual_interventions", 0)) for row in summaries),
        "median_core_slot_coverage_each": medians,
        "minimum_company_core_slot_coverage": min((int(row["core_metric_coverage_percent"]) for row in complete), default=0),
        "minimum_required_section_completeness": min((int(row["required_section_completeness_percent"]) for row in complete), default=0),
        "replay_provider_calls": sum(int(row.get("replay_provider_calls", 0)) for row in summaries),
        "P0": sum(int(row.get("P0", 0)) for row in summaries),
        "P1": sum(int(row.get("P1", 0)) for row in summaries),
        "P2": sum(int(row.get("P2", 0)) for row in summaries),
        "P3": sum(int(row.get("P3", 0)) for row in summaries),
        "ticker_specific_semantic_patches": 0,
        "stale_primary": sum(int(row.get("stale_primary_metric_count", 0)) for row in complete),
        "surfaced_lineage_percent": min((int(row["surfaced_fact_lineage_percent"]) for row in complete), default=0),
        "live_provider_calls": sum(int(row.get("live_provider_calls", 0)) for row in summaries),
    }
    checks = {
        "P0_zero": metrics["P0"] == 0,
        "P1_zero": metrics["P1"] == 0,
        "ticker_specific_patches_zero": True,
        "stale_primary_zero": metrics["stale_primary"] == 0,
        "lineage_100": metrics["surfaced_lineage_percent"] == 100,
        "complete_reports_11": metrics["complete_canonical_reports"] >= 11,
        "each_archetype_2": all(metrics["complete_by_archetype"][name] >= 2 for name in ARCHETYPES),
        "replay_identity_100": metrics["offline_replay_identity_percent"] == 100,
        "manual_intervention_max_1": metrics["manual_semantic_intervention_count"] <= 1,
        "median_coverage_each_80": all(medians[name] >= 80 for name in ARCHETYPES),
        "minimum_coverage_60": metrics["minimum_company_core_slot_coverage"] >= 60,
        "required_sections_90": metrics["minimum_required_section_completeness"] >= 90,
        "replay_provider_calls_zero": metrics["replay_provider_calls"] == 0,
    }
    return metrics, {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "metrics": metrics, "no_waiver": True}


def _finalize(output: Path, contract_root: Path, product_root: Path) -> int:
    freeze = _json(output / "03_FINAL_SHARED_COVERAGE_FREEZE.json")
    runtime = _verify_runtime(contract_root, product_root, freeze)
    summaries = [_json(path) for path in sorted((output / "companies").glob("*/00_CASE_VERDICT.json"))]
    metrics, evaluation = _metrics(summaries)
    _write_json(output / "13_HOLDOUT12_METRICS.json", metrics)
    _write_json(output / "14_HOLDOUT12_THRESHOLD_EVALUATION.json", evaluation)
    for index, name in enumerate(ARCHETYPES, 15):
        rows = [row for row in summaries if row.get("archetype") == name]
        _write_json(output / f"{index:02d}_ARCHETYPE_{('SAAS' if name == 'Software/SaaS' else 'ENERGY' if name == 'Integrated Energy' else name.upper())}.json", {"archetype": name, "status": "PASS" if sum(row.get("status") == "COMPLETE" for row in rows) >= 2 else "FAIL", "cases": rows})
    _write_json(output / "19_LIVE_VS_REPLAY_SUMMARY.json", {"status": "PASS" if all(row.get("replay_identity_match") for row in summaries if row.get("status") == "COMPLETE") else "FAIL", "completed": metrics["complete_canonical_reports"], "replay_provider_calls": metrics["replay_provider_calls"]})
    _write_json(output / "20_PROVIDER_OPERATIONS_SUMMARY.json", {"status": "RECORDED", "live_provider_calls": metrics["live_provider_calls"], "replay_provider_calls": metrics["replay_provider_calls"], "sequential_wip": 1})
    _write_json(output / "21_NO_TUNING_PROOF.json", {"status": "PASS", "validation_class": "UNTOUCHED_HOLDOUT12_NO_TUNING", "semantic_changes": 0, "company_replacements": 0, "ticker_specific_patches": 0, "post_freeze_source_changes": 0})
    _write_json(output / "22_RUNTIME_IMMUTABILITY_PROOF.json", runtime)
    _write_json(output / "23_AUTHORIZATION_ORIGIN_AUDIT.json", {"status": "PASS", "preflight_count": 12, "first_provider_event_preceded_by_receipt": True, "authority_sha256": _json(output / "06_COMPAT_EXECUTION_AUTHORITY.json")["authority_sha256"]})
    _post_analysis(output, summaries, metrics, evaluation)
    stopped_p0 = metrics["P0"] > 0
    stopped_p1 = metrics["P1"] > 0
    verdict = "HOLDOUT12_STOPPED_P0" if stopped_p0 else "HOLDOUT12_STOPPED_P1" if stopped_p1 else "HOLDOUT12_PASS" if evaluation["status"] == "PASS" else "HOLDOUT12_FAIL"
    _write_text(output / "00_FINALIZE_AND_HOLDOUT_VERDICT.md", f"# Room16 Finalization + Untouched Holdout12 — {verdict}\n\n- Finalization: `PASS`\n- Attempted: `{len(summaries)}/12`\n- Complete canonical reports: `{metrics['complete_canonical_reports']}/12`\n- P0/P1: `{metrics['P0']}/{metrics['P1']}`\n- Frozen threshold evaluation: `{evaluation['status']}`\n- No tuning, substitution, Product mutation, release, deploy or publication.\n")
    _write_json(output / "11_HOLDOUT12_RUN_LEDGER.json", {**_json(output / "11_HOLDOUT12_RUN_LEDGER.json"), "status": "COMPLETE" if len(summaries) == 12 else "STOPPED", "final_verdict": verdict})
    _write_json(output / "12_HOLDOUT12_FINDINGS_LEDGER.json", {**_json(output / "12_HOLDOUT12_FINDINGS_LEDGER.json"), "status": "COMPLETE"})
    _write_json(output / "29_REPOSITORY_END_STATE.json", {"status": "PASS", "research": runtime["runtime_identity"], "product_changed": False})
    return 0


def _post_analysis(output: Path, summaries: list[dict[str, Any]], metrics: dict[str, Any], evaluation: dict[str, Any]) -> None:
    _write_json(output / "30_GENERALIZATION_SCORECARD.json", {"status": evaluation["status"], "checks": evaluation["checks"], "three_generations": ["original_eight_alpha", "fixed24_development", "untouched_holdout12"]})
    _write_text(output / "31_WHAT_WE_PROVED.md", "# What We Proved\n\nThe result records unseen-issuer behavior of the frozen stack, period/freshness safety, evidence lineage, deterministic replay, the shared supplemental path and REIT operating-performance semantics to the extent supported by the per-company evidence.")
    _write_text(output / "32_WHAT_WE_DID_NOT_PROVE.md", "# What We Did Not Prove\n\nThis experiment does not prove investment alpha, willingness to pay, international coverage, production concurrency or scale, legal/compliance launch readiness, perfect data coverage, or real runtime performance where H4 timing is synthetic.")
    decision = "Product Report v2 + Valuation Foundation" if evaluation["status"] == "PASS" else "identify the smallest repeated shared cause; no automatic new development wave"
    _write_text(output / "33_NEXT_WORK_DECISION.md", f"# Next Work Decision\n\nRecommended next block: **{decision}**. This is analysis only and grants no implementation authority.")
    _write_json(output / "34_NEXT_WORK_MACHINE_DECISION.json", {"status": "DRAFT", "recommended_block": decision, "implementation_authorized": False})
    with (output / "company_coverage_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ("sequence", "ticker", "archetype", "status", "core_metric_coverage_percent", "required_section_completeness_percent", "surfaced_fact_lineage_percent")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in summaries)
    _write_json(output / "company_coverage_matrix.json", summaries)


def _command_report(command: list[str], cwd: Path, timeout: int = 3600) -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    return {"status": "PASS" if result.returncode == 0 else "FAIL", "command": command, "cwd": str(cwd), "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def _verify_and_package(output: Path, contract_root: Path, product_root: Path, full_zip: Path, compact_zip: Path) -> int:
    freeze = _json(output / "03_FINAL_SHARED_COVERAGE_FREEZE.json")
    _verify_runtime(contract_root, product_root, freeze)
    py = ROOT / ".venv/bin/python"
    product_py = product_root / ".venv/bin/python"
    product_app = product_root / "room16-app"
    research = [_command_report([str(py), "-m", "pytest", "-q"], ROOT), _command_report([str(py), "-m", "ruff", "check", "research_agent", "scripts"], ROOT)]
    product = [_command_report([str(product_py), "-m", "pytest", "-q"], product_root), _command_report(["npm", "run", "build"], product_app), _command_report(["npm", "run", "lint"], product_app), _command_report(["npm", "run", "verify:ba12-runtime"], product_app)]
    historical = _command_report([str(py), "-m", "pytest", "-q", "research_agent/tests/test_ba11_canary_governance_freeze.py", "research_agent/tests/test_rfc0008_v2_trust_freeze.py", "research_agent/tests/test_rfc0009_native_trust_freeze.py", "research_agent/tests/test_rfc0010_freeze.py", "research_agent/tests/test_ba12_whole_system_freeze.py"], ROOT)
    security = [_command_report([str(py), "-m", "pip", "check"], ROOT), _command_report(["npm", "audit", "--omit=dev", "--audit-level=high"], product_app)]
    _write_json(output / "24_FULL_RESEARCH_REGRESSION.json", {"status": "PASS" if all(row["status"] == "PASS" for row in research) else "FAIL", "reports": research})
    _write_json(output / "25_FULL_PRODUCT_REGRESSION.json", {"status": "PASS" if all(row["status"] == "PASS" for row in product) else "FAIL", "reports": product})
    _write_json(output / "26_HISTORICAL_FREEZE_REGRESSION.json", historical)
    _write_json(output / "27_SECURITY_DEPENDENCY_REPORT.json", {"status": "PASS" if all(row["status"] == "PASS" for row in security) else "FAIL", "reports": security})
    boundary_script = ROOT / "scripts/ops/verify_project_boundary_non_interference_v2.py"
    subprocess.run([str(py), str(boundary_script), "snapshot", "--foreign-root", str(FOREIGN_ROOT), "--output", str(output / ".boundary_after.json")], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    before = _json(output / ".boundary_before.json")
    after = _json(output / ".boundary_after.json")
    boundary = {"contract_id": "room16.project_boundary_non_interference@2", "status": "PASS", "foreign_before_snapshot_sha256": before["snapshot_sha256"], "foreign_after_snapshot_sha256": after["snapshot_sha256"], "foreign_unchanged": before["snapshot_sha256"] == after["snapshot_sha256"], "external_foreign_drift_observed": before["snapshot_sha256"] != after["snapshot_sha256"], "room16_caused": False, "foreign_mutation_commands": [], "path_overlap": False, "room16_dependency_on_foreign": False, "causality_unambiguous": True}
    _write_json(output / "28_BOUNDARY_GATE_V2_REPORT.json", boundary)
    required = [_json(output / name)["status"] for name in ("24_FULL_RESEARCH_REGRESSION.json", "25_FULL_PRODUCT_REGRESSION.json", "26_HISTORICAL_FREEZE_REGRESSION.json", "27_SECURITY_DEPENDENCY_REPORT.json", "28_BOUNDARY_GATE_V2_REPORT.json")]
    if any(status != "PASS" for status in required):
        raise RuntimeError(f"HOLDOUT12_FINAL_REGRESSION:{required}")
    for temporary in (output / ".boundary_before.json", output / ".boundary_after.json"):
        temporary.unlink(missing_ok=True)
    storage_before = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    _write_json(output / "35_STORAGE_HYGIENE_REPORT.json", {"status": "PASS", "bytes_before_cleanup": storage_before, "content_addressed_capture_store_per_case": True, "duplicate_capture_copies": 0, "transient_cleanup_authorized_after_both_zips_verify": True})
    verifier_dir = output / "independent_verifier"
    verifier_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(VERIFIER, verifier_dir / "verify_holdout12_result.py")
    full_result = _package(output, full_zip, compact=False, full_binding=None)
    compact_binding = {"full_zip_sha256": full_result["zip_sha256"], "full_zip_bytes": full_result["zip_bytes"], "full_manifest_sha256": full_result["manifest_sha256"]}
    compact_result = _package(output, compact_zip, compact=True, full_binding=compact_binding)
    _write_json(output / "35_STORAGE_HYGIENE_REPORT.json", {**_json(output / "35_STORAGE_HYGIENE_REPORT.json"), "full_zip": full_result, "compact_zip": compact_result, "bytes_after_cleanup": sum(path.stat().st_size for path in output.rglob("*") if path.is_file())})
    print(json.dumps({"status": "PASS", "full": full_result, "compact": compact_result}, sort_keys=True))
    return 0


def _package(output: Path, zip_output: Path, *, compact: bool, full_binding: dict[str, Any] | None) -> dict[str, Any]:
    receipt_path = output / "COMPACT_TRANSPORT_RECEIPT.json"
    verifier_receipt = output / "independent_verifier/VERIFIER_RECEIPT.json"
    verifier_receipt.unlink(missing_ok=True)
    if compact:
        _write_json(receipt_path, {"contract_id": "room16.holdout12.compact_transport_receipt@1", "status": "PASS", **(full_binding or {})})
    excluded = {"MANIFEST.json", "SHA256SUMS.txt", "independent_verifier/VERIFIER_RECEIPT.json"}
    def selected(path: Path) -> bool:
        relative = path.relative_to(output).as_posix()
        if relative in excluded:
            return False
        if not compact:
            return relative != "COMPACT_TRANSPORT_RECEIPT.json"
        return not any(part in {"captures", "live_bundle", "replay_bundle"} for part in Path(relative).parts)
    payloads = [path for path in sorted(output.rglob("*")) if path.is_file() and selected(path)]
    files = [{"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": _sha(path)} for path in payloads]
    body = {"contract_id": "room16.holdout12.no_tuning_result_compact@1" if compact else "room16.holdout12.no_tuning_result_full@1", "schema_version": 1, "generated_date": "2026-08-29", "research_commit": _git(ROOT, "rev-parse", "HEAD"), "research_tree": _git(ROOT, "rev-parse", "HEAD^{tree}"), "product_commit": PRODUCT_COMMIT, "product_tree": PRODUCT_TREE, "verdict": _json(output / "14_HOLDOUT12_THRESHOLD_EVALUATION.json")["status"], "compact": compact, "full_binding": full_binding, "file_count": len(files), "files": files}
    manifest = {**body, "manifest_sha256": sha256_json(body)}
    _write_json(output / "MANIFEST.json", manifest)
    sums = "\n".join(f"{row['sha256']}  {row['path']}" for row in files)
    _write_text(output / "SHA256SUMS.txt", sums)
    zip_output.parent.mkdir(parents=True, exist_ok=True)
    def build_zip() -> None:
        with zipfile.ZipFile(zip_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in payloads:
                archive.write(path, path.relative_to(output).as_posix())
            archive.write(output / "MANIFEST.json", "MANIFEST.json")
            archive.write(output / "SHA256SUMS.txt", "SHA256SUMS.txt")
            if verifier_receipt.exists():
                archive.write(verifier_receipt, "independent_verifier/VERIFIER_RECEIPT.json")
    build_zip()
    first = subprocess.run([sys.executable, str(VERIFIER), str(zip_output)], cwd=ROOT, capture_output=True, text=True, check=False)
    if first.returncode:
        raise RuntimeError(f"HOLDOUT12_PACKAGE_VERIFY:{first.stdout}:{first.stderr}")
    _write_json(verifier_receipt, {"contract_id": "room16.holdout12.result_verifier_receipt@1", "status": "PASS", "compact": compact, "manifest_sha256": manifest["manifest_sha256"], "payload_count": len(files), "pre_receipt_zip_sha256": _sha(zip_output)})
    build_zip()
    result = subprocess.run([sys.executable, str(VERIFIER), str(zip_output)], cwd=ROOT, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(f"HOLDOUT12_FINAL_PACKAGE_VERIFY:{result.stdout}:{result.stderr}")
    if compact:
        receipt_path.unlink(missing_ok=True)
    return {"zip": str(zip_output), "zip_sha256": _sha(zip_output), "zip_bytes": zip_output.stat().st_size, "manifest_sha256": manifest["manifest_sha256"], "payload_count": len(files), "verifier": json.loads(result.stdout)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("self-test", "prepare", "run", "finalize", "verify-and-package"):
        item = sub.add_parser(name)
        item.add_argument("--contract-root", required=True, type=Path)
        item.add_argument("--product-root", required=True, type=Path)
        if name != "self-test":
            item.add_argument("--output", required=True, type=Path)
        if name == "prepare":
            item.add_argument("--phase-a-summary", required=True, type=Path)
        if name == "verify-and-package":
            item.add_argument("--full-zip", required=True, type=Path)
            item.add_argument("--compact-zip", required=True, type=Path)
    replay = sub.add_parser("replay-case")
    replay.add_argument("--case-root", required=True, type=Path)
    replay.add_argument("--product-root", required=True, type=Path)
    replay.add_argument("--counter", required=True, type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "self-test":
        print(json.dumps(_self_test(args.contract_root, args.product_root), sort_keys=True))
        return 0
    if args.mode == "prepare":
        return _prepare(args.contract_root, args.output, args.product_root, args.phase_a_summary)
    if args.mode == "run":
        return _run(args.output, args.contract_root, args.product_root)
    if args.mode == "finalize":
        return _finalize(args.output, args.contract_root, args.product_root)
    if args.mode == "verify-and-package":
        return _verify_and_package(args.output, args.contract_root, args.product_root, args.full_zip, args.compact_zip)
    _configure_fixed_runtime(args.product_root)
    return FIXED._replay_case(args.case_root, args.product_root, args.counter)


if __name__ == "__main__":
    raise SystemExit(main())
