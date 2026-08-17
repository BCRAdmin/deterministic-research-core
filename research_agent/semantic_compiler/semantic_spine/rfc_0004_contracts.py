"""Additive RFC-0004 semantic integrity contracts.

These contracts live above immutable Compiler Foundation 1.0.0 and retained
Registry Foundation 1.1.0.  They do not alter either ABI.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import CompileVerdictIR, DiagnosticIR

from .contracts import HashedSpineIR, PayloadGraphEdgeIR, PayloadGraphNodeIR
from .rfc_0003_contracts import SemanticDecisionEdgeIR

SHA256_PATTERN = r"^[0-9a-f]{64}$"
GIT_SHA_PATTERN = r"^[0-9a-f]{40}$"


class SemanticRegistryLockIR(HashedSpineIR):
    """All semantic authorities that can change pass meaning or output."""

    contract_id: Literal["room16.compiler.semantic_registry_lock_ir"] = (
        "room16.compiler.semantic_registry_lock_ir"
    )
    contract_version: Literal[1] = 1
    semantic_registry_authority_sha256: str = Field(pattern=SHA256_PATTERN)
    metric_signature_authority_sha256: str = Field(pattern=SHA256_PATTERN)
    formula_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    evidence_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    claim_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    decision_policy_sha256: str = Field(pattern=SHA256_PATTERN)
    pass_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    compiler_implementation_commit: str = Field(pattern=GIT_SHA_PATTERN)
    compiler_implementation_version: Literal["4.0.0-rfc0004"] = "4.0.0-rfc0004"
    compiler_implementation_sha256: str = Field(pattern=SHA256_PATTERN)


class SemanticTableArtifactRefIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_table_artifact_ref_ir"] = (
        "room16.compiler.semantic_table_artifact_ref_ir"
    )
    contract_version: Literal[2] = 2
    table_id: str
    semantic_table_ir_sha256: str = Field(pattern=SHA256_PATTERN)
    source_input_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_uri: str = Field(pattern=r"^room16-table://sha256/[0-9a-f]{64}$")
    cell_count: int = Field(ge=0)
    locator_contract: Literal["source_input+table_locator+row_index+column_index"] = (
        "source_input+table_locator+row_index+column_index"
    )
    table_kind: str
    title: str
    orientation: str


class LegacyTableCellMappingIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.legacy_table_cell_mapping_ir"] = (
        "room16.compiler.legacy_table_cell_mapping_ir"
    )
    contract_version: Literal[1] = 1
    fact_id: str
    legacy_table_id: str
    legacy_cell_id: str
    canonical_table_id: str | None
    canonical_cell_id: str | None
    mapping_status: Literal["mapped", "quarantined_unresolved"]
    source_locator: str | None
    mapping_basis: str

    @model_validator(mode="after")
    def mapping_is_truthful(self) -> "LegacyTableCellMappingIR":
        bound = self.canonical_table_id is not None and self.canonical_cell_id is not None
        if (self.mapping_status == "mapped") != bound:
            raise ValueError("legacy table/cell mapping status does not match canonical binding")
        return self


class ExpectedFormulaRoleContractIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.expected_formula_role_contract_ir"] = (
        "room16.compiler.expected_formula_role_contract_ir"
    )
    contract_version: Literal[1] = 1
    formula_definition_id: str
    legacy_formula_id: str
    role: str
    expected_dimension: str
    allowed_role_patterns: tuple[str, ...]
    required: bool
    min_cardinality: int = Field(ge=0)
    max_cardinality: int = Field(ge=1)


class FormulaOperandFactIR(HashedSpineIR):
    """Evidence-backed typed fact used only as a formula input.

    It is separate from source-native ``TypedFactSpineIR`` so compatibility
    evidence cannot be misrepresented as source-native L5 output.
    """

    contract_id: Literal["room16.compiler.formula_operand_fact_ir"] = (
        "room16.compiler.formula_operand_fact_ir"
    )
    contract_version: Literal[1] = 1
    operand_fact_id: str
    metric_role: str
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
    source_locators: tuple[str, ...]
    evidence_payload_sha256s: tuple[str, ...]
    origin_mode: Literal["compatibility_evidence_typed_fact"] = (
        "compatibility_evidence_typed_fact"
    )

    @model_validator(mode="after")
    def lineage_is_complete(self) -> "FormulaOperandFactIR":
        for field in ("source_ids", "evidence_ids", "source_locators", "evidence_payload_sha256s"):
            values = getattr(self, field)
            if not values or values != tuple(sorted(set(values))):
                raise ValueError(f"{field} must be non-empty, unique and sorted")
        return self


class PolicyParameterIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.policy_parameter_ir"] = (
        "room16.compiler.policy_parameter_ir"
    )
    contract_version: Literal[1] = 1
    parameter_id: str
    policy_definition_id: str
    formula_definition_id: str
    role: str
    value: int | float | str | bool | None
    dimension: str
    unit: str
    currency: str
    period_kind: Literal["not_applicable"] = "not_applicable"
    authority_sha256: str = Field(pattern=SHA256_PATTERN)
    origin_mode: Literal["registered_policy_parameter"] = "registered_policy_parameter"


class FormulaOperandBindingIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.formula_operand_ir"] = (
        "room16.compiler.formula_operand_ir"
    )
    contract_version: Literal[2] = 2
    operand_id: str
    formula_instance_id: str
    result_fact_id: str
    role: str
    expected_role_contract: ExpectedFormulaRoleContractIR
    operand_fact_or_parameter_id: str | None
    binding_kind: Literal[
        "typed_fact", "evidence_typed_fact", "policy_parameter", "quarantined_unresolved_operand"
    ]
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
    source_locators: tuple[str, ...]
    origin_mode: Literal[
        "existing_typed_fact",
        "compatibility_evidence_typed_fact",
        "registered_policy_parameter",
        "quarantined_unresolved_operand",
    ]

    @model_validator(mode="after")
    def binding_is_truthful(self) -> "FormulaOperandBindingIR":
        unresolved = self.binding_kind == "quarantined_unresolved_operand"
        if unresolved != (self.operand_fact_or_parameter_id is None):
            raise ValueError("operand binding status and target disagree")
        if not unresolved and self.origin_mode != "registered_policy_parameter":
            if not self.source_ids or not self.evidence_ids:
                raise ValueError("fact operand requires source and evidence lineage")
        if unresolved and (self.source_ids or self.evidence_ids or self.source_locators):
            raise ValueError("unresolved operand cannot claim provenance")
        return self


class SemanticDecisionNodeIR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_decision_node_ir"] = (
        "room16.compiler.semantic_decision_node_ir"
    )
    contract_version: Literal[2] = 2
    node_id: str
    definition_id: str
    instance_presence: Literal["present", "not_present_schema_coverage"]
    claim_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    rule_refs: tuple[str, ...]
    policy_refs: tuple[str, ...]
    payload: dict[str, Any]

    @model_validator(mode="after")
    def references_are_sets(self) -> "SemanticDecisionNodeIR":
        for field in (
            "claim_ids", "fact_ids", "evidence_ids", "source_ids", "rule_refs", "policy_refs"
        ):
            values = getattr(self, field)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{field} must be unique and sorted")
        if self.instance_presence == "not_present_schema_coverage" and any(
            (self.claim_ids, self.fact_ids, self.evidence_ids, self.source_ids)
        ):
            raise ValueError("not-present schema nodes cannot satisfy instance lineage")
        return self


class CompleteEvidenceGraphRFC0004IR(HashedSpineIR):
    contract_id: Literal["room16.compiler.complete_evidence_graph_ir"] = (
        "room16.compiler.complete_evidence_graph_ir"
    )
    contract_version: Literal[2] = 2
    ticker: str
    as_of_date: str
    compiler_mode: Literal["compatibility_shadow"] = "compatibility_shadow"
    source_native_fact_generation: Literal[False] = False
    nodes: tuple[PayloadGraphNodeIR, ...]
    edges: tuple[PayloadGraphEdgeIR, ...]
    unknown_source_ids: tuple[str, ...]
    table_artifact_refs: tuple[SemanticTableArtifactRefIR, ...]
    legacy_table_cell_mappings: tuple[LegacyTableCellMappingIR, ...]
    unresolved_executable_fact_ids: tuple[str, ...]


class SemanticDecisionGraphRFC0004IR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_decision_graph_ir"] = (
        "room16.compiler.semantic_decision_graph_ir"
    )
    contract_version: Literal[2] = 2
    ticker: str
    as_of_date: str
    generic_decision_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    decision_packet_source_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_authority_sha256: str = Field(pattern=SHA256_PATTERN)
    claim_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    nodes: tuple[SemanticDecisionNodeIR, ...]
    edges: tuple[SemanticDecisionEdgeIR, ...]
    required_definition_ids: tuple[str, ...]
    present_definition_ids: tuple[str, ...]
    schema_coverage_definition_ids: tuple[str, ...]
    unknown_definition_ids: tuple[str, ...]


class SemanticCompileStateRFC0004IR(HashedSpineIR):
    contract_id: Literal["room16.compiler.semantic_compile_state_ir"] = (
        "room16.compiler.semantic_compile_state_ir"
    )
    contract_version: Literal[2] = 2
    rfc_id: Literal["RFC-0004"] = "RFC-0004"
    stage: str
    ticker: str
    as_of_date: str
    archive_name: str
    archive_sha256: str = Field(pattern=SHA256_PATTERN)
    semantic_registry_lock: SemanticRegistryLockIR
    compiler_mode: Literal["compatibility_shadow"] = "compatibility_shadow"
    source_native_fact_generation: Literal[False] = False
    release_ready: Literal[False] = False
    publication_allowed: Literal[False] = False
    renderer_cutover: Literal[False] = False
    ba10_authorized: Literal[False] = False
    artifacts: dict[str, Any]
    artifact_sha256s: dict[str, str]

    @model_validator(mode="after")
    def artifact_hashes_match(self) -> "SemanticCompileStateRFC0004IR":
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


class ExecutionAttestationIR(HashedSpineIR):
    """Non-semantic, post-kernel execution and build attestation."""

    contract_id: Literal["room16.compiler.execution_attestation_ir"] = (
        "room16.compiler.execution_attestation_ir"
    )
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    final_compile_state_sha256: str = Field(pattern=SHA256_PATTERN)
    verification_report_sha256: str = Field(pattern=SHA256_PATTERN)
    pass_execution_record_sha256s: tuple[str, ...]
    pass_execution_complete: bool
    fixture_attestation_sha256: str = Field(pattern=SHA256_PATTERN)
    fixture_diagnostic_codes_stable: bool
    semantic_verdict: CompileVerdictIR

    @model_validator(mode="after")
    def execution_records_are_present(self) -> "ExecutionAttestationIR":
        if self.pass_execution_complete and not self.pass_execution_record_sha256s:
            raise ValueError("complete execution attestation requires pass records")
        return self


class VerificationReportRFC0004IR(HashedSpineIR):
    contract_id: Literal["room16.compiler.verification_report_ir"] = (
        "room16.compiler.verification_report_ir"
    )
    contract_version: Literal[4] = 4
    ticker: str
    as_of_date: str
    verification_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    diagnostics: tuple[DiagnosticIR, ...]
    verdict: CompileVerdictIR
    sealed_by_l10: Literal[True] = True

    @model_validator(mode="after")
    def verdict_is_derived(self) -> "VerificationReportRFC0004IR":
        if CompileVerdictIR.derive(list(self.diagnostics)) != self.verdict:
            raise ValueError("compile verdict must be derived only from diagnostics")
        return self
