from __future__ import annotations

from dataclasses import replace
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from nacl.exceptions import BadSignatureError

from research_agent.ba12_native.compiler import resolve_bundle_signing_authority
from research_agent.productization_v2.native_trust import load_native_trust
from research_agent.tests.support.room16_test_signing import (
    PRODUCTION_PUBLIC_KEY_HEX,
    TEST_PUBLIC_KEY_HEX,
    r16_test_signing_authority,
    sign_test_payload,
    r16_test_key_id,
    verify_test_payload,
)


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
PRODUCTION_FIXTURE = (
    ROOT
    / "research_agent/tests/fixtures/production_signed_compiler_bundle_v2_pinned"
)


def _verify_production_fixture(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            "import fs from 'node:fs'; import {verifyCompilerArtifactBundleV2} from './room16-app/server-modules/compiler-artifact-bundle-v2.mjs'; const root=process.argv[1]; const receipt=JSON.parse(fs.readFileSync(root+'/RECEIPT.json','utf8')); console.log(verifyCompilerArtifactBundleV2(root,{receipt}).manifest.bundle_sha256)",
            str(root),
        ],
        cwd=PRODUCT,
        capture_output=True,
        text=True,
    )


def test_test_key_is_not_production_trust_key():
    assert TEST_PUBLIC_KEY_HEX != PRODUCTION_PUBLIC_KEY_HEX
    assert r16_test_key_id().startswith("ROOM16_TEST_ONLY_")


def test_injected_signing_authority_requires_test_only_namespace():
    authority = replace(
        r16_test_signing_authority(),
        key_id="room16.production.impersonation",
    )
    with pytest.raises(ValueError, match="BA12_TEST_ONLY_SIGNING_AUTHORITY_REQUIRED"):
        resolve_bundle_signing_authority(
            authority,
            production_key_policy=load_native_trust()["key_policy"],
            mismatch_code="BA12_SIGNING_KEY_POLICY_MISMATCH",
        )


def test_test_signing_is_deterministic_and_verifiable():
    payload = b"room16-test-signing-contract-v1"
    first = sign_test_payload(payload)
    second = sign_test_payload(payload)
    assert first == second
    verify_test_payload(payload, first)


def test_tamper_is_rejected():
    payload = b"room16-test-signing-contract-v1"
    signature = sign_test_payload(payload)
    with pytest.raises(BadSignatureError):
        verify_test_payload(payload + b"-tampered", signature)


def test_frozen_product_verifier_accepts_authentic_production_fixture():
    expected = json.loads((PRODUCTION_FIXTURE / "BUNDLE_MANIFEST.json").read_text())[
        "bundle_sha256"
    ]
    result = _verify_production_fixture(PRODUCTION_FIXTURE)
    assert result.returncode == 0 and expected in result.stdout


def test_frozen_product_verifier_rejects_tampered_production_fixture(tmp_path: Path):
    copied = tmp_path / "production-fixture"
    shutil.copytree(PRODUCTION_FIXTURE, copied)
    artifact = copied / "artifacts/typed_facts.json"
    artifact.write_bytes(artifact.read_bytes() + b"\n")
    result = _verify_production_fixture(copied)
    assert result.returncode != 0
    assert "RFC8_ARTIFACT_HASH_MISMATCH" in result.stderr
