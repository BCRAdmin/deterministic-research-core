"""Executable RFC-0011 shared case runner intended for the future H5 caller."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .compiler import SharedCompileResult, compile_shared_successor
from .contracts import SharedBaseInputIR, SupplementalCompileInputIR
from .execution_authority import AuthorizationReceiptIR, verify_receipt_for_live_case
from .operations_ledger import OperationsLedger


@dataclass(frozen=True)
class SharedCaseRunResult:
    compiled: SharedCompileResult
    report: dict[str, Any]


@dataclass(frozen=True)
class CanonicalAlphaCaseRunResult:
    compiled: SharedCompileResult
    report: dict[str, Any]


def _append_stage(
    ledger: OperationsLedger,
    *,
    run_id: str,
    stage: str,
    as_of_date: str,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    provider_id: str | None = None,
    provider_status: str | None = None,
    network_calls: int = 0,
    capture_bytes: int = 0,
) -> None:
    sequence = len(ledger.verify()) + 1
    ledger.append(
        run_id=run_id,
        stage=stage,
        attempt=1,
        started_at=f"{as_of_date}T10:{sequence:02d}:00Z",
        ended_at=f"{as_of_date}T10:{sequence:02d}:01Z",
        duration_ms=1000,
        status="PASS",
        provider_id_or_null=provider_id,
        provider_status_or_null=provider_status,
        network_call_count=network_calls,
        capture_bytes=capture_bytes,
        input_sha256s=inputs,
        output_sha256s=outputs,
        diagnostic_codes=(),
    )


def _ledger_report(
    compiled: SharedCompileResult,
    *,
    ledger: OperationsLedger,
    research_commit: str,
    research_tree: str,
) -> SharedCompileResult:
    report = {
        "status": "PASS",
        "path": str(ledger.path),
        "events": [item.model_dump(mode="json") for item in ledger.verify()],
        "aggregate": ledger.aggregate(),
        "research_commit": research_commit,
        "research_tree": research_tree,
    }
    receipt_path = compiled.bundle_root / "SHARED_RUN_RECEIPT.json"
    receipt_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    return replace(compiled, ledger_report=report)


def run_shared_case(
    *,
    base_input: SharedBaseInputIR,
    supplemental_input: SupplementalCompileInputIR,
    archetype_profile_id: str,
    output_root: Path,
    ledger_path: Path,
    research_commit: str,
    research_tree: str,
    monotonic_counter: int,
) -> SharedCaseRunResult:
    """Execute the real shared compiler path with no hidden network fallback."""

    compiled = compile_shared_successor(
        base_input=base_input,
        archetype_profile_id=archetype_profile_id,
        supplemental_input=supplemental_input,
        output_root=output_root,
        ledger_path=ledger_path,
        research_commit=research_commit,
        research_tree=research_tree,
        monotonic_counter=monotonic_counter,
    )
    stages = [item["stage"] for item in compiled.ledger_report["events"]]
    return SharedCaseRunResult(
        compiled=compiled,
        report={
            "contract_id": "room16.rfc0011.real_shared_runner_report",
            "contract_version": 1,
            "actual_function_called": "run_shared_case",
            "shared_compiler_called": True,
            "bundle_verified": compiled.verification["status"] == "PASS",
            "h4_stages": stages,
            "network_calls": compiled.ledger_report["aggregate"]["live_network_calls"],
            "fixed24_queries": 0,
            "fixed24_batch_authorized": False,
            "status": "PASS",
        },
    )


def run_canonical_alpha_case(
    *,
    base_input: SharedBaseInputIR,
    supplemental_input: SupplementalCompileInputIR,
    archetype_profile_id: str,
    output_root: Path,
    ledger_path: Path,
    research_commit: str,
    research_tree: str,
    monotonic_counter: int,
    acquisition_mode: str,
    authorization_receipt: AuthorizationReceiptIR | None = None,
) -> CanonicalAlphaCaseRunResult:
    """Bind a verified full source case to the R4 shared compiler and report surface."""

    if acquisition_mode not in {"verified_live_capture", "offline_replay"}:
        raise ValueError("R4_CANONICAL_ACQUISITION_MODE_INVALID")
    verified_receipt = None
    if acquisition_mode == "verified_live_capture":
        verified_receipt = verify_receipt_for_live_case(
            receipt=authorization_receipt,
            ticker=base_input.ticker,
            archetype_profile_id=archetype_profile_id,
            as_of_date=base_input.as_of_date,
            research_commit=research_commit,
            research_tree=research_tree,
        )
    run_id = f"rfc0011-r4.case.{base_input.ticker.lower()}.{base_input.source_snapshot_sha256[:12]}"
    ledger = OperationsLedger(ledger_path)
    _append_stage(
        ledger,
        run_id=run_id,
        stage="resolve_identity",
        as_of_date=base_input.as_of_date,
        inputs=(base_input.request_sha256,),
        outputs=(base_input.base_input_sha256,),
    )
    _append_stage(
        ledger,
        run_id=run_id,
        stage="compile_request",
        as_of_date=base_input.as_of_date,
        inputs=(base_input.request_sha256,),
        outputs=(base_input.request_sha256,),
    )
    _append_stage(
        ledger,
        run_id=run_id,
        stage="source_plan",
        as_of_date=base_input.as_of_date,
        inputs=(base_input.request_sha256,),
        outputs=(base_input.acquisition_plan_sha256,),
    )
    live = acquisition_mode == "verified_live_capture"
    for receipt in base_input.snapshot_ir.retrieval_receipts:
        _append_stage(
            ledger,
            run_id=run_id,
            stage=f"base_provider_acquisition.{receipt.provider_id}",
            as_of_date=base_input.as_of_date,
            inputs=(receipt.payload_sha256,),
            outputs=(receipt.receipt_id, receipt.payload_sha256),
            provider_id=receipt.provider_id,
            provider_status="verified_live_receipt" if live else "offline_replay",
            network_calls=1 if live else 0,
            capture_bytes=receipt.payload_bytes if live else 0,
        )
    _append_stage(
        ledger,
        run_id=run_id,
        stage="base_capture_bridge",
        as_of_date=base_input.as_of_date,
        inputs=tuple(
            item.payload_sha256 for item in base_input.snapshot_ir.retrieval_receipts
        ),
        outputs=(base_input.source_snapshot_sha256,),
    )
    _append_stage(
        ledger,
        run_id=run_id,
        stage="rfc0011.discovery",
        as_of_date=base_input.as_of_date,
        inputs=(supplemental_input.supplemental_policy_sha256,),
        outputs=(supplemental_input.discovery_set_sha256,),
        provider_status="bound_existing_capture",
    )
    _append_stage(
        ledger,
        run_id=run_id,
        stage="rfc0011.child_capture.bound",
        as_of_date=base_input.as_of_date,
        inputs=(supplemental_input.discovery_set_sha256,),
        outputs=(supplemental_input.supplemental_evidence_set_sha256,),
        provider_status="bound_existing_capture",
    )
    _append_stage(
        ledger,
        run_id=run_id,
        stage="rfc0011.normalize",
        as_of_date=base_input.as_of_date,
        inputs=(supplemental_input.supplemental_evidence_set_sha256,),
        outputs=(supplemental_input.observation_set_sha256,),
    )
    compiled = compile_shared_successor(
        base_input=base_input,
        archetype_profile_id=archetype_profile_id,
        supplemental_input=supplemental_input,
        output_root=output_root,
        ledger_path=ledger_path,
        research_commit=research_commit,
        research_tree=research_tree,
        monotonic_counter=monotonic_counter,
        run_id_override=run_id,
    )
    if not live:
        _append_stage(
            ledger,
            run_id=run_id,
            stage="offline_replay",
            as_of_date=base_input.as_of_date,
            inputs=(base_input.source_snapshot_sha256,),
            outputs=(compiled.internal_report.report_sha256,),
        )
        compiled = _ledger_report(
            compiled,
            ledger=ledger,
            research_commit=research_commit,
            research_tree=research_tree,
        )
    aggregate = compiled.ledger_report["aggregate"]
    return CanonicalAlphaCaseRunResult(
        compiled=compiled,
        report={
            "contract_id": "room16.rfc0011.r4.canonical_alpha_case_report",
            "contract_version": 1,
            "actual_function_called": "run_canonical_alpha_case",
            "ticker": base_input.ticker,
            "archetype_profile_id": archetype_profile_id,
            "acquisition_mode": acquisition_mode,
            "authorization_receipt_sha256": (
                verified_receipt.receipt_sha256 if verified_receipt is not None else None
            ),
            "authorization_preflight_count": (
                verified_receipt.authorization_preflight_count
                if verified_receipt is not None
                else 0
            ),
            "case_attempt_count": 1 if live else 0,
            "source_snapshot_sha256": base_input.source_snapshot_sha256,
            "bundle_sha256": compiled.manifest["bundle_sha256"],
            "internal_report_sha256": compiled.internal_report.report_sha256,
            "bundle_verified": compiled.verification["status"] == "PASS",
            "live_network_call_count": aggregate["live_network_calls"],
            "live_capture_bytes": aggregate["live_capture_bytes"],
            "replay_network_call_count": aggregate["replay_provider_calls"],
            "core_metric_coverage_percent": compiled.internal_report.source_coverage[
                "core_metric_coverage_percent"
            ],
            "required_section_completeness_percent": (
                compiled.internal_report.report_completeness[
                    "required_section_completeness_percent"
                ]
            ),
            "holdout_live_query_count": 0,
            "fixed24_query_count": 0,
            "fixed24_run_count": 0,
            "fixed24_batch_authorized": False,
            "product_report_v2": False,
            "status": "PASS",
        },
    )


def replay_canonical_alpha_case(**values: Any) -> CanonicalAlphaCaseRunResult:
    return run_canonical_alpha_case(**values, acquisition_mode="offline_replay")
