from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from research_agent.alpha_bank.v2 import BANK_V2_PROFILE, prepare_bank_v2_candidate
from research_agent.alpha_reit.v3 import (
    R15_ATTACK_FIELDS,
    REIT_V3_PROFILE,
    SOURCE_EXTENSION_CONTRACT,
    guard_r15_action,
    parse_primary_text_candidates,
    resolve_core_slots,
    select_reported_ffo,
    validate_primary_text_candidate,
)
from research_agent.alpha_saas.v2 import SAAS_V2_PROFILE, prepare_saas_v2_candidate
from research_agent.profile_authority.contracts import validate_sector_profile_contract
from research_agent.profile_authority.source_extension import (
    captured_artifact,
    seal_discovered_source_set,
    validate_sec_url,
    verify_self_hash,
)


@pytest.mark.parametrize("attack", sorted(R15_ATTACK_FIELDS))
def test_r15_active_attack_is_blocked(attack: str) -> None:
    with pytest.raises(ValueError, match="R15_POLICY_BLOCK"):
        guard_r15_action({attack: True})


def test_r15_has_at_least_50_active_attacks() -> None:
    assert len(R15_ATTACK_FIELDS) >= 50


def test_source_extension_rejects_non_sec_domain() -> None:
    with pytest.raises(ValueError, match="UNAPPROVED_DOMAIN"):
        validate_sec_url("https://example.com/not-authority")


def test_capture_must_exist_before_parse(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="CAPTURE_REQUIRED"):
        captured_artifact(
            tmp_path / "missing.json",
            url="https://data.sec.gov/submissions/CIK0000000001.json",
            media_type="application/json",
        )


def test_discovered_source_set_is_hash_bound() -> None:
    receipt = seal_discovered_source_set(
        ticker="TEST",
        cik="1",
        submissions_sha256="a" * 64,
        filing_index_artifacts=[{"sha256": "b" * 64}],
        documents=[
            {
                "url": "https://www.sec.gov/Archives/edgar/data/1/000000000126000001/test.htm",
                "accession": "0000000001-26-000001",
                "document_name": "test.htm",
                "filing_date": "2026-08-01",
            }
        ],
        maximum_documents=4,
    )
    assert verify_self_hash(receipt, "discovered_source_set_sha256")
    tampered = copy.deepcopy(receipt)
    tampered["documents"][0]["document_name"] = "other.htm"
    with pytest.raises(ValueError, match="SELF_HASH_MISMATCH"):
        verify_self_hash(tampered, "discovered_source_set_sha256")


def test_primary_text_candidate_is_explicit_and_tamper_evident(tmp_path: Path) -> None:
    payload = b"""<html><body><p>Reconciliation of net income to NAREIT FFO ($000)</p>
    <table><tr><td>FFO (as defined by NAREIT) attributable to common shareholders</td><td>$</td><td>3,058</td></tr>
    <tr><td>AFFO attributable to common shareholders</td><td>$</td><td>4,000</td></tr></table></body></html>"""
    path = tmp_path / "captured.htm"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    candidates = parse_primary_text_candidates(
        path,
        ticker="TEST",
        cik="1",
        filing={
            "accession": "0000000001-26-000001",
            "form": "8-K",
            "filing_date": "2026-08-01",
            "report_date": "2026-06-30",
            "document_name": "captured.htm",
        },
        source_artifact_sha256=digest,
        source_snapshot_sha256="b" * 64,
    )
    assert len(candidates) == 2
    selected = select_reported_ffo(candidates)
    assert selected["selected"]["numeric_value"] == "3058000"
    assert selected["selected"]["economic_scope_grade"] == "A"
    assert selected["receipt"]["status"] == "SELECTED"
    validate_primary_text_candidate(selected["selected"])
    tampered = copy.deepcopy(selected["selected"])
    tampered["numeric_value"] = "1"
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        validate_primary_text_candidate(tampered)


def test_core_slots_count_only_explicit_ffo() -> None:
    empty = resolve_core_slots(
        ["revenue", "net_income", "operating_cash_flow", "total_debt"],
        {"selected": None},
    )
    resolved = resolve_core_slots(
        ["revenue", "net_income", "operating_cash_flow", "total_debt"],
        {"selected": {"metric_id": "reported_ffo"}},
    )
    assert sum(row["counted"] for row in empty) == 4
    assert sum(row["counted"] for row in resolved) == 5


def test_shared_profile_candidates_are_full_hash_authority() -> None:
    for profile in (REIT_V3_PROFILE, BANK_V2_PROFILE, SAAS_V2_PROFILE):
        assert validate_sector_profile_contract(profile)
        assert profile["runtime_authority"]["full_contract_hash_authorization"] is True


def test_bank_and_saas_candidate_preparation_is_additive() -> None:
    bank = prepare_bank_v2_candidate(
        research_commit="a" * 40, research_tree="b" * 40, evidence_hashes=["c" * 64]
    )
    saas = prepare_saas_v2_candidate(
        research_commit="a" * 40, research_tree="b" * 40, evidence_hashes=["d" * 64]
    )
    assert bank["status"] == "BANK_V2_CANDIDATE_SEALED"
    assert saas["status"] == "SAAS_V2_CANDIDATE_SEALED"
    assert bank["clean_validation_performed"] is False
    assert saas["clean_validation_performed"] is False


def test_frozen_energy_is_not_part_of_source_extension() -> None:
    assert SOURCE_EXTENSION_CONTRACT["profile_family"] == "REIT"
    assert SOURCE_EXTENSION_CONTRACT["profile_version"] == 3
    assert SOURCE_EXTENSION_CONTRACT["historical_base_acquisition_contract_modified"] is False
