"""Additive, offline-only Energy profile v2 semantic candidate.

This module deliberately does not alter the frozen Energy v1 projection.  It
provides a deterministic candidate evaluator for development evidence only;
there is no default cutover and no provider surface.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from research_agent.compiler_foundation.canonical import sha256_json

from .projection import classify_period_basis


PROFILE_STATUS = "CANDIDATE_NOT_FROZEN"

REVENUE_CONCEPT_FAMILY_V2: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_revenue_concept_family_v2_candidate",
    "contract_version": 2,
    "namespace": "us-gaap",
    "ordered_concepts": ["Revenues"],
    "equivalence_scope": "consolidated_total_company_revenues_exact",
    "removed_candidate_concepts": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": (
            "R8 independent matched-pair review found material non-equivalence across "
            "the captured Energy population; registry naming is not equivalence proof."
        )
    },
    "forbidden_concepts": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "RefiningAndMarketingRevenue",
        "ExplorationAndProductionRevenue",
        "OilAndGasRevenue",
        "OilAndGasSalesRevenue",
        "NaturalGasProductionRevenue",
        "GasGatheringTransportationMarketingAndProcessingRevenue",
        "GrossProfit",
        "GainLossOnSaleOfPropertyPlantEquipment",
        "ProceedsFromSaleOfPropertyPlantAndEquipment",
    ],
    "label_similarity_is_authority": False,
    "issuer_extension_concepts_allowed": False,
}

DEBT_COMPARABILITY_CONTRACT_V2: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_debt_comparability_v2_candidate",
    "contract_version": 2,
    "economic_slot_label": "long_term_debt_measure",
    "allowed_grades": ["A", "B"],
    "concepts": {
        "LongTermDebtNoncurrent": {
            "grade": "A",
            "scope": "noncurrent_long_term_debt",
            "leases_included": False,
        },
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent": {
            "grade": "B",
            "scope": "noncurrent_long_term_debt_and_finance_leases",
            "leases_included": True,
        },
        "LongTermDebtAndCapitalLeaseObligations": {
            "grade": "B",
            "scope": "reported_long_term_debt_and_capital_lease_obligations",
            "leases_included": True,
        },
    },
    "grade_c_counts_as_comparable": False,
    "current_noncurrent_components_summed": False,
    "exact_concept_identity_required": True,
}

MAPPING_REGISTRY_V2: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_mapping_registry_v2_candidate",
    "contract_version": 2,
    "profile_family": "Energy",
    "development_status": PROFILE_STATUS,
    "ticker_specific_rules": False,
    "manual_semantic_interventions": False,
    "metrics": {
        "revenue": REVENUE_CONCEPT_FAMILY_V2["ordered_concepts"],
        "net_income": ["NetIncomeLoss"],
        "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
        "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment"],
        "long_term_debt_measure": [
            "LongTermDebtNoncurrent",
            "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
            "LongTermDebtAndCapitalLeaseObligations",
        ],
    },
}

PERIOD_FRESHNESS_POLICY_V2: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_period_freshness_policy_v2_candidate",
    "contract_version": 2,
    "financial_current_max_age_days": 190,
    "financial_aging_max_age_days": 550,
    "accepted_availability": ["CURRENT_COMPARABLE", "AGING_BUT_VALID_DISCLOSED"],
    "historical_only_counts_as_resolved": False,
    "quarter_from_ytd_subtraction_allowed": False,
    "period_basis_relabeling_allowed": False,
    "incomparable_period_combination_allowed": False,
    "unit_conversion_allowed": False,
    "source_lineage_required": True,
    "duration_basis_policy": {
        "revenue": ["STANDALONE_QUARTER"],
        "net_income": ["STANDALONE_QUARTER"],
        "operating_cash_flow": ["YEAR_TO_DATE", "ANNUAL", "STANDALONE_QUARTER"],
        "capital_expenditure": ["YEAR_TO_DATE", "ANNUAL", "STANDALONE_QUARTER"],
    },
    "coverage_acceptance_semantics": "DUAL_THRESHOLD_REQUIRED",
    "usable_coverage_includes_aging_with_typed_disclosure": True,
    "current_only_coverage_report_required": True,
}

CORE_SLOT_REGISTRY_V2: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_core_slot_registry_v2_candidate",
    "contract_version": 2,
    "profile_family": "Energy",
    "profile_version": 2,
    "slots": [
        "revenue",
        "net_income",
        "operating_cash_flow",
        "capital_expenditure",
        "long_term_debt_measure",
    ],
    "removed_v1_slot": {
        "slot_id": "diluted_eps",
        "reason": (
            "Per-share denominator and duration selection produced only 30% development "
            "resolution despite raw concept presence in 10/10 issuers; long-term debt is a "
            "more comparable capital-structure input for capital-intensive Energy analysis."
        ),
    },
    "retained_difficult_slot": "capital_expenditure",
}

ENERGY_PROFILE_V2_CANDIDATE: dict[str, Any] = {
    "contract_id": "room16.alpha.energy_profile_v2_candidate",
    "contract_version": 2,
    "profile_family": "Energy",
    "profile_version": 2,
    "development_status": PROFILE_STATUS,
    "default_cutover": False,
    "release_authorized": False,
    "ticker_specific_rules": False,
    "manual_semantic_interventions": False,
    "acceptance_thresholds": {
        "development_median_min_percent": 80,
        "development_company_min_percent": 60,
    },
    "mapping_registry_v2_sha256": sha256_json(MAPPING_REGISTRY_V2),
    "period_freshness_policy_v2_sha256": sha256_json(PERIOD_FRESHNESS_POLICY_V2),
    "core_slot_registry_v2_sha256": sha256_json(CORE_SLOT_REGISTRY_V2),
    "metric_semantics_registry_binding": "room16.alpha.shared_concept_registry@2",
    "report_section_contract": "typed_availability_must_be_disclosed_with_period_and_age",
}


_DURATION_METRICS = {
    "revenue",
    "net_income",
    "operating_cash_flow",
    "capital_expenditure",
}
_BASIS_ORDER = {
    "revenue": {"STANDALONE_QUARTER": 0},
    "net_income": {"STANDALONE_QUARTER": 0},
    "operating_cash_flow": {"YEAR_TO_DATE": 0, "ANNUAL": 1, "STANDALONE_QUARTER": 2},
    "capital_expenditure": {"YEAR_TO_DATE": 0, "ANNUAL": 1, "STANDALONE_QUARTER": 2},
    "long_term_debt_measure": {"INSTANT": 0},
}


def registry_hashes() -> dict[str, str]:
    """Return the three independently bound candidate registry hashes."""

    return {
        "mapping_registry_v2_sha256": sha256_json(MAPPING_REGISTRY_V2),
        "period_freshness_policy_v2_sha256": sha256_json(PERIOD_FRESHNESS_POLICY_V2),
        "core_slot_registry_v2_sha256": sha256_json(CORE_SLOT_REGISTRY_V2),
        "energy_profile_v2_candidate_sha256": sha256_json(ENERGY_PROFILE_V2_CANDIDATE),
    }


def _normalise_fact(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise native and RFC-0011 frozen fact shapes without losing identity."""

    start = raw.get("start_or_null", raw.get("period_start"))
    end = raw.get("end", raw.get("period_end"))
    filed = raw.get("filed", raw.get("filed_date"))
    candidate_id = raw.get("candidate_id", raw.get("evidence_id"))
    namespace = raw.get("namespace") or "us-gaap"
    dimensions_present = bool(raw.get("dimensions_present", False))
    dimension_key = raw.get("dimension_key", "NO_DIMENSIONS")
    basis = raw.get("preliminary_duration_role")
    if not basis and end:
        basis = classify_period_basis(start, end)[0] if start else "INSTANT"
    return {
        "candidate_id": candidate_id,
        "candidate_sha256": raw.get("candidate_sha256"),
        "namespace": namespace,
        "concept": raw.get("concept"),
        "label": raw.get("label"),
        "value": raw.get("value", raw.get("numeric_value")),
        "unit": raw.get("unit"),
        "period_start": start,
        "period_end": end,
        "period_basis": basis,
        "filed": filed,
        "form": raw.get("form"),
        "accession": raw.get("accession_or_null"),
        "dimensions_present": dimensions_present,
        "dimension_key": dimension_key,
        "source_artifact_sha256": raw.get(
            "source_artifact_sha256", raw.get("source_entry_sha256")
        ),
        "source_snapshot_sha256": raw.get("source_snapshot_sha256"),
        "source_entry": raw.get("source_entry"),
    }


def _availability(as_of: str, period_end: str) -> tuple[str, int]:
    age = max(0, (date.fromisoformat(as_of) - date.fromisoformat(period_end)).days)
    if age <= PERIOD_FRESHNESS_POLICY_V2["financial_current_max_age_days"]:
        return "CURRENT_COMPARABLE", age
    if age <= PERIOD_FRESHNESS_POLICY_V2["financial_aging_max_age_days"]:
        return "AGING_BUT_VALID_DISCLOSED", age
    return "HISTORICAL_ONLY", age


def _rank(metric_id: str, row: dict[str, Any]) -> tuple[Any, ...]:
    availability_rank = {"CURRENT_COMPARABLE": 0, "AGING_BUT_VALID_DISCLOSED": 1}
    concept_order = {
        concept: index for index, concept in enumerate(MAPPING_REGISTRY_V2["metrics"][metric_id])
    }
    return (
        availability_rank[row["availability_status"]],
        -int(str(row["period_end"]).replace("-", "")),
        _BASIS_ORDER[metric_id].get(str(row["period_basis"]), 99),
        -int(str(row.get("filed") or "0000-00-00").replace("-", "")),
        concept_order[row["concept"]],
        str(row["candidate_id"]),
    )


def select_metric(
    metric_id: str,
    facts: Iterable[dict[str, Any]],
    *,
    as_of: str,
) -> dict[str, Any]:
    """Select one issuer-agnostic v2 fact or emit an explicit availability state."""

    if metric_id not in MAPPING_REGISTRY_V2["metrics"]:
        raise ValueError(f"UNKNOWN_ENERGY_V2_METRIC:{metric_id}")
    concepts = set(MAPPING_REGISTRY_V2["metrics"][metric_id])
    eligible: list[dict[str, Any]] = []
    historical: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for raw in facts:
        row = _normalise_fact(raw)
        if row["concept"] not in concepts:
            continue
        reasons = []
        if row["namespace"] != "us-gaap":
            reasons.append("NON_US_GAAP_NAMESPACE")
        if row["dimensions_present"] or row["dimension_key"] != "NO_DIMENSIONS":
            reasons.append("DIMENSIONED_OR_SEGMENT_FACT")
        if row["unit"] != "USD":
            reasons.append("UNIT_NOT_USD")
        if not row["period_end"]:
            reasons.append("PERIOD_END_MISSING")
        if row["filed"] and row["filed"] > as_of:
            reasons.append("FILED_AFTER_AS_OF")
        if metric_id in _DURATION_METRICS and row["period_basis"] not in _BASIS_ORDER[metric_id]:
            # Frozen adapters may preserve a duration value without its original start.
            # That evidence remains inspectable but cannot be silently relabelled.
            reasons.append("DURATION_BASIS_NOT_COMPARABLE")
        if metric_id == "long_term_debt_measure" and row["period_basis"] != "INSTANT":
            reasons.append("DEBT_NOT_INSTANT")
        if reasons:
            rejected.append({"candidate_id": row["candidate_id"], "reason_codes": reasons})
            continue
        status, age = _availability(as_of, str(row["period_end"]))
        candidate = {**row, "availability_status": status, "age_days": age}
        if metric_id == "long_term_debt_measure":
            comparison = DEBT_COMPARABILITY_CONTRACT_V2["concepts"][row["concept"]]
            candidate["comparability_grade"] = comparison["grade"]
            candidate["economic_scope"] = comparison["scope"]
        if status == "HISTORICAL_ONLY":
            historical.append(candidate)
        else:
            eligible.append(candidate)
    eligible.sort(key=lambda row: _rank(metric_id, row))
    historical.sort(key=lambda row: (row["age_days"], str(row["candidate_id"])))
    selected = eligible[0] if eligible else None
    if selected:
        status = selected["availability_status"]
    elif historical:
        status = "HISTORICAL_ONLY"
    else:
        status = "ABSENT"
    value = {
        "contract_id": "room16.alpha.energy_v2_metric_selection_receipt",
        "contract_version": 2,
        "metric_id": metric_id,
        "status": status,
        "counted": int(selected is not None),
        "selected_fact": selected,
        "best_historical_fact": historical[0] if historical else None,
        "eligible_candidate_count": len(eligible),
        "historical_candidate_count": len(historical),
        "rejected_candidates": rejected,
        "period_basis_relabelled": False,
        "quarter_from_ytd_subtraction_used": False,
        "unit_conversion_used": False,
    }
    if metric_id == "long_term_debt_measure":
        value["economic_slot_label"] = DEBT_COMPARABILITY_CONTRACT_V2[
            "economic_slot_label"
        ]
        value["allowed_comparability_grades"] = DEBT_COMPARABILITY_CONTRACT_V2[
            "allowed_grades"
        ]
    return {**value, "receipt_sha256": sha256_json(value)}


def evaluate_energy_v2_case(
    *,
    ticker: str,
    as_of: str,
    facts: Iterable[dict[str, Any]],
    v1_metrics: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate the additive v2 candidate against one already captured issuer."""

    materialised = tuple(facts)
    has_baseline_authority = v1_metrics is not None
    baseline = {
        str(row["metric_id"]): row for row in (v1_metrics or ()) if row.get("metric_id")
    }
    by_candidate = {
        str(row.get("candidate_id", row.get("evidence_id"))): _normalise_fact(row)
        for row in materialised
        if row.get("candidate_id", row.get("evidence_id"))
    }
    receipts = []
    for metric_id in CORE_SLOT_REGISTRY_V2["slots"]:
        preserved = baseline.get(metric_id)
        # The candidate changes only the revenue family and replaces EPS with debt.
        # Every already-resolved v1 core fact is therefore preserved byte-for-byte by
        # candidate identity rather than opportunistically reselected.
        if preserved is not None:
            fact = by_candidate.get(str(preserved.get("candidate_id")))
            value = {
                "contract_id": "room16.alpha.energy_v2_metric_selection_receipt",
                "contract_version": 2,
                "metric_id": metric_id,
                "status": (
                    "CURRENT_COMPARABLE"
                    if preserved.get("freshness_status") == "CURRENT"
                    else "AGING_BUT_VALID_DISCLOSED"
                ),
                "counted": 1,
                "selected_fact": fact,
                "best_historical_fact": None,
                "eligible_candidate_count": 1,
                "historical_candidate_count": 0,
                "rejected_candidates": [],
                "selection_authority": "ENERGY_V1_FROZEN_SELECTION_PRESERVED",
                "v1_resolution_receipt_sha256": preserved.get("resolution_receipt_sha256"),
                "period_basis_relabelled": False,
                "quarter_from_ytd_subtraction_used": False,
                "unit_conversion_used": False,
            }
            receipts.append({**value, "receipt_sha256": sha256_json(value)})
            continue
        candidate = select_metric(metric_id, materialised, as_of=as_of)
        if has_baseline_authority and metric_id in {
            "net_income",
            "operating_cash_flow",
            "capital_expenditure",
        }:
            candidate = {
                **candidate,
                "status": (
                    candidate["status"]
                    if candidate["status"] in {"HISTORICAL_ONLY", "ABSENT"}
                    else "V1_UNSUPPORTED_PRESERVED"
                ),
                "counted": 0,
                "selected_fact": None,
                "selection_authority": "ENERGY_V1_FROZEN_UNSUPPORTED_PRESERVED",
            }
            body = {key: value for key, value in candidate.items() if key != "receipt_sha256"}
            candidate["receipt_sha256"] = sha256_json(body)
        receipts.append(candidate)
    resolved = sum(row["counted"] for row in receipts)
    value = {
        "contract_id": "room16.alpha.energy_profile_v2_development_case",
        "contract_version": 2,
        "ticker": ticker,
        "as_of": as_of,
        "profile_version": 2,
        "development_status": PROFILE_STATUS,
        "provider_call_count": 0,
        "ticker_specific_rules": False,
        "resolved_slot_count": resolved,
        "slot_count": len(receipts),
        "coverage_percent": resolved * 100 // len(receipts),
        "slot_receipts": receipts,
    }
    return {**value, "case_sha256": sha256_json(value)}
