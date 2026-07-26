import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from research_agent.current import runner
from research_agent.current.runner import (
    CurrentResearchError,
    CurrentResearchRequest,
    run_current_research,
)
from research_agent.sources.bse.bse_provider import BseIssuer
from research_agent.sources.prices.price_provider_base import PriceProviderBase

REPO_ROOT = Path(__file__).resolve().parents[2]
SNOW_SOURCE_ROOT = (
    REPO_ROOT
    / "outputs"
    / "source_inputs"
    / "guardrail_coverage_batch_003_current_research"
)


class _FakeSec:
    def __init__(self, ticker="GENR"):
        self.ticker = ticker

    def get_company_tickers(self):
        return {
            "0": {
                "ticker": self.ticker,
                "cik_str": 123456,
                "title": "Generic Research Corp.",
            }
        }

    def get_companyfacts(self, cik):
        return {"cik": int(cik), "entityName": "Generic Research Corp.", "facts": {}}

    def get_submissions(self, cik):
        return {"filings": {"recent": {"filingDate": ["2026-07-20"]}}}


class _FakePrices(PriceProviderBase):
    source_type = "trusted_market_data_vendor"
    source_url = "https://prices.example/docs"

    def get_history(self, ticker, start, end):
        end_date = date.fromisoformat(end)
        rows = []
        for offset in range(260, -1, -1):
            day = end_date - timedelta(days=offset)
            rows.append(
                {
                    "date": day.isoformat(),
                    "open": 100.0,
                    "high": 102.0,
                    "low": 99.0,
                    "close": 101.0,
                    "volume": 1000,
                    "adjusted_close": 101.0,
                }
            )
        return pd.DataFrame(rows)


class _WeakPrices(_FakePrices):
    source_type = "yahoo_finance"


class _NoBse:
    def resolve(self, ticker):
        return None


class _FakeBse(_FakePrices):
    source_type = "exchange_ohlcv"
    source_url = "https://www.bse.hu/pages/company_profile/%24security/GENR"

    def resolve(self, ticker):
        if ticker != "GENR":
            return None
        return BseIssuer(
            ticker="GENR",
            company_name="Generic Hungarian Research Plc.",
            isin="HU0000000001",
            currency="HUF",
            issuer_id="1",
            security_id="2",
            profile_url=self.source_url,
        )

    def build_financial_payload(self, issuer, *, as_of_date, retrieved_at):
        return {
            "company_name": issuer.company_name,
            "source_id": "BSE_GENR_OFFICIAL_FINANCIALS",
            "source_type": "company_ir",
            "url": issuer.profile_url,
            "retrieved_at": retrieved_at,
            "metrics": [
                {
                    "metric_name": "revenue",
                    "value": 1_000_000_000,
                    "unit": "HUF",
                    "period": "FY2025",
                    "period_bucket": "annual",
                    "start_date": "2025-01-01",
                    "end_date": "2025-12-31",
                    "date": "2025-12-31",
                    "statement_type": "income_statement",
                }
            ],
        }


class _StoredSnowSec(_FakeSec):
    def __init__(self):
        super().__init__(ticker="SNOW")

    def get_companyfacts(self, cik):
        return json.loads(
            (SNOW_SOURCE_ROOT / "sec_companyfacts" / "SNOW.json").read_text(
                encoding="utf-8"
            )
        )


class _StoredSnowPrices(_FakePrices):
    def get_history(self, ticker, start, end):
        return pd.read_csv(SNOW_SOURCE_ROOT / "prices" / "SNOW.csv")


def _request(tmp_path, ticker="GENR"):
    return CurrentResearchRequest(
        ticker=ticker,
        as_of_date="2026-07-26",
        sec_user_agent="Room16 operator@example.com",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
        price_api_key="unused-in-test",
    )


def test_current_runner_stages_generic_inputs_and_returns_authority(monkeypatch, tmp_path):
    def fake_pipeline(ticker, as_of_date, config):
        authority = tmp_path / "outputs" / ticker / as_of_date / "authority_bundle"
        authority.mkdir(parents=True)
        (authority / "authority_manifest.json").write_text(
            json.dumps(
                {
                    "contract_id": "room16.research_authority_bundle",
                    "analysis_allowed": True,
                }
            ),
            encoding="utf-8",
        )
        assert config.packet_dir.startswith(str(tmp_path))
        assert config.price_source_type == "trusted_market_data_vendor"

    monkeypatch.setattr(runner, "run_research_pipeline", fake_pipeline)
    result = run_current_research(
        _request(tmp_path),
        price_provider=_FakePrices(),
        sec_client=_FakeSec(),
    )

    assert result["status"] == "authority_ready"
    assert result["ticker"] == "GENR"
    assert result["price_row_count"] == 261
    assert result["latest_filing_date"] == "2026-07-20"
    assert (tmp_path / "staging" / "GENR" / "2026-07-26" / "sources").exists()


def test_current_runner_rejects_unsupported_official_issuer(tmp_path):
    with pytest.raises(CurrentResearchError, match="official issuer adapters"):
        run_current_research(
            _request(tmp_path, ticker="OTHER"),
            price_provider=_FakePrices(),
            sec_client=_FakeSec(ticker="GENR"),
            bse_provider=_NoBse(),
        )


def test_current_runner_rejects_non_authority_price_provider(tmp_path):
    with pytest.raises(CurrentResearchError, match="not authority-grade"):
        run_current_research(
            _request(tmp_path),
            price_provider=_WeakPrices(),
            sec_client=_FakeSec(),
        )


def test_current_runner_builds_real_authority_bundle_from_generic_adapters(tmp_path):
    request = CurrentResearchRequest(
        ticker="SNOW",
        as_of_date="2026-05-17",
        sec_user_agent="Room16 operator@example.com",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
        ir_release_dir=str(SNOW_SOURCE_ROOT / "ir_releases"),
        price_api_key="unused-in-test",
    )

    result = run_current_research(
        request,
        price_provider=_StoredSnowPrices(),
        sec_client=_StoredSnowSec(),
    )

    manifest = json.loads(
        (
            tmp_path
            / "outputs"
            / "SNOW"
            / "2026-05-17"
            / "authority_bundle"
            / "authority_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == "authority_ready"
    assert result["analysis_allowed"] is True
    assert manifest["analysis_allowed"] is True
    assert manifest["contract_id"] == "room16.research_authority_bundle"


def test_current_runner_routes_public_bse_issuer_without_sec_or_api_key(
    monkeypatch,
    tmp_path,
):
    def fake_pipeline(ticker, as_of_date, config):
        assert ticker == "GENR"
        assert config.cik_records_path is None
        assert config.sec_companyfacts_path is None
        assert config.price_source_type == "exchange_ohlcv"
        assert config.price_currency == "HUF"
        assert Path(config.ir_release_dir, "GENR.json").exists()
        authority = tmp_path / "outputs" / ticker / as_of_date / "authority_bundle"
        authority.mkdir(parents=True)
        (authority / "authority_manifest.json").write_text(
            json.dumps(
                {
                    "contract_id": "room16.research_authority_bundle",
                    "analysis_allowed": True,
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(runner, "run_research_pipeline", fake_pipeline)
    request = CurrentResearchRequest(
        ticker="GENR",
        as_of_date="2026-07-26",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
    )
    result = run_current_research(request, bse_provider=_FakeBse())

    assert result["status"] == "authority_ready"
    assert result["jurisdiction"] == "HU"
    assert result["isin"] == "HU0000000001"
    assert result["price_provider"] == "bse"
