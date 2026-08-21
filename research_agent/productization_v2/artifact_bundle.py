"""Additive v2 migration bundle emitter and verifier.

This RFC-0008 emitter intentionally emits only truthful dual-read migration
bundles from accepted v1 canaries. Native v2 emission remains a BA12 task.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json
from research_agent.productization.artifact_bundle import verify_compiler_artifact_bundle
from research_agent.productization.contracts import ArtifactRecord, BundleSectionRecord

from .contracts import (
    CompilerArtifactBundleManifestV2,
    CompatibilityStateV2,
    CompileIdentityV2,
    ConsumerPolicyEnvelopeV2,
    ConsumerPolicyV2,
    EligibilityStateV2,
    EmitterIdentityV2,
    PublicKeyPolicyEnvelopeV2,
    PublicKeyPolicyV2,
    TrustRootV2,
)
from .schema_profile import manifest_schema_profile_v2
from .trust_root import (
    CONSUMER_ENVELOPE_PATH,
    KEY_ENVELOPE_PATH,
    TRUST_ROOT_PATH,
    verify_policy_envelope,
)

BUNDLE_MANIFEST = "BUNDLE_MANIFEST.json"
CONFIG_ROOT = Path(__file__).resolve().parent / "config"


class ArtifactBundleV2Error(ValueError):
    """Stable fail-closed v2 Artifact ABI diagnostic."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code = code
        self.detail = detail


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_trust_root_v2(path: Path = TRUST_ROOT_PATH) -> TrustRootV2:
    try:
        root = TrustRootV2.model_validate(json.loads(path.read_text(encoding="utf-8")))
        root.verify_self_hash()
        return root
    except Exception as exc:
        raise ArtifactBundleV2Error("RFC8_R2_TRUST_ROOT_INVALID", str(exc)) from exc


def load_consumer_policy_v2(
    path: Path = CONSUMER_ENVELOPE_PATH,
    *,
    root: TrustRootV2 | None = None,
) -> ConsumerPolicyV2:
    try:
        trust_root = root or load_trust_root_v2()
        envelope = ConsumerPolicyEnvelopeV2.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        verify_policy_envelope(envelope, root=trust_root)
        return envelope.payload
    except Exception as exc:
        raise ArtifactBundleV2Error("RFC8_R2_CONSUMER_POLICY_INVALID", str(exc)) from exc


def load_public_key_policy_v2(
    path: Path = KEY_ENVELOPE_PATH,
    *,
    root: TrustRootV2 | None = None,
) -> PublicKeyPolicyV2:
    try:
        trust_root = root or load_trust_root_v2()
        envelope = PublicKeyPolicyEnvelopeV2.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        )
        verify_policy_envelope(envelope, root=trust_root)
        return envelope.payload
    except Exception as exc:
        raise ArtifactBundleV2Error("RFC8_R2_KEY_POLICY_INVALID", str(exc)) from exc


def build_migration_bundle_v2(
    *,
    v1_bundle_root: Path,
    output_root: Path,
    consumer_policy: ConsumerPolicyV2 | None = None,
) -> CompilerArtifactBundleManifestV2:
    """Re-issue an accepted v1 canary as truthful v2 migration evidence."""

    v1_bundle_root = v1_bundle_root.resolve()
    output_root = output_root.resolve()
    v1 = verify_compiler_artifact_bundle(v1_bundle_root)
    policy = consumer_policy or load_consumer_policy_v2()
    policy.verify_self_hash()
    implementation_sha256 = sha256_json(
        {
            "artifact_bundle.py": _sha(Path(__file__)),
            "trust_receipt.py": _sha(Path(__file__).with_name("trust_receipt.py")),
        }
    )
    emitter = EmitterIdentityV2(
        implementation_sha256=implementation_sha256,
        schema_sha256=_sha(Path(__file__).with_name("contracts.py")),
        consumer_policy_sha256=policy.policy_sha256,
    )
    v1_manifest_bytes = (v1_bundle_root / BUNDLE_MANIFEST).read_bytes()
    migration_reference = ArtifactRecord(
        artifact_id="migration.v1_manifest",
        artifact_kind="v1_migration_reference",
        contract_id="room16.compiler_artifact_bundle",
        contract_version=1,
        layer="L11",
        producer_pass_id="rfc0008.l11.emit_migration_bundle_v2",
        relative_path="migration/v1_manifest.json",
        media_type="application/json",
        sha256=hashlib.sha256(v1_manifest_bytes).hexdigest(),
        byte_length=len(v1_manifest_bytes),
        required=False,
        compatibility_rule="byte_identical_compatibility_view",
        authoritative=False,
        compatibility_only=True,
        provenance_refs=(v1.bundle_sha256,),
    )
    artifacts = tuple(
        sorted((*v1.artifacts, migration_reference), key=lambda item: item.artifact_id)
    )
    compiler_identity = {
        **v1.compiler_identity.model_dump(mode="json"),
        "bundle_abi_version": "2.0.0",
        "semantic_artifact_origin": "frozen_v1_migration",
    }
    compile_identity = CompileIdentityV2(
        ticker=v1.compile_identity.ticker,
        as_of_date=v1.compile_identity.as_of_date,
        final_compile_state_sha256=v1.compile_identity.final_compile_state_sha256,
        verification_report_sha256=v1.compile_identity.verification_report_sha256,
        replay_sha256=v1.compile_identity.replay_sha256,
        migration_v1_bundle_sha256=v1.bundle_sha256,
    )
    compatibility = CompatibilityStateV2(
        mode="bundle_dual_read",
        compiler_mode="migration_dual_read",
        source_native_fact_generation=False,
        native_source_production=False,
        authority_v3_bridge_direction="bundle_to_authority_v3_only",
    )
    section_hashes = {
        "artifact_hashes": sha256_json([item.model_dump(mode="json") for item in artifacts]),
        "compatibility_state": sha256_json(compatibility),
        "compile_identity": sha256_json(compile_identity),
        "compiler_version": sha256_json(compiler_identity),
        "ir_references": sha256_json(
            [
                {"artifact_id": item.artifact_id, "sha256": item.sha256}
                for item in artifacts
                if item.authoritative
            ]
        ),
    }
    sections = tuple(
        BundleSectionRecord.model_validate(
            {
                **item.model_dump(mode="json"),
                "schema_version": "2.0.0"
                if item.section_id in section_hashes
                else item.schema_version,
                "sha256": section_hashes.get(item.section_id, item.sha256),
            }
        )
        for item in v1.sections
    )
    body: dict[str, Any] = {
        "contract_id": "room16.compiler_artifact_bundle",
        "contract_version": 2,
        "schema_version": "2.0.0",
        "canonicalization_profile": "room16.foundation.canonical_json@1",
        "hash_algorithm": "sha256",
        "compiler_identity": compiler_identity,
        "emitter_identity": emitter.model_dump(mode="json"),
        "compile_identity": compile_identity.model_dump(mode="json"),
        "compatibility": compatibility.model_dump(mode="json"),
        "eligibility": EligibilityStateV2(
            compile_allowed=v1.eligibility.compile_allowed,
            renderer_eligible=v1.eligibility.renderer_eligible,
        ).model_dump(mode="json"),
        "ba10_v1_freeze_sha256": policy.ba10_v1_freeze_sha256,
        "ba11_freeze_sha256": policy.ba11_freeze_sha256,
        "artifact_index_sha256": sha256_json([item.model_dump(mode="json") for item in artifacts]),
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "section_index_sha256": sha256_json([item.model_dump(mode="json") for item in sections]),
        "sections": [item.model_dump(mode="json") for item in sections],
        "required_sections": list(v1.required_sections),
        "optional_sections": sorted({*v1.optional_sections, "v1_migration_reference"}),
        "extensions": {
            "migration": {
                "canonical_authority": False,
                "native_source_production": False,
                "v1_bundle_sha256": v1.bundle_sha256,
                "v1_manifest_sha256": migration_reference.sha256,
            }
        },
    }
    body["bundle_sha256"] = sha256_json(body)
    manifest = CompilerArtifactBundleManifestV2.model_validate(body)
    manifest.verify_bundle_hash()
    with tempfile.TemporaryDirectory(prefix="room16-rfc0008-v2-") as temporary:
        staging = Path(temporary) / "bundle"
        shutil.copytree(v1_bundle_root, staging)
        (staging / "migration").mkdir(exist_ok=True)
        (staging / "migration/v1_manifest.json").write_bytes(v1_manifest_bytes)
        (staging / BUNDLE_MANIFEST).write_bytes(canonical_bytes(manifest.model_dump(mode="json")))
        if output_root.exists():
            shutil.rmtree(output_root)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, output_root)
    return verify_compiler_artifact_bundle_v2(output_root, consumer_policy=policy)


def verify_compiler_artifact_bundle_v2(
    root: Path,
    *,
    consumer_policy: ConsumerPolicyV2 | None = None,
) -> CompilerArtifactBundleManifestV2:
    root = root.resolve()
    manifest_path = root / BUNDLE_MANIFEST
    if not manifest_path.is_file():
        raise ArtifactBundleV2Error("RFC8_BUNDLE_MISSING", str(root))
    try:
        manifest = CompilerArtifactBundleManifestV2.model_validate_json(manifest_path.read_bytes())
        manifest.verify_bundle_hash()
    except Exception as exc:
        raise ArtifactBundleV2Error("RFC8_MANIFEST_INVALID", str(exc)) from exc
    policy = consumer_policy or load_consumer_policy_v2()
    policy.verify_self_hash()
    if (
        manifest.emitter_identity.emitter_id != policy.trusted_emitter_id
        or manifest.emitter_identity.consumer_policy_sha256 != policy.policy_sha256
        or manifest.ba10_v1_freeze_sha256 != policy.ba10_v1_freeze_sha256
        or manifest.ba11_freeze_sha256 != policy.ba11_freeze_sha256
        or manifest.compatibility.authority_v3_bridge_direction
        not in policy.allowed_authority_v3_bridge_directions
        or manifest.compiler_identity != policy.compiler_identity
        or policy.manifest_schema_profile_sha256 != manifest_schema_profile_v2()["profile_sha256"]
    ):
        raise ArtifactBundleV2Error("RFC8_TRUST_POLICY_MISMATCH")
    if (
        manifest.compatibility.mode == "bundle_native"
        and policy.source_native_fact_generation_required_for_native
        and not manifest.compatibility.source_native_fact_generation
    ):
        raise ArtifactBundleV2Error("RFC8_NATIVE_STATE_FALSE")
    artifact_hashes = {item.sha256 for item in manifest.artifacts}
    for item in manifest.artifacts:
        target = (root / item.relative_path).resolve()
        if root not in target.parents:
            raise ArtifactBundleV2Error("RFC8_ARTIFACT_PATH_UNSAFE", item.relative_path)
        if not target.is_file():
            raise ArtifactBundleV2Error("RFC8_ARTIFACT_MISSING", item.artifact_id)
        if target.stat().st_size != item.byte_length or _sha(target) != item.sha256:
            raise ArtifactBundleV2Error("RFC8_ARTIFACT_HASH_MISMATCH", item.artifact_id)
        if any(value not in artifact_hashes for value in item.dependency_sha256s):
            raise ArtifactBundleV2Error("RFC8_ARTIFACT_DEPENDENCY_UNRESOLVED", item.artifact_id)
    return manifest
