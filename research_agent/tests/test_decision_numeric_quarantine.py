from research_agent.research_core.models.data_packet import (
    DataPacket,
    MaterialNewsEvent,
    NewsCoverage,
    PriceBasis,
)
from research_agent.run_pipeline import _decision_inputs


def _packet(*events: MaterialNewsEvent) -> DataPacket:
    return DataPacket(
        ticker="TEST",
        as_of_date="2026-08-14",
        price_basis=PriceBasis(
            close=100.0,
            date="2026-08-14",
            source="test",
        ),
        source_registry_id="TEST_2026-08-14",
        news_coverage=NewsCoverage(material_events=list(events)),
    )


def test_unresolved_operating_metric_cannot_enter_decision_inputs() -> None:
    event = MaterialNewsEvent(
        date="2026-08-14",
        headline="Issuer operating context",
        event_type="operating_kpi",
        source_id="UNRESOLVED_KPI",
        source_type="sec_filing",
        summary="An unresolved placeholder decreased 23 percent.",
        numeric_evidence=[
            {
                "metric_name": "operating_kpi_unmapped_statement_context",
                "value": -0.23,
                "direction": "decrease",
                "impact": "adverse",
                "mapping_status": "unmapped",
            }
        ],
    )

    assert _decision_inputs(_packet(event)) == []


def test_unresolved_legal_numbers_are_removed_but_named_risk_survives() -> None:
    event = MaterialNewsEvent(
        date="2026-08-14",
        headline="Issuer legal context",
        event_type="filing_legal_contingencies",
        source_id="LEGAL_RISK",
        source_type="sec_filing",
        summary=(
            "In March 2026, four class actions concerning Kirkland Signature "
            "tequila were filed under IEEPA, Case No. 26-cv-02734."
        ),
        numeric_evidence=[
            {
                "metric_name": "filing_legal_contingencies_unmapped_01",
                "value": 26.0,
                "mapping_status": "unresolved",
            }
        ],
    )

    decision_input = _decision_inputs(_packet(event))[0]

    assert "Kirkland Signature tequila" in decision_input["summary"]
    assert "IEEPA" in decision_input["summary"]
    assert not any(character.isdigit() for character in decision_input["summary"])
