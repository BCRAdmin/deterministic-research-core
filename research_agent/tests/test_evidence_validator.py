from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.evidence.evidence_validator import (
    validate_guidance_consensus_separation,
    validate_metric_evidence,
    validate_news_event_date,
    validate_vendor_not_primary,
)


def test_missing_evidence_for_hard_metric_is_flagged():
    ledger = EvidenceLedger(ticker="MDB", as_of_date="2026-05-01", evidence_items=[])

    issue = validate_metric_evidence("free_cash_flow", ledger)

    assert issue["code"] == "MISSING_EVIDENCE_FOR_METRIC"


def test_vendor_source_for_hard_metric_warns():
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_VENDOR_FCF",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="zacks_mdb",
                source_type="zacks",
                authority_rank=5,
                statement="FCF was 492.6M.",
                value=492600000,
                unit="usd",
                period="FY2026",
                supports_metrics=["free_cash_flow"],
            )
        ],
    )

    issue = validate_metric_evidence("free_cash_flow", ledger)
    vendor_issue = validate_vendor_not_primary("free_cash_flow", ledger)

    assert issue["code"] == "NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC"
    assert vendor_issue["code"] == "VENDOR_SOURCE_USED_AS_PRIMARY"


def test_news_event_without_date_warns():
    item = EvidenceItem(
        evidence_id="MDB_NEWS_ITEM",
        ticker="MDB",
        claim_type="news",
        source_id="reuters_mdb",
        source_type="reuters",
        authority_rank=3,
        statement="MongoDB announced a product update.",
    )

    issue = validate_news_event_date(item)

    assert issue["code"] == "MISSING_DATE_FOR_NEWS_EVENT"


def test_guidance_and_consensus_are_separate_evidence_items():
    ledger = _build_mdb_fixture_ledger()

    guidance_items = ledger.find_by_metric("company_guidance_eps")
    consensus_items = ledger.find_by_metric("consensus_forward_eps")

    assert validate_guidance_consensus_separation(ledger) is None
    assert guidance_items[0].source_type == "company_ir"
    assert consensus_items[0].source_type in {"finviz", "stockanalysis", "market_data_provider"}


def test_guidance_consensus_conflation_is_flagged():
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_EPS_CONFLATED",
                ticker="MDB",
                claim_type="guidance",
                source_id="mixed_eps",
                source_type="zacks",
                authority_rank=5,
                statement="EPS guidance and consensus were mixed.",
                supports_metrics=["company_guidance_eps", "consensus_forward_eps"],
            )
        ],
    )

    issue = validate_guidance_consensus_separation(ledger)

    assert issue["code"] == "GUIDANCE_CONSENSUS_CONFLATION"


def _build_mdb_fixture_ledger():
    return EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_IR_GUIDANCE_EPS",
                ticker="MDB",
                claim_type="guidance",
                source_id="MDB_IR_Q4_FY2026",
                source_type="company_ir",
                authority_rank=1,
                statement="Company guided FY2027 non-GAAP EPS to 5.75-5.93.",
                period="FY2027",
                supports_metrics=["company_guidance_eps"],
            ),
            EvidenceItem(
                evidence_id="MDB_CONSENSUS_FORWARD_EPS",
                ticker="MDB",
                claim_type="valuation_metric",
                source_id="market_data_provider_mdb",
                source_type="market_data_provider",
                authority_rank=5,
                statement="Consensus FY2027 EPS was 7.05.",
                value=7.05,
                period="FY2027",
                supports_metrics=["consensus_forward_eps"],
            ),
        ],
    )
