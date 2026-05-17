from __future__ import annotations

from research_agent.evidence.evidence_ledger import EvidenceLedger


def map_claim_to_evidence(claim, ledger: EvidenceLedger):
    matched = []
    for metric in claim.evidence_metrics:
        matched.extend(ledger.find_by_metric(metric))

    if not matched:
        return {
            "claim_id": getattr(claim, "claim_id", None),
            "evidence_ids": [],
            "status": "missing_evidence",
        }

    evidence_ids = list(dict.fromkeys(item.evidence_id for item in matched))
    return {
        "claim_id": getattr(claim, "claim_id", None),
        "evidence_ids": evidence_ids,
        "status": "mapped",
    }


def map_claims_to_evidence(claims, ledger: EvidenceLedger) -> list[dict]:
    return [map_claim_to_evidence(claim, ledger) for claim in claims]
