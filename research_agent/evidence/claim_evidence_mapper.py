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


def bind_evidence_claim_ids(claims, ledger: EvidenceLedger) -> None:
    """Build exact claim→evidence reverse edges from explicit claim bindings.

    Category tags are deliberately not accepted here.  The operation replaces
    previous edges, making repeated pipeline runs idempotent instead of
    accumulating stale relationships.
    """

    by_id: dict[str, object] = {}
    for item in ledger.evidence_items:
        if item.evidence_id in by_id:
            raise ValueError(f"duplicate evidence_id: {item.evidence_id}")
        by_id[item.evidence_id] = item
        item.supports_claim_ids = []
        item.supports_claims = []
    for claim in claims:
        claim_id = str(getattr(claim, "claim_id", "") or "").strip()
        if not claim_id:
            raise ValueError("research claim has no stable claim_id")
        evidence_ids = list(dict.fromkeys(
            str(value).strip()
            for value in getattr(claim, "evidence_ids", []) or []
            if str(value).strip()
        ))
        if not evidence_ids:
            raise ValueError(f"research claim {claim_id} has no explicit evidence_ids")
        for evidence_id in evidence_ids:
            item = by_id.get(evidence_id)
            if item is None:
                raise ValueError(
                    f"research claim {claim_id} references missing evidence {evidence_id}"
                )
            item.supports_claim_ids = sorted(
                set(item.supports_claim_ids) | {claim_id}
            )
            item.supports_claims = list(item.supports_claim_ids)


def validate_claim_evidence_graph(claims, ledger: EvidenceLedger) -> dict:
    """Return atomic graph evidence and fail on any asymmetric edge."""

    claim_list = list(claims)
    expected = {
        (str(claim.claim_id), str(evidence_id))
        for claim in claim_list
        for evidence_id in claim.evidence_ids
    }
    actual = {
        (str(claim_id), item.evidence_id)
        for item in ledger.evidence_items
        for claim_id in item.supports_claim_ids
    }
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise ValueError(
            "claim/evidence graph is asymmetric: "
            f"missing={missing[:5]} extra={extra[:5]}"
        )
    return {
        "contract_id": "room16.claim_evidence_graph_integrity",
        "contract_version": 1,
        "status": "pass",
        "claim_count": len(claim_list),
        "edge_count": len(expected),
        "missing_edges": [],
        "extra_edges": [],
    }


def validate_visible_citation_completeness(markdown: str, claims) -> dict:
    """Require a complete evidence join beside every rendered material claim."""

    missing: list[dict[str, str]] = []
    checked = 0
    for claim in claims:
        claim_id = str(getattr(claim, "claim_id", "") or "")
        claim_text = str(
            getattr(claim, "claim_text", None)
            or getattr(claim, "claim", "")
            or ""
        ).strip()
        if not claim_id or not claim_text:
            continue
        anchor = claim_text[: min(len(claim_text), 90)]
        position = markdown.find(anchor)
        if position < 0:
            continue
        checked += 1
        paragraph_end = markdown.find("\n\n", position)
        paragraph = markdown[position : paragraph_end if paragraph_end >= 0 else len(markdown)]
        if claim_id not in paragraph:
            missing.append({"claim_id": claim_id, "missing": "claim_id"})
        for evidence_id in getattr(claim, "evidence_ids", []) or []:
            if str(evidence_id) not in paragraph:
                missing.append(
                    {"claim_id": claim_id, "missing": str(evidence_id)}
                )
    if missing:
        raise ValueError(
            "visible citation completeness failed: "
            + ", ".join(
                f"{item['claim_id']}->{item['missing']}" for item in missing[:12]
            )
        )
    return {
        "contract_id": "room16.visible_citation_completeness",
        "contract_version": 1,
        "status": "pass",
        "rendered_claim_count": checked,
        "missing_bindings": [],
    }
