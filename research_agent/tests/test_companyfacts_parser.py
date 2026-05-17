from research_agent.sources.sec.companyfacts_parser import CompanyFactsParser
from research_agent.sources.sec.sec_fundamentals_builder import build_sec_fundamentals_from_companyfacts


FIXTURE_COMPANYFACTS = {
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {"val": 2_460_000_000, "fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-15", "start": "2025-02-01", "end": "2026-01-31", "accn": "0001441816-26-000010"},
                        {"val": 600_000_000, "fy": 2026, "fp": "Q1", "form": "10-Q", "filed": "2025-06-01", "start": "2025-02-01", "end": "2025-04-30", "accn": "q1"},
                        {"val": 610_000_000, "fy": 2026, "fp": "Q2", "form": "10-Q", "filed": "2025-09-01", "start": "2025-05-01", "end": "2025-07-31", "accn": "q2"},
                        {"val": 620_000_000, "fy": 2026, "fp": "Q3", "form": "10-Q", "filed": "2025-12-01", "start": "2025-08-01", "end": "2025-10-31", "accn": "q3"},
                        {"val": 630_000_000, "fy": 2026, "fp": "Q4", "form": "10-K", "filed": "2026-03-15", "start": "2025-11-01", "end": "2026-01-31", "accn": "q4"},
                    ]
                }
            },
            "NetCashProvidedByUsedInOperatingActivities": {
                "units": {"USD": [{"val": 100, "fy": 2026, "fp": "Q4", "form": "10-K", "filed": "2026-03-15", "end": "2026-01-31", "accn": "ocf"}]}
            },
            "PaymentsToAcquirePropertyPlantAndEquipment": {
                "units": {"USD": [{"val": 20, "fy": 2026, "fp": "Q4", "form": "10-K", "filed": "2026-03-15", "end": "2026-01-31", "accn": "capex"}]}
            },
        }
    }
}


def test_companyfacts_parser_extracts_revenue():
    parser = CompanyFactsParser("TEST", "0000000001", FIXTURE_COMPANYFACTS)

    fact = parser.latest_annual_fact("revenue")

    assert fact.value == 2_460_000_000
    assert fact.form == "10-K"
    assert fact.period == "FY2026_FY"


def test_sec_fact_generates_high_authority_evidence():
    parser = CompanyFactsParser("TEST", "0000000001", FIXTURE_COMPANYFACTS)
    fact = parser.latest_annual_fact("revenue")
    item = parser.to_evidence_item(fact)

    assert item.source_type == "sec_filing"
    assert item.authority_rank == 1
    assert "revenue" in item.supports_metrics
    assert "revenue_ttm" in item.supports_metrics


def test_sec_fundamentals_builder_returns_metrics_and_evidence():
    metrics, evidence = build_sec_fundamentals_from_companyfacts("TEST", "1", FIXTURE_COMPANYFACTS)

    assert metrics["revenue_latest_annual"] == 2_460_000_000
    assert metrics["quarterly"]["revenue"][-1] == 630_000_000
    assert any(item.source_type == "sec_filing" for item in evidence)
