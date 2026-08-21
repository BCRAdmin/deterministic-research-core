from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest
from nacl.signing import SigningKey
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json
from research_agent.productization.contracts import CompilerArtifactBundleManifest
from research_agent.productization_v2.artifact_bundle import (
    load_consumer_policy_v2,
    load_public_key_policy_v2,
    load_trust_root_v2,
    verify_compiler_artifact_bundle_v2,
)
from research_agent.productization_v2.contracts import (
    BundleReceiptV2,
    CompilerArtifactBundleManifestV2,
    CompilerIdentityV2,
    ConsumerPolicyEnvelopeV2,
    PublicKeyPolicyEnvelopeV2,
    PublicKeyPolicyV2,
)
from research_agent.productization_v2.trust_receipt import (
    ReceiptV2Error,
    verify_bundle_receipt_v2,
)
from research_agent.productization_v2.trust_root import (
    TrustRootV2Error,
    envelope_domain_hash,
    verify_policy_envelope,
    verify_policy_envelope_chain,
)
from scripts.ops.verify_rfc0008_v2_trust_evidence import (
    MANIFEST_DOMAIN,
    REQUIRED_MEMBERS,
    EvidenceVerificationError,
    verify_package,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
CONFIG = ROOT / "research_agent/productization_v2/config"
CANARIES = CONFIG / "migration_canaries"
PRODUCT_FIXTURE = PRODUCT / "room16-app/fixtures/compiler-artifact-bundle-v2-pinned"
FOREIGN = ROOT.parents[1] / "Utility-Websites/materialbedarf-rechner.de"
TEST_IDS = tuple(f"RFC8-R2-T-{index:03d}" for index in range(1, 46))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def manifest(ticker: str = "WM") -> CompilerArtifactBundleManifestV2:
    value = CompilerArtifactBundleManifestV2.model_validate(
        load(CANARIES / ticker / "BUNDLE_MANIFEST.json")
    )
    value.verify_bundle_hash()
    return value


def receipt(ticker: str = "WM") -> BundleReceiptV2:
    return BundleReceiptV2.model_validate(load(CANARIES / ticker / "RECEIPT.json"))


def consumer_envelope() -> ConsumerPolicyEnvelopeV2:
    return ConsumerPolicyEnvelopeV2.model_validate(
        load(CONFIG / "consumer_policy_envelope_v2.json")
    )


def key_envelope() -> PublicKeyPolicyEnvelopeV2:
    return PublicKeyPolicyEnvelopeV2.model_validate(
        load(CONFIG / "public_key_policy_envelope_v2.json")
    )


def rehash_manifest(value: dict) -> dict:
    value = copy.deepcopy(value)
    value.pop("bundle_sha256", None)
    value["bundle_sha256"] = sha256_json(value)
    return value


def deterministic_zip(path: Path, payloads: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name in sorted(payloads):
            info = zipfile.ZipInfo(name, (2026, 8, 21, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, payloads[name])


def valid_evidence_zip(path: Path) -> Path:
    payloads = {
        name: canonical_bytes({"contract_id": f"fixture.{name}", "status": "PASS"})
        for name in REQUIRED_MEMBERS
    }
    files = [
        {"bytes": len(data), "path": name, "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in sorted(payloads.items())
    ]
    body = {
        "acceptance": {
            "r1_matrix_passed": 45,
            "r1_matrix_total": 45,
            "r2_matrix_passed": 45,
            "r2_matrix_total": 45,
        },
        "baseline_lock": {
            "ba10_v1_freeze_sha256": "29bc0bf2d00aa22d49fd7bb569cf080cc335778c1773b9e63710ecd61dfebc8e",
            "ba11_freeze_sha256": "2c0e0e292f2b167e68814e2e2180f9f0823ea8be452be52b95f56db95a4ca1cf",
            "product_base": "874e3f02f758f90e8fe9cb6394dda9fa884bbd0c",
            "research_base": "add974e6d93c095a3aa7ca607c0d85acf60058e0",
        },
        "contract_id": "room16.rfc0008.v2_trust_migration_evidence_manifest",
        "contract_version": 2,
        "files": files,
        "final_state": {
            "ba12_implementation_ready": False,
            "ba12_resume_authorized": False,
            "deploy_allowed": False,
            "publication_allowed": False,
            "ready_for_independent_rereview": True,
            "release_allowed": False,
            "rfc0008_frozen": False,
            "rfc0008_implementation_ready": False,
        },
        "generated_date": "2026-08-21",
        "manifest_hash_domain": MANIFEST_DOMAIN,
        "manifest_hash_preimage_rule": "sha256(canonical_json({domain,value:manifest_without_manifest_sha256}))",
        "payload_rule": "all ZIP members except MANIFEST.json",
    }
    manifest_value = {
        **body,
        "manifest_sha256": hashlib.sha256(
            canonical_bytes({"domain": MANIFEST_DOMAIN, "value": body})
        ).hexdigest(),
    }
    payloads["MANIFEST.json"] = canonical_bytes(manifest_value)
    deterministic_zip(path, payloads)
    return path


def mutate_evidence(source: Path, output: Path, mutate) -> Path:
    with zipfile.ZipFile(source) as zf:
        payloads = {name: zf.read(name) for name in zf.namelist()}
    mutate(payloads)
    deterministic_zip(output, payloads)
    return output


@pytest.mark.parametrize("test_id", TEST_IDS, ids=TEST_IDS)
def test_rfc0008_r2_acceptance_matrix(test_id: str, tmp_path: Path) -> None:
    number = int(test_id.rsplit("-", 1)[1])
    root = load_trust_root_v2()
    policy = load_consumer_policy_v2()
    keys = load_public_key_policy_v2()
    if number == 1:
        root.verify_self_hash()
        assert (
            root.root_sha256 == "56a94fcd6eede746dc2778f05774bc46f80cd50be02cf3302027aab729f8a356"
        )
    elif number in {2, 3}:
        pattern = "blocks replacement" if number == 2 else "blocks caller-selected"
        result = subprocess.run(
            [
                "node",
                "--test",
                f"--test-name-pattern={pattern}",
                "scripts/test_compiler_artifact_bundle_v2.mjs",
            ],
            cwd=PRODUCT / "room16-app",
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0 and "pass 1" in result.stdout
    elif number == 4:
        changed = root.model_copy(update={"root_public_key_hex": "0" * 64})
        with pytest.raises(ValueError):
            changed.verify_self_hash()
    elif number == 5:
        verify_policy_envelope(consumer_envelope(), root=root)
    elif number == 6:
        value = consumer_envelope().model_dump(mode="json")
        value["payload"]["key_policy_sha256"] = "0" * 64
        body = dict(value["payload"])
        body.pop("policy_sha256")
        value["payload"]["policy_sha256"] = sha256_json(body)
        value["envelope_sha256"] = envelope_domain_hash(value)
        with pytest.raises(TrustRootV2Error, match="SIGNATURE"):
            verify_policy_envelope(ConsumerPolicyEnvelopeV2.model_validate(value), root=root)
    elif number == 7:
        verify_policy_envelope(key_envelope(), root=root)
    elif number == 8:
        value = key_envelope().model_dump(mode="json")
        value["payload"]["keys"][0]["state"] = "grace_verify_only"
        body = dict(value["payload"])
        body.pop("policy_sha256")
        value["payload"]["policy_sha256"] = sha256_json(body)
        value["envelope_sha256"] = envelope_domain_hash(value)
        with pytest.raises(TrustRootV2Error, match="SIGNATURE"):
            verify_policy_envelope(PublicKeyPolicyEnvelopeV2.model_validate(value), root=root)
    elif number == 9:
        second = ConsumerPolicyEnvelopeV2.model_validate(
            load(CONFIG / "policy_chain_fixtures/consumer_policy_envelope_v2_generation_2.json")
        )
        assert (
            verify_policy_envelope_chain([consumer_envelope(), second], root=root).generation == 2
        )
    elif number == 10:
        second = PublicKeyPolicyEnvelopeV2.model_validate(
            load(CONFIG / "policy_chain_fixtures/public_key_policy_envelope_v2_generation_2.json")
        )
        with pytest.raises(TrustRootV2Error, match="GENESIS"):
            verify_policy_envelope_chain([second], root=root)
    elif number == 11:
        with pytest.raises(TrustRootV2Error, match="FORK"):
            verify_policy_envelope_chain([consumer_envelope(), consumer_envelope()], root=root)
    elif number == 12:
        value = keys.model_dump(mode="json", exclude={"policy_sha256"})
        duplicate = dict(value["keys"][0])
        duplicate["key_id"] = "research.rfc0008.secondary"
        value["keys"] = sorted([*value["keys"], duplicate], key=lambda item: item["key_id"])
        value["policy_sha256"] = sha256_json(value)
        with pytest.raises(ValidationError, match="duplicated"):
            PublicKeyPolicyV2.model_validate(value)
    elif number == 13:
        verify_bundle_receipt_v2(
            receipt(),
            manifest=manifest(),
            consumer_policy=policy,
            key_policy=keys,
            now_utc="2026-08-21T13:00:00Z",
        )
    elif number == 14:
        value = receipt().model_dump(mode="json")
        value["research_key_id"] = "product.ephemeral.attacker"
        value["receipt_sha256"] = sha256_json(
            {
                "domain": "room16.compiler_artifact_bundle_receipt@2",
                "value": {key: item for key, item in value.items() if key != "receipt_sha256"},
            }
        )
        with pytest.raises(ReceiptV2Error, match="UNKNOWN_KEY"):
            verify_bundle_receipt_v2(
                BundleReceiptV2.model_validate(value),
                manifest=manifest(),
                consumer_policy=policy,
                key_policy=keys,
                now_utc="2026-08-21T13:00:00Z",
            )
    elif number == 15:
        value = keys.model_dump(mode="json", exclude={"policy_sha256"})
        value["keys"][0]["state"] = "revoked"
        value["policy_sha256"] = sha256_json(value)
        with pytest.raises(ReceiptV2Error, match="REVOKED"):
            verify_bundle_receipt_v2(
                receipt(),
                manifest=manifest(),
                consumer_policy=policy,
                key_policy=PublicKeyPolicyV2.model_validate(value),
                now_utc="2026-08-21T13:00:00Z",
            )
    elif number == 16:
        assert (
            CompilerIdentityV2.model_validate(manifest().compiler_identity).foundation_version
            == "1.0.0"
        )
    elif number in {17, 18, 19, 20}:
        fields = {
            17: ["foundation_version"],
            18: ["registry_foundation_version"],
            19: ["semantic_wave_version_lock"],
            20: ["pass_manifest_sha256", "ir_schema_set_sha256", "registry_authority_sha256"],
        }[number]
        for field in fields:
            value = manifest().compiler_identity.model_dump(mode="json")
            value[field] = (
                "0" * 64 if field.endswith("sha256") or field.endswith("lock") else "9.9.9"
            )
            with pytest.raises(ValidationError):
                CompilerIdentityV2.model_validate(value)
    elif number == 21:
        assert manifest().artifact_index_sha256 == sha256_json(
            [item.model_dump(mode="json") for item in manifest().artifacts]
        )
    elif number == 22:
        value = manifest().model_dump(mode="json")
        value["artifact_index_sha256"] = "0" * 64
        value = rehash_manifest(value)
        with pytest.raises(ValidationError, match="artifact index"):
            CompilerArtifactBundleManifestV2.model_validate(value)
    elif number == 23:
        value = manifest().model_dump(mode="json")
        value["semantic_override"] = True
        with pytest.raises(ValidationError):
            CompilerArtifactBundleManifestV2.model_validate(value)
    elif number == 24:
        value = manifest().model_dump(mode="json")
        value["required_sections"] = value["required_sections"][1:]
        value = rehash_manifest(value)
        with pytest.raises(ValidationError, match="contract drift"):
            CompilerArtifactBundleManifestV2.model_validate(value)
    elif number == 25:
        value = manifest().model_dump(mode="json")
        value["section_index_sha256"] = "0" * 64
        value = rehash_manifest(value)
        with pytest.raises(ValidationError, match="section index"):
            CompilerArtifactBundleManifestV2.model_validate(value)
    elif number == 26:
        value = manifest().model_dump(mode="json")
        value["sections"][0]["artifact_ids"] = ["unknown.artifact"]
        value["section_index_sha256"] = sha256_json(value["sections"])
        value = rehash_manifest(value)
        with pytest.raises(ValidationError, match="unknown artifacts"):
            CompilerArtifactBundleManifestV2.model_validate(value)
    elif number in {27, 28}:
        value = manifest().model_dump(mode="json")
        value["eligibility"]["release_ready" if number == 27 else "publication_allowed"] = True
        with pytest.raises(ValidationError):
            CompilerArtifactBundleManifestV2.model_validate(value)
    elif number == 29:
        for ticker in ("WM", "COST", "ABT"):
            assert (
                CompilerArtifactBundleManifest.model_validate(
                    load(CANARIES / ticker / "V1_BUNDLE_MANIFEST.json")
                ).contract_version
                == 1
            )
    elif number in {30, 31, 32}:
        ticker = ("WM", "COST", "ABT")[number - 30]
        value = verify_compiler_artifact_bundle_v2(
            ROOT / f".runtime/rfc0008/migration_canaries/{ticker}/build_one/v2"
        )
        verify_bundle_receipt_v2(
            receipt(ticker),
            manifest=value,
            consumer_policy=policy,
            key_policy=keys,
            now_utc="2026-08-21T13:00:00Z",
        )
    elif number == 33:
        source = (
            PRODUCT / "room16-app/server-modules/compiler-artifact-bundle-router.mjs"
        ).read_text()
        assert "if (version === 2)" in source and "RFC8_ROUTER_VERSION_UNSUPPORTED" in source
    elif number in {34, 37}:
        package = valid_evidence_zip(tmp_path / "valid.zip")
        result = verify_package(package)
        assert result["status"] == "PASS" and result["manifest_sha256"]
    elif number == 35:
        source = valid_evidence_zip(tmp_path / "source.zip")
        tampered = mutate_evidence(
            source,
            tmp_path / "tampered.zip",
            lambda payloads: payloads.__setitem__(
                "MANIFEST.json",
                payloads["MANIFEST.json"].replace(b'"manifest_sha256":"', b'"manifest_sha256":"0'),
            ),
        )
        with pytest.raises(EvidenceVerificationError, match="SELF_HASH"):
            verify_package(tampered)
    elif number == 36:
        source = valid_evidence_zip(tmp_path / "source.zip")
        extra = mutate_evidence(
            source,
            tmp_path / "extra.zip",
            lambda payloads: payloads.__setitem__("unmanifested.json", b"{}"),
        )
        with pytest.raises(EvidenceVerificationError, match="CLOSURE"):
            verify_package(extra)
    elif number == 38:
        source = valid_evidence_zip(tmp_path / "source.zip")
        missing_name = sorted(REQUIRED_MEMBERS)[0]
        missing = mutate_evidence(
            source, tmp_path / "missing.zip", lambda payloads: payloads.pop(missing_name)
        )
        with pytest.raises(EvidenceVerificationError):
            verify_package(missing)
    elif number == 39:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        product_tracked = subprocess.run(
            ["git", "ls-files"], cwd=PRODUCT, check=True, capture_output=True, text=True
        ).stdout.splitlines()
        assert not any(
            "signing_key" in item or ".runtime/rfc0008" in item
            for item in [*tracked, *product_tracked]
        )
    elif number == 40:
        source = ROOT / "scripts/ops/build_rfc0008_v2_trust_evidence_r2.py"
        assert source.is_file() and "pytest" in source.read_text(encoding="utf-8")
    elif number == 41:
        package_json = load(PRODUCT / "room16-app/package.json")
        assert (
            "test_compiler_artifact_bundle_v2.mjs"
            in package_json["scripts"]["verify:compiler-artifact-bundle"]
        )
    elif number == 42:
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
    elif number == 43:
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
    elif number == 44:
        first = valid_evidence_zip(tmp_path / "one.zip")
        second = valid_evidence_zip(tmp_path / "two.zip")
        assert first.read_bytes() == second.read_bytes()
    elif number == 45:
        assert (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=FOREIGN,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            == "b8da17ea731d014341da2a45ec86af65dce5291a"
        )
        assert (
            subprocess.run(
                ["git", "rev-parse", "HEAD^{tree}"],
                cwd=FOREIGN,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            == "ca79b2022dcba4a3257b9035d225cdc9df7451df"
        )
