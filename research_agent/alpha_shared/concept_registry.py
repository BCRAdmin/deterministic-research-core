"""Semantic concept authority for the RFC-0011 shared successor."""

from __future__ import annotations

from research_agent.compiler_foundation.canonical import sha256_json


def _candidate(
    concept: str,
    *,
    semantic_role: str,
    equivalence_class: str,
    aggregation_role: str,
    formula_eligibility: tuple[str, ...] = (),
    forbidden_uses: tuple[str, ...] = (),
    allowed_archetype_profiles: tuple[str, ...] = ("generic", "saas", "reit", "bank", "energy"),
) -> dict[str, object]:
    return {
        "concept": concept,
        "semantic_role": semantic_role,
        "equivalence_class": equivalence_class,
        "aggregation_role": aggregation_role,
        "formula_eligibility": list(formula_eligibility),
        "required_dimensions": [],
        "forbidden_uses": list(forbidden_uses),
        "allowed_archetype_profiles": list(allowed_archetype_profiles),
        "taxonomy_documentation_binding": f"us-gaap:{concept}",
    }


CONCEPT_REGISTRY = {
    "contract_id": "room16.alpha.shared_concept_registry",
    "contract_version": 2,
    "families": {
        "cash_and_equivalents": {
            "metric_definition": "Unrestricted cash and cash equivalents at carrying value.",
            "period_type": "INSTANT",
            "allowed_units": ["USD"],
            "candidates": [
                _candidate(
                    "CashAndCashEquivalentsAtCarryingValue",
                    semantic_role="EXACT_DIRECT",
                    equivalence_class="unrestricted_cash_equivalents",
                    aggregation_role="DIRECT_TOTAL",
                    formula_eligibility=("analytical_liquidity", "net_debt"),
                ),
                _candidate(
                    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                    semantic_role="DISCLOSURE_ONLY",
                    equivalence_class="cash_including_restricted",
                    aggregation_role="AGGREGATE_TOTAL",
                    forbidden_uses=("unrestricted_cash", "net_debt", "analytical_liquidity"),
                ),
            ],
        },
        "capital_expenditure": {
            "metric_definition": "Cash paid to acquire property, plant and equipment.",
            "period_type": "DURATION",
            "allowed_units": ["USD"],
            "candidates": [
                _candidate(
                    "PaymentsToAcquirePropertyPlantAndEquipment",
                    semantic_role="EXACT_DIRECT",
                    equivalence_class="cash_ppe_capex",
                    aggregation_role="DIRECT_TOTAL",
                    formula_eligibility=("free_cash_flow",),
                ),
                _candidate(
                    "CapitalExpendituresIncurredButNotYetPaid",
                    semantic_role="FORMULA_INELIGIBLE",
                    equivalence_class="incurred_unpaid_capex",
                    aggregation_role="DISCLOSURE_COMPONENT",
                    forbidden_uses=("free_cash_flow", "cash_capex"),
                ),
            ],
        },
        "long_term_debt": {
            "metric_definition": "Noncurrent long-term debt, including finance leases only when explicitly stated.",
            "period_type": "INSTANT",
            "allowed_units": ["USD"],
            "candidates": [
                _candidate(
                    "LongTermDebtNoncurrent",
                    semantic_role="EXACT_DIRECT",
                    equivalence_class="noncurrent_long_term_debt",
                    aggregation_role="DIRECT_TOTAL",
                ),
                _candidate(
                    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
                    semantic_role="ALTERNATE_EXACT",
                    equivalence_class="noncurrent_long_term_debt_and_leases",
                    aggregation_role="DIRECT_TOTAL",
                ),
                _candidate(
                    "LongTermDebtAndCapitalLeaseObligations",
                    semantic_role="ALTERNATE_EXACT",
                    equivalence_class="long_term_debt_and_leases",
                    aggregation_role="DIRECT_TOTAL",
                ),
                _candidate(
                    "LongTermDebtCurrent",
                    semantic_role="COMPONENT_ONLY",
                    equivalence_class="current_debt_component",
                    aggregation_role="COMPONENT",
                    forbidden_uses=("long_term_debt_total",),
                ),
                _candidate(
                    "LongTermDebtAndFinanceLeaseObligationsCurrent",
                    semantic_role="COMPONENT_ONLY",
                    equivalence_class="current_debt_and_leases_component",
                    aggregation_role="COMPONENT",
                    forbidden_uses=("long_term_debt_total",),
                ),
                _candidate(
                    "DebtInstrumentCarryingAmount",
                    semantic_role="DISCLOSURE_ONLY",
                    equivalence_class="instrument_level_debt",
                    aggregation_role="COMPONENT",
                    forbidden_uses=("long_term_debt_total", "total_debt"),
                ),
            ],
        },
        "net_revenue": {
            "metric_definition": "Total company revenue; a bank component alone is not total net revenue.",
            "period_type": "DURATION",
            "allowed_units": ["USD"],
            "candidates": [
                _candidate(
                    "Revenues",
                    semantic_role="EXACT_DIRECT",
                    equivalence_class="total_revenue",
                    aggregation_role="DIRECT_TOTAL",
                    allowed_archetype_profiles=("generic", "saas", "reit", "energy"),
                ),
                _candidate(
                    "RevenueFromContractWithCustomerExcludingAssessedTax",
                    semantic_role="ALTERNATE_EXACT",
                    equivalence_class="customer_revenue_ex_tax",
                    aggregation_role="DIRECT_TOTAL",
                    allowed_archetype_profiles=("generic", "saas", "reit", "energy"),
                ),
                _candidate(
                    "RevenuesNetOfInterestExpense",
                    semantic_role="EXACT_DIRECT",
                    equivalence_class="bank_total_net_revenue",
                    aggregation_role="DIRECT_TOTAL",
                    allowed_archetype_profiles=("generic", "bank"),
                ),
                _candidate(
                    "InterestIncomeExpenseNonoperatingNet",
                    semantic_role="COMPONENT_ONLY",
                    equivalence_class="net_interest_component",
                    aggregation_role="COMPONENT",
                    forbidden_uses=("total_bank_net_revenue",),
                ),
                _candidate(
                    "InterestIncomeExpenseNet",
                    semantic_role="COMPONENT_ONLY",
                    equivalence_class="net_interest_component",
                    aggregation_role="COMPONENT",
                    forbidden_uses=("total_bank_net_revenue",),
                ),
                _candidate(
                    "NoninterestIncome",
                    semantic_role="COMPONENT_ONLY",
                    equivalence_class="noninterest_revenue_component",
                    aggregation_role="COMPONENT",
                    forbidden_uses=("total_bank_net_revenue",),
                ),
            ],
        },
        "production_volume": {
            "metric_definition": (
                "Consolidated oil-equivalent production for an explicitly bound duration."
            ),
            "period_type": "DURATION",
            "allowed_units": ["KBOE_PER_DAY"],
            "candidates": [
                _candidate(
                    "oil-equivalent production",
                    semantic_role="EXACT_DIRECT",
                    equivalence_class="consolidated_oil_equivalent_production",
                    aggregation_role="DIRECT_TOTAL",
                    allowed_archetype_profiles=("generic", "energy"),
                ),
            ],
        },
    },
}
CONCEPT_REGISTRY_SHA256 = sha256_json(CONCEPT_REGISTRY)


def concept_record(metric_id: str, concept: str) -> dict[str, object] | None:
    family = CONCEPT_REGISTRY["families"].get(metric_id)
    if not isinstance(family, dict):
        return None
    return next((item for item in family["candidates"] if item["concept"] == concept), None)
