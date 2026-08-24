"""Independent fail-closed verification for RFC-0010 capture graphs."""

from __future__ import annotations

from pathlib import Path

from research_agent.compiler_foundation.canonical import sha256_json

from .ba3_bridge import LiveBridgeResult
from .capture_store import ContentAddressedCaptureStore
from .contracts import fail
from .live_receipt import LiveCaptureRecord

FORBIDDEN_SEMANTIC_AUTHORITY = ("fact", "metric", "claim", "decision", "rating")


def verify_live_bridge(
    *,
    records: tuple[LiveCaptureRecord, ...],
    result: LiveBridgeResult,
    capture_store_root: Path,
) -> dict[str, object]:
    if not result.capture_set.eligible_for_native_compile:
        raise fail("LIVE_CAPTURE_SET_INELIGIBLE", "capture set is not eligible")
    if result.closure is None or not result.closure.eligible_for_native_compile:
        raise fail("LIVE_RUN_CLOSURE_MISSING", "durable eligible run closure is missing")
    if result.capture_set.expected_acquisition_ids != tuple(
        sorted(record.receipt.acquisition_id for record in records)
    ):
        raise fail("LIVE_CAPTURE_SET_UNEXPECTED", "capture set and live records differ")
    binding_by_id = {item.acquisition_id: item for item in result.bindings}
    ba3_by_id = {
        item.acquisition_id: item for item in result.snapshot.retrieval_receipts
    }
    store = ContentAddressedCaptureStore(capture_store_root)
    for record in records:
        live = record.receipt
        artifact = record.artifact
        payload = store.read_verified(artifact)
        if len(payload) != live.payload_bytes:
            raise fail("LIVE_CAPTURE_PAYLOAD_SIZE_MISMATCH", "live receipt size differs")
        if live.normalized_outcome != "success":
            raise fail("LIVE_RECEIPT_OUTCOME_INVALID", "successful receipt lacks success outcome")
        binding = binding_by_id.get(live.acquisition_id)
        ba3 = ba3_by_id.get(live.acquisition_id)
        if binding is None or ba3 is None:
            raise fail("LIVE_CAPTURE_BINDING_MISSING", "live acquisition is not fully bound")
        if (
            binding.request_sha256 != live.request_sha256
            or binding.acquisition_plan_sha256 != live.acquisition_plan_sha256
            or binding.provider_id != live.provider_id
            or binding.source_id != live.source_id
            or binding.source_type != live.source_type
            or binding.live_receipt_sha256 != live.receipt_sha256
            or binding.capture_artifact_sha256 != artifact.artifact_sha256
            or binding.payload_sha256 != live.payload_sha256
            or binding.payload_bytes != live.payload_bytes
            or binding.ba3_source_snapshot_sha256 != result.snapshot.snapshot_sha256
            or binding.ba3_retrieval_receipt_sha256
            != sha256_json(ba3.model_dump(mode="json"))
        ):
            raise fail("LIVE_CAPTURE_BINDING_MISMATCH", "cross-stage binding is invalid")
        if (
            ba3.payload_sha256 != live.payload_sha256
            or ba3.payload_bytes != live.payload_bytes
            or ba3.provider_id != live.provider_id
            or ba3.source_id != live.source_id
            or ba3.source_type != live.source_type
            or ba3.transport != "offline_replay"
            or ba3.variable_cost_incurred is not False
        ):
            raise fail("LIVE_BA3_BINDING_MISMATCH", "BA3 replay identity is invalid")
    if (
        result.closure.capture_set_sha256 != result.capture_set.set_sha256
        or result.closure.ba3_source_snapshot_sha256_or_null
        != result.snapshot.snapshot_sha256
        or result.closure.binding_sha256s
        != tuple(sorted(item.binding_sha256 for item in result.bindings))
    ):
        raise fail("LIVE_RUN_CLOSURE_MISMATCH", "durable closure differs from live graph")
    return {
        "binding_count": len(result.bindings),
        "capture_set_sha256": result.capture_set.set_sha256,
        "contract_id": "room16.rfc0010.live_bridge_verification@1",
        "semantic_authority_created": False,
        "snapshot_sha256": result.snapshot.snapshot_sha256,
        "status": "PASS",
    }


def verify_authority_boundary() -> dict[str, object]:
    from .contracts import (
        LiveCaptureArtifact,
        LiveCaptureBinding,
        LiveCaptureSet,
        LiveRetrievalReceipt,
    )

    models = (
        LiveCaptureArtifact,
        LiveCaptureBinding,
        LiveCaptureSet,
        LiveRetrievalReceipt,
    )
    field_names = {
        field.lower() for model in models for field in model.model_fields
    }
    violations = sorted(
        forbidden
        for forbidden in FORBIDDEN_SEMANTIC_AUTHORITY
        if forbidden in field_names or f"{forbidden}s" in field_names
    )
    if violations:
        raise fail(
            "LIVE_AUTHORITY_BOUNDARY_VIOLATION",
            f"live contracts create semantic authority fields: {','.join(violations)}",
        )
    return {
        "contract_id": "room16.rfc0010.authority_boundary_verification@1",
        "forbidden_authority_fields": list(FORBIDDEN_SEMANTIC_AUTHORITY),
        "status": "PASS",
    }
