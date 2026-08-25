from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import zipfile

import pytest

from scripts.ops.verify_rfc0010_freeze import (
    DEFAULT_ACCEPTANCE,
    DEFAULT_HANDOFF,
    DEFAULT_PRODUCT,
    DEFAULT_RECORD,
    ROOT,
    freeze_sha256,
    verify,
)


FREEZE_TEST_IDS = tuple(f"RFC10-F-T-{index:03d}" for index in range(1, 25))


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return verify(DEFAULT_RECORD, DEFAULT_ACCEPTANCE, DEFAULT_HANDOFF, DEFAULT_PRODUCT)


@pytest.mark.parametrize("test_id", FREEZE_TEST_IDS, ids=FREEZE_TEST_IDS)
def test_rfc0010_freeze_matrix(test_id: str, result: dict[str, object]) -> None:
    assert result["status"] == "PASS"
    checks = result["checks"]
    assert isinstance(checks, dict)
    mapping = {
        "RFC10-F-T-001": "r2_package_identity",
        "RFC10-F-T-002": "r2_standalone_verifier",
        "RFC10-F-T-003": "r2_standalone_verifier",
        "RFC10-F-T-004": "research_identity",
        "RFC10-F-T-005": "product_identity",
        "RFC10-F-T-006": "foreign_boundary_binding",
        "RFC10-F-T-007": "foreign_boundary_binding",
        "RFC10-F-T-008": "independent_review_closure",
        "RFC10-F-T-009": "independent_review_closure",
        "RFC10-F-T-010": "runtime_files_exact",
        "RFC10-F-T-011": "runtime_files_exact",
        "RFC10-F-T-012": "runtime_files_exact",
        "RFC10-F-T-013": "runtime_files_exact",
        "RFC10-F-T-014": "ba3_contract",
        "RFC10-F-T-015": "semantic_wave_freeze",
        "RFC10-F-T-016": "ba10_freeze",
        "RFC10-F-T-017": "ba11_freeze",
        "RFC10-F-T-018": "rfc0008_freeze",
        "RFC10-F-T-019": "rfc0009_freeze",
        "RFC10-F-T-020": "r2_standalone_verifier",
        "RFC10-F-T-021": "product_identity",
        "RFC10-F-T-022": "phase_a_zero_runtime_diff",
        "RFC10-F-T-023": "freeze_self_hash",
        "RFC10-F-T-024": "foreign_boundary_binding",
    }
    assert checks[mapping[test_id]] is True


def test_freeze_self_hash_rejects_gate_escalation() -> None:
    record = json.loads(DEFAULT_RECORD.read_text(encoding="utf-8"))
    assert record["freeze_sha256"] == freeze_sha256(record)
    tampered = copy.deepcopy(record)
    tampered["release_authorized"] = True
    assert tampered["freeze_sha256"] != freeze_sha256(tampered)


def test_external_acceptance_is_byte_exact() -> None:
    with zipfile.ZipFile(DEFAULT_HANDOFF) as archive:
        assert (
            archive.read("01_EXTERNAL_INDEPENDENT_RFC0010_ACCEPTANCE.json")
            == DEFAULT_ACCEPTANCE.read_bytes()
        )


def test_handoff_embeds_exact_r2_and_ba12_authorities() -> None:
    with zipfile.ZipFile(DEFAULT_HANDOFF) as archive:
        r2 = archive.read(
            "authority/ROOM16_RFC0010_BA12_LIVE_CAPTURE_TRANSPORT_R2_6B2EFC3CB2FC_2026-08-25.zip"
        )
        ba12 = archive.read(
            "authority/ROOM16_BA12_FINAL_STRANGLER_CUTOVER_EXECUTION_R1_5CDAE89A5339_2026-08-21.zip"
        )
    assert hashlib.sha256(r2).hexdigest() == "4aee8c0d0fe2329f21cc3878ac5144352128abfc184e0ae2048e676b53c02b47"
    assert hashlib.sha256(ba12).hexdigest() == "5cdae89a5339400ead3079ea6b5f58f4662439a6946b61c5cdbf6f57e8efef43"


def test_phase_a_has_no_runtime_semantic_diff() -> None:
    research = subprocess.run(
        ["git", "status", "--porcelain", "--", "research_agent/ba12_live_source"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    product = subprocess.run(
        ["git", "status", "--porcelain", "--", "room16-app"],
        cwd=DEFAULT_PRODUCT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert research == ""
    assert product == ""
