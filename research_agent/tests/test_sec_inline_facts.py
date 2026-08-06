import json

from research_agent.sources.sec.sec_filing_risks import SecFilingReference
from research_agent.sources.sec.sec_inline_facts import (
    build_sec_inline_debt_supplement_payload,
    build_sec_inline_fact_supplement_payload,
    load_sec_inline_fact_supplement,
    merge_sec_inline_filing_into_companyfacts,
    merge_sec_inline_fact_supplement_payloads,
    save_sec_inline_fact_supplement,
)


def _current_statement_html():
    duration = """
      <xbrli:context id="duration"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    """
    instant = """
      <xbrli:context id="instant"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
    """
    return f"""
    <html><body>{duration}{instant}
      <ix:nonNumeric name="dei:DocumentFiscalYearFocus">2026</ix:nonNumeric>
      <ix:nonNumeric name="dei:DocumentFiscalPeriodFocus">Q2</ix:nonNumeric>
      <ix:nonFraction unitRef="usd" contextRef="duration" name="us-gaap:Revenues" scale="6">1,200</ix:nonFraction>
      <ix:nonFraction unitRef="usd" contextRef="duration" name="us-gaap:OperatingIncomeLoss" scale="6">240</ix:nonFraction>
      <ix:nonFraction unitRef="usd" contextRef="duration" name="us-gaap:NetIncomeLoss" scale="6">180</ix:nonFraction>
      <ix:nonFraction unitRef="usd" contextRef="duration" name="us-gaap:NetCashProvidedByUsedInOperatingActivities" scale="6">210</ix:nonFraction>
      <ix:nonFraction unitRef="usd" contextRef="instant" name="us-gaap:AssetsCurrent" scale="6">3,100</ix:nonFraction>
      <ix:nonFraction unitRef="usd" contextRef="instant" name="us-gaap:LiabilitiesCurrent" scale="6">1,000</ix:nonFraction>
      <ix:nonFraction unitRef="usd" contextRef="instant" name="us-gaap:StockholdersEquity" scale="6">4,200</ix:nonFraction>
    </body></html>
    """


def test_backfills_current_companyfacts_from_exact_inline_filing():
    required = {
        "revenue",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "current_assets",
        "current_liabilities",
        "equity",
    }
    merged, count = merge_sec_inline_filing_into_companyfacts(
        filing=_filing(),
        html=_current_statement_html(),
        companyfacts={"facts": {"us-gaap": {}}},
        required_metrics=required,
    )

    assert count == 7
    revenue = merged["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    assert revenue["val"] == 1_200_000_000
    assert revenue["accn"] == _filing().accession_number
    assert revenue["fp"] == "Q2"
    assert merged["room16_inline_filing_backfills"][0]["fact_count"] == 7


def test_inline_companyfacts_backfill_fails_closed_when_core_metric_is_missing():
    html = _current_statement_html().replace("us-gaap:LiabilitiesCurrent", "example:Other")

    try:
        merge_sec_inline_filing_into_companyfacts(
            filing=_filing(),
            html=html,
            companyfacts={"facts": {"us-gaap": {}}},
            required_metrics={"revenue", "current_liabilities"},
        )
    except ValueError as exc:
        assert "current_liabilities" in str(exc)
    else:
        raise AssertionError("missing core metric must block inline backfill")


def _filing():
    return SecFilingReference(
        cik="1283699",
        form="10-Q",
        filing_date="2026-07-23",
        report_date="2026-06-30",
        accession_number="0001283699-26-000101",
        primary_document="tmus-20260630.htm",
        url="https://www.sec.gov/Archives/example/tmus-20260630.htm",
    )


def _companyfacts(*, with_debt=False):
    facts = {
        "Revenues": {
            "units": {
                "USD": [
                    {
                        "val": 22_790_000_000,
                        "fy": 2026,
                        "fp": "Q2",
                        "form": "10-Q",
                        "filed": "2026-07-23",
                        "start": "2026-04-01",
                        "end": "2026-06-30",
                        "accn": "0001283699-26-000101",
                    }
                ]
            }
        }
    }
    if with_debt:
        facts["LongTermDebtNoncurrent"] = {
            "units": {
                "USD": [
                    {
                        "val": 78_504_000_000,
                        "fy": 2026,
                        "fp": "Q2",
                        "form": "10-Q",
                        "filed": "2026-07-23",
                        "end": "2026-06-30",
                        "accn": "0001283699-26-000101",
                    }
                ]
            }
        }
    return {"facts": {"us-gaap": facts}}


def _html():
    return """
    <html><body>
      <xbrli:context id="current"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:context id="prior"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
      <table>
        <tr><td>Long-term debt</td><td><ix:nonFraction unitRef="usd" contextRef="current" name="us-gaap:LongTermDebtNoncurrent" scale="6">78,504</ix:nonFraction></td><td><ix:nonFraction unitRef="usd" contextRef="prior" name="us-gaap:LongTermDebtNoncurrent" scale="6">79,649</ix:nonFraction></td></tr>
        <tr><td>Long-term debt to affiliates</td><td><ix:nonFraction unitRef="usd" contextRef="current" name="us-gaap:LongTermDebtNoncurrent" format="ixt:fixed-zero" scale="6">—</ix:nonFraction></td></tr>
      </table>
      <table>
        <tr><td>Long-term debt</td><td><ix:nonFraction unitRef="usd" contextRef="current" name="us-gaap:LongTermDebtNoncurrent" scale="6">1,415</ix:nonFraction></td></tr>
      </table>
    </body></html>
    """


def test_recovers_current_liquidity_and_explicit_zero_debt_from_inline_filing():
    html = _current_statement_html().replace(
        "</body>",
        """
        <xbrli:context id="credit"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:CreditFacilityAxis">us-gaap:RevolvingCreditFacilityMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
        <ix:nonFraction unitRef="usd" contextRef="instant" name="us-gaap:OtherShortTermInvestments" scale="6">622</ix:nonFraction>
        <ix:nonFraction unitRef="usd" contextRef="instant" name="us-gaap:MarketableSecurities" scale="6">2,842</ix:nonFraction>
        <p>There were no outstanding borrowings under the credit facility.
        <ix:nonFraction unitRef="usd" contextRef="credit" name="us-gaap:DebtInstrumentCarryingAmount" format="ixt:fixed-zero" scale="6">no</ix:nonFraction></p>
        </body>
        """,
    )
    payload = build_sec_inline_fact_supplement_payload(
        ticker="GENR",
        filing=_filing(),
        html=html,
        companyfacts=_companyfacts(),
        retrieved_at="2026-07-24T00:00:00Z",
        allowed_metrics={
            "short_term_investments",
            "marketable_securities",
            "credit_facility_borrowings",
        },
    )

    assert payload is not None
    values = {item["metric_name"]: item["value"] for item in payload["facts"]}
    assert values == {
        "short_term_investments": 622_000_000.0,
        "marketable_securities": 2_842_000_000.0,
        "credit_facility_borrowings": 0.0,
    }


def test_recovers_first_current_statement_debt_and_preserves_filing_authority(tmp_path):
    payload = build_sec_inline_debt_supplement_payload(
        ticker="TMUS",
        filing=_filing(),
        html=_html(),
        companyfacts=_companyfacts(),
        retrieved_at="2026-08-03T04:00:00+00:00",
    )

    assert payload is not None
    assert payload["facts"][0]["value"] == 78_504_000_000
    path = save_sec_inline_fact_supplement(tmp_path / "TMUS.json", payload)
    facts, evidence = load_sec_inline_fact_supplement(path, ticker="TMUS")
    assert facts[0].metric_name == "debt_noncurrent"
    assert facts[0].end == "2026-06-30"
    assert evidence[0].value == 78_504_000_000
    assert evidence[0].url == _filing().url
    assert json.loads(path.read_text(encoding="utf-8"))["filing"]["form"] == "10-Q"


def test_does_not_duplicate_current_companyfacts_debt():
    assert (
        build_sec_inline_debt_supplement_payload(
            ticker="TMUS",
            filing=_filing(),
            html=_html(),
            companyfacts=_companyfacts(with_debt=True),
            retrieved_at="2026-08-03T04:00:00+00:00",
        )
        is None
    )


def test_sums_current_cover_page_stock_classes_as_economic_shares(tmp_path):
    html = _html().replace(
        "<table>",
        """
        <xbrli:context id="class-a"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-07-15</xbrli:instant></xbrli:period></xbrli:context>
        <xbrli:context id="class-b"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassBMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-07-15</xbrli:instant></xbrli:period></xbrli:context>
        <p>As of July 15, 2026, there were
          <ix:nonFraction unitRef="shares" contextRef="class-a" name="dei:EntityCommonStockSharesOutstanding" scale="0">3,539,192,198</ix:nonFraction>
          Class A shares and
          <ix:nonFraction unitRef="shares" contextRef="class-b" name="dei:EntityCommonStockSharesOutstanding" scale="0">9,444,375</ix:nonFraction>
          Class B shares outstanding.
        </p>
        <table>
        """,
        1,
    )
    payload = build_sec_inline_fact_supplement_payload(
        ticker="CMCSA",
        filing=_filing(),
        html=html,
        companyfacts=_companyfacts(with_debt=True),
        retrieved_at="2026-08-03T04:00:00+00:00",
    )

    assert payload is not None
    assert len(payload["facts"]) == 1
    assert payload["facts"][0]["metric_name"] == "economic_share_count"
    assert payload["facts"][0]["value"] == 3_548_636_573
    assert payload["facts"][0]["end"] == "2026-07-15"
    assert "[MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED]" in (
        payload["facts"][0]["normalization_note"]
    )
    path = save_sec_inline_fact_supplement(tmp_path / "CMCSA.json", payload)
    facts, evidence = load_sec_inline_fact_supplement(path, ticker="CMCSA")
    assert facts[0].metric_name == "economic_share_count"
    assert evidence[0].supports_metrics == ["economic_share_count"]


def test_recovers_exact_current_and_comparative_inline_capex_rows(tmp_path):
    html = """
    <html><body>
      <xbrli:context id="current"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="prior"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="segment"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementBusinessSegmentsAxis">cop:AlaskaMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
      <table>
        <tr><td>Capital expenditures and investments</td><td>(<ix:nonFraction unitRef="usd" contextRef="current" name="cop:PaymentToAcquireProductiveAssetsAndInvestments" scale="6">5,900</ix:nonFraction>)</td><td>(<ix:nonFraction unitRef="usd" contextRef="prior" name="cop:PaymentToAcquireProductiveAssetsAndInvestments" scale="6">6,700</ix:nonFraction>)</td></tr>
        <tr><td>Capital expenditures and investments</td><td><ix:nonFraction unitRef="usd" contextRef="segment" name="cop:SegmentCapitalExpenditures" scale="6">900</ix:nonFraction></td></tr>
      </table>
    </body></html>
    """
    payload = build_sec_inline_fact_supplement_payload(
        ticker="COP",
        filing=_filing(),
        html=html,
        companyfacts=_companyfacts(with_debt=True),
        retrieved_at="2026-08-03T04:00:00+00:00",
        allowed_metrics={"capex"},
    )

    assert payload is not None
    assert [(fact["start"], fact["end"], fact["value"]) for fact in payload["facts"]] == [
        ("2025-01-01", "2025-06-30", 6_700_000_000),
        ("2026-01-01", "2026-06-30", 5_900_000_000),
    ]
    path = save_sec_inline_fact_supplement(tmp_path / "COP.json", payload)
    facts, evidence = load_sec_inline_fact_supplement(path, ticker="COP")
    assert [fact.metric_name for fact in facts] == ["capex", "capex"]
    assert all(item.supports_metrics == ["capex"] for item in evidence)
    assert all(item.url == _filing().url for item in evidence)


def test_does_not_duplicate_current_companyfacts_capex():
    companyfacts = _companyfacts(with_debt=True)
    companyfacts["facts"]["us-gaap"]["PaymentsToAcquireProductiveAssets"] = {
        "units": {
            "USD": [
                {
                    "val": 5_900_000_000,
                    "fy": 2026,
                    "fp": "Q2",
                    "form": "10-Q",
                    "filed": "2026-07-23",
                    "start": "2026-01-01",
                    "end": "2026-06-30",
                    "accn": "0001283699-26-000101",
                }
            ]
        }
    }

    assert (
        build_sec_inline_fact_supplement_payload(
            ticker="COP",
            filing=_filing(),
            html=_html(),
            companyfacts=companyfacts,
            retrieved_at="2026-08-03T04:00:00+00:00",
            allowed_metrics={"capex"},
        )
        is None
    )


def test_merges_inline_facts_with_their_own_filing_authority(tmp_path):
    current = build_sec_inline_fact_supplement_payload(
        ticker="COP",
        filing=_filing(),
        html="""
        <xbrli:context id="current"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
        <table><tr><td>Capital expenditures and investments</td><td><ix:nonFraction unitRef="usd" contextRef="current" name="cop:PaymentToAcquireProductiveAssetsAndInvestments" scale="6">5,900</ix:nonFraction></td></tr></table>
        """,
        companyfacts=_companyfacts(with_debt=True),
        retrieved_at="2026-08-03T04:00:00+00:00",
        allowed_metrics={"capex"},
    )
    annual_filing = SecFilingReference(
        cik="1283699",
        form="10-K",
        filing_date="2026-02-10",
        report_date="2025-12-31",
        accession_number="0001283699-26-000010",
        primary_document="cop-20251231.htm",
        url="https://www.sec.gov/Archives/example/cop-20251231.htm",
    )
    annual_companyfacts = _companyfacts(with_debt=True)
    annual_companyfacts["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(
        {
            "val": 58_000_000_000,
            "fy": 2025,
            "fp": "FY",
            "form": "10-K",
            "filed": "2026-02-10",
            "start": "2025-01-01",
            "end": "2025-12-31",
            "accn": "0001283699-26-000010",
        }
    )
    annual = build_sec_inline_fact_supplement_payload(
        ticker="COP",
        filing=annual_filing,
        html="""
        <xbrli:context id="annual"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:startDate>2025-01-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period></xbrli:context>
        <table><tr><td>Capital expenditures and investments</td><td><ix:nonFraction unitRef="usd" contextRef="annual" name="cop:PaymentToAcquireProductiveAssetsAndInvestments" scale="6">12,600</ix:nonFraction></td></tr></table>
        """,
        companyfacts=annual_companyfacts,
        retrieved_at="2026-08-03T04:00:00+00:00",
        allowed_metrics={"capex"},
    )

    merged = merge_sec_inline_fact_supplement_payloads(current, annual)
    path = save_sec_inline_fact_supplement(tmp_path / "COP-merged.json", merged)
    _facts, evidence = load_sec_inline_fact_supplement(path, ticker="COP")
    assert {item.url for item in evidence} == {
        _filing().url,
        annual_filing.url,
    }
