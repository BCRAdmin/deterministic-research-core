from __future__ import annotations

from typing import Any

import pytest

from scripts.ops.run_fixed24_no_tuning_batch import _resolve_identity


class _NoDirectoryQueryAdapter:
    def get_company_tickers(self) -> object:
        raise AssertionError("existing directory proof must not query the provider")


def test_existing_directory_identity_proof_has_zero_provider_calls() -> None:
    directory = {
        "0": {
            "cik_str": 1035002,
            "ticker": "VLO",
            "title": "VALERO ENERGY CORP/TX",
        }
    }
    _, result = _resolve_identity(
        "VLO",
        "Valero Energy Corporation",
        _NoDirectoryQueryAdapter(),  # type: ignore[arg-type]
        directory_payload=directory,
        directory_source_receipt_sha256="b" * 64,
    )
    assert result["provider_query_count"] == 0
    assert result["identity_source_mode"] == "pinned_existing_company_directory"
    assert result["issuer_identity"]["cik"] == "0001035002"


def test_existing_directory_requires_a_bound_source_receipt() -> None:
    directory: dict[str, dict[str, Any]] = {
        "0": {"cik_str": 1035002, "ticker": "VLO", "title": "VALERO ENERGY CORP/TX"}
    }
    with pytest.raises(RuntimeError, match="ISSUER_IDENTITY_OFFLINE_DIRECTORY_RECEIPT_MISSING"):
        _resolve_identity(
            "VLO",
            "Valero Energy Corporation",
            _NoDirectoryQueryAdapter(),  # type: ignore[arg-type]
            directory_payload=directory,
        )
