import pytest

from research_agent.evidence.claim_evidence_mapper import (
    bind_evidence_claim_ids,
    map_claim_to_evidence,
    validate_claim_evidence_graph,
    validate_visible_citation_completeness,
)
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


def test_reverse_claim_edges_are_rebuilt_exactly_and_stale_edges_are_removed():
    claim = ResearchClaim(
        claim_id="CLAIM-001",
        agent="fundamental",
        claim="Current revenue is source-bound.",
        evidence_metrics=["revenue_ttm"],
        evidence_ids=["EVIDENCE-001"],
        source_ids=["SOURCE-001"],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="WM",
        as_of_date="2026-08-11",
        evidence_items=[
            EvidenceItem(
                evidence_id="EVIDENCE-001",
                ticker="WM",
                claim_type="financial_metric",
                source_id="SOURCE-001",
                source_type="sec_filing",
                authority_rank=1,
                statement="Revenue evidence.",
                supports_metrics=["revenue_ttm"],
                supports_claim_ids=["STALE-CLAIM"],
            )
        ],
    )

    bind_evidence_claim_ids([claim], ledger)
    report = validate_claim_evidence_graph([claim], ledger)

    assert ledger.evidence_items[0].supports_claim_ids == ["CLAIM-001"]
    assert report["edge_count"] == 1


def test_visible_citation_gate_blocks_truncated_evidence_join():
    claim = ResearchClaim(
        claim_id="CLAIM-001",
        agent="fundamental",
        claim="Current revenue is source-bound.",
        evidence_metrics=["revenue_ttm"],
        evidence_ids=["EVIDENCE-001", "EVIDENCE-002"],
        source_ids=["SOURCE-001"],
        confidence="high",
    )
    markdown = (
        "Current revenue is source-bound. Evidence: `CLAIM-001, EVIDENCE-001`."
    )

    with pytest.raises(ValueError, match="EVIDENCE-002"):
        validate_visible_citation_completeness(markdown, [claim])


def test_visible_citation_gate_accepts_later_bound_duplicate_text():
    claim = ResearchClaim(
        claim_id="CLAIM-001",
        agent="fundamental",
        claim="Current revenue is source-bound.",
        evidence_metrics=["revenue_ttm"],
        evidence_ids=["EVIDENCE-001"],
        source_ids=["SOURCE-001"],
        confidence="high",
    )
    markdown = (
        "Current revenue is source-bound. This is an unbound source excerpt.\n\n"
        "Current revenue is source-bound. Evidence: `CLAIM-001`, `EVIDENCE-001`."
    )

    report = validate_visible_citation_completeness(markdown, [claim])

    assert report["status"] == "pass"


def test_visible_citation_gate_distinguishes_claims_with_long_shared_prefix():
    shared = (
        "Issuer-filed business context: Our revenues from volume excluding "
        "acquisitions and divestitures "
    )
    current = ResearchClaim(
        claim_id="WM_CLAIM_018",
        agent="deterministic_content_generator",
        claim=shared + "decreased in the current quarter.",
        claim_text=shared + "decreased in the current quarter.",
        section="Business & Segment Context",
        claim_type="news",
        evidence_ids=["E_CURRENT"],
        evidence_metrics=["operating_kpi_volume_current"],
        source_ids=["S_CURRENT"],
        confidence="high",
    )
    annual = ResearchClaim(
        claim_id="WM_CLAIM_022",
        agent="deterministic_content_generator",
        claim=shared + "increased in fiscal 2025.",
        claim_text=shared + "increased in fiscal 2025.",
        section="Business & Segment Context",
        claim_type="news",
        evidence_ids=["E_ANNUAL"],
        evidence_metrics=["operating_kpi_volume_annual"],
        source_ids=["S_ANNUAL"],
        confidence="high",
    )
    markdown = (
        f"{current.claim_text} <!-- room16-lineage claim=WM_CLAIM_018 evidence=E_CURRENT -->\n\n"
        f"{annual.claim_text} <!-- room16-lineage claim=WM_CLAIM_022 evidence=E_ANNUAL -->"
    )

    report = validate_visible_citation_completeness(markdown, [current, annual])

    assert report["status"] == "pass"


def test_visible_citation_gate_accepts_hidden_table_lineage():
    markdown = """| Metric | Value |
|---|---:|
| Revenue | $100 million |

<!-- room16-table-lineage id=REVENUE_TABLE evidence=EVIDENCE-001 -->
"""
    ledger = EvidenceLedger(
        ticker="WM",
        as_of_date="2026-08-11",
        evidence_items=[
            EvidenceItem(
                evidence_id="EVIDENCE-001",
                ticker="WM",
                claim_type="financial_metric",
                source_id="SOURCE-001",
                source_type="sec_filing",
                authority_rank=1,
                statement="Revenue evidence.",
                supports_metrics=["revenue_ttm"],
            )
        ],
    )

    report = validate_visible_citation_completeness(markdown, [], ledger)

    assert report["rendered_material_table_count"] == 1
