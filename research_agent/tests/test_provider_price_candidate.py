import hashlib
import json

import pytest

from research_agent.sources.prices.provider_price_candidate import (
    ProviderPriceCandidateReceipt,
    load_provider_price_candidate,
)


def _candidate(tmp_path):
    series = tmp_path / "prices.csv"
    series.write_text(
        "date,close\n2025-01-02,100.0\n2025-01-03,101.0\n",
        encoding="utf-8",
    )
    receipt = ProviderPriceCandidateReceipt(
        created_at="2025-01-04T12:00:00+00:00",
        provider_id="test-provider",
        provider_dataset_id="test-total-return",
        ticker="TST",
        requested_start="2025-01-01",
        requested_end="2025-01-04",
        rows=2,
        first_date="2025-01-02",
        last_date="2025-01-03",
        series_basis="total_return_adjusted",
        cash_distributions_included=True,
        corporate_actions_included=True,
        data_file="prices.csv",
        data_sha256="sha256:" + hashlib.sha256(series.read_bytes()).hexdigest(),
        source_url="https://prices.example/eod",
        methodology_url="https://prices.example/methodology",
        license_url="https://prices.example/license",
        pricing_url="https://prices.example/pricing",
    )
    receipt_path = tmp_path / "provider_receipt.json"
    receipt_path.write_text(receipt.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return series, receipt_path


def test_provider_price_candidate_binds_exact_normalized_series(tmp_path):
    series, receipt_path = _candidate(tmp_path)

    receipt = load_provider_price_candidate(
        receipt_path,
        expected_series_path=series,
    )

    assert receipt.ticker == "TST"
    assert receipt.rows == 2
    assert receipt.live_activation_allowed is False
    assert receipt.rights_verification_status == "operator_evidence_still_required"


def test_provider_price_candidate_rejects_tampered_or_substituted_series(tmp_path):
    series, receipt_path = _candidate(tmp_path)
    substituted = tmp_path / "other.csv"
    substituted.write_text(series.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError, match="does not bind the supplied price series"):
        load_provider_price_candidate(receipt_path, expected_series_path=substituted)

    series.write_text("date,close\n2025-01-02,999.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="data hash does not match"):
        load_provider_price_candidate(receipt_path, expected_series_path=series)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("data_file", "../prices.csv", "safe relative filename"),
        ("rows", 3, "row count does not match"),
        ("first_date", "2025-01-01", "first_date does not match"),
        ("created_at", "2025-01-01T12:00:00+00:00", "predates its last observation"),
        ("methodology_url", "http://prices.example/methodology", "must use HTTPS"),
    ],
)
def test_provider_price_candidate_rejects_false_receipt_claims(tmp_path, field, value, message):
    series, receipt_path = _candidate(tmp_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload[field] = value
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_provider_price_candidate(receipt_path, expected_series_path=series)


def test_provider_price_candidate_rejects_unknown_fields_and_unordered_rows(tmp_path):
    series, receipt_path = _candidate(tmp_path)
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["unverified_claim"] = True
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_provider_price_candidate(receipt_path, expected_series_path=series)

    series, receipt_path = _candidate(tmp_path)
    series.write_text(
        "date,close\n2025-01-03,101.0\n2025-01-02,100.0\n",
        encoding="utf-8",
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["data_sha256"] = "sha256:" + hashlib.sha256(series.read_bytes()).hexdigest()
    receipt_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="not ordered by date"):
        load_provider_price_candidate(receipt_path, expected_series_path=series)
