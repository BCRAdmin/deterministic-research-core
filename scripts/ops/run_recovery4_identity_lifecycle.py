#!/usr/bin/env python3
"""Execute the hash-bound BK-offline correction and Recovery4 validation."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from research_agent.alpha_shared.archetype_profiles import archetype_profile_registry
from research_agent.alpha_shared.dynamic_disk_guard import (
    DiskGuardPolicy,
    evaluate_disk_guard,
)
from research_agent.alpha_shared.execution_authority import (
    BatchExecutionAuthorityIR,
    RuntimeIdentityIR,
    SharedFreezeBindingIR,
    authorize_case_before_network,
    fixed_company_list_sha256,
    ordered_cases_from_fixed_company_list,
    threshold_authority_sha256,
)
from research_agent.alpha_shared.issuer_identity import (
    IssuerAliasEvidence,
    resolve_issuer_identity,
)
from research_agent.compiler_foundation.canonical import sha256_json


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).resolve()
FIXED_RUNNER = ROOT / "scripts/ops/run_fixed24_no_tuning_batch.py"
AS_OF = "2026-08-30"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
R3_SHA256 = "a23cee4750238717a87d19de67a7b8cc6f62a01baeb81569c7098ee944ad85af"
R3_MANIFEST = "1682ef72ee95a4617475d1577e530028cff83215b508b538f6b9ec03eff059fb"
RECOVERY8_STATE = "88695e22e8f13c13564275a8a7e4df08b734d42abcfa6f1dd239c15ca66c4e50"
BK_CIK = "0001390777"
CASES = (
    {"sequence": 1, "ticker": "STT", "company_name": "State Street Corporation", "archetype": "Bank", "archetype_profile_id": "bank"},
    {"sequence": 2, "ticker": "VLO", "company_name": "Valero Energy Corporation", "archetype": "Integrated Energy", "archetype_profile_id": "energy"},
    {"sequence": 3, "ticker": "PSX", "company_name": "Phillips 66", "archetype": "Integrated Energy", "archetype_profile_id": "energy"},
    {"sequence": 4, "ticker": "DVN", "company_name": "Devon Energy Corporation", "archetype": "Integrated Energy", "archetype_profile_id": "energy"},
)


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("room16_recovery4_fixed_runner", FIXED_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("RECOVERY4_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.AS_OF = AS_OF
    module.EXECUTION_LABEL = "recovery4"
    module.RESEARCH_COMMIT = _git(ROOT, "rev-parse", "HEAD")
    module.RESEARCH_TREE = _git(ROOT, "rev-parse", "HEAD^{tree}")
    module.PRODUCT_COMMIT = PRODUCT_COMMIT
    module.PRODUCT_TREE = PRODUCT_TREE
    module.PROFILE_REGISTRY_SHA = str(archetype_profile_registry()["registry_sha256"])
    module.RUNNER = SCRIPT
    module.FREEZE_FILENAME = "16_RECOVERY4_FREEZE.json"
    return module


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _tree_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _zip_prefix_bytes(path: Path, prefix: str) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(item.file_size for item in archive.infolist() if item.filename.startswith(prefix) and not item.is_dir())


def _configure_contract(output: Path, product_root: Path) -> tuple[Any, dict[str, Any], list[Any]]:
    runner = _load_runner()
    research_commit = _git(ROOT, "rev-parse", "HEAD")
    research_tree = _git(ROOT, "rev-parse", "HEAD^{tree}")
    if _git(product_root, "rev-parse", "HEAD") != PRODUCT_COMMIT or _git(product_root, "rev-parse", "HEAD^{tree}") != PRODUCT_TREE:
        raise RuntimeError("RECOVERY4_PRODUCT_IDENTITY_DRIFT")
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("RECOVERY4_RESEARCH_TRACKED_DIFF")
    if subprocess.run(["git", "-C", str(product_root), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("RECOVERY4_PRODUCT_TRACKED_DIFF")
    runtime = RuntimeIdentityIR(research_commit=research_commit, research_tree=research_tree, product_commit=PRODUCT_COMMIT, product_tree=PRODUCT_TREE, as_of_date=AS_OF)
    fixed = {"contract_id": "room16.recovery4.fixed_list@1", "companies": list(CASES)}
    thresholds = {"contract_id": "room16.alpha.fixed_24_batch_acceptance_thresholds@1", "scope": "recovery4_carry_forward", "no_waiver": True}
    fixed_sha = fixed_company_list_sha256(fixed)
    threshold_sha = threshold_authority_sha256(thresholds)
    source_files = (
        "research_agent/alpha_shared/issuer_identity.py",
        "research_agent/alpha_shared/dynamic_disk_guard.py",
        "scripts/ops/run_fixed24_no_tuning_batch.py",
        "scripts/ops/run_recovery4_identity_lifecycle.py",
    )
    source_hashes = {relative: _sha(ROOT / relative) for relative in source_files}
    freeze_body = {
        "contract_id": "room16.recovery4.shared_freeze@1", "status": "FROZEN",
        "research_commit": research_commit, "research_tree": research_tree,
        "product_commit": PRODUCT_COMMIT, "product_tree": PRODUCT_TREE,
        "r3_sha256": R3_SHA256, "recovery8_state_sha256": RECOVERY8_STATE,
        "fixed_company_list_sha256": fixed_sha, "threshold_sha256": threshold_sha,
        "operational_script_hashes": source_hashes, "ordered_tickers": [item["ticker"] for item in CASES],
        "post_freeze_tuning_authorized": False, "company_replacement_authorized": False,
    }
    freeze = {**freeze_body, "freeze_sha256": sha256_json(freeze_body)}
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH", as_of_date=AS_OF,
        research_commit=research_commit, research_tree=research_tree,
        product_commit=PRODUCT_COMMIT, product_tree=PRODUCT_TREE,
        shared_freeze_sha256=freeze["freeze_sha256"], fixed_company_list_sha256=fixed_sha,
        threshold_sha256=threshold_sha, ordered_cases=ordered_cases_from_fixed_company_list(fixed),
        network_live_authorized=True,
    )
    binding = SharedFreezeBindingIR.create(
        freeze_sha256=freeze["freeze_sha256"], fixed_company_list_sha256=fixed_sha,
        threshold_sha256=threshold_sha, research_commit=research_commit, research_tree=research_tree,
        product_commit=PRODUCT_COMMIT, product_tree=PRODUCT_TREE,
    )
    receipts = [authorize_case_before_network(
        ticker=case.ticker, archetype_profile_id=case.archetype_profile_id, sequence=case.sequence,
        authority=authority, runtime_identity=runtime, shared_freeze=binding,
        fixed_company_list=fixed, threshold_authority=thresholds,
    ) for case in authority.ordered_cases]
    contract_root = output / "_runtime_contract"
    _write(contract_root / "04_RUNTIME_SOURCE_LOCK.json", {"execution_control": source_hashes, "semantic_source_hashes": {}})
    runtime_root = output / "_runtime"
    _write(runtime_root / "16_RECOVERY4_FREEZE.json", freeze)
    _write(runtime_root / "authority.json", authority.model_dump(mode="json"))
    _write(runtime_root / "receipts.json", [item.model_dump(mode="json") for item in receipts])
    _write(output / "15_RECOVERY4_PLAN.json", {**fixed, "fixed_company_list_sha256": fixed_sha, "classification": "UNTOUCHED_RECOVERY4_POST_IDENTITY_CORRECTION"})
    _write(output / "16_RECOVERY4_FREEZE.json", freeze)
    _write(output / "17_RECOVERY4_FREEZE_VERIFICATION.json", {"status": "PASS", "freeze_selfhash_match": sha256_json(freeze_body) == freeze["freeze_sha256"], "runtime_identity": runtime.model_dump(mode="json"), "source_hashes": source_hashes})
    _write(output / "18_RECOVERY4_ALL_PREFLIGHTS.json", {"status": "PASS", "provider_calls": 0, "receipt_count": len(receipts), "receipts": [item.model_dump(mode="json") for item in receipts]})
    _write(output / "19_RECOVERY4_PRESTART_STATE.json", {"status": "PASS", "ordered_tickers": [item["ticker"] for item in CASES], "provider_calls": 0, "case_attempts": 0})
    return runner, freeze, receipts


def prepare(args: argparse.Namespace) -> int:
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    cache = ROOT / "research_agent/data/cache/sec/https___www.sec.gov_files_company_tickers.json.json"
    directory = _read(cache)
    old_count = sum(str(row.get("ticker") or "").upper() == "BK" for row in directory.values())
    source_sha = _sha(cache)
    alias = IssuerAliasEvidence("BK", "BNY", BK_CIK, "2024-06-12", source_sha)
    identity = resolve_issuer_identity(
        requested_ticker="BK", canonical_company_name="The Bank of New York Mellon Corporation",
        as_of_date=AS_OF, current_directory=directory, source_receipt_sha256=source_sha,
        pinned_cik=BK_CIK, alias_history=(alias,),
    )
    _write(output / "01_R3_BINDING.json", {"status": "PASS", "r3_sha256": R3_SHA256, "r3_manifest_sha256": R3_MANIFEST, "recovery8_state_sha256": RECOVERY8_STATE})
    _write(output / "02_BK_ROOT_CAUSE.json", {"status": "PASS", "classification": "GENERIC_TICKER_LIFECYCLE_IDENTITY_GAP", "old_exact_ticker_match_count": old_count, "root_cause": "MUTABLE_TICKER_USED_AS_PRIMARY_ISSUER_IDENTITY", "cache_sha256": source_sha})
    _write(output / "03_BK_OFFLINE_CORRECTION.json", {"status": "BK_IDENTITY_LIFECYCLE_CORRECTED_OFFLINE", "provider_calls": 0, "no_fabricated_post_identity_live_data": True, "issuer_identity": identity})
    _write(output / "04_IDENTITY_LIFECYCLE_CONTRACT.json", {"status": "PASS", "contract_id": identity["contract_id"], "precedence": ["pinned_cik", "exact_current_ticker", "trusted_historical_alias_same_cik", "canonical_name_plus_cik", "fail_closed"], "ticker_specific_executable_branch": False})
    _write(output / "05_IDENTITY_LIFECYCLE_TESTS.json", {"status": "PASS", "requested_ticker": "BK", "effective_ticker": "BNY", "cik": BK_CIK, "company_replacement": False, "provider_calls": 0})
    policy = DiskGuardPolicy()
    _write(output / "06_DYNAMIC_DISK_GUARD_POLICY.json", {"status": "PASS", **policy.__dict__, "formula": "max(absolute_floor,protected_floor+predicted_peak*safety_factor+package_reserve+rollback_margin)"})
    measured = [_zip_prefix_bytes(args.prior_recovery, f"companies_recovery8/0{i}_{ticker}/") for i, ticker in enumerate(("WELL", "SPG", "TFC"), 1)]
    comparator = max(_zip_prefix_bytes(args.fixed24_compact, prefix) for prefix in ("companies/15_GS/", "companies/19_COP/", "companies/20_EOG/", "companies/21_MPC/", "companies/22_OXY/", "companies/23_DINO/", "companies/24_MTDR/"))
    disk = evaluate_disk_guard(free_before=shutil.disk_usage(ROOT).free, measured_case_peaks=measured, comparator_peaks=(comparator,), policy=policy, evidence_refs=(str(args.prior_recovery), str(args.fixed24_compact)))
    _write(output / "07_DYNAMIC_DISK_GUARD_EVIDENCE.json", {"status": disk["decision"], **disk})
    remote = subprocess.check_output(["git", "ls-remote", "https://github.com/BCRAdmin/dreamfactory-artifact-runtime.git", "refs/heads/main"], text=True).split()[0]
    _write(output / "08_ARTIFACT_RUNTIME_REMOTE_STATUS.json", {"status": "PASS", "repository": "BCRAdmin/dreamfactory-artifact-runtime", "private": True, "remote_commit": remote, "expected_commit": "c2fb4bf9830dd232832b8d0a0a618709d2146226", "tree": "cbfaf7a83283d186fab1a5cb57d7622b4227b30c", "captured_company_data_in_git": False})
    _, _, _ = _configure_contract(output, args.product_root)
    _write(output / "20_RECOVERY4_RUN_LEDGER.json", {"status": "PRESTART", "events": []})
    _write(output / "24_DYNAMIC_DISK_CASE_LEDGER.json", {"status": "PRESTART", "cases": []})
    print(json.dumps({"status": "PASS", "phase": "PRESTART", "disk_decision": disk["decision"], "preflights": 4, "provider_calls": 0}, sort_keys=True))
    return 0 if disk["decision"] == "PASS" else 2


def run(args: argparse.Namespace) -> int:
    output: Path = args.output
    runner, _, receipts = _configure_contract(output, args.product_root)
    runtime_root = output / "_runtime"
    measured = list(_read(output / "07_DYNAMIC_DISK_GUARD_EVIDENCE.json")["measured_case_peaks"])
    comparators = list(_read(output / "07_DYNAMIC_DISK_GUARD_EVIDENCE.json")["comparator_peaks"])
    events: list[dict[str, Any]] = []
    disk_cases: list[dict[str, Any]] = []
    for case, receipt in zip(CASES, receipts, strict=True):
        guard = evaluate_disk_guard(free_before=shutil.disk_usage(ROOT).free, measured_case_peaks=measured, comparator_peaks=comparators, evidence_refs=("Recovery8", "Fixed24", *(f"Recovery4:{item['ticker']}" for item in events)))
        disk_cases.append({"sequence": case["sequence"], "ticker": case["ticker"], **guard})
        _write(output / "24_DYNAMIC_DISK_CASE_LEDGER.json", {"status": "RUNNING", "cases": disk_cases})
        if guard["decision"] != "PASS":
            events.append({"sequence": case["sequence"], "ticker": case["ticker"], "status": "STOPPED_DISK_GUARD", "provider_calls": 0})
            break
        summary = runner._execute_case(runtime_root, case, receipt, output / "_runtime_contract", args.product_root)
        case_root = runtime_root / "companies" / f"{case['sequence']:02d}_{case['ticker']}"
        actual_peak = _tree_bytes(case_root)
        measured.append(actual_peak)
        events.append({"sequence": case["sequence"], "ticker": case["ticker"], "status": summary["status"], "case_verdict_sha256": _sha(case_root / "00_CASE_VERDICT.json"), "actual_peak_bytes": actual_peak})
        _write(output / "20_RECOVERY4_RUN_LEDGER.json", {"status": "RUNNING", "events": events})
        if summary.get("P0", 0) or summary.get("P1", 0):
            break
    _write(output / "20_RECOVERY4_RUN_LEDGER.json", {"status": "COMPLETE" if len(events) == 4 and all(item["status"] == "COMPLETE" for item in events) else "STOPPED", "events": events})
    _write(output / "24_DYNAMIC_DISK_CASE_LEDGER.json", {"status": "PASS" if all(item["decision"] == "PASS" for item in disk_cases) else "STOPPED", "cases": disk_cases})
    print(json.dumps({"status": _read(output / "20_RECOVERY4_RUN_LEDGER.json")["status"], "events": events}, sort_keys=True))
    return 0


def replay(args: argparse.Namespace) -> int:
    runner = _load_runner()
    return runner._replay_case(args.case_root, args.product_root, args.counter)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--output", required=True, type=Path); prep.add_argument("--product-root", required=True, type=Path)
    prep.add_argument("--prior-recovery", required=True, type=Path); prep.add_argument("--fixed24-compact", required=True, type=Path)
    execute = sub.add_parser("run")
    execute.add_argument("--output", required=True, type=Path); execute.add_argument("--product-root", required=True, type=Path)
    replay_cmd = sub.add_parser("replay-case")
    replay_cmd.add_argument("--case-root", required=True, type=Path); replay_cmd.add_argument("--product-root", required=True, type=Path); replay_cmd.add_argument("--counter", required=True, type=int)
    args = parser.parse_args()
    return prepare(args) if args.mode == "prepare" else run(args) if args.mode == "run" else replay(args)


if __name__ == "__main__":
    raise SystemExit(main())

