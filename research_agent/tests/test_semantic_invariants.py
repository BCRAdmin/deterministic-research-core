from copy import deepcopy
from types import SimpleNamespace

from research_agent.quality.semantic_invariants import verify_semantic_invariants
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.run_pipeline import _material_topic_report_coverage


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
    assert report["semantic_integrity_passed"] is True
    assert report["internally_reviewable"] is True
    assert report["release_candidate"] is False
    assert report["release_allowed"] is False
    assert report["blocking_failures"] == []


def test_semantic_invariant_allows_source_bound_structural_dash_fact():
    fixture = _fixture()
    fixture["fact_ledger"]["claims"].append(
        {
            "metric": "operating_kpi_integration_costs_collection",
            "dimension": "currency",
            "display_unit": "USD",
            "currency": "USD",
            "period_kind": "duration",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "presentation_basis": "period_total",
            "row_metric": "integration_costs",
            "column_metric": "collection",
            "source_cell_status": "not_applicable_dash",
            "evidence_ids": ["EVIDENCE-001"],
            "claim_bound_evidence_ids": [],
            "value": 0.0,
            "source_value": 0.0,
            "source_scale": "million",
            "source_sign": 1,
        }
    )

    report = verify_semantic_invariants(**fixture)

    assert "fact_evidence_is_claim_bound" not in report["blocking_failures"]


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


def test_material_topic_propagation_requires_direct_topic_claim_not_rating_synthesis():
    direct = ResearchClaim(
        claim_id="TEST_CLAIM_001",
        section="Key Risks",
        claim_type="risk",
        agent="deterministic_content_generator",
        claim="The issuer disclosed a material regulatory order.",
        evidence_metrics=[],
        source_ids=["SEC_TEST_TOPIC_LEGAL_01"],
        confidence="high",
    )
    synthesis = ResearchClaim(
        claim_id="TEST_CLAIM_002",
        section="Final Rating & Action Plan",
        claim_type="rating",
        agent="deterministic_content_generator",
        claim="A decision synthesis rendered through the rating section.",
        evidence_metrics=[],
        source_ids=["SEC_TEST_TOPIC_LEGAL_01"],
        confidence="high",
    )

    result = _material_topic_report_coverage(
        markdown=(
            "# Report\n\nTEST_CLAIM_001 — The issuer disclosed a material "
            "regulatory order.\n"
        ),
        claims=[direct, synthesis],
        report_kind="full_research_report",
    )

    assert result["status"] == "pass"
    assert result["required_claim_count"] == 1
    assert result["dispositions"][0]["claim_id"] == "TEST_CLAIM_001"
