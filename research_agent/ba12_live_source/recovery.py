"""Idempotent RFC-0010 recovery entry points."""

from __future__ import annotations

from pathlib import Path

from research_agent.semantic_compiler.source_frontend.contracts import (
    CompileRequestIR,
    SourceAcquisitionIR,
)

from .ba3_bridge import LiveBridgeResult, bridge_capture_set_to_ba3
from .authority_store import RecoveredLiveRun, LiveAuthorityStore
from .live_receipt import (
    LiveCaptureExecutor,
    LiveCaptureRecord,
)


def recover_after_capture(
    *,
    executor: LiveCaptureExecutor,
    request: CompileRequestIR,
    plan: SourceAcquisitionIR,
    acquisition_id: str,
    attempt_id: str,
) -> LiveCaptureRecord:
    """Complete a prepared attempt using only its persisted authority and bytes."""

    return executor.recover_attempt(
        request=request,
        plan=plan,
        acquisition_id=acquisition_id,
        attempt_id=attempt_id,
    )


def recover_bridge(
    *,
    request: CompileRequestIR,
    plan: SourceAcquisitionIR,
    executor: LiveCaptureExecutor,
    snapshot_root: Path,
    staged_at_utc: str,
) -> LiveBridgeResult:
    """Reload successful attempts from disk and re-run the deterministic bridge."""

    attempts = executor.attempt_store.terminal_for_run(
        request_sha256=request.request_sha256,
        acquisition_plan_sha256=plan.plan_sha256,
    )
    records = tuple(
        executor.load_successful_record(
            request_sha256=request.request_sha256,
            acquisition_id=attempt.acquisition_id,
            attempt_id=attempt.attempt_id,
        )
        for attempt in attempts
        if attempt.terminal_state == "captured_success"
    )

    return bridge_capture_set_to_ba3(
        request=request,
        plan=plan,
        records=records,
        capture_store_root=executor.capture_store.root,
        snapshot_root=snapshot_root,
        staged_at_utc=staged_at_utc,
    )


def load_closed_run(
    *, executor: LiveCaptureExecutor, closure_sha256: str
) -> RecoveredLiveRun:
    """Load and verify a closed run graph without any previous runtime object."""

    return LiveAuthorityStore(executor.root / "authority").load_closed_run(
        closure_sha256
    )
