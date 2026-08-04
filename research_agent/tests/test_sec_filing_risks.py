import pytest

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
      <div>Risk Factors</div><div>Item 2.</div>
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
    filings = select_sec_risk_filing_candidates(_submissions(), cik="1234", as_of_date="2026-07-24")

    assert [filing.form for filing in filings] == ["10-Q", "10-K"]
    assert filings[0].filing_date == "2026-05-07"
    assert filings[0].url.endswith("/000000123426000051/current.htm")


def test_extracts_only_substantive_risk_headings():
    assert extract_sec_risk_headings(_risk_html()) == [
        "If we fail to execute our strategy, our business growth may suffer.",
        "Supply chain interruptions could increase costs or reduce revenue.",
    ]


def test_rejects_lowercase_risk_fragment_from_broken_filing_boundary():
    html = """
    <html><body>
      <div><strong>Item 1A. Risk Factors</strong></div>
      <p><strong>us, our business and results of operations could be adversely affected by disruptions.</strong></p>
      <p><strong>Our business could be adversely affected by intense competition.</strong></p>
      <div><strong>Item 1B. Unresolved Staff Comments</strong></div>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "Our business could be adversely affected by intense competition."
    ]


def test_rejoins_wrapped_workiva_risk_headings():
    html = """
    <html><body>
      <div><strong>Item 1A. Risk Factors</strong></div>
      <div><strong>If we cannot commercialize our medicines, our business could</strong></div>
      <div><strong>be materially harmed.</strong></div>
      <div><strong>Pricing pressure could adversely affect our business,</strong></div>
      <div><strong>revenues, and results of operations.</strong></div>
      <div><strong>Competition may negatively affect our business and market</strong></div>
      <div><strong>position.</strong></div>
      <div><strong>Item 1B. Unresolved Staff Comments</strong></div>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "If we cannot commercialize our medicines, our business could be materially harmed.",
        "Pricing pressure could adversely affect our business, revenues, and results of operations.",
        "Competition may negatively affect our business and market position.",
    ]


def test_rejoins_wrapped_workiva_business_context():
    html = """
    <html><body>
      <div><strong>Item 1. Business</strong></div>
      <div>We are a global biotechnology company that develops medicines for</div>
      <div>people with serious diseases, with a focus on specialty markets.</div>
      <div><strong>Item 1A. Risk Factors</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We are a global biotechnology company that develops medicines for people with serious diseases, with a focus on specialty markets."
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


@pytest.mark.parametrize("summary_heading", ["Risk Factor Summary", "Risk Factors Summary"])
def test_extracts_plain_risk_factor_summary_without_category_titles(summary_heading):
    html = f"""
    <html><body>
      <div><strong>Item 1A. Risk Factors</strong></div>
      <p><strong>{summary_heading}</strong></p>
      <p>For a more complete discussion of the material risks facing our business, see below.</p>
      <p><strong>Business and Operational Risks</strong></p>
      <p>We may fail to execute our cloud strategy, which could reduce our revenues and profitability.</p>
      <p>Our products may contain errors that could adversely affect customer demand and our reputation.</p>
      <p><strong>Risks Related to Our Common Stock</strong></p>
      <p>Our stock price could become volatile and investors may lose value.</p>
      <p><strong>Other Risks Related to our Operations</strong></p>
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


def test_extracts_dash_labeled_risks_from_narrative_heading_not_toc():
    html = """
    <html><body>
      <div>Risk Factors</div><div>24</div>
      <p>ABOUT THE COMPANY. The company manufactures aerospace products and provides aftermarket services.</p>
      <p>RISK FACTORS. The following discussion describes material factors that may make an investment risky.</p>
      <p>STRATEGIC RISKS. Strategic risk relates to future business plans.</p>
      <p>Commercial aviation sector - Our financial performance may be adversely affected by cyclical demand and weaker customers.</p>
      <p>Supply chain - Significant input shortages and supplier disruptions could delay production and increase costs.</p>
      <p>LEGAL PROCEEDINGS. Refer to the financial statement notes.</p>
      <p><strong>COMPONENTS OF DEFERRED TAX ASSETS AND LIABILITIES</strong></p>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "Commercial aviation sector",
        "Supply chain",
    ]


def test_extracts_business_context_from_about_company_heading():
    html = """
    <html><body>
      <p>ABOUT GE AEROSPACE. General Electric Company operates as GE Aerospace. GE Aerospace is a global aerospace leader with a large commercial propulsion fleet.</p>
      <p>SEGMENTS. GE Aerospace operates through two reportable segments: Commercial Engines &amp; Services and Defense &amp; Propulsion Technologies.</p>
      <p>COMMERCIAL ENGINES &amp; SERVICES. The segment designs, develops, manufactures and services jet engines for commercial airframes.</p>
      <p>RISK FACTORS. The following discussion describes material risks.</p>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "GE Aerospace is a global aerospace leader with a large commercial propulsion fleet.",
        "GE Aerospace operates through two reportable segments: Commercial Engines & Services and Defense & Propulsion Technologies.",
        "The segment designs, develops, manufactures and services jet engines for commercial airframes.",
    ]


def test_risk_summary_intro_is_not_a_concrete_risk():
    html = """
    <html><body>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
      <p><strong>The following is a summary of the principal risks that could adversely affect our business, financial condition and results of operations.</strong></p>
      <p><strong>The semiconductor industry is highly cyclical and severe downturns may adversely affect our business.</strong></p>
      <div><strong>ITEM 1B. UNRESOLVED STAFF COMMENTS</strong></div>
    </body></html>
    """

    assert extract_sec_risk_headings(html) == [
        "The semiconductor industry is highly cyclical and severe downturns may adversely affect our business."
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


def test_rejects_generic_risk_section_heading_as_evidence():
    html = """
    <html><body>
      <div><strong>Item 1A. Risk Factors</strong></div>
      <p><strong>General risk factors</strong></p>
      <p>The following discussion describes the principal risks affecting the company.</p>
      <div><strong>Item 1B. Unresolved Staff Comments</strong></div>
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
    assert {event["source_type"] for event in payload["events"]} == {"sec_filing"}
    assert len({event["evidence_id"] for event in payload["events"]}) == 2


def test_business_context_preserves_two_distinct_segment_descriptions():
    html = """
    <html><body>
      <div><strong>ITEM 1. BUSINESS</strong></div>
      <p>We are a global media and technology company that provides connectivity services and creates content and experiences for customers.</p>
      <p>Our Connectivity business is reported in the Residential Connectivity and Business Services segments.</p>
      <p>Our Content business is reported in the Media, Studios and Theme Parks segments.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We are a global media and technology company that provides connectivity services and creates content and experiences for customers.",
        "Our Connectivity business is reported in the Residential Connectivity and Business Services segments.",
        "Our Content business is reported in the Media, Studios and Theme Parks segments.",
    ]


def test_named_issuer_context_deduplicates_segments_and_rejects_risk_category():
    html = """
    <html><body>
      <div><strong>ITEM 1. BUSINESS</strong></div>
      <p>Alphabet is a collection of businesses, the largest of which is Google.</p>
      <p>We report Google in two segments, Google Services and Google Cloud, and all non-Google businesses collectively as Other Bets.</p>
      <p>For reporting purposes Google comprises two segments: Google Services and Google Cloud.</p>
      <p>Google Services products and platforms include ads, Android, Chrome, devices, Search and YouTube for users around the world.</p>
      <div>Risk Factors</div>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
      <p><strong>Risks Specific to our Company</strong></p>
      <p><strong>Reduced advertising spending could harm our business and operating results.</strong></p>
      <div><strong>ITEM 2. PROPERTIES</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "Alphabet is a collection of businesses, the largest of which is Google.",
        "We report Google in two segments, Google Services and Google Cloud, and all non-Google businesses collectively as Other Bets.",
        "Google Services products and platforms include ads, Android, Chrome, devices, Search and YouTube for users around the world.",
    ]
    assert extract_sec_risk_headings(html) == [
        "Reduced advertising spending could harm our business and operating results."
    ]


def test_business_context_prefers_direct_activity_over_orphan_market_reference():
    html = """
    <html><body>
      <div><strong>ITEM 1. BUSINESS</strong></div>
      <p>These markets bring together all of our services with local and global talent and solutions.</p>
      <p>Our three geographic markets are our reporting segments.</p>
      <p>The geographic markets have primary responsibility for building relationships and delivering our full range of solutions and services.</p>
      <p>We help our clients build their digital core using AI, data, cloud products, platforms, solutions and security services.</p>
      <p>We operate business processes for clients across finance, procurement, supply chain, marketing, sales and human resources.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We help our clients build their digital core using AI, data, cloud products, platforms, solutions and security services.",
        "Our three geographic markets are our reporting segments.",
        "We operate business processes for clients across finance, procurement, supply chain, marketing, sales and human resources.",
    ]


def test_business_context_prefers_named_offerings_over_market_segment_fragments():
    html = """
    <html><body>
      <div><strong>ITEM 1. BUSINESS</strong></div>
      <p>Salesforce, Inc. is a global leader in customer relationship management technology.</p>
      <p>Our Agentforce Service offering enables companies to bring customer and field service needs onto one integrated AI-powered platform.</p>
      <p>Our Commerce offering helps connect marketing, sales, service and fulfillment on a single platform.</p>
      <p>Vendors offer software tailored to industries or market segments, including marketing, e-commerce and AI software vendors.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "Salesforce, Inc. is a global leader in customer relationship management technology.",
        "Our Agentforce Service offering enables companies to bring customer and field service needs onto one integrated AI-powered platform.",
        "Our Commerce offering helps connect marketing, sales, service and fulfillment on a single platform.",
    ]


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


def test_business_context_skips_capability_reference_without_its_antecedent():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>Mastercard is a technology company in the global payments industry.</p>
      <p>We operate a payments network that provides choice and flexibility for consumers, merchants and our customers.</p>
      <p>Using these capabilities, we offer consumer and commercial payment products, capture new payment flows and provide services and solutions.</p>
      <p>Driving brand preference by offering differentiated propositions across cards and platforms; expanding distribution across new channels; and growing acceptance.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "Mastercard is a technology company in the global payments industry.",
        "We operate a payments network that provides choice and flexibility for consumers, merchants and our customers.",
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


def test_business_context_prefers_core_logistics_activity_over_technology_detail():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>Our services include transportation and delivery through our integrated air and ground network, distribution, contract logistics, ocean freight, airfreight, customs brokerage and insurance.</p>
      <p>We develop technologies that help customers enhance their shipping and logistics business processes, lowering costs, improving service and increasing efficiency.</p>
      <p>We have two reporting segments: U.S. Domestic Package and International Package.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "Our services include transportation and delivery through our integrated air and ground network, distribution, contract logistics, ocean freight, airfreight, customs brokerage and insurance.",
        "We have two reporting segments: U.S. Domestic Package and International Package.",
    ]


def test_business_context_keeps_concise_issuer_identity_before_generic_detail():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>We are a leading provider of telecommunications and technology services globally. The services and products that we offer vary by market and utilize various technology platforms in a range of geographies.</p>
      <p>The Communications segment provides wireless and wireline telecom and broadband services to consumers located in the United States and businesses globally.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We are a leading provider of telecommunications and technology services globally.",
        "The Communications segment provides wireless and wireline telecom and broadband services to consumers located in the United States and businesses globally.",
    ]


def test_business_context_prefers_revenue_activity_over_promotional_puffery():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>Our customers benefit from what we believe is an unmatched combination of the best value and best network, alongside an unwavering focus on offering them the best possible service experience and an undisputable drive for disruptive innovation in wireless and beyond.</p>
      <p>We work with our customers to understand the service they need to win in their markets and then drive how we win together.</p>
      <p>We generate the majority of our service revenues by providing wireless communications and broadband services to postpaid and prepaid customers.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We generate the majority of our service revenues by providing wireless communications and broadband services to postpaid and prepaid customers."
    ]


def test_business_context_keeps_streaming_identity_segment_and_revenue_model():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>Netflix, Inc. (“Netflix”, the “Company”, “registrant”, “we”, or “us”) is one of the world’s leading entertainment services offering TV series, films, games and live programming.</p>
      <p>We believe an important component of our success is our company culture.</p>
      <p>We operate as one operating segment. Our revenues are primarily derived from monthly membership fees for services related to streaming content to our members.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "Netflix, Inc. (“Netflix”, the “Company”, “registrant”, “we”, or “us”) is one of the world’s leading entertainment services offering TV series, films, games and live programming.",
        "We operate as one operating segment.",
        "Our revenues are primarily derived from monthly membership fees for services related to streaming content to our members.",
    ]


def test_business_context_prefers_identity_and_named_segments_over_summary():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>NVIDIA pioneered accelerated computing to help solve difficult computational problems. NVIDIA is now a data center scale AI infrastructure company.</p>
      <p>We report our business results in two segments.</p>
      <p>The Compute &amp; Networking segment includes accelerated computing and networking platforms, AI solutions and software, and Automotive platforms.</p>
      <p>The Graphics segment includes GPUs for gaming and PCs and workstation graphics products.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "NVIDIA is now a data center scale AI infrastructure company.",
        "The Compute & Networking segment includes accelerated computing and networking platforms, AI solutions and software, and Automotive platforms.",
        "The Graphics segment includes GPUs for gaming and PCs and workstation graphics products.",
    ]


def test_business_context_reads_named_segments_from_filing_list():
    html = """
    <html><body>
      <p><strong>ITEM 1. BUSINESS</strong></p>
      <p>We are a global computing company that develops processors and software platforms for customers.</p>
      <p>Beginning in fiscal year 2025, we combined two former segments into one reportable segment.</p>
      <p>Our three reportable segments are:</p>
      <p>• the Data Center segment, which primarily includes accelerators, server CPUs and networking products;</p>
      <p>• the Client and Gaming segment, which primarily includes CPUs, chipsets and graphics products; and</p>
      <p>• the Embedded segment, which primarily includes embedded CPUs and adaptive products.</p>
      <p>In addition to these reportable segments, we have an All Other category, which is not a reportable segment.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "We are a global computing company that develops processors and software platforms for customers.",
        "the Data Center segment, which primarily includes accelerators, server CPUs and networking products.",
        "the Client and Gaming segment, which primarily includes CPUs, chipsets and graphics products.",
    ]


def test_business_context_supports_combined_resource_company_items():
    html = """
    <html><body>
      <div><strong>ITEMS 1 AND 2. BUSINESS AND PROPERTIES</strong></div>
      <p>ConocoPhillips is an independent E&amp;P company headquartered in Houston, Texas with operations and activities in 14 countries. On December 31, 2025, we employed approximately 9,900 people and had total assets of $122 billion.</p>
      <p>We manage our operations through five operating segments, defined by geographic region: Alaska; Lower 48; Canada; Europe, Middle East and North Africa; and Asia Pacific.</p>
      <p>For operating segment and geographic information, see Note 22.</p>
      <p>We explore for, produce, transport and market crude oil, bitumen, natural gas, NGLs and LNG on a worldwide basis.</p>
      <div><strong>ITEM 1A. RISK FACTORS</strong></div>
    </body></html>
    """

    assert extract_sec_business_context(html) == [
        "ConocoPhillips is an independent E&P company headquartered in Houston, Texas with operations and activities in 14 countries.",
        "We manage our operations through five operating segments, defined by geographic region: Alaska; Lower 48; Canada; Europe, Middle East and North Africa; and Asia Pacific.",
        "We explore for, produce, transport and market crude oil, bitumen, natural gas, NGLs and LNG on a worldwide basis.",
    ]


def test_builds_primary_risk_evidence_without_inventing_numeric_metrics():
    filing = select_sec_risk_filing_candidates(_submissions(), cik="1234", as_of_date="2026-07-24")[
        0
    ]
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
