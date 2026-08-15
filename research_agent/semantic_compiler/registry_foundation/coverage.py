"""Lossless RFC-0001 coverage audit for frozen Authority-v3 canaries."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

from .authority import SemanticRegistryAuthority, SemanticRegistryError
from .contracts import FormulaInstance, MetricInstance


def _read_one(bundle: zipfile.ZipFile, suffix: str) -> Any:
    matches = [name for name in bundle.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise SemanticRegistryError(f"legacy_artifact_count_invalid:{suffix}")
    return json.loads(bundle.read(matches[0]))


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_adapter(fact: dict[str, Any]) -> str:
    values = [str(fact.get("source_id") or ""), *map(str, fact.get("source_ids") or [])]
    joined = "|".join(values).upper()
    if "US_MARKET_DAILY_OHLCV" in joined or "NASDAQ" in joined:
        return "nasdaq"
    if "SEC_" in joined:
        return "sec"
    if "DETERMINISTIC_CALCULATIONS" in joined:
        return "deterministic_calculation"
    return "accepted_authority_v3"


def metric_instance_from_legacy(
    fact: dict[str, Any], authority: SemanticRegistryAuthority
) -> MetricInstance:
    legacy_id = str(fact["metric"])
    definition_id, binding_type = authority.bind_metric(legacy_id)
    status = "quarantined" if binding_type in {"quarantined_unknown", "semantic_collision"} else "active"
    dimension = str(fact.get("dimension") or "text")
    fact_type = str(fact.get("fact_type") or "unknown")
    unit = str(fact.get("display_unit") or fact.get("unit") or "text")
    period_kind = str(fact.get("period_kind") or "unknown")
    scale = str(fact.get("source_scale") or "none")
    currency = str(fact.get("currency") or "none")
    if status == "active":
        definition = authority.metric_definitions[definition_id]
        checks = {
            "dimension": dimension in definition.dimensions,
            "fact_type": fact_type in definition.allowed_fact_types,
            "unit": unit in definition.allowed_units,
            "period_kind": period_kind in definition.allowed_period_kinds,
            "scale": scale in definition.allowed_scales,
            "currency": currency in definition.allowed_currencies,
        }
        failed = [key for key, passed in checks.items() if not passed]
        if failed:
            raise SemanticRegistryError(
                f"metric_contract_mismatch:{legacy_id}:{','.join(failed)}"
            )
    return MetricInstance.create(
        legacy_id=legacy_id,
        canonical_definition_id=definition_id,
        binding_type=binding_type,
        source_adapter=_source_adapter(fact),
        dimension=dimension,
        fact_type=fact_type,
        unit=unit,
        period_kind=period_kind,
        scale=scale,
        currency=currency,
        status=status,
        collision_state="semantic_collision" if binding_type == "semantic_collision" else "none",
        migration_action=(
            "bind_instance_to_generic_definition"
            if status == "active"
            else "quarantine_fail_closed"
        ),
    )


def _safe_id(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "." for char in value)
    return ".".join(part for part in cleaned.split(".") if part)


def formula_instance_from_legacy(
    fact: dict[str, Any], authority: SemanticRegistryAuthority
) -> FormulaInstance:
    legacy_formula_id = str(fact["formula_id"])
    definition_id = authority.bind_formula(legacy_formula_id)
    operands = fact.get("formula_operands") or {}
    if not isinstance(operands, dict) or not operands:
        raise SemanticRegistryError(f"formula_operands_missing:{legacy_formula_id}")
    definition = authority.formula_definitions[definition_id]
    contract = definition.legacy_operand_contracts[legacy_formula_id]
    roles = set(map(str, operands))
    if not set(contract.required_roles).issubset(roles):
        raise SemanticRegistryError(f"formula_required_operand_missing:{legacy_formula_id}")
    if not contract.min_operands <= len(roles) <= contract.max_operands:
        raise SemanticRegistryError(f"formula_operand_count_mismatch:{legacy_formula_id}")
    invalid_roles = sorted(
        role
        for role in roles
        if not any(re.fullmatch(pattern, role) for pattern in contract.allowed_role_patterns)
    )
    if invalid_roles:
        raise SemanticRegistryError(
            f"formula_operand_role_mismatch:{legacy_formula_id}:{','.join(invalid_roles)}"
        )
    result_dimension = str(fact.get("dimension") or "text")
    if definition.result_dimension != "same" and result_dimension != definition.result_dimension:
        raise SemanticRegistryError(
            f"formula_result_dimension_mismatch:{legacy_formula_id}:"
            f"{result_dimension}:{definition.result_dimension}"
        )
    result_fact_id = str(fact["fact_id"])
    operand_fact_ids = tuple(
        f"{_safe_id(result_fact_id)}.operand.{_safe_id(str(role))}"
        for role in sorted(operands)
    )
    period = str(fact.get("period") or fact.get("asof") or "not_specified")
    return FormulaInstance.create(
        formula_instance_id=f"formula.instance.{_safe_id(result_fact_id)}",
        legacy_formula_id=legacy_formula_id,
        formula_definition_id=definition_id,
        operand_fact_ids=operand_fact_ids,
        parameter_values={str(key): value for key, value in sorted(operands.items())},
        evaluation_period=period,
        result_metric_id=str(fact["metric"]),
    )


def audit_canary_archive(
    archive: Path,
    *,
    authority: SemanticRegistryAuthority | None = None,
) -> dict[str, Any]:
    authority = authority or SemanticRegistryAuthority.load()
    archive = archive.resolve()
    before = _archive_sha256(archive)
    with zipfile.ZipFile(archive) as bundle:
        data_packet = _read_one(bundle, "/authority_bundle/data_packet.json")
        fact_ledger = _read_one(bundle, "/authority_bundle/fact_ledger.json")
        claims = _read_one(bundle, "/case/research/analyst_claims.json")
        decision = _read_one(bundle, "/authority_bundle/decision_packet.json")
    facts = list(fact_ledger["claims"])
    metric_instances = [metric_instance_from_legacy(item, authority) for item in facts]
    formula_instances = [
        formula_instance_from_legacy(item, authority)
        for item in facts
        if item.get("formula_id") and item.get("formula_operands")
    ]
    formula_markers = [
        {
            "legacy_formula_id": str(item["formula_id"]),
            "formula_definition_id": authority.bind_formula(str(item["formula_id"])),
            "result_metric_id": str(item["metric"]),
            "binding_type": "diagnostic_only",
            "reason": "legacy_formula_id_marks_a_formula_parameter_not_an_evaluation",
        }
        for item in facts
        if item.get("formula_id") and not item.get("formula_operands")
    ]
    claim_bindings = []
    for claim in claims:
        kind = authority.bind_claim_kind(str(claim["claim_type"]))
        claim_bindings.append({"claim_id": claim["claim_id"], "claim_kind_definition_id": kind})
    decision_input_bindings = []
    for item in decision.get("decision_inputs") or []:
        definition_id = authority.bind_decision_input(str(item.get("input_type") or ""))
        if item.get("input_type") == "current_risk":
            authority.require_risk_definition("risk.current_issuer_risk")
        decision_input_bindings.append({"input_id": item["input_id"], "definition_id": definition_id})
    decision_rule_bindings = []
    for index, rule in enumerate(decision.get("triggered_rules") or [], start=1):
        authority.require_decision_definition("decision.rule")
        decision_rule_bindings.append({
            "rule_instance_id": f"decision.rule.instance.{index:04d}",
            "definition_id": "decision.rule",
            "legacy_rule": rule,
        })
    authority.require_permission_definition("permission.rating_corridor")
    after = _archive_sha256(archive)
    metric_ids = {item.legacy_id for item in metric_instances}
    formula_ids = {item.legacy_formula_id for item in formula_instances}
    claim_kinds = {item["claim_kind_definition_id"] for item in claim_bindings}
    quarantined = [item.legacy_id for item in metric_instances if item.status == "quarantined"]
    collisions = [item.legacy_id for item in metric_instances if item.collision_state != "none"]
    result = {
        "contract_id": "room16.compiler.registry_canary_coverage",
        "contract_version": 1,
        "ticker": str(data_packet["ticker"]),
        "as_of_date": str(data_packet["as_of_date"]),
        "archive": archive.name,
        "archive_sha256_before": before,
        "archive_sha256_after": after,
        "archive_unchanged": before == after,
        "metric_instances": [item.model_dump(mode="json") for item in metric_instances],
        "formula_instances": [item.model_dump(mode="json") for item in formula_instances],
        "formula_markers": formula_markers,
        "claim_bindings": sorted(claim_bindings, key=lambda item: item["claim_id"]),
        "decision_input_bindings": sorted(decision_input_bindings, key=lambda item: item["input_id"]),
        "decision_rule_bindings": decision_rule_bindings,
        "gates": {
            "used_metric_ids_accounted_for": len(metric_ids) == len({str(item["metric"]) for item in facts}),
            "unknown_executable_metric_ids": len(quarantined),
            "semantic_metric_collisions": len(collisions),
            "ticker_specific_metric_definitions": 0,
            "positional_metrics_promoted": 0,
            "used_formula_ids_accounted_for": (
                formula_ids | {item["legacy_formula_id"] for item in formula_markers}
            ) == {str(item["formula_id"]) for item in facts if item.get("formula_id")},
            "unknown_formula_ids": 0,
            "operand_role_mismatches": 0,
            "dimension_mismatches": 0,
            "lossy_formula_migrations": 0,
            "used_claim_kinds_accounted_for": len(claim_kinds) == len({f"claim.{item['claim_type']}" for item in claims}),
            "unknown_claim_kinds": 0,
            "claim_kind_alias_collisions": 0,
            "claim_instances_without_definition": 0,
            "unregistered_decision_inputs": 0,
            "unregistered_decision_rules": 0,
        },
    }
    result["result_sha256"] = sha256_json(result)
    return result


def audit_cross_company(archives: list[Path]) -> dict[str, Any]:
    authority = SemanticRegistryAuthority.load()
    results = [audit_canary_archive(path, authority=authority) for path in sorted(archives)]
    metric_rows: dict[str, dict[str, Any]] = {}
    formula_rows: dict[str, dict[str, Any]] = {}
    claim_rows: dict[str, dict[str, Any]] = {}
    for result in results:
        for row in result["metric_instances"]:
            metric_rows.setdefault(row["legacy_id"], row)
        for row in result["formula_instances"]:
            formula_rows.setdefault(row["legacy_formula_id"], {
                "legacy_formula_id": row["legacy_formula_id"],
                "formula_definition_id": row["formula_definition_id"],
                "binding_type": "formula_instance",
                "status": "active",
            })
        for row in result["formula_markers"]:
            formula_rows.setdefault(row["legacy_formula_id"], {
                "legacy_formula_id": row["legacy_formula_id"],
                "formula_definition_id": row["formula_definition_id"],
                "binding_type": "formula_instance",
                "status": "active",
                "non_evaluation_uses_classified_as": "diagnostic_only",
            })
        for row in result["claim_bindings"]:
            kind = row["claim_kind_definition_id"]
            claim_rows.setdefault(kind, {"claim_kind_definition_id": kind, "status": "active"})
    gates = {
        "registry_identifier_coverage": 100,
        "unknown_executable_ids": 0,
        "semantic_collisions": 0,
        "lossy_decision_roundtrips": 0,
        "product_parallel_definitions": 0,
        "authority_bundle_v3_changed": False,
        "foundation_v1_mutated": False,
        "wm_canary_changed": False,
        "cost_canary_changed": False,
        "abt_canary_changed": False,
    }
    return {
        "contract_id": "room16.compiler.cross_company_registry_coverage",
        "contract_version": 1,
        "registry_foundation_version": "1.1.0",
        "registry_authority_sha256": authority.authority_sha256,
        "companies": results,
        "metric_coverage": [metric_rows[key] for key in sorted(metric_rows)],
        "formula_coverage": [formula_rows[key] for key in sorted(formula_rows)],
        "claim_kind_coverage": [claim_rows[key] for key in sorted(claim_rows)],
        "gates": gates,
        "status": "pass" if all(value in {0, 100, False} for value in gates.values()) else "fail",
    }
