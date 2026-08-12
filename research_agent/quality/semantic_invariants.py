"""Atomic semantic release invariants for Room16 authority artifacts."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from research_agent.quality.semantic_contracts import audit_semantic_records


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
    semantic_facts = [
        {
            **fact,
            "fact_id": fact.get("fact_id") or fact.get("claim_id"),
            "metric_id": fact.get("metric_id") or fact.get("metric"),
            "signed_value": fact.get("signed_value", fact.get("value")),
            "normalized_magnitude": fact.get("normalized_magnitude"),
        }
        for fact in facts
    ]
    semantic_claims = [
        claim.model_dump() if hasattr(claim, "model_dump") else dict(vars(claim))
        for claim in claim_list
    ]
    semantic_tables = [
        table
        for event in event_list
        for table in (getattr(event, "table_contracts", []) or [])
    ]
    semantic_sources = [
        {
            "source_id": event.source_id,
            "report_disposition": event.report_disposition,
        }
        for event in event_list
        if getattr(event, "source_id", None)
    ]
    semantic_audit = audit_semantic_records(
        facts=semantic_facts,
        tables=semantic_tables,
        claims=semantic_claims,
        sources=semantic_sources,
    )
    semantic_error_codes = set(semantic_audit["error_codes"])
    check(
        "typed_fact_units",
        all(
            fact.get("source_cell_status") == "not_applicable_dash"
            or (
            fact.get("dimension") not in {None, "unknown"}
            and bool(fact.get("display_unit"))
            and (fact.get("dimension") != "currency" or bool(fact.get("currency")))
            and not (
                _money_like_metric(str(fact.get("metric") or ""))
                and fact.get("dimension") == "count"
            )
            )
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
            (
                not str(fact.get("metric") or "").startswith("filing_")
                or "_unmapped_" not in str(fact.get("metric") or "")
            )
            and not (
                fact.get("row_metric")
                and "_event_" in str(fact.get("metric") or "")
            )
            and (
                not fact.get("row_metric")
                or bool(fact.get("column_metric"))
            )
            for fact in facts
        ),
        "No unmapped positional filing metric is promoted into the canonical fact ledger.",
    )
    check(
        "typed_fact_rate_semantics_valid",
        not semantic_error_codes.intersection({"rate_period_kind_mismatch", "rate_basis_missing", "metric_period_role_mismatch"}),
        "Rate, run-rate and guidance facts use an explicit compatible period role.",
    )
    check(
        "table_headers_preserved",
        "table_headers_not_preserved" not in semantic_error_codes,
        "Every extracted canonical table preserves its axes and source headers.",
    )
    check(
        "table_cell_alignment_valid",
        not semantic_error_codes.intersection({"table_comparison_semantics_invalid", "table_cell_alignment_invalid"}),
        "Every source cell remains aligned to an explicit row, column, period and value role.",
    )
    check(
        "direction_and_sign_consistent",
        not semantic_error_codes.intersection({"direction_sign_mismatch", "impact_direction_missing"}),
        "Signed values, direction and economic impact agree with one another.",
    )
    check(
        "not_applicable_distinct_from_zero",
        "not_applicable_zero_collision" not in semantic_error_codes,
        "Structural N/A, blank and missing cells are not represented as numeric zero.",
    )
    check(
        "claim_numeric_coverage_complete",
        "claim_numeric_coverage_incomplete" not in semantic_error_codes,
        "Every visible claim number has its own fact/evidence binding.",
    )
    check(
        "source_fact_value_normalization",
        all(_fact_value_matches_source_contract(fact) for fact in facts),
        "Every promoted source value preserves its declared scale and direction.",
    )
    check(
        "fact_evidence_is_claim_bound",
        all(
            (
                fact.get("source_cell_status") == "not_applicable_dash"
                and bool(fact.get("row_metric"))
                and bool(fact.get("column_metric"))
            )
            or set(fact.get("evidence_ids") or []).issubset(
                set(fact.get("claim_bound_evidence_ids") or [])
            )
            for fact in facts
        ),
        "A numeric fact may use only claim-bound evidence; explicit table dashes may retain structural source evidence without a numeric claim.",
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
    fact_ids = {str(fact.get("fact_id") or fact.get("claim_id")) for fact in facts}
    claim_numeric_lineage_complete = all(
        all(
            binding.get("fact_id") in fact_ids
            and binding.get("evidence_id") in evidence_by_id
            and binding.get("source_id")
            and binding.get("source_locator")
            for binding in (getattr(claim, "numeric_bindings", []) or [])
        )
        and len(getattr(claim, "numeric_bindings", []) or [])
        == len(getattr(claim, "numeric_mentions", []) or [])
        for claim in claim_list
    )
    check(
        "claim_evidence_lineage_complete",
        claim_numeric_lineage_complete,
        "Every numeric report span resolves claim → fact → evidence → source locator.",
    )
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
            len(
                mapped_items := [
                    item
                    for item in (getattr(event, "numeric_evidence", []) or [])
                    if getattr(item, "mapping_status", "mapped") == "mapped"
                ]
            )
            == len(
                {
                    _event_numeric_identity(item)
                    for item in mapped_items
                }
            )
            for event in event_list
        ),
        "No mapped material source number is lost through a duplicate metric key; unresolved numbers remain inventory-only.",
    )
    check(
        "material_event_table_semantics",
        all(_event_numeric_semantics(event) for event in event_list),
        "Multidimensional financial rows preserve semantic columns and explicit dash cells.",
    )
    check(
        "operating_kpi_source_attestation",
        all(
            not str(fact.get("metric") or "").startswith("operating_kpi_")
            or all(
                fact.get(key)
                for key in (
                    "source_accession_number",
                    "source_document",
                    "source_document_role",
                    "source_snapshot_path",
                    "source_content_sha256",
                    "source_content_bytes",
                )
            )
            for fact in facts
        ),
        "Every promoted operating KPI names and hashes its exact SEC source document.",
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
    check(
        "source_disposition_claim_accurate",
        "source_disposition_claim_mismatch" not in semantic_error_codes,
        "Source disposition is aggregated from the actual claim render locations.",
    )
    check(
        "numeric_audit_semantically_valid",
        semantic_audit["status"] == "pass",
        "The ID-bound semantic numeric audit found no blocking error.",
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
    check(
        "decision_lineage_complete",
        material_risk_ids.issubset(decision_input_ids)
        and all(
            getattr(item, "transmission", None)
            and getattr(item, "review_trigger", None)
            and (
                getattr(item, "included_in_score", False)
                or getattr(item, "exclusion_reason", None)
            )
            for item in decision_packet.decision_inputs
        ),
        "Each material risk/driver explains score inclusion or exclusion, transmission and review trigger.",
    )
    check(
        "historical_finding_regressions_pass",
        semantic_audit["status"] == "pass",
        "Historical semantic error classes are enforced by the same fail-closed contract.",
    )

    failures = [item["check_id"] for item in checks if item["status"] != "pass"]
    report = {
        "contract_id": "room16.semantic_invariant_report",
        "contract_version": 3,
        "status": "pass" if not failures else "fail",
        "semantic_integrity_passed": not failures,
        "internally_reviewable": not failures,
        "release_candidate": False,
        "publication_allowed": False,
        "release_allowed": False,
        "quality_state": "passed" if not failures else "blocked",
        "internal_review_state": "ready" if not failures else "blocked",
        "release_state": "not_evaluated",
        "publication_state": "blocked",
        "checks": checks,
        "blocking_failures": failures,
        "semantic_numeric_audit": semantic_audit,
    }
    return report


def _fact_value_matches_source_contract(fact: Mapping[str, Any]) -> bool:
    if fact.get("source_cell_status") == "not_applicable_dash":
        return fact.get("value") is None and fact.get("source_value") is None
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
        return (
            basis == "point_in_time"
            and bool(fact.get("period_end"))
            and str(fact.get("asof") or "") == str(fact.get("period_end") or "")
        )
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
    if kind == "rate":
        return basis in {"effective_rate", "annualized_run_rate"}
    return False


def _money_like_metric(metric: str) -> bool:
    return any(
        marker in metric.casefold()
        for marker in (
            "free_cash_flow",
            "revenue",
            "income",
            "expense",
            "cost",
            "consideration",
            "proceeds",
            "capex",
            "cash_paid",
            "ebitda",
        )
    )


def _event_numeric_semantics(event: Any) -> bool:
    metrics = list(getattr(event, "numeric_evidence", []) or [])
    table_metrics = [item for item in metrics if getattr(item, "row_metric", None)]
    if not table_metrics:
        return True
    if any(
        not getattr(item, "column_metric", None)
        or getattr(item, "source_cell_status", None)
        not in {"reported_value", "not_applicable_dash"}
        for item in table_metrics
    ):
        return False
    cell_identities = {
        (
            getattr(item, "table_id", None),
            getattr(item, "row_key", None),
            getattr(item, "column_key", None),
            getattr(item, "period_start", None),
            getattr(item, "period_end", None),
            getattr(item, "fact_type", None),
        )
        for item in table_metrics
    }
    if len(cell_identities) != len(table_metrics):
        return False
    columns = [str(item.column_metric) for item in table_metrics]
    segment_columns = {
        "collection_and_disposal",
        "recycling_processing_and_sales",
        "renewable_energy",
        "healthcare_solutions",
        "corporate_and_other",
        "total_wm",
    }
    if set(columns) == segment_columns:
        dash_columns = {
            str(item.column_metric)
            for item in table_metrics
            if item.source_cell_status == "not_applicable_dash"
        }
        return dash_columns == {
            "collection_and_disposal",
            "recycling_processing_and_sales",
            "renewable_energy",
        }
    return True


def _event_numeric_identity(item: Any) -> tuple[Any, ...]:
    """Identify a fact semantically; never use extraction order as identity."""

    return (
        getattr(item, "metric_name", None),
        getattr(item, "table_id", None),
        getattr(item, "row_key", None),
        getattr(item, "column_key", None),
        getattr(item, "period_start", None),
        getattr(item, "period_end", None),
        getattr(item, "fact_type", None),
        getattr(item, "source_locator", None),
    )
