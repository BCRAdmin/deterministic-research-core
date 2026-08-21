"""Hash-pinned schema profile shared with the Product v2 verifier."""

from __future__ import annotations

from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization.contracts import (
    REQUIRED_ARTIFACT_KINDS,
    REQUIRED_BUNDLE_SECTION_IDS,
    ArtifactRecord,
    BundleSectionRecord,
)

from .contracts import (
    CompileIdentityV2,
    CompilerArtifactBundleManifestV2,
    CompilerIdentityV2,
    CompatibilityStateV2,
    EligibilityStateV2,
    EmitterIdentityV2,
)


def _fields(model: type) -> list[str]:
    return sorted(model.model_fields)


def manifest_schema_profile_v2() -> dict[str, Any]:
    profile = {
        "contract_id": "room16.compiler_artifact_bundle.schema_profile",
        "contract_version": 2,
        "unknown_field_policy": "fail_closed",
        "missing_field_policy": "fail_closed",
        "models": {
            "artifact": _fields(ArtifactRecord),
            "bundle_manifest": _fields(CompilerArtifactBundleManifestV2),
            "bundle_section": _fields(BundleSectionRecord),
            "compatibility": _fields(CompatibilityStateV2),
            "compile_identity": _fields(CompileIdentityV2),
            "compiler_identity": _fields(CompilerIdentityV2),
            "eligibility": _fields(EligibilityStateV2),
            "emitter_identity": _fields(EmitterIdentityV2),
        },
        "required_artifact_kinds": list(REQUIRED_ARTIFACT_KINDS),
        "required_bundle_section_ids": list(REQUIRED_BUNDLE_SECTION_IDS),
        "compiler_identity_lock": CompilerIdentityV2(
            semantic_artifact_origin="frozen_v1_migration"
        ).model_dump(mode="json"),
        "bundle_contract": {
            "canonicalization_profile": "room16.foundation.canonical_json@1",
            "contract_id": "room16.compiler_artifact_bundle",
            "contract_version": 2,
            "hash_algorithm": "sha256",
            "schema_version": "2.0.0",
        },
    }
    return {**profile, "profile_sha256": sha256_json(profile)}
