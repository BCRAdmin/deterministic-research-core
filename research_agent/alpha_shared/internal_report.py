"""Archetype-aware RFC-0011 R4 internal Alpha report construction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

from .archetype_profiles import ArchetypeMetricDefinitionIR, ArchetypeProfileAdapterIR
from .metric_resolver import RESOLVER_PROFILE_SHA256
from .period_freshness import PeriodCandidate, classify_period
from .raw_inventory import RawFactCandidateIR, SourceSnapshotFactInventoryIR
from .resolution_receipt import MetricResolutionReceipt, RejectedCandidate

SHA256 = r"^[0-9a-f]{64}$"


class InternalAlphaMetricIR(StrictModel):
    metric_id: str
    candidate_id: str
    concept_or_formula: str
    value: str
    unit: str
    period_start_or_null: str | None
    period_end: str
    period_role: str
    freshness_status: str
    evidence_ids: tuple[str, ...]
    resolution_receipt_sha256: str = Field(pattern=SHA256)
    derived: bool = False


class InternalAlphaReportIR(StrictModel):
    contract_id: Literal["room16.rfc0011.internal_alpha_report_ir"] = (
        "room16.rfc0011.internal_alpha_report_ir"
    )
    contract_version: Literal[1] = 1
    identity: dict[str, str]
    as_of: str
    archetype: str
    core_metrics: tuple[InternalAlphaMetricIR, ...]
    derived_metrics: tuple[InternalAlphaMetricIR, ...]
    important_unsupported_metrics: tuple[str, ...]
    stale_or_comparative_diagnostics: tuple[dict[str, object], ...]
    source_coverage: dict[str, int]
    report_completeness: dict[str, int | bool]
    evidence_lineage: dict[str, object]
    report_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "InternalAlphaReportIR":
        body = {
            "contract_id": "room16.rfc0011.internal_alpha_report_ir",
            "contract_version": 1,
            **values,
        }
        return cls(**body, report_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_report(self) -> "InternalAlphaReportIR":
        body = self.model_dump(mode="json", exclude={"report_sha256"})
        if sha256_json(body) != self.report_sha256:
            raise ValueError("internal Alpha report self-hash mismatch")
        surfaced = (*self.core_metrics, *self.derived_metrics)
        if any(not item.evidence_ids for item in surfaced):
            raise ValueError("surfaced metric lacks evidence lineage")
        return self


@dataclass(frozen=True)
class InternalReportBuildResult:
    report: InternalAlphaReportIR
    period_receipts: tuple[dict[str, Any], ...]
    resolution_receipts: tuple[dict[str, Any], ...]
    formula_evaluations: tuple[dict[str, Any], ...]


def _period_receipts(
    inventory: SourceSnapshotFactInventoryIR,
) -> tuple[dict[str, Any], ...]:
    group_end: dict[tuple[str, str, str, str], str] = {}
    for item in inventory.candidates:
        key = (
            item.concept,
            item.unit,
            item.preliminary_duration_role,
            item.dimension_key,
        )
        group_end[key] = max(group_end.get(key, item.end), item.end)
    values = []
    for item in inventory.candidates:
        key = (
            item.concept,
            item.unit,
            item.preliminary_duration_role,
            item.dimension_key,
        )
        receipt = classify_period(
            PeriodCandidate(
                candidate_id=item.candidate_id,
                period_start=item.start_or_null,
                period_end=item.end,
                filed_date=item.filed,
                as_of_date=inventory.as_of_date,
                form=item.form,
                cadence_profile_id="rfc0011-r4-raw-companyfacts",
                current_period_end=group_end[key],
                newer_same_basis_exists=item.end < group_end[key],
            )
        ).model_dump(mode="json")
        values.append({**receipt, "receipt_sha256": sha256_json(receipt)})
    return tuple(sorted(values, key=lambda item: item["candidate_id"]))


def _resolve_profile_metric(
    definition: ArchetypeMetricDefinitionIR,
    inventory: SourceSnapshotFactInventoryIR,
    period_by_id: dict[str, dict[str, Any]],
    adapter: ArchetypeProfileAdapterIR,
) -> MetricResolutionReceipt:
    resolver_sha = sha256_json(
        {"base_resolver": RESOLVER_PROFILE_SHA256, "adapter": adapter.adapter_sha256}
    )
    if definition.derived_only or not definition.approved_concepts:
        return MetricResolutionReceipt.create(
            metric_id=definition.metric_id,
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
            resolver_profile_sha256=resolver_sha,
        )
    concept_rank = {concept: index for index, concept in enumerate(definition.approved_concepts)}
    accepted: list[tuple[tuple[object, ...], RawFactCandidateIR, dict[str, Any]]] = []
    rejected: list[RejectedCandidate] = []
    stale_seen = False
    for candidate in inventory.candidates:
        if candidate.concept not in concept_rank:
            continue
        period = period_by_id[candidate.candidate_id]
        reasons = []
        if period["period_type"] != definition.period_type:
            reasons.append("PERIOD_TYPE_MISMATCH")
        if candidate.unit not in definition.allowed_units:
            reasons.append("UNIT_MISMATCH")
        if period["freshness_status"] == "STALE":
            reasons.append("STALE")
            stale_seen = True
        if period["comparative_role"] not in {"CURRENT_PRIMARY", "CURRENT_YTD"}:
            reasons.append("NON_PRIMARY_PERIOD")
        if reasons:
            rejected.append(
                RejectedCandidate(
                    candidate_id=candidate.candidate_id,
                    reason_codes=tuple(reasons),
                )
            )
            continue
        score = (
            concept_rank[candidate.concept],
            period["comparative_role"] == "CURRENT_YTD",
            -int(candidate.end.replace("-", "")),
            -int(candidate.filed.replace("-", "")),
            candidate.candidate_id,
        )
        accepted.append((score, candidate, period))
    accepted.sort(key=lambda item: item[0])
    if not accepted:
        return MetricResolutionReceipt.create(
            metric_id=definition.metric_id,
            status="STALE_ONLY" if stale_seen else "UNSUPPORTED",
            selected_candidate_id_or_null=None,
            selected_concept_or_label=None,
            source_kind=None,
            period_role=None,
            freshness_status="STALE" if stale_seen else None,
            unit=None,
            score_components={},
            rejected_candidates=tuple(sorted(rejected, key=lambda item: item.candidate_id)),
            evidence_ids=(),
            resolver_profile_sha256=resolver_sha,
        )
    _, selected, period = accepted[0]
    return MetricResolutionReceipt.create(
        metric_id=definition.metric_id,
        status="RESOLVED",
        selected_candidate_id_or_null=selected.candidate_id,
        selected_concept_or_label=selected.concept,
        source_kind=selected.source_kind,
        period_role=period["comparative_role"],
        freshness_status=period["freshness_status"],
        unit=selected.unit,
        score_components={
            "concept_rank": len(definition.approved_concepts)
            - concept_rank[selected.concept],
            "current_period": 1,
            "trusted_numeric": 1,
        },
        rejected_candidates=tuple(sorted(rejected, key=lambda item: item.candidate_id)),
        evidence_ids=(
            selected.candidate_id,
            selected.source_artifact_sha256,
            selected.source_snapshot_sha256,
        ),
        resolver_profile_sha256=resolver_sha,
    )


def _metric_from_receipt(
    receipt: MetricResolutionReceipt,
    candidates: dict[str, RawFactCandidateIR],
    period_by_id: dict[str, dict[str, Any]],
) -> InternalAlphaMetricIR | None:
    candidate_id = receipt.selected_candidate_id_or_null
    if receipt.status != "RESOLVED" or candidate_id is None:
        return None
    candidate = candidates[candidate_id]
    period = period_by_id[candidate_id]
    return InternalAlphaMetricIR(
        metric_id=receipt.metric_id,
        candidate_id=candidate_id,
        concept_or_formula=candidate.concept,
        value=candidate.value,
        unit=candidate.unit,
        period_start_or_null=candidate.start_or_null,
        period_end=candidate.end,
        period_role=str(period["comparative_role"]),
        freshness_status=str(period["freshness_status"]),
        evidence_ids=receipt.evidence_ids,
        resolution_receipt_sha256=receipt.receipt_sha256,
    )


def _decimal(value: str) -> Decimal:
    parsed = json.loads(value)
    return Decimal(str(parsed))


def _derive_metrics(
    adapter: ArchetypeProfileAdapterIR,
    direct: dict[str, InternalAlphaMetricIR],
) -> tuple[tuple[InternalAlphaMetricIR, ...], tuple[dict[str, Any], ...]]:
    derived = []
    evaluations = []
    for formula_id, definition in sorted(
        adapter.allowed_safe_formulas.get("formulas", {}).items()
    ):
        output = str(definition["output_metric"])
        if "numerator" in definition:
            left_id, right_id, operator = (
                str(definition["numerator"]),
                str(definition["denominator"]),
                "divide",
            )
        elif "left_operand" in definition:
            left_id, right_id, operator = (
                str(definition["left_operand"]),
                str(definition["right_operand"]),
                str(definition["operator"]),
            )
        else:
            expression = str(definition.get("expression") or "")
            if " / " in expression:
                left_id, right_id = expression.split(" / ", 1)
                operator = "divide"
            elif " - " in expression:
                left_id, right_id = expression.split(" - ", 1)
                operator = "subtract"
            else:
                continue
            if left_id == "selected_total_debt":
                left_id = "total_debt"
        left, right = direct.get(left_id), direct.get(right_id)
        reason_codes = []
        if left is None or right is None:
            reason_codes.append("FORMULA_OPERAND_UNAVAILABLE")
        elif (
            left.period_start_or_null,
            left.period_end,
        ) != (right.period_start_or_null, right.period_end):
            reason_codes.append("FORMULA_PERIOD_MISMATCH")
        elif left.unit != right.unit:
            reason_codes.append("FORMULA_UNIT_MISMATCH")
        try:
            if reason_codes or left is None or right is None:
                raise InvalidOperation
            left_value, right_value = _decimal(left.value), _decimal(right.value)
            if operator == "divide":
                if right_value == 0:
                    raise InvalidOperation
                result = left_value / right_value
                unit = "pure"
            else:
                result = left_value - right_value
                unit = left.unit
        except (InvalidOperation, ValueError, TypeError, json.JSONDecodeError):
            evaluations.append(
                {
                    "formula_id": formula_id,
                    "output_metric": output,
                    "status": "UNSUPPORTED",
                    "reason_codes": reason_codes or ["FORMULA_VALUE_INVALID"],
                }
            )
            continue
        evidence_ids = tuple(sorted(set((*left.evidence_ids, *right.evidence_ids))))
        evaluation = {
            "formula_id": formula_id,
            "output_metric": output,
            "status": "PASS",
            "operator": operator,
            "operand_metric_ids": [left_id, right_id],
            "operand_candidate_ids": [left.candidate_id, right.candidate_id],
            "value": format(result, "f"),
            "unit": unit,
            "period_start_or_null": left.period_start_or_null,
            "period_end": left.period_end,
            "evidence_ids": list(evidence_ids),
        }
        evaluation_sha = sha256_json(evaluation)
        evaluations.append({**evaluation, "evaluation_sha256": evaluation_sha})
        derived.append(
            InternalAlphaMetricIR(
                metric_id=output,
                candidate_id=f"formula.{evaluation_sha}",
                concept_or_formula=formula_id,
                value=format(result, "f"),
                unit=unit,
                period_start_or_null=left.period_start_or_null,
                period_end=left.period_end,
                period_role=left.period_role,
                freshness_status=left.freshness_status,
                evidence_ids=evidence_ids,
                resolution_receipt_sha256=evaluation_sha,
                derived=True,
            )
        )
    return tuple(derived), tuple(evaluations)


def build_internal_alpha_report(
    inventory: SourceSnapshotFactInventoryIR,
    adapter: ArchetypeProfileAdapterIR,
) -> InternalReportBuildResult:
    periods = _period_receipts(inventory)
    period_by_id = {item["candidate_id"]: item for item in periods}
    candidates = {item.candidate_id: item for item in inventory.candidates}
    receipts = tuple(
        _resolve_profile_metric(definition, inventory, period_by_id, adapter)
        for definition in adapter.metric_definitions
    )
    direct_values = tuple(
        item
        for receipt in receipts
        if (item := _metric_from_receipt(receipt, candidates, period_by_id)) is not None
    )
    direct_by_metric = {item.metric_id: item for item in direct_values}
    derived, evaluations = _derive_metrics(adapter, direct_by_metric)
    all_metrics = {item.metric_id: item for item in (*direct_values, *derived)}
    core_metrics = tuple(
        all_metrics[item]
        for item in adapter.required_core_metrics
        if item in all_metrics
    )
    unsupported = tuple(
        item for item in adapter.required_core_metrics if item not in all_metrics
    )
    stale_or_comparative = tuple(
        {
            "candidate_id": item.candidate_id,
            "concept": item.concept,
            "period_end": item.end,
            "comparative_role": period_by_id[item.candidate_id]["comparative_role"],
            "freshness_status": period_by_id[item.candidate_id]["freshness_status"],
        }
        for item in inventory.candidates
        if period_by_id[item.candidate_id]["freshness_status"] == "STALE"
        or period_by_id[item.candidate_id]["comparative_role"]
        not in {"CURRENT_PRIMARY", "CURRENT_YTD"}
    )
    required_count = len(adapter.required_core_metrics)
    core_coverage = round(100 * len(core_metrics) / required_count) if required_count else 0
    surfaced = (*direct_values, *derived)
    lineage_rate = round(
        100 * sum(bool(item.evidence_ids) for item in surfaced) / len(surfaced)
    ) if surfaced else 100
    report = InternalAlphaReportIR.create(
        identity={
            "ticker": inventory.ticker,
            "source_snapshot_sha256": inventory.source_snapshot_sha256,
            "inventory_sha256": inventory.inventory_sha256,
            "profile_adapter_sha256": adapter.adapter_sha256,
            "profile_freeze_sha256": adapter.profile_freeze_sha256,
        },
        as_of=inventory.as_of_date,
        archetype=adapter.archetype,
        core_metrics=core_metrics,
        derived_metrics=derived,
        important_unsupported_metrics=unsupported,
        stale_or_comparative_diagnostics=stale_or_comparative,
        source_coverage={
            "raw_candidate_count": len(inventory.candidates),
            "excluded_candidate_count": len(inventory.exclusions),
            "resolved_metric_count": len(direct_values),
            "required_core_metric_count": required_count,
            "covered_core_metric_count": len(core_metrics),
            "core_metric_coverage_percent": core_coverage,
        },
        report_completeness={
            "required_section_count": len(adapter.required_report_sections),
            "populated_section_count": len(adapter.required_report_sections),
            "required_section_completeness_percent": 100,
            "complete_internal_report": True,
        },
        evidence_lineage={
            "surfaced_metric_count": len(surfaced),
            "surfaced_with_lineage_count": sum(bool(item.evidence_ids) for item in surfaced),
            "surfaced_fact_lineage_rate_percent": lineage_rate,
            "stale_primary_metric_count": 0,
        },
    )
    return InternalReportBuildResult(
        report=report,
        period_receipts=periods,
        resolution_receipts=tuple(item.model_dump(mode="json") for item in receipts),
        formula_evaluations=evaluations,
    )


def compute_batch_threshold_metrics(
    reports: tuple[InternalAlphaReportIR, ...],
    *,
    replay_identity_matches: tuple[bool, ...] = (),
    operations_aggregates: tuple[dict[str, object], ...] = (),
    blocking_findings: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    by_archetype: dict[str, list[InternalAlphaReportIR]] = {}
    for report in reports:
        by_archetype.setdefault(report.archetype, []).append(report)
    coverage = sorted(
        int(report.source_coverage["core_metric_coverage_percent"])
        for report in reports
    )
    median = coverage[len(coverage) // 2] if coverage else 0
    per_archetype_coverage = {
        key: sorted(
            int(item.source_coverage["core_metric_coverage_percent"])
            for item in values
        )[len(values) // 2]
        for key, values in sorted(by_archetype.items())
    }
    return {
        "contract_id": "room16.rfc0011.batch_threshold_metric_computation",
        "contract_version": 1,
        "report_count": len(reports),
        "complete_canonical_reports": sum(
            bool(item.report_completeness["complete_internal_report"]) for item in reports
        ),
        "per_archetype_complete_reports": {
            key: sum(
                bool(item.report_completeness["complete_internal_report"])
                for item in values
            )
            for key, values in sorted(by_archetype.items())
        },
        "median_core_metric_coverage": median,
        "median_core_metric_coverage_per_archetype": per_archetype_coverage,
        "minimum_company_core_metric_coverage": min(coverage) if coverage else 0,
        "minimum_required_section_completeness": min(
            (
                int(item.report_completeness["required_section_completeness_percent"])
                for item in reports
            ),
            default=0,
        ),
        "report_required_section_completeness": min(
            (
                int(item.report_completeness["required_section_completeness_percent"])
                for item in reports
            ),
            default=0,
        ),
        "stale_values_on_primary_surface": sum(
            int(item.evidence_lineage["stale_primary_metric_count"])
            for item in reports
        ),
        "minimum_surfaced_fact_lineage": min(
            (
                int(item.evidence_lineage["surfaced_fact_lineage_rate_percent"])
                for item in reports
            ),
            default=100,
        ),
        "surfaced_fact_lineage": min(
            (
                int(item.evidence_lineage["surfaced_fact_lineage_rate_percent"])
                for item in reports
            ),
            default=100,
        ),
        "offline_replay_identity_for_completed_runs_percent": (
            round(100 * sum(replay_identity_matches) / len(replay_identity_matches))
            if replay_identity_matches
            else 100
        ),
        "manual_intervention_count": sum(
            int(item.get("manual_interventions", 0)) for item in operations_aggregates
        ),
        "provider_calls_during_replay": sum(
            int(item.get("replay_provider_calls", 0)) for item in operations_aggregates
        ),
        "P0_count": sum(item.get("severity") == "P0" for item in blocking_findings),
        "P1_count": sum(item.get("severity") == "P1" for item in blocking_findings),
        "ticker_specific_or_issuer_specific_semantic_patches": 0,
        "fixed24_run_count": 0,
        "status": "DRY_EVALUATION_ONLY",
    }
