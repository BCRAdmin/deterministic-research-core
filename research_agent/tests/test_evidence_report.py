from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.evidence.evidence_report import render_evidence_report, save_evidence_report


def test_evidence_report_markdown_summarizes_sources_and_warnings(tmp_path):
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_IR_REVENUE",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="MDB_IR_Q4_FY2026",
                source_type="company_ir",
                authority_rank=1,
                statement="Revenue was 2.46B.",
                value=2460000000,
                unit="usd",
                supports_metrics=["revenue_ttm"],
            )
        ],
    )

    markdown = render_evidence_report(ledger, required_metrics=["revenue_ttm", "free_cash_flow_ttm"])
    path = save_evidence_report(markdown, tmp_path / "evidence_report.md")

    assert path.exists()
    assert "# Evidence Report - MDB" in markdown
    assert "MDB_IR_Q4_FY2026" in markdown
    assert "2,460,000,000.00 USD" in markdown
    assert "MISSING_EVIDENCE_FOR_METRIC" in markdown


def test_evidence_report_displays_non_us_currency_units():
    ledger = EvidenceLedger(
        ticker="ANY",
        as_of_date="2026-07-27",
        evidence_items=[
            EvidenceItem(
                evidence_id="ANY_REVENUE",
                ticker="ANY",
                claim_type="financial_metric",
                source_id="BSE_ANY_OFFICIAL_FINANCIALS",
                source_type="company_ir",
                authority_rank=1,
                statement="Revenue was reported in HUF.",
                value=65_509_130_000,
                unit="HUF",
                supports_metrics=["revenue_ttm"],
            ),
            EvidenceItem(
                evidence_id="ANY_EPS",
                ticker="ANY",
                claim_type="financial_metric",
                source_id="BSE_ANY_OFFICIAL_FINANCIALS",
                source_type="company_ir",
                authority_rank=1,
                statement="EPS was reported in HUF per share.",
                value=505.32,
                unit="HUF_per_share",
                supports_metrics=["trailing_eps"],
            ),
        ],
    )

    markdown = render_evidence_report(ledger)

    assert "65,509,130,000.00 HUF" in markdown
    assert "505.32 HUF/share" in markdown
