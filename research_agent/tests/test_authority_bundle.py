from __future__ import annotations

import json
from pathlib import Path

import pytest

from research_agent.integration.authority_bundle import (
    AUTHORITY_CONTRACT_ID,
    build_authority_bundle,
    verify_authority_bundle,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _packet_set(root: Path, ticker: str = "GENERIC", as_of: str = "2026-07-01") -> tuple[Path, Path]:
    packet_dir = root / "packets" / ticker / as_of
    registry_path = root / "packets" / f"{ticker}_{as_of}_source_registry.json"
    _write_json(
        packet_dir / "data_packet.json",
        {
            "ticker": ticker,
            "company_name": "Generic Company",
            "as_of_date": as_of,
            "price_basis": {
                "close": 100.0,
                "date": as_of,
                "currency": "USD",
                "source": "exchange",
            },
            "source_registry_id": f"{ticker}_{as_of}",
        },
    )
    _write_json(
        packet_dir / "metrics_packet.json",
        {
            "ticker": ticker,
            "as_of_date": as_of,
            "technical": {
                "indicator_date": as_of,
                "close": 100.0,
                "sma_50": 95.0,
                "sma_200": 90.0,
                "rsi_14": 55.0,
                "avg_volume_20": 1_000_000.0,
            },
            "fundamentals": {
                "fiscal_period": "TTM",
                "revenue_ttm": 1_000_000_000.0,
                "free_cash_flow_ttm": 100_000_000.0,
                "operating_cash_flow_ttm": 120_000_000.0,
                "capex_ttm": 20_000_000.0,
            },
            "valuation": {"price_to_fcf": 20.0},
        },
    )
    _write_json(
        packet_dir / "validation_report.json",
        {
            "ticker": ticker,
            "as_of_date": as_of,
            "has_blocking_errors": False,
            "issues": [],
        },
    )
    _write_json(
        packet_dir / "decision_packet.json",
        {
            "ticker": ticker,
            "as_of_date": as_of,
            "rating_permission": {
                "allowed_ratings": ["Hold", "Accumulate"],
                "blocked_ratings": ["Sell"],
                "preferred_rating": "Accumulate",
            },
        },
    )
    supported_metrics = [
        "close",
        "sma_50",
        "sma_200",
        "rsi_14",
        "avg_volume_20",
        "revenue_ttm",
        "free_cash_flow_ttm",
        "operating_cash_flow_ttm",
        "capex_ttm",
    ]
    _write_json(
        packet_dir / "evidence_ledger.json",
        {
            "ticker": ticker,
            "as_of_date": as_of,
            "evidence_items": [
                {
                    "evidence_id": f"{ticker}_PRIMARY",
                    "ticker": ticker,
                    "source_id": f"{ticker}_SEC",
                    "supports_metrics": supported_metrics[5:],
                },
                {
                    "evidence_id": f"{ticker}_PRICE",
                    "ticker": ticker,
                    "source_id": f"{ticker}_PRICE",
                    "supports_metrics": supported_metrics[:5],
                },
            ],
        },
    )
    _write_json(
        registry_path,
        {
            "registry_id": f"{ticker}_{as_of}",
            "sources": [
                {
                    "source_id": f"{ticker}_SEC",
                    "ticker": ticker,
                    "source_type": "sec_filing",
                    "authority_rank": 1,
                    "used_for": ["revenue", "operating_cash_flow", "capex", "free_cash_flow"],
                },
                {
                    "source_id": f"{ticker}_PRICE",
                    "ticker": ticker,
                    "source_type": "exchange_ohlcv",
                    "authority_rank": 2,
                    "used_for": ["price", "volume", "technical_indicators"],
                },
            ],
        },
    )
    return packet_dir, registry_path


@pytest.mark.parametrize("ticker", ["MEGA", "BANK", "INDUSTRIAL", "FOREIGN_ADR"])
def test_authority_bundle_is_ticker_agnostic(tmp_path: Path, ticker: str) -> None:
    packet_dir, registry_path = _packet_set(tmp_path, ticker=ticker)
    output_dir = tmp_path / "bundle" / ticker

    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=output_dir,
    )
    verification = verify_authority_bundle(output_dir)

    assert manifest["contract_id"] == AUTHORITY_CONTRACT_ID
    assert manifest["analysis_allowed"] is True
    assert verification["status"] == "pass"
    assert verification["analysis_allowed"] is True


def test_authority_bundle_fails_when_validation_blocks(tmp_path: Path) -> None:
    packet_dir, registry_path = _packet_set(tmp_path)
    validation_path = packet_dir / "validation_report.json"
    payload = json.loads(validation_path.read_text(encoding="utf-8"))
    payload["has_blocking_errors"] = True
    payload["issues"] = [{"severity": "error", "code": "TTM_SUM_MISMATCH"}]
    _write_json(validation_path, payload)

    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=tmp_path / "bundle",
    )

    assert manifest["analysis_allowed"] is False
    assert "deterministic_validation_clean" in manifest["blocking_failures"]


def test_authority_bundle_detects_tampering(tmp_path: Path) -> None:
    packet_dir, registry_path = _packet_set(tmp_path)
    output_dir = tmp_path / "bundle"
    build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=output_dir,
    )
    (output_dir / "metrics_packet.json").write_text("{}", encoding="utf-8")

    verification = verify_authority_bundle(output_dir)

    assert verification["status"] == "fail"
    assert "artifact_metrics_packet" in verification["blocking_failures"]


def test_authority_bundle_blocks_unregistered_evidence(tmp_path: Path) -> None:
    packet_dir, registry_path = _packet_set(tmp_path)
    ledger_path = packet_dir / "evidence_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["evidence_items"][0]["source_id"] = "UNREGISTERED"
    _write_json(ledger_path, ledger)

    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=tmp_path / "bundle",
    )

    assert manifest["analysis_allowed"] is False
    assert "evidence_sources_registered" in manifest["blocking_failures"]
