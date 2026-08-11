import pytest

from research_agent.sources.sec.sec_material_events import (
    build_material_event_payload,
    classify_material_event_text,
    inventory_recent_8k_filings,
    select_material_event_filings,
    verify_material_event_payload,
)


def test_selects_results_8k_for_explicit_protocol_disposition():
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
    assert [row["primary_document"] for row in rows] == ["incident.htm", "results.htm"]
    inventory = inventory_recent_8k_filings(
        submissions,
        as_of_date="2026-08-05",
    )
    assert [row["disposition"] for row in inventory] == [
        "material_candidate",
        "material_candidate",
    ]


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


def test_explicit_results_item_cannot_be_reclassified_by_exhibit_keywords() -> None:
    event = classify_material_event_text(
        "Item 2.02 The company furnished quarterly financial results as Exhibit 99.1. "
        "The exhibit also discusses cybersecurity investments and unauthorized access risk.",
        items={"2.02"},
    )

    assert event is not None
    assert event[0] == "results_announcement"
    assert "Item 2.02" in event[2]


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
    assert payload["coverage_status"] == "complete"
    assert payload["all_candidates_dispositioned"] is True
    assert payload["filing_dispositions"][0]["disposition"] == "material_event"


def test_selects_and_dispositions_acquisition_and_debt_8k_items():
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "filingDate": ["2026-08-01", "2026-08-03"],
                "accessionNumber": [
                    "0000000001-26-000003",
                    "0000000001-26-000004",
                ],
                "primaryDocument": ["acquisition.htm", "debt.htm"],
                "items": ["2.01,9.01", "2.03"],
            }
        }
    }
    rows = select_material_event_filings(submissions, as_of_date="2026-08-05")
    payload = build_material_event_payload(
        ticker="TEST",
        cik="1",
        filings=[
            (rows[0], "<p>Item 2.01 The transaction closed following satisfaction of all conditions.</p>"),
            (rows[1], "<p>Item 2.03 The company entered into a new secured credit facility.</p>"),
        ],
        retrieved_at="2026-08-05T12:00:00Z",
    )

    assert [event["event_type"] for event in payload["events"]] == [
        "acquisition_or_disposition",
        "financing_obligation",
    ]
    assert len(payload["filing_dispositions"]) == 2


def test_material_event_payload_retains_excluded_and_non_material_dispositions():
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K", "8-K", "8-K", "8-K"],
                "filingDate": [
                    "2026-08-01",
                    "2026-08-02",
                    "2025-01-01",
                    "2026-08-07",
                ],
                "accessionNumber": [
                    "0000000001-26-000001",
                    "0000000001-26-000002",
                    "0000000001-25-000003",
                    "0000000001-26-000004",
                ],
                "primaryDocument": ["deal.htm", "results.htm", "old.htm", "future.htm"],
                "items": ["2.01", "2.02,9.01", "8.01", "8.01"],
            }
        }
    }
    inventory = inventory_recent_8k_filings(
        submissions,
        as_of_date="2026-08-05",
    )
    selected = select_material_event_filings(
        submissions,
        as_of_date="2026-08-05",
    )
    payload = build_material_event_payload(
        ticker="TEST",
        cik="1",
        filings=[
                (
                    selected[0],
                    "<p>Item 2.01 The company completed the material acquisition after all closing conditions were satisfied.</p>",
                ),
            (
                selected[1],
                "<p>Item 2.02 The company furnished quarterly financial results as Exhibit 99.1.</p>",
            ),
        ],
        retrieved_at="2026-08-05T12:00:00Z",
        candidate_inventory=inventory,
    )

    assert payload["all_candidates_dispositioned"] is True
    assert [
        item["disposition"] for item in payload["filing_dispositions"]
    ] == [
        "superseded",
        "material_event",
        "material_event",
        "non_material_with_reason",
    ]


def test_protocol_year_includes_filings_older_than_120_days() -> None:
    submissions = {
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "filingDate": ["2026-03-25", "2025-12-31"],
                "accessionNumber": [
                    "0000000001-26-000010",
                    "0000000001-25-000011",
                ],
                "primaryDocument": ["credit.htm", "old.htm"],
                "items": ["1.01,9.01", "1.01,9.01"],
            }
        }
    }

    inventory = inventory_recent_8k_filings(submissions, as_of_date="2026-08-10")

    assert inventory[0]["disposition"] == "excluded_outside_lookback"
    assert inventory[1]["disposition"] == "material_candidate"


def test_header_only_material_event_cannot_false_pass() -> None:
    filing = {
        "filing_date": "2026-05-13",
        "accession_number": "0001104659-26-059860",
        "primary_document": "leadership.htm",
        "items": "5.02,9.01",
    }

    with pytest.raises(ValueError, match="item-specific disposition"):
        build_material_event_payload(
            ticker="WM",
            cik="823768",
            filings=[
                (
                    filing,
                    "<p>Item 5.02 Departure of Directors or Certain Officers.</p>",
                )
            ],
            retrieved_at="2026-08-10T12:00:00Z",
            as_of_date="2026-08-10",
        )


def test_leadership_event_requires_and_retains_substantive_actions() -> None:
    filing = {
        "filing_date": "2026-05-13",
        "accession_number": "0001104659-26-059860",
        "primary_document": "leadership.htm",
        "items": "5.02,9.01",
    }
    payload = build_material_event_payload(
        ticker="WM",
        cik="823768",
        filings=[
            (
                filing,
                "<p>Item 5.02 Retirement of Mr. Rafael E. Carrasco. "
                "Mr. Carrasco announced his retirement after leading the Stericycle, Inc. integration. "
                "Promotion of Ms. Tara J. Hemmer. Ms. Hemmer was promoted to Executive Vice President and Chief "
                "Operating Officer. Mr. John J. Morris, Jr. resigned from the COO role and "
                "continues as President of the company.</p>",
            )
        ],
        retrieved_at="2026-08-10T12:00:00Z",
        as_of_date="2026-08-10",
    )

    assert verify_material_event_payload(payload)["status"] == "pass"
    summary = payload["events"][0]["summary"]
    assert all(name in summary for name in ("Carrasco", "Hemmer", "Morris"))
    assert all(action in summary.casefold() for action in ("retir", "promot", "resign"))
