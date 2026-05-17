from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.sources.earnings.earnings_calendar import (
    earnings_event_to_evidence,
    is_event_risk_window,
    load_earnings_events,
    next_earnings_event,
)
from research_agent.sources.earnings.earnings_event import EarningsEvent
from research_agent.sources.sec.sec_fundamentals_builder import build_sec_fundamentals_from_companyfacts


def test_source_ingestion_can_create_evidence_ledger_from_sec_fixture():
    fixture = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {"val": 100, "fy": 2026, "fp": "FY", "form": "10-K", "filed": "2026-03-01", "end": "2026-01-31", "accn": "annual"}
                        ]
                    }
                }
            }
        }
    }
    _, evidence = build_sec_fundamentals_from_companyfacts("MDB", "1441816", fixture)
    ledger = EvidenceLedger(ticker="MDB", as_of_date="2026-05-01", evidence_items=evidence)

    assert ledger.has_primary_evidence_for_metric("revenue")
    assert ledger.find_by_metric("revenue_ttm")[0].source_type == "sec_filing"


def test_earnings_calendar_identifies_event_risk_window():
    events = [
        EarningsEvent(
            ticker="MDB",
            fiscal_period="Q1 FY2027",
            report_date="2026-05-08",
            timing="after_market",
            confirmed=True,
            source_id="earnings_calendar",
        )
    ]

    event = next_earnings_event("MDB", events, as_of_date="2026-05-01")

    assert event.report_date == "2026-05-08"
    assert is_event_risk_window(event, "2026-05-01")


def test_earnings_calendar_loads_csv_and_generates_evidence(tmp_path):
    path = tmp_path / "earnings.csv"
    path.write_text(
        "ticker,report_date,fiscal_period,timing,confirmed,source_id,source_type\n"
        "MDB,2026-05-08,Q1 FY2027,after_market,true,nasdaq_calendar,earnings_calendar\n",
        encoding="utf-8",
    )

    events = load_earnings_events(path)
    event = next_earnings_event("MDB", events, as_of_date="2026-05-01")
    evidence = earnings_event_to_evidence(event)

    assert event.confirmed
    assert evidence.claim_type == "event"
    assert "next_earnings_date" in evidence.supports_metrics


def test_unconfirmed_earnings_event_is_not_event_risk():
    event = EarningsEvent(
        ticker="MDB",
        fiscal_period="Q1 FY2027",
        report_date="2026-05-08",
        confirmed=False,
        source_id="unconfirmed_calendar",
    )

    assert not is_event_risk_window(event, "2026-05-01")
