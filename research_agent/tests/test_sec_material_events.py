from research_agent.sources.sec.sec_material_events import (
    build_material_event_payload,
    classify_material_event_text,
    select_material_event_filings,
)


def test_selects_material_8k_without_treating_results_as_incident():
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "filingDate": ["2026-07-16", "2026-07-28"],
                "accessionNumber": ["0000000001-26-000001", "0000000001-26-000002"],
                "primaryDocument": ["incident.htm", "results.htm"],
                "items": ["8.01", "2.02,9.01"],
            }
        }
    }
    rows = select_material_event_filings(submissions, as_of_date="2026-08-05")
    assert [row["primary_document"] for row in rows] == ["incident.htm"]


def test_classifies_cyber_disruption_and_later_recovery_separately():
    incident = classify_material_event_text(
        "The issuer identified unauthorized access in connection with a ransomware event. "
        "Production operations were temporarily suspended."
    )
    recovery = classify_material_event_text(
        "The issuer has resumed the majority of production and reported significant "
        "progress in restoring impacted operations."
    )
    assert incident is not None and incident[0] == "cyber_incident"
    assert recovery is not None and recovery[0] == "operational_recovery"


def test_builds_primary_source_event_payload():
    filing = {
        "filing_date": "2026-07-16",
        "accession_number": "0001628280-26-048466",
        "primary_document": "ko-20260716.htm",
        "items": "8.01",
    }
    payload = build_material_event_payload(
        ticker="KO",
        cik="21344",
        filings=[
            (
                filing,
                "<p>Unauthorized access occurred in connection with a ransomware event.</p>"
                "<p>Production operations were temporarily suspended.</p>",
            )
        ],
        retrieved_at="2026-07-16T20:00:00Z",
    )
    assert payload["events"][0]["event_type"] == "cyber_incident"
    assert payload["events"][0]["source_type"] == "sec_filing"
    assert payload["events"][0]["url"].endswith("/ko-20260716.htm")
