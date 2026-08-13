from copy import deepcopy
from types import SimpleNamespace

from research_agent.quality.quality_state_invariants import verify_quality_state


def _quality():
    return SimpleNamespace(
        publishable=False,
        status="Needs manual review",
        internal_research_quality_score=60,
        archetype_confidence=1.0,
        archetype_triggered_rules=["identity:WASTE_ENVIRONMENTAL_SERVICES"],
        business_model_kpi_coverage_complete=True,
        business_model_kpi_gap_count=0,
        missing_business_kpis=[],
        company_defined_fcf_mismatch_count=1,
    )


def _audit():
    return SimpleNamespace(
        has_blocking_errors=True,
        issues=[SimpleNamespace(code="COMPANY_DEFINED_FCF_MISMATCH")],
    )


def test_quality_state_consistent_fixture_passes():
    result = verify_quality_state(
        quality_report=_quality(), audit_report=_audit()
    )
    assert result["contract_version"] == 4
    assert result["internally_reviewable"] is True
    assert result["release_candidate"] is False
    assert result["release_allowed"] is False
    assert result["integrity_contract_passed"] is True
    assert result["report_publishable"] is False
    assert result["publication_allowed"] is False


def test_quality_state_negative_mutants_fail_atomically():
    mutants = {
        "blocking_audit_caps_internal_score": lambda q: setattr(
            q, "internal_research_quality_score", 90
        ),
        "archetype_confidence_is_explainable": lambda q: setattr(
            q, "archetype_triggered_rules", []
        ),
        "business_kpi_coverage_is_consistent": lambda q: setattr(
            q, "business_model_kpi_gap_count", 2
        ),
        "fcf_mismatch_count_matches_audit": lambda q: setattr(
            q, "company_defined_fcf_mismatch_count", 0
        ),
    }
    for check_id, mutate in mutants.items():
        quality = deepcopy(_quality())
        mutate(quality)
        report = verify_quality_state(
            quality_report=quality,
            audit_report=_audit(),
        )
        assert report["release_allowed"] is False
        assert check_id in report["blocking_failures"]


def test_quality_state_blocks_kpi_metadata_that_disagrees_with_canonical_audit():
    quality = _quality()
    quality.business_model_kpi_coverage_complete = False
    quality.business_model_kpi_gap_count = 1
    quality.missing_business_kpis = ["segment_growth"]
    audit = SimpleNamespace(
        has_blocking_errors=False,
        issues=[
            SimpleNamespace(
                code="BUSINESS_MODEL_KPI_COVERAGE_INCOMPLETE",
                message=(
                    "Required business-model KPIs are missing: segment_growth, "
                    "transaction_financing"
                ),
            )
        ],
    )

    report = verify_quality_state(quality_report=quality, audit_report=audit)

    assert "business_kpi_coverage_matches_canonical_audit" in report["blocking_failures"]
