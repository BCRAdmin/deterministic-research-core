US_GAAP_CONCEPTS = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RegulatedAndUnregulatedOperatingRevenue",
        "SalesRevenueNet",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": [
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLoss",
    ],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "cash_and_equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_term_investments": [
        "OtherShortTermInvestments",
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "DebtSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ],
    "marketable_securities": [
        "MarketableSecurities",
        "MarketableSecuritiesNoncurrent",
        "DebtSecuritiesNoncurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent",
    ],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "total_debt": [
        "DebtAndFinanceLeaseObligations",
        "DebtAndCapitalLeaseObligations",
        "DebtLongtermAndShorttermCombinedAmount",
        "LongTermDebt",
    ],
    "short_term_debt": ["ShortTermBorrowings", "CommercialPaper"],
    "debt_current": [
        "DebtCurrent",
        "LongTermDebtCurrent",
        "LongTermDebtAndCapitalLeaseObligationsCurrent",
    ],
    "debt_noncurrent": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        "ConvertibleDebtNoncurrent",
    ],
    "lease_liability_current": [
        "OperatingLeaseLiabilityCurrent",
        "FinanceLeaseLiabilityCurrent",
    ],
    "lease_liability_noncurrent": [
        "OperatingLeaseLiabilityNoncurrent",
        "FinanceLeaseLiabilityNoncurrent",
    ],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "sbc": ["ShareBasedCompensation"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "dividends_paid": [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
        "PaymentsOfOrdinaryDividends",
    ],
    "treasury_stock_value": [
        "TreasuryStockCommonValue",
        "TreasuryStockValue",
    ],
    "treasury_share_count": [
        "TreasuryStockCommonShares",
        "TreasuryStockShares",
    ],
    "depreciation_and_amortization": [
        "DepreciationAndAmortization",
        "DepreciationDepletionAndAmortization",
    ],
    "interest_expense": ["InterestExpenseNonoperating", "InterestExpense"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "eps_diluted": ["EarningsPerShareDiluted"],
}


DEI_CONCEPTS = {
    "listed_share_count": ["EntityCommonStockSharesOutstanding"],
}


def concept_priority(metric_name: str, source_concept: str | None) -> int:
    """Return the configured preference rank for a canonical SEC concept."""

    if not source_concept:
        return 0
    namespace, separator, concept = source_concept.partition(":")
    if not separator:
        namespace, concept = "us-gaap", namespace
    concepts = (
        US_GAAP_CONCEPTS.get(metric_name, [])
        if namespace == "us-gaap"
        else DEI_CONCEPTS.get(metric_name, [])
        if namespace == "dei"
        else []
    )
    try:
        return len(concepts) - concepts.index(concept)
    except ValueError:
        return 0
