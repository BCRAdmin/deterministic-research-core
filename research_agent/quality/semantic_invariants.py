"""Atomic semantic release invariants for Room16 authority artifacts."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def verify_semantic_invariants(
    *,
    fact_ledger: Mapping[str, Any],
    evidence_ledger: Any,
    source_registry: Any,
    claims: Iterable[Any],
    decision_packet: Any,
    material_events: Iterable[Any] = (),
) -> dict[str, Any]:
    claim_list = list(claims)
    event_list = list(material_events)
    checks: list[dict[str, Any]] = []

    def check(check_id: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "pass" if passed else "fail",
                "blocking": True,
                "detail": detail,
            }
        )

    facts = list(fact_ledger.get("claims") or [])
    check(
        "typed_fact_units",
        all(
            fact.get("dimension") not in {None, "unknown"}
            and bool(fact.get("display_unit"))
            and (fact.get("dimension") != "currency" or bool(fact.get("currency")))
            for fact in facts
        ),
        "Every material fact has a dimension, display unit and ISO currency when monetary.",
    )
    check(
        "typed_fact_periods",
        all(_fact_period_valid(fact) for fact in facts),
        "Period kind, presentation basis and current/comparison bounds are mutually consistent.",
    )
    check(
        "semantic_metric_names",
        all(
            not str(fact.get("metric") or "").startswith("filing_")
            or "_unmapped_" not in str(fact.get("metric") or "")
            for fact in facts
        ),
        "No unmapped positional filing metric is promoted into the canonical fact ledger.",
    )
    check(
        "source_fact_value_normalization",
        all(_fact_value_matches_source_contract(fact) for fact in facts),
        "Every promoted source value preserves its declared scale and direction.",
    )
    check(
        "fact_evidence_is_claim_bound",
        all(
            set(fact.get("evidence_ids") or []).issubset(
                set(fact.get("claim_bound_evidence_ids") or [])
            )
            for fact in facts
        ),
        "A fact may use only evidence explicitly bound to the originating claim.",
    )

    evidence_items = list(evidence_ledger.evidence_items)
    claim_ids = {str(claim.claim_id) for claim in claim_list if claim.claim_id}
    evidence_edges = {
        (claim_id, item.evidence_id)
        for item in evidence_items
        for claim_id in item.supports_claim_ids
    }
    claim_edges = {
        (str(claim.claim_id), str(evidence_id))
        for claim in claim_list
        for evidence_id in claim.evidence_ids
    }
    check(
        "claim_evidence_edge_equality",
        evidence_edges == claim_edges,
        f"claim_edges={len(claim_edges)} evidence_reverse_edges={len(evidence_edges)}",
    )
    check(
        "evidence_claim_foreign_keys",
        all(
            claim_id in claim_ids
            for item in evidence_items
            for claim_id in item.supports_claim_ids
        ),
        "Every supports_claim_id resolves to a real analyst claim.",
    )
    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    check(
        "claim_evidence_selectivity",
        all(
            all(
                evidence_id in evidence_by_id
                and (
                    evidence_by_id[evidence_id].value is None
                    or bool(
                        set(evidence_by_id[evidence_id].supports_metrics).intersection(
                            set(claim.metric_refs or claim.metric_values)
                        )
                    )
                )
                for evidence_id in claim.evidence_ids
            )
            for claim in claim_list
            if getattr(claim, "metric_values", None)
        ),
        "Every numeric evidence edge supports a metric actually used by that claim.",
    )
    check(
        "material_event_numeric_cardinality",
        all(
            len(getattr(event, "numeric_evidence", []) or [])
            == len(
                {
                    item.metric_name
                    for item in (getattr(event, "numeric_evidence", []) or [])
                }
            )
            for event in event_list
        ),
        "No material source number is lost through a duplicate metric key.",
    )

    expected_source_edges = {
        (str(source_id), str(claim.claim_id))
        for claim in claim_list
        for source_id in claim.source_ids
    }
    registry_edges = {
        (source.source_id, claim_id)
        for source in source_registry.sources
        for claim_id in source.claim_ids
    }
    check(
        "claim_source_edge_equality",
        expected_source_edges == registry_edges,
        f"claim_source_edges={len(expected_source_edges)} registry_reverse_edges={len(registry_edges)}",
    )

    required_state_fields = (
        "content_complete",
        "dependency_status",
        "report_disposition",
        "report_disposition_reason",
        "materiality_rationale",
    )
    check(
        "material_event_state_non_null",
        all(
            all(getattr(event, field, None) not in {None, ""} for field in required_state_fields)
            for event in event_list
        ),
        "Required material-event state survives ingestion into the data packet.",
    )
    check(
        "material_event_state_consistent",
        all(
            getattr(event, "content_complete", None) is True
            and getattr(event, "dependency_status", None) == "complete"
            and getattr(event, "report_disposition", None)
            not in {"blocked_incomplete", "unresolved", "unknown"}
            for event in event_list
        ),
        "Every promoted material event is complete and has a non-blocking report disposition.",
    )
    check(
        "leadership_materiality_reason_consistent",
        all(
            not (
                getattr(event, "event_type", None) == "leadership_change"
                and getattr(event, "material", True) is True
                and "routine compensation" in str(
                    getattr(event, "report_disposition_reason", "") or ""
                ).casefold()
            )
            for event in event_list
        ),
        "A substantive leadership event cannot be dispositioned as routine compensation.",
    )

    permission = decision_packet.rating_permission
    discriminating = (
        permission.permission_type == "safety_fallback"
        or len(permission.allowed_ratings) > 1
    )
    check(
        "rating_policy_not_singleton",
        discriminating,
        "A singleton policy corridor must not masquerade as an analytical rating.",
    )
    check(
        "calibration_status_honest",
        decision_packet.calibration_mode
        in {
            "standardized_uncalibrated",
            "company_calibrated",
            "backtested",
            "shadow",
        },
        f"calibration_mode={decision_packet.calibration_mode}",
    )
    material_risk_ids = {
        event.source_id
        for event in event_list
        if event.event_type
        in {
            "risk",
            "filing_legal_contingencies",
            "cyber_incident",
            "operational_disruption",
            "product_recall",
        }
    }
    decision_input_ids = {item.input_id for item in decision_packet.decision_inputs}
    check(
        "current_risk_decision_lineage",
        material_risk_ids.issubset(decision_input_ids),
        f"risk_ids={len(material_risk_ids)} decision_inputs={len(decision_input_ids)}",
    )

    failures = [item["check_id"] for item in checks if item["status"] != "pass"]
    report = {
        "contract_id": "room16.semantic_invariant_report",
        "contract_version": 2,
        "status": "pass" if not failures else "fail",
        "semantic_integrity_passed": not failures,
        "internally_reviewable": not failures,
        "release_candidate": False,
        "publication_allowed": False,
        "release_allowed": False,
        "checks": checks,
        "blocking_failures": failures,
    }
    return report


def _fact_value_matches_source_contract(fact: Mapping[str, Any]) -> bool:
    raw = fact.get("source_value")
    scale = str(fact.get("source_scale") or "").casefold()
    sign = fact.get("source_sign")
    if raw is None or not scale:
        return True
    multiplier = {
        "base": 1.0,
        "percent": 0.01,
        "basis_points": 1.0,
        "thousand": 1_000.0,
        "k": 1_000.0,
        "million": 1_000_000.0,
        "mn": 1_000_000.0,
        "m": 1_000_000.0,
        "billion": 1_000_000_000.0,
        "bn": 1_000_000_000.0,
    }.get(scale)
    if multiplier is None:
        return True
    expected = float(raw) * multiplier * float(sign or 1)
    actual = float(fact.get("value"))
    return abs(expected - actual) <= max(1e-9, abs(expected) * 1e-9)


def _fact_period_valid(fact: Mapping[str, Any]) -> bool:
    kind = fact.get("period_kind")
    basis = fact.get("presentation_basis")
    if kind == "instant":
        return basis == "point_in_time" and bool(fact.get("period_end"))
    if kind == "duration":
        return (
            basis in {"period_total", "period_average"}
            and bool(fact.get("period_start"))
            and bool(fact.get("period_end"))
        )
    if kind == "comparison":
        return (
            basis == "period_over_period_comparison"
            and fact.get("period_start") == fact.get("current_period_start")
            and fact.get("period_end") == fact.get("current_period_end")
            and all(
                fact.get(key)
                for key in (
                    "current_period_start",
                    "current_period_end",
                    "comparison_period_start",
                    "comparison_period_end",
                )
            )
        )
    if kind == "trailing_twelve_months":
        return basis == "trailing_twelve_months"
    if kind == "guidance":
        return basis == "guidance_range"
    return False
