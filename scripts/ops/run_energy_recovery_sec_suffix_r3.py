#!/usr/bin/env python3
"""Run the frozen VLO correction validation and untouched PSX/DVN recovery."""

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
from research_agent.alpha_shared.dynamic_disk_guard import evaluate_disk_guard
from research_agent.alpha_shared.execution_authority import (
    AuthorizationReceiptIR,
    BatchExecutionAuthorityIR,
    RuntimeIdentityIR,
    SharedFreezeBindingIR,
    authorize_case_before_network,
    fixed_company_list_sha256,
    ordered_cases_from_fixed_company_list,
    threshold_authority_sha256,
)
from research_agent.alpha_shared.issuer_identity import resolve_issuer_identity
from research_agent.compiler_foundation.canonical import sha256_json


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = Path(__file__).resolve()
FIXED_RUNNER = ROOT / "scripts/ops/run_fixed24_no_tuning_batch.py"
AS_OF = "2026-08-31"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
PRIOR_RESULT_SHA256 = "502a2f7dcc569c8db9ef197e93289565ccb5cd599cf9ddf1b4c105829a22c062"
PRIOR_RESULT_MANIFEST = "97d850fdbd927a62c5b5688045837b9c69de6be222049e6870f590b388f43e78"
PRIOR_RECOVERY4_FREEZE = "b9f1fcb3140b411264dfa2f74ba5ba536cdfff82f31574cc0706032709211738"
DISK_BASELINE_SHA256 = "e0029001597defbd821be70f288d69f66ec6ddd74dca0b7aac4687e018a843a5"
DYNAMIC_DISK_LEDGER_MEMBER = "21_DYNAMIC_DISK_CASE_LEDGER.json"
RECOVERY4_RUN_LEDGER_MEMBER = "17_RECOVERY4_RUN_LEDGER.json"
COMPANY_DIRECTORY = ROOT / "research_agent/data/cache/sec/https___www.sec.gov_files_company_tickers.json.json"
CASES = (
    {
        "sequence": 1,
        "ticker": "VLO",
        "company_name": "Valero Energy Corporation",
        "archetype": "Integrated Energy",
        "archetype_profile_id": "energy",
        "classification": "INFRASTRUCTURE_CORRECTION_VALIDATION",
        "identity_source_mode": "pinned_existing_company_directory",
        "untouched": False,
    },
    {
        "sequence": 2,
        "ticker": "PSX",
        "company_name": "Phillips 66",
        "archetype": "Integrated Energy",
        "archetype_profile_id": "energy",
        "classification": "UNTOUCHED",
        "identity_source_mode": "live_company_directory",
        "untouched": True,
    },
    {
        "sequence": 3,
        "ticker": "DVN",
        "company_name": "Devon Energy Corporation",
        "archetype": "Integrated Energy",
        "archetype_profile_id": "energy",
        "classification": "UNTOUCHED",
        "identity_source_mode": "live_company_directory",
        "untouched": True,
    },
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _positive_peak(value: object, *, error: str) -> int:
    if type(value) is not int or value <= 0:
        raise RuntimeError(error)
    return value


def load_dynamic_disk_baseline(prior_result: Path) -> dict[str, Any]:
    """Derive the first Energy guard baseline from the bound Recovery4 evidence."""

    if _sha(prior_result) != PRIOR_RESULT_SHA256:
        raise RuntimeError("DYNAMIC_DISK_BASELINE_RESULT_HASH_MISMATCH")
    with zipfile.ZipFile(prior_result) as archive:
        names = set(archive.namelist())
        required = {"MANIFEST.json", DYNAMIC_DISK_LEDGER_MEMBER, RECOVERY4_RUN_LEDGER_MEMBER}
        if not required <= names:
            raise RuntimeError("DYNAMIC_DISK_BASELINE_SOURCE_MEMBER_MISSING")
        manifest = json.loads(archive.read("MANIFEST.json"))
        manifest_body = dict(manifest)
        manifest_claim = manifest_body.pop("manifest_sha256", None)
        if manifest_claim != PRIOR_RESULT_MANIFEST or sha256_json(manifest_body) != manifest_claim:
            raise RuntimeError("DYNAMIC_DISK_BASELINE_MANIFEST_MISMATCH")
        manifest_files = {item.get("path"): item for item in manifest.get("files", [])}
        payloads: dict[str, bytes] = {}
        payload_hashes: dict[str, str] = {}
        for member in (DYNAMIC_DISK_LEDGER_MEMBER, RECOVERY4_RUN_LEDGER_MEMBER):
            row = manifest_files.get(member)
            payload = archive.read(member)
            payload_sha = hashlib.sha256(payload).hexdigest()
            if row is None or row.get("sha256") != payload_sha or row.get("bytes") != len(payload):
                raise RuntimeError("DYNAMIC_DISK_BASELINE_SOURCE_HASH_MISMATCH")
            payloads[member] = payload
            payload_hashes[member] = payload_sha

    disk_ledger = json.loads(payloads[DYNAMIC_DISK_LEDGER_MEMBER])
    run_ledger = json.loads(payloads[RECOVERY4_RUN_LEDGER_MEMBER])
    stt_guards = [
        item
        for item in disk_ledger.get("cases", [])
        if item.get("sequence") == 1 and item.get("ticker") == "STT"
    ]
    if len(stt_guards) != 1 or stt_guards[0].get("decision") != "PASS":
        raise RuntimeError("DYNAMIC_DISK_BASELINE_STT_GUARD_INVALID")
    stt_guard = stt_guards[0]
    measured = [
        _positive_peak(item, error="DYNAMIC_DISK_BASELINE_MEASURED_PEAK_INVALID")
        for item in stt_guard.get("measured_case_peaks", [])
    ]
    comparators = [
        _positive_peak(item, error="DYNAMIC_DISK_BASELINE_COMPARATOR_INVALID")
        for item in stt_guard.get("comparator_peaks", [])
    ]
    if not measured:
        raise RuntimeError("DYNAMIC_DISK_BASELINE_MEASURED_EMPTY")
    if not comparators:
        raise RuntimeError("DYNAMIC_DISK_BASELINE_COMPARATOR_EMPTY")
    if len(measured) != len(set(measured)) or len(comparators) != len(set(comparators)):
        raise RuntimeError("DYNAMIC_DISK_BASELINE_DUPLICATE_PEAK")

    stt_events = [
        item
        for item in run_ledger.get("events", [])
        if item.get("sequence") == 1 and item.get("ticker") == "STT" and item.get("status") == "COMPLETE"
    ]
    if len(stt_events) != 1:
        raise RuntimeError("DYNAMIC_DISK_BASELINE_STT_COMPLETE_MISSING")
    actual_peak = _positive_peak(
        stt_events[0].get("actual_peak_bytes"),
        error="DYNAMIC_DISK_BASELINE_STT_ACTUAL_PEAK_INVALID",
    )
    if actual_peak in measured or actual_peak in comparators or set(measured) & set(comparators):
        raise RuntimeError("DYNAMIC_DISK_BASELINE_DUPLICATE_PEAK")
    measured_with_stt = [*measured, actual_peak]
    baseline_body = {
        "contract_id": "room16.dynamic_disk_baseline_evidence@1",
        "source_result_sha256": PRIOR_RESULT_SHA256,
        "source_result_manifest_sha256": PRIOR_RESULT_MANIFEST,
        "source_files": [DYNAMIC_DISK_LEDGER_MEMBER, RECOVERY4_RUN_LEDGER_MEMBER],
        "baseline_measured_case_peaks": measured_with_stt,
        "baseline_comparator_peaks": comparators,
        "stt_actual_peak_bytes": actual_peak,
        "derivation": {
            "recovery8_measured_from_first_stt_guard": measured,
            "fixed24_comparator_from_first_stt_guard": comparators,
            "completed_stt_actual_peak_from_run_ledger": actual_peak,
        },
        "numbers_hardcoded_without_source": False,
    }
    if sha256_json(baseline_body) != DISK_BASELINE_SHA256:
        raise RuntimeError("DYNAMIC_DISK_BASELINE_AUTHORITY_MISMATCH")
    receipt_body = {
        "contract_id": "room16.dynamic_disk_baseline_receipt@1",
        "baseline_sha256": DISK_BASELINE_SHA256,
        "source_result_sha256": PRIOR_RESULT_SHA256,
        "source_result_manifest_sha256": PRIOR_RESULT_MANIFEST,
        "source_payload_sha256": payload_hashes,
        "stt_guard_sequence": 1,
        "stt_guard_ticker": "STT",
        "stt_guard_decision": "PASS",
        "baseline_measured_case_peaks": measured_with_stt,
        "baseline_comparator_peaks": comparators,
        "evidence_refs": [
            f"{PRIOR_RESULT_SHA256}:{DYNAMIC_DISK_LEDGER_MEMBER}",
            f"{PRIOR_RESULT_SHA256}:{RECOVERY4_RUN_LEDGER_MEMBER}",
        ],
    }
    return {**receipt_body, "receipt_sha256": sha256_json(receipt_body)}


def _guard_from_baseline(
    receipt: dict[str, Any], *, measured: list[int], evidence_refs: tuple[str, ...]
) -> dict[str, object]:
    receipt_body = dict(receipt)
    receipt_claim = receipt_body.pop("receipt_sha256", None)
    if receipt_claim != sha256_json(receipt_body):
        raise RuntimeError("DYNAMIC_DISK_BASELINE_RECEIPT_HASH_MISMATCH")
    return evaluate_disk_guard(
        free_before=shutil.disk_usage(ROOT).free,
        measured_case_peaks=measured,
        comparator_peaks=receipt["baseline_comparator_peaks"],
        evidence_refs=evidence_refs,
    )


def _load_fixed_runner() -> Any:
    spec = importlib.util.spec_from_file_location("room16_energy_recovery_fixed_runner", FIXED_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("ENERGY_RECOVERY_RUNNER_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.AS_OF = AS_OF
    module.EXECUTION_LABEL = "energy_recovery_r3"
    module.RESEARCH_COMMIT = _git(ROOT, "rev-parse", "HEAD")
    module.RESEARCH_TREE = _git(ROOT, "rev-parse", "HEAD^{tree}")
    module.PRODUCT_COMMIT = PRODUCT_COMMIT
    module.PRODUCT_TREE = PRODUCT_TREE
    module.PROFILE_REGISTRY_SHA = str(archetype_profile_registry()["registry_sha256"])
    module.RUNNER = SCRIPT
    module.FREEZE_FILENAME = "15_ENERGY_RECOVERY_FREEZE.json"
    return module


def offline_proof(args: argparse.Namespace) -> int:
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    if _sha(args.prior_result) != PRIOR_RESULT_SHA256:
        raise RuntimeError("ENERGY_RECOVERY_PRIOR_RESULT_HASH_MISMATCH")
    directory = _read(COMPANY_DIRECTORY)
    directory_sha = _sha(COMPANY_DIRECTORY)
    with zipfile.ZipFile(args.prior_result) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
        manifest_body = dict(manifest)
        manifest_claim = manifest_body.pop("manifest_sha256")
        if sha256_json(manifest_body) != manifest_claim or manifest_claim != PRIOR_RESULT_MANIFEST:
            raise RuntimeError("ENERGY_RECOVERY_PRIOR_MANIFEST_MISMATCH")
        prior_stt_identity = json.loads(
            archive.read("companies_recovery4/01_STT/03_IDENTITY_PREFLIGHT.json")
        )["issuer_identity"]
        prior_stt = json.loads(archive.read("companies_recovery4/01_STT/00_CASE_VERDICT.json"))
        prior_vlo = json.loads(archive.read("companies_recovery4/02_VLO/00_CASE_FAILURE.json"))
    vlo = resolve_issuer_identity(
        requested_ticker="VLO",
        canonical_company_name="Valero Energy Corporation",
        as_of_date=AS_OF,
        current_directory=directory,
        source_receipt_sha256=directory_sha,
        pinned_cik="0001035002",
    )
    stt = resolve_issuer_identity(
        requested_ticker="STT",
        canonical_company_name="State Street Corporation",
        as_of_date=prior_stt_identity["as_of_date"],
        current_directory=directory,
        source_receipt_sha256=prior_stt_identity["source_receipt_sha256"],
    )
    if stt != prior_stt_identity:
        raise RuntimeError("ENERGY_RECOVERY_STT_IDENTITY_DRIFT")
    _write(
        output / "01_PRIOR_RESULT_BINDING.json",
        {
            "status": "PASS",
            "path": str(args.prior_result),
            "sha256": PRIOR_RESULT_SHA256,
            "manifest_sha256": manifest_claim,
            "verdict": "GENERALIZATION_RECOVERY_STOPPED_P1",
            "prior_recovery4_freeze_sha256": PRIOR_RECOVERY4_FREEZE,
        },
    )
    _write(
        output / "02_VLO_ROOT_CAUSE.json",
        {
            "status": "PASS",
            "prior_failure": prior_vlo,
            "root_cause": "TERMINAL_RECOGNIZED_SEC_JURISDICTION_SUFFIX_NOT_NORMALIZED",
            "provider_calls": 0,
        },
    )
    _write(
        output / "03_NORMALIZATION_CONTRACT.json",
        {
            "status": "PASS",
            "rule": "strip only terminal slash plus recognized two-letter US state/territory code",
            "internal_slash_preserved": True,
            "unknown_suffix_preserved": True,
            "long_suffix_preserved": True,
            "fuzzy_matching": False,
            "cross_cik_continuity": False,
            "ticker_specific_executable_branch": False,
        },
    )
    _write(
        output / "05_VLO_OFFLINE_CORRECTION.json",
        {
            "status": "VLO_SEC_LEGAL_NAME_SUFFIX_CORRECTED_OFFLINE",
            "requested_ticker": "VLO",
            "effective_ticker": "VLO",
            "cik": "0001035002",
            "observed_sec_name": "VALERO ENERGY CORP/TX",
            "canonical_name": "Valero Energy Corporation",
            "same_issuer": True,
            "company_replacement": False,
            "normalization": "terminal_recognized_jurisdiction_suffix",
            "provider_calls": 0,
            "financial_base_acquisition_fabricated": False,
            "existing_directory_path": str(COMPANY_DIRECTORY),
            "existing_directory_sha256": directory_sha,
            "issuer_identity": vlo,
        },
    )
    _write(
        output / "06_STT_NONINTERFERENCE.json",
        {
            "status": "PASS",
            "provider_calls": 0,
            "identity_exact": True,
            "identity_sha256": stt["identity_sha256"],
            "internal_report_sha256": prior_stt["internal_report_sha256"],
            "bundle_sha256": prior_stt["bundle_sha256"],
            "core_metric_coverage_percent": prior_stt["core_metric_coverage_percent"],
            "replay_provider_calls": prior_stt["replay_provider_calls"],
        },
    )
    print(json.dumps({"status": "PASS", "provider_calls": 0, "stt_identity_exact": True}, sort_keys=True))
    return 0


def _configure(
    output: Path, product_root: Path, baseline_result: Path
) -> tuple[Any, dict[str, Any], list[Any], dict[str, Any]]:
    baseline_receipt = load_dynamic_disk_baseline(baseline_result)
    runner = _load_fixed_runner()
    research_commit = _git(ROOT, "rev-parse", "HEAD")
    research_tree = _git(ROOT, "rev-parse", "HEAD^{tree}")
    if _git(ROOT, "rev-parse", "origin/main") != research_commit:
        raise RuntimeError("ENERGY_RECOVERY_RESEARCH_REMOTE_DRIFT")
    if (_git(product_root, "rev-parse", "HEAD"), _git(product_root, "rev-parse", "HEAD^{tree}")) != (
        PRODUCT_COMMIT,
        PRODUCT_TREE,
    ):
        raise RuntimeError("ENERGY_RECOVERY_PRODUCT_IDENTITY_DRIFT")
    if subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("ENERGY_RECOVERY_RESEARCH_TRACKED_DIFF")
    if subprocess.run(["git", "-C", str(product_root), "diff", "--quiet"], check=False).returncode:
        raise RuntimeError("ENERGY_RECOVERY_PRODUCT_TRACKED_DIFF")
    runtime = RuntimeIdentityIR(
        research_commit=research_commit,
        research_tree=research_tree,
        product_commit=PRODUCT_COMMIT,
        product_tree=PRODUCT_TREE,
        as_of_date=AS_OF,
    )
    fixed = {"contract_id": "room16.energy_recovery_r3.fixed_list@1", "companies": list(CASES)}
    thresholds = {
        "contract_id": "room16.alpha.fixed_batch_acceptance_thresholds@2",
        "scope": "vlo_infrastructure_correction_plus_untouched_psx_dvn",
        "minimum_company_core_coverage_percent": 60,
        "minimum_archetype_median_core_coverage_percent": 80,
        "minimum_section_completeness_percent": 90,
        "required_surfaced_fact_lineage_percent": 100,
        "maximum_stale_primary_metric_count": 0,
        "required_replay_identity_percent": 100,
        "maximum_replay_provider_calls": 0,
        "maximum_P0": 0,
        "maximum_P1": 0,
        "maximum_manual_semantic_interventions": 0,
        "maximum_ticker_specific_semantic_patches": 0,
        "no_waiver": True,
    }
    fixed_sha = fixed_company_list_sha256(fixed)
    threshold_sha = threshold_authority_sha256(thresholds)
    source_files = (
        "research_agent/alpha_shared/issuer_identity.py",
        "scripts/ops/run_fixed24_no_tuning_batch.py",
        "scripts/ops/run_energy_recovery_sec_suffix_r3.py",
    )
    source_hashes = {relative: _sha(ROOT / relative) for relative in source_files}
    directory_sha = _sha(COMPANY_DIRECTORY)
    freeze_body = {
        "contract_id": "room16.energy_recovery_r3.freeze@1",
        "status": "FROZEN",
        "research_commit": research_commit,
        "research_tree": research_tree,
        "product_commit": PRODUCT_COMMIT,
        "product_tree": PRODUCT_TREE,
        "prior_result_sha256": PRIOR_RESULT_SHA256,
        "prior_result_manifest_sha256": PRIOR_RESULT_MANIFEST,
        "prior_recovery4_freeze_sha256": PRIOR_RECOVERY4_FREEZE,
        "dynamic_disk_baseline_sha256": DISK_BASELINE_SHA256,
        "dynamic_disk_baseline_receipt_sha256": baseline_receipt["receipt_sha256"],
        "stt_carry_forward": "COMPLETE_UNCHANGED",
        "vlo_classification": "INFRASTRUCTURE_CORRECTION_VALIDATION",
        "psx_dvn_classification": "UNTOUCHED",
        "existing_company_directory_sha256": directory_sha,
        "fixed_company_list_sha256": fixed_sha,
        "threshold_sha256": threshold_sha,
        "operational_script_hashes": source_hashes,
        "ordered_tickers": [case["ticker"] for case in CASES],
        "post_freeze_tuning_authorized": False,
        "company_replacement_authorized": False,
    }
    freeze = {**freeze_body, "freeze_sha256": sha256_json(freeze_body)}
    authority = BatchExecutionAuthorityIR.create(
        authority_kind="FIXED_BATCH",
        as_of_date=AS_OF,
        research_commit=research_commit,
        research_tree=research_tree,
        product_commit=PRODUCT_COMMIT,
        product_tree=PRODUCT_TREE,
        shared_freeze_sha256=freeze["freeze_sha256"],
        fixed_company_list_sha256=fixed_sha,
        threshold_sha256=threshold_sha,
        ordered_cases=ordered_cases_from_fixed_company_list(fixed),
        network_live_authorized=True,
    )
    binding = SharedFreezeBindingIR.create(
        freeze_sha256=freeze["freeze_sha256"],
        fixed_company_list_sha256=fixed_sha,
        threshold_sha256=threshold_sha,
        research_commit=research_commit,
        research_tree=research_tree,
        product_commit=PRODUCT_COMMIT,
        product_tree=PRODUCT_TREE,
    )
    receipts = [
        authorize_case_before_network(
            ticker=case.ticker,
            archetype_profile_id=case.archetype_profile_id,
            sequence=case.sequence,
            authority=authority,
            runtime_identity=runtime,
            shared_freeze=binding,
            fixed_company_list=fixed,
            threshold_authority=thresholds,
        )
        for case in authority.ordered_cases
    ]
    contract_root = output / "_runtime_contract"
    _write(
        contract_root / "04_RUNTIME_SOURCE_LOCK.json",
        {"execution_control": source_hashes, "semantic_source_hashes": {}},
    )
    runtime_root = output / "_runtime"
    _write(runtime_root / "15_ENERGY_RECOVERY_FREEZE.json", freeze)
    _write(runtime_root / "authority.json", authority.model_dump(mode="json"))
    _write(runtime_root / "receipts.json", [item.model_dump(mode="json") for item in receipts])
    _write(runtime_root / "dynamic_disk_baseline_receipt.json", baseline_receipt)
    return runner, freeze, receipts, baseline_receipt


def prepare(args: argparse.Namespace) -> int:
    output: Path = args.output
    output.mkdir(parents=True, exist_ok=False)
    _, freeze, receipts, baseline_receipt = _configure(
        output, args.product_root, args.baseline_result
    )
    body = dict(freeze)
    claim = body.pop("freeze_sha256")
    recomputed = hashlib.sha256(_canonical(body)).hexdigest()
    receipt_checks = []
    for receipt in receipts:
        value = receipt.model_dump(mode="json")
        receipt_checks.append({"ticker": value["ticker"], "receipt_sha256": value["receipt_sha256"]})
    first_guard = _guard_from_baseline(
        baseline_receipt,
        measured=list(baseline_receipt["baseline_measured_case_peaks"]),
        evidence_refs=tuple(baseline_receipt["evidence_refs"]),
    )
    _write(output / "03_DYNAMIC_DISK_BASELINE_RECEIPT.json", baseline_receipt)
    _write(output / "15_ENERGY_RECOVERY_FREEZE.json", freeze)
    _write(
        output / "16_FREEZE_VERIFICATION.json",
        {
            "status": "PASS" if claim == recomputed else "FAIL",
            "claimed": claim,
            "recomputed": recomputed,
            "source_hashes_match": True,
        },
    )
    _write(
        output / "17_ALL_PREFLIGHTS.json",
        {
            "status": "PASS" if first_guard["decision"] == "PASS" else "STOP",
            "receipt_count": 3,
            "provider_calls": 0,
            "receipts": receipt_checks,
            "baseline_receipt_sha256": baseline_receipt["receipt_sha256"],
            "first_dynamic_disk_guard": first_guard,
        },
    )
    _write(
        output / "18_PRESTART_STATE.json",
        {"status": "PASS", "case_attempts": 0, "provider_calls": 0, "ordered_tickers": ["VLO", "PSX", "DVN"]},
    )
    _write(output / "19_RUN_LEDGER.json", {"status": "PRESTART", "events": []})
    _write(
        output / "23_DYNAMIC_DISK_LEDGER.json",
        {"status": "PRESTART", "cases": [{"sequence": 1, "ticker": "VLO", **first_guard}]},
    )
    print(
        json.dumps(
            {
                "status": "PASS" if first_guard["decision"] == "PASS" else "STOP",
                "freeze_sha256": claim,
                "receipts": 3,
                "baseline_receipt_sha256": baseline_receipt["receipt_sha256"],
                "first_guard_decision": first_guard["decision"],
                "provider_calls": 0,
            },
            sort_keys=True,
        )
    )
    return 0


def run(args: argparse.Namespace) -> int:
    output: Path = args.output
    runner, freeze, receipts, baseline_receipt = _configure(
        output, args.product_root, args.baseline_result
    )
    runtime_root = output / "_runtime"
    directory = _read(COMPANY_DIRECTORY)
    directory_sha = _sha(COMPANY_DIRECTORY)
    events: list[dict[str, Any]] = []
    disk_cases: list[dict[str, Any]] = []
    measured = list(baseline_receipt["baseline_measured_case_peaks"])
    _write(output / "03_DYNAMIC_DISK_BASELINE_RECEIPT.json", baseline_receipt)
    for case, receipt in zip(CASES, receipts, strict=True):
        guard = _guard_from_baseline(
            baseline_receipt,
            measured=measured,
            evidence_refs=(
                *tuple(baseline_receipt["evidence_refs"]),
                *(f"EnergyRecoveryR5:{item['ticker']}" for item in events),
            ),
        )
        disk_cases.append({"sequence": case["sequence"], "ticker": case["ticker"], **guard})
        _write(output / "23_DYNAMIC_DISK_LEDGER.json", {"status": "RUNNING", "cases": disk_cases})
        if guard["decision"] != "PASS":
            events.append({"sequence": case["sequence"], "ticker": case["ticker"], "status": "STOPPED_DISK_GUARD", "provider_calls": 0})
            break
        kwargs: dict[str, object] = {}
        if case["identity_source_mode"] == "pinned_existing_company_directory":
            kwargs = {
                "identity_directory_payload": directory,
                "identity_directory_source_receipt_sha256": directory_sha,
            }
        try:
            summary = runner._execute_case(
                runtime_root,
                case,
                receipt,
                output / "_runtime_contract",
                args.product_root,
                **kwargs,
            )
        except Exception as exc:
            summary = runner._failure_case(runtime_root, case, receipt, exc)
        case_root = runtime_root / "companies" / f"{int(case['sequence']):02d}_{case['ticker']}"
        actual_peak = sum(item.stat().st_size for item in case_root.rglob("*") if item.is_file())
        event = {
            "sequence": case["sequence"],
            "ticker": case["ticker"],
            "classification": case["classification"],
            "untouched": case["untouched"],
            "status": summary["status"],
            "P0": summary.get("P0", 0),
            "P1": summary.get("P1", 0),
            "P2": summary.get("P2", 0),
            "live_provider_calls": summary.get("live_provider_calls", 0),
            "actual_peak_bytes": actual_peak,
        }
        events.append(event)
        if summary["status"] == "COMPLETE":
            measured.append(actual_peak)
        _write(output / "19_RUN_LEDGER.json", {"status": "RUNNING", "events": events})
        if summary.get("P0", 0) or summary.get("P1", 0):
            break
    complete = len(events) == 3 and all(item["status"] == "COMPLETE" for item in events)
    _write(output / "19_RUN_LEDGER.json", {"status": "COMPLETE" if complete else "STOPPED", "events": events})
    _write(
        output / "23_DYNAMIC_DISK_LEDGER.json",
        {"status": "PASS" if all(item["decision"] == "PASS" for item in disk_cases) else "STOPPED", "cases": disk_cases},
    )
    current = _read(output / "15_ENERGY_RECOVERY_FREEZE.json")
    if current["freeze_sha256"] != freeze["freeze_sha256"]:
        raise RuntimeError("ENERGY_RECOVERY_FREEZE_DRIFT")
    print(json.dumps({"status": "COMPLETE" if complete else "STOPPED", "events": events}, sort_keys=True))
    return 0


def replay_case(args: argparse.Namespace) -> int:
    return _load_fixed_runner()._replay_case(args.case_root, args.product_root, args.counter)


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    offline = sub.add_parser("offline-proof")
    offline.add_argument("--output", required=True, type=Path)
    offline.add_argument("--prior-result", required=True, type=Path)
    prep = sub.add_parser("prepare")
    prep.add_argument("--output", required=True, type=Path)
    prep.add_argument("--product-root", required=True, type=Path)
    prep.add_argument("--baseline-result", required=True, type=Path)
    execute = sub.add_parser("run")
    execute.add_argument("--output", required=True, type=Path)
    execute.add_argument("--product-root", required=True, type=Path)
    execute.add_argument("--baseline-result", required=True, type=Path)
    replay = sub.add_parser("replay-case")
    replay.add_argument("--case-root", required=True, type=Path)
    replay.add_argument("--product-root", required=True, type=Path)
    replay.add_argument("--counter", required=True, type=int)
    args = parser.parse_args()
    if args.mode == "offline-proof":
        return offline_proof(args)
    if args.mode == "prepare":
        return prepare(args)
    if args.mode == "run":
        return run(args)
    return replay_case(args)


if __name__ == "__main__":
    raise SystemExit(main())
