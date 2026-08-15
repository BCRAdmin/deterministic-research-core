"""Additive RFC-0002 IR contracts above immutable Compiler Foundation 1.0.0."""

from __future__ import annotations

from typing import Any, Literal, TypeVar

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import (
    CompileVerdictIR,
    DiagnosticIR,
    ProvenanceRef,
    StrictModel,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"


class HashedSpineIR(StrictModel):
    ir_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def valid_ir_hash(self) -> "HashedSpineIR":
        body = self.model_dump(mode="json", exclude={"ir_sha256"})
        if sha256_json(body) != self.ir_sha256:
            raise ValueError("IR hash mismatch")
        return self


H = TypeVar("H", bound=HashedSpineIR)


def create_hashed(model: type[H], **values: Any) -> H:
    draft = model.model_construct(ir_sha256="0" * 64, **values)
    body = draft.model_dump(mode="json", exclude={"ir_sha256"})
    return model.model_validate({**body, "ir_sha256": sha256_json(body)})


class SourceInputIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.source_input_ir"] = "room16.compiler.source_input_ir"
    contract_version: Literal[2] = 2
    source_input_id: str
    input_kind: Literal["source_snapshot", "legacy_compatibility"]
    archive_sha256: str = Field(pattern=SHA256_PATTERN)
    member_path: str
    media_type: str
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    payload_size: int = Field(ge=0)
    compatibility_adapter_id: str | None = None
    provenance: ProvenanceRef

    @model_validator(mode="after")
    def adapter_is_explicit(self) -> "SourceInputIR":
        if self.input_kind == "legacy_compatibility" and not self.compatibility_adapter_id:
            raise ValueError("legacy compatibility input requires an explicit adapter")
        if self.input_kind == "source_snapshot" and self.compatibility_adapter_id:
            raise ValueError("primary source snapshots cannot masquerade as compatibility inputs")
        return self


class ParsedPayloadIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.parsed_payload_ir"] = "room16.compiler.parsed_payload_ir"
    contract_version: Literal[2] = 2
    parsed_payload_id: str
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    parser_id: str
    payload_kind: Literal["json", "csv", "html", "markdown", "text"]
    payload: Any
    compatibility_adapter_id: str | None = None


class TableAxisIR(StrictModel):
    axis_id: str
    axis_kind: Literal["row", "column", "period", "unit", "scale", "header"]
    labels: tuple[str, ...]
    source_indices: tuple[int, ...]


class SemanticCellIR(StrictModel):
    cell_id: str
    row_index: int = Field(ge=0)
    column_index: int = Field(ge=0)
    row_key: str
    column_key: str
    value_state: Literal["value", "zero", "missing", "not_applicable", "dash"]
    raw_value: Any = None
    normalized_value: int | float | str | bool | None = None
    locator: ProvenanceRef


class SemanticTableIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_table_ir"] = "room16.compiler.semantic_table_ir"
    contract_version: Literal[2] = 2
    table_id: str
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    table_kind: Literal["financial_statement", "guidance", "operating_kpi", "source_register", "valuation", "generic"]
    title: str
    orientation: Literal["row_major", "transposed"]
    header_depth: int = Field(ge=0)
    row_header_depth: int = Field(ge=0)
    sparse: bool
    merged_cells_expanded: bool
    axes: tuple[TableAxisIR, ...]
    cells: tuple[SemanticCellIR, ...]


class TableDispositionIR(StrictModel):
    detected_table_id: str
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    locator: str
    disposition: Literal["registered", "excluded"]
    registered_table_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    exclusion_code: str | None = None

    @model_validator(mode="after")
    def exactly_one_disposition(self) -> "TableDispositionIR":
        if self.disposition == "registered" and (not self.registered_table_sha256 or self.exclusion_code):
            raise ValueError("registered table requires only a table hash")
        if self.disposition == "excluded" and (not self.exclusion_code or self.registered_table_sha256):
            raise ValueError("excluded table requires only an exclusion code")
        return self


class TableDiscoveryIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.table_discovery_ir"] = "room16.compiler.table_discovery_ir"
    contract_version: Literal[2] = 2
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    tables: tuple[SemanticTableIR, ...]
    dispositions: tuple[TableDispositionIR, ...]
    detected_count: int = Field(ge=0)
    registered_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)

    @model_validator(mode="after")
    def coverage_closed(self) -> "TableDiscoveryIR":
        if self.detected_count != self.registered_count + self.excluded_count:
            raise ValueError("detected tables must equal registered plus explicitly excluded")
        if self.registered_count != len(self.tables) or self.detected_count != len(self.dispositions):
            raise ValueError("table disposition counts do not match artifacts")
        return self


class NormalizedFactRecordIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.normalized_fact_record_ir"] = "room16.compiler.normalized_fact_record_ir"
    contract_version: Literal[2] = 2
    record_id: str
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    compatibility_adapter_id: Literal["authority_bundle_v3.fact_ledger"]
    fact_id: str
    metric_id: str
    value_state: Literal["value", "zero", "missing", "not_applicable"]
    value: int | float | str | bool | None
    signed_value: int | float | None
    dimension: str
    fact_type: str
    unit: str
    currency: str
    scale: str
    period_kind: str
    period_start: str | None
    period_end: str | None
    source_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_locator: str | None
    table_id: str | None
    cell_id: str | None
    formula_id: str | None
    formula_operands: dict[str, Any]


class TypedFactSpineIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.typed_fact_spine_ir"] = "room16.compiler.typed_fact_spine_ir"
    contract_version: Literal[2] = 2
    fact_id: str
    metric_id: str
    metric_definition_id: str
    fact_kind: Literal["duration", "flow", "guidance_range", "instant", "qualitative", "ratio"]
    fact_type: str
    value_state: Literal["value", "zero", "missing", "not_applicable"]
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
    table_id: str | None
    cell_id: str | None
    normalized_record_sha256: str = Field(pattern=SHA256_PATTERN)


class MetricSignatureIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.metric_signature_ir"] = "room16.compiler.metric_signature_ir"
    contract_version: Literal[2] = 2
    signature_id: str
    legacy_metric_id: str
    metric_definition_id: str
    dimension: str
    fact_kind: str
    fact_subtype: str
    period_role: str
    unit: str
    scale: str
    currency: str
    aggregation_behavior: str
    direction_contract: str
    comparison_contract: str
    expected_contract_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def expected_contract_matches(self) -> "MetricSignatureIR":
        body = self.model_dump(mode="json", exclude={"ir_sha256", "expected_contract_sha256", "contract_id", "contract_version", "signature_id"})
        if sha256_json(body) != self.expected_contract_sha256:
            raise ValueError("metric semantic contract hash mismatch")
        return self


class MetricSpineIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.metric_spine_ir"] = "room16.compiler.metric_spine_ir"
    contract_version: Literal[2] = 2
    metric_instance_id: str
    fact_id: str
    metric_id: str
    signature_id: str
    signature_sha256: str = Field(pattern=SHA256_PATTERN)
    typed_fact_sha256: str = Field(pattern=SHA256_PATTERN)
    value: int | float | str | bool | None


class PayloadGraphNodeIR(StrictModel):
    node_id: str
    node_kind: str
    subject_ref: str
    payload: Any
    payload_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def payload_hash_matches(self) -> "PayloadGraphNodeIR":
        if sha256_json(self.payload) != self.payload_sha256:
            raise ValueError("graph node payload hash mismatch")
        return self


class PayloadGraphEdgeIR(StrictModel):
    edge_id: str
    edge_kind: str
    from_node_id: str
    to_node_id: str
    ordinal: int = Field(ge=0)
    payload: dict[str, Any] = {}
    payload_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def payload_hash_matches(self) -> "PayloadGraphEdgeIR":
        if sha256_json(self.payload) != self.payload_sha256:
            raise ValueError("graph edge payload hash mismatch")
        return self


class EvidenceGraphSpineIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.evidence_graph_spine_ir"] = "room16.compiler.evidence_graph_spine_ir"
    contract_version: Literal[2] = 2
    ticker: str
    as_of_date: str
    nodes: tuple[PayloadGraphNodeIR, ...]
    edges: tuple[PayloadGraphEdgeIR, ...]
    unknown_source_ids: tuple[str, ...]


class ClaimLineageIR(StrictModel):
    claim_id: str
    span_id: str
    fact_id: str
    evidence_id: str
    source_id: str
    locator: str
    lineage_kind: Literal["declared", "semantic_alternate"]
    lineage_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def lineage_hash_matches(self) -> "ClaimLineageIR":
        body = self.model_dump(mode="json", exclude={"lineage_sha256"})
        if sha256_json(body) != self.lineage_sha256:
            raise ValueError("claim lineage hash mismatch")
        return self


class ClaimGraphSpineIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.claim_graph_spine_ir"] = "room16.compiler.claim_graph_spine_ir"
    contract_version: Literal[2] = 2
    ticker: str
    as_of_date: str
    evidence_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    nodes: tuple[PayloadGraphNodeIR, ...]
    edges: tuple[PayloadGraphEdgeIR, ...]
    numeric_lineages: tuple[ClaimLineageIR, ...]
    claims_without_lineage: tuple[str, ...]
    numeric_bindings_without_lineage: tuple[str, ...]


class DecisionGraphSpineIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.decision_graph_spine_ir"] = "room16.compiler.decision_graph_spine_ir"
    contract_version: Literal[2] = 2
    ticker: str
    as_of_date: str
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    parsed_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    root_node_id: str
    nodes: tuple[PayloadGraphNodeIR, ...]
    edges: tuple[PayloadGraphEdgeIR, ...]
    comparison_payload_sha256: str = Field(pattern=SHA256_PATTERN)
    reconstructed_payload_sha256: str = Field(pattern=SHA256_PATTERN)


class VerificationPlanIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.verification_plan_ir"] = "room16.compiler.verification_plan_ir"
    contract_version: Literal[1] = 1
    plan_id: str
    pass_id: Literal["ba9.l10.verify_semantics"] = "ba9.l10.verify_semantics"
    bound_ir_sha256s: tuple[str, ...]
    invariant_codes: tuple[str, ...]
    fail_closed: Literal[True] = True


class VerificationReportIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.verification_report_ir"] = "room16.compiler.verification_report_ir"
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    verification_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    diagnostics: tuple[DiagnosticIR, ...]
    verdict: CompileVerdictIR

    @model_validator(mode="after")
    def verdict_is_derived(self) -> "VerificationReportIR":
        derived = CompileVerdictIR.derive(list(self.diagnostics))
        if derived != self.verdict:
            raise ValueError("compile verdict must be derived only from diagnostics")
        return self
