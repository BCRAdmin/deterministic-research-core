"""Versioned definition and instance contracts approved by RFC-0001."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"
ID_PATTERN = r"^[a-z][a-z0-9_.:-]*$"
Classification = Literal[
    "canonical_definition",
    "definition_alias",
    "instance_binding",
    "formula_instance",
    "deprecated_alias",
    "diagnostic_only",
    "quarantined_unknown",
    "semantic_collision",
]


def _ordered(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{field} must be unique and sorted")
    return values


class MetricDefinition(StrictModel):
    definition_id: str = Field(pattern=ID_PATTERN)
    definition_version: int = Field(ge=1)
    semantic_description: str = Field(min_length=1)
    dimensions: tuple[str, ...]
    allowed_fact_types: tuple[str, ...]
    allowed_units: tuple[str, ...]
    allowed_period_kinds: tuple[str, ...]
    allowed_scales: tuple[str, ...]
    allowed_currencies: tuple[str, ...]
    instance_patterns: tuple[str, ...] = ()
    compatibility: Literal["additive_v1"] = "additive_v1"

    @model_validator(mode="after")
    def ordered_sets(self) -> "MetricDefinition":
        for field in (
            "dimensions", "allowed_fact_types", "allowed_units",
            "allowed_period_kinds", "allowed_scales", "allowed_currencies",
            "instance_patterns",
        ):
            _ordered(getattr(self, field), field)
        return self


class MetricInstance(StrictModel):
    contract_id: Literal["room16.compiler.metric_instance"] = "room16.compiler.metric_instance"
    contract_version: Literal[1] = 1
    legacy_id: str = Field(min_length=1)
    canonical_definition_id: str = Field(pattern=ID_PATTERN)
    binding_type: Classification
    source_adapter: str
    dimension: str
    fact_type: str
    unit: str
    period_kind: str
    scale: str
    currency: str
    status: Literal["active", "quarantined"]
    collision_state: Literal["none", "semantic_collision"] = "none"
    migration_action: str
    binding_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(cls, **values: Any) -> "MetricInstance":
        body = dict(values)
        return cls(**values, binding_sha256=sha256_json(body))

    @model_validator(mode="after")
    def valid_binding(self) -> "MetricInstance":
        body = self.model_dump(mode="json", exclude={"binding_sha256", "contract_id", "contract_version"})
        if sha256_json(body) != self.binding_sha256:
            raise ValueError("metric instance binding hash mismatch")
        if self.status == "active" and self.binding_type in {"quarantined_unknown", "semantic_collision"}:
            raise ValueError("quarantined or colliding metric cannot be executable")
        return self


class FormulaDefinition(StrictModel):
    formula_definition_id: str = Field(pattern=ID_PATTERN)
    formula_version: int = Field(ge=1)
    expression_contract: str = Field(min_length=1)
    operand_roles: tuple[str, ...]
    operand_dimensions: tuple[str, ...]
    result_dimension: str
    rounding_policy: str
    missing_operand_policy: Literal["fail_closed"] = "fail_closed"
    zero_division_policy: Literal["fail_closed", "not_applicable"]
    provenance_policy: Literal["all_operands_required"] = "all_operands_required"
    determinism_contract: Literal["pure_same_input_same_output"] = "pure_same_input_same_output"
    legacy_aliases: tuple[str, ...] = ()
    legacy_operand_contracts: dict[str, "FormulaOperandContract"]

    @model_validator(mode="after")
    def valid_roles(self) -> "FormulaDefinition":
        _ordered(self.operand_roles, "operand_roles")
        _ordered(self.legacy_aliases, "legacy_aliases")
        if list(self.legacy_operand_contracts) != sorted(self.legacy_operand_contracts):
            raise ValueError("legacy operand contracts must be sorted")
        if set(self.legacy_operand_contracts) != set(self.legacy_aliases):
            raise ValueError("every formula alias requires exactly one operand contract")
        if len(self.operand_dimensions) not in {1, len(self.operand_roles)}:
            raise ValueError("operand dimensions must be one wildcard or match operand roles")
        return self


class FormulaOperandContract(StrictModel):
    required_roles: tuple[str, ...]
    allowed_role_patterns: tuple[str, ...]
    min_operands: int = Field(ge=1)
    max_operands: int = Field(ge=1)

    @model_validator(mode="after")
    def valid_contract(self) -> "FormulaOperandContract":
        _ordered(self.required_roles, "required_roles")
        _ordered(self.allowed_role_patterns, "allowed_role_patterns")
        if self.max_operands < self.min_operands:
            raise ValueError("formula operand bounds invalid")
        return self


class FormulaInstance(StrictModel):
    contract_id: Literal["room16.compiler.formula_instance"] = "room16.compiler.formula_instance"
    contract_version: Literal[1] = 1
    formula_instance_id: str = Field(pattern=ID_PATTERN)
    legacy_formula_id: str
    formula_definition_id: str = Field(pattern=ID_PATTERN)
    operand_fact_ids: tuple[str, ...]
    parameter_values: dict[str, int | float | str | bool | None]
    evaluation_period: str
    result_metric_id: str
    evaluation_hash: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(cls, **values: Any) -> "FormulaInstance":
        values["operand_fact_ids"] = tuple(sorted(values["operand_fact_ids"]))
        body = dict(values)
        return cls(**values, evaluation_hash=sha256_json(body))

    @model_validator(mode="after")
    def valid_evaluation(self) -> "FormulaInstance":
        _ordered(self.operand_fact_ids, "operand_fact_ids")
        body = self.model_dump(mode="json", exclude={"evaluation_hash", "contract_id", "contract_version"})
        if sha256_json(body) != self.evaluation_hash:
            raise ValueError("formula evaluation hash mismatch")
        return self


class ClaimKindDefinition(StrictModel):
    claim_kind_id: str = Field(pattern=ID_PATTERN)
    required_fact_roles: tuple[str, ...]
    optional_fact_roles: tuple[str, ...]
    allowed_evidence_edges: tuple[str, ...]
    materiality_contract: str
    rendering_eligibility: str
    decision_eligibility: str
    citation_requirements: str
    quarantine_behavior: Literal["fail_closed"] = "fail_closed"


class ClaimInstance(StrictModel):
    contract_id: Literal["room16.compiler.claim_instance"] = "room16.compiler.claim_instance"
    contract_version: Literal[1] = 1
    claim_id: str
    claim_kind_id: str = Field(pattern=ID_PATTERN)
    fact_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    materiality: str
    payload_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(cls, **values: Any) -> "ClaimInstance":
        values["fact_ids"] = tuple(sorted(set(values.get("fact_ids", ()))))
        values["evidence_ids"] = tuple(sorted(set(values.get("evidence_ids", ()))))
        body = dict(values)
        return cls(**values, payload_sha256=sha256_json(body))

    @model_validator(mode="after")
    def valid_payload(self) -> "ClaimInstance":
        _ordered(self.fact_ids, "fact_ids")
        _ordered(self.evidence_ids, "evidence_ids")
        body = self.model_dump(
            mode="json",
            exclude={"payload_sha256", "contract_id", "contract_version"},
        )
        if sha256_json(body) != self.payload_sha256:
            raise ValueError("claim instance payload hash mismatch")
        return self


class DecisionNodeDefinition(StrictModel):
    decision_node_definition_id: str = Field(pattern=ID_PATTERN)
    node_semantics: str
    allowed_input_kinds: tuple[str, ...]
    required_lineage: tuple[str, ...]
    compatibility: Literal["additive_v1"] = "additive_v1"


class DecisionNodeInstance(StrictModel):
    contract_id: Literal["room16.compiler.decision_node_instance"] = (
        "room16.compiler.decision_node_instance"
    )
    contract_version: Literal[1] = 1
    node_id: str
    definition_id: str = Field(pattern=ID_PATTERN)
    subject_refs: tuple[str, ...]
    payload: dict[str, Any]
    node_sha256: str = Field(pattern=SHA256_PATTERN)

    @classmethod
    def create(cls, **values: Any) -> "DecisionNodeInstance":
        values["subject_refs"] = tuple(sorted(values.get("subject_refs", ())))
        body = dict(values)
        return cls(**values, node_sha256=sha256_json(body))

    @model_validator(mode="after")
    def valid_node(self) -> "DecisionNodeInstance":
        _ordered(self.subject_refs, "subject_refs")
        body = self.model_dump(
            mode="json",
            exclude={"node_sha256", "contract_id", "contract_version"},
        )
        if sha256_json(body) != self.node_sha256:
            raise ValueError("decision node hash mismatch")
        return self


class RiskDefinition(StrictModel):
    risk_definition_id: str = Field(pattern=ID_PATTERN)
    semantic_description: str
    score_eligibility: Literal["calibrated_only", "never"]
    counterevidence_required: bool


class PermissionCorridorDefinition(StrictModel):
    permission_corridor_definition_id: str = Field(pattern=ID_PATTERN)
    allowed_rating_contract: str
    publication_contract: str
    non_advice_boundary_required: Literal[True] = True
