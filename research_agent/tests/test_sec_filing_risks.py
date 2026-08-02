from research_agent.sources.sec.sec_filing_risks import (
    SecFilingReference,
    build_sec_business_context_payload,
    build_sec_risk_evidence,
    extract_sec_business_context,
    extract_sec_risk_headings,
    select_sec_risk_filing_candidates,
)


def _submissions():
    return {
        "filings": {
            "recent": {
                "form": ["10-Q", "10-Q", "10-K"],
                "filingDate": ["2026-08-05", "2026-05-07", "2026-02-24"],
                "reportDate": ["2026-06-30", "2026-03-31", "2025-12-31"],
                "accessionNumber": [
                    "0000001234-26-000099",
                    "0000001234-26-000051",
                    "0000001234-26-000035",
                ],
                "primaryDocument": ["future.htm", "current.htm", "annual.htm"],
            }
        }
    }


def _risk_html():
    return """
    <html><body>
      <div>Risk Factors</div><div>Item 2. Short table entry</div>
      <div>Risk Factors</div>
      <p>Our business results are subject to a variety of risks described below.</p>
      <p><strong>If we fail to execute our strategy, our business growth may suffer.</strong></p>
      <p>Long explanatory paragraph about strategy execution and operations.</p>
      <p><strong>Supply chain interruptions could increase costs or reduce revenue.</strong></p>
      <p>Long explanatory paragraph about sourcing and distribution.</p>
      <p>• A litigation bullet could create noise but is not a risk heading.</p>
      <div>Item 3. Market Risk</div>
      <p>Changes after the section must not be captured as risks.</p>
    </body></html>
    """


def test_selects_latest_filed_report_without_future_leakage_and_keeps_annual_fallback():
    filings = select_sec_risk_filing_candidates(
        _submissions(), cik="1234", as_of_date="2026-07-24"
    )

    assert [filing.form for filing in filings] == ["10-Q", "10-K"]
    assert filings[0].filing_date == "2026-05-07"
    assert filings[0].url.endswith("/000000123426000051/current.htm")


def test_extracts_only_substantive_risk_headings():
    assert extract_sec_risk_headings(_risk_html()) == [
        "If we fail to execute our strategy, our business growth may suffer.",
        "Supply chain interruptions could increase costs or reduce revenue.",
    ]


def test_extracts_split_risk_heading_across_repeated_item_1a_page_headers():
    html = """
    <html><body>
      <div><strong>ITEM 1A. RIS K FACTORS</strong></div>
      <p><strong>Competition could adversely affect our operating results.</strong></p>
      <div>Item 1A</div>
      <p><strong>Cyberattacks may harm our reputation or competitive position.</strong></p>
      <div>Item 1B. Unresolved Staff Comments</div>
      <p><strong>Later disclosures may adversely affect our business.</strong></p>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "Competition could adversely affect our operating results.",
        "Cyberattacks may harm our reputation or competitive position.",
    ]


def test_rejects_unemphasized_narrative_from_false_risk_section():
    html = """
    <html><body>
      <div>Item 1A.</div><div>Risk Factors.</div><div>42</div>
      <p>Income tax expense may increase because of changes in the level and mix of income.</p>
      <p>Refer to the annual report for a discussion of the factors that could affect credit ratings.</p>
      <div>Item 2. Unregistered Sales of Equity Securities.</div>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == []


def test_extracts_business_context_only_from_annual_item_1():
    html = """
    <html><body>
      <div>Item 1.</div><div>Business</div><div>3</div>
      <div><strong>ITEM 1. B USINESS</strong></div>
      <p>GENERAL</p>
      <p>The issuer employs 12,000 people worldwide. The issuer develops secure software platforms and cloud services for business customers across several markets.</p>
      <p><strong>OPERATING SEGMENTS</strong></p>
      <p>The business operates through Enterprise Platforms, Cloud Services, and Consumer Products segments.</p>
      <div><strong>ITEM 1A. RIS K FACTORS</strong></div>
      <p>Competition could adversely affect operating results.</p>
    </body></html>
    """
    filing = SecFilingReference(
        cik="1234",
        form="10-K",
        filing_date="2026-07-20",
        report_date="2026-06-30",
        accession_number="0000001234-26-000001",
        primary_document="issuer-20260630.htm",
        url="https://www.sec.gov/Archives/example",
    )

    payload = build_sec_business_context_payload(
        ticker="TEST",
        filing=filing,
        html=html,
        retrieved_at="2026-07-21T00:00:00+00:00",
    )

    assert [event["summary"] for event in payload["events"]] == [
        "The issuer develops secure software platforms and cloud services for business customers across several markets.",
        "The business operates through Enterprise Platforms, Cloud Services, and Consumer Products segments.",
    ]
    assert {event["source_type"] for event in payload["events"]} == {
        "sec_filing"
    }
    assert len({event["evidence_id"] for event in payload["events"]}) == 2


def test_extracts_business_context_from_cross_referenced_annual_report():
    html = """
    <html><body>
      <p><strong>BUSINESS SUMMARY</strong></p>
      <p><strong>DESCRIPTION OF THE BUSINESS</strong></p>
      <p>The company is primarily a franchisor, and franchising enables local restaurant operators to serve customers in their communities.</p>
      <p>The reportable business segments are Domestic Markets and International Markets.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
      <p><strong>Competition could adversely affect operating results.</strong></p>
      <div>Form 10-K Cross-Reference Index</div>
      <div>Item 1 Business</div><div>Page 3</div>
      <div>Item 1A Risk Factors</div><div>Page 27</div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "The company is primarily a franchisor, and franchising enables local restaurant operators to serve customers in their communities.",
        "The reportable business segments are Domestic Markets and International Markets.",
    ]


def test_builds_primary_risk_evidence_without_inventing_numeric_metrics():
    filing = select_sec_risk_filing_candidates(
        _submissions(), cik="1234", as_of_date="2026-07-24"
    )[0]
    evidence = build_sec_risk_evidence(
        ticker="TEST",
        filing=filing,
        html=_risk_html(),
        retrieved_at="2026-07-24T12:00:00Z",
    )

    assert len(evidence) == 2
    assert evidence[0].claim_type == "risk"
    assert evidence[0].source_type == "sec_filing"
    assert evidence[0].supports_metrics == []
    assert evidence[0].supports_claims == ["company_risk_analysis"]
