"""Explainable shared metric resolver with fail-closed semantic selection."""

from __future__ import annotations

from pydantic import Field

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

from .concept_registry import CONCEPT_REGISTRY, CONCEPT_REGISTRY_SHA256
from .resolution_receipt import MetricResolutionReceipt, RejectedCandidate


class MetricCandidate(StrictModel):
    candidate_id: str
    concept_or_label: str
    source_kind: str
    period_type: str
    period_role: str
    freshness_status: str
    unit: str
    evidence_ids: tuple[str, ...]
    direct: bool = True
    dimensions_compatible: bool = True
    authority_compatible: bool = True
    numeric_value: str | None = None
    semantic_metric_id: str | None = None


RESOLVER_PROFILE = {
    "contract_id": "room16.alpha.shared_metric_resolver_profile",
    "contract_version": 1,
    "concept_registry_sha256": CONCEPT_REGISTRY_SHA256,
    "unsafe_numeric_similarity_matching": False,
    "stale_selection_allowed": False,
    "ambiguous_tie_policy": "AMBIGUOUS",
    "unsupported_over_unsafe_fallback": True,
}
RESOLVER_PROFILE_SHA256 = sha256_json(RESOLVER_PROFILE)


def _family(metric_id: str) -> dict[str, object] | None:
    families = CONCEPT_REGISTRY["families"]
    value = families.get(metric_id) if isinstance(families, dict) else None
    return value if isinstance(value, dict) else None


def resolve_metric(metric_id: str, candidates: tuple[MetricCandidate, ...]) -> MetricResolutionReceipt:
    family = _family(metric_id)
    if family is None:
        return MetricResolutionReceipt.create(
            metric_id=metric_id,
            status="UNSUPPORTED",
            selected_candidate_id_or_null=None,
            selected_concept_or_label=None,
            source_kind=None,
            period_role=None,
            freshness_status=None,
            unit=None,
            score_components={},
            rejected_candidates=(),
            evidence_ids=(),
            resolver_profile_sha256=RESOLVER_PROFILE_SHA256,
        )
    concepts = set(family["concepts"])
    expected_period = family["period_type"]
    units = set(family["units"])
    accepted: list[tuple[int, MetricCandidate]] = []
    rejected: list[RejectedCandidate] = []
    stale_seen = False
    for candidate in sorted(candidates, key=lambda item: item.candidate_id):
        reasons: list[str] = []
        if candidate.semantic_metric_id not in {None, metric_id}:
            reasons.append("SEMANTIC_FAMILY_MISMATCH")
        if candidate.concept_or_label not in concepts:
            reasons.append("CONCEPT_NOT_IN_FAMILY")
        if candidate.period_type != expected_period:
            reasons.append("PERIOD_TYPE_MISMATCH")
        if candidate.unit not in units:
            reasons.append("UNIT_MISMATCH")
        if not candidate.dimensions_compatible:
            reasons.append("DIMENSION_MISMATCH")
        if not candidate.authority_compatible:
            reasons.append("AUTHORITY_MISMATCH")
        if candidate.freshness_status == "STALE":
            reasons.append("STALE")
            stale_seen = True
        if candidate.period_role not in {"CURRENT_PRIMARY", "CURRENT_YTD"}:
            reasons.append("NON_PRIMARY_PERIOD")
        if reasons:
            rejected.append(RejectedCandidate(candidate_id=candidate.candidate_id, reason_codes=tuple(reasons)))
            continue
        score = 100 + (10 if candidate.direct else 0) + (5 if candidate.freshness_status == "CURRENT" else 0)
        accepted.append((score, candidate))
    accepted.sort(key=lambda item: (-item[0], item[1].candidate_id))
    if not accepted:
        status = "STALE_ONLY" if stale_seen else "UNSUPPORTED"
        return MetricResolutionReceipt.create(
            metric_id=metric_id,
            status=status,
            selected_candidate_id_or_null=None,
            selected_concept_or_label=None,
            source_kind=None,
            period_role=None,
            freshness_status="STALE" if stale_seen else None,
            unit=None,
            score_components={},
            rejected_candidates=tuple(rejected),
            evidence_ids=(),
            resolver_profile_sha256=RESOLVER_PROFILE_SHA256,
        )
    top_score = accepted[0][0]
    tied = [candidate for score, candidate in accepted if score == top_score]
    if len(tied) > 1:
        rejected.extend(
            RejectedCandidate(candidate_id=item.candidate_id, reason_codes=("EQUAL_TOP_SCORE",))
            for item in tied
        )
        return MetricResolutionReceipt.create(
            metric_id=metric_id,
            status="AMBIGUOUS",
            selected_candidate_id_or_null=None,
            selected_concept_or_label=None,
            source_kind=None,
            period_role=None,
            freshness_status=None,
            unit=None,
            score_components={"top_score": top_score},
            rejected_candidates=tuple(sorted(rejected, key=lambda item: item.candidate_id)),
            evidence_ids=(),
            resolver_profile_sha256=RESOLVER_PROFILE_SHA256,
        )
    selected = tied[0]
    return MetricResolutionReceipt.create(
        metric_id=metric_id,
        status="RESOLVED",
        selected_candidate_id_or_null=selected.candidate_id,
        selected_concept_or_label=selected.concept_or_label,
        source_kind=selected.source_kind,
        period_role=selected.period_role,
        freshness_status=selected.freshness_status,
        unit=selected.unit,
        score_components={"semantic": 100, "direct": 10 if selected.direct else 0, "fresh": 5 if selected.freshness_status == "CURRENT" else 0},
        rejected_candidates=tuple(rejected),
        evidence_ids=selected.evidence_ids,
        resolver_profile_sha256=RESOLVER_PROFILE_SHA256,
    )
