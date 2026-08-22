from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ops.verify_ba12_rfc0008_native_trust_conflict import verify

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
EVIDENCE = ROOT / "docs/compiler_foundation/rfcs/BA12_R2_NATIVE_TRUST_CONFLICT_STOP.json"
TEST_IDS = tuple(f"BA12-STOP-{index:03d}" for index in range(1, 6))


@pytest.mark.parametrize("test_id", TEST_IDS, ids=TEST_IDS)
def test_ba12_native_trust_stop_contract(test_id: str) -> None:
    result = verify(PRODUCT)
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    number = int(test_id.rsplit("-", 1)[1])
    if number == 1:
        assert result["diagnostic_code"] == "RFC8_TRUST_POLICY_MISMATCH"
    elif number == 2:
        assert result["checks"]["bundle_v2_contract_accepts_source_native_identity"] is True
        assert result["checks"]["truthful_native_bundle_rejected_by_frozen_verifier"] is True
    elif number == 3:
        assert result["bindings"] == {
            key: value
            for key, value in evidence["bindings"].items()
            if key
            not in {
                "product_commit",
                "product_tree",
                "research_commit_before_stop_evidence",
                "research_tree_before_stop_evidence",
            }
        }
    elif number == 4:
        assert result["stop_conditions"] == [2, 6, 7, 8]
        assert result["forbidden_actions_preserved"]["frozen_v2_policy_changed"] is False
        assert result["forbidden_actions_preserved"]["product_changed"] is False
    else:
        assert evidence["status"] == "STOPPED_RFC_TRIGGER_REQUIRED"
        assert evidence["foreign_repository_boundary"]["unchanged"] is True
        assert evidence["forbidden_actions_preserved"]["ba12_frozen"] is False
