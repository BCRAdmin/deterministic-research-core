"""Atomic semantic release invariants for Room16 authority artifacts."""

from __future__ import annotations

import hashlib
import re
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
    rendered_markdown: str | None = None,
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
    source_tables = [
        table
        for event in event_list
        for table in (getattr(event, "table_contracts", []) or [])
    ]
    rendered_tables = _rendered_markdown_table_contracts(
        rendered_markdown or "",
        facts=semantic_facts,
    )
    semantic_tables = [*source_tables, *rendered_tables]
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
    source_table_ids = {
        str(table.get("table_id") or "")
        for table in source_tables
        if table.get("table_id")
    }
    fact_source_table_ids = {
        str(fact.get("table_id") or "")
        for fact in semantic_facts
        if fact.get("table_id")
    }
    rendered_report_sha256 = (
        "sha256:" + hashlib.sha256(rendered_markdown.encode("utf-8")).hexdigest()
        if rendered_markdown is not None
        else ""
    )
    check(
        "rendered_report_bound",
        rendered_markdown is None or bool(rendered_report_sha256),
        (
            f"canonical_report_sha256={rendered_report_sha256}"
            if rendered_markdown is not None
            else "Pre-render gate; canonical report binding is evaluated post-render."
        ),
    )
    check(
        "rendered_tables_audited",
        rendered_markdown is None
        or all(table.get("lineage_complete") is True for table in rendered_tables),
        (
            f"rendered_material_tables={len(rendered_tables)} "
            f"lineage_complete={sum(table.get('lineage_complete') is True for table in rendered_tables)}"
        ),
    )
    check(
        "source_table_contract_coverage",
        fact_source_table_ids.issubset(source_table_ids),
        (
            f"fact_source_table_ids={len(fact_source_table_ids)} "
            f"source_table_ids={len(source_table_ids)} "
            f"missing={sorted(fact_source_table_ids - source_table_ids)}"
        ),
    )
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
        all(_fact_period_valid(fact) for fact in facts)
        and "fact_type_period_kind_mismatch" not in semantic_error_codes,
        "Fact type, period kind, presentation basis and current/comparison bounds are mutually consistent.",
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
    unsafe_numeric_source_ids = {
        str(event.source_id)
        for event in event_list
        if any(
            getattr(item, "mapping_status", "mapped") != "mapped"
            for item in (getattr(event, "numeric_evidence", []) or [])
        )
    }
    check(
        "unmapped_numeric_claim_quarantine",
        all(
            not any(
                str(binding.get("source_id") or "") in unsafe_numeric_source_ids
                for binding in (getattr(claim, "numeric_bindings", []) or [])
            )
            for claim in claim_list
        ),
        "Unmapped source numbers remain inventory-only; qualitative source edges cannot support numeric bindings.",
    )
    unsafe_kpi_source_ids = {
        str(event.source_id)
        for event in event_list
        if event.event_type in {"operating_kpi", "company_outlook", "guidance"}
        and str(event.source_id) in unsafe_numeric_source_ids
    }
    check(
        "unmapped_numeric_decision_quarantine",
        not unsafe_kpi_source_ids.intersection(
            {str(item.input_id) for item in decision_packet.decision_inputs}
        ),
        "An unresolved operating KPI cannot enter decision inputs or counter-signals.",
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
        "contract_version": 5,
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
        "canonical_report_sha256": rendered_report_sha256,
        "source_table_count": len(source_tables),
        "rendered_material_table_count": len(rendered_tables),
        "rendered_table_contracts": rendered_tables,
    }
    return report


def _rendered_markdown_table_contracts(
    markdown: str,
    *,
    facts: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Bind each visible material Markdown table to its explicit lineage.

    Source-table contracts prove extraction fidelity.  This second inventory
    proves that the tables a reviewer actually sees were also inspected.
    """

    if not markdown:
        return []
    main_body = markdown.partition("## Evidence Appendix")[0]
    lines = main_body.splitlines()
    contracts: list[dict[str, Any]] = []
    fact_list = list(facts)
    index = 0
    while index + 1 < len(lines):
        if not lines[index].lstrip().startswith("|") or not re.match(
            r"^\s*\|(?:\s*:?-+:?\s*\|)+\s*$",
            lines[index + 1],
        ):
            index += 1
            continue
        start = index
        table_lines: list[str] = []
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            table_lines.append(lines[index])
            index += 1
        headers = _markdown_cells(table_lines[0])
        rows = [
            _markdown_cells(line)
            for line in table_lines[2:]
            if _markdown_cells(line)
        ]
        first_header = (headers[0] if headers else "").casefold()
        visible_text = " ".join(" ".join(row) for row in rows)
        is_material = bool(re.search(r"\d", visible_text)) and first_header not in {
            "identity field",
            "field",
        }
        if not is_material:
            continue
        trailer = " ".join(lines[index : min(len(lines), index + 4)])
        lineage = re.search(
            r"room16-table-lineage\s+id=([^\s]+)\s+evidence=([^\s]+)",
            trailer,
        )
        if not lineage:
            lineage = re.search(
                r"Table claim\s+`([^`]+)`\s+·\s+Evidence:\s*`([^`]+)`",
                trailer,
            )
        table_id = lineage.group(1) if lineage else f"rendered_table_line_{start + 1}"
        evidence_ids = (
            [item.strip() for item in lineage.group(2).split(",") if item.strip()]
            if lineage
            else []
        )
        cells = []
        for row_index, row in enumerate(rows):
            row_key = row[0] if row else f"row_{row_index + 1}"
            for column_index, value in enumerate(row[1:], start=1):
                column_key = (
                    headers[column_index]
                    if column_index < len(headers)
                    else f"column_{column_index + 1}"
                )
                cell = {
                        "cell_id": f"{table_id}_r{row_index + 1}_c{column_index + 1}",
                        "table_id": table_id,
                        "row_key": row_key or f"row_{row_index + 1}",
                        "column_key": column_key or f"column_{column_index + 1}",
                        "raw_text": value,
                    }
                cell.update(
                    _rendered_cell_binding(
                        value,
                        facts=fact_list,
                        allowed_evidence_ids=set(evidence_ids),
                    )
                )
                cells.append(cell)
        material_numeric_cells = [
            cell
            for cell in cells
            if _material_non_date_tokens(str(cell.get("raw_text") or ""))
        ]
        contracts.append(
            {
                "table_id": table_id,
                "source_id": ",".join(evidence_ids),
                "source_locator": f"canonical_report.md#L{start + 1}",
                "header_rows": [headers],
                "row_headers": [row[0] for row in rows if row],
                "column_headers": headers[1:],
                "row_dimension": "rendered_row",
                "column_dimension": "rendered_column",
                "period_axis": [],
                "metric_axis": headers[1:],
                "unit_axis": [],
                "currency_axis": [],
                "comparison_axis": [],
                "value_role": "visible_report_value",
                "table_semantic_type": "rendered_markdown",
                "cells": cells,
                "lineage_complete": bool(lineage and evidence_ids)
                and all(cell.get("lineage_complete") for cell in material_numeric_cells),
                "evidence_ids": evidence_ids,
                "material_numeric_cell_count": len(material_numeric_cells),
                "cell_lineage_complete_count": sum(
                    cell.get("lineage_complete") is True
                    for cell in material_numeric_cells
                ),
            }
        )
    return contracts


def _material_non_date_tokens(value: str) -> list[str]:
    without_dates = re.sub(r"\b20\d{2}-\d{2}-\d{2}\b", "", value)
    return re.findall(
        r"-?\$?\d[\d,]*(?:\.\d+)?(?:[BMK]|%)?",
        without_dates,
        re.IGNORECASE,
    )


def _fact_display_tokens(fact: Mapping[str, Any]) -> set[str]:
    value = fact.get("value")
    if value is None:
        return set()
    number = float(value)
    magnitude = abs(number)
    sign = "-" if number < 0 else ""
    dimension = str(fact.get("dimension") or "").casefold()
    currency = str(fact.get("currency") or "").upper()
    tokens: set[str] = set()
    if dimension in {"percent", "ratio", "basis_points"} or str(fact.get("unit") or "").casefold() in {"percent", "basis_points"}:
        percent = magnitude * 100 if magnitude <= 1 else magnitude
        tokens.update({f"{sign}{percent:.1f}%", f"{sign}{percent:.2f}%"})
    if currency:
        prefix = "$" if currency == "USD" else ""
        if magnitude >= 1_000_000_000:
            tokens.add(f"{sign}{prefix}{magnitude / 1_000_000_000:.2f}B")
        elif magnitude >= 1_000_000:
            tokens.update({f"{sign}{prefix}{magnitude / 1_000_000:.1f}M", f"{sign}{prefix}{magnitude / 1_000_000:.2f}M"})
        else:
            tokens.update({f"{sign}{prefix}{magnitude:.2f}", f"{sign}{prefix}{magnitude:g}"})
    tokens.update(
        {
            f"{number:g}",
            f"{number:.1f}",
            f"{number:.2f}",
            f"{number:,.0f}",
            f"{number:,.1f}",
            f"{number:,.2f}",
        }
    )
    return {token.casefold() for token in tokens}


def _rendered_cell_binding(
    value: str,
    *,
    facts: Iterable[Mapping[str, Any]],
    allowed_evidence_ids: set[str],
) -> dict[str, Any]:
    tokens = [token.casefold() for token in _material_non_date_tokens(value)]
    if not tokens:
        return {"fact_ids": [], "evidence_ids": [], "lineage_complete": True}
    matches: dict[str, tuple[str, list[str]]] = {}
    for fact in facts:
        evidence_ids = [str(item) for item in fact.get("evidence_ids") or [] if str(item) in allowed_evidence_ids]
        if not evidence_ids:
            continue
        for token in tokens:
            if token in _fact_display_tokens(fact):
                matches[token] = (
                    str(fact.get("fact_id") or fact.get("claim_id") or ""),
                    evidence_ids,
                )
    return {
        "fact_ids": list(dict.fromkeys(match[0] for match in matches.values() if match[0])),
        "evidence_ids": list(dict.fromkeys(evidence_id for _, evidence in matches.values() for evidence_id in evidence)),
        "lineage_complete": len(matches) == len(set(tokens)),
        "unresolved_tokens": sorted(set(tokens) - set(matches)),
    }


def _markdown_cells(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [cell.strip() for cell in stripped.split("|")] if stripped else []


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
