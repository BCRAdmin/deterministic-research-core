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


def test_claim_keeps_explicit_evidence_binding_instead_of_all_metric_matches():
    claim = ResearchClaim(
        agent="fundamental",
        claim="Current FCF is grounded in the selected calculation.",
        evidence_metrics=["free_cash_flow_ttm"],
        evidence_ids=["CURRENT_DERIVED_FCF"],
        source_ids=["CURRENT_CALCULATION"],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="STALE_EQUAL_FCF",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="OLD_FILING",
                source_type="sec_filing",
                authority_rank=1,
                statement="An older filing reported the same value.",
                supports_metrics=["free_cash_flow_ttm"],
            ),
            EvidenceItem(
                evidence_id="CURRENT_DERIVED_FCF",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="CURRENT_CALCULATION",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement="Current FCF was derived from current inputs.",
                supports_metrics=["free_cash_flow_ttm"],
            ),
        ],
    )

    mapped = map_claim_to_evidence(claim, ledger)

    assert mapped["status"] == "mapped"
    assert mapped["evidence_ids"] == ["CURRENT_DERIVED_FCF"]


def test_missing_explicit_evidence_does_not_fall_back_to_metric_matches():
    claim = ResearchClaim(
        agent="fundamental",
        claim="Current FCF has a missing explicit binding.",
        evidence_metrics=["free_cash_flow_ttm"],
        evidence_ids=["MISSING_CURRENT_FCF"],
        source_ids=["CURRENT_CALCULATION"],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="MDB",
        as_of_date="2026-05-01",
        evidence_items=[
            EvidenceItem(
                evidence_id="OTHER_FCF",
                ticker="MDB",
                claim_type="financial_metric",
                source_id="OTHER_SOURCE",
                source_type="sec_filing",
                authority_rank=1,
                statement="Another FCF item exists.",
                supports_metrics=["free_cash_flow_ttm"],
            )
        ],
    )

    mapped = map_claim_to_evidence(claim, ledger)

    assert mapped["status"] == "missing_evidence"
    assert mapped["evidence_ids"] == []
