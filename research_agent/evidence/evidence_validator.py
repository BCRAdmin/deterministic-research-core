from __future__ import annotations

from collections import Counter
from typing import Optional

from research_agent.evidence.citation_policy import requires_primary_source
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.evidence.source_ranker import is_vendor_source
from research_agent.research_core.models.claims import ResearchClaim


PRIMARY_METRIC_WORDS = {
    "revenue",
    "free_cash_flow",
    "fcf",
    "operating_income",
    "net_income",
    "eps",
    "guidance",
    "sbc",
    "cash",
    "debt",
}


def validate_metric_evidence(metric_name: str, ledger: EvidenceLedger):
    items = ledger.find_by_metric(metric_name)
    if not items:
        return {
            "severity": "error",
            "code": "MISSING_EVIDENCE_FOR_METRIC",
            "metric": metric_name,
            "message": f"No evidence found for metric {metric_name}.",
        }

    if requires_primary_source(metric_name, "financial_metric"):
        if not any(item.authority_rank <= 2 for item in items):
            return {
                "severity": "warning",
                "code": "NO_PRIMARY_EVIDENCE_FOR_HARD_METRIC",
                "metric": metric_name,
                "message": f"{metric_name} has no primary or high-authority evidence.",
            }

    return None


def validate_vendor_not_primary(metric_name: str, ledger: EvidenceLedger):
    items = ledger.find_by_metric(metric_name)
    if not items:
        return None
    vendor_items = [item for item in items if is_vendor_source(item.source_type)]
    authoritative_non_vendor = any(
        item.authority_rank <= 2 and not is_vendor_source(item.source_type)
        for item in items
    )
    if (
        vendor_items
        and not authoritative_non_vendor
        and requires_primary_source(metric_name, "financial_metric")
    ):
        return {
            "severity": "warning",
            "code": "VENDOR_SOURCE_USED_AS_PRIMARY",
            "metric": metric_name,
            "message": f"{metric_name} relies on vendor-level evidence and must not be treated as primary.",
        }
    return None


def validate_news_event_date(item: EvidenceItem):
    if item.claim_type in {"news", "event"} and not item.date:
        return {
            "severity": "warning",
            "code": "MISSING_DATE_FOR_NEWS_EVENT",
            "message": f"Evidence item {item.evidence_id} is a news/event claim without a publication date.",
        }
    return None


def validate_guidance_consensus_separation(ledger: EvidenceLedger):
    guidance_items = ledger.find_by_metric("company_guidance_eps")
    consensus_items = ledger.find_by_metric("consensus_forward_eps")
    if not guidance_items or not consensus_items:
        return None
    conflated = [
        item for item in guidance_items for other in consensus_items if item.evidence_id == other.evidence_id
    ]
    if conflated:
        return {
            "severity": "error",
            "code": "GUIDANCE_CONSENSUS_CONFLATION",
            "metric": "forward_eps",
            "message": "Company guidance EPS and consensus forward EPS use the same evidence item.",
        }
    return None


def validate_claim_has_evidence(claim: ResearchClaim, ledger: EvidenceLedger):
    referenced_ids = [
        str(evidence_id).strip()
        for evidence_id in claim.evidence_ids
        if str(evidence_id).strip()
    ]
    if referenced_ids:
        ledger_id_counts = Counter(
            item.evidence_id for item in ledger.evidence_items
        )
        invalid_ids = [
            evidence_id
            for evidence_id in referenced_ids
            if ledger_id_counts[evidence_id] != 1
        ]
        if not invalid_ids:
            return None
        return {
            "severity": "error",
            "code": "MISSING_EVIDENCE_FOR_CLAIM",
            "evidence_ids": sorted(set(invalid_ids)),
            "message": (
                "ResearchClaim references missing or non-unique EvidenceItems."
            ),
        }
    for metric in claim.evidence_metrics:
        if ledger.find_by_metric(metric):
            return None
    return {
        "severity": "error",
        "code": "MISSING_EVIDENCE_FOR_CLAIM",
        "message": "ResearchClaim has no mapped EvidenceItem.",
    }


def validate_ledger(
    ledger: EvidenceLedger,
    required_metrics: Optional[list[str]] = None,
    claims: Optional[list[ResearchClaim]] = None,
) -> list[dict]:
    issues: list[dict] = []
    for metric in required_metrics or []:
        issue = validate_metric_evidence(metric, ledger)
        if issue:
            issues.append(issue)
        vendor_issue = validate_vendor_not_primary(metric, ledger)
        if vendor_issue:
            issues.append(vendor_issue)
    for item in ledger.evidence_items:
        issue = validate_news_event_date(item)
        if issue:
            issues.append(issue)
    guidance_issue = validate_guidance_consensus_separation(ledger)
    if guidance_issue:
        issues.append(guidance_issue)
    for claim in claims or []:
        issue = validate_claim_has_evidence(claim, ledger)
        if issue:
            issues.append(issue)
    return issues
