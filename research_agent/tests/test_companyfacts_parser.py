from research_agent.sources.sec.companyfacts_parser import CompanyFactsParser
from research_agent.sources.sec.sec_fundamentals_builder import (
    build_sec_evidence_for_source_ids,
    build_sec_fundamentals_from_companyfacts,
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


def test_sec_fact_generates_high_authority_evidence():
    parser = CompanyFactsParser("TEST", "0000000001", FIXTURE_COMPANYFACTS)
    fact = parser.latest_annual_fact("revenue")
    item = parser.to_evidence_item(fact)

    assert item.source_type == "sec_filing"
    assert item.authority_rank == 1
    assert "revenue" in item.supports_metrics
    assert "revenue_ttm" in item.supports_metrics


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
        parser.to_evidence_item(fact).evidence_id
        for fact in parser.get_facts_for_metric("revenue")
    }

    assert len(evidence_ids) == 2


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
    assert [(item.value, item.source_lineage) for item in exact] == [
        (600_000_000.0, ["q1"])
    ]


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
    canonical, _ = build_canonical_financials_from_facts(
        "MCD", "2026-07-24", facts
    )
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["share_data"]["listed_share_count"] == 710_505_859
    assert fundamentals["balance_sheet"]["total_debt"] == 40_105_000_000
    assert (
        fundamentals["balance_sheet"]["total_lease_liabilities"]
        == 14_776_000_000
    )
