from research_agent.sources.ir.earnings_release_parser import parse_earnings_release_evidence
from research_agent.sources.ir.guidance_extractor import extract_eps_guidance, extract_revenue_guidance


def test_extract_eps_guidance_range():
    text = "For FY2027, non-GAAP diluted EPS is expected to be $5.75 to $5.93."

    ranges = extract_eps_guidance(text, period="FY2027")

    assert ranges[0].metric == "company_guidance_eps"
    assert ranges[0].low == 5.75
    assert ranges[0].high == 5.93


def test_extract_revenue_guidance_range():
    text = "Revenue is expected to be $2.50 billion to $2.55 billion."

    ranges = extract_revenue_guidance(text, period="FY2027")

    assert ranges[0].metric == "company_guidance_revenue"
    assert ranges[0].low == 2_500_000_000
    assert ranges[0].high == 2_550_000_000


def test_guidance_parser_produces_evidence_items():
    text = "For FY2027, non-GAAP EPS is expected to be $5.75 to $5.93."

    evidence = parse_earnings_release_evidence(
        ticker="MDB",
        text=text,
        period="FY2027",
        source_id="MDB_IR_Q4_FY2026",
        source_type="earnings_release",
    )

    assert evidence[0].claim_type == "guidance"
    assert evidence[0].source_type == "earnings_release"
    assert evidence[0].authority_rank == 1
    assert "company_guidance_eps" in evidence[0].supports_metrics
