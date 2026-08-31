from __future__ import annotations

from copy import deepcopy

import pytest

from research_agent.alpha_energy.v2 import (
    CORE_SLOT_REGISTRY_V2,
    ENERGY_PROFILE_V2_CANDIDATE,
    MAPPING_REGISTRY_V2,
    PERIOD_FRESHNESS_POLICY_V2,
    REVENUE_CONCEPT_FAMILY_V2,
    evaluate_energy_v2_case,
    registry_hashes,
    select_metric,
)
from research_agent.compiler_foundation.canonical import sha256_json


AS_OF = "2026-08-31"


def _fact(
    concept: str,
    *,
    candidate_id: str | None = None,
    start: str | None = "2026-04-01",
    end: str = "2026-06-30",
    basis: str = "STANDALONE_QUARTER",
    filed: str = "2026-08-05",
    dimensions: bool = False,
    namespace: str = "us-gaap",
    unit: str = "USD",
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id or f"raw.{concept}",
        "candidate_sha256": "a" * 64,
        "namespace": namespace,
        "concept": concept,
        "label": concept,
        "value": "100",
        "unit": unit,
        "start_or_null": start,
        "end": end,
        "preliminary_duration_role": basis,
        "filed": filed,
        "form": "10-Q",
        "accession_or_null": "0000000000-26-000001",
        "dimensions_present": dimensions,
        "dimension_key": "SEGMENT" if dimensions else "NO_DIMENSIONS",
        "source_artifact_sha256": "b" * 64,
        "source_snapshot_sha256": "c" * 64,
    }


def _complete_case() -> list[dict[str, object]]:
    return [
        _fact("RevenueFromContractWithCustomerExcludingAssessedTax"),
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
        _fact(
            "LongTermDebtAndCapitalLeaseObligations",
            start=None,
            basis="INSTANT",
        ),
    ]


def test_v2_is_additive_candidate_with_no_default_cutover() -> None:
    assert ENERGY_PROFILE_V2_CANDIDATE["profile_version"] == 2
    assert ENERGY_PROFILE_V2_CANDIDATE["development_status"] == "CANDIDATE_NOT_FROZEN"
    assert ENERGY_PROFILE_V2_CANDIDATE["default_cutover"] is False
    assert ENERGY_PROFILE_V2_CANDIDATE["release_authorized"] is False


def test_threshold_is_not_lowered() -> None:
    assert ENERGY_PROFILE_V2_CANDIDATE["acceptance_thresholds"] == {
        "development_median_min_percent": 80,
        "development_company_min_percent": 60,
    }


def test_registry_hashes_bind_canonical_documents() -> None:
    hashes = registry_hashes()
    assert hashes["mapping_registry_v2_sha256"] == sha256_json(MAPPING_REGISTRY_V2)
    assert hashes["period_freshness_policy_v2_sha256"] == sha256_json(
        PERIOD_FRESHNESS_POLICY_V2
    )
    assert hashes["core_slot_registry_v2_sha256"] == sha256_json(CORE_SLOT_REGISTRY_V2)


def test_revenue_family_accepts_proven_ex_tax_total() -> None:
    receipt = select_metric(
        "revenue",
        [_fact("RevenueFromContractWithCustomerExcludingAssessedTax")],
        as_of=AS_OF,
    )
    assert receipt["status"] == "CURRENT_COMPARABLE"
    assert receipt["selected_fact"]["concept"] == (
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    )


@pytest.mark.parametrize(
    "concept",
    REVENUE_CONCEPT_FAMILY_V2["forbidden_concepts"],
)
def test_revenue_negative_controls_are_not_mapped(concept: str) -> None:
    receipt = select_metric("revenue", [_fact(concept)], as_of=AS_OF)
    assert receipt["status"] == "ABSENT"
    assert receipt["counted"] == 0


def test_segment_revenue_is_rejected_even_for_allowed_concept() -> None:
    receipt = select_metric(
        "revenue",
        [_fact("RevenueFromContractWithCustomerExcludingAssessedTax", dimensions=True)],
        as_of=AS_OF,
    )
    assert receipt["status"] == "ABSENT"
    assert receipt["rejected_candidates"][0]["reason_codes"] == [
        "DIMENSIONED_OR_SEGMENT_FACT"
    ]


def test_stale_capex_remains_historical_and_does_not_count() -> None:
    receipt = select_metric(
        "capital_expenditure",
        [
            _fact(
                "PaymentsToAcquirePropertyPlantAndEquipment",
                start="2020-01-01",
                end="2020-09-30",
                basis="YEAR_TO_DATE",
                filed="2020-11-01",
            )
        ],
        as_of=AS_OF,
    )
    assert receipt["status"] == "HISTORICAL_ONLY"
    assert receipt["counted"] == 0
    assert receipt["selected_fact"] is None


def test_aging_capex_is_typed_and_not_relabelled_current() -> None:
    receipt = select_metric(
        "capital_expenditure",
        [
            _fact(
                "PaymentsToAcquirePropertyPlantAndEquipment",
                start="2025-01-01",
                end="2025-09-30",
                basis="YEAR_TO_DATE",
                filed="2025-11-01",
            )
        ],
        as_of=AS_OF,
    )
    assert receipt["status"] == "AGING_BUT_VALID_DISCLOSED"
    assert receipt["selected_fact"]["availability_status"] == "AGING_BUT_VALID_DISCLOSED"
    assert receipt["period_basis_relabelled"] is False


def test_quarter_from_ytd_is_never_synthesized() -> None:
    receipt = select_metric(
        "capital_expenditure",
        [
            _fact(
                "PaymentsToAcquirePropertyPlantAndEquipment",
                start="2026-01-01",
                basis="YEAR_TO_DATE",
            )
        ],
        as_of=AS_OF,
    )
    assert receipt["selected_fact"]["period_basis"] == "YEAR_TO_DATE"
    assert receipt["quarter_from_ytd_subtraction_used"] is False


def test_long_term_debt_family_preserves_exact_concept() -> None:
    receipt = select_metric(
        "long_term_debt_and_leases",
        [
            _fact(
                "LongTermDebtNoncurrent",
                start=None,
                basis="INSTANT",
            )
        ],
        as_of=AS_OF,
    )
    assert receipt["counted"] == 1
    assert receipt["selected_fact"]["concept"] == "LongTermDebtNoncurrent"


def test_selection_is_deterministic_under_input_reordering() -> None:
    rows = [
        _fact("Revenues", candidate_id="raw.z"),
        _fact(
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            candidate_id="raw.a",
        ),
    ]
    left = select_metric("revenue", rows, as_of=AS_OF)
    right = select_metric("revenue", reversed(rows), as_of=AS_OF)
    assert left == right
    assert left["selected_fact"]["concept"] == "Revenues"


def test_selected_fact_preserves_lineage() -> None:
    source = _fact("Revenues")
    receipt = select_metric("revenue", [source], as_of=AS_OF)
    selected = receipt["selected_fact"]
    assert selected["candidate_id"] == source["candidate_id"]
    assert selected["source_artifact_sha256"] == source["source_artifact_sha256"]
    assert selected["source_snapshot_sha256"] == source["source_snapshot_sha256"]
    assert selected["accession"] == source["accession_or_null"]


def test_profile_redesign_retains_capex_and_replaces_eps_with_debt() -> None:
    assert CORE_SLOT_REGISTRY_V2["retained_difficult_slot"] == "capital_expenditure"
    assert "diluted_eps" not in CORE_SLOT_REGISTRY_V2["slots"]
    assert "long_term_debt_and_leases" in CORE_SLOT_REGISTRY_V2["slots"]


def test_complete_candidate_case_is_five_of_five() -> None:
    result = evaluate_energy_v2_case(
        ticker="ENE",
        as_of=AS_OF,
        facts=_complete_case(),
    )
    assert result["provider_call_count"] == 0
    assert result["coverage_percent"] == 100
    assert result["ticker_specific_rules"] is False


def test_ticker_does_not_change_semantic_result() -> None:
    facts = _complete_case()
    first = evaluate_energy_v2_case(ticker="AAA", as_of=AS_OF, facts=facts)
    second = evaluate_energy_v2_case(ticker="BBB", as_of=AS_OF, facts=deepcopy(facts))
    first.pop("ticker"); first.pop("case_sha256")
    second.pop("ticker"); second.pop("case_sha256")
    assert first == second


def test_frozen_v1_selection_is_preserved_for_unchanged_slot() -> None:
    fact = _fact("NetIncomeLoss", candidate_id="raw.frozen")
    result = evaluate_energy_v2_case(
        ticker="ENE",
        as_of=AS_OF,
        facts=[fact],
        v1_metrics=[
            {
                "metric_id": "net_income",
                "candidate_id": "raw.frozen",
                "freshness_status": "CURRENT",
                "resolution_receipt_sha256": "d" * 64,
            }
        ],
    )
    receipt = next(row for row in result["slot_receipts"] if row["metric_id"] == "net_income")
    assert receipt["counted"] == 1
    assert receipt["selected_fact"]["candidate_id"] == "raw.frozen"
    assert receipt["selection_authority"] == "ENERGY_V1_FROZEN_SELECTION_PRESERVED"
