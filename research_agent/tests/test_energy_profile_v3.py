from copy import deepcopy

import pytest

from research_agent.alpha_energy.v3 import (
    CAPEX_COMPARABILITY_CONTRACT_V3,
    CORE_SLOT_REGISTRY_V3,
    ENERGY_SEMANTIC_CONTRACT_V3,
    PERIOD_FRESHNESS_POLICY_V3,
    REVENUE_COMPARABILITY_CONTRACT_V3,
    evaluate_energy_v3_case,
    inline_xbrl_candidates_v3,
    select_metric_v3,
)
from research_agent.compiler_foundation.canonical import sha256_json


def _fact(
    concept,
    *,
    start="2026-04-01",
    end="2026-06-30",
    basis="STANDALONE_QUARTER",
    namespace="us-gaap",
    dimensions=False,
):
    body = {
        "namespace": namespace,
        "concept": concept,
        "label": concept,
        "value": "100",
        "unit": "USD",
        "start_or_null": start,
        "end": end,
        "filed": "2026-08-01",
        "form": "10-Q",
        "accession_or_null": "0000000001-26-000001",
        "dimensions_present": dimensions,
        "dimension_key": "SEGMENT" if dimensions else "NO_DIMENSIONS",
        "preliminary_duration_role": basis,
        "source_artifact_sha256": "a" * 64,
        "source_snapshot_sha256": "b" * 64,
    }
    digest = sha256_json(body)
    return {**body, "candidate_id": f"raw.{digest}", "candidate_sha256": digest}


def test_v3_selects_newer_admissible_ocf_without_v1_receipt_authority():
    q1 = _fact(
        "NetCashProvidedByUsedInOperatingActivities",
        start="2026-01-01",
        end="2026-03-31",
    )
    q2 = _fact(
        "NetCashProvidedByUsedInOperatingActivities",
        start="2026-01-01",
        end="2026-06-30",
        basis="YEAR_TO_DATE",
    )

    receipt = select_metric_v3("operating_cash_flow", [q1, q2], as_of="2026-09-03")

    assert receipt["selected_fact"]["candidate_id"] == q2["candidate_id"]
    assert receipt["v1_resolution_receipt_used"] is False
    assert receipt["selection_authority"] == "RAW_TYPED_FACT_EVIDENCE_ONLY"


def test_revenue_grade_b_is_visible_and_never_promoted_to_grade_a():
    receipt = select_metric_v3(
        "revenue",
        [_fact("RevenueFromContractWithCustomerExcludingAssessedTax")],
        as_of="2026-09-03",
    )

    assert receipt["counted"] == 1
    assert receipt["selected_fact"]["economic_scope_grade"] == "B"
    assert REVENUE_COMPARABILITY_CONTRACT_V3["grade_b_is_grade_a"] is False


@pytest.mark.parametrize(
    "concept",
    [
        "RefiningAndMarketingRevenue",
        "ExplorationAndProductionRevenue",
        "OilAndGasSalesRevenue",
        "NaturalGasProductionRevenue",
        "GrossProfit",
    ],
)
def test_revenue_components_and_label_neighbours_are_not_authority(concept):
    assert select_metric_v3("revenue", [_fact(concept)], as_of="2026-09-03")["status"] == "ABSENT"


def test_revenue_ytd_is_not_relabelled_as_quarter():
    receipt = select_metric_v3(
        "revenue",
        [_fact("Revenues", start="2026-01-01", basis="YEAR_TO_DATE")],
        as_of="2026-09-03",
    )
    assert receipt["counted"] == 0
    assert receipt["rejected_candidates"][0]["reason_codes"] == ["PERIOD_BASIS_NOT_ADMISSIBLE"]
    assert receipt["quarter_from_ytd_subtraction_used"] is False


def test_capex_family_is_explicitly_graded_and_label_similarity_is_not_authority():
    assert CAPEX_COMPARABILITY_CONTRACT_V3["label_similarity_is_authority"] is False
    receipt = select_metric_v3(
        "capital_expenditure",
        [
            _fact(
                "PaymentsToAcquireOilAndGasPropertyAndEquipment",
                start="2026-01-01",
                basis="YEAR_TO_DATE",
            )
        ],
        as_of="2026-09-03",
    )
    assert receipt["selected_fact"]["economic_scope_grade"] == "B"


def test_dimensioned_fact_is_rejected_even_for_an_allowed_concept():
    receipt = select_metric_v3("revenue", [_fact("Revenues", dimensions=True)], as_of="2026-09-03")
    assert receipt["status"] == "ABSENT"
    assert receipt["rejected_candidates"][0]["reason_codes"] == ["DIMENSIONED_OR_SEGMENT_FACT"]


def test_sole_successor_lifecycle_context_is_typed_not_treated_as_segment():
    fact = _fact("Revenues")
    fact["dimensions_present"] = True
    fact["dimension_key"] = "lifecycle"
    fact["dimensions"] = {"us-gaap:BusinessAcquisitionAxis": "issuer:SuccessorMember"}
    receipt = select_metric_v3("revenue", [fact], as_of="2026-09-03")
    assert receipt["counted"] == 1
    assert receipt["selected_fact"]["context_scope_grade"] == "B"
    assert receipt["selected_fact"]["context_scope"] == "LIFECYCLE_CONSOLIDATED_SUCCESSOR"


def test_predecessor_lifecycle_context_fails_closed():
    fact = _fact("Revenues")
    fact["dimensions_present"] = True
    fact["dimension_key"] = "lifecycle"
    fact["dimensions"] = {"us-gaap:BusinessAcquisitionAxis": "issuer:PredecessorMember"}
    receipt = select_metric_v3("revenue", [fact], as_of="2026-09-03")
    assert receipt["status"] == "ABSENT"


def test_debt_is_not_synthesized_from_current_and_noncurrent_components():
    receipt = select_metric_v3(
        "long_term_debt_measure",
        [_fact("LongTermDebtCurrent", start=None, basis="INSTANT")],
        as_of="2026-09-03",
    )
    assert receipt["status"] == "ABSENT"
    assert receipt["current_noncurrent_debt_summed"] is False


def test_input_reordering_does_not_change_selection_receipt():
    rows = [
        _fact("Revenues", start="2026-01-01", end="2026-03-31"),
        _fact("Revenues"),
    ]
    assert select_metric_v3("revenue", rows, as_of="2026-09-03") == select_metric_v3(
        "revenue", reversed(rows), as_of="2026-09-03"
    )


def test_ticker_is_not_a_semantic_input():
    assert "ticker" not in str(ENERGY_SEMANTIC_CONTRACT_V3["metrics"]).casefold()
    assert CORE_SLOT_REGISTRY_V3["subsector_assignment_by_ticker"] is False


def test_tampered_semantic_or_period_contract_is_rejected():
    semantic = deepcopy(ENERGY_SEMANTIC_CONTRACT_V3)
    semantic["contract_id"] = "ticker.allowlist"
    with pytest.raises(ValueError, match="SEMANTIC_CONTRACT_NOT_AUTHORIZED"):
        select_metric_v3("revenue", [], as_of="2026-09-03", semantic_contract=semantic)
    policy = deepcopy(PERIOD_FRESHNESS_POLICY_V3)
    policy["contract_id"] = "weakened"
    with pytest.raises(ValueError, match="PERIOD_POLICY_NOT_AUTHORIZED"):
        select_metric_v3("revenue", [], as_of="2026-09-03", period_policy=policy)


def test_inline_xbrl_adapter_resolves_opaque_usd_unit_and_preserves_lineage():
    html = """
    <html><body>
      <xbrli:unit id="opaque"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
      <xbrli:context id="q2"><xbrli:entity><xbrli:identifier>1</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <table><tr><td>Revenue</td><td><ix:nonFraction id="r" unitRef="opaque" contextRef="q2" name="us-gaap:Revenues" scale="6">123</ix:nonFraction></td></tr></table>
    </body></html>
    """
    facts = inline_xbrl_candidates_v3(
        html,
        source_artifact_sha256="a" * 64,
        source_payload_sha256="b" * 64,
        source_snapshot_sha256="c" * 64,
        filing_date="2026-08-01",
        form="10-Q",
        accession="0000000001-26-000001",
        source_id="SEC_INLINE_TEST",
    )
    assert len(facts) == 1
    assert facts[0]["unit"] == "USD"
    assert facts[0]["value"] == "123000000.0"
    assert facts[0]["presentation_evidence"] == "Revenue 123"
    assert select_metric_v3("revenue", facts, as_of="2026-09-03")["counted"] == 1


def test_inline_extension_concept_is_not_admitted_by_ticker_or_label():
    html = """
    <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
    <xbrli:context id="q"><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <ix:nonFraction unitRef="usd" contextRef="q" name="issuer:TotalRevenue" scale="0">10</ix:nonFraction>
    """
    facts = inline_xbrl_candidates_v3(
        html,
        source_artifact_sha256="a" * 64,
        source_payload_sha256="b" * 64,
        source_snapshot_sha256="c" * 64,
        filing_date="2026-08-01",
        form="10-Q",
        accession="0000000001-26-000001",
        source_id="SEC_INLINE_TEST",
    )
    assert facts == []


def test_case_evaluation_reports_dual_coverage_and_no_v1_authority():
    rows = [
        _fact("Revenues"),
        _fact("NetIncomeLoss"),
        _fact(
            "NetCashProvidedByUsedInOperatingActivities",
            start="2026-01-01",
            basis="YEAR_TO_DATE",
        ),
        _fact(
            "PaymentsToAcquirePropertyPlantAndEquipment",
            start="2026-01-01",
            basis="YEAR_TO_DATE",
        ),
        _fact("LongTermDebtNoncurrent", start=None, basis="INSTANT"),
    ]
    result = evaluate_energy_v3_case(ticker="GENR", as_of="2026-09-03", raw_typed_candidates=rows)
    assert result["coverage_percent"] == 100
    assert result["current_only_coverage_percent"] == 100
    assert result["v1_resolution_receipt_used"] is False
