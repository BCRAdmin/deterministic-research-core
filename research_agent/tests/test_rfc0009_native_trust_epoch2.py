from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from research_agent.productization_v2.native_trust import (
    GEN2_CONSUMER_ENVELOPE_PATH,
    GEN2_EMITTER_PROFILE_PATH,
    GEN2_SCHEMA_PROFILE_PATH,
    NativeTrustError,
    load_native_trust,
    verify_native_bundle_v2,
)

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
FREEZE = ROOT / "docs/compiler_foundation/freezes/RFC0008_COMPILER_ARTIFACT_BUNDLE_V2_TRUST_FREEZE_v1.json"
PROBE = ROOT / "research_agent/tests/fixtures/rfc0009-native-probe"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_rfc9_t001_rfc0008_freeze_protected_files_remain_exact() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    for repository, root in (("research", ROOT), ("product", PRODUCT)):
        for record in freeze["protected_files"][repository]:
            assert _sha(root / record["path"]) == record["sha256"]
    assert freeze["freeze_sha256"] == "27636f891457a98a790702f8fbba19763e0a8b363978c205c9eca54361a84fb0"


def test_rfc9_t002_any_gen1_byte_change_is_detectable() -> None:
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    record = freeze["protected_files"]["research"][0]
    payload = (ROOT / record["path"]).read_bytes()
    assert hashlib.sha256(payload).hexdigest() == record["sha256"]
    assert hashlib.sha256(payload + b"\n").hexdigest() != record["sha256"]


def test_rfc9_research_verifies_rooted_gen2_and_native_probe() -> None:
    trust = load_native_trust()
    receipt = json.loads((PROBE / "RECEIPT.json").read_text(encoding="utf-8"))
    result = verify_native_bundle_v2(PROBE, receipt=receipt)
    assert result["status"] == "PASS"
    assert result["consumer_policy_generation"] == 2
    assert result["consumer_policy_envelope_sha256"] == trust["gen2"]["envelope_sha256"]


@pytest.mark.parametrize(
    ("field", "value", "code"),
    (
        ("previous_envelope_sha256", "0" * 64, "RFC9_GEN2_PREDECESSOR_INVALID"),
        ("generation", 3, "RFC9_GEN2_PREDECESSOR_INVALID"),
        ("root_key_id", "research.attacker.root", "RFC9_GEN2_ROOT_MISMATCH"),
    ),
)
def test_rfc9_gen2_chain_mutations_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: object, code: str
) -> None:
    import research_agent.productization_v2.native_trust as native

    envelope = json.loads(GEN2_CONSUMER_ENVELOPE_PATH.read_text(encoding="utf-8"))
    envelope[field] = value
    target = tmp_path / "gen2.json"
    target.write_text(json.dumps(envelope), encoding="utf-8")
    monkeypatch.setattr(native, "GEN2_CONSUMER_ENVELOPE_PATH", target)
    with pytest.raises(NativeTrustError, match=code):
        native.load_native_trust()


def test_rfc9_research_product_public_mirrors_are_byte_exact() -> None:
    pairs = (
        (GEN2_CONSUMER_ENVELOPE_PATH, "room16_compiler_artifact_consumer_policy_envelope_v2_generation_2_native.json"),
        (GEN2_SCHEMA_PROFILE_PATH, "room16_compiler_artifact_bundle_schema_profile_v2_generation_2_native.json"),
        (GEN2_EMITTER_PROFILE_PATH, "room16_compiler_native_emitter_profile_v2.json"),
    )
    for research_path, product_name in pairs:
        assert research_path.read_bytes() == (PRODUCT / "room16-app/config" / product_name).read_bytes()


def test_rfc9_t043_private_signing_keys_absent_from_git_and_product() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.splitlines()
    assert not any("signing_key_ed25519.bin" in item for item in tracked)
    assert not list(PRODUCT.rglob("*signing_key*"))
    assert not list((ROOT / "outputs").rglob("*signing_key*"))
