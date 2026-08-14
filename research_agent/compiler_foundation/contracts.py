"""Versioned BA0 compiler IR, pass, registry, diagnostic, and verdict contracts."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import sha256_json

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
STABLE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]*$")


class ContractError(ValueError):
    """Raised when a compiler contract is invalid or has been tampered with."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CompilerLayer(str, Enum):
    L0_COMPILE_INTAKE = "L0_compile_intake"
    L1_SOURCE_ACQUISITION = "L1_source_acquisition"
    L2_SOURCE_SNAPSHOT = "L2_source_snapshot"
    L3_PARSE_DISCOVER = "L3_parse_discover"
    L4_NORMALIZE_RECONCILE = "L4_normalize_reconcile"
    L5_TYPED_FACT = "L5_typed_fact"
    L6_METRIC_FORMULA = "L6_metric_formula"
    L7_EVIDENCE_GRAPH = "L7_evidence_graph"
    L8_CLAIM_GRAPH = "L8_claim_graph"
    L9_DECISION_GRAPH = "L9_decision_graph"
    L10_VERIFICATION = "L10_verification"
    L11_EMIT = "L11_emit"


class SemanticSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ReleaseEffect(str, Enum):
    NONE = "none"
    REVIEW_REQUIRED = "review_required"
    COMPILE_BLOCK = "compile_block"
    RELEASE_BLOCK = "release_block"


class QuarantineStatus(str, Enum):
    CLEAR = "clear"
    QUARANTINED = "quarantined"
    RELEASE_BLOCKED = "release_blocked"


class PassStatus(str, Enum):
    EXECUTED = "executed"
    CACHE_HIT = "cache_hit"
    REPLAYED = "replayed"
    SKIPPED = "skipped"
    FAILED = "failed"


class ProvenanceRef(StrictModel):
    contract_id: Literal["room16.compiler.provenance_ref"] = "room16.compiler.provenance_ref"
    contract_version: Literal[1] = 1
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    artifact_path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    locator: str | None = None


class QuarantineState(StrictModel):
    contract_id: Literal["room16.compiler.quarantine_state"] = "room16.compiler.quarantine_state"
    contract_version: Literal[1] = 1
    status: QuarantineStatus = QuarantineStatus.CLEAR
    reason_codes: tuple[str, ...] = ()
    diagnostic_codes: tuple[str, ...] = ()
    review_required: bool = False

    @model_validator(mode="after")
    def consistent(self) -> "QuarantineState":
        if self.status != QuarantineStatus.CLEAR and not self.reason_codes:
            raise ValueError("quarantined states require at least one reason code")
        if self.status == QuarantineStatus.CLEAR and self.review_required:
            raise ValueError("clear state cannot require quarantine review")
        return self


class CompatibilityPolicy(StrictModel):
    contract_id: Literal["room16.compiler.compatibility_policy"] = "room16.compiler.compatibility_policy"
    contract_version: Literal[1] = 1
    current_major: int = Field(ge=1)
    current_minor: int = Field(ge=0)
    minimum_reader_major: int = Field(ge=1)
    maximum_reader_major: int = Field(ge=1)
    unknown_field_policy: Literal["fail_closed"] = "fail_closed"
    unknown_id_policy: Literal["fail_closed"] = "fail_closed"
    major_change_policy: Literal["explicit_migration_required"] = "explicit_migration_required"
    minor_change_policy: Literal["additive_only"] = "additive_only"

    @model_validator(mode="after")
    def range_valid(self) -> "CompatibilityPolicy":
        if not self.minimum_reader_major <= self.current_major <= self.maximum_reader_major:
            raise ValueError("current major outside supported reader range")
        return self


DEFAULT_COMPATIBILITY = CompatibilityPolicy(
    current_major=1,
    current_minor=0,
    minimum_reader_major=1,
    maximum_reader_major=1,
)


class IREnvelope(StrictModel):
    contract_id: Literal["room16.compiler.ir_envelope"] = "room16.compiler.ir_envelope"
    contract_version: Literal[1] = 1
    ir_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    ir_version: int = Field(ge=1)
    layer: CompilerLayer
    producer_pass_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    payload: dict[str, Any]
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_refs: tuple[ProvenanceRef, ...] = ()
    quarantine: QuarantineState = QuarantineState()
    compatibility: CompatibilityPolicy = DEFAULT_COMPATIBILITY

    @classmethod
    def create(cls, *, ir_type: str, layer: CompilerLayer, producer_pass_id: str,
               payload: dict[str, Any], provenance_refs: tuple[ProvenanceRef, ...] = (),
               quarantine: QuarantineState | None = None) -> "IREnvelope":
        return cls(
            ir_type=ir_type,
            ir_version=1,
            layer=layer,
            producer_pass_id=producer_pass_id,
            payload=payload,
            payload_sha256=sha256_json(payload),
            provenance_refs=provenance_refs,
            quarantine=quarantine or QuarantineState(),
        )

    def verify_hash(self) -> None:
        if sha256_json(self.payload) != self.payload_sha256:
            raise ContractError("IR payload hash mismatch")


class RegistryEntry(StrictModel):
    entry_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    entry_version: int = Field(ge=1)
    status: Literal["active", "deprecated", "reserved"] = "active"
    definition: dict[str, Any]


class RegistryEnvelope(StrictModel):
    contract_id: Literal["room16.compiler.registry_envelope"] = "room16.compiler.registry_envelope"
    contract_version: Literal[1] = 1
    registry_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    registry_kind: Literal[
        "source", "metric", "table", "typed_fact", "formula", "evidence_policy",
        "claim", "decision", "diagnostic", "verdict"
    ]
    registry_version: int = Field(ge=1)
    owner: Literal["research"] = "research"
    entries: tuple[RegistryEntry, ...]
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    compatibility: CompatibilityPolicy = DEFAULT_COMPATIBILITY

    @model_validator(mode="after")
    def unique_sorted_entries(self) -> "RegistryEnvelope":
        ids = [entry.entry_id for entry in self.entries]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("registry entries must be unique and sorted by entry_id")
        return self

    @classmethod
    def create(cls, *, registry_id: str, registry_kind: str,
               entries: list[RegistryEntry]) -> "RegistryEnvelope":
        ordered = tuple(sorted(entries, key=lambda item: item.entry_id))
        return cls(
            registry_id=registry_id,
            registry_kind=registry_kind,
            registry_version=1,
            entries=ordered,
            content_sha256=sha256_json([item.model_dump(mode="json") for item in ordered]),
        )

    def verify_hash(self) -> None:
        value = [item.model_dump(mode="json") for item in self.entries]
        if sha256_json(value) != self.content_sha256:
            raise ContractError(f"registry hash mismatch: {self.registry_id}")

    def resolve(self, entry_id: str) -> RegistryEntry:
        self.verify_hash()
        for entry in self.entries:
            if entry.entry_id == entry_id and entry.status != "reserved":
                return entry
        raise ContractError(f"unknown or reserved registry id: {self.registry_id}:{entry_id}")


class PassManifest(StrictModel):
    contract_id: Literal["room16.compiler.pass_manifest"] = "room16.compiler.pass_manifest"
    contract_version: Literal[1] = 1
    pass_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    pass_version: int = Field(ge=1)
    layer: CompilerLayer
    ordinal: int = Field(ge=0)
    input_ir_types: tuple[str, ...]
    output_ir_type: str
    side_effect_contract: Literal["none"] = "none"
    determinism_contract: Literal["pure_same_input_same_output"] = "pure_same_input_same_output"
    cache_contract: Literal["content_addressed"] = "content_addressed"
    replay_contract: Literal["hash_verified"] = "hash_verified"
    failure_contract: Literal["fail_closed_diagnostic"] = "fail_closed_diagnostic"
    skippable: bool = False
    registry_dependencies: tuple[str, ...] = ()


class DiagnosticIR(StrictModel):
    contract_id: Literal["room16.compiler.diagnostic_ir"] = "room16.compiler.diagnostic_ir"
    contract_version: Literal[1] = 1
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")
    semantic_severity: SemanticSeverity
    release_effect: ReleaseEffect
    layer: CompilerLayer
    pass_id: str
    subject_ref: str
    source_refs: tuple[ProvenanceRef, ...] = ()
    root_cause_ref: str
    fixture_refs: tuple[str, ...] = ()
    message: str
    details: dict[str, Any] = {}


class CompileVerdictIR(StrictModel):
    contract_id: Literal["room16.compiler.compile_verdict_ir"] = "room16.compiler.compile_verdict_ir"
    contract_version: Literal[1] = 1
    compile_allowed: bool
    release_allowed: bool
    review_required: bool
    diagnostic_codes: tuple[str, ...]
    blocking_codes: tuple[str, ...]
    diagnostics_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def derive(cls, diagnostics: list[DiagnosticIR]) -> "CompileVerdictIR":
        ordered = sorted(diagnostics, key=lambda item: (item.code, item.pass_id, item.subject_ref))
        compile_blocked = any(item.release_effect == ReleaseEffect.COMPILE_BLOCK for item in ordered)
        release_blocked = any(
            item.release_effect in {ReleaseEffect.COMPILE_BLOCK, ReleaseEffect.RELEASE_BLOCK}
            for item in ordered
        )
        review = any(item.release_effect == ReleaseEffect.REVIEW_REQUIRED for item in ordered)
        blocking = tuple(
            item.code for item in ordered
            if item.release_effect in {ReleaseEffect.COMPILE_BLOCK, ReleaseEffect.RELEASE_BLOCK}
        )
        dumped = [item.model_dump(mode="json") for item in ordered]
        return cls(
            compile_allowed=not compile_blocked,
            release_allowed=not release_blocked,
            review_required=review or release_blocked,
            diagnostic_codes=tuple(item.code for item in ordered),
            blocking_codes=blocking,
            diagnostics_sha256=sha256_json(dumped),
        )


class PassExecutionRecord(StrictModel):
    contract_id: Literal["room16.compiler.pass_execution_record"] = "room16.compiler.pass_execution_record"
    contract_version: Literal[1] = 1
    pass_id: str
    pass_version: int
    ordinal: int
    status: PassStatus
    input_payload_sha256: str
    output_payload_sha256: str
    cache_key: str
    diagnostic_codes: tuple[str, ...] = ()
