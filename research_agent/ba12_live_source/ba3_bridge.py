"""Truthful RFC-0010 bridge into the unchanged frozen BA3 offline path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.source_frontend.contracts import (
    CompileRequestIR,
    RetrievalReceiptIR,
    SourceAcquisitionIR,
    SourceSnapshotIR,
)
from research_agent.semantic_compiler.source_frontend.offline import (
    OfflineSourceInput,
    freeze_offline_sources,
)

from .contracts import (
    LiveCaptureBinding,
    LiveCaptureDisposition,
    LiveCaptureSet,
    LiveRunClosure,
    fail,
)
from .attempt_store import LiveAttemptStore
from .authority_store import LiveAuthorityStore
from .live_receipt import LiveCaptureRecord


@dataclass(frozen=True)
class LiveBridgeResult:
    snapshot: SourceSnapshotIR
    bindings: tuple[LiveCaptureBinding, ...]
    capture_set: LiveCaptureSet
    closure: LiveRunClosure | None = None


def _ba3_receipt_hash(receipt: RetrievalReceiptIR) -> str:
    return sha256_json(receipt.model_dump(mode="json"))


def bridge_capture_set_to_ba3(
    *,
    request: CompileRequestIR,
    plan: SourceAcquisitionIR,
    records: tuple[LiveCaptureRecord, ...],
    capture_store_root: Path,
    snapshot_root: Path,
    staged_at_utc: str,
) -> LiveBridgeResult:
    """Replay a fully closed live-capture set through frozen BA3 byte-for-byte."""

    expected_ids = tuple(item.acquisition_id for item in plan.acquisitions)
    record_ids = tuple(sorted(record.receipt.acquisition_id for record in records))
    if record_ids != tuple(sorted(expected_ids)) or len(record_ids) != len(set(record_ids)):
        raise fail(
            "LIVE_CAPTURE_SET_INCOMPLETE",
            "successful live records must exactly cover the acquisition plan",
        )
    by_id = {record.receipt.acquisition_id: record for record in records}
    offline_inputs: list[OfflineSourceInput] = []
    for acquisition in plan.acquisitions:
        record = by_id[acquisition.acquisition_id]
        live = record.receipt
        artifact = record.artifact
        if (
            live.request_sha256 != request.request_sha256
            or live.acquisition_plan_sha256 != plan.plan_sha256
            or live.provider_id != acquisition.provider_id
            or live.capture_artifact_sha256 != artifact.artifact_sha256
            or live.payload_sha256 != artifact.content_sha256
            or live.payload_bytes != artifact.byte_length
        ):
            raise fail("LIVE_CAPTURE_IDENTITY_MISMATCH", "live record is not bound to the plan")
        capture_path = capture_store_root / artifact.content_addressed_relative_path
        offline_inputs.append(
            OfflineSourceInput(
                acquisition_id=live.acquisition_id,
                source_id=live.source_id,
                source_type=live.source_type,
                provider_id=live.provider_id,
                path=capture_path,
                original_locator=f"room16-capture://sha256/{live.payload_sha256}",
                retrieved_at=staged_at_utc,
                available_at=live.available_at_utc,
                published_at=live.published_at_utc_or_null,
                filing_date=live.filing_date_or_null,
                media_type=live.media_type,
                disposition="material_evidence",
                transport="offline_replay",
                availability_basis="public_timestamp",
            )
        )

    snapshot = freeze_offline_sources(
        request=request,
        plan=plan,
        inputs=tuple(offline_inputs),
        snapshot_root=snapshot_root,
    )
    ba3_by_acquisition = {
        receipt.acquisition_id: receipt for receipt in snapshot.retrieval_receipts
    }
    bindings: list[LiveCaptureBinding] = []
    dispositions: list[LiveCaptureDisposition] = []
    for acquisition_id in sorted(expected_ids):
        record = by_id[acquisition_id]
        live = record.receipt
        artifact = record.artifact
        ba3 = ba3_by_acquisition.get(acquisition_id)
        if ba3 is None:
            raise fail("LIVE_BA3_RECEIPT_MISSING", "frozen BA3 did not emit a planned receipt")
        if (
            ba3.transport != "offline_replay"
            or not ba3.original_locator.startswith("room16-capture://sha256/")
            or ba3.original_locator != f"room16-capture://sha256/{live.payload_sha256}"
            or ba3.payload_sha256 != live.payload_sha256
            or ba3.payload_bytes != live.payload_bytes
            or ba3.acquisition_id != live.acquisition_id
            or ba3.provider_id != live.provider_id
            or ba3.source_id != live.source_id
            or ba3.source_type != live.source_type
            or ba3.media_type != live.media_type
            or ba3.available_at != live.available_at_utc
            or ba3.published_at != live.published_at_utc_or_null
            or ba3.filing_date != live.filing_date_or_null
            or ba3.variable_cost_incurred is not False
        ):
            raise fail("LIVE_BA3_BINDING_MISMATCH", "frozen BA3 receipt differs from live capture")
        binding = LiveCaptureBinding.create(
            request_sha256=request.request_sha256,
            acquisition_plan_sha256=plan.plan_sha256,
            acquisition_id=acquisition_id,
            provider_id=live.provider_id,
            source_id=live.source_id,
            source_type=live.source_type,
            live_receipt_sha256=live.receipt_sha256,
            capture_artifact_sha256=artifact.artifact_sha256,
            payload_sha256=live.payload_sha256,
            payload_bytes=live.payload_bytes,
            ba3_retrieval_receipt_sha256=_ba3_receipt_hash(ba3),
            ba3_source_snapshot_sha256=snapshot.snapshot_sha256,
            live_fetched_at_utc=live.fetched_at_utc,
            ba3_retrieved_at_utc=ba3.retrieved_at,
        )
        bindings.append(binding)
        dispositions.append(
            LiveCaptureDisposition(
                acquisition_id=acquisition_id,
                required=True,
                terminal_state="captured_bound",
                live_receipt_sha256=live.receipt_sha256,
                binding_sha256=binding.binding_sha256,
            )
        )
    capture_set = LiveCaptureSet.create(
        request_sha256=request.request_sha256,
        acquisition_plan_sha256=plan.plan_sha256,
        expected_acquisition_ids=tuple(sorted(expected_ids)),
        dispositions=tuple(dispositions),
    )
    execution_root = capture_store_root.resolve().parent
    attempts = LiveAttemptStore(execution_root / "attempts").terminal_for_run(
        request_sha256=request.request_sha256,
        acquisition_plan_sha256=plan.plan_sha256,
    )
    if (
        tuple(sorted(item.acquisition_id for item in attempts))
        != tuple(sorted(expected_ids))
        or any(item.terminal_state != "captured_success" for item in attempts)
    ):
        raise fail(
            "LIVE_RUN_ATTEMPT_COVERAGE",
            "successful bridge requires one durable successful attempt per acquisition",
        )
    closure = LiveAuthorityStore(execution_root / "authority").persist_closed_graph(
        capture_set=capture_set,
        attempts=attempts,
        bindings=tuple(bindings),
        snapshot=snapshot,
    )
    return LiveBridgeResult(
        snapshot=snapshot,
        bindings=tuple(bindings),
        capture_set=capture_set,
        closure=closure,
    )


def close_failed_capture_run(
    *,
    request: CompileRequestIR,
    plan: SourceAcquisitionIR,
    execution_root: Path,
) -> tuple[LiveCaptureSet, LiveRunClosure]:
    """Persist a fail-closed run when any required acquisition terminates failed."""

    attempts = LiveAttemptStore(execution_root / "attempts").terminal_for_run(
        request_sha256=request.request_sha256,
        acquisition_plan_sha256=plan.plan_sha256,
    )
    expected_ids = tuple(item.acquisition_id for item in plan.acquisitions)
    if tuple(sorted(item.acquisition_id for item in attempts)) != tuple(sorted(expected_ids)):
        raise fail(
            "LIVE_RUN_ATTEMPT_COVERAGE",
            "run closure requires exactly one terminal attempt per planned acquisition",
        )
    if not any(item.terminal_state == "failed" for item in attempts):
        raise fail("LIVE_RUN_FAILURE_REQUIRED", "failed run closure requires a failed attempt")
    dispositions: list[LiveCaptureDisposition] = []
    for attempt in sorted(attempts, key=lambda item: item.acquisition_id):
        if attempt.terminal_state == "failed":
            dispositions.append(
                LiveCaptureDisposition(
                    acquisition_id=attempt.acquisition_id,
                    required=True,
                    terminal_state="failed_required",
                    failure_code=attempt.failure_code_or_null,
                )
            )
        elif attempt.terminal_state == "captured_success":
            dispositions.append(
                LiveCaptureDisposition(
                    acquisition_id=attempt.acquisition_id,
                    required=True,
                    terminal_state="captured_unbound",
                    live_receipt_sha256=attempt.live_receipt_sha256_or_null,
                )
            )
        else:
            raise fail("LIVE_RUN_NOT_TERMINAL", "prepared attempt cannot close a run")
    capture_set = LiveCaptureSet.create(
        request_sha256=request.request_sha256,
        acquisition_plan_sha256=plan.plan_sha256,
        expected_acquisition_ids=tuple(sorted(expected_ids)),
        dispositions=tuple(dispositions),
    )
    closure = LiveAuthorityStore(execution_root / "authority").persist_closed_graph(
        capture_set=capture_set,
        attempts=attempts,
    )
    return capture_set, closure
