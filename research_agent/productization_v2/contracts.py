"""Strict, hash-bound contracts for CompilerArtifactBundle v2."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel
from research_agent.productization.contracts import (
    REQUIRED_ARTIFACT_KINDS,
    REQUIRED_BUNDLE_SECTION_IDS,
    ArtifactRecord,
    BundleSectionRecord,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"
HEX_PATTERN = r"^[0-9a-f]+$"
UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
BA10_V1_FREEZE_SHA256 = "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e"
BA11_FREEZE_SHA256 = "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf"
SEMANTIC_WAVE_VERSION_LOCK = "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
PASS_MANIFEST_SHA256 = "854abab7764f1a26a26ac2a97585171154aaac52c2eb8ecb848e800d2da02d33"
IR_SCHEMA_SET_SHA256 = "b7b6194ad05b023c1c1cb1fe2a5cba6d5f830dfd6ee400df954c35c997847f4c"
REGISTRY_AUTHORITY_SHA256 = "55585f2242f32da4cc401455cd3186a97bf74f2c4a7feb5078e00d6a6e1ea5fb"


class CompilerIdentityV2(StrictModel):
    compiler_name: Literal["Room16 Financial Research Compiler"] = (
        "Room16 Financial Research Compiler"
    )
    foundation_version: Literal["1.0.0"] = "1.0.0"
    registry_foundation_version: Literal["1.1.0"] = "1.1.0"
    semantic_wave_version: Literal["1.0.0"] = "1.0.0"
    semantic_wave_version_lock: Literal[SEMANTIC_WAVE_VERSION_LOCK] = SEMANTIC_WAVE_VERSION_LOCK
    compiler_version: Literal["1.0.0"] = "1.0.0"
    pass_manifest_sha256: Literal[PASS_MANIFEST_SHA256] = PASS_MANIFEST_SHA256
    ir_schema_set_sha256: Literal[IR_SCHEMA_SET_SHA256] = IR_SCHEMA_SET_SHA256
    registry_authority_sha256: Literal[REGISTRY_AUTHORITY_SHA256] = REGISTRY_AUTHORITY_SHA256
    bundle_abi_version: Literal["2.0.0"] = "2.0.0"
    semantic_artifact_origin: Literal["frozen_v1_migration", "source_native"]


class CompileIdentityV2(StrictModel):
    ticker: str = Field(pattern=r"^[A-Z0-9.^-]+$")
    as_of_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    compile_request_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    source_acquisition_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    retrieval_receipt_set_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    source_snapshot_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    final_compile_state_sha256: str = Field(pattern=SHA256_PATTERN)
    verification_report_sha256: str = Field(pattern=SHA256_PATTERN)
    replay_sha256: str = Field(pattern=SHA256_PATTERN)
    migration_v1_bundle_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)


class CompatibilityStateV2(StrictModel):
    mode: Literal["bundle_dual_read", "bundle_primary_with_v3_view", "bundle_native"]
    compiler_mode: Literal["migration_dual_read", "source_native"]
    source_native_fact_generation: bool
    native_source_production: bool
    legacy_semantic_input_allowed: Literal[False] = False
    authority_v3_semantic_input_allowed: Literal[False] = False
    authority_v3_bridge_direction: Literal["bundle_to_authority_v3_only", "disabled"]

    @model_validator(mode="after")
    def truthful_mode(self) -> "CompatibilityStateV2":
        if self.mode == "bundle_native":
            if (
                self.compiler_mode != "source_native"
                or not self.source_native_fact_generation
                or not self.native_source_production
            ):
                raise ValueError("bundle_native requires truthful native source production")
        elif self.mode == "bundle_dual_read":
            if (
                self.compiler_mode != "migration_dual_read"
                or self.source_native_fact_generation
                or self.native_source_production
            ):
                raise ValueError("migration dual-read must not claim native source production")
        return self


class EligibilityStateV2(StrictModel):
    compile_allowed: bool
    renderer_eligible: bool
    renderer_cutover: bool = False
    ba11_frozen: Literal[True] = True
    ba12_cutover_candidate: bool = False
    release_ready: Literal[False] = False
    publication_allowed: Literal[False] = False
    deploy_allowed: Literal[False] = False


class EmitterIdentityV2(StrictModel):
    emitter_id: Literal["room16.compiler_artifact_bundle_builder_v2"] = (
        "room16.compiler_artifact_bundle_builder_v2"
    )
    emitter_version: Literal["2.0.0-rfc0008"] = "2.0.0-rfc0008"
    producer_pass_id: Literal["rfc0008.l11.emit_migration_bundle_v2"] = (
        "rfc0008.l11.emit_migration_bundle_v2"
    )
    implementation_sha256: str = Field(pattern=SHA256_PATTERN)
    schema_sha256: str = Field(pattern=SHA256_PATTERN)
    consumer_policy_sha256: str = Field(pattern=SHA256_PATTERN)


class CompilerArtifactBundleManifestV2(StrictModel):
    contract_id: Literal["room16.compiler_artifact_bundle"] = "room16.compiler_artifact_bundle"
    contract_version: Literal[2] = 2
    schema_version: Literal["2.0.0"] = "2.0.0"
    canonicalization_profile: Literal["room16.foundation.canonical_json@1"] = (
        "room16.foundation.canonical_json@1"
    )
    hash_algorithm: Literal["sha256"] = "sha256"
    bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    compiler_identity: CompilerIdentityV2
    emitter_identity: EmitterIdentityV2
    compile_identity: CompileIdentityV2
    compatibility: CompatibilityStateV2
    eligibility: EligibilityStateV2
    ba10_v1_freeze_sha256: Literal[BA10_V1_FREEZE_SHA256] = BA10_V1_FREEZE_SHA256
    ba11_freeze_sha256: Literal[BA11_FREEZE_SHA256] = BA11_FREEZE_SHA256
    artifact_index_sha256: str = Field(pattern=SHA256_PATTERN)
    artifacts: tuple[ArtifactRecord, ...]
    section_index_sha256: str = Field(pattern=SHA256_PATTERN)
    sections: tuple[BundleSectionRecord, ...]
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...] = ()
    extensions: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def closed_and_directional(self) -> "CompilerArtifactBundleManifestV2":
        ids = [item.artifact_id for item in self.artifacts]
        paths = [item.relative_path for item in self.artifacts]
        artifact_dump = [item.model_dump(mode="json") for item in self.artifacts]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("v2 artifact IDs must be unique and sorted")
        if len(paths) != len(set(paths)):
            raise ValueError("v2 artifact paths must be unique")
        if sha256_json(artifact_dump) != self.artifact_index_sha256:
            raise ValueError("v2 artifact index hash mismatch")
        section_dump = [item.model_dump(mode="json") for item in self.sections]
        section_ids = [item.section_id for item in self.sections]
        if section_ids != sorted(section_ids) or len(section_ids) != len(set(section_ids)):
            raise ValueError("v2 section IDs must be unique and sorted")
        if sha256_json(section_dump) != self.section_index_sha256:
            raise ValueError("v2 section index hash mismatch")
        unknown_artifact_ids = {
            artifact_id
            for section in self.sections
            for artifact_id in section.artifact_ids
            if artifact_id not in set(ids)
        }
        if unknown_artifact_ids:
            raise ValueError("v2 section references unknown artifacts")
        required_kinds = {item.artifact_kind for item in self.artifacts if item.required}
        missing_kinds = set(self.required_sections) - required_kinds
        if missing_kinds:
            raise ValueError("v2 required artifact kind missing")
        required_section_ids = {item.section_id for item in self.sections if item.required}
        if set(REQUIRED_BUNDLE_SECTION_IDS) - required_section_ids:
            raise ValueError("v2 required semantic section missing")
        if set(self.required_sections) != set(REQUIRED_ARTIFACT_KINDS):
            raise ValueError("v2 required artifact-kind contract drift")
        bridge_hashes = {
            item.sha256 for item in self.artifacts if item.artifact_kind == "authority_v3_bridge"
        }
        for item in self.artifacts:
            if item.authoritative and bridge_hashes.intersection(item.dependency_sha256s):
                raise ValueError("Authority-v3 bridge cannot feed v2 semantic authority")
        if self.compatibility.mode == "bundle_native":
            native = (
                self.compile_identity.compile_request_sha256,
                self.compile_identity.source_acquisition_sha256,
                self.compile_identity.retrieval_receipt_set_sha256,
                self.compile_identity.source_snapshot_sha256,
            )
            if not all(native) or self.compile_identity.migration_v1_bundle_sha256 is not None:
                raise ValueError("native v2 compile identity is incomplete or legacy-bound")
        elif self.compile_identity.migration_v1_bundle_sha256 is None:
            raise ValueError("migration v2 requires an explicit non-authoritative v1 reference")
        return self

    def verify_bundle_hash(self) -> None:
        body = self.model_dump(mode="json", exclude={"bundle_sha256"})
        if sha256_json(body) != self.bundle_sha256:
            raise ValueError("v2 bundle manifest hash mismatch")


class ConsumerPolicyV2(StrictModel):
    contract_id: Literal["room16.compiler.consumer_policy_lock"] = (
        "room16.compiler.consumer_policy_lock"
    )
    contract_version: Literal[2] = 2
    owner: Literal["research_compiler"] = "research_compiler"
    artifact_bundle_contract_major: Literal[2] = 2
    schema_version_min: Literal["2.0.0"] = "2.0.0"
    schema_version_max: Literal["2.x"] = "2.x"
    canonicalization_profile: Literal["room16.foundation.canonical_json@1"] = (
        "room16.foundation.canonical_json@1"
    )
    hash_algorithm: Literal["sha256"] = "sha256"
    trusted_emitter_id: Literal["room16.compiler_artifact_bundle_builder_v2"] = (
        "room16.compiler_artifact_bundle_builder_v2"
    )
    source_native_fact_generation_required_for_native: Literal[True] = True
    legacy_semantic_input_allowed: Literal[False] = False
    allowed_authority_v3_bridge_directions: tuple[
        Literal["bundle_to_authority_v3_only", "disabled"], ...
    ]
    product_may_edit_semantics: Literal[False] = False
    mutable_bundle_hash_allowlist_allowed: Literal[False] = False
    ba10_v1_freeze_sha256: Literal[BA10_V1_FREEZE_SHA256] = BA10_V1_FREEZE_SHA256
    ba11_freeze_sha256: Literal[BA11_FREEZE_SHA256] = BA11_FREEZE_SHA256
    compiler_identity: CompilerIdentityV2
    manifest_schema_profile_sha256: str = Field(pattern=SHA256_PATTERN)
    key_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    policy_sha256: str = Field(pattern=SHA256_PATTERN)

    def verify_self_hash(self) -> None:
        body = self.model_dump(mode="json", exclude={"policy_sha256"})
        if sha256_json(body) != self.policy_sha256:
            raise ValueError("v2 consumer policy self-hash mismatch")


class TrustedPublicKeyV2(StrictModel):
    key_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]*$")
    public_key_hex: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: Literal["active", "grace_verify_only", "revoked"]
    not_before_utc: str = Field(pattern=UTC_PATTERN)
    not_after_utc: str | None = Field(default=None, pattern=UTC_PATTERN)


class PublicKeyPolicyV2(StrictModel):
    contract_id: Literal["room16.compiler.public_key_policy"] = "room16.compiler.public_key_policy"
    contract_version: Literal[2] = 2
    owner: Literal["research_compiler"] = "research_compiler"
    signature_algorithm: Literal["ed25519"] = "ed25519"
    keys: tuple[TrustedPublicKeyV2, ...]
    rotation_sequence: tuple[str, ...]
    policy_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def closed_keys(self) -> "PublicKeyPolicyV2":
        ids = [item.key_id for item in self.keys]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ValueError("v2 key IDs must be unique and sorted")
        public_keys = [item.public_key_hex for item in self.keys]
        if len(public_keys) != len(set(public_keys)):
            raise ValueError("v2 public keys must not be duplicated across key IDs")
        return self

    def verify_self_hash(self) -> None:
        body = self.model_dump(mode="json", exclude={"policy_sha256"})
        if sha256_json(body) != self.policy_sha256:
            raise ValueError("v2 public key policy self-hash mismatch")


class TrustRootV2(StrictModel):
    contract_id: Literal["room16.compiler.v2_trust_root"] = "room16.compiler.v2_trust_root"
    contract_version: Literal[1] = 1
    owner: Literal["research_compiler"] = "research_compiler"
    root_id: Literal["room16.compiler.v2_trust_root@1"] = "room16.compiler.v2_trust_root@1"
    root_key_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]*$")
    root_public_key_hex: str = Field(pattern=r"^[0-9a-f]{64}$")
    consumer_policy_contract_id: Literal["room16.compiler.consumer_policy_lock"] = (
        "room16.compiler.consumer_policy_lock"
    )
    consumer_policy_contract_version: Literal[2] = 2
    public_key_policy_contract_id: Literal["room16.compiler.public_key_policy"] = (
        "room16.compiler.public_key_policy"
    )
    public_key_policy_contract_version: Literal[2] = 2
    artifact_bundle_contract_major: Literal[2] = 2
    canonicalization_profile: Literal["room16.foundation.canonical_json@1"] = (
        "room16.foundation.canonical_json@1"
    )
    hash_algorithm: Literal["sha256"] = "sha256"
    ba10_v1_freeze_sha256: Literal[BA10_V1_FREEZE_SHA256] = BA10_V1_FREEZE_SHA256
    ba11_freeze_sha256: Literal[BA11_FREEZE_SHA256] = BA11_FREEZE_SHA256
    issued_at_utc: str = Field(pattern=UTC_PATTERN)
    root_sha256: str = Field(pattern=SHA256_PATTERN)

    def verify_self_hash(self) -> None:
        body = self.model_dump(mode="json", exclude={"root_sha256"})
        expected = sha256_json({"domain": self.root_id, "value": body})
        if expected != self.root_sha256:
            raise ValueError("v2 trust root self-hash mismatch")


class ConsumerPolicyEnvelopeV2(StrictModel):
    contract_id: Literal["room16.compiler.consumer_policy_envelope"] = (
        "room16.compiler.consumer_policy_envelope"
    )
    contract_version: Literal[2] = 2
    generation: int = Field(gt=0)
    previous_envelope_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    root_id: Literal["room16.compiler.v2_trust_root@1"] = "room16.compiler.v2_trust_root@1"
    root_key_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]*$")
    issued_at_utc: str = Field(pattern=UTC_PATTERN)
    payload: ConsumerPolicyV2
    signature_algorithm: Literal["ed25519"] = "ed25519"
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")
    envelope_sha256: str = Field(pattern=SHA256_PATTERN)


class PublicKeyPolicyEnvelopeV2(StrictModel):
    contract_id: Literal["room16.compiler.public_key_policy_envelope"] = (
        "room16.compiler.public_key_policy_envelope"
    )
    contract_version: Literal[2] = 2
    generation: int = Field(gt=0)
    previous_envelope_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    root_id: Literal["room16.compiler.v2_trust_root@1"] = "room16.compiler.v2_trust_root@1"
    root_key_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]*$")
    issued_at_utc: str = Field(pattern=UTC_PATTERN)
    payload: PublicKeyPolicyV2
    signature_algorithm: Literal["ed25519"] = "ed25519"
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")
    envelope_sha256: str = Field(pattern=SHA256_PATTERN)


class BundleReceiptV2(StrictModel):
    contract_id: Literal["room16.compiler_artifact_bundle_receipt"] = (
        "room16.compiler_artifact_bundle_receipt"
    )
    contract_version: Literal[2] = 2
    receipt_id: str = Field(pattern=r"^rfc0008\.[a-z0-9_.-]+$")
    bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    compile_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    compiler_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    emitter_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    policy_sha256: str = Field(pattern=SHA256_PATTERN)
    ba10_v1_freeze_sha256: Literal[BA10_V1_FREEZE_SHA256] = BA10_V1_FREEZE_SHA256
    ba11_freeze_sha256: Literal[BA11_FREEZE_SHA256] = BA11_FREEZE_SHA256
    research_key_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]*$")
    issued_at_utc: str = Field(pattern=UTC_PATTERN)
    not_after_utc: str | None = Field(default=None, pattern=UTC_PATTERN)
    monotonic_counter: int = Field(gt=0)
    nonce: str = Field(pattern=r"^[a-z0-9][a-z0-9_.:-]{15,127}$")
    signature_algorithm: Literal["ed25519"] = "ed25519"
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)


def receipt_signature_body(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value for key, value in values.items() if key not in {"signature", "receipt_sha256"}
    }


def receipt_hash_body(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key != "receipt_sha256"}


def receipt_domain_hash(values: dict[str, Any]) -> str:
    return sha256_json(
        {
            "domain": "room16.compiler_artifact_bundle_receipt@2",
            "value": receipt_hash_body(values),
        }
    )
