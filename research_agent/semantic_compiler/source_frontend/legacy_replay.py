"""Shadow replay of accepted Authority-v3 Source Snapshot v4 archives into BA3 IR."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import CompilerLayer

from .offline import OfflineSourceInput, freeze_offline_sources
from .planner import _fail, build_compile_request, plan_source_acquisition


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _one_name(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
            pass_id="ba3.l2.freeze_source_snapshot",
            subject=suffix,
            message="accepted canary archive does not contain exactly one required legacy artifact",
            root_cause="legacy_canary_archive_shape_invalid",
        )
    return matches[0]


def replay_legacy_snapshot_zip(*, archive: Path, work_root: Path) -> dict[str, Any]:
    """Read a frozen candidate ZIP, verify v4 source bytes, and emit BA3 shadow IR."""

    archive = archive.resolve()
    archive_hash_before = _archive_sha256(archive)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        manifest_name = _one_name(
            names,
            "/authority_bundle/source_snapshot_manifest.json",
        )
        data_packet_name = _one_name(names, "/authority_bundle/data_packet.json")
        manifest_bytes = bundle.read(manifest_name)
        manifest = json.loads(manifest_bytes)
        data_packet = json.loads(bundle.read(data_packet_name))
        if (
            manifest.get("contract_id") != "room16.source_snapshot_manifest"
            or manifest.get("contract_version") != 4
            or manifest.get("all_sources_dispositioned") is not True
            or manifest.get("blocking_source_ids") != []
        ):
            raise _fail(
                code="VERSION_UNSUPPORTED",
                layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                pass_id="ba3.l2.freeze_source_snapshot",
                subject=str(manifest.get("contract_id") or "legacy_snapshot"),
                message="legacy source snapshot is not an accepted complete v4 input",
                root_cause="legacy_source_snapshot_contract_invalid",
            )
        ticker = str(manifest["ticker"]).upper()
        as_of_date = str(manifest["as_of_date"])
        resolution = {
            "input": ticker,
            "inputKind": "ticker",
            "ticker": ticker,
            "companyName": data_packet.get("company_name"),
            "exchange": data_packet.get("exchange_display_name")
            or data_packet.get("exchange"),
            "exchangeCode": data_packet.get("exchange"),
            "jurisdiction": data_packet.get("jurisdiction"),
            "isin": data_packet.get("isin"),
            "wkn": data_packet.get("wkn"),
            "source": "accepted_authority_v3_canary",
            "status": "supported",
            "runtimeReady": True,
        }
        request = build_compile_request(
            resolution,
            as_of_date=as_of_date,
            allowed_provider_ids=("nasdaq", "sec"),
            available_configuration_ids=("ROOM16_SEC_USER_AGENT",),
        )
        plan = plan_source_acquisition(request)
        acquisition_by_provider = {
            item.provider_id: item.acquisition_id for item in plan.acquisitions
        }
        dispositions_by_snapshot: dict[str, list[dict[str, Any]]] = {}
        for disposition in manifest["source_dispositions"]:
            for snapshot_id in disposition.get("snapshot_ids") or []:
                dispositions_by_snapshot.setdefault(snapshot_id, []).append(disposition)

        archive_prefix = manifest_name.rsplit("source_snapshot_manifest.json", 1)[0]
        source_prefix = f"{archive_prefix}source_snapshots/"
        staging_root = work_root.resolve() / "legacy-staging" / ticker
        staging_root.mkdir(parents=True, exist_ok=True)
        offline_inputs: list[OfflineSourceInput] = []
        for artifact in manifest["artifacts"]:
            relative = str(artifact["path"])
            if relative.startswith("/") or ".." in Path(relative).parts:
                raise _fail(
                    code="CONTRACT_HASH_MISMATCH",
                    layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                    pass_id="ba3.l2.freeze_source_snapshot",
                    subject=relative,
                    message="legacy snapshot path is unsafe",
                    root_cause="legacy_snapshot_path_escape",
                )
            payload = bundle.read(f"{source_prefix}{relative}")
            if (
                _sha256_bytes(payload) != artifact["sha256"]
                or len(payload) != artifact["bytes"]
            ):
                raise _fail(
                    code="CONTRACT_HASH_MISMATCH",
                    layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
                    pass_id="ba3.l2.freeze_source_snapshot",
                    subject=str(artifact["snapshot_id"]),
                    message="legacy source artifact bytes differ from the v4 manifest",
                    root_cause="legacy_snapshot_artifact_tamper",
                )
            staged_path = staging_root / relative
            staged_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.write_bytes(payload)
            linked = dispositions_by_snapshot.get(str(artifact["snapshot_id"]), [])
            primary = linked[0] if linked else None
            if relative.startswith("prices/"):
                provider_id = "nasdaq"
                source_type = "exchange_ohlcv"
            else:
                provider_id = "sec"
                source_type = (
                    str(primary.get("source_type"))
                    if primary and primary.get("source_type") in {"company_ir", "sec_filing"}
                    else "sec_filing"
                )
            source_id = (
                str(primary["source_id"])
                if primary and primary.get("source_id")
                else f"legacy:{artifact['snapshot_id']}"
            )
            captured_at = str(artifact.get("captured_at") or manifest["generated_at"])
            offline_inputs.append(
                OfflineSourceInput(
                    acquisition_id=acquisition_by_provider[provider_id],
                    source_id=source_id,
                    source_type=source_type,
                    provider_id=provider_id,
                    path=staged_path,
                    original_locator=f"authority-v3://source_snapshots/{relative}",
                    retrieved_at=captured_at,
                    available_at=captured_at,
                    media_type=artifact.get("media_type"),
                    availability_basis="accepted_authority_v3_snapshot",
                    disposition=(
                        "material_evidence" if linked else "supporting_material"
                    ),
                )
            )

    snapshot_root = work_root.resolve() / "ba3-snapshot" / ticker
    snapshot = freeze_offline_sources(
        request=request,
        plan=plan,
        inputs=tuple(offline_inputs),
        snapshot_root=snapshot_root,
    )
    archive_hash_after = _archive_sha256(archive)
    if archive_hash_after != archive_hash_before:
        raise _fail(
            code="CONTRACT_HASH_MISMATCH",
            layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
            pass_id="ba3.l2.freeze_source_snapshot",
            subject=archive.name,
            message="canary archive changed during shadow replay",
            root_cause="canary_archive_changed",
        )
    return {
        "status": "pass",
        "ticker": ticker,
        "as_of_date": as_of_date,
        "archive": archive.name,
        "archive_sha256_before": archive_hash_before,
        "archive_sha256_after": archive_hash_after,
        "legacy_snapshot_manifest_sha256": _sha256_bytes(manifest_bytes),
        "legacy_snapshot_semantic_sha256": sha256_json(manifest),
        "legacy_artifact_count": len(manifest["artifacts"]),
        "legacy_source_disposition_count": len(manifest["source_dispositions"]),
        "compile_request_sha256": request.request_sha256,
        "source_acquisition_plan_sha256": plan.plan_sha256,
        "source_snapshot_ir_sha256": snapshot.snapshot_sha256,
        "ba3_artifact_count": len(snapshot.artifacts),
        "ba3_receipt_count": len(snapshot.retrieval_receipts),
        "all_legacy_sources_dispositioned": manifest["all_sources_dispositioned"],
        "all_ba3_artifacts_dispositioned": snapshot.all_sources_dispositioned,
        "candidate_archive_unchanged": True,
    }
