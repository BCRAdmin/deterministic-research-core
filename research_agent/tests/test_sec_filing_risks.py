from research_agent.sources.sec.sec_filing_risks import (
    build_sec_risk_evidence,
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
