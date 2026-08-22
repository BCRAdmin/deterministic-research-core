"""Additive RFC-0009 native Bundle@2 trust epoch.

Generation 1 remains implemented by the frozen RFC-0008 modules. This module
verifies the root-signed Gen1 -> Gen2 consumer-policy chain and the separately
hash-addressed native schema/emitter profile without changing frozen files.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey
from pydantic import Field

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json
from research_agent.compiler_foundation.contracts import StrictModel
from research_agent.productization_v2.contracts import (
    BA10_V1_FREEZE_SHA256,
    BA11_FREEZE_SHA256,
    BundleReceiptV2,
    CompilerArtifactBundleManifestV2,
    CompilerIdentityV2,
    PublicKeyPolicyEnvelopeV2,
    PublicKeyPolicyV2,
)
from research_agent.productization_v2.trust_receipt import verify_bundle_receipt_v2
from research_agent.productization_v2.trust_root import (
    CONSUMER_ENVELOPE_PATH,
    KEY_ENVELOPE_PATH,
    TRUST_ROOT_PATH,
    envelope_domain_hash,
    envelope_signature_preimage,
    verify_policy_envelope,
)

CONFIG_ROOT = Path(__file__).resolve().parent / "config"
GEN2_CONSUMER_ENVELOPE_PATH = CONFIG_ROOT / "consumer_policy_envelope_v2_generation_2_native.json"
GEN2_SCHEMA_PROFILE_PATH = CONFIG_ROOT / "manifest_schema_profile_v2_generation_2_native.json"
GEN2_EMITTER_PROFILE_PATH = CONFIG_ROOT / "native_emitter_profile_v2.json"
GEN1_SCHEMA_PROFILE_PATH = CONFIG_ROOT / "manifest_schema_profile_v2.json"

PINNED_ROOT_SHA256 = "56a94fcd6eede746dc2778f05774bc46f80cd50be02cf3302027aab729f8a356"
PINNED_ROOT_PUBLIC_KEY_HEX = "621d4a04fb14f322e2cfd57f650532c43f2d4c0d45c0f4d6834f5b9dd14af034"
PINNED_GEN1_ENVELOPE_SHA256 = "7f16189fdfd6b676fd3cb58acf9c6c51a9a1b66671dbb7c1f76156dffc5cd8c9"
PINNED_GEN1_SCHEMA_SHA256 = "2abbedc920bcac4d2470ee1a63e3e258ce7e82c6a9e034d0455330fd6f9b72c3"
NATIVE_EMITTER_ID = "room16.compiler_artifact_bundle_builder_v2_native"
NATIVE_EMITTER_VERSION = "2.1.0-ba12"
NATIVE_PRODUCER_PASS_ID = "ba12.l11.emit_native_bundle_v2"


class NativeTrustError(ValueError):
    """Stable fail-closed RFC-0009 diagnostic."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}:{detail}" if detail else code)
        self.code = code
        self.detail = detail


class NativeConsumerPolicyV2(StrictModel):
    contract_id: Literal["room16.compiler.consumer_policy_lock"]
    contract_version: Literal[2]
    owner: Literal["research_compiler"]
    artifact_bundle_contract_major: Literal[2]
    schema_version_min: Literal["2.0.0"]
    schema_version_max: Literal["2.x"]
    canonicalization_profile: Literal["room16.foundation.canonical_json@1"]
    hash_algorithm: Literal["sha256"]
    trusted_emitter_id: Literal["room16.compiler_artifact_bundle_builder_v2_native"]
    source_native_fact_generation_required_for_native: Literal[True]
    legacy_semantic_input_allowed: Literal[False]
    allowed_authority_v3_bridge_directions: tuple[
        Literal["bundle_to_authority_v3_only", "disabled"], ...
    ]
    product_may_edit_semantics: Literal[False]
    mutable_bundle_hash_allowlist_allowed: Literal[False]
    ba10_v1_freeze_sha256: Literal[BA10_V1_FREEZE_SHA256]
    ba11_freeze_sha256: Literal[BA11_FREEZE_SHA256]
    compiler_identity: CompilerIdentityV2
    manifest_schema_profile_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    key_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    def verify_self_hash(self) -> None:
        if sha256_json(self.model_dump(mode="json", exclude={"policy_sha256"})) != self.policy_sha256:
            raise NativeTrustError("RFC9_POLICY_SELF_HASH_MISMATCH")


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise NativeTrustError("RFC9_CONFIG_INVALID", str(path)) from exc
    if not isinstance(value, dict):
        raise NativeTrustError("RFC9_CONFIG_INVALID", str(path))
    return value


def _verify_profile(value: dict[str, Any], *, code: str) -> None:
    body = {key: item for key, item in value.items() if key != "profile_sha256"}
    if sha256_json(body) != value.get("profile_sha256"):
        raise NativeTrustError(code)


def load_native_trust() -> dict[str, Any]:
    root = _read(TRUST_ROOT_PATH)
    if (
        root.get("root_sha256") != PINNED_ROOT_SHA256
        or root.get("root_public_key_hex") != PINNED_ROOT_PUBLIC_KEY_HEX
    ):
        raise NativeTrustError("RFC9_ROOT_SUBSTITUTION")

    gen1_raw = _read(CONSUMER_ENVELOPE_PATH)
    if gen1_raw.get("envelope_sha256") != PINNED_GEN1_ENVELOPE_SHA256:
        raise NativeTrustError("RFC9_GEN1_ENVELOPE_DRIFT")
    from research_agent.productization_v2.contracts import ConsumerPolicyEnvelopeV2, TrustRootV2

    root_model = TrustRootV2.model_validate(root)
    gen1_model = ConsumerPolicyEnvelopeV2.model_validate(gen1_raw)
    verify_policy_envelope(gen1_model, root=root_model)

    gen2 = _read(GEN2_CONSUMER_ENVELOPE_PATH)
    required_envelope_fields = {
        "contract_id", "contract_version", "generation", "previous_envelope_sha256",
        "root_id", "root_key_id", "issued_at_utc", "payload", "signature_algorithm",
        "signature", "envelope_sha256",
    }
    if set(gen2) != required_envelope_fields:
        raise NativeTrustError("RFC9_GEN2_ENVELOPE_SCHEMA_INVALID")
    if gen2.get("generation") != 2 or gen2.get("previous_envelope_sha256") != PINNED_GEN1_ENVELOPE_SHA256:
        raise NativeTrustError("RFC9_GEN2_PREDECESSOR_INVALID")
    if gen2.get("root_id") != root["root_id"] or gen2.get("root_key_id") != root["root_key_id"]:
        raise NativeTrustError("RFC9_GEN2_ROOT_MISMATCH")
    if gen2.get("contract_id") != gen1_raw["contract_id"] or gen2.get("contract_version") != 2:
        raise NativeTrustError("RFC9_GEN2_CONTRACT_MISMATCH")
    if gen2.get("signature_algorithm") != "ed25519" or envelope_domain_hash(gen2) != gen2.get("envelope_sha256"):
        raise NativeTrustError("RFC9_GEN2_ENVELOPE_HASH_MISMATCH")
    try:
        VerifyKey(bytes.fromhex(PINNED_ROOT_PUBLIC_KEY_HEX)).verify(
            canonical_bytes(envelope_signature_preimage(gen2)),
            bytes.fromhex(str(gen2.get("signature", ""))),
        )
    except (BadSignatureError, ValueError) as exc:
        raise NativeTrustError("RFC9_GEN2_ROOT_SIGNATURE_INVALID") from exc

    policy = NativeConsumerPolicyV2.model_validate(gen2["payload"])
    policy.verify_self_hash()
    if policy.compiler_identity.semantic_artifact_origin != "source_native":
        raise NativeTrustError("RFC9_NATIVE_ORIGIN_INVALID")
    gen1_policy = gen1_raw["payload"]
    allowed_delta = {
        "trusted_emitter_id",
        "manifest_schema_profile_sha256",
        "policy_sha256",
    }
    for key in set(gen1_policy) | set(gen2["payload"]):
        if key == "compiler_identity":
            for identity_key in set(gen1_policy[key]) | set(gen2["payload"][key]):
                if identity_key == "semantic_artifact_origin":
                    continue
                if gen1_policy[key].get(identity_key) != gen2["payload"][key].get(identity_key):
                    raise NativeTrustError("RFC9_FROZEN_COMPILER_LOCK_DRIFT", identity_key)
        elif key not in allowed_delta and gen1_policy.get(key) != gen2["payload"].get(key):
            raise NativeTrustError("RFC9_FORBIDDEN_POLICY_DELTA", key)

    gen1_profile = _read(GEN1_SCHEMA_PROFILE_PATH)
    native_profile = _read(GEN2_SCHEMA_PROFILE_PATH)
    emitter_profile = _read(GEN2_EMITTER_PROFILE_PATH)
    if gen1_profile.get("profile_sha256") != PINNED_GEN1_SCHEMA_SHA256:
        raise NativeTrustError("RFC9_GEN1_SCHEMA_DRIFT")
    _verify_profile(native_profile, code="RFC9_NATIVE_SCHEMA_HASH_MISMATCH")
    _verify_profile(emitter_profile, code="RFC9_NATIVE_EMITTER_PROFILE_HASH_MISMATCH")
    if native_profile["profile_sha256"] != policy.manifest_schema_profile_sha256:
        raise NativeTrustError("RFC9_NATIVE_SCHEMA_POLICY_BINDING_MISMATCH")
    emitter_lock = native_profile.get("native_emitter_lock", {})
    expected_emitter = {
        "emitter_id": NATIVE_EMITTER_ID,
        "emitter_version": NATIVE_EMITTER_VERSION,
        "producer_pass_id": NATIVE_PRODUCER_PASS_ID,
        "implementation_sha256": emitter_profile.get("emitter_identity", {}).get(
            "implementation_sha256"
        ),
        "schema_sha256": emitter_profile.get("emitter_identity", {}).get(
            "schema_sha256"
        ),
    }
    if emitter_lock != expected_emitter or emitter_profile.get("emitter_identity") != expected_emitter:
        raise NativeTrustError("RFC9_NATIVE_EMITTER_BINDING_MISMATCH")
    if policy.trusted_emitter_id != NATIVE_EMITTER_ID:
        raise NativeTrustError("RFC9_NATIVE_EMITTER_POLICY_MISMATCH")

    key_envelope = PublicKeyPolicyEnvelopeV2.model_validate(_read(KEY_ENVELOPE_PATH))
    verify_policy_envelope(key_envelope, root=root_model)
    if key_envelope.generation != 1 or key_envelope.payload.policy_sha256 != policy.key_policy_sha256:
        raise NativeTrustError("RFC9_KEY_POLICY_DRIFT")
    return {
        "root": root,
        "gen1": gen1_raw,
        "gen2": gen2,
        "policy": policy,
        "native_profile": native_profile,
        "emitter_profile": emitter_profile,
        "key_policy": key_envelope.payload,
    }


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_native_bundle_v2(
    bundle_root: Path,
    *,
    receipt: dict[str, Any] | BundleReceiptV2,
    now_utc: str = "2026-08-22T12:00:00Z",
) -> dict[str, Any]:
    trust = load_native_trust()
    root = bundle_root.resolve()
    try:
        manifest = _read(root / "BUNDLE_MANIFEST.json")
    except NativeTrustError as exc:
        raise NativeTrustError("RFC9_NATIVE_MANIFEST_INVALID", exc.detail) from exc
    profile = trust["native_profile"]
    model_fields = profile["models"]
    if set(manifest) != set(model_fields["bundle_manifest"]):
        raise NativeTrustError("RFC9_NATIVE_MANIFEST_SCHEMA_INVALID")
    for field, profile_name in (
        ("compiler_identity", "compiler_identity"),
        ("emitter_identity", "emitter_identity"),
        ("compile_identity", "compile_identity"),
        ("compatibility", "compatibility"),
        ("eligibility", "eligibility"),
    ):
        if set(manifest.get(field, {})) != set(model_fields[profile_name]):
            raise NativeTrustError("RFC9_NATIVE_MANIFEST_SCHEMA_INVALID", field)

    structural = json.loads(json.dumps(manifest))
    structural["emitter_identity"].update(
        {
            "emitter_id": "room16.compiler_artifact_bundle_builder_v2",
            "emitter_version": "2.0.0-rfc0008",
            "producer_pass_id": "rfc0008.l11.emit_migration_bundle_v2",
        }
    )
    try:
        CompilerArtifactBundleManifestV2.model_validate(structural)
    except Exception as exc:
        raise NativeTrustError("RFC9_NATIVE_MANIFEST_CONTRACT_INVALID", str(exc)) from exc
    body = {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    if sha256_json(body) != manifest.get("bundle_sha256"):
        raise NativeTrustError("RFC9_NATIVE_MANIFEST_HASH_MISMATCH")
    if manifest["compiler_identity"] != trust["policy"].compiler_identity.model_dump(mode="json"):
        raise NativeTrustError("RFC9_NATIVE_COMPILER_IDENTITY_MISMATCH")
    emitter = manifest["emitter_identity"]
    expected = {
        **trust["emitter_profile"]["emitter_identity"],
        "consumer_policy_sha256": trust["policy"].policy_sha256,
    }
    if emitter != expected:
        raise NativeTrustError("RFC9_NATIVE_EMITTER_IDENTITY_MISMATCH")
    compatibility = manifest["compatibility"]
    expected_compatibility = {
        "mode": "bundle_native",
        "compiler_mode": "source_native",
        "source_native_fact_generation": True,
        "native_source_production": True,
        "legacy_semantic_input_allowed": False,
        "authority_v3_semantic_input_allowed": False,
        "authority_v3_bridge_direction": "bundle_to_authority_v3_only",
    }
    if compatibility != expected_compatibility:
        raise NativeTrustError("RFC9_NATIVE_COMPATIBILITY_INVALID")
    eligibility = manifest["eligibility"]
    if eligibility["release_ready"] or eligibility["publication_allowed"] or eligibility["deploy_allowed"]:
        raise NativeTrustError("RFC9_NATIVE_GATE_INVALID")
    for artifact in manifest["artifacts"]:
        relative = Path(artifact["relative_path"])
        target = (root / relative).resolve()
        if root not in target.parents or not target.is_file():
            raise NativeTrustError("RFC9_NATIVE_ARTIFACT_PATH_INVALID", artifact["artifact_id"])
        if target.stat().st_size != artifact["byte_length"] or _sha(target) != artifact["sha256"]:
            raise NativeTrustError("RFC9_NATIVE_ARTIFACT_HASH_MISMATCH", artifact["artifact_id"])

    receipt_model = receipt if isinstance(receipt, BundleReceiptV2) else BundleReceiptV2.model_validate(receipt)
    verify_bundle_receipt_v2(
        receipt_model,
        manifest=SimpleNamespace(
            bundle_sha256=manifest["bundle_sha256"],
            compile_identity=manifest["compile_identity"],
            compiler_identity=manifest["compiler_identity"],
            emitter_identity=manifest["emitter_identity"],
            ba10_v1_freeze_sha256=manifest["ba10_v1_freeze_sha256"],
            ba11_freeze_sha256=manifest["ba11_freeze_sha256"],
        ),
        consumer_policy=trust["policy"],
        key_policy=trust["key_policy"],
        now_utc=now_utc,
    )
    return {
        "status": "PASS",
        "bundle_sha256": manifest["bundle_sha256"],
        "consumer_policy_generation": 2,
        "consumer_policy_envelope_sha256": trust["gen2"]["envelope_sha256"],
        "trust_root_sha256": trust["root"]["root_sha256"],
        "receipt_sha256": receipt_model.receipt_sha256,
    }
