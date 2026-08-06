from research_agent.sources.sec.companyfacts_parser import CompanyFactsParser
from research_agent.sources.sec.sec_fundamentals_builder import (
    build_sec_evidence_for_source_ids,
    build_sec_fundamentals_from_companyfacts,
)
from research_agent.research_core.calculations.fundamentals import (
    calculate_fundamental_metrics,
)
from research_agent.reconciliation.source_reconciler import (
    build_canonical_financials_from_facts,
    canonical_financials_to_fundamentals,
)


FIXTURE_COMPANYFACTS = {
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {
                            "val": 2_460_000_000,
                            "fy": 2026,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2026-03-15",
                            "start": "2025-02-01",
                            "end": "2026-01-31",
                            "accn": "0001441816-26-000010",
                        },
                        {
                            "val": 600_000_000,
                            "fy": 2026,
                            "fp": "Q1",
                            "form": "10-Q",
                            "filed": "2025-06-01",
                            "start": "2025-02-01",
                            "end": "2025-04-30",
                            "accn": "q1",
                        },
                        {
                            "val": 610_000_000,
                            "fy": 2026,
                            "fp": "Q2",
                            "form": "10-Q",
                            "filed": "2025-09-01",
                            "start": "2025-05-01",
                            "end": "2025-07-31",
                            "accn": "q2",
                        },
                        {
                            "val": 620_000_000,
                            "fy": 2026,
                            "fp": "Q3",
                            "form": "10-Q",
                            "filed": "2025-12-01",
                            "start": "2025-08-01",
                            "end": "2025-10-31",
                            "accn": "q3",
                        },
                        {
                            "val": 630_000_000,
                            "fy": 2026,
                            "fp": "Q4",
                            "form": "10-K",
                            "filed": "2026-03-15",
                            "start": "2025-11-01",
                            "end": "2026-01-31",
                            "accn": "q4",
                        },
                    ]
                }
            },
            "NetCashProvidedByUsedInOperatingActivities": {
                "units": {
                    "USD": [
                        {
                            "val": 100,
                            "fy": 2026,
                            "fp": "Q4",
                            "form": "10-K",
                            "filed": "2026-03-15",
                            "end": "2026-01-31",
                            "accn": "ocf",
                        }
                    ]
                }
            },
            "PaymentsToAcquirePropertyPlantAndEquipment": {
                "units": {
                    "USD": [
                        {
                            "val": 20,
                            "fy": 2026,
                            "fp": "Q4",
                            "form": "10-K",
                            "filed": "2026-03-15",
                            "end": "2026-01-31",
                            "accn": "capex",
                        }
                    ]
                }
            },
        }
    }
}


def test_companyfacts_parser_extracts_revenue():
    parser = CompanyFactsParser("TEST", "0000000001", FIXTURE_COMPANYFACTS)

    fact = parser.latest_annual_fact("revenue")

    assert fact.value == 2_460_000_000
    assert fact.form == "10-K"
    assert fact.period == "FY2026_FY"


def test_companyfacts_parser_maps_utility_standard_concepts():
    common = {
        "fy": 2026,
        "fp": "Q1",
        "form": "10-Q",
        "filed": "2026-05-05",
        "start": "2026-01-01",
        "end": "2026-03-31",
        "accn": "utility-q1",
    }
    fixture = {
        "facts": {
            "us-gaap": {
                "RegulatedAndUnregulatedOperatingRevenue": {
                    "units": {"USD": [{**common, "val": 9_178_000_000}]}
                },
                "PaymentsOfOrdinaryDividends": {"units": {"USD": [{**common, "val": 846_000_000}]}},
                "InterestExpenseNonoperating": {"units": {"USD": [{**common, "val": 968_000_000}]}},
            }
        }
    }

    parser = CompanyFactsParser("UTILITY", "1", fixture)

    assert parser.get_facts_for_metric("revenue")[0].value == 9_178_000_000
    assert parser.get_facts_for_metric("dividends_paid")[0].value == 846_000_000
    assert parser.get_facts_for_metric("interest_expense")[0].value == 968_000_000


def test_current_debt_securities_complete_cash_and_investments():
    def instant_fact(value, *, end, accession, filed):
        return {
            "val": value,
            "fy": 2027,
            "fp": "Q1",
            "form": "10-Q",
            "filed": filed,
            "end": end,
            "accn": accession,
        }

    fixture = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            instant_fact(
                                13_237_000_000,
                                end="2026-04-26",
                                accession="current-quarter",
                                filed="2026-05-20",
                            )
                        ]
                    }
                },
                "DebtSecuritiesCurrent": {
                    "units": {
                        "USD": [
                            instant_fact(
                                37_098_000_000,
                                end="2026-04-26",
                                accession="current-quarter",
                                filed="2026-05-20",
                            )
                        ]
                    }
                },
                "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent": {
                    "units": {
                        "USD": [
                            instant_fact(
                                12_000_000_000,
                                end="2026-04-26",
                                accession="current-quarter",
                                filed="2026-05-20",
                            )
                        ]
                    }
                },
                "MarketableSecuritiesCurrent": {
                    "units": {
                        "USD": [
                            instant_fact(
                                49_122_000_000,
                                end="2025-10-26",
                                accession="older-quarter",
                                filed="2025-11-19",
                            )
                        ]
                    }
                },
                "LongTermDebt": {
                    "units": {
                        "USD": [
                            instant_fact(
                                8_470_000_000,
                                end="2026-04-26",
                                accession="current-quarter",
                                filed="2026-05-20",
                            )
                        ]
                    }
                },
            }
        }
    }
    parser = CompanyFactsParser("BASE", "1", fixture)
    facts = [
        fact
        for metric_name in (
            "cash_and_equivalents",
            "short_term_investments",
            "marketable_securities",
            "total_debt",
        )
        for fact in parser.get_facts_for_metric(metric_name)
    ]
    canonical, _warnings = build_canonical_financials_from_facts("BASE", "2026-07-31", facts)
    normalized = canonical_financials_to_fundamentals(canonical)
    metrics = calculate_fundamental_metrics(normalized)

    assert normalized["balance_sheet"]["short_term_investments"] == 37_098_000_000
    assert normalized["balance_sheet"]["marketable_securities"] == 12_000_000_000
    assert metrics.cash_and_investments == 62_335_000_000
    assert metrics.net_cash == 53_865_000_000


def test_convertible_debt_noncurrent_completes_total_debt():
    fixture = {
        "facts": {
            "us-gaap": {
                "ConvertibleDebtNoncurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 2_281_903_000,
                                "fy": 2027,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-29",
                                "end": "2026-04-30",
                                "accn": "snow-q1",
                            }
                        ]
                    }
                }
            }
        }
    }
    parser = CompanyFactsParser("BASE", "1", fixture)
    facts = parser.get_facts_for_metric("debt_noncurrent")
    canonical, _warnings = build_canonical_financials_from_facts(
        "BASE", "2026-07-31", facts
    )
    normalized = canonical_financials_to_fundamentals(canonical)
    metrics = calculate_fundamental_metrics(normalized)

    assert normalized["balance_sheet"]["debt_noncurrent"] == 2_281_903_000
    assert metrics.total_debt == 2_281_903_000


def test_treasury_stock_balance_excludes_period_acquisition_cost():
    common = {
        "fy": 2026,
        "fp": "Q2",
        "form": "10-Q",
        "filed": "2026-07-21",
        "end": "2026-06-30",
        "accn": "treasury-q2",
    }
    fixture = {
        "facts": {
            "us-gaap": {
                "TreasuryStockCommonValue": {"units": {"USD": [{**common, "val": 38_177_000_000}]}},
                "TreasuryStockValueAcquiredCostMethod": {
                    "units": {
                        "USD": [
                            {
                                **common,
                                "start": "2026-04-01",
                                "val": 991_000_000,
                            }
                        ]
                    }
                },
            }
        }
    }

    facts = CompanyFactsParser("TEST", "1", fixture).get_facts_for_metric("treasury_stock_value")

    assert [fact.value for fact in facts] == [38_177_000_000]
    assert facts[0].concept == "us-gaap:TreasuryStockCommonValue"


def test_companyfacts_parser_maps_combined_short_and_long_term_debt():
    fixture = {
        "facts": {
            "us-gaap": {
                "DebtLongtermAndShorttermCombinedAmount": {
                    "units": {
                        "USD": [
                            {
                                "val": 129_541_000_000,
                                "fy": 2026,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-06-22",
                                "end": "2026-05-31",
                                "accn": "orcl-2026",
                                "frame": "CY2026Q2I",
                            }
                        ]
                    }
                }
            }
        }
    }

    facts = CompanyFactsParser("TEST", "1", fixture).get_facts_for_metric("total_debt")

    assert len(facts) == 1
    assert facts[0].value == 129_541_000_000
    assert facts[0].concept == "us-gaap:DebtLongtermAndShorttermCombinedAmount"


def test_sec_fact_generates_high_authority_evidence():
    parser = CompanyFactsParser("TEST", "0000000001", FIXTURE_COMPANYFACTS)
    fact = parser.latest_annual_fact("revenue")
    item = parser.to_evidence_item(fact)

    assert item.source_type == "sec_filing"
    assert item.authority_rank == 1
    assert "revenue" in item.supports_metrics
    assert "revenue_ttm" in item.supports_metrics
    assert item.url == (
        "https://www.sec.gov/Archives/edgar/data/1/000144181626000010/"
    )


def test_comparative_facts_in_one_filing_keep_distinct_evidence_ids():
    fixture = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "val": 100,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-01",
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "accn": "same-filing",
                            },
                            {
                                "val": 120,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-01",
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "accn": "same-filing",
                            },
                        ]
                    }
                }
            }
        }
    }
    parser = CompanyFactsParser("TEST", "1", fixture)
    evidence_ids = {
        parser.to_evidence_item(fact).evidence_id for fact in parser.get_facts_for_metric("revenue")
    }

    assert len(evidence_ids) == 2


def test_identical_xbrl_alias_facts_are_materialized_once():
    row = {
        "val": 1_170_000_000,
        "fy": 2026,
        "fp": "Q1",
        "form": "10-Q",
        "filed": "2026-05-07",
        "end": "2026-03-31",
        "accn": "mcd-q1",
        "frame": "CY2026Q1I",
    }
    fixture = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [row]}},
                "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": {
                    "units": {"USD": [dict(row)]}
                },
            }
        }
    }

    facts = CompanyFactsParser("MCD", "63908", fixture).get_facts_for_metric("cash_and_equivalents")
    evidence = CompanyFactsParser("MCD", "63908", fixture).to_evidence_item(facts[0])

    assert len(facts) == 1
    assert evidence.supports_metrics == ["cash_and_equivalents"]


def test_productive_asset_capex_and_split_debt_build_complete_current_metrics():
    def duration_fact(value, fy, fp, start, end, accession, form="10-Q"):
        return {
            "val": value,
            "fy": fy,
            "fp": fp,
            "form": form,
            "filed": "2026-05-27" if form == "10-Q" else "2026-03-18",
            "start": start,
            "end": end,
            "accn": accession,
            "frame": f"CY{end[:4]}Q1" if fp == "Q1" else "CY2025",
        }

    def instant_fact(value):
        return {
            "val": value,
            "fy": 2026,
            "fp": "Q1",
            "form": "10-Q",
            "filed": "2026-05-27",
            "end": "2026-05-03",
            "accn": "quarter",
            "frame": "CY2026Q1I",
        }

    fixture = {
        "facts": {
            "us-gaap": {
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            duration_fact(
                                16_325,
                                2025,
                                "FY",
                                "2025-02-03",
                                "2026-02-01",
                                "annual",
                                "10-K",
                            ),
                            duration_fact(
                                4_325,
                                2025,
                                "Q1",
                                "2025-02-03",
                                "2025-05-04",
                                "prior-quarter",
                            ),
                            duration_fact(
                                6_032,
                                2026,
                                "Q1",
                                "2026-02-02",
                                "2026-05-03",
                                "current-quarter",
                            ),
                        ]
                    }
                },
                "PaymentsToAcquireProductiveAssets": {
                    "units": {
                        "USD": [
                            duration_fact(
                                3_679,
                                2025,
                                "FY",
                                "2025-02-03",
                                "2026-02-01",
                                "annual",
                                "10-K",
                            ),
                            duration_fact(
                                806,
                                2025,
                                "Q1",
                                "2025-02-03",
                                "2025-05-04",
                                "prior-quarter",
                            ),
                            duration_fact(
                                844,
                                2026,
                                "Q1",
                                "2026-02-02",
                                "2026-05-03",
                                "current-quarter",
                            ),
                        ]
                    }
                },
                "LongTermDebt": {
                    "units": {
                        "USD": [
                            {
                                "val": 49_397,
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-03-18",
                                "end": "2026-02-01",
                                "accn": "annual",
                                "frame": "CY2025Q4I",
                            }
                        ]
                    }
                },
                "CommercialPaper": {"units": {"USD": [instant_fact(3_503)]}},
                "LongTermDebtAndCapitalLeaseObligationsCurrent": {
                    "units": {"USD": [instant_fact(5_178)]}
                },
                "LongTermDebtAndCapitalLeaseObligations": {
                    "units": {"USD": [instant_fact(44_828)]}
                },
            }
        }
    }
    parser = CompanyFactsParser("BASE", "1", fixture)
    facts = [
        fact
        for metric_name in (
            "operating_cash_flow",
            "capex",
            "total_debt",
            "short_term_debt",
            "debt_current",
            "debt_noncurrent",
        )
        for fact in parser.get_facts_for_metric(metric_name)
    ]
    canonical, _ = build_canonical_financials_from_facts("BASE", "2026-07-31", facts)
    normalized = canonical_financials_to_fundamentals(canonical)
    metrics = calculate_fundamental_metrics(normalized)

    assert normalized["ttm"]["capex"] == 3_717
    assert metrics.operating_cash_flow_ttm == 18_032
    assert metrics.capex_ttm == 3_717
    assert metrics.free_cash_flow_ttm == 14_315
    assert metrics.short_term_debt == 3_503
    assert metrics.debt_current == 5_178
    assert metrics.debt_noncurrent == 44_828
    assert metrics.total_debt == 53_509


def test_conflicting_xbrl_alias_facts_remain_visible():
    common = {
        "fy": 2026,
        "fp": "Q1",
        "form": "10-Q",
        "filed": "2026-05-07",
        "end": "2026-03-31",
        "accn": "mcd-q1",
        "frame": "CY2026Q1I",
    }
    fixture = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {"USD": [{**common, "val": 1_170_000_000}]}
                },
                "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents": {
                    "units": {"USD": [{**common, "val": 1_180_000_000}]}
                },
            }
        }
    }

    parser = CompanyFactsParser("MCD", "63908", fixture)
    facts = parser.get_facts_for_metric("cash_and_equivalents")
    evidence_ids = [parser.to_evidence_item(fact).evidence_id for fact in facts]
    canonical, _warnings = build_canonical_financials_from_facts("MCD", "2026-05-07", facts)
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert [fact.value for fact in facts] == [1_170_000_000, 1_180_000_000]
    assert len(set(evidence_ids)) == 2
    assert len(canonical.metrics_for("cash_and_equivalents")) == 2
    assert {
        evidence_id
        for metric in canonical.metrics_for("cash_and_equivalents")
        for evidence_id in metric.evidence_ids
    } == set(evidence_ids)
    assert fundamentals["balance_sheet"]["cash_and_equivalents"] == 1_170_000_000


def test_same_ten_k_q4_fact_is_not_emitted_twice():
    fixture = {
        "facts": {
            "us-gaap": {
                "GrossProfit": {
                    "units": {
                        "USD": [
                            {
                                "val": 16_465_000_000,
                                "fy": 2019,
                                "fp": "Q4",
                                "form": "10-K",
                                "filed": "2019-10-11",
                                "start": "2018-09-03",
                                "end": "2019-09-01",
                                "accn": "0000909832-19-000019",
                                "frame": "CY2019",
                            }
                        ]
                    }
                }
            }
        }
    }

    _metrics, evidence = build_sec_fundamentals_from_companyfacts("COST", "909832", fixture)

    assert len(evidence) == 1
    assert len({item.evidence_id for item in evidence}) == 1


def test_period_eps_evidence_does_not_impersonate_trailing_eps():
    parser = CompanyFactsParser(
        "COST",
        "909832",
        {
            "facts": {
                "us-gaap": {
                    "EarningsPerShareDiluted": {
                        "units": {
                            "USD/shares": [
                                {
                                    "val": 18.21,
                                    "fy": 2025,
                                    "fp": "FY",
                                    "form": "10-K",
                                    "filed": "2025-10-08",
                                    "start": "2024-09-02",
                                    "end": "2025-08-31",
                                    "accn": "0000909832-25-000101",
                                }
                            ]
                        }
                    }
                }
            }
        },
    )

    item = parser.to_evidence_item(parser.get_facts_for_metric("eps_diluted")[0])

    assert item.supports_metrics == ["eps_diluted", "eps_diluted_ttm"]
    assert "trailing_eps" not in item.supports_metrics


def test_sec_fundamentals_builder_returns_metrics_and_evidence():
    metrics, evidence = build_sec_fundamentals_from_companyfacts("TEST", "1", FIXTURE_COMPANYFACTS)

    assert metrics["revenue_latest_annual"] == 2_460_000_000
    assert metrics["quarterly"]["revenue"][-1] == 630_000_000
    assert any(item.source_type == "sec_filing" for item in evidence)
    exact = build_sec_evidence_for_source_ids(
        "TEST",
        "1",
        FIXTURE_COMPANYFACTS,
        {"SEC_q1"},
    )
    assert [(item.value, item.source_lineage) for item in exact] == [(600_000_000.0, ["q1"])]


def test_recognizes_depreciation_depletion_and_amortization():
    fixture = {
        "facts": {
            "us-gaap": {
                "DepreciationDepletionAndAmortization": {
                    "units": {
                        "USD": [
                            {
                                "val": 2_906_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "accn": "cop-q1",
                            }
                        ]
                    }
                }
            }
        }
    }

    metrics, evidence = build_sec_fundamentals_from_companyfacts("COP", "1163165", fixture)

    assert metrics["quarterly"]["depreciation_and_amortization"] == [2_906_000_000]
    assert evidence[0].supports_metrics == [
        "depreciation_and_amortization",
        "depreciation_and_amortization_ttm",
    ]


def test_current_evidence_excludes_stale_metric_history():
    fixture = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 10_000_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "accn": "current",
                            }
                        ]
                    }
                },
                "CommercialPaper": {
                    "units": {
                        "USD": [
                            {
                                "val": 1_000_000_000,
                                "fy": 2013,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2013-04-30",
                                "end": "2013-03-31",
                                "accn": "stale",
                            }
                        ]
                    }
                },
                "ShortTermBorrowings": {
                    "units": {
                        "USD": [
                            {
                                "val": 2_000_000_000,
                                "fy": 2027,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2027-04-30",
                                "end": "2027-03-31",
                                "accn": "future",
                            }
                        ]
                    }
                },
            }
        }
    }

    metrics, evidence = build_sec_fundamentals_from_companyfacts(
        "COP",
        "1163165",
        fixture,
        as_of_date="2026-07-31",
    )

    assert "short_term_debt_latest_4_quarters" not in metrics
    assert not any("short_term_debt" in item.supports_metrics for item in evidence)


def test_diluted_shares_are_scaled_from_same_period_income_and_eps():
    companyfacts = {
        "facts": {
            "us-gaap": {
                "WeightedAverageNumberOfDilutedSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "val": 713.5,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 1_983_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {
                                "val": 2.78,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
            }
        }
    }

    fact = CompanyFactsParser("MCD", "63908", companyfacts).get_facts_for_metric("shares_diluted")[
        0
    ]

    assert fact.raw_value == 713.5
    assert fact.value == 713_500_000
    assert "same-period net income and diluted EPS" in fact.normalization_note


def test_full_diluted_share_count_is_not_rescaled():
    companyfacts = {
        "facts": {
            "us-gaap": {
                "WeightedAverageNumberOfDilutedSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "val": 347_624_244,
                                "form": "10-K",
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "accn": "normal",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 1_390_496_976,
                                "form": "10-K",
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "accn": "normal",
                            }
                        ]
                    }
                },
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {
                                "val": 4.0,
                                "form": "10-K",
                                "start": "2025-01-01",
                                "end": "2025-12-31",
                                "accn": "normal",
                            }
                        ]
                    }
                },
            }
        }
    }

    fact = CompanyFactsParser("TEST", "1", companyfacts).get_facts_for_metric("shares_diluted")[0]

    assert fact.value == 347_624_244
    assert fact.normalization_note is None


def test_balance_sheet_builder_uses_latest_quarter_instead_of_annual_value():
    companyfacts = {
        "facts": {
            "us-gaap": {
                "AssetsCurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 4_163_000_000,
                                "fy": 2025,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2026-02-24",
                                "end": "2025-12-31",
                                "accn": "fy",
                            },
                            {
                                "val": 4_709_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "end": "2026-03-31",
                                "accn": "q1",
                            },
                        ]
                    }
                }
            }
        }
    }

    metrics, _ = build_sec_fundamentals_from_companyfacts(
        "MCD",
        "63908",
        companyfacts,
    )

    assert metrics["balance_sheet"]["current_assets"] == 4_709_000_000


def test_share_scale_warnings_are_coalesced_for_one_issuer_history():
    parser = CompanyFactsParser(
        "MCD",
        "63908",
        {
            "facts": {
                "us-gaap": {
                    "WeightedAverageNumberOfDilutedSharesOutstanding": {
                        "units": {
                            "shares": [
                                {
                                    "val": 716.4,
                                    "form": "10-K",
                                    "fp": "FY",
                                    "fy": 2025,
                                    "filed": "2026-02-24",
                                    "start": "2025-01-01",
                                    "end": "2025-12-31",
                                    "accn": "fy",
                                },
                                {
                                    "val": 713.5,
                                    "form": "10-Q",
                                    "fp": "Q1",
                                    "fy": 2026,
                                    "filed": "2026-05-07",
                                    "start": "2026-01-01",
                                    "end": "2026-03-31",
                                    "accn": "q1",
                                },
                            ]
                        }
                    },
                    "NetIncomeLoss": {
                        "units": {
                            "USD": [
                                {
                                    "val": 8_563_000_000,
                                    "form": "10-K",
                                    "fp": "FY",
                                    "fy": 2025,
                                    "filed": "2026-02-24",
                                    "start": "2025-01-01",
                                    "end": "2025-12-31",
                                    "accn": "fy",
                                },
                                {
                                    "val": 1_983_000_000,
                                    "form": "10-Q",
                                    "fp": "Q1",
                                    "fy": 2026,
                                    "filed": "2026-05-07",
                                    "start": "2026-01-01",
                                    "end": "2026-03-31",
                                    "accn": "q1",
                                },
                            ]
                        }
                    },
                    "EarningsPerShareDiluted": {
                        "units": {
                            "USD/shares": [
                                {
                                    "val": 11.95,
                                    "form": "10-K",
                                    "fp": "FY",
                                    "fy": 2025,
                                    "filed": "2026-02-24",
                                    "start": "2025-01-01",
                                    "end": "2025-12-31",
                                    "accn": "fy",
                                },
                                {
                                    "val": 2.78,
                                    "form": "10-Q",
                                    "fp": "Q1",
                                    "fy": 2026,
                                    "filed": "2026-05-07",
                                    "start": "2026-01-01",
                                    "end": "2026-03-31",
                                    "accn": "q1",
                                },
                            ]
                        }
                    },
                }
            }
        },
    )
    facts = parser.get_facts_for_metric("shares_diluted")

    _, warnings = build_canonical_financials_from_facts(
        ticker="MCD",
        as_of_date="2026-07-24",
        facts=facts,
    )
    scale_warnings = [
        warning for warning in warnings if warning["code"] == "SEC_SHARE_SCALE_NORMALIZED"
    ]

    assert len(scale_warnings) == 1
    assert scale_warnings[0]["count"] == 2


def test_companyfacts_maps_point_in_time_shares_debt_leases_and_buybacks():
    companyfacts = {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "val": 710_505_859,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                }
            },
            "us-gaap": {
                "LongTermDebtNoncurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 40_105_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
                "OperatingLeaseLiabilityCurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 707_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
                "OperatingLeaseLiabilityNoncurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 14_069_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
                "FinanceLeaseLiabilityCurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 100_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
                "FinanceLeaseLiabilityNoncurrent": {
                    "units": {
                        "USD": [
                            {
                                "val": 1_000_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
                "PaymentsForRepurchaseOfCommonStock": {
                    "units": {
                        "USD": [
                            {
                                "val": 396_000_000,
                                "fy": 2026,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2026-05-07",
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "accn": "mcd-q1",
                            }
                        ]
                    }
                },
            },
        }
    }
    parser = CompanyFactsParser("MCD", "63908", companyfacts)
    facts = [
        fact
        for metric in (
            "listed_share_count",
            "debt_noncurrent",
            "lease_liability_current",
            "lease_liability_noncurrent",
            "buybacks",
        )
        for fact in parser.get_facts_for_metric(metric)
    ]
    canonical, _ = build_canonical_financials_from_facts("MCD", "2026-07-24", facts)
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["share_data"]["listed_share_count"] == 710_505_859
    assert fundamentals["balance_sheet"]["total_debt"] == 40_105_000_000
    assert fundamentals["balance_sheet"]["lease_liability_current"] == 807_000_000
    assert fundamentals["balance_sheet"]["lease_liability_noncurrent"] == 15_069_000_000
    assert fundamentals["balance_sheet"]["total_lease_liabilities"] == 15_876_000_000
    assert fundamentals["lease_component_bridges"]["lease_liability_current"]["operands"] == {
        "operating_lease_liability_current": 707_000_000,
        "finance_lease_liability_current": 100_000_000,
    }


def test_net_income_uses_financial_filing_fallback_and_ignores_proxy_facts():
    def fact(value, start, end, fp, form, accession):
        return {
            "val": value,
            "fy": 2026 if end.startswith("2026") else 2025,
            "fp": fp,
            "form": form,
            "filed": "2026-05-06",
            "start": start,
            "end": end,
            "accn": accession,
        }

    companyfacts = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            fact(
                                8_884_000_000,
                                "2025-01-01",
                                "2025-12-31",
                                "FY",
                                "DEF 14A",
                                "proxy",
                            )
                        ]
                    }
                },
                "NetIncomeLossAvailableToCommonStockholdersBasic": {
                    "units": {
                        "USD": [
                            fact(
                                8_884_000_000,
                                "2025-01-01",
                                "2025-12-31",
                                "FY",
                                "10-K",
                                "annual",
                            ),
                            fact(
                                2_003_000_000,
                                "2025-01-01",
                                "2025-03-31",
                                "Q1",
                                "10-Q",
                                "prior-q1",
                            ),
                            fact(
                                2_549_000_000,
                                "2026-01-01",
                                "2026-03-31",
                                "Q1",
                                "10-Q",
                                "current-q1",
                            ),
                        ]
                    }
                },
            }
        }
    }
    parser = CompanyFactsParser("TEST", "1", companyfacts)
    facts = parser.get_facts_for_metric("net_income")
    canonical, _ = build_canonical_financials_from_facts("TEST", "2026-07-31", facts)
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert {fact.form for fact in facts} == {"10-K", "10-Q"}
    assert fundamentals["ttm"]["net_income"] == 9_430_000_000
