"""Versioned BA4-BA9 Intermediate Representation contracts."""

from __future__ import annotations

from typing import Any, ClassVar, Literal, TypeVar

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import QuarantineState, StrictModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class HashedIR(StrictModel):
    ir_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def valid_ir_hash(self) -> "HashedIR":
        body = self.model_dump(mode="json", exclude={"ir_sha256"})
        if sha256_json(body) != self.ir_sha256:
            raise ValueError("IR hash mismatch")
        return self


H = TypeVar("H", bound=HashedIR)


def create_hashed(model: type[H], **values: Any) -> H:
    draft = model.model_construct(ir_sha256="0" * 64, **values)
    body = draft.model_dump(mode="json", exclude={"ir_sha256"})
    return model.model_validate({**body, "ir_sha256": sha256_json(body)})


class SourceLocatorIR(StrictModel):
    snapshot_id: str
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_path: str
    pointer: str
    table_id: str | None = None
    cell_id: str | None = None


class ParsedRecordIR(StrictModel):
    record_id: str
    record_kind: Literal["object", "array", "scalar", "text", "csv_row"]
    pointer: str
    payload: Any


class ParsedDocumentIR(HashedIR):
    contract_id: Literal["room16.compiler.parsed_document_ir"] = "room16.compiler.parsed_document_ir"
    contract_version: Literal[1] = 1
    source_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    document_id: str
    snapshot_id: str
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    media_type: str
    parser_id: str
    parser_version: Literal[1] = 1
    records: tuple[ParsedRecordIR, ...]
    quarantine: QuarantineState = QuarantineState()


class CanonicalCellIR(StrictModel):
    cell_id: str
    row_key: str
    column_key: str
    value_state: Literal["value", "zero", "missing", "not_applicable", "dash"]
    raw_value: Any = None
    normalized_value: int | float | str | bool | None = None
    locator: SourceLocatorIR


class CanonicalTableIR(HashedIR):
    contract_id: Literal["room16.compiler.canonical_table_ir"] = "room16.compiler.canonical_table_ir"
    contract_version: Literal[1] = 1
    table_id: str
    table_definition_id: Literal[
        "financial_statement", "guidance", "operating_kpi", "source_register", "valuation"
    ]
    title: str
    row_keys: tuple[str, ...]
    column_keys: tuple[str, ...]
    cells: tuple[CanonicalCellIR, ...]
    quarantine: QuarantineState = QuarantineState()


class NormalizedRecordIR(HashedIR):
    contract_id: Literal["room16.compiler.normalized_record_ir"] = "room16.compiler.normalized_record_ir"
    contract_version: Literal[1] = 1
    record_id: str
    metric_id: str
    value_state: Literal["value", "zero", "missing", "not_applicable"]
    value: int | float | str | bool | None
    signed_value: int | float | None
    dimension: str
    unit: str
    currency: str
    scale: str
    period_kind: str
    period_start: str | None
    period_end: str | None
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    table_id: str | None = None
    cell_id: str | None = None


class TypedFactIR(HashedIR):
    contract_id: Literal["room16.compiler.typed_fact_ir"] = "room16.compiler.typed_fact_ir"
    contract_version: Literal[1] = 1
    fact_id: str
    metric_id: str
    metric_definition_id: str
    fact_kind: Literal["duration", "flow", "guidance_range", "instant", "qualitative", "ratio"]
    fact_subtype: str
    value_state: Literal["value", "zero", "missing", "not_applicable"]
    value: int | float | str | bool | None
    dimension: str
    unit: str
    currency: str
    period_kind: str
    period_start: str | None
    period_end: str | None
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    normalized_record_sha256: str = Field(pattern=SHA256_PATTERN)
    role: Literal["reported_or_derived", "formula_operand"] = "reported_or_derived"


class MetricIR(HashedIR):
    contract_id: Literal["room16.compiler.metric_ir"] = "room16.compiler.metric_ir"
    contract_version: Literal[1] = 1
    metric_instance_id: str
    metric_definition_id: str
    result_fact_id: str
    value: int | float | str | bool | None
    dimension: str
    unit: str
    period_kind: str
    binding_sha256: str = Field(pattern=SHA256_PATTERN)


class FormulaEvaluationIR(HashedIR):
    contract_id: Literal["room16.compiler.formula_evaluation_ir"] = (
        "room16.compiler.formula_evaluation_ir"
    )
    contract_version: Literal[1] = 1
    formula_instance_id: str
    formula_definition_id: str
    operand_fact_ids: tuple[str, ...]
    result_fact_id: str
    expected_value: int | float
    evaluated_value: int | float
    result_dimension: str
    rounding_policy: str
    evaluation_status: Literal["verified", "diagnostic_only"]
    evaluation_hash: str = Field(pattern=SHA256_PATTERN)


class GraphNodeIR(StrictModel):
    node_id: str
    node_kind: str
    subject_ref: str
    payload_sha256: str = Field(pattern=SHA256_PATTERN)


class GraphEdgeIR(StrictModel):
    edge_id: str
    edge_kind: str
    from_node_id: str
    to_node_id: str
    payload_sha256: str = Field(pattern=SHA256_PATTERN)


class EvidenceGraphIR(HashedIR):
    contract_id: Literal["room16.compiler.evidence_graph_ir"] = "room16.compiler.evidence_graph_ir"
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    nodes: tuple[GraphNodeIR, ...]
    edges: tuple[GraphEdgeIR, ...]
    orphan_fact_ids: tuple[str, ...]


class ClaimGraphIR(HashedIR):
    contract_id: Literal["room16.compiler.claim_graph_ir"] = "room16.compiler.claim_graph_ir"
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    nodes: tuple[GraphNodeIR, ...]
    edges: tuple[GraphEdgeIR, ...]
    claims_without_definition: tuple[str, ...]
    claims_without_evidence: tuple[str, ...]


class DecisionGraphIR(HashedIR):
    contract_id: Literal["room16.compiler.decision_graph_ir"] = "room16.compiler.decision_graph_ir"
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    nodes: tuple[GraphNodeIR, ...]
    edges: tuple[GraphEdgeIR, ...]
    legacy_payload: dict[str, Any]
    legacy_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    roundtrip_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    permission_corridor_preserved: Literal[True] = True
    rating_permission_preserved: Literal[True] = True
    non_advice_boundary_preserved: Literal[True] = True
