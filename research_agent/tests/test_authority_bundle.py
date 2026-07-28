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
                "free_cash_flow_formula": "cfo_minus_capex",
                "buybacks": 50_000_000.0,
                "dividends_paid": 75_000_000.0,
                "shareholder_distributions_ttm": 125_000_000.0,
                "shareholder_distributions_minus_fcf_ttm": 25_000_000.0,
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
            "analytical_rating_unconstrained": "Accumulate",
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
        "buybacks",
        "dividends_paid",
        "shareholder_distributions_ttm",
        "shareholder_distributions_minus_fcf_ttm",
        "price_to_fcf",
    ]
    metric_values = {
        "close": 100.0,
        "sma_50": 95.0,
        "sma_200": 90.0,
        "rsi_14": 55.0,
        "avg_volume_20": 1_000_000.0,
        "revenue_ttm": 1_000_000_000.0,
        "free_cash_flow_ttm": 100_000_000.0,
        "operating_cash_flow_ttm": 120_000_000.0,
        "capex_ttm": 20_000_000.0,
        "buybacks": 50_000_000.0,
        "dividends_paid": 75_000_000.0,
        "shareholder_distributions_ttm": 125_000_000.0,
        "shareholder_distributions_minus_fcf_ttm": 25_000_000.0,
        "price_to_fcf": 20.0,
    }
    _write_json(
        packet_dir / "evidence_ledger.json",
        {
            "ticker": ticker,
            "as_of_date": as_of,
            "evidence_items": [
                {
                    "evidence_id": f"{ticker}_{metric.upper()}",
                    "ticker": ticker,
                    "source_id": (
                        f"{ticker}_PRICE"
                        if metric in supported_metrics[:5]
                        else f"{ticker}_SEC"
                    ),
                    "supports_metrics": [metric],
                    "value": metric_values[metric],
                    "normalized_value": metric_values[metric],
                    "formula_id": "deterministic_test_fixture",
                    "formula_operands": {"input": metric_values[metric]},
                    "date": as_of,
                    "period": (
                        "daily_history"
                        if metric in supported_metrics[:5]
                        else "TTM"
                    ),
                }
                for metric in supported_metrics
            ],
        },
    )
    _write_json(
        packet_dir / "fact_ledger.json",
        {
            "contract_id": "room16-canonical-fact-ledger",
            "contract_version": 1,
            "ticker": ticker,
            "report_asof": as_of,
            "claims": [{"claim_id": f"{ticker}_FACT_CLOSE"}],
            "sources": [],
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


def test_authority_bundle_blocks_stale_price_basis(tmp_path: Path) -> None:
    packet_dir, registry_path = _packet_set(
        tmp_path,
        as_of="2026-07-27",
    )
    data_path = packet_dir / "data_packet.json"
    data_packet = json.loads(data_path.read_text(encoding="utf-8"))
    data_packet["price_basis"]["date"] = "2026-01-02"
    _write_json(data_path, data_packet)

    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=tmp_path / "bundle",
    )

    assert manifest["analysis_allowed"] is False
    assert "price_basis_current_for_analysis" in manifest["blocking_failures"]


def test_authority_bundle_blocks_when_fact_ledger_is_missing(tmp_path: Path) -> None:
    packet_dir, registry_path = _packet_set(tmp_path)
    (packet_dir / "fact_ledger.json").unlink()

    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=tmp_path / "bundle",
    )

    assert manifest["analysis_allowed"] is False
    assert "canonical_fact_ledger_present" in manifest["blocking_failures"]


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


def test_authority_bundle_carries_and_verifies_fact_ledger(tmp_path: Path) -> None:
    packet_dir, registry_path = _packet_set(tmp_path)
    fact_ledger_path = tmp_path / "fact_ledger.json"
    _write_json(
        fact_ledger_path,
        {
            "ticker": "GENERIC",
            "report_asof": "2026-07-01",
            "claims": [{"claim_id": "GENERIC_FACT_CLOSE"}],
            "sources": [],
        },
    )
    output_dir = tmp_path / "bundle"

    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        fact_ledger_path=fact_ledger_path,
        output_dir=output_dir,
    )
    verification = verify_authority_bundle(output_dir)

    assert manifest["artifacts"]["fact_ledger"]["path"] == "fact_ledger.json"
    assert verification["status"] == "pass"


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


def test_authority_bundle_blocks_material_metric_value_mismatch(
    tmp_path: Path,
) -> None:
    packet_dir, registry_path = _packet_set(tmp_path)
    ledger_path = packet_dir / "evidence_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    revenue = next(
        item
        for item in ledger["evidence_items"]
        if item["supports_metrics"] == ["revenue_ttm"]
    )
    revenue["value"] = 999_000_000.0
    revenue["normalized_value"] = 999_000_000.0
    _write_json(ledger_path, ledger)

    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=tmp_path / "bundle",
    )

    assert manifest["analysis_allowed"] is False
    assert "material_metrics_evidence_mapped" in manifest["blocking_failures"]
    check = next(
        item
        for item in manifest["checks"]
        if item["check_id"] == "material_metrics_evidence_mapped"
    )
    assert check["detail"] == "revenue_ttm"

    revenue["value"] = 1_000_000_000.0
    revenue["normalized_value"] = None
    revenue["formula_operands"] = {}
    revenue["date"] = None
    revenue["period"] = None
    _write_json(ledger_path, ledger)
    manifest = build_authority_bundle(
        packet_dir=packet_dir,
        source_registry_path=registry_path,
        output_dir=tmp_path / "formula_only_bundle",
    )
    assert "material_metrics_evidence_mapped" in manifest["blocking_failures"]
