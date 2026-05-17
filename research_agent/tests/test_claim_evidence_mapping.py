from research_agent.evidence.claim_evidence_mapper import map_claim_to_evidence
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.models.claims import ResearchClaim


def test_claim_without_evidence_is_unmapped():
    claim = ResearchClaim(
        agent="fundamental",
        claim="MongoDB has strong FCF generation.",
        evidence_metrics=["free_cash_flow_ttm"],
        source_ids=[],
        confidence="high",
    )
    ledger = EvidenceLedger(ticker="MDB", as_of_date="2026-05-01", evidence_items=[])

    mapped = map_claim_to_evidence(claim, ledger)

    assert mapped["status"] == "missing_evidence"
    assert mapped["evidence_ids"] == []


def test_claim_maps_to_metric_evidence_item():
    claim = ResearchClaim(
        agent="fundamental",
        claim="MongoDB has strong FCF generation.",
        evidence_metrics=["free_cash_flow_ttm"],
        source_ids=[],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="MDB_IR_Q4_FY2026_FREE_CASH_FLOW",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="MDB_IR_Q4_FY2026",
                source_type="company_ir",
                authority_rank=1,
                statement="FY2026 FCF was 492.6M.",
                supports_metrics=["free_cash_flow_ttm"],
            )
        ],
    )

    mapped = map_claim_to_evidence(claim, ledger)

    assert mapped["status"] == "mapped"
    assert mapped["evidence_ids"] == ["MDB_IR_Q4_FY2026_FREE_CASH_FLOW"]
