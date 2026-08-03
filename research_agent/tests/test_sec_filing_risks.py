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


def test_extracts_emphasized_title_case_risks_without_terminal_periods():
    html = """
    <html><body>
      <div><strong>Item 1A. Risk Factors</strong></div>
      <p><strong>Business and Industry Risks</strong></p>
      <p><strong>We Face Intense Competition</strong></p>
      <p>Competition may reduce demand or increase our costs.</p>
      <p><strong>Our Expansion Subjects Us to Additional Risks</strong></p>
      <p>Expansion may strain our resources.</p>
      <p><strong>We Have a Rapidly Evolving Business Model and Our Stock Price Is Highly Volatile</strong></p>
      <p>Market changes could affect our results.</p>
      <div><strong>Item 1B. Unresolved Staff Comments</strong></div>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "We Face Intense Competition",
        "Our Expansion Subjects Us to Additional Risks",
        "We Have a Rapidly Evolving Business Model and Our Stock Price Is Highly Volatile",
    ]


def test_extracts_plain_risk_factor_summary_without_category_titles():
    html = """
    <html><body>
      <div><strong>Item 1A. Risk Factors</strong></div>
      <p><strong>Risk Factor Summary</strong></p>
      <p><strong>Business and Operational Risks</strong></p>
      <p>We may fail to execute our cloud strategy, which could reduce our revenues and profitability.</p>
      <p>Our products may contain errors that could adversely affect customer demand and our reputation.</p>
      <p><strong>Risks Related to Our Common Stock</strong></p>
      <p>Our stock price could become volatile and investors may lose value.</p>
      <p><strong>Business and Operational Risks</strong></p>
      <p>This explanatory narrative may describe a risk but is not a heading.</p>
      <p><strong>Cybersecurity incidents could harm our operations and reputation.</strong></p>
      <div><strong>Item 1B. Unresolved Staff Comments</strong></div>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "We may fail to execute our cloud strategy, which could reduce our revenues and profitability.",
        "Our products may contain errors that could adversely affect customer demand and our reputation.",
        "Our stock price could become volatile and investors may lose value.",
        "Cybersecurity incidents could harm our operations and reputation.",
    ]


def test_extracts_title_case_heading_merged_with_risk_narrative():
    html = """
    <html><body>
      <div><strong>Item 1A. Risk Factors:</strong></div>
      <p><strong>Risks Related to Our Business</strong></p>
      <p>Failure of Innovation Initiatives Could Impact the Long-Term Success of the Company: IBM invests in emerging technologies, and these initiatives may fail to produce sustainable returns.</p>
      <p>Damage to Our Reputation Could Impact the Company’s Business: Negative perceptions could reduce customer demand and make it harder to retain employees.</p>
      <p>Risk Factors Related to IBM Securities: The market value of our securities may fluctuate or decline.</p>
      <p>This narrative contains a caution: ordinary prose may mention risks but is not a title case heading.</p>
      <div><strong>Item 1B. Unresolved Staff Comments</strong></div>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "Failure of Innovation Initiatives Could Impact the Long-Term Success of the Company",
        "Damage to Our Reputation Could Impact the Company’s Business",
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


def test_business_context_keeps_abbreviations_and_cleans_list_markers():
    html = """
    <html><body>
      <p><strong>BUSINESS SUMMARY</strong></p>
      <p>• Subscription fees - Fees charged to customers for streaming services, including fees charged to distributors (i.e. television providers) and direct subscribers.</p>
      <p>◦ The company operates its entertainment products and consumer services through three reportable business segments</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "Subscription fees - Fees charged to customers for streaming services, including fees charged to distributors (i.e. television providers) and direct subscribers.",
        "The company operates its entertainment products and consumer services through three reportable business segments.",
    ]


def test_business_context_skips_fragments_with_unresolved_references():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>Our products are primarily brought to market through direct-store delivery, customer warehouse and distributor networks.</p>
      <p>One customer represented 14 percent of sales. The loss of this customer would have a material adverse effect on our food and beverage segments.</p>
      <p>The reportable business segments are North America Foods, North America Beverages and International Markets.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "Our products are primarily brought to market through direct-store delivery, customer warehouse and distributor networks.",
        "The reportable business segments are North America Foods, North America Beverages and International Markets.",
    ]


def test_business_context_prefers_business_and_segments_over_transition_or_accounting_text():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>Starbucks is a specialty coffee retailer operating in 89 markets. Formed in 1985, its shares trade on Nasdaq. We purchase and roast high-quality coffees that we sell with handcrafted beverages and food through company-operated stores.</p>
      <p>Therefore, one of our core strategies is to support our partners in the competitive specialty coffee market:</p>
      <p><strong>SEGMENT FINANCIAL INFORMATION</strong></p>
      <p>Segment information is prepared on the same basis that our Chief Operating Decision Maker evaluates financial results and makes key operating decisions.</p>
      <p>We have three reportable operating segments: 1) North America; 2) International; and 3) Channel Development.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We purchase and roast high-quality coffees that we sell with handcrafted beverages and food through company-operated stores.",
        "We have three reportable operating segments: North America; International; and Channel Development.",
    ]


def test_business_context_prefers_complete_segment_subject_over_orphan_detail():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>We operate retail and ecommerce businesses serving customers through stores and digital channels.</p>
      <p>Our operations comprise three reportable segments: Walmart U.S., Walmart International and Sam's Club U.S.</p>
      <p>As a membership-only club, membership income is a significant component of the segment's operating income.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We operate retail and ecommerce businesses serving customers through stores and digital channels.",
        "Our operations comprise three reportable segments: Walmart U.S., Walmart International and Sam's Club U.S.",
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
