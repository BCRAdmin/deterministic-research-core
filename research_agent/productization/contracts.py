"""Versioned BA10 Artifact ABI contracts.

These contracts live above the frozen Semantic Compiler Wave.  They package
verified L0-L10 artifacts; they do not change or reinterpret those artifacts.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"
SAFE_PATH_PATTERN = r"^[A-Za-z0-9._/-]+$"


class ArtifactRecord(StrictModel):
    artifact_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    artifact_kind: str = Field(pattern=r"^[a-z][a-z0-9_.-]*$")
    contract_id: str = Field(min_length=1)
    contract_version: int | str
    layer: str
    producer_pass_id: str
    relative_path: str = Field(pattern=SAFE_PATH_PATTERN)
    media_type: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    byte_length: int = Field(ge=0)
    required: bool = True
    owner: Literal["research_compiler"] = "research_compiler"
    compatibility_rule: Literal[
        "exact_hash",
        "byte_identical_compatibility_view",
    ] = "exact_hash"
    authoritative: bool
    compatibility_only: bool = False
    dependency_sha256s: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()

    @field_validator("relative_path")
    @classmethod
    def relative_path_is_safe(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("artifact path must be relative and traversal-free")
        return value

    @model_validator(mode="after")
    def authority_flags_are_consistent(self) -> "ArtifactRecord":
        if self.authoritative and self.compatibility_only:
            raise ValueError("compatibility artifacts cannot be semantic authority")
        if self.dependency_sha256s != tuple(sorted(set(self.dependency_sha256s))):
            raise ValueError("artifact dependencies must be unique and sorted")
        return self


class BundleSectionRecord(StrictModel):
    section_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    schema_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    sha256: str = Field(pattern=SHA256_PATTERN)
    owner: Literal["research_compiler"] = "research_compiler"
    compatibility_rule: Literal[
        "exact_version",
        "same_major_additive",
        "immutable_reference",
        "byte_identical_compatibility_view",
    ]
    required: bool
    artifact_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def artifact_ids_are_closed(self) -> "BundleSectionRecord":
        if self.artifact_ids != tuple(sorted(set(self.artifact_ids))):
            raise ValueError("section artifact ids must be unique and sorted")
        return self


class CompilerIdentity(StrictModel):
    compiler_name: Literal["Room16 Financial Research Compiler"] = (
        "Room16 Financial Research Compiler"
    )
    foundation_version: Literal["1.0.0"] = "1.0.0"
    registry_foundation_version: Literal["1.1.0"] = "1.1.0"
    semantic_wave_version: Literal["1.0.0"] = "1.0.0"
    compiler_version: Literal["1.0.0"] = "1.0.0"
    semantic_wave_version_lock: Literal[
        "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
    ] = "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
    pass_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    ir_schema_set_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_authority_sha256: str = Field(pattern=SHA256_PATTERN)


class CompileIdentity(StrictModel):
    ticker: str = Field(pattern=r"^[A-Z0-9.^-]+$")
    as_of_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_archive_sha256: str = Field(pattern=SHA256_PATTERN)
    final_compile_state_sha256: str = Field(pattern=SHA256_PATTERN)
    verification_report_sha256: str = Field(pattern=SHA256_PATTERN)
    replay_sha256: str = Field(pattern=SHA256_PATTERN)


class CompatibilityState(StrictModel):
    mode: Literal[
        "authority_v3_compatibility_shadow",
        "bundle_dual_read",
        "bundle_primary_with_v3_view",
        "bundle_native",
    ]
    compiler_mode: Literal["compatibility_shadow"] = "compatibility_shadow"
    source_native_fact_generation: Literal[False] = False
    authority_bundle_contract_id: Literal["room16.research_authority_bundle"] = (
        "room16.research_authority_bundle"
    )
    authority_bundle_contract_version: Literal[3] = 3
    bridge_contract_id: Literal["room16.authority_v3_compatibility_view"] = (
        "room16.authority_v3_compatibility_view"
    )
    bridge_contract_version: Literal[1] = 1


class EligibilityState(StrictModel):
    compile_allowed: bool
    renderer_eligible: bool
    release_ready: Literal[False] = False
    publication_allowed: Literal[False] = False
    renderer_cutover: Literal[False] = False
    ba11_authorized: Literal[False] = False
    ba12_authorized: Literal[False] = False


class ConsumerCapabilities(StrictModel):
    required_bundle_major: Literal[1] = 1
    required_canonicalization: Literal["room16.foundation.canonical_json@1"] = (
        "room16.foundation.canonical_json@1"
    )
    required_hash_algorithm: Literal["sha256"] = "sha256"
    unknown_optional_field_policy: Literal["preserve_ignore"] = "preserve_ignore"
    unknown_required_field_policy: Literal["fail_closed"] = "fail_closed"
    missing_required_artifact_policy: Literal["fail_closed"] = "fail_closed"


class CompilerArtifactBundleManifest(StrictModel):
    contract_id: Literal["room16.compiler_artifact_bundle"] = (
        "room16.compiler_artifact_bundle"
    )
    contract_version: Literal[1] = 1
    schema_version: Literal["1.1.0"] = "1.1.0"
    canonicalization_profile: Literal["room16.foundation.canonical_json@1"] = (
        "room16.foundation.canonical_json@1"
    )
    hash_algorithm: Literal["sha256"] = "sha256"
    bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    compiler_identity: CompilerIdentity
    compile_identity: CompileIdentity
    registry_lock: dict[str, Any]
    artifact_index_sha256: str = Field(pattern=SHA256_PATTERN)
    artifacts: tuple[ArtifactRecord, ...]
    section_index_sha256: str = Field(pattern=SHA256_PATTERN)
    sections: tuple[BundleSectionRecord, ...]
    compatibility: CompatibilityState
    eligibility: EligibilityState
    consumer_capabilities: ConsumerCapabilities = ConsumerCapabilities()
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...] = ()
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def artifact_index_is_closed(self) -> "CompilerArtifactBundleManifest":
        ids = [item.artifact_id for item in self.artifacts]
        paths = [item.relative_path for item in self.artifacts]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("bundle artifact ids must be unique and sorted")
        if len(paths) != len(set(paths)):
            raise ValueError("bundle artifact paths must be unique")
        dumped = [item.model_dump(mode="json") for item in self.artifacts]
        if sha256_json(dumped) != self.artifact_index_sha256:
            raise ValueError("bundle artifact index hash mismatch")
        required_kinds = {item.artifact_kind for item in self.artifacts if item.required}
        missing = set(self.required_sections) - required_kinds
        if missing:
            raise ValueError(f"bundle required section missing:{','.join(sorted(missing))}")
        section_ids = [item.section_id for item in self.sections]
        if section_ids != sorted(section_ids) or len(section_ids) != len(set(section_ids)):
            raise ValueError("bundle section ids must be unique and sorted")
        section_dump = [item.model_dump(mode="json") for item in self.sections]
        if sha256_json(section_dump) != self.section_index_sha256:
            raise ValueError("bundle section index hash mismatch")
        missing_section_ids = set(REQUIRED_BUNDLE_SECTION_IDS) - {
            item.section_id for item in self.sections if item.required
        }
        if missing_section_ids:
            raise ValueError(
                "bundle required semantic section missing:"
                + ",".join(sorted(missing_section_ids))
            )
        artifact_ids = set(ids)
        unknown_artifact_ids = {
            artifact_id
            for section in self.sections
            for artifact_id in section.artifact_ids
            if artifact_id not in artifact_ids
        }
        if unknown_artifact_ids:
            raise ValueError(
                "bundle section references unknown artifacts:"
                + ",".join(sorted(unknown_artifact_ids))
            )
        return self

    def verify_bundle_hash(self) -> None:
        body = self.model_dump(mode="json", exclude={"bundle_sha256"})
        if sha256_json(body) != self.bundle_sha256:
            raise ValueError("bundle manifest hash mismatch")


REQUIRED_ARTIFACT_KINDS = (
    "compile_state",
    "diagnostics",
    "compile_verdict",
    "execution_attestation",
    "pass_execution_records",
    "source_provenance",
    "parsed_table_ir",
    "typed_facts",
    "metrics",
    "formula_evaluations",
    "evidence_graph",
    "claim_graph",
    "decision_graph",
    "verification_plan",
    "verification_report",
    "authority_v3_bridge",
    "renderer_projection",
)

REQUIRED_BUNDLE_SECTION_IDS = (
    "artifact_hashes",
    "claim_graph",
    "compatibility_state",
    "compile_identity",
    "compile_verdict",
    "compiler_version",
    "decision_graph",
    "diagnostics",
    "evidence_graph",
    "formula_evaluations",
    "foundation_version",
    "ir_references",
    "metrics",
    "pass_manifest",
    "registry_lock",
    "source_provenance",
    "typed_facts",
)
