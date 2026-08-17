from __future__ import annotations

import hashlib
import json
import shutil
import unicodedata
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from research_agent.compiler_foundation.canonical import canonical_json, sha256_json
from research_agent.productization.artifact_bundle import (
    ArtifactBundleError,
    build_compiler_artifact_bundle,
    materialize_authority_v3_view,
    verify_compiler_artifact_bundle,
)
from research_agent.productization.contracts import (
    REQUIRED_BUNDLE_SECTION_IDS,
    CompilerArtifactBundleManifest,
)
from research_agent.semantic_compiler.semantic_spine.rfc_0004 import replay_rfc_0004_archive

RESEARCH_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = RESEARCH_ROOT.parent / "company-dossier-lab"
CANARY_ROOT = PRODUCT_ROOT / ".runtime/cross-company-release-current/ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448"
WM_ARCHIVE = CANARY_ROOT / "ROOM16_WM_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
CANARY_HASHES = {
    "WM": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
    "COST": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
    "ABT": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_research_owned_cross_language_corpus_is_exact_and_nfc() -> None:
    path = RESEARCH_ROOT / "research_agent/productization/config/conformance_corpus_v1.json"
    corpus = json.loads(path.read_text(encoding="utf-8"))
    assert corpus["contract_id"] == "room16.compiler_artifact_bundle_conformance_corpus"
    for case in corpus["valid_cases"]:
        assert canonical_json(case["value"]) == case["canonical_json"]
        assert sha256_json(case["value"]) == case["sha256"]
        assert unicodedata.normalize("NFC", case["canonical_json"]) == case["canonical_json"]


def test_manifest_rejects_unknown_top_level_semantic_field() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CompilerArtifactBundleManifest.model_validate({"unexpected_truth": 1})


def test_frozen_canary_archives_are_unchanged() -> None:
    for ticker, expected in CANARY_HASHES.items():
        archive = CANARY_ROOT / f"ROOM16_{ticker}_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip"
        assert _sha(archive) == expected


@pytest.fixture(scope="module")
def wm_bundle(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, dict]:
    root = tmp_path_factory.mktemp("ba10-wm-bundle")
    replay = replay_rfc_0004_archive(archive=WM_ARCHIVE)
    first = root / "first"
    second = root / "second"
    build_compiler_artifact_bundle(archive=WM_ARCHIVE, output_root=first, replay=replay)
    build_compiler_artifact_bundle(archive=WM_ARCHIVE, output_root=second, replay=replay)
    return first, second, replay


def test_bundle_is_deterministic_and_contains_every_required_section(wm_bundle) -> None:
    first, second, _ = wm_bundle
    one = verify_compiler_artifact_bundle(first)
    two = verify_compiler_artifact_bundle(second)
    assert (first / "BUNDLE_MANIFEST.json").read_bytes() == (second / "BUNDLE_MANIFEST.json").read_bytes()
    assert one.bundle_sha256 == two.bundle_sha256
    assert one.schema_version == "1.1.0"
    assert tuple(section.section_id for section in one.sections) == REQUIRED_BUNDLE_SECTION_IDS
    assert all(section.owner == "research_compiler" for section in one.sections)
    assert all(item.owner == "research_compiler" for item in one.artifacts)
    assert one.compatibility.mode == "authority_v3_compatibility_shadow"
    assert one.compatibility.source_native_fact_generation is False
    assert one.eligibility.release_ready is False
    assert one.eligibility.publication_allowed is False
    assert {item.artifact_kind for item in one.artifacts if item.required}.issuperset(one.required_sections)


def test_bundle_tamper_fails_closed_with_stable_code(wm_bundle, tmp_path: Path) -> None:
    first, _, _ = wm_bundle
    second = tmp_path / "tampered"
    shutil.copytree(first, second)
    manifest = verify_compiler_artifact_bundle(second)
    target = next(item for item in manifest.artifacts if item.artifact_kind == "compile_verdict")
    path = second / target.relative_path
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ArtifactBundleError) as error:
        verify_compiler_artifact_bundle(second)
    assert error.value.diagnostic_code == "ABI_ARTIFACT_HASH_MISMATCH"


def test_authority_v3_bridge_materializes_exact_bytes(wm_bundle, tmp_path: Path) -> None:
    first, _, _ = wm_bundle
    result = materialize_authority_v3_view(bundle_root=first, output_root=tmp_path / "authority_bundle")
    assert result["byte_parity_verified"] is True
    manifest = verify_compiler_artifact_bundle(first)
    bridge_record = next(item for item in manifest.artifacts if item.artifact_kind == "authority_v3_bridge")
    bridge = json.loads((first / bridge_record.relative_path).read_text(encoding="utf-8"))
    with zipfile.ZipFile(WM_ARCHIVE) as source:
        for item in bridge["files"]:
            assert (tmp_path / "authority_bundle" / item["view_path"]).read_bytes() == source.read(item["source_member"])


def test_missing_required_artifact_fails_closed(wm_bundle, tmp_path: Path) -> None:
    first, _, _ = wm_bundle
    clone = tmp_path / "missing"
    shutil.copytree(first, clone)
    manifest = verify_compiler_artifact_bundle(clone)
    target = next(item for item in manifest.artifacts if item.required)
    (clone / target.relative_path).unlink()
    with pytest.raises(ArtifactBundleError) as error:
        verify_compiler_artifact_bundle(clone)
    assert error.value.diagnostic_code == "ABI_ARTIFACT_MISSING"


def test_missing_required_section_fails_closed(wm_bundle, tmp_path: Path) -> None:
    first, _, _ = wm_bundle
    clone = tmp_path / "missing-section"
    shutil.copytree(first, clone)
    manifest_path = clone / "BUNDLE_MANIFEST.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload.pop("sections")
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ArtifactBundleError) as error:
        verify_compiler_artifact_bundle(clone)
    assert error.value.diagnostic_code == "ABI_MANIFEST_INVALID"


def test_unknown_manifest_truth_fails_closed(wm_bundle, tmp_path: Path) -> None:
    first, _, _ = wm_bundle
    clone = tmp_path / "unknown-truth"
    shutil.copytree(first, clone)
    manifest_path = clone / "BUNDLE_MANIFEST.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["product_generated_rating"] = "buy"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ArtifactBundleError) as error:
        verify_compiler_artifact_bundle(clone)
    assert error.value.diagnostic_code == "ABI_MANIFEST_INVALID"
