"""Metric-semantic concept families with no issuer-specific branches."""

from __future__ import annotations

from research_agent.compiler_foundation.canonical import sha256_json

CONCEPT_REGISTRY = {
    "contract_id": "room16.alpha.shared_concept_registry",
    "contract_version": 1,
    "families": {
        "cash_and_equivalents": {
            "concepts": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
            "period_type": "INSTANT",
            "units": ["USD"],
        },
        "capital_expenditure": {
            "concepts": ["PaymentsToAcquirePropertyPlantAndEquipment", "CapitalExpendituresIncurredButNotYetPaid"],
            "period_type": "DURATION",
            "units": ["USD"],
        },
        "long_term_debt": {
            "concepts": ["LongTermDebtCurrent", "LongTermDebtNoncurrent", "LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtAndFinanceLeaseObligationsNoncurrent"],
            "period_type": "INSTANT",
            "units": ["USD"],
        },
        "net_revenue": {
            "concepts": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "InterestIncomeExpenseNonoperatingNet"],
            "period_type": "DURATION",
            "units": ["USD"],
        },
    },
}
CONCEPT_REGISTRY_SHA256 = sha256_json(CONCEPT_REGISTRY)
