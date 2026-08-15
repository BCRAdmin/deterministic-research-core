"""BA5 normalization, reconciliation and Typed Fact IR construction."""

from __future__ import annotations

from typing import Any

from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority

from .contracts import NormalizedRecordIR, TypedFactIR, create_hashed


class TypedFactError(ValueError):
    """Fail-closed fact construction or reconciliation error."""


def _safe(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "." for char in value)
    return ".".join(part for part in cleaned.split(".") if part)


def _state(fact: dict[str, Any]) -> str:
    flags = [
        bool(fact.get("is_zero")),
        bool(fact.get("is_missing")),
        bool(fact.get("is_not_applicable")),
    ]
    if sum(flags) > 1:
        raise TypedFactError(f"value_state_collision:{fact.get('fact_id')}")
    if flags[1]:
        return "missing"
    if flags[2]:
        return "not_applicable"
    if flags[0]:
        return "zero"
    return "value"


def _kind(fact: dict[str, Any]) -> str:
    dimension = str(fact.get("dimension") or "")
    period = str(fact.get("period_kind") or "")
    subtype = str(fact.get("fact_type") or "")
    if subtype == "guidance_range" or period == "guidance":
        return "guidance_range"
    if dimension in {"multiple", "percent", "basis_points", "per_share"} or period in {"rate", "comparison"}:
        return "ratio"
    if dimension == "text":
        return "qualitative"
    if period == "instant" or subtype in {"instant_value", "stock_value"}:
        return "instant"
    if subtype in {"flow_value", "period_total", "reconciliation_component", "contribution_to_change"}:
        return "flow"
    return "duration"


def normalize_legacy_fact(fact: dict[str, Any]) -> NormalizedRecordIR:
    source_ids = tuple(sorted(set(map(str, fact.get("source_ids") or [fact.get("source_id")])) - {"None", ""}))
    evidence_ids = tuple(sorted(set(map(str, fact.get("evidence_ids") or []))))
    value = fact.get("value")
    signed = fact.get("signed_value")
    return create_hashed(
        NormalizedRecordIR,
        record_id=f"normalized.{_safe(str(fact['fact_id']))}",
        metric_id=str(fact["metric"]),
        value_state=_state(fact),
        value=value,
        signed_value=signed if isinstance(signed, (int, float)) else None,
        dimension=str(fact.get("dimension") or "text"),
        unit=str(fact.get("display_unit") or fact.get("unit") or "text"),
        currency=str(fact.get("currency") or "none"),
        scale=str(fact.get("source_scale") or "none"),
        period_kind=str(fact.get("period_kind") or "unknown"),
        period_start=fact.get("period_start"),
        period_end=fact.get("period_end"),
        source_ids=source_ids,
        evidence_ids=evidence_ids,
        table_id=fact.get("table_id"),
        cell_id=fact.get("cell_id"),
    )


def build_typed_facts(
    facts: list[dict[str, Any]],
    *,
    authority: SemanticRegistryAuthority | None = None,
) -> tuple[tuple[NormalizedRecordIR, ...], tuple[TypedFactIR, ...]]:
    authority = authority or SemanticRegistryAuthority.load()
    normalized: list[NormalizedRecordIR] = []
    typed: list[TypedFactIR] = []
    seen: dict[str, str] = {}
    for fact in sorted(facts, key=lambda item: str(item["fact_id"])):
        record = normalize_legacy_fact(fact)
        fact_id = str(fact["fact_id"])
        previous = seen.get(fact_id)
        if previous is not None and previous != record.ir_sha256:
            raise TypedFactError(f"conflicting_duplicate_fact:{fact_id}")
        if previous is not None:
            continue
        seen[fact_id] = record.ir_sha256
        definition_id, binding_type = authority.bind_metric(str(fact["metric"]))
        if binding_type in {"quarantined_unknown", "semantic_collision"}:
            raise TypedFactError(f"unexecutable_metric:{fact['metric']}")
        normalized.append(record)
        typed.append(create_hashed(
            TypedFactIR,
            fact_id=fact_id,
            metric_id=str(fact["metric"]),
            metric_definition_id=definition_id,
            fact_kind=_kind(fact),
            fact_subtype=str(fact.get("fact_type") or "unknown"),
            value_state=record.value_state,
            value=record.value,
            dimension=record.dimension,
            unit=record.unit,
            currency=record.currency,
            period_kind=record.period_kind,
            period_start=record.period_start,
            period_end=record.period_end,
            source_ids=record.source_ids,
            evidence_ids=record.evidence_ids,
            normalized_record_sha256=record.ir_sha256,
        ))
        operands = fact.get("formula_operands") or {}
        if isinstance(operands, dict):
            for role, value in sorted(operands.items()):
                operand_fact_id = f"{_safe(fact_id)}.operand.{_safe(str(role))}"
                operand_record = create_hashed(
                    NormalizedRecordIR,
                    record_id=f"normalized.{operand_fact_id}",
                    metric_id=f"formula_operand.{_safe(str(role))}",
                    value_state="zero" if value == 0 else "value",
                    value=value,
                    signed_value=value if isinstance(value, (int, float)) else None,
                    dimension=record.dimension,
                    unit=record.unit,
                    currency=record.currency,
                    scale="none",
                    period_kind=record.period_kind,
                    period_start=record.period_start,
                    period_end=record.period_end,
                    source_ids=record.source_ids,
                    evidence_ids=record.evidence_ids,
                )
                normalized.append(operand_record)
                typed.append(create_hashed(
                    TypedFactIR,
                    fact_id=operand_fact_id,
                    metric_id=f"formula_operand.{_safe(str(role))}",
                    metric_definition_id=definition_id,
                    fact_kind=_kind(fact),
                    fact_subtype="formula_operand",
                    value_state=operand_record.value_state,
                    value=value,
                    dimension=record.dimension,
                    unit=record.unit,
                    currency=record.currency,
                    period_kind=record.period_kind,
                    period_start=record.period_start,
                    period_end=record.period_end,
                    source_ids=record.source_ids,
                    evidence_ids=record.evidence_ids,
                    normalized_record_sha256=operand_record.ir_sha256,
                    role="formula_operand",
                ))
    normalized.sort(key=lambda item: item.record_id)
    typed.sort(key=lambda item: item.fact_id)
    ids = [item.fact_id for item in typed]
    if len(ids) != len(set(ids)):
        raise TypedFactError("typed_fact_id_collision")
    return tuple(normalized), tuple(typed)
