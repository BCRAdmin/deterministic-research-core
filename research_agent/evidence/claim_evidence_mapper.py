from __future__ import annotations

from research_agent.evidence.evidence_ledger import EvidenceLedger


def map_claim_to_evidence(claim, ledger: EvidenceLedger):
    explicit_ids = list(dict.fromkeys(
        str(evidence_id).strip()
        for evidence_id in getattr(claim, "evidence_ids", [])
        if str(evidence_id).strip()
    ))
    if explicit_ids:
        ledger_id_counts: dict[str, int] = {}
        for item in ledger.evidence_items:
            ledger_id_counts[item.evidence_id] = (
                ledger_id_counts.get(item.evidence_id, 0) + 1
            )
        if all(ledger_id_counts.get(evidence_id) == 1 for evidence_id in explicit_ids):
            return {
                "claim_id": getattr(claim, "claim_id", None),
                "evidence_ids": explicit_ids,
                "status": "mapped",
            }
        return {
            "claim_id": getattr(claim, "claim_id", None),
            "evidence_ids": [],
            "status": "missing_evidence",
        }

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
