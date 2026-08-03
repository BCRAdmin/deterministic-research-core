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
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.run_pipeline import (
    _load_ir_guidance_inputs,
    _sec_derived_fcf_used,
    build_data_packet,
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
        return {
            "cik": int(cik),
            "entityName": "Generic Research Corp.",
            "facts": {"us-gaap": {"Revenues": {"units": {}}}},
        }

    def get_submissions(self, cik):
        return {"filings": {"recent": {"filingDate": ["2026-07-20"]}}}


class _FakeSecWithRisks(_FakeSec):
    def get_companyfacts(self, cik):
        return {
            "cik": int(cik),
            "entityName": "Generic Research Corp.",
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {
                                    "val": 1_000_000,
                                    "form": "10-K",
                                    "filed": "2026-07-20",
                                    "start": "2026-04-01",
                                    "end": "2026-06-30",
                                    "accn": "0000123456-26-000001",
                                }
                            ]
                        }
                    }
                }
            },
        }

    def get_submissions(self, cik):
        return {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "filingDate": ["2026-07-20"],
                    "reportDate": ["2026-06-30"],
                    "accessionNumber": ["0000123456-26-000001"],
                    "primaryDocument": ["generic-20260630.htm"],
                }
            }
        }

    def get_filing_html(self, **kwargs):
        return """
        <div><strong>ITEM 1. B USINESS</strong></div>
        <p>The issuer develops secure software platforms and cloud services for business customers worldwide.</p>
        <div><strong>ITEM 1A. RIS K FACTORS</strong></div>
        <p><strong>Failure to execute our strategy could adversely affect business growth.</strong></p>
        <p>Supporting explanation for the disclosed issuer risk.</p>
        <div>Item 3. Market Risk</div>
        """


class _FakeSecWithQuarterAndAnnualRisks(_FakeSecWithRisks):
    def get_companyfacts(self, cik):
        payload = super().get_companyfacts(cik)
        row = payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
        row["form"] = "10-Q"
        row["accn"] = "0000123456-26-000010"
        return payload

    def get_submissions(self, cik):
        return {
            "filings": {
                "recent": {
                    "form": ["10-Q", "10-K"],
                    "filingDate": ["2026-07-20", "2026-02-20"],
                    "reportDate": ["2026-06-30", "2025-12-31"],
                    "accessionNumber": [
                        "0000123456-26-000010",
                        "0000123456-26-000001",
                    ],
                    "primaryDocument": ["quarter.htm", "annual.htm"],
                }
            }
        }

    def get_filing_html(self, **kwargs):
        if kwargs["accession_number"].endswith("000010"):
            return """
            <div><strong>ITEM 1A. RISK FACTORS</strong></div>
            <p><strong>Seasonality could adversely affect quarterly operating results.</strong></p>
            <div>Item 2. Unregistered Sales</div>
            """
        return """
        <div><strong>ITEM 1. BUSINESS</strong></div>
        <p>The issuer develops software products and subscription services for business customers worldwide.</p>
        <div><strong>ITEM 1A. RISK FACTORS</strong></div>
        <p><strong>Competition could adversely affect operating results.</strong></p>
        <p><strong>Cyberattacks may harm our services or reputation.</strong></p>
        <p><strong>Supply interruptions could increase costs or reduce revenue.</strong></p>
        <div>Item 2. Properties</div>
        """


class _FakeSecWithLaggingCompanyFacts(_FakeSecWithRisks):
    def get_companyfacts(self, cik):
        payload = super().get_companyfacts(cik)
        row = payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
        row["filed"] = "2026-04-20"
        row["accn"] = "0000123456-26-000000"
        return payload


class _FakeSecWithNewerResults8K(_FakeSecWithQuarterAndAnnualRisks):
    def get_submissions(self, cik):
        return {
            "filings": {
                "recent": {
                    "form": ["8-K", "10-Q", "10-K"],
                    "filingDate": [
                        "2026-07-24",
                        "2026-07-20",
                        "2026-02-20",
                    ],
                    "reportDate": [
                        "2026-07-24",
                        "2026-06-30",
                        "2025-12-31",
                    ],
                    "accessionNumber": [
                        "0000123456-26-000011",
                        "0000123456-26-000010",
                        "0000123456-26-000001",
                    ],
                    "primaryDocument": [
                        "results.htm",
                        "quarter.htm",
                        "annual.htm",
                    ],
                    "items": ["2.02,9.01", "", ""],
                }
            }
        }


class _FakeIfrsSec(_FakeSec):
    def get_companyfacts(self, cik):
        return {
            "cik": int(cik),
            "entityName": "Generic IFRS Issuer",
            "facts": {
                "ifrs-full": {
                    "Revenue": {
                        "units": {
                            "TWD": [
                                {
                                    "val": 1_000_000,
                                    "form": "20-F",
                                    "filed": "2026-04-30",
                                    "start": "2025-01-01",
                                    "end": "2025-12-31",
                                }
                            ]
                        }
                    }
                }
            },
        }


class _FakeUsGaapForeignIssuerSec(_FakeSec):
    def get_companyfacts(self, cik):
        return {
            "cik": int(cik),
            "entityName": "Generic US-GAAP Foreign Issuer",
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "CNY": [
                                {
                                    "val": 1_000_000,
                                    "form": "20-F",
                                    "filed": "2026-04-30",
                                    "start": "2025-04-01",
                                    "end": "2026-03-31",
                                },
                                {
                                    "val": 300_000,
                                    "form": "6-K",
                                    "filed": "2026-07-30",
                                    "start": "2026-04-01",
                                    "end": "2026-06-30",
                                },
                            ]
                        }
                    }
                }
            },
        }


class _FakeSuccessorWithoutStandardFacts(_FakeSec):
    def get_companyfacts(self, cik):
        return {
            "cik": int(cik),
            "entityName": "Generic Successor Holdings Corp.",
            "facts": {
                "ffd": {
                    "TtlFeeAmt": {
                        "units": {
                            "USD": [
                                {
                                    "val": 0,
                                    "form": "POSASR",
                                    "filed": "2026-07-01",
                                    "end": "2026-06-23",
                                }
                            ]
                        }
                    }
                }
            },
        }


class _FakeFinancialSec(_FakeSec):
    def get_submissions(self, cik):
        return {
            "sic": "6021",
            "sicDescription": "National Commercial Banks",
            "filings": {"recent": {"filingDate": ["2026-07-20"]}},
        }


class _FakeReitSec(_FakeSec):
    def get_submissions(self, cik):
        return {
            "sic": "6798",
            "sicDescription": "Real Estate Investment Trusts",
            "filings": {"recent": {"filingDate": ["2026-07-20"]}},
        }


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

    def build_news_payload(self, issuer, *, as_of_date, retrieved_at):
        return {
            "coverage_status": "partial",
            "checked_at": retrieved_at,
            "window_start": as_of_date,
            "window_end": as_of_date,
            "sources_checked": [issuer.profile_url],
            "events": [
                {
                    "date": as_of_date,
                    "headline": "BSE issuer profile describes the business activity",
                    "event_type": "business_context",
                    "material": True,
                    "source_id": "BSE_GENR_ISSUER_PROFILE",
                    "source_type": "company_ir",
                    "authority_rank": 1,
                    "url": issuer.profile_url,
                    "retrieved_at": retrieved_at,
                    "summary": "The issuer provides secure identity solutions.",
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

    def get_company_tickers(self):
        return {
            "0": {
                "ticker": "SNOW",
                "cik_str": 1640147,
                "title": "Snowflake Inc.",
            }
        }


class _StoredSnowPrices(_FakePrices):
    def get_history(self, ticker, start, end):
        return pd.read_csv(SNOW_SOURCE_ROOT / "prices" / "SNOW.csv")


class _StoredAaplSec(_FakeSec):
    def __init__(self):
        super().__init__(ticker="AAPL")

    def get_company_tickers(self):
        return {
            "0": {
                "ticker": "AAPL",
                "cik_str": 320193,
                "title": "Apple Inc.",
            }
        }

    def get_companyfacts(self, cik):
        return json.loads(
            (SNOW_SOURCE_ROOT / "sec_companyfacts" / "AAPL.json").read_text(
                encoding="utf-8"
            )
        )


class _StoredAaplPrices(_FakePrices):
    def get_history(self, ticker, start, end):
        return pd.read_csv(SNOW_SOURCE_ROOT / "prices" / "AAPL.csv")


def _request(tmp_path, ticker="GENR"):
    return CurrentResearchRequest(
        ticker=ticker,
        as_of_date="2026-07-26",
        jurisdiction="US",
        sec_user_agent="Room16 operator@example.com",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
        price_api_key="unused-in-test",
    )


def _assert_no_run_dirs(tmp_path):
    assert not (tmp_path / "staging").exists()
    assert not (tmp_path / "outputs").exists()


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


def test_current_runner_stages_sec_risks_for_the_existing_pipeline(monkeypatch, tmp_path):
    def fake_pipeline(ticker, as_of_date, config):
        risk_path = Path(config.sec_risk_factors_path)
        payload = json.loads(risk_path.read_text(encoding="utf-8"))
        assert payload["evidence_items"][0]["claim_type"] == "risk"
        context_path = Path(config.official_news_dir, "GENR_news.json")
        context = json.loads(context_path.read_text(encoding="utf-8"))
        assert context["events"][0]["event_type"] == "business_context"
        assert context["events"][0]["source_type"] == "sec_filing"
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
    result = run_current_research(
        _request(tmp_path),
        price_provider=_FakePrices(),
        sec_client=_FakeSecWithRisks(),
    )

    assert result["risk_source_status"] == "available"
    assert result["risk_filing_date"] == "2026-07-20"
    assert result["risk_factor_count"] == 1
    assert result["business_context_status"] == "available"
    assert result["business_context_filing_date"] == "2026-07-20"
    assert result["business_context_count"] == 1


def test_current_runner_supplements_sparse_quarterly_risks_from_annual_filing(
    monkeypatch,
    tmp_path,
):
    def fake_pipeline(ticker, as_of_date, config):
        payload = json.loads(
            Path(config.sec_risk_factors_path).read_text(encoding="utf-8")
        )
        assert [item["form"] for item in payload["filings"]] == ["10-Q", "10-K"]
        assert len(payload["evidence_items"]) == 4
        assert len({item["source_id"] for item in payload["evidence_items"]}) == 2
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
    result = run_current_research(
        _request(tmp_path),
        price_provider=_FakePrices(),
        sec_client=_FakeSecWithQuarterAndAnnualRisks(),
    )

    assert result["risk_source_status"] == "available"
    assert result["risk_filing_date"] == "2026-07-20"
    assert result["risk_factor_count"] == 4
    assert result["business_context_filing_date"] == "2026-02-20"


def test_current_runner_blocks_when_latest_sec_financials_are_not_in_companyfacts(
    tmp_path,
):
    with pytest.raises(CurrentResearchError, match="älteren Quartal"):
        run_current_research(
            _request(tmp_path),
            price_provider=_FakePrices(),
            sec_client=_FakeSecWithLaggingCompanyFacts(),
        )

    _assert_no_run_dirs(tmp_path)


def test_current_runner_blocks_newer_sec_results_announcement_before_pipeline(
    tmp_path,
):
    with pytest.raises(CurrentResearchError, match="Item 2.02"):
        run_current_research(
            _request(tmp_path),
            price_provider=_FakePrices(),
            sec_client=_FakeSecWithNewerResults8K(),
        )

    _assert_no_run_dirs(tmp_path)


def test_current_runner_rejects_unsupported_official_issuer(tmp_path):
    with pytest.raises(CurrentResearchError, match="offiziellen Marktadapter"):
        run_current_research(
            _request(tmp_path, ticker="OTHER").model_copy(
                update={"jurisdiction": None}
            ),
            price_provider=_FakePrices(),
            sec_client=_FakeSec(ticker="GENR"),
            bse_provider=_NoBse(),
        )
    _assert_no_run_dirs(tmp_path)


def test_current_runner_names_unsupported_sec_ifrs_profile_before_pipeline(tmp_path):
    with pytest.raises(CurrentResearchError, match="IFRS-Taxonomie mit 20-F"):
        run_current_research(
            _request(tmp_path),
            price_provider=_FakePrices(),
            sec_client=_FakeIfrsSec(),
        )

    _assert_no_run_dirs(tmp_path)


def test_current_runner_names_us_gaap_foreign_issuer_basis_gap_before_pipeline(
    tmp_path,
):
    with pytest.raises(
        CurrentResearchError,
        match=r"US-GAAP.*20-F/6-K.*ADS-Verhältnis.*SEC-FPI-Adapter",
    ):
        run_current_research(
            _request(tmp_path),
            price_provider=_FakePrices(),
            sec_client=_FakeUsGaapForeignIssuerSec(),
        )

    _assert_no_run_dirs(tmp_path)


def test_current_runner_names_successor_without_standard_facts_before_pipeline(
    tmp_path,
):
    with pytest.raises(
        CurrentResearchError,
        match="nicht unterstützten Taxonomien ffd.*Vorgänger-/Nachfolger-Kette",
    ):
        run_current_research(
            _request(tmp_path),
            price_provider=_FakePrices(),
            sec_client=_FakeSuccessorWithoutStandardFacts(),
        )

    _assert_no_run_dirs(tmp_path)


def test_current_runner_names_unsupported_financial_profile_before_pipeline(tmp_path):
    with pytest.raises(
        CurrentResearchError,
        match="National Commercial Banks.*SIC 6021.*Finanzbranchenprofil",
    ):
        run_current_research(
            _request(tmp_path),
            price_provider=_FakePrices(),
            sec_client=_FakeFinancialSec(),
        )

    _assert_no_run_dirs(tmp_path)


def test_current_runner_names_unsupported_reit_profile_before_pipeline(tmp_path):
    with pytest.raises(
        CurrentResearchError,
        match=r"Real Estate Investment Trusts.*SIC 6798.*REIT-Branchenprofil mit FFO/AFFO",
    ):
        run_current_research(
            _request(tmp_path),
            price_provider=_FakePrices(),
            sec_client=_FakeReitSec(),
        )

    _assert_no_run_dirs(tmp_path)


def test_current_runner_names_missing_sec_identity_before_adapter_lookup(tmp_path):
    request = CurrentResearchRequest(
        ticker="RIOT",
        as_of_date="2026-07-26",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
    )
    with pytest.raises(CurrentResearchError, match="ROOM16_SEC_USER_AGENT"):
        run_current_research(
            request,
            price_provider=_FakePrices(),
            bse_provider=_NoBse(),
        )
    _assert_no_run_dirs(tmp_path)


def test_auto_price_provider_uses_public_nasdaq_without_paid_key():
    request = CurrentResearchRequest(
        ticker="RIOT",
        as_of_date="2026-07-24",
        sec_user_agent="Room16 operator@example.com",
    )
    provider = runner._build_price_provider(request)
    assert provider.provider_id == "nasdaq"
    assert provider.source_type == "exchange_ohlcv"


def test_explicit_massive_provider_still_requires_key():
    request = CurrentResearchRequest(
        ticker="RIOT",
        as_of_date="2026-07-24",
        sec_user_agent="Room16 operator@example.com",
        price_provider="massive",
    )
    with pytest.raises(CurrentResearchError, match="API-Schlüssel für Massive/Polygon"):
        runner._build_price_provider(request)


def test_current_runner_rejects_non_authority_price_provider(tmp_path):
    with pytest.raises(CurrentResearchError, match="Quellenstandard nicht"):
        run_current_research(
            _request(tmp_path),
            price_provider=_WeakPrices(),
            sec_client=_FakeSec(),
        )
    _assert_no_run_dirs(tmp_path)


def test_current_runner_builds_real_authority_bundle_from_generic_adapters(tmp_path):
    request = CurrentResearchRequest(
        ticker="AAPL",
        as_of_date="2026-05-17",
        sec_user_agent="Room16 operator@example.com",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
        ir_release_dir=str(SNOW_SOURCE_ROOT / "ir_releases"),
        price_api_key="unused-in-test",
    )

    result = run_current_research(
        request,
        price_provider=_StoredAaplPrices(),
        sec_client=_StoredAaplSec(),
    )

    manifest = json.loads(
        (
            tmp_path
            / "outputs"
            / "AAPL"
            / "2026-05-17"
            / "authority_bundle"
            / "authority_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"] == "authority_ready"
    assert result["analysis_allowed"] is True
    assert manifest["analysis_allowed"] is True
    assert manifest["contract_id"] == "room16.research_authority_bundle"


def test_current_runner_rejects_ambiguous_stored_authority_inputs(tmp_path):
    request = CurrentResearchRequest(
        ticker="SNOW",
        as_of_date="2026-05-17",
        sec_user_agent="Room16 operator@example.com",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
        ir_release_dir=str(SNOW_SOURCE_ROOT / "ir_releases"),
        price_api_key="unused-in-test",
    )

    with pytest.raises(RuntimeError, match="evidence_ids_unique"):
        run_current_research(
            request,
            price_provider=_StoredSnowPrices(),
            sec_client=_StoredSnowSec(),
        )


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
        assert Path(config.official_news_dir, "GENR_news.json").exists()
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
        jurisdiction="HU",
        isin="HU0000000001",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
    )
    result = run_current_research(request, bse_provider=_FakeBse())

    assert result["status"] == "authority_ready"
    assert result["jurisdiction"] == "HU"
    assert result["isin"] == "HU0000000001"
    assert result["price_provider"] == "bse"
    assert not (
        tmp_path
        / "staging"
        / "GENR"
        / "2026-07-26"
        / "sources"
        / "sec_companyfacts"
    ).exists()


def test_current_runner_uses_resolved_jurisdiction_for_colliding_ticker(
    monkeypatch,
    tmp_path,
):
    def fake_pipeline(ticker, as_of_date, config):
        assert config.cik_records_path is None
        assert config.price_currency == "HUF"
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
        jurisdiction="HU",
        isin="HU0000000001",
        sec_user_agent="Room16 operator@example.com",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
    )

    result = run_current_research(
        request,
        sec_client=_FakeSec(ticker="GENR"),
        bse_provider=_FakeBse(),
    )

    assert result["jurisdiction"] == "HU"
    assert result["isin"] == "HU0000000001"


def test_current_runner_blocks_cross_market_ticker_ambiguity(tmp_path):
    request = CurrentResearchRequest(
        ticker="GENR",
        as_of_date="2026-07-26",
        sec_user_agent="Room16 operator@example.com",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
    )

    with pytest.raises(CurrentResearchError, match="mehrdeutig"):
        run_current_research(
            request,
            sec_client=_FakeSec(ticker="GENR"),
            bse_provider=_FakeBse(),
        )
    _assert_no_run_dirs(tmp_path)


def test_current_runner_blocks_resolver_isin_mismatch(tmp_path):
    request = CurrentResearchRequest(
        ticker="GENR",
        as_of_date="2026-07-26",
        jurisdiction="HU",
        isin="HU9999999999",
        staging_root=str(tmp_path / "staging"),
        output_root=str(tmp_path / "outputs"),
    )

    with pytest.raises(CurrentResearchError, match="widersprüchlichen Wertpapieridentität"):
        run_current_research(request, bse_provider=_FakeBse())
    _assert_no_run_dirs(tmp_path)


def test_data_packet_uses_explicit_exchange_price_currency():
    packet = build_data_packet(
        ticker="ANY",
        as_of_date="2026-07-24",
        prices=pd.DataFrame(
            [
                {
                    "date": "2026-07-23",
                    "open": 6900,
                    "high": 7000,
                    "low": 6850,
                    "close": 6950,
                    "volume": 8914,
                }
            ]
        ),
        fundamentals={
            "company_name": "ANY Security Printing Company",
            "latest_fiscal_year": "FY2025",
            "latest_quarter": "FY2026_Q1",
            "fiscal_year_end": "12-31",
        },
        news=[],
        price_currency="HUF",
    )

    assert packet.price_basis.currency == "HUF"
    assert packet.fiscal_context.latest_fiscal_year == "FY2025"
    assert packet.fiscal_context.latest_quarter == "FY2026_Q1"


def test_data_packet_exposes_validated_material_news_coverage():
    packet = build_data_packet(
        ticker="MCD",
        as_of_date="2026-07-24",
        prices=pd.DataFrame(
            [
                {
                    "date": "2026-07-24",
                    "open": 264,
                    "high": 266,
                    "low": 263,
                    "close": 264.76,
                    "volume": 100,
                }
            ]
        ),
        fundamentals={"company_name": "MCDONALDS CORP"},
        news=[
            {
                "event_type": "coverage_manifest",
                "status": "complete",
                "checked_at": "2026-07-27T00:00:00Z",
                "window_start": "2026-03-31",
                "window_end": "2026-07-24",
                "sources_checked": ["company IR"],
            },
            {
                "event_type": "strategy",
                "material": True,
                "date": "2026-06-01",
                "headline": "McDonald's > NEXT",
                "source_id": "MCD_IR_NEXT_2026",
                "source_type": "company_ir",
                "url": "https://example.com/next",
            },
        ],
    )

    assert packet.news_coverage.status == "complete"
    assert packet.news_coverage.window_end == "2026-07-24"
    assert packet.news_coverage.material_events[0].source_id == "MCD_IR_NEXT_2026"


def test_official_metrics_preserve_ttm_fiscal_period(tmp_path):
    release_dir = tmp_path / "official"
    release_dir.mkdir()
    (release_dir / "ANY.json").write_text(
        json.dumps(
            {
                "company_name": "ANY Security Printing Company",
                "source_id": "BSE_ANY_OFFICIAL_FINANCIALS",
                "source_type": "company_ir",
                "metrics": [
                    {
                        "metric_name": "revenue",
                        "value": 71_000_000_000,
                        "unit": "HUF",
                        "period": "FY2025",
                        "period_bucket": "annual",
                        "fiscal_year": 2025,
                        "fiscal_period": "FY",
                        "end_date": "2025-12-31",
                    },
                    {
                        "metric_name": "revenue",
                        "value": 17_000_000_000,
                        "unit": "HUF",
                        "period": "FY2026_Q1",
                        "period_bucket": "quarterly",
                        "fiscal_year": 2026,
                        "fiscal_period": "Q1",
                        "end_date": "2026-03-31",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    fundamentals, _evidence, _canonical = _load_ir_guidance_inputs(
        "ANY",
        str(release_dir),
    )

    assert fundamentals["latest_fiscal_year"] == "FY2025"
    assert fundamentals["latest_quarter"] == "FY2026_Q1"
    assert fundamentals["fiscal_period"] == "TTM through FY2026_Q1"
    assert fundamentals["fiscal_year_end"] == "12-31"


def test_sec_derived_fcf_is_recognized_from_deterministic_lineage():
    ledger = EvidenceLedger(
        ticker="KO",
        as_of_date="2026-07-28",
        evidence_items=[
            EvidenceItem(
                evidence_id="KO_DETERMINISTIC_FCF",
                ticker="KO",
                claim_type="financial_metric",
                source_id="ROOM16_KO_DETERMINISTIC_CALCULATIONS",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement="FCF equals SEC operating cash flow minus SEC capex.",
                supports_metrics=["free_cash_flow_ttm"],
                source_lineage=["SEC_0000021344_10Q"],
            )
        ],
    )

    assert _sec_derived_fcf_used(ledger) == 1
