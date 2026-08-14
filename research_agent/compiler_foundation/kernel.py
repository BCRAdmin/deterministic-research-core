"""Deterministic shadow pass protocol for BA1.

The kernel operates only on IR envelopes and caller-supplied pass functions.
It has no legacy-run, queue, renderer, provider, or LLM entry point.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from .canonical import sha256_json
from .contracts import (
    ContractError,
    DiagnosticIR,
    IREnvelope,
    PassExecutionRecord,
    PassManifest,
    PassStatus,
    ReleaseEffect,
    SemanticSeverity,
)
from .registry import RegistryAuthority

PassFunction = Callable[[dict[str, Any]], dict[str, Any]]


class PassProtocolError(ContractError):
    """Fail-closed pass failure carrying the canonical DiagnosticIR."""

    def __init__(self, diagnostic: DiagnosticIR) -> None:
        self.diagnostic = diagnostic
        super().__init__(f"{diagnostic.code}: {diagnostic.message}")


def _failure(*, code: str, message: str, envelope: IREnvelope,
             manifest: PassManifest | None = None, subject_ref: str) -> PassProtocolError:
    pass_id = manifest.pass_id if manifest else "foundation.kernel"
    layer = manifest.layer if manifest else envelope.layer
    return PassProtocolError(DiagnosticIR(
        code=code,
        semantic_severity=SemanticSeverity.ERROR,
        release_effect=ReleaseEffect.COMPILE_BLOCK,
        layer=layer,
        pass_id=pass_id,
        subject_ref=subject_ref,
        source_refs=envelope.provenance_refs,
        root_cause_ref=f"compiler_foundation:{code.casefold()}",
        fixture_refs=(f"negative:{code.casefold()}",),
        message=message,
    ))


def load_pass_manifests(path: Path | None = None) -> tuple[PassManifest, ...]:
    target = path or Path(__file__).with_name("config") / "pass_manifests.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("contract_id") != "room16.compiler.pass_manifest_set" or payload.get("contract_version") != 1:
        raise ContractError("unsupported pass manifest set")
    manifests = tuple(PassManifest.model_validate(item) for item in payload.get("passes", []))
    ordinals = [item.ordinal for item in manifests]
    ids = [item.pass_id for item in manifests]
    if not manifests or ordinals != sorted(ordinals) or len(ordinals) != len(set(ordinals)):
        raise ContractError("pass order is invalid")
    if len(ids) != len(set(ids)):
        raise ContractError("pass ids must be unique")
    return manifests


class PassKernel:
    def __init__(self, manifests: tuple[PassManifest, ...], authority: RegistryAuthority) -> None:
        self.manifests = manifests
        self.authority = authority
        self._cache: dict[str, IREnvelope] = {}

    def _cache_key(self, manifest: PassManifest, envelope: IREnvelope) -> str:
        return sha256_json({
            "pass_id": manifest.pass_id,
            "pass_version": manifest.pass_version,
            "input_payload_sha256": envelope.payload_sha256,
            "registry_authority_sha256": self.authority.authority_sha256,
        })

    def execute(
        self,
        initial: IREnvelope,
        implementations: dict[str, PassFunction],
        *,
        skip: frozenset[str] = frozenset(),
        replay: tuple[PassExecutionRecord, ...] | None = None,
    ) -> tuple[IREnvelope, tuple[PassExecutionRecord, ...]]:
        initial.verify_hash()
        known_ids = {item.pass_id for item in self.manifests}
        unknown_skip = set(skip) - known_ids
        if unknown_skip:
            raise _failure(
                code="PASS_ID_UNKNOWN",
                message=f"unknown pass id in skip set: {sorted(unknown_skip)}",
                envelope=initial,
                subject_ref="skip_set",
            )
        replay_ids = [item.pass_id for item in replay or ()]
        if len(replay_ids) != len(set(replay_ids)):
            raise _failure(
                code="REPLAY_PASS_ID_DUPLICATE",
                message="duplicate pass id in replay records",
                envelope=initial,
                subject_ref="replay_records",
            )
        unknown_replay = set(replay_ids) - known_ids
        if unknown_replay:
            raise _failure(
                code="REPLAY_PASS_ID_UNKNOWN",
                message=f"unknown pass id in replay records: {sorted(unknown_replay)}",
                envelope=initial,
                subject_ref="replay_records",
            )
        current = initial
        records: list[PassExecutionRecord] = []
        replay_by_id = {item.pass_id: item for item in replay or ()}
        for manifest in self.manifests:
            if manifest.pass_id in skip:
                if not manifest.skippable:
                    raise _failure(
                        code="PASS_SKIP_FORBIDDEN",
                        message=f"pass is not skippable: {manifest.pass_id}",
                        envelope=current,
                        manifest=manifest,
                        subject_ref=manifest.pass_id,
                    )
                skipped_output = IREnvelope.create(
                    ir_type=manifest.output_ir_type,
                    layer=manifest.layer,
                    producer_pass_id=manifest.pass_id,
                    payload=current.payload,
                    provenance_refs=current.provenance_refs,
                    quarantine=current.quarantine,
                )
                records.append(self._record(manifest, PassStatus.SKIPPED, current, skipped_output))
                current = skipped_output
                continue
            if current.ir_type not in manifest.input_ir_types:
                raise _failure(
                    code="PASS_INPUT_TYPE_MISMATCH",
                    message=f"pass input mismatch: {manifest.pass_id} cannot consume {current.ir_type}",
                    envelope=current,
                    manifest=manifest,
                    subject_ref=current.ir_type,
                )
            for dependency in manifest.registry_dependencies:
                try:
                    self.authority.registry(dependency)
                except ContractError as exc:
                    raise _failure(
                        code="PASS_REGISTRY_DEPENDENCY_UNKNOWN",
                        message=str(exc),
                        envelope=current,
                        manifest=manifest,
                        subject_ref=dependency,
                    ) from exc
            implementation = implementations.get(manifest.pass_id)
            if implementation is None:
                raise _failure(
                    code="PASS_IMPLEMENTATION_MISSING",
                    message=f"missing pass implementation: {manifest.pass_id}",
                    envelope=current,
                    manifest=manifest,
                    subject_ref=manifest.pass_id,
                )
            cache_key = self._cache_key(manifest, current)
            prior = replay_by_id.get(manifest.pass_id)
            if prior is not None:
                if prior.cache_key != cache_key or prior.input_payload_sha256 != current.payload_sha256:
                    raise _failure(
                        code="REPLAY_INPUT_HASH_MISMATCH",
                        message=f"replay input mismatch: {manifest.pass_id}",
                        envelope=current,
                        manifest=manifest,
                        subject_ref=manifest.pass_id,
                    )
                output_payload = self._invoke(implementation, current, manifest)
                candidate = IREnvelope.create(
                    ir_type=manifest.output_ir_type,
                    layer=manifest.layer,
                    producer_pass_id=manifest.pass_id,
                    payload=output_payload,
                    provenance_refs=current.provenance_refs,
                    quarantine=current.quarantine,
                )
                if candidate.payload_sha256 != prior.output_payload_sha256:
                    raise _failure(
                        code="REPLAY_OUTPUT_HASH_MISMATCH",
                        message=f"replay output mismatch: {manifest.pass_id}",
                        envelope=current,
                        manifest=manifest,
                        subject_ref=manifest.pass_id,
                    )
                status = PassStatus.REPLAYED
            elif cache_key in self._cache:
                candidate = self._cache[cache_key]
                status = PassStatus.CACHE_HIT
            else:
                output_payload = self._invoke(implementation, current, manifest)
                candidate = IREnvelope.create(
                    ir_type=manifest.output_ir_type,
                    layer=manifest.layer,
                    producer_pass_id=manifest.pass_id,
                    payload=output_payload,
                    provenance_refs=current.provenance_refs,
                    quarantine=current.quarantine,
                )
                self._cache[cache_key] = candidate
                status = PassStatus.EXECUTED
            records.append(self._record(manifest, status, current, candidate, cache_key))
            current = candidate
        return current, tuple(records)

    def _invoke(self, implementation: PassFunction, current: IREnvelope,
                manifest: PassManifest) -> dict[str, Any]:
        try:
            output = implementation(current.payload)
        except Exception as exc:
            raise _failure(
                code="PASS_EXECUTION_FAILED",
                message=f"pass execution failed: {manifest.pass_id}: {type(exc).__name__}",
                envelope=current,
                manifest=manifest,
                subject_ref=manifest.pass_id,
            ) from exc
        if not isinstance(output, dict):
            raise _failure(
                code="PASS_OUTPUT_INVALID",
                message=f"pass output must be an object: {manifest.pass_id}",
                envelope=current,
                manifest=manifest,
                subject_ref=manifest.output_ir_type,
            )
        return output

    def _record(self, manifest: PassManifest, status: PassStatus, input_ir: IREnvelope,
                output_ir: IREnvelope, cache_key: str | None = None) -> PassExecutionRecord:
        return PassExecutionRecord(
            pass_id=manifest.pass_id,
            pass_version=manifest.pass_version,
            ordinal=manifest.ordinal,
            status=status,
            input_payload_sha256=input_ir.payload_sha256,
            output_payload_sha256=output_ir.payload_sha256,
            cache_key=cache_key or self._cache_key(manifest, input_ir),
        )


def identity_shadow_pass(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a detached payload copy without semantic transformation."""
    return json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
