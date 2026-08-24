"""Idempotent RFC-0010 recovery entry points."""

from __future__ import annotations

from pathlib import Path

from research_agent.semantic_compiler.source_frontend.contracts import (
    CompileRequestIR,
    SourceAcquisitionIR,
)

from .ba3_bridge import LiveBridgeResult, bridge_capture_set_to_ba3
from .contracts import LiveCaptureArtifact
from .live_receipt import (
    LiveCaptureExecutor,
    LiveCaptureRecord,
    ProviderResponse,
)


def recover_after_capture(
    *,
    executor: LiveCaptureExecutor,
    request: CompileRequestIR,
    plan: SourceAcquisitionIR,
    acquisition_id: str,
    attempt_id: str,
    response: ProviderResponse,
    artifact: LiveCaptureArtifact,
) -> LiveCaptureRecord:
    """Complete an attempt whose immutable capture exists but receipt does not."""

    executor.capture_store.read_verified(artifact)
    return executor.finalize_receipt(
        request=request,
        plan=plan,
        acquisition_id=acquisition_id,
        attempt_id=attempt_id,
        response=response,
        artifact=artifact,
    )


def recover_bridge(
    *,
    request: CompileRequestIR,
    plan: SourceAcquisitionIR,
    records: tuple[LiveCaptureRecord, ...],
    capture_store_root: Path,
    snapshot_root: Path,
    staged_at_utc: str,
) -> LiveBridgeResult:
    """Re-run the deterministic bridge after any post-receipt crash."""

    return bridge_capture_set_to_ba3(
        request=request,
        plan=plan,
        records=records,
        capture_store_root=capture_store_root,
        snapshot_root=snapshot_root,
        staged_at_utc=staged_at_utc,
    )
