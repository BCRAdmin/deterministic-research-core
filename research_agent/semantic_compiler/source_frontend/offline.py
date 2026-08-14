"""Offline, content-addressed BA3 source acquisition and snapshot execution."""

from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path

from research_agent.compiler_foundation.contracts import CompilerLayer
from research_agent.compiler_foundation.registry import RegistryAuthority

from .contracts import (
    CompileRequestIR,
    RetrievalReceiptIR,
    SourceAcquisitionIR,
    SourceArtifactIR,
    SourceDispositionIR,
    SourceSnapshotIR,
    safe_suffix,
)
from .planner import SourceFrontendError, _fail


@dataclass(frozen=True)
class OfflineSourceInput:
    acquisition_id: str
    source_id: str
    source_type: str
    provider_id: str
    path: Path
    original_locator: str
    retrieved_at: str
    available_at: str
    published_at: str | None = None
    filing_date: str | None = None
    media_type: str | None = None
    disposition: str = "material_evidence"
    transport: str = "offline_replay"
    availability_basis: str = "public_timestamp"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _assert_no_lookahead(item: OfflineSourceInput, as_of_date: str) -> None:
    if item.availability_basis == "accepted_authority_v3_snapshot":
        if item.transport != "offline_replay" or not item.original_locator.startswith(
            "authority-v3://"
        ):
            raise _fail(
                code="VERSION_UNSUPPORTED",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.bind_retrieval_receipts",
                subject=item.source_id,
                message="legacy availability basis is restricted to accepted Authority-v3 replay",
                root_cause="legacy_availability_basis_misused",
            )
        return
    if item.availability_basis != "public_timestamp":
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.bind_retrieval_receipts",
            subject=item.source_id,
            message="retrieval receipt availability basis is unsupported",
            root_cause="availability_basis_invalid",
        )
    cutoff = datetime.combine(
        date.fromisoformat(as_of_date),
        time.max,
        tzinfo=timezone.utc,
    )
    try:
        available = _parse_time(item.available_at)
        published = _parse_time(item.published_at) if item.published_at else None
    except ValueError as exc:
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.bind_retrieval_receipts",
            subject=item.source_id,
            message="retrieval receipt has an unsupported or timezone-free source timestamp",
            root_cause="retrieval_time_contract_invalid",
        ) from exc
    if available > cutoff or (published is not None and published > cutoff):
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.bind_retrieval_receipts",
            subject=item.source_id,
            message="source was not publicly available by the compile as-of cutoff",
            root_cause="source_lookahead_detected",
        )


def _receipt_id(item: OfflineSourceInput, payload_sha256: str) -> str:
    digest = hashlib.sha256(
        (
            f"{item.acquisition_id}\0{item.source_id}\0{item.original_locator}\0"
            f"{payload_sha256}\0{item.available_at}"
        ).encode("utf-8")
    ).hexdigest()
    return f"receipt.{digest}"


def freeze_offline_sources(
    *,
    request: CompileRequestIR,
    plan: SourceAcquisitionIR,
    inputs: tuple[OfflineSourceInput, ...],
    snapshot_root: Path,
) -> SourceSnapshotIR:
    """Verify staged bytes, write content-addressed snapshots and emit SourceSnapshotIR@1."""

    if request.request_sha256 != plan.request_sha256:
        raise _fail(
            code="CONTRACT_HASH_MISMATCH",
            layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
            pass_id="ba3.l2.freeze_source_snapshot",
            subject="source_acquisition.request_sha256",
            message="source acquisition plan belongs to a different compile request",
            root_cause="compile_request_plan_hash_mismatch",
        )
    if not inputs:
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
            pass_id="ba3.l2.freeze_source_snapshot",
            subject="offline_inputs",
            message="offline source execution requires at least one verified payload",
            root_cause="offline_source_inputs_empty",
        )
    acquisition_by_id = {item.acquisition_id: item for item in plan.acquisitions}
    provided_acquisitions = {item.acquisition_id for item in inputs}
    if provided_acquisitions != set(acquisition_by_id):
        raise _fail(
            code="UNKNOWN_REGISTRY_ID",
            layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
            pass_id="ba3.l2.freeze_source_snapshot",
            subject=",".join(sorted(set(acquisition_by_id) ^ provided_acquisitions)),
            message="offline payload set does not cover the exact acquisition plan",
            root_cause="acquisition_payload_coverage_mismatch",
        )

    source_registry = RegistryAuthority.load().registry("room16.registry.source")
    artifacts_by_id: dict[str, SourceArtifactIR] = {}
    receipts: list[RetrievalReceiptIR] = []
    dispositions: list[SourceDispositionIR] = []
    receipt_ids: set[str] = set()
    source_root = snapshot_root.resolve()
    source_root.mkdir(parents=True, exist_ok=True)

    for item in sorted(inputs, key=lambda value: (value.source_id, value.original_locator)):
        acquisition = acquisition_by_id[item.acquisition_id]
        if item.provider_id != acquisition.provider_id:
            raise _fail(
                code="UNKNOWN_REGISTRY_ID",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.bind_retrieval_receipts",
                subject=item.provider_id,
                message="retrieval receipt provider differs from the acquisition plan",
                root_cause="retrieval_provider_mismatch",
            )
        if item.source_type not in acquisition.allowed_source_types:
            raise _fail(
                code="UNKNOWN_REGISTRY_ID",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.bind_retrieval_receipts",
                subject=item.source_type,
                message="retrieval source type is not allowed by the selected adapter",
                root_cause="retrieval_source_type_not_allowed",
            )
        try:
            source_registry.resolve(item.source_type)
        except ValueError as exc:
            raise _fail(
                code="UNKNOWN_REGISTRY_ID",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.bind_retrieval_receipts",
                subject=item.source_type,
                message="retrieval source type is absent from Foundation Registry Authority",
                root_cause="retrieval_source_type_unknown",
            ) from exc
        if item.disposition not in {"material_evidence", "supporting_material"}:
            raise _fail(
                code="VERSION_UNSUPPORTED",
                layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                pass_id="ba3.l2.freeze_source_snapshot",
                subject=item.source_id,
                message="offline source disposition is unsupported",
                root_cause="source_disposition_invalid",
            )
        _assert_no_lookahead(item, request.as_of_date)
        input_path = item.path.resolve()
        if not input_path.is_file() or input_path.stat().st_size < 1:
            raise _fail(
                code="CONTRACT_HASH_MISMATCH",
                layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                pass_id="ba3.l2.freeze_source_snapshot",
                subject=item.source_id,
                message="retrieval receipt payload is missing or empty",
                root_cause="retrieval_payload_missing",
            )
        payload_sha256 = _sha256(input_path)
        payload_bytes = input_path.stat().st_size
        suffix = safe_suffix(item.original_locator or input_path.name)
        relative = Path("sources") / payload_sha256[:2] / f"{payload_sha256}{suffix}"
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if _sha256(destination) != payload_sha256 or destination.stat().st_size != payload_bytes:
                raise _fail(
                    code="CONTRACT_HASH_MISMATCH",
                    layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                    pass_id="ba3.l2.freeze_source_snapshot",
                    subject=relative.as_posix(),
                    message="existing content-addressed snapshot bytes do not match their path",
                    root_cause="snapshot_destination_tampered",
                )
        else:
            destination.write_bytes(input_path.read_bytes())
        snapshot_id = f"snapshot.{payload_sha256}"
        media_type = item.media_type or mimetypes.guess_type(
            item.original_locator
        )[0] or "application/octet-stream"
        artifacts_by_id[snapshot_id] = SourceArtifactIR(
            snapshot_id=snapshot_id,
            path=relative.as_posix(),
            sha256=payload_sha256,
            bytes=payload_bytes,
            media_type=media_type,
        )
        receipt_id = _receipt_id(item, payload_sha256)
        if receipt_id in receipt_ids:
            raise _fail(
                code="CONTRACT_HASH_MISMATCH",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.bind_retrieval_receipts",
                subject=receipt_id,
                message="duplicate retrieval receipt identity",
                root_cause="retrieval_receipt_duplicate",
            )
        receipt_ids.add(receipt_id)
        receipts.append(
            RetrievalReceiptIR(
                receipt_id=receipt_id,
                acquisition_id=item.acquisition_id,
                source_id=item.source_id,
                source_type=item.source_type,
                provider_id=item.provider_id,
                original_locator=item.original_locator,
                media_type=media_type,
                payload_sha256=payload_sha256,
                payload_bytes=payload_bytes,
                retrieved_at=item.retrieved_at,
                available_at=item.available_at,
                published_at=item.published_at,
                filing_date=item.filing_date,
                availability_basis=item.availability_basis,
                transport=item.transport,
            )
        )
        dispositions.append(
            SourceDispositionIR(
                source_id=item.source_id,
                source_type=item.source_type,
                provider_id=item.provider_id,
                receipt_id=receipt_id,
                snapshot_ids=(snapshot_id,),
                disposition=item.disposition,
            )
        )

    snapshot = SourceSnapshotIR.create(
        request_sha256=request.request_sha256,
        acquisition_plan_sha256=plan.plan_sha256,
        ticker=request.instrument.ticker,
        as_of_date=request.as_of_date,
        artifacts=tuple(artifacts_by_id.values()),
        retrieval_receipts=tuple(receipts),
        source_dispositions=tuple(dispositions),
    )
    manifest_path = source_root / "source_snapshot_ir.json"
    manifest_path.write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verify_source_snapshot(snapshot, snapshot_root=source_root)
    return snapshot


def verify_source_snapshot(snapshot: SourceSnapshotIR, *, snapshot_root: Path) -> None:
    """Rehash every SourceSnapshotIR artifact before parsing or replay."""

    root = snapshot_root.resolve()
    for artifact in snapshot.artifacts:
        target = (root / artifact.path).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise SourceFrontendError(
                _fail(
                    code="CONTRACT_HASH_MISMATCH",
                    layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                    pass_id="ba3.l2.freeze_source_snapshot",
                    subject=artifact.path,
                    message="source snapshot path escapes the snapshot root",
                    root_cause="snapshot_path_escape",
                ).diagnostic
            ) from exc
        if (
            not target.is_file()
            or target.stat().st_size != artifact.bytes
            or _sha256(target) != artifact.sha256
        ):
            raise _fail(
                code="CONTRACT_HASH_MISMATCH",
                layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                pass_id="ba3.l2.freeze_source_snapshot",
                subject=artifact.snapshot_id,
                message="source snapshot artifact failed byte/hash verification",
                root_cause="source_snapshot_tamper",
            )
