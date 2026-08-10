from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_agent.research_core.ingestion.source_registry import (
    bind_registry_claims,
    SourceRegistry,
    SourceRegistryEntry,
)
from research_agent.research_core.ingestion.source_snapshot import (
    build_source_snapshot_manifest,
    verify_source_snapshot_manifest,
)


def _registry(ticker: str = "TEST") -> SourceRegistry:
    return SourceRegistry(
        registry_id=f"{ticker}_2026-08-10",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker}_SEC_0000123456-26-000001",
                ticker=ticker,
                source_type="sec_filing",
                url=(
                    "https://www.sec.gov/Archives/edgar/data/123456/"
                    "000012345626000001/filing.htm"
                ),
                used_for=["revenue"],
            ),
            SourceRegistryEntry(
                source_id=f"{ticker}_PRICE",
                ticker=ticker,
                source_type="exchange_ohlcv",
                used_for=["price"],
            ),
            SourceRegistryEntry(
                source_id=f"ROOM16_{ticker}_CALCULATIONS",
                ticker=ticker,
                source_type="deterministic_calculation",
                used_for=["free_cash_flow"],
            ),
        ],
    )


def _source_tree(root: Path, ticker: str = "TEST") -> None:
    filing = root / "sec" / "filing.json"
    filing.parent.mkdir(parents=True, exist_ok=True)
    filing.write_text(
        json.dumps({"accession": "0000123456-26-000001", "revenue": 10}),
        encoding="utf-8",
    )
    prices = root / "prices" / f"{ticker}.csv"
    prices.parent.mkdir(parents=True, exist_ok=True)
    prices.write_text(
        "date,open,high,low,close,volume\n2026-08-10,10,11,9,10,100\n",
        encoding="utf-8",
    )


def test_registry_binds_narrative_claims_without_numeric_fact_metrics() -> None:
    registry = _registry()
    source_id = "TEST_SEC_0000123456-26-000001"
    claim = SimpleNamespace(
        claim_id="TEST_CLAIM_007",
        source_ids=[source_id],
    )

    bind_registry_claims(
        registry,
        {"claims": []},
        research_claims=[claim],
    )

    source = next(item for item in registry.sources if item.source_id == source_id)
    assert source.claim_ids == ["TEST_CLAIM_007"]


def test_registry_rejects_narrative_claim_with_unregistered_source() -> None:
    registry = _registry()
    claim = SimpleNamespace(
        claim_id="TEST_CLAIM_008",
        source_ids=["TEST_UNREGISTERED_SOURCE"],
    )

    with pytest.raises(ValueError, match="references unregistered source"):
        bind_registry_claims(
            registry,
            {"claims": []},
            research_claims=[claim],
        )


def test_snapshot_manifest_binds_every_external_source(tmp_path: Path) -> None:
    _source_tree(tmp_path)
    manifest = build_source_snapshot_manifest(
        source_root=tmp_path,
        source_registry=_registry(),
        ticker="TEST",
        as_of_date="2026-08-10",
    )
    verification = verify_source_snapshot_manifest(manifest, source_root=tmp_path)

    assert manifest["all_sources_dispositioned"] is True
    assert verification["status"] == "pass"
    assert verification["source_count"] == 3
    assert verification["derived_source_count"] == 1
    assert manifest["contract_version"] == 2
    assert manifest["parser_version"] == "room16.source_snapshot_parser@2"
    sec = next(
        item
        for item in manifest["source_dispositions"]
        if item["source_type"] == "sec_filing"
    )
    assert sec["retrieved_at"]["status"] == "snapshot_capture_fallback"
    assert sec["published_at"] == {
        "value": None,
        "status": "unavailable_in_source",
    }
    assert sec["accepted_at"] == {
        "value": None,
        "status": "unavailable_in_source",
    }


def test_snapshot_manifest_fails_closed_for_unbound_source(tmp_path: Path) -> None:
    _source_tree(tmp_path)
    registry = _registry()
    registry.sources.append(
        SourceRegistryEntry(
            source_id="TEST_UNCAPTURED_IR",
            ticker="TEST",
            source_type="company_ir",
            url="https://example.invalid/missing",
            used_for=["guidance"],
        )
    )
    manifest = build_source_snapshot_manifest(
        source_root=tmp_path,
        source_registry=registry,
        ticker="TEST",
        as_of_date="2026-08-10",
    )
    verification = verify_source_snapshot_manifest(manifest, source_root=tmp_path)

    assert manifest["all_sources_dispositioned"] is False
    assert manifest["blocking_source_ids"] == ["TEST_UNCAPTURED_IR"]
    assert verification["status"] == "fail"


def test_snapshot_verifier_detects_changed_source_bytes(tmp_path: Path) -> None:
    _source_tree(tmp_path)
    manifest = build_source_snapshot_manifest(
        source_root=tmp_path,
        source_registry=_registry(),
        ticker="TEST",
        as_of_date="2026-08-10",
    )
    (tmp_path / "prices" / "TEST.csv").write_text("tampered", encoding="utf-8")

    verification = verify_source_snapshot_manifest(manifest, source_root=tmp_path)

    assert verification["status"] == "fail"
    assert any(
        failure.startswith("source_artifact_hash:")
        for failure in verification["blocking_failures"]
    )


def test_snapshot_manifest_extracts_sec_publication_and_acceptance_times(
    tmp_path: Path,
) -> None:
    _source_tree(tmp_path)
    filing = tmp_path / "sec" / "filing.json"
    filing.write_text(
        json.dumps(
            {
                "accession": "0000123456-26-000001",
                "filingDate": "2026-08-09",
                "acceptanceDateTime": "2026-08-09T16:04:05-04:00",
            }
        ),
        encoding="utf-8",
    )

    manifest = build_source_snapshot_manifest(
        source_root=tmp_path,
        source_registry=_registry(),
        ticker="TEST",
        as_of_date="2026-08-10",
        retrieved_at="2026-08-10T12:00:00+00:00",
    )
    sec = next(
        item
        for item in manifest["source_dispositions"]
        if item["source_type"] == "sec_filing"
    )

    assert sec["published_at"] == {
        "value": "2026-08-09",
        "status": "extracted_from_snapshot",
    }
    assert sec["accepted_at"] == {
        "value": "2026-08-09T16:04:05-04:00",
        "status": "extracted_from_snapshot",
    }


def test_snapshot_verifier_rejects_missing_provenance_metadata(tmp_path: Path) -> None:
    _source_tree(tmp_path)
    manifest = build_source_snapshot_manifest(
        source_root=tmp_path,
        source_registry=_registry(),
        ticker="TEST",
        as_of_date="2026-08-10",
    )
    manifest["source_dispositions"][0].pop("parser_version")

    verification = verify_source_snapshot_manifest(manifest, source_root=tmp_path)

    assert verification["status"] == "fail"
    assert any(
        failure.startswith("source_disposition_provenance:")
        for failure in verification["blocking_failures"]
    )
