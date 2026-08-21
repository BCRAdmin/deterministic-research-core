from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ops/verify_ba11_canary_governance_freeze.py"
SPEC = importlib.util.spec_from_file_location("verify_ba11_freeze", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_ba11_freeze_verifier_passes_for_accepted_identities() -> None:
    result = MODULE.verify(
        MODULE.DEFAULT_RECORD,
        MODULE.DEFAULT_ACCEPTANCE,
        MODULE.DEFAULT_HANDOFF,
        ROOT.parent / "company-dossier-lab",
    )
    assert result["status"] == "PASS"
    assert result["independent_rereview"] == "ACCEPTED"
    assert result["ba11_implementation_ready"] is True
    assert result["ba11_frozen"] is True
    assert result["ba12_authorized"] is False


def test_ba11_freeze_verifier_rejects_record_tamper(tmp_path: Path) -> None:
    record = json.loads(MODULE.DEFAULT_RECORD.read_text(encoding="utf-8"))
    record["publication_authorized"] = True
    path = tmp_path / "tampered-freeze.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    result = MODULE.verify(
        path,
        MODULE.DEFAULT_ACCEPTANCE,
        MODULE.DEFAULT_HANDOFF,
        ROOT.parent / "company-dossier-lab",
    )
    assert result["status"] == "FAIL"
    assert result["checks"]["freeze_self_hash"] is False
    assert result["checks"]["final_status"] is False


def test_ba11_freeze_verifier_rejects_acceptance_tamper(tmp_path: Path) -> None:
    acceptance = json.loads(MODULE.DEFAULT_ACCEPTANCE.read_text(encoding="utf-8"))
    acceptance["verdict"] = "CHANGES_REQUIRED"
    path = tmp_path / "tampered-acceptance.json"
    path.write_text(json.dumps(acceptance), encoding="utf-8")
    result = MODULE.verify(
        MODULE.DEFAULT_RECORD,
        path,
        MODULE.DEFAULT_HANDOFF,
        ROOT.parent / "company-dossier-lab",
    )
    assert result["status"] == "FAIL"
    assert result["checks"]["independent_acceptance_file"] is False


def test_ba11_freeze_hash_is_domain_separated() -> None:
    record = json.loads(MODULE.DEFAULT_RECORD.read_text(encoding="utf-8"))
    original = MODULE.freeze_sha256(record)
    record["freeze_hash_domain"] = "room16.ba11.other_domain@1"
    assert MODULE.freeze_sha256(record) != original
