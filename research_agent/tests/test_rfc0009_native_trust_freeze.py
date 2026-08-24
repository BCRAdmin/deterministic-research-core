from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import zipfile

import pytest

from scripts.ops.verify_rfc0009_native_trust_freeze import (
    DEFAULT_ACCEPTANCE,
    DEFAULT_HANDOFF,
    DEFAULT_PRODUCT,
    DEFAULT_RECORD,
    ROOT,
    freeze_sha256,
    verify,
)


FREEZE_TEST_IDS = tuple(f"RFC9-F-T-{index:03d}" for index in range(1, 21))


@pytest.fixture(scope="module")
def result() -> dict[str, object]:
    return verify(DEFAULT_RECORD, DEFAULT_ACCEPTANCE, DEFAULT_HANDOFF, DEFAULT_PRODUCT)


@pytest.mark.parametrize("test_id", FREEZE_TEST_IDS, ids=FREEZE_TEST_IDS)
def test_rfc0009_freeze_matrix(test_id: str, result: dict[str, object]) -> None:
    assert result["status"] == "PASS"
    checks = result["checks"]
    assert isinstance(checks, dict)
    mapping = {
        "RFC9-F-T-001": "r2_package_identity",
        "RFC9-F-T-002": "r2_standalone_verifier",
        "RFC9-F-T-003": "r2_standalone_verifier",
        "RFC9-F-T-004": "native_trust_bindings",
        "RFC9-F-T-005": "native_trust_bindings",
        "RFC9-F-T-006": "dynamic_emitter_rule",
        "RFC9-F-T-007": "dynamic_emitter_rule",
        "RFC9-F-T-008": "r2_standalone_verifier",
        "RFC9-F-T-009": "dynamic_boolean_rules",
        "RFC9-F-T-010": "dynamic_boolean_rules",
        "RFC9-F-T-011": "final_status",
        "RFC9-F-T-012": "frozen_files_exact",
        "RFC9-F-T-013": "native_trust_bindings",
        "RFC9-F-T-014": "r2_standalone_verifier",
        "RFC9-F-T-015": "ba10_freeze",
        "RFC9-F-T-016": "ba11_freeze",
        "RFC9-F-T-017": "rfc0008_freeze",
        "RFC9-F-T-018": "frozen_files_exact",
        "RFC9-F-T-019": "freeze_contract",
        "RFC9-F-T-020": "freeze_self_hash",
    }
    assert checks[mapping[test_id]] is True


def test_freeze_self_hash_rejects_escalation() -> None:
    record = json.loads(DEFAULT_RECORD.read_text(encoding="utf-8"))
    assert record["freeze_sha256"] == freeze_sha256(record)
    tampered = copy.deepcopy(record)
    tampered["release_authorized"] = True
    assert tampered["freeze_sha256"] != freeze_sha256(tampered)


def test_external_acceptance_is_byte_exact() -> None:
    with zipfile.ZipFile(DEFAULT_HANDOFF) as archive:
        assert archive.read("01_EXTERNAL_INDEPENDENT_RFC0009_ACCEPTANCE.json") == DEFAULT_ACCEPTANCE.read_bytes()


def test_handoff_and_embedded_authorities_are_exact() -> None:
    with zipfile.ZipFile(DEFAULT_HANDOFF) as archive:
        r2 = archive.read("authority/ROOM16_RFC0009_BA12_NATIVE_TRUST_EPOCH2_R2_A77CAD16F16F_2026-08-22.zip")
        ba12 = archive.read("authority/ROOM16_BA12_FINAL_STRANGLER_CUTOVER_EXECUTION_R1_5CDAE89A5339_2026-08-21.zip")
    assert hashlib.sha256(r2).hexdigest() == "a0639186b4d54547a4a2249e8eafab7d66ff692b1a54fbb95eb0e4da6c7a829e"
    assert hashlib.sha256(ba12).hexdigest() == "5cdae89a5339400ead3079ea6b5f58f4662439a6946b61c5cdbf6f57e8efef43"


def test_phase_a_has_no_runtime_diff() -> None:
    research = subprocess.run(["git", "status", "--porcelain", "--", "research_agent/productization_v2"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    product = subprocess.run(["git", "status", "--porcelain", "--", "room16-app"], cwd=DEFAULT_PRODUCT, check=True, capture_output=True, text=True).stdout
    assert research == ""
    assert product == ""
