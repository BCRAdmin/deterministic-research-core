"""Additive RFC-0003 contracts above immutable Foundation 1.0.0."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import CompileVerdictIR, DiagnosticIR
from research_agent.semantic_compiler.registry_foundation.contracts import DecisionNodeInstance

from .contracts import HashedSpineIR, PayloadGraphEdgeIR, PayloadGraphNodeIR

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class ParsedPayloadRefIR(HashedSpineIR):
    """Lossless content-addressed reference to a parsed payload.

    The raw immutable source remains the storage authority.  Keeping its full
    HTML/text body in every subsequent compile-state envelope would multiply
    hundreds of megabytes without adding semantic information.
    """

    contract_id: Literal["room16.compiler.parsed_payload_ref_ir"] = "room16.compiler.parsed_payload_ref_ir"
    contract_version: Literal[1] = 1
    parsed_payload_id: str
    parsed_payload_ir_sha256: str = Field(pattern=SHA256_PATTERN)
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    parser_id: str
    payload_kind: Literal["json", "csv", "html", "markdown", "text"]
    compatibility_adapter_id: str | None = None


class SemanticTableRefIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_table_ref_ir"] = "room16.compiler.semantic_table_ref_ir"
    contract_version: Literal[1] = 1
    table_id: str
    semantic_table_ir_sha256: str = Field(pattern=SHA256_PATTERN)
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    table_kind: str
    title: str
    orientation: str
    cell_count: int = Field(ge=0)


class SemanticCellRefIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_cell_ref_ir"] = "room16.compiler.semantic_cell_ref_ir"
    contract_version: Literal[1] = 1
    cell_id: str
    cell_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    table_id: str
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    locator_sha256: str = Field(pattern=SHA256_PATTERN)


class TableDiscoverySummaryIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.table_discovery_summary_ir"] = "room16.compiler.table_discovery_summary_ir"
    contract_version: Literal[1] = 1
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    table_discovery_ir_sha256: str = Field(pattern=SHA256_PATTERN)
    detected_count: int = Field(ge=0)
    registered_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)

    @model_validator(mode="after")
    def coverage_closed(self) -> "TableDiscoverySummaryIR":
        if self.detected_count != self.registered_count + self.excluded_count:
            raise ValueError("table discovery summary coverage incomplete")
        return self


class FormulaOperandIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.formula_operand_ir"] = "room16.compiler.formula_operand_ir"
    contract_version: Literal[1] = 1
    operand_id: str
    formula_instance_id: str
    result_fact_id: str
    role: str
    value: int | float | str | bool | None
    dimension: str
    unit: str
    currency: str
    scale: str
    period_kind: str
    period_start: str | None
    period_end: str | None
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_locator: str | None
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    normalized_record_sha256: str = Field(pattern=SHA256_PATTERN)
    origin_mode: Literal["compatibility_embedded_operand"]


class FormulaEvaluationRFC0003IR(HashedSpineIR):
    contract_id: Literal["room16.compiler.formula_evaluation_ir"] = "room16.compiler.formula_evaluation_ir"
    contract_version: Literal[3] = 3
    formula_instance_id: str
    formula_definition_id: str
    operand_ids: tuple[str, ...]
    operand_sha256s: tuple[str, ...]
    result_fact_id: str
    result_typed_fact_sha256: str = Field(pattern=SHA256_PATTERN)
    expected_value: float
    evaluated_value: float
    result_dimension: str
    rounding_policy: str
    evaluation_status: Literal["verified"] = "verified"
    evaluation_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def operand_sets_match(self) -> "FormulaEvaluationRFC0003IR":
        if not self.operand_ids or len(self.operand_ids) != len(self.operand_sha256s):
            raise ValueError("formula operands and hashes must be non-empty and aligned")
        if self.operand_ids != tuple(sorted(set(self.operand_ids))):
            raise ValueError("formula operand ids must be unique and sorted")
        return self


class CompleteEvidenceGraphIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.complete_evidence_graph_ir"] = "room16.compiler.complete_evidence_graph_ir"
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    compiler_mode: Literal["compatibility_shadow"] = "compatibility_shadow"
    source_native_fact_generation: Literal[False] = False
    nodes: tuple[PayloadGraphNodeIR, ...]
    edges: tuple[PayloadGraphEdgeIR, ...]
    unknown_source_ids: tuple[str, ...]
    unresolved_declared_table_ids: tuple[str, ...]
    unresolved_declared_cell_ids: tuple[str, ...]


class SemanticDecisionEdgeIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_decision_edge_ir"] = "room16.compiler.semantic_decision_edge_ir"
    contract_version: Literal[1] = 1
    edge_id: str
    edge_kind: Literal["derived_from_packet", "constrains", "contributes_to", "opposes", "explains"]
    from_node_id: str
    to_node_id: str
    ordinal: int = Field(ge=0)


class SemanticDecisionGraphIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_decision_graph_ir"] = "room16.compiler.semantic_decision_graph_ir"
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    generic_decision_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    decision_packet_source_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_authority_sha256: str = Field(pattern=SHA256_PATTERN)
    nodes: tuple[DecisionNodeInstance, ...]
    edges: tuple[SemanticDecisionEdgeIR, ...]
    required_definition_ids: tuple[str, ...]
    bound_definition_ids: tuple[str, ...]
    unknown_definition_ids: tuple[str, ...]


class SemanticCompileStateIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_compile_state_ir"] = "room16.compiler.semantic_compile_state_ir"
    contract_version: Literal[1] = 1
    rfc_id: Literal["RFC-0003"] = "RFC-0003"
    stage: str
    ticker: str
    as_of_date: str
    archive_name: str
    archive_sha256: str = Field(pattern=SHA256_PATTERN)
    compiler_mode: Literal["compatibility_shadow"] = "compatibility_shadow"
    source_native_fact_generation: Literal[False] = False
    release_ready: Literal[False] = False
    publication_allowed: Literal[False] = False
    renderer_cutover: Literal[False] = False
    ba10_authorized: Literal[False] = False
    artifacts: dict[str, Any]
    artifact_sha256s: dict[str, str]

    @model_validator(mode="after")
    def artifact_hashes_match(self) -> "SemanticCompileStateIR":
        if tuple(self.artifacts) != tuple(sorted(self.artifacts)):
            raise ValueError("compile state artifacts must be sorted")
        if tuple(self.artifact_sha256s) != tuple(sorted(self.artifact_sha256s)):
            raise ValueError("compile state artifact hashes must be sorted")
        if set(self.artifacts) != set(self.artifact_sha256s):
            raise ValueError("compile state artifact hash coverage incomplete")
        for key, value in self.artifacts.items():
            if sha256_json(value) != self.artifact_sha256s[key]:
                raise ValueError(f"compile state artifact hash mismatch:{key}")
        return self


class VerificationPlanRFC0003IR(HashedSpineIR):
    contract_id: Literal["room16.compiler.verification_plan_ir"] = "room16.compiler.verification_plan_ir"
    contract_version: Literal[3] = 3
    plan_id: str
    pass_id: Literal["ba9.l10.verify_semantics"] = "ba9.l10.verify_semantics"
    bound_ir_sha256s: tuple[str, ...]
    bound_parsed_ir_sha256s: tuple[str, ...]
    bound_artifact_sha256s: dict[str, str]
    invariant_codes: tuple[str, ...]
    fail_closed: Literal[True] = True


class VerificationReportRFC0003IR(HashedSpineIR):
    contract_id: Literal["room16.compiler.verification_report_ir"] = "room16.compiler.verification_report_ir"
    contract_version: Literal[3] = 3
    ticker: str
    as_of_date: str
    verification_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    diagnostics: tuple[DiagnosticIR, ...]
    verdict: CompileVerdictIR
    kernel_execution_record_sha256s: tuple[str, ...] = ()
    sealed_after_kernel: bool = False

    @model_validator(mode="after")
    def verdict_is_derived(self) -> "VerificationReportRFC0003IR":
        if CompileVerdictIR.derive(list(self.diagnostics)) != self.verdict:
            raise ValueError("compile verdict must be derived only from diagnostics")
        return self
