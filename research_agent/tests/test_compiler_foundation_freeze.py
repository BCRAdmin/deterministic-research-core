from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ops.verify_compiler_foundation_freeze import (
    DEFAULT_MANIFEST,
    FreezeVerificationError,
    verify_foundation_freeze,
)

PRODUCT_REPO = Path(__file__).resolve().parents[3] / "company-dossier-lab"


def test_foundation_freeze_verifies_exact_repositories() -> None:
    result = verify_foundation_freeze(
        manifest_path=DEFAULT_MANIFEST,
        product_repo=PRODUCT_REPO,
    )
    assert result["status"] == "pass"
    assert result["compiler_foundation_version"] == "1.0.0"
    assert result["canaries"] == "unchanged"


def test_foundation_freeze_rejects_version_lock_tamper(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    payload["version_lock_inputs"]["authority_bundle_version"] = 4
    target = tmp_path / "tampered.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(FreezeVerificationError, match="foundation_version_lock"):
        verify_foundation_freeze(manifest_path=target, product_repo=PRODUCT_REPO)


def test_foundation_freeze_requires_exact_rfc_triggers() -> None:
    payload = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    assert payload["rfc_required_for"] == [
        "abi_change",
        "ir_change",
        "layer_change",
        "ownership_change",
        "pass_change",
        "registry_change",
    ]
    assert payload["development_boundary"] == {
        "foundation_changes_without_rfc_allowed": False,
        "future_changes_via_compiler_contracts_only": True,
        "company_specific_architecture_changes_allowed": False,
        "companies_validate_architecture": True,
        "next_build_section": "BA3",
    }
