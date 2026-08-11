from copy import deepcopy
from types import SimpleNamespace

from research_agent.quality.semantic_invariants import verify_semantic_invariants


def _fixture():
    fact = {
        "metric": "revenue_ttm",
        "dimension": "currency",
        "display_unit": "USD",
        "currency": "USD",
        "period_kind": "trailing_twelve_months",
        "presentation_basis": "trailing_twelve_months",
    }
    claim = SimpleNamespace(
        claim_id="CLAIM-001",
        evidence_ids=["EVIDENCE-001"],
        source_ids=["SOURCE-001"],
    )
    evidence = SimpleNamespace(
        evidence_id="EVIDENCE-001",
        supports_claim_ids=["CLAIM-001"],
    )
    source = SimpleNamespace(
        source_id="SOURCE-001",
        claim_ids=["CLAIM-001"],
    )
    decision = SimpleNamespace(
        rating_permission=SimpleNamespace(
            permission_type="analytical",
            allowed_ratings=["Buy", "Hold"],
        ),
        calibration_mode="standardized_uncalibrated",
        decision_inputs=[
            SimpleNamespace(input_id="RISK-001")
        ],
    )
    event = SimpleNamespace(
        source_id="RISK-001",
        event_type="filing_legal_contingencies",
        content_complete=True,
        dependency_status="complete",
        report_disposition="included_main_report",
        report_disposition_reason="Current legal risk is visible.",
        materiality_rationale="Primary-source material legal exposure.",
    )
    return {
        "fact_ledger": {"claims": [fact]},
        "evidence_ledger": SimpleNamespace(evidence_items=[evidence]),
        "source_registry": SimpleNamespace(sources=[source]),
        "claims": [claim],
        "decision_packet": decision,
        "material_events": [event],
    }


def test_semantic_invariant_fixture_passes():
    report = verify_semantic_invariants(**_fixture())
    assert report["release_allowed"] is True
    assert report["blocking_failures"] == []


def test_semantic_invariant_negative_mutants_are_blocked():
    mutations = {
        "typed_fact_units": lambda fixture: fixture["fact_ledger"]["claims"][0].update(
            {"currency": None}
        ),
        "claim_evidence_edge_equality": lambda fixture: setattr(
            fixture["evidence_ledger"].evidence_items[0],
            "supports_claim_ids",
            [],
        ),
        "claim_source_edge_equality": lambda fixture: setattr(
            fixture["source_registry"].sources[0],
            "claim_ids",
            [],
        ),
        "material_event_state_consistent": lambda fixture: setattr(
            fixture["material_events"][0],
            "dependency_status",
            "missing_content",
        ),
        "rating_policy_not_singleton": lambda fixture: setattr(
            fixture["decision_packet"].rating_permission,
            "allowed_ratings",
            ["Hold"],
        ),
        "current_risk_decision_lineage": lambda fixture: setattr(
            fixture["decision_packet"],
            "decision_inputs",
            [],
        ),
    }

    for expected_failure, mutate in mutations.items():
        fixture = deepcopy(_fixture())
        mutate(fixture)
        report = verify_semantic_invariants(**fixture)
        assert report["release_allowed"] is False
        assert expected_failure in report["blocking_failures"]
