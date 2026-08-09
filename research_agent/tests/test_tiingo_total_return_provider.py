import json

import pandas as pd
import pytest

from research_agent.sources.prices.tiingo_total_return_provider import (
    TiingoTotalReturnProvider,
    main,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _row(day="2026-07-24T00:00:00.000Z"):
    return {
        "date": day,
        "open": 100,
        "high": 102,
        "low": 99,
        "close": 101,
        "volume": 1000,
        "adjOpen": 95,
        "adjHigh": 97,
        "adjLow": 94,
        "adjClose": 96,
        "adjVolume": 1050,
        "divCash": 1.25,
        "splitFactor": 1,
    }


def test_tiingo_provider_stays_disabled_without_operator_token(monkeypatch):
    monkeypatch.delenv("TIINGO_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="remains disabled"):
        TiingoTotalReturnProvider.from_environment()
    with pytest.raises(ValueError, match="token is required"):
        TiingoTotalReturnProvider("")


def test_tiingo_provider_uses_header_auth_and_normalizes_total_return_fields(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return _Response([_row()])

    monkeypatch.setattr(
        "research_agent.sources.prices.tiingo_total_return_provider.urllib.request.urlopen",
        fake_urlopen,
    )
    provider = TiingoTotalReturnProvider(
        "test-secret-token",
        base_url="https://prices.example",
        timeout_seconds=17,
    )
    history = provider.get_history("mcd", "2026-07-01", "2026-07-24")
    total_return = provider.get_total_return_series("mcd", "2026-07-01", "2026-07-24")

    assert list(history.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adjusted_open",
        "adjusted_high",
        "adjusted_low",
        "adjusted_close",
        "adjusted_volume",
        "cash_distribution",
        "split_factor",
    ]
    assert history.iloc[0]["date"] == "2026-07-24"
    assert history.iloc[0]["adjusted_close"] == 96
    assert history.iloc[0]["cash_distribution"] == 1.25
    assert total_return.to_dict("records") == [{"date": "2026-07-24", "close": 96.0}]
    assert "/tiingo/daily/MCD/prices?" in captured["url"]
    assert "startDate=2026-07-01" in captured["url"]
    assert "endDate=2026-07-24" in captured["url"]
    assert "test-secret-token" not in captured["url"]
    assert captured["authorization"] == "Token test-secret-token"
    assert captured["timeout"] == 17


def test_tiingo_provider_rejects_bad_range_duplicates_and_invalid_adjustments(monkeypatch):
    provider = TiingoTotalReturnProvider("token", base_url="https://prices.example")
    with pytest.raises(ValueError, match="start must not be after end"):
        provider.get_history("MCD", "2026-07-25", "2026-07-24")
    with pytest.raises(ValueError, match="ticker is missing or invalid"):
        provider.get_history("SBX.MU", "2026-07-01", "2026-07-24")

    monkeypatch.setattr(
        "research_agent.sources.prices.tiingo_total_return_provider.urllib.request.urlopen",
        lambda request, timeout: _Response([_row(), _row()]),
    )
    with pytest.raises(RuntimeError, match="duplicate EOD date"):
        provider.get_history("MCD", "2026-07-01", "2026-07-24")

    invalid = _row()
    invalid["adjClose"] = 0
    monkeypatch.setattr(
        "research_agent.sources.prices.tiingo_total_return_provider.urllib.request.urlopen",
        lambda request, timeout: _Response([invalid]),
    )
    with pytest.raises(RuntimeError, match="nonpositive adjClose"):
        provider.get_history("MCD", "2026-07-01", "2026-07-24")

    inconsistent = _row()
    inconsistent["adjHigh"] = 90
    monkeypatch.setattr(
        "research_agent.sources.prices.tiingo_total_return_provider.urllib.request.urlopen",
        lambda request, timeout: _Response([inconsistent]),
    )
    with pytest.raises(RuntimeError, match="inconsistent adjusted high"):
        provider.get_history("MCD", "2026-07-01", "2026-07-24")


def test_tiingo_contract_metadata_never_claims_automatic_activation():
    metadata = TiingoTotalReturnProvider.outcome_contract_metadata()

    assert metadata == {
        "provider_id": "tiingo",
        "provider_dataset_id": "tiingo_eod_adjusted_crsp_methodology",
        "series_basis": "total_return_adjusted",
        "cash_distributions_included": True,
        "corporate_actions_included": True,
        "methodology_url": "https://www.tiingo.com/documentation/end-of-day",
        "license_url": "https://www.tiingo.com/documentation/general",
        "pricing_url": "https://www.tiingo.com/about/pricing",
        "activation_status": "operator_purchase_and_rights_evidence_required",
    }


def test_tiingo_probe_requires_explicit_paid_confirmation_without_network(
    tmp_path, monkeypatch, capsys
):
    target = tmp_path / "candidate"
    monkeypatch.setattr(
        "sys.argv",
        [
            "tiingo_total_return_provider",
            "--ticker",
            "MCD",
            "--start",
            "2025-07-31",
            "--end",
            "2026-08-07",
            "--output-dir",
            str(target),
        ],
    )

    assert main() == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["reason"] == "explicit_paid_provider_confirmation_required"
    assert not target.exists()


def test_tiingo_probe_writes_atomic_candidate_without_claiming_rights(
    tmp_path, monkeypatch, capsys
):
    class _Provider:
        def get_total_return_series(self, ticker, start, end):
            assert (ticker, start, end) == ("MCD", "2025-07-31", "2026-08-07")
            return pd.DataFrame(
                [
                    {"date": "2025-07-31", "close": 100.0},
                    {"date": "2026-08-07", "close": 110.0},
                ]
            )

    monkeypatch.setattr(
        TiingoTotalReturnProvider,
        "from_environment",
        classmethod(lambda cls: _Provider()),
    )
    target = tmp_path / "candidate"
    monkeypatch.setattr(
        "sys.argv",
        [
            "tiingo_total_return_provider",
            "--ticker",
            "MCD",
            "--start",
            "2025-07-31",
            "--end",
            "2026-08-07",
            "--output-dir",
            str(target),
            "--confirm-paid-provider",
        ],
    )

    assert main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "candidate_downloaded"
    assert payload["rows"] == 2
    assert payload["rights_verification_status"] == "operator_evidence_still_required"
    assert payload["live_activation_allowed"] is False
    assert payload["output_dir"] == str(target)
    assert (target / "prices.csv").read_text(encoding="utf-8") == (
        "date,close\n2025-07-31,100.0\n2026-08-07,110.0\n"
    )
    stored_receipt = json.loads((target / "provider_receipt.json").read_text())
    assert stored_receipt["schema_version"] == "room16.provider_price_candidate@1"
    assert stored_receipt["data_file"] == "prices.csv"
    assert stored_receipt["data_sha256"].startswith("sha256:")
    assert "output_dir" not in stored_receipt
    assert "token" not in json.dumps(stored_receipt).lower()


def test_tiingo_probe_failure_leaves_no_partial_candidate(tmp_path, monkeypatch, capsys):
    class _Provider:
        def get_total_return_series(self, ticker, start, end):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(
        TiingoTotalReturnProvider,
        "from_environment",
        classmethod(lambda cls: _Provider()),
    )
    target = tmp_path / "candidate"
    monkeypatch.setattr(
        "sys.argv",
        [
            "tiingo_total_return_provider",
            "--ticker",
            "MCD",
            "--start",
            "2025-07-31",
            "--end",
            "2026-08-07",
            "--output-dir",
            str(target),
            "--confirm-paid-provider",
        ],
    )

    assert main() == 2
    assert json.loads(capsys.readouterr().err)["error"] == "provider unavailable"
    assert not target.exists()
    assert not list(tmp_path.glob(".tiingo-candidate-building-*"))
