from research_agent.reconciliation.canonical_financials import (
    CanonicalFinancials,
    CanonicalMetric,
)
from research_agent.reconciliation.source_reconciler import (
    build_canonical_financials_from_facts,
    canonical_financials_to_fundamentals,
    quality_relevant_reconciliation_warnings,
    reconcile_metric,
)
from research_agent.research_core.calculations.fundamentals import (
    calculate_fundamental_metrics,
)
from research_agent.sources.sec.companyfacts_parser import ParsedFact


def _metric(value, basis, source_id="SEC", confidence="high", metric_name="eps"):
    return CanonicalMetric(
        metric_name=metric_name,
        value=value,
        unit="usd_per_share",
        period="FY2027",
        fiscal_year=2027,
        fiscal_period="FY",
        period_bucket="annual",
        start_date="2026-02-01",
        end_date="2027-01-31",
        basis=basis,
        statement_type="guidance" if "guidance" in metric_name else "income_statement",
        source_ids=[source_id],
        evidence_ids=[source_id],
        confidence=confidence,
    )


def _fact(metric_name, value, fp, start, end, accession):
    return ParsedFact(
        metric_name=metric_name,
        value=value,
        unit="USD",
        period=f"FY2026_{fp}",
        fy=2026,
        fp=fp,
        form="10-K" if fp == "FY" else "10-Q",
        filed="2026-03-01",
        start=start,
        end=end,
        accession=accession,
    )


def test_gaap_and_non_gaap_metrics_are_not_merged():
    canonical, warnings = reconcile_metric("eps", [
        _metric(value=0.18, basis="gaap"),
        _metric(value=5.93, basis="non_gaap", source_id="IR"),
    ])

    bases = {metric.basis for metric in canonical}

    assert "gaap" in bases
    assert "non_gaap" in bases


def test_guidance_and_consensus_remain_separate():
    canonical, warnings = reconcile_metric("forward_eps", [
        _metric(value=5.93, basis="company_defined", source_id="IR", metric_name="company_guidance_eps"),
        _metric(value=7.05, basis="consensus", source_id="PROVIDER", metric_name="consensus_forward_eps"),
    ])

    bases = {metric.basis for metric in canonical}

    assert "company_defined" in bases
    assert "consensus" in bases


def test_source_value_disagreement_warns_within_same_basis():
    canonical, warnings = reconcile_metric("revenue", [
        _metric(value=100, basis="gaap", source_id="SEC", metric_name="revenue"),
        _metric(value=105, basis="gaap", source_id="VENDOR", metric_name="revenue"),
    ])

    disagreement = next(
        warning
        for warning in warnings
        if warning["code"] == "TRUE_SOURCE_VALUE_DISAGREEMENT"
    )
    assert disagreement["period"] == "FY2027"
    assert disagreement["end_date"] == "2027-01-31"
    assert disagreement["source_ids"] == ["SEC", "VENDOR"]
    assert disagreement["candidate_values"] == [100.0, 105.0]
    assert canonical[0].value == 100


def test_quality_scope_keeps_current_and_undated_conflicts_only():
    warnings = [
        {
            "code": "PERIOD_TYPE_MISMATCH_IGNORED",
            "severity": "info",
        },
        {
            "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
            "end_date": "2023-12-31",
        },
        {
            "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
            "end_date": "2025-12-31",
        },
        {"code": "TRUE_SOURCE_VALUE_DISAGREEMENT"},
        {"code": "STALE_FINANCIAL_METRIC_EXCLUDED"},
    ]
    fundamentals = {
        "ttm_bridges": {
            "revenue": {
                "period_start": "2025-01-01",
            }
        }
    }

    relevant = quality_relevant_reconciliation_warnings(
        warnings,
        fundamentals,
    )

    assert relevant == warnings[2:]


def test_quality_scope_keeps_dated_conflicts_without_material_period():
    warning = {
        "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
        "end_date": "2023-12-31",
    }

    assert quality_relevant_reconciliation_warnings([warning], {}) == [warning]


def test_quality_scope_uses_the_material_window_for_each_metric():
    warnings = [
        {
            "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
            "metric": "revenue",
            "end_date": "2025-12-31",
        },
        {
            "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
            "metric": "equity",
            "end_date": "2024-06-30",
        },
        {
            "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
            "metric": "equity",
            "end_date": "2026-06-30",
        },
        {
            "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
            "metric": "unused_historical_metric",
            "end_date": "2025-12-31",
        },
    ]
    fundamentals = {
        "ttm_bridges": {
            "revenue": {
                "period_start": "2025-07-01",
            }
        },
        "reconciliation_material_dates": {
            "equity": "2026-06-30",
        },
    }

    assert quality_relevant_reconciliation_warnings(warnings, fundamentals) == [
        warnings[0],
        warnings[2],
    ]


def test_period_type_variants_are_ignored_not_warned():
    canonical, warnings = reconcile_metric("revenue", [
        _metric(value=100, basis="gaap", source_id="SEC", metric_name="revenue"),
        _metric(value=25, basis="gaap", source_id="SEC", metric_name="revenue").model_copy(
            update={
                "period": "Q4_FY2027_quarterly",
                "fiscal_period": "FY",
                "period_bucket": "quarterly",
                "start_date": "2026-11-01",
                "end_date": "2027-01-31",
            }
        ),
    ])

    assert not any(warning["code"] == "TRUE_SOURCE_VALUE_DISAGREEMENT" for warning in warnings)
    assert any(warning["code"] == "PERIOD_TYPE_MISMATCH_IGNORED" for warning in warnings)


def test_ytd_source_disagreements_are_ignored_not_true_warnings():
    ytd_metric = _metric(value=300, basis="gaap", source_id="SEC", metric_name="revenue").model_copy(
        update={
            "period": "Q2_FY2027_ytd",
            "fiscal_period": "Q2",
            "period_bucket": "ytd",
            "start_date": "2026-02-01",
            "end_date": "2026-07-31",
        }
    )

    canonical, warnings = reconcile_metric("revenue", [
        ytd_metric,
        ytd_metric.model_copy(update={"value": 305, "source_ids": ["SEC_RESTATEMENT"]}),
    ])

    assert not any(warning["code"] == "TRUE_SOURCE_VALUE_DISAGREEMENT" for warning in warnings)
    assert any(warning["code"] == "PERIOD_TYPE_MISMATCH_IGNORED" for warning in warnings)
    assert canonical[0].value == 300


def test_canonical_financials_can_be_built_from_sec_facts():
    facts = [
        _fact("revenue", 10, "Q1", "2025-02-01", "2025-04-30", "q1"),
        _fact("revenue", 11, "Q2", "2025-05-01", "2025-07-31", "q2"),
        _fact("revenue", 12, "Q3", "2025-08-01", "2025-10-31", "q3"),
        _fact("revenue", 13, "Q4", "2025-11-01", "2026-01-31", "q4"),
    ]

    canonical, warnings = build_canonical_financials_from_facts("TEST", "2026-05-01", facts)
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert canonical.get_metric("revenue", "Q4_FY2026_quarterly").value == 13
    assert fundamentals["quarterly"]["revenue"] == [10, 11, 12, 13]


def test_stale_duration_metric_is_not_mixed_into_current_ttm():
    stale = _metric(
        value=64_333,
        basis="gaap",
        source_id="SEC_OLD",
        metric_name="gross_profit",
    ).model_copy(
        update={
            "period": "FY2016",
            "fiscal_year": 2016,
            "start_date": "2016-01-01",
            "end_date": "2016-12-31",
        }
    )
    canonical = CanonicalFinancials(
        ticker="RIOT",
        as_of_date="2026-07-24",
        metrics=[stale],
    )

    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert "gross_profit" not in fundamentals["annual"]
    assert any(
        issue["code"] == "STALE_FINANCIAL_METRIC_EXCLUDED"
        and issue["metric"] == "gross_profit"
        for issue in fundamentals["reconciliation_issues"]
    )


def test_stale_balance_sheet_metric_is_not_treated_as_current():
    stale = CanonicalMetric(
        metric_name="short_term_investments",
        value=2_170_000,
        unit="USD",
        period="FY2022",
        fiscal_year=2022,
        fiscal_period="FY",
        period_bucket="instant",
        end_date="2022-12-31",
        basis="gaap",
        statement_type="balance_sheet",
        source_ids=["SEC_OLD"],
        confidence="high",
    )
    current = stale.model_copy(
        update={
            "metric_name": "cash_and_equivalents",
            "value": 289_176_000,
            "period": "FY2026_Q1",
            "fiscal_year": 2026,
            "fiscal_period": "Q1",
            "end_date": "2026-03-31",
            "source_ids": ["SEC_CURRENT"],
        }
    )
    canonical = CanonicalFinancials(
        ticker="RIOT",
        as_of_date="2026-07-24",
        metrics=[stale, current],
    )

    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["balance_sheet"]["cash_and_equivalents"] == 289_176_000
    assert "short_term_investments" not in fundamentals["balance_sheet"]


def test_stale_debt_current_does_not_hide_current_short_term_debt():
    def instant_metric(metric_name, value, end_date, source_concept):
        return CanonicalMetric(
            metric_name=metric_name,
            value=value,
            unit="USD",
            period=end_date,
            period_bucket="instant",
            end_date=end_date,
            basis="gaap",
            statement_type="balance_sheet",
            source_ids=[f"SEC_{metric_name}"],
            evidence_ids=[f"EVIDENCE_{metric_name}"],
            confidence="high",
            source_concept=source_concept,
        )

    canonical = CanonicalFinancials(
        ticker="BASE",
        as_of_date="2026-07-31",
        metrics=[
            instant_metric(
                "total_debt", 41_438, "2025-12-28", "us-gaap:LongTermDebt"
            ),
            instant_metric(
                "debt_current", 8_500, "2025-12-28", "us-gaap:DebtCurrent"
            ),
            instant_metric(
                "short_term_debt",
                11_692,
                "2026-06-28",
                "us-gaap:ShortTermBorrowings",
            ),
            instant_metric(
                "debt_noncurrent",
                37_344,
                "2026-06-28",
                "us-gaap:LongTermDebtNoncurrent",
            ),
        ],
    )

    balance = canonical_financials_to_fundamentals(canonical)["balance_sheet"]

    assert balance["total_debt"] == 49_036
    assert balance["short_term_debt"] == 11_692
    assert balance["debt_noncurrent"] == 37_344
    assert "debt_current" not in balance


def test_duplicate_short_term_debt_alias_is_not_double_counted():
    def instant_metric(metric_name, value, source_concept):
        return CanonicalMetric(
            metric_name=metric_name,
            value=value,
            unit="USD",
            period="2026-06-30",
            period_bucket="instant",
            end_date="2026-06-30",
            basis="gaap",
            statement_type="balance_sheet",
            source_ids=["SEC_CURRENT"],
            evidence_ids=[f"EVIDENCE_{metric_name}"],
            confidence="high",
            source_concept=source_concept,
        )

    canonical = CanonicalFinancials(
        ticker="BASE",
        as_of_date="2026-07-31",
        metrics=[
            instant_metric(
                "debt_current",
                5_772,
                "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent",
            ),
            instant_metric(
                "short_term_debt",
                5_775,
                "us-gaap:ShortTermBorrowings",
            ),
            instant_metric(
                "debt_noncurrent",
                56_212,
                "us-gaap:LongTermDebtNoncurrent",
            ),
        ],
    )

    balance = canonical_financials_to_fundamentals(canonical)["balance_sheet"]

    assert balance["total_debt"] == 61_984
    assert balance["debt_current"] == 5_772
    assert balance["debt_noncurrent"] == 56_212
    assert "short_term_debt" not in balance


def test_balance_sheet_totals_do_not_mix_prior_debt_with_current_cash():
    def instant_metric(metric_name, value, end_date, source_concept):
        return CanonicalMetric(
            metric_name=metric_name,
            value=value,
            unit="USD",
            period=end_date,
            period_bucket="instant",
            end_date=end_date,
            basis="gaap",
            statement_type="balance_sheet",
            source_ids=[f"SEC_{metric_name}"],
            evidence_ids=[f"EVIDENCE_{metric_name}"],
            confidence="high",
            source_concept=source_concept,
        )

    canonical = CanonicalFinancials(
        ticker="BASE",
        as_of_date="2026-07-31",
        metrics=[
            instant_metric(
                "cash_and_equivalents",
                4_072,
                "2026-03-31",
                "us-gaap:CashAndCashEquivalentsAtCarryingValue",
            ),
            instant_metric(
                "short_term_debt",
                5_514,
                "2025-12-31",
                "us-gaap:ShortTermBorrowings",
            ),
            instant_metric(
                "debt_noncurrent",
                30_696,
                "2025-12-31",
                "us-gaap:LongTermDebtNoncurrent",
            ),
        ],
    )

    fundamentals = canonical_financials_to_fundamentals(canonical)
    balance = fundamentals["balance_sheet"]

    assert balance["cash_and_equivalents"] == 4_072
    assert "short_term_debt" not in balance
    assert "debt_noncurrent" not in balance
    assert "total_debt" not in balance
    assert {
        issue["metric"]
        for issue in fundamentals["reconciliation_issues"]
        if issue["code"] == "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED"
    } == {"short_term_debt", "debt_noncurrent"}


def test_ttm_bridge_does_not_skip_q4_when_current_q1_arrives():
    facts = [
        _fact("revenue", 25_920, "FY", "2024-01-01", "2024-12-31", "fy-2024"),
        _fact("revenue", 5_956, "Q1", "2025-01-01", "2025-03-31", "q1-2025"),
        _fact("revenue", 6_843, "Q2", "2025-04-01", "2025-06-30", "q2-2025"),
        _fact("revenue", 7_078, "Q3", "2025-07-01", "2025-09-30", "q3-2025"),
        _fact("revenue", 26_885, "FY", "2025-01-01", "2025-12-31", "fy-2025"),
        _fact("revenue", 6_517, "Q1", "2026-01-01", "2026-03-31", "q1-2026"),
    ]

    canonical, _ = build_canonical_financials_from_facts(
        "MCD", "2026-07-24", facts
    )
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["quarterly"]["revenue"] == [
        6_843,
        7_078,
        7_008,
        6_517,
    ]
    assert sum(fundamentals["quarterly"]["revenue"]) == 27_446
    bridge = fundamentals["ttm_bridges"]["revenue"]
    assert bridge["formula_id"] == (
        "annual_minus_prior_interim_plus_current_interim"
    )
    assert bridge["operands"] == {
        "annual": 26_885,
        "prior_interim": 5_956,
        "current_interim": 6_517,
    }
    assert fundamentals["revenue_growth_yoy"] == (26_885 - 25_920) / 25_920
    assert fundamentals["revenue_growth_yoy_bridge"]["operands"] == {
        "current_annual_revenue": 26_885,
        "prior_annual_revenue": 25_920,
    }


def test_current_period_growth_pairs_same_fiscal_quarter():
    canonical = CanonicalFinancials(
        ticker="MCD",
        as_of_date="2026-07-24",
        metrics=[
            CanonicalMetric(
                metric_name="revenue",
                value=value,
                unit="USD",
                period=f"CY{date_year}Q{quarter}",
                fiscal_year=fiscal_year,
                fiscal_period=f"Q{quarter}",
                period_bucket="quarterly",
                start_date=f"{date_year}-0{1 if quarter == 1 else 4}-01",
                end_date=f"{date_year}-0{3 if quarter == 1 else 6}-30",
                duration_days=89,
                basis="gaap",
                statement_type="income_statement",
                source_ids=[f"SEC_MCD_{date_year}_Q{quarter}"],
                confidence="high",
            )
            for date_year, fiscal_year, quarter, value in (
                (2025, 2026, 1, 5_956),
                (2025, 2025, 2, 6_843),
                (2026, 2026, 1, 6_517),
            )
        ],
    )

    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["current_period_revenue_growth_yoy"] == (
        6_517 - 5_956
    ) / 5_956
    assert fundamentals["current_period_growth_bridges"]["revenue"][
        "operands"
    ] == {
        "current_revenue": 6_517,
        "prior_revenue": 5_956,
    }


def test_latest_annual_report_supersedes_prior_quarter_context():
    metrics = []
    for metric_name, prior_value, current_value in (
        ("revenue", 281_724, 331_839),
        ("operating_income", 128_528, 155_237),
        ("net_income", 101_832, 133_749),
    ):
        metrics.extend(
            [
                CanonicalMetric(
                    metric_name=metric_name,
                    value=value,
                    unit="USD",
                    period=f"FY{fiscal_year}",
                    fiscal_year=fiscal_year,
                    fiscal_period="FY",
                    period_bucket="annual",
                    start_date=f"{fiscal_year - 1}-07-01",
                    end_date=f"{fiscal_year}-06-30",
                    duration_days=364,
                    basis="gaap",
                    statement_type="income_statement",
                    source_ids=[f"SEC_MSFT_FY{fiscal_year}"],
                    confidence="high",
                )
                for fiscal_year, value in (
                    (2025, prior_value),
                    (2026, current_value),
                )
            ]
        )
    metrics.append(
        CanonicalMetric(
            metric_name="revenue",
            value=82_886,
            unit="USD",
            period="FY2026_Q3",
            fiscal_year=2026,
            fiscal_period="Q3",
            period_bucket="quarterly",
            start_date="2026-01-01",
            end_date="2026-03-31",
            duration_days=89,
            basis="gaap",
            statement_type="income_statement",
            source_ids=["SEC_MSFT_Q3_2026"],
            confidence="high",
        )
    )
    canonical = CanonicalFinancials(
        ticker="MSFT",
        as_of_date="2026-07-31",
        metrics=metrics,
    )

    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["latest_quarter"] == "FY2026_Q3"
    assert fundamentals["fiscal_period"] == "TTM through FY2026"
    assert fundamentals["current_period_revenue_growth_yoy"] == (
        331_839 - 281_724
    ) / 281_724
    assert fundamentals["current_period_growth_bridges"]["revenue"][
        "formula_id"
    ] == "matching_fiscal_year_yoy_growth"
    assert fundamentals["current_period_growth_bridges"]["revenue"][
        "period_type"
    ] == "annual"


def test_ttm_bridge_subtracts_matching_prior_interim_for_current_q2():
    facts = [
        _fact("revenue", 10, "Q1", "2025-01-01", "2025-03-31", "q1-2025"),
        _fact("revenue", 20, "Q2", "2025-04-01", "2025-06-30", "q2-2025"),
        _fact("revenue", 30, "Q3", "2025-07-01", "2025-09-30", "q3-2025"),
        _fact("revenue", 100, "FY", "2025-01-01", "2025-12-31", "fy-2025"),
        _fact("revenue", 11, "Q1", "2026-01-01", "2026-03-31", "q1-2026"),
        _fact("revenue", 22, "Q2", "2026-04-01", "2026-06-30", "q2-2026"),
    ]

    canonical, _ = build_canonical_financials_from_facts(
        "TEST", "2026-07-24", facts
    )
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["quarterly"]["revenue"] == [30, 40, 11, 22]
    assert sum(fundamentals["quarterly"]["revenue"]) == 103
    assert fundamentals["ttm_bridges"]["revenue"]["operands"] == {
        "annual": 100,
        "prior_interim": 30,
        "current_interim": 33,
    }
    assert fundamentals["latest_fiscal_year"] == "FY2026"
    assert fundamentals["latest_quarter"] == "FY2026_Q2"
    assert fundamentals["fiscal_year_end"] == "12-31"
    assert fundamentals["fiscal_period"] == "TTM through FY2026_Q2"


def test_ttm_bridge_uses_matching_ytd_for_non_calendar_year():
    facts = [
        ParsedFact(
            metric_name="revenue",
            value=100,
            unit="USD",
            period="FY2025",
            fy=2025,
            fp="FY",
            form="10-K",
            filed="2025-10-01",
            start="2024-09-02",
            end="2025-08-31",
            accession="fy-2025",
        ),
        ParsedFact(
            metric_name="revenue",
            value=70,
            unit="USD",
            period="FY2025_Q3",
            fy=2025,
            fp="Q3",
            form="10-Q",
            filed="2025-06-01",
            start="2024-09-02",
            end="2025-05-11",
            accession="q3-2025",
        ),
        ParsedFact(
            metric_name="revenue",
            value=80,
            unit="USD",
            period="FY2026_Q3",
            fy=2026,
            fp="Q3",
            form="10-Q",
            filed="2026-06-01",
            start="2025-09-01",
            end="2026-05-10",
            accession="q3-2026",
        ),
    ]

    canonical, _ = build_canonical_financials_from_facts(
        "COST", "2026-07-31", facts
    )
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["ttm"]["revenue"] == 110
    assert calculate_fundamental_metrics(fundamentals).revenue_ttm == 110
    assert fundamentals["ttm_bridges"]["revenue"]["operands"] == {
        "annual": 100,
        "prior_interim": 70,
        "current_interim": 80,
    }
    assert fundamentals["ttm_bridges"]["revenue"]["period_start"] == "2025-05-12"


def test_ttm_bridge_rejects_standalone_q3_as_ytd_replacement():
    facts = [
        ParsedFact(
            metric_name="revenue",
            value=100,
            unit="USD",
            period="FY2025",
            fy=2025,
            fp="FY",
            form="10-K",
            filed="2025-10-01",
            start="2024-09-02",
            end="2025-08-31",
            accession="fy-2025",
        ),
        ParsedFact(
            metric_name="revenue",
            value=25,
            unit="USD",
            period="FY2025_Q3",
            fy=2025,
            fp="Q3",
            form="10-Q",
            filed="2025-06-01",
            start="2025-02-17",
            end="2025-05-11",
            accession="q3-2025",
        ),
        ParsedFact(
            metric_name="revenue",
            value=30,
            unit="USD",
            period="FY2026_Q3",
            fy=2026,
            fp="Q3",
            form="10-Q",
            filed="2026-06-01",
            start="2026-02-16",
            end="2026-05-10",
            accession="q3-2026",
        ),
    ]

    canonical, _ = build_canonical_financials_from_facts(
        "COST", "2026-07-31", facts
    )
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert "revenue" not in fundamentals["ttm"]
    assert "revenue" not in fundamentals.get("ttm_bridges", {})
    assert calculate_fundamental_metrics(fundamentals).revenue_ttm == 100


def test_ttm_uses_four_reported_contiguous_quarters_before_annual_bridge():
    facts = [
        _fact("revenue", 100, "FY", "2025-01-01", "2025-12-31", "fy-2025"),
        _fact("revenue", 20, "Q2", "2025-04-01", "2025-06-30", "q2-2025"),
        _fact("revenue", 30, "Q3", "2025-07-01", "2025-09-30", "q3-2025"),
        _fact("revenue", 40, "Q4", "2025-10-01", "2025-12-31", "q4-2025"),
        _fact("revenue", 25, "Q1", "2026-01-01", "2026-03-31", "q1-2026"),
    ]

    canonical, _ = build_canonical_financials_from_facts(
        "GENERIC", "2026-07-24", facts
    )
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert fundamentals["quarterly"]["revenue"] == [20, 30, 40, 25]
    bridge = fundamentals["ttm_bridges"]["revenue"]
    assert bridge["formula_id"] == "sum_four_contiguous_quarters"
    assert list(bridge["operands"].values()) == [20, 30, 40, 25]
    assert bridge["period_start"] == "2025-04-01"
    assert bridge["period_end"] == "2026-03-31"
