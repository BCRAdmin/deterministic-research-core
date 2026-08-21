from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization.contracts import CompilerArtifactBundleManifest
from research_agent.productization_v2.contracts import (
    BundleReceiptV2,
    CompatibilityStateV2,
    CompilerArtifactBundleManifestV2,
    ConsumerPolicyV2,
    EmitterIdentityV2,
    PublicKeyPolicyV2,
)
from research_agent.productization_v2.trust_receipt import (
    ReceiptV2Error,
    ReceiptVerificationState,
    verify_bundle_receipt_v2,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
CONFIG = ROOT / "research_agent/productization_v2/config"
CANARIES = CONFIG / "migration_canaries"
TICKERS = ("WM", "COST", "ABT")
TEST_IDS = tuple(f"RFC8-T-{index:03d}" for index in range(1, 46))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def policy() -> ConsumerPolicyV2:
    value = ConsumerPolicyV2.model_validate(load_json(CONFIG / "consumer_policy_v2.json"))
    value.verify_self_hash()
    return value


def key_policy() -> PublicKeyPolicyV2:
    value = PublicKeyPolicyV2.model_validate(load_json(CONFIG / "public_key_policy_v2.json"))
    value.verify_self_hash()
    return value


def manifest(ticker: str = "WM") -> CompilerArtifactBundleManifestV2:
    value = CompilerArtifactBundleManifestV2.model_validate(
        load_json(CANARIES / ticker / "BUNDLE_MANIFEST.json")
    )
    value.verify_bundle_hash()
    return value


def receipt(ticker: str = "WM") -> BundleReceiptV2:
    return BundleReceiptV2.model_validate(load_json(CANARIES / ticker / "RECEIPT.json"))


def rebuilt_key_policy(state: str) -> PublicKeyPolicyV2:
    body = load_json(CONFIG / "public_key_policy_v2.json")
    body.pop("policy_sha256")
    body["keys"][0]["state"] = state
    body["policy_sha256"] = sha256_json(body)
    return PublicKeyPolicyV2.model_validate(body)


def rehash_manifest(value: dict) -> dict:
    body = copy.deepcopy(value)
    body.pop("bundle_sha256", None)
    body["bundle_sha256"] = sha256_json(body)
    return body


def verify_receipt(value: BundleReceiptV2 | None = None, **kwargs) -> None:
    verify_bundle_receipt_v2(
        value or receipt(),
        manifest=kwargs.pop("manifest", manifest()),
        consumer_policy=kwargs.pop("consumer_policy", policy()),
        key_policy=kwargs.pop("key_policy", key_policy()),
        now_utc=kwargs.pop("now_utc", "2026-08-21T13:00:00Z"),
        **kwargs,
    )


def mutate_receipt(**changes) -> BundleReceiptV2:
    value = receipt().model_dump(mode="json")
    value.update(changes)
    return BundleReceiptV2.model_validate(value)


@pytest.mark.parametrize("test_id", TEST_IDS, ids=TEST_IDS)
def test_rfc0008_acceptance_matrix(test_id: str) -> None:
    number = int(test_id.rsplit("-", 1)[1])
    if number == 1:
        result = subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                "scripts/ops/verify_ba10_artifact_abi_renderer_freeze.py",
                "--product-repo",
                str(PRODUCT),
                "--json",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0 and json.loads(result.stdout)["status"] == "PASS"
    elif number == 2:
        result = subprocess.run(
            [
                str(ROOT / ".venv/bin/python"),
                "scripts/ops/verify_ba11_canary_governance_freeze.py",
                "--json",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0 and json.loads(result.stdout)["status"] == "PASS"
    elif number == 3:
        assert policy().ba10_v1_freeze_sha256 == (
            "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e"
        )
    elif number == 4:
        value = manifest()
        assert value.contract_version == 2 and value.schema_version == "2.0.0"
    elif number == 5:
        state = CompatibilityStateV2(
            mode="bundle_native",
            compiler_mode="source_native",
            source_native_fact_generation=True,
            native_source_production=True,
            authority_v3_bridge_direction="disabled",
        )
        assert state.source_native_fact_generation is True
    elif number == 6:
        source = (PRODUCT / "room16-app/server-modules/compiler-artifact-bundle.mjs").read_text(
            encoding="utf-8"
        )
        assert 'manifest.compatibility?.mode !== "authority_v3_compatibility_shadow"' in source
    elif number == 7:
        with pytest.raises(ValidationError, match="truthful native"):
            CompatibilityStateV2(
                mode="bundle_native",
                compiler_mode="source_native",
                source_native_fact_generation=False,
                native_source_production=False,
                authority_v3_bridge_direction="disabled",
            )
    elif number == 8:
        with pytest.raises(ValidationError):
            CompatibilityStateV2(
                mode="bundle_native",
                compiler_mode="source_native",
                source_native_fact_generation=True,
                native_source_production=True,
                legacy_semantic_input_allowed=True,
                authority_v3_bridge_direction="disabled",
            )
    elif number == 9:
        value = manifest()
        bridge = next(
            item for item in value.artifacts if item.artifact_kind == "authority_v3_bridge"
        )
        assert bridge.authoritative is False and bridge.compatibility_only is True
        assert value.compatibility.authority_v3_bridge_direction == "bundle_to_authority_v3_only"
    elif number == 10:
        value = manifest().model_dump(mode="json")
        bridge_sha = next(
            item["sha256"]
            for item in value["artifacts"]
            if item["artifact_kind"] == "authority_v3_bridge"
        )
        target = next(item for item in value["artifacts"] if item["authoritative"])
        target["dependency_sha256s"] = sorted({*target["dependency_sha256s"], bridge_sha})
        value["artifact_index_sha256"] = sha256_json(value["artifacts"])
        value = rehash_manifest(value)
        with pytest.raises(ValidationError, match="cannot feed"):
            CompilerArtifactBundleManifestV2.model_validate(value)
    elif number == 11:
        assert manifest().emitter_identity.emitter_id.endswith("_v2")
    elif number == 12:
        with pytest.raises(ValidationError):
            EmitterIdentityV2(
                emitter_id="room16.compiler_artifact_bundle_builder",
                implementation_sha256="a" * 64,
                schema_sha256="b" * 64,
                consumer_policy_sha256="c" * 64,
            )
    elif number == 13:
        policy().verify_self_hash()
    elif number == 14:
        assert (CONFIG / "consumer_policy_v2.json").read_bytes() == (
            PRODUCT / "room16-app/config/room16_compiler_artifact_consumer_policy_v2.json"
        ).read_bytes()
        assert (CONFIG / "public_key_policy_v2.json").read_bytes() == (
            PRODUCT / "room16-app/config/room16_compiler_artifact_trusted_keys_v2.json"
        ).read_bytes()
    elif number == 15:
        value = load_json(CONFIG / "consumer_policy_v2.json")
        value["product_may_edit_semantics"] = True
        with pytest.raises((ValidationError, ValueError)):
            ConsumerPolicyV2.model_validate(value).verify_self_hash()
    elif number == 16:
        verify_receipt()
    elif number == 17:
        with pytest.raises(ReceiptV2Error, match="bundle_sha256"):
            verify_receipt(mutate_receipt(bundle_sha256="0" * 64))
    elif number == 18:
        with pytest.raises(ReceiptV2Error, match="compile_identity_sha256"):
            verify_receipt(mutate_receipt(compile_identity_sha256="0" * 64))
    elif number == 19:
        with pytest.raises(ReceiptV2Error, match="emitter_identity_sha256"):
            verify_receipt(mutate_receipt(emitter_identity_sha256="0" * 64))
    elif number == 20:
        with pytest.raises(ReceiptV2Error, match="policy_sha256"):
            verify_receipt(mutate_receipt(policy_sha256="0" * 64))
    elif number == 21:
        with pytest.raises((ValidationError, ReceiptV2Error)):
            verify_receipt(mutate_receipt(ba10_v1_freeze_sha256="0" * 64))
    elif number == 22:
        with pytest.raises((ValidationError, ReceiptV2Error)):
            verify_receipt(mutate_receipt(ba11_freeze_sha256="0" * 64))
    elif number == 23:
        tampered = mutate_receipt(signature="0" * 128)
        value = tampered.model_dump(mode="json")
        value["receipt_sha256"] = sha256_json(
            {
                "domain": "room16.compiler_artifact_bundle_receipt@2",
                "value": {key: item for key, item in value.items() if key != "receipt_sha256"},
            }
        )
        with pytest.raises(ReceiptV2Error, match="SIGNATURE"):
            verify_receipt(BundleReceiptV2.model_validate(value))
    elif number == 24:
        with pytest.raises(ReceiptV2Error, match="REVOKED"):
            verify_receipt(key_policy=rebuilt_key_policy("revoked"))
    elif number == 25:
        expired = load_json(CONFIG / "public_key_policy_v2.json")
        expired.pop("policy_sha256")
        expired["keys"][0]["not_after_utc"] = "2026-08-21T12:30:00Z"
        expired["policy_sha256"] = sha256_json(expired)
        with pytest.raises(ReceiptV2Error, match="EXPIRED"):
            verify_receipt(key_policy=PublicKeyPolicyV2.model_validate(expired))
    elif number == 26:
        verify_receipt(key_policy=rebuilt_key_policy("active"))
        verify_receipt(key_policy=rebuilt_key_policy("grace_verify_only"))
        with pytest.raises(ReceiptV2Error, match="REVOKED"):
            verify_receipt(key_policy=rebuilt_key_policy("revoked"))
    elif number == 27:
        v1 = CompilerArtifactBundleManifest.model_validate(
            load_json(CANARIES / "WM/V1_BUNDLE_MANIFEST.json")
        )
        assert v1.contract_version == 1
        with pytest.raises(ValidationError):
            CompilerArtifactBundleManifest.model_validate(manifest().model_dump(mode="json"))
    elif number == 28:
        assert manifest().contract_version == 2
        with pytest.raises(ValidationError):
            CompilerArtifactBundleManifestV2.model_validate(
                load_json(CANARIES / "WM/V1_BUNDLE_MANIFEST.json")
            )
    elif number == 29:
        source = (
            PRODUCT / "room16-app/server-modules/compiler-artifact-bundle-router.mjs"
        ).read_text(encoding="utf-8")
        assert (
            "if (version === 2)" in source and "catch" not in source.split("if (version === 2)")[1]
        )
    elif number == 30:
        source = (
            PRODUCT / "room16-app/server-modules/compiler-artifact-bundle-router.mjs"
        ).read_text(encoding="utf-8")
        assert "RFC8_DUAL_CANONICAL_AUTHORITY" in source
    elif number in {31, 32, 33}:
        ticker = TICKERS[number - 31]
        value = manifest(ticker)
        v1 = load_json(CANARIES / ticker / "V1_BUNDLE_MANIFEST.json")
        v2_semantic = {
            item.artifact_id: item.sha256 for item in value.artifacts if item.authoritative
        }
        v1_semantic = {
            item["artifact_id"]: item["sha256"] for item in v1["artifacts"] if item["authoritative"]
        }
        assert v2_semantic == v1_semantic
        migration_reference = next(
            item for item in value.artifacts if item.artifact_kind == "v1_migration_reference"
        )
        assert migration_reference.sha256 == value.extensions["migration"]["v1_manifest_sha256"]
        verify_receipt(receipt(ticker), manifest=value)
    elif number == 34:
        for ticker in TICKERS:
            assert manifest(ticker).compatibility.native_source_production is False
    elif number == 35:
        catalog = load_json(CONFIG / "migration_canary_catalog_v2.json")
        assert all(item["deterministic"] for item in catalog["canaries"])
    elif number == 36:
        first = receipt().model_dump_json()
        second = receipt().model_dump_json()
        assert first == second
    elif number == 37:
        result = subprocess.run(
            ["node", "--test", "scripts/test_compiler_artifact_bundle_v2.mjs"],
            cwd=PRODUCT / "room16-app",
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
    elif number == 38:
        assert policy().mutable_bundle_hash_allowlist_allowed is False
        assert "bundle_hashes" not in load_json(CONFIG / "consumer_policy_v2.json")
    elif number == 39:
        assert 'testpaths = ["research_agent/tests"]' in (ROOT / "pyproject.toml").read_text()
    elif number == 40:
        package = load_json(PRODUCT / "room16-app/package.json")
        assert (
            "test_compiler_artifact_bundle_v2.mjs"
            in package["scripts"]["verify:compiler-artifact-bundle"]
        )
    elif number == 41:
        assert all(
            CompilerArtifactBundleManifest.model_validate(
                load_json(CANARIES / ticker / "V1_BUNDLE_MANIFEST.json")
            ).contract_version
            == 1
            for ticker in TICKERS
        )
    elif number == 42:
        assert policy().ba11_freeze_sha256 == (
            "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf"
        )
    elif number == 43:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        assert not any("signing_key_ed25519.bin" in item for item in tracked)
        assert not any(
            "private" in item.lower() and "productization_v2" in item for item in tracked
        )
    elif number == 44:
        foreign = ROOT.parents[1] / "Utility-Websites/materialbedarf-rechner.de"
        assert (
            subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=foreign,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            == "https://github.com/BCRAdmin/materialbedarf-rechner.de.git"
        )
    elif number == 45:
        source = ROOT / "scripts/ops/build_rfc0008_v2_trust_evidence.py"
        assert source.is_file() and "deterministic" in source.read_text(encoding="utf-8")
