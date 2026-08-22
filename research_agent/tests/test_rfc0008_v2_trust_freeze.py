from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

from scripts.ops.verify_rfc0008_v2_trust_freeze import (
    DEFAULT_ACCEPTANCE,
    DEFAULT_HANDOFF,
    DEFAULT_PRODUCT,
    DEFAULT_RECORD,
    ROOT,
    freeze_sha256,
    verify,
)


FREEZE_TEST_IDS = tuple(f"RFC8-F-T-{index:03d}" for index in range(1, 21))


@pytest.fixture(scope="module")
def freeze_result() -> dict[str, object]:
    return verify(DEFAULT_RECORD, DEFAULT_ACCEPTANCE, DEFAULT_HANDOFF, DEFAULT_PRODUCT)


@pytest.mark.parametrize("test_id", FREEZE_TEST_IDS, ids=FREEZE_TEST_IDS)
def test_rfc0008_freeze_matrix(
    test_id: str, freeze_result: dict[str, object]
) -> None:
    assert freeze_result["status"] == "PASS"
    checks = freeze_result["checks"]
    assert isinstance(checks, dict)
    mapping = {
        "RFC8-F-T-001": "handoff_integrity",
        "RFC8-F-T-002": "r2_standalone_verifier",
        "RFC8-F-T-003": "r2_standalone_verifier",
        "RFC8-F-T-004": "research_identity",
        "RFC8-F-T-005": "product_identity",
        "RFC8-F-T-006": "ba10_freeze",
        "RFC8-F-T-007": "ba11_freeze",
        "RFC8-F-T-008": "ba10_freeze",
        "RFC8-F-T-009": "trust_bindings",
        "RFC8-F-T-010": "trust_bindings",
        "RFC8-F-T-011": "trust_bindings",
        "RFC8-F-T-012": "trust_bindings",
        "RFC8-F-T-013": "migration_canaries",
        "RFC8-F-T-014": "migration_canaries",
        "RFC8-F-T-015": "migration_canaries",
        "RFC8-F-T-016": "frozen_files_exact",
        "RFC8-F-T-017": "private_keys_absent",
        "RFC8-F-T-018": "frozen_files_exact",
        "RFC8-F-T-019": "final_status",
        "RFC8-F-T-020": "freeze_self_hash",
    }
    assert checks[mapping[test_id]] is True


def test_freeze_self_hash_fails_after_status_tamper() -> None:
    record = json.loads(DEFAULT_RECORD.read_text(encoding="utf-8"))
    assert record["freeze_sha256"] == freeze_sha256(record)
    record["release_authorized"] = True
    assert record["freeze_sha256"] != freeze_sha256(record)


def test_external_acceptance_is_byte_exact_handoff_member() -> None:
    with zipfile.ZipFile(DEFAULT_HANDOFF) as archive:
        assert (
            archive.read("01_EXTERNAL_INDEPENDENT_RFC0008_ACCEPTANCE.json")
            == DEFAULT_ACCEPTANCE.read_bytes()
        )


def test_freeze_phase_has_no_rfc0008_runtime_worktree_diff() -> None:
    research = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "research_agent/productization_v2",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    product = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "room16-app/config/room16_compiler_v2_trust_root.json",
            "room16-app/config/room16_compiler_artifact_consumer_policy_envelope_v2.json",
            "room16-app/config/room16_compiler_artifact_key_policy_envelope_v2.json",
            "room16-app/config/room16_compiler_artifact_bundle_schema_profile_v2.json",
            "room16-app/server-modules/compiler-artifact-bundle-v2.mjs",
        ],
        cwd=DEFAULT_PRODUCT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert research == ""
    assert product == ""


def test_handoff_and_r2_authority_hashes_are_exact() -> None:
    with zipfile.ZipFile(DEFAULT_HANDOFF) as archive:
        r2 = archive.read(
            "authority/ROOM16_RFC0008_V2_TRUST_MIGRATION_R2_"
            "939AF5294285_2026-08-21.zip"
        )
    assert (
        hashlib.sha256(r2).hexdigest()
        == "130fcf06f2ce9698bdd9ffaba305abf3416b04855c8a505131103a626b612fab"
    )
