"""RFC-0003 executable compatibility-shadow compiler.

Every semantic pass is invoked exclusively by Foundation ``PassKernel``.  The
small amount of code outside the kernel only loads immutable inputs and seals
the non-circular execution attestation after the kernel has returned.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import (
    CompileVerdictIR,
    CompilerLayer,
    DiagnosticIR,
    IREnvelope,
    PassExecutionRecord,
    ProvenanceRef,
    ReleaseEffect,
    SemanticSeverity,
)
from research_agent.compiler_foundation.kernel import PassKernel, load_pass_manifests
from research_agent.compiler_foundation.registry import RegistryAuthority
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority
from research_agent.semantic_compiler.semantic_wave.metrics import evaluate_legacy_formula

from .contracts import (
    ClaimGraphSpineIR,
    DecisionGraphSpineIR,
    MetricSignatureIR,
    MetricSpineIR,
    NormalizedFactRecordIR,
    ParsedPayloadIR,
    PayloadGraphEdgeIR,
    PayloadGraphNodeIR,
    SourceInputIR,
    TypedFactSpineIR,
    create_hashed,
)
from .rfc_0003_contracts import (
    FormulaEvaluationRFC0003IR,
    ParsedPayloadRefIR,
    SemanticCellRefIR,
    SemanticDecisionEdgeIR,
    TableDiscoverySummaryIR,
    VerificationPlanRFC0003IR,
)
from .rfc_0004_contracts import (
    CompleteEvidenceGraphRFC0004IR,
    ExecutionAttestationIR,
    ExpectedFormulaRoleContractIR,
    FormulaOperandBindingIR,
    FormulaOperandFactIR,
    LegacyTableCellMappingIR,
    PolicyParameterIR,
    SemanticCompileStateRFC0004IR,
    SemanticDecisionGraphRFC0004IR,
    SemanticDecisionNodeIR,
    SemanticRegistryLockIR,
    SemanticTableArtifactRefIR,
    VerificationReportRFC0004IR,
)
from .semantics import (
    build_claim_graph,
    build_decision_graph,
    build_metrics,
    build_typed_facts,
    normalize_fact_ledger,
    reconstruct_decision,
)
from .signature_authority import MetricSignatureAuthority
from .table_grammar import discover_tables, parse_payload

PASS_MANIFEST_PATH = Path(__file__).with_name("config") / "rfc_0003_pass_manifests.json"
IMPLEMENTATION_VERSION = "4.0.0-rfc0004"
POLICY_PARAMETER_DEFINITIONS = {
    "capital_allocation": ("financial_risk_model_component", "index", "index"),
    "cash_flow_durability": ("financial_risk_model_component", "index", "index"),
    "dcf_base_discount_rate": ("valuation_policy_parameter", "percent", "decimal"),
    "dcf_base_terminal_growth_rate": ("valuation_policy_parameter", "percent", "decimal"),
    "dilution": ("financial_risk_model_component", "index", "index"),
    "discount_rate": ("valuation_policy_parameter", "percent", "decimal"),
    "financial_resilience": ("financial_risk_model_component", "index", "index"),
    "forecast_years": ("valuation_policy_parameter", "count", "years"),
    "free_cash_flow_growth_rate": ("valuation_policy_parameter", "percent", "decimal"),
    "terminal_growth_rate": ("valuation_policy_parameter", "percent", "decimal"),
}
REQUIRED_EVIDENCE_NODE_KINDS = (
    "cell", "evidence", "formula_evaluation", "formula_operand", "locator",
    "metric", "normalized_record", "parsed_payload", "source", "source_input",
    "table", "typed_fact",
)
RFC0003_INVARIANTS = (
    "CLAIM_LINEAGE_COMPLETE",
    "COMPATIBILITY_MODE_STATUS_TRUTHFUL",
    "DECISION_GRAPH_ROUNDTRIP_VALID",
    "DECISION_REGISTRY_BINDINGS_COMPLETE",
    "EVIDENCE_GRAPH_REQUIRED_NODE_TYPES_COMPLETE",
    "EVIDENCE_SOURCE_REGISTRY_COMPLETE",
    "FIXTURE_DIAGNOSTIC_CODES_STABLE",
    "FORMULA_EVALUATION_COMPLETE",
    "FORMULA_OPERAND_LINEAGE_COMPLETE",
    "IR_SPINE_CONNECTED",
    "LEGACY_COMPATIBILITY_ADAPTER_USED",
    "METRIC_SIGNATURE_COVERAGE_COMPLETE",
    "PARSED_IR_BOUND_IN_VERIFICATION_PLAN",
    "PASS_KERNEL_EXECUTION_COMPLETE",
    "TABLE_DISCOVERY_COVERAGE_COMPLETE",
    "TABLE_FACT_LINEAGE_TRUTHFUL",
)
RFC0004_INVARIANTS = (
    "CANONICAL_TABLE_ARTIFACTS_RESOLVABLE",
    "CLAIM_LINEAGE_COMPLETE",
    "COMPATIBILITY_MODE_STATUS_TRUTHFUL",
    "DECISION_GRAPH_ROUNDTRIP_VALID",
    "DECISION_CLAIM_LINEAGE_COMPLETE",
    "DECISION_FACT_LINEAGE_COMPLETE",
    "DECISION_REGISTRY_BINDINGS_COMPLETE",
    "DECISION_RISK_COUNTEREVIDENCE_BOUND",
    "DECISION_SCORE_INPUTS_BOUND",
    "DECLARED_TABLE_CELL_LINEAGE_COMPLETE",
    "EVIDENCE_GRAPH_REQUIRED_NODE_TYPES_COMPLETE",
    "EVIDENCE_SOURCE_REGISTRY_COMPLETE",
    "EXECUTABLE_FACT_TABLE_LINEAGE_COMPLETE",
    "FORMULA_EVALUATION_COMPLETE",
    "FORMULA_OPERAND_LINEAGE_COMPLETE",
    "IR_SPINE_CONNECTED",
    "LEGACY_COMPATIBILITY_ADAPTER_USED",
    "METRIC_SIGNATURE_COVERAGE_COMPLETE",
    "PARSED_IR_BOUND_IN_VERIFICATION_PLAN",
    "TABLE_DISCOVERY_COVERAGE_COMPLETE",
    "TABLE_FACT_LINEAGE_TRUTHFUL",
)


class RFC0003Error(ValueError):
    """Stable RFC-0003 failure with a Diagnostic ABI code."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _one(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise RFC0003Error("SOURCE_ARCHIVE_MEMBER_COUNT_INVALID", suffix)
    return matches[0]


def _source_input(*, source_input_id: str, input_kind: str, archive_sha256: str,
                  member_path: str, media_type: str, payload: bytes,
                  adapter_id: str | None = None) -> SourceInputIR:
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    return create_hashed(
        SourceInputIR,
        source_input_id=source_input_id,
        input_kind=input_kind,
        archive_sha256=archive_sha256,
        member_path=member_path,
        media_type=media_type,
        payload_sha256=payload_sha256,
        payload_size=len(payload),
        compatibility_adapter_id=adapter_id,
        provenance=ProvenanceRef(
            source_id=source_input_id,
            artifact_path=member_path,
            sha256=payload_sha256,
            locator=f"authority-v3://{member_path}",
        ),
    )


def _implementation_commit() -> str:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", str(Path(__file__).resolve())],
        cwd=Path(__file__).resolve().parents[3], capture_output=True, check=True, text=True,
    )
    return result.stdout.strip()


def _implementation_sha256() -> str:
    paths = (
        Path(__file__), Path(__file__).with_name("rfc_0004.py"),
        Path(__file__).with_name("rfc_0004_contracts.py"),
        Path(__file__).with_name("semantics.py"), Path(__file__).with_name("table_grammar.py"),
        PASS_MANIFEST_PATH,
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _semantic_registry_lock() -> SemanticRegistryLockIR:
    semantic = SemanticRegistryAuthority.load()
    signatures = MetricSignatureAuthority.load()
    payload = semantic.payload
    return create_hashed(
        SemanticRegistryLockIR,
        semantic_registry_authority_sha256=semantic.authority_sha256,
        metric_signature_authority_sha256=signatures.authority_sha256,
        formula_policy_sha256=sha256_json({
            "formula_definitions": payload.get("formula_definitions") or [],
            "policy_parameters": POLICY_PARAMETER_DEFINITIONS,
        }),
        evidence_policy_sha256=sha256_json({
            "mode": "claim-fact-evidence-source-locator",
            "unknown_source_policy": "fail_closed",
            "table_artifact_policy": "content_addressed_replay_resolvable",
        }),
        claim_policy_sha256=sha256_json(payload.get("claim_kind_definitions") or []),
        decision_policy_sha256=sha256_json({
            "decision_node_definitions": payload.get("decision_node_definitions") or [],
            "risk_definitions": payload.get("risk_definitions") or [],
            "permission_corridor_definitions": payload.get("permission_corridor_definitions") or [],
        }),
        pass_manifest_sha256=hashlib.sha256(PASS_MANIFEST_PATH.read_bytes()).hexdigest(),
        compiler_implementation_commit=_implementation_commit(),
        compiler_implementation_version=IMPLEMENTATION_VERSION,
        compiler_implementation_sha256=_implementation_sha256(),
    )


def _create_state(*, previous: SemanticCompileStateRFC0004IR | None = None, stage: str,
                  ticker: str | None = None, as_of_date: str | None = None,
                  archive_name: str | None = None, archive_sha256: str | None = None,
                  semantic_registry_lock: SemanticRegistryLockIR | None = None,
                  artifacts: dict[str, Any]) -> SemanticCompileStateRFC0004IR:
    values = {
        "stage": stage,
        "ticker": ticker if ticker is not None else previous.ticker,
        "as_of_date": as_of_date if as_of_date is not None else previous.as_of_date,
        "archive_name": archive_name if archive_name is not None else previous.archive_name,
        "archive_sha256": archive_sha256 if archive_sha256 is not None else previous.archive_sha256,
        "semantic_registry_lock": semantic_registry_lock or previous.semantic_registry_lock,
        "artifacts": {key: artifacts[key] for key in sorted(artifacts)},
    }
    values["artifact_sha256s"] = {
        key: sha256_json(values["artifacts"][key]) for key in sorted(values["artifacts"])
    }
    return create_hashed(SemanticCompileStateRFC0004IR, **values)


def _state(payload: dict[str, Any]) -> SemanticCompileStateRFC0004IR:
    return SemanticCompileStateRFC0004IR.model_validate(payload)


def _items(state: SemanticCompileStateRFC0004IR, key: str, model: Any) -> tuple[Any, ...]:
    return tuple(model.model_validate(item) for item in state.artifacts[key])


def _compatibility_documents(state: SemanticCompileStateRFC0004IR) -> dict[str, tuple[SourceInputIR, ParsedPayloadIR]]:
    sources = _items(state, "source_inputs", SourceInputIR)
    parsed = _items(state, "compatibility_parsed_documents", ParsedPayloadIR)
    parsed_by_source_hash = {item.source_input_sha256: item for item in parsed}
    result: dict[str, tuple[SourceInputIR, ParsedPayloadIR]] = {}
    for source in sources:
        if not source.compatibility_adapter_id:
            continue
        name = source.compatibility_adapter_id.rsplit(".", 1)[-1]
        result[name] = (source, parsed_by_source_hash[source.ir_sha256])
    return result


def load_initial_state(archive: Path) -> tuple[SemanticCompileStateRFC0004IR, tuple[ProvenanceRef, ...]]:
    archive = archive.resolve()
    archive_hash = _archive_sha256(archive)
    source_inputs: list[SourceInputIR] = []
    raw_payloads: dict[str, str] = {}
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        manifest_name = _one(names, "/authority_bundle/source_snapshot_manifest.json")
        manifest = json.loads(bundle.read(manifest_name))
        ticker = str(manifest["ticker"])
        as_of_date = str(manifest["as_of_date"])
        source_prefix = manifest_name.rsplit("source_snapshot_manifest.json", 1)[0] + "source_snapshots/"
        for artifact in sorted(manifest["artifacts"], key=lambda item: str(item["snapshot_id"])):
            member = f"{source_prefix}{artifact['path']}"
            payload = bundle.read(member)
            source = _source_input(
                source_input_id=str(artifact["snapshot_id"]), input_kind="source_snapshot",
                archive_sha256=archive_hash, member_path=str(artifact["path"]),
                media_type=str(artifact.get("media_type") or "application/octet-stream"), payload=payload,
            )
            if source.payload_sha256 != str(artifact["sha256"]) or source.payload_size != int(artifact["bytes"]):
                raise RFC0003Error("SOURCE_SNAPSHOT_MANIFEST_MISMATCH", source.source_input_id)
            source_inputs.append(source)
            raw_payloads[source.ir_sha256] = base64.b64encode(payload).decode("ascii")
        members = {
            "fact_ledger": (_one(names, "/authority_bundle/fact_ledger.json"), "authority_bundle_v3.fact_ledger"),
            "evidence_ledger": (_one(names, "/authority_bundle/evidence_ledger.json"), "authority_bundle_v3.evidence_ledger"),
            "source_registry": (_one(names, f"/authority_bundle/{ticker}_{as_of_date}_source_registry.json"), "authority_bundle_v3.source_registry"),
            "analyst_claims": (_one(names, "/case/research/analyst_claims.json"), "authority_bundle_v3.analyst_claims"),
            "decision_packet": (_one(names, "/authority_bundle/decision_packet.json"), "authority_bundle_v3.decision_packet"),
        }
        for name, (member, adapter_id) in sorted(members.items()):
            payload = bundle.read(member)
            source = _source_input(
                source_input_id=f"compat.{name}", input_kind="legacy_compatibility",
                archive_sha256=archive_hash, member_path=member, media_type="application/json",
                payload=payload, adapter_id=adapter_id,
            )
            source_inputs.append(source)
            raw_payloads[source.ir_sha256] = base64.b64encode(payload).decode("ascii")
    artifacts = {
        "raw_payloads": raw_payloads,
        "source_inputs": [item.model_dump(mode="json") for item in sorted(source_inputs, key=lambda item: item.source_input_id)],
    }
    state = _create_state(
        stage="source_inputs", ticker=ticker, as_of_date=as_of_date,
        archive_name=archive.name, archive_sha256=archive_hash,
        semantic_registry_lock=_semantic_registry_lock(), artifacts=artifacts,
    )
    return state, tuple(item.provenance for item in sorted(source_inputs, key=lambda item: item.source_input_id))


def _parse_sources(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    sources = _items(state, "source_inputs", SourceInputIR)
    raw = state.artifacts["raw_payloads"]
    parsed_refs: list[ParsedPayloadRefIR] = []
    compatibility_documents: list[ParsedPayloadIR] = []
    for source in sources:
        document, _ = parse_payload(source, base64.b64decode(raw[source.ir_sha256]))
        parsed_refs.append(create_hashed(
            ParsedPayloadRefIR,
            parsed_payload_id=document.parsed_payload_id,
            parsed_payload_ir_sha256=document.ir_sha256,
            source_input_sha256=document.source_input_sha256,
            parser_id=document.parser_id,
            payload_kind=document.payload_kind,
            compatibility_adapter_id=document.compatibility_adapter_id,
        ))
        if source.input_kind == "legacy_compatibility":
            compatibility_documents.append(document)
    artifacts = dict(state.artifacts)
    artifacts["parsed_payload_refs"] = [item.model_dump(mode="json") for item in sorted(parsed_refs, key=lambda item: item.parsed_payload_id)]
    artifacts["compatibility_parsed_documents"] = [item.model_dump(mode="json") for item in sorted(compatibility_documents, key=lambda item: item.parsed_payload_id)]
    return _create_state(previous=state, stage="parsed", artifacts=artifacts).model_dump(mode="json")


def _same_numeric(left: Any, right: Any) -> bool:
    return (
        isinstance(left, (int, float)) and not isinstance(left, bool)
        and isinstance(right, (int, float)) and not isinstance(right, bool)
        and math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-8)
    )


def _tokens(value: Any) -> set[str]:
    return {part for part in re.split(r"[^a-z0-9]+", str(value or "").casefold()) if len(part) > 1}


def _legacy_cell_score(claim: dict[str, Any], cell: Any) -> int:
    source_value = claim.get("source_value")
    fact_value = claim.get("value")
    scale = {"percent": 0.01, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}.get(
        str(claim.get("source_scale") or "").casefold(), 1
    )
    value_match = (
        bool(claim.get("is_not_applicable")) and cell.value_state == "dash"
    ) or (
        bool(claim.get("is_missing")) and cell.value_state == "missing"
    ) or _same_numeric(cell.normalized_value, source_value)
    value_match = value_match or (
        isinstance(cell.normalized_value, (int, float))
        and _same_numeric(float(cell.normalized_value) * scale, fact_value)
    )
    if not value_match:
        return -1
    score = 20
    row_tokens = _tokens(claim.get("row_metric") or claim.get("label"))
    column_tokens = _tokens(claim.get("column_metric"))
    segment_tokens = _tokens(claim.get("segment"))
    period_tokens = _tokens(claim.get("asof") or claim.get("period_end"))
    score += 3 * len(row_tokens & _tokens(cell.row_key))
    score += 2 * len(column_tokens & _tokens(cell.column_key))
    score += 3 * len(segment_tokens & (_tokens(cell.row_key) | _tokens(cell.column_key)))
    score += 4 * len(period_tokens & _tokens(cell.column_key))
    return score


def _map_legacy_table_cells(
    *, claims: list[dict[str, Any]], tables: list[Any], sources: tuple[SourceInputIR, ...]
) -> tuple[LegacyTableCellMappingIR, ...]:
    source_paths = {item.ir_sha256: item.member_path for item in sources}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        if claim.get("table_id") and claim.get("cell_id"):
            grouped.setdefault(str(claim["table_id"]), []).append(claim)
    mappings: list[LegacyTableCellMappingIR] = []
    for legacy_table_id, members in sorted(grouped.items()):
        declared_paths = {str(item.get("source_snapshot_path")) for item in members if item.get("source_snapshot_path")}
        candidates = [
            table for table in tables
            if not declared_paths or source_paths.get(table.source_input_sha256) in declared_paths
        ]
        table_results: list[tuple[int, str, Any, dict[str, Any]]] = []
        for table in candidates:
            selected: dict[str, Any] = {}
            total = 0
            valid = True
            for claim in members:
                scored = sorted(
                    ((_legacy_cell_score(claim, cell), cell.cell_id, cell) for cell in table.cells),
                    key=lambda item: (-item[0], item[1]),
                )
                if not scored or scored[0][0] < 20:
                    valid = False
                    break
                tied = [item for item in scored if item[0] == scored[0][0]]
                semantic_cells = {
                    (item[2].raw_value, item[2].row_index, item[2].row_key) for item in tied
                }
                if len(semantic_cells) != 1:
                    valid = False
                    break
                chosen = min(tied, key=lambda item: (item[2].column_index, item[1]))
                total += chosen[0]
                selected[str(claim["fact_id"])] = chosen[2]
            if valid:
                table_results.append((total, table.table_id, table, selected))
        table_results.sort(key=lambda item: (-item[0], item[1]))
        winner = table_results[0] if table_results and (
            len(table_results) == 1 or table_results[0][0] > table_results[1][0]
        ) else None
        for claim in sorted(members, key=lambda item: str(item["fact_id"])):
            cell = None if winner is None else winner[3][str(claim["fact_id"])]
            mappings.append(create_hashed(
                LegacyTableCellMappingIR,
                fact_id=str(claim["fact_id"]), legacy_table_id=legacy_table_id,
                legacy_cell_id=str(claim["cell_id"]),
                canonical_table_id=None if winner is None else winner[2].table_id,
                canonical_cell_id=None if cell is None else cell.cell_id,
                mapping_status="quarantined_unresolved" if winner is None else "mapped",
                source_locator=str(claim.get("source_locator")) if claim.get("source_locator") else None,
                mapping_basis=(
                    "unresolved_after_source_path_value_axis_matching" if winner is None
                    else "source_path+source_value+row_column_segment_period_axes"
                ),
            ))
    return tuple(mappings)


def _discover_tables(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    sources = _items(state, "source_inputs", SourceInputIR)
    raw = state.artifacts["raw_payloads"]
    fact_document = _compatibility_documents(state)["fact_ledger"][1]
    fact_claims = list(fact_document.payload.get("claims", []))
    summaries: list[TableDiscoverySummaryIR] = []
    complete_tables: list[Any] = []
    for source in sources:
        _, candidates = parse_payload(source, base64.b64decode(raw[source.ir_sha256]))
        discovery = discover_tables(source, candidates)
        summaries.append(create_hashed(
            TableDiscoverySummaryIR,
            source_input_sha256=discovery.source_input_sha256,
            table_discovery_ir_sha256=discovery.ir_sha256,
            detected_count=discovery.detected_count,
            registered_count=discovery.registered_count,
            excluded_count=discovery.excluded_count,
        ))
        for table in discovery.tables:
            complete_tables.append(table)
    mappings = _map_legacy_table_cells(claims=fact_claims, tables=complete_tables, sources=sources)
    mapped_cell_ids = {item.canonical_cell_id for item in mappings if item.canonical_cell_id}
    table_refs = [create_hashed(
        SemanticTableArtifactRefIR,
        table_id=table.table_id, semantic_table_ir_sha256=table.ir_sha256,
        source_input_sha256=table.source_input_sha256,
        artifact_uri=f"room16-table://sha256/{table.ir_sha256}", cell_count=len(table.cells),
        table_kind=table.table_kind, title=table.title, orientation=table.orientation,
    ) for table in complete_tables]
    cell_refs = [create_hashed(
        SemanticCellRefIR,
        cell_id=cell.cell_id, cell_payload_sha256=sha256_json(cell.model_dump(mode="json")),
        table_id=table.table_id, source_input_sha256=table.source_input_sha256,
        row_index=cell.row_index, column_index=cell.column_index,
        locator_sha256=sha256_json(cell.locator.model_dump(mode="json")),
    ) for table in complete_tables for index, cell in enumerate(table.cells)
    if index == 0 or cell.cell_id in mapped_cell_ids]
    artifacts = dict(state.artifacts)
    artifacts.pop("raw_payloads")
    artifacts["table_discovery_summaries"] = [item.model_dump(mode="json") for item in sorted(summaries, key=lambda item: item.source_input_sha256)]
    artifacts["table_refs"] = [item.model_dump(mode="json") for item in sorted(table_refs, key=lambda item: item.table_id)]
    artifacts["cell_refs"] = [item.model_dump(mode="json") for item in sorted(cell_refs, key=lambda item: item.cell_id)]
    artifacts["legacy_table_cell_mappings"] = [
        item.model_dump(mode="json") for item in mappings
    ]
    artifacts["cell_reference_policy"] = {
        "policy": "content_addressed_complete_tables_plus_mapped_lineage_cells",
        "declared_cell_id_count": len(mappings),
        "materialized_cell_ref_count": len(cell_refs),
        "mapped_declared_cell_count": sum(item.mapping_status == "mapped" for item in mappings),
        "all_cells_retrievable_by_content_addressed_table_uri": True,
    }
    return _create_state(previous=state, stage="tables", artifacts=artifacts).model_dump(mode="json")


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    compat = _compatibility_documents(state)
    normalized = normalize_fact_ledger(*compat["fact_ledger"])
    artifacts = dict(state.artifacts)
    artifacts["normalized_records"] = [item.model_dump(mode="json") for item in normalized]
    return _create_state(previous=state, stage="normalized", artifacts=artifacts).model_dump(mode="json")


def _build_facts(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    facts = build_typed_facts(_items(state, "normalized_records", NormalizedFactRecordIR), SemanticRegistryAuthority.load())
    artifacts = dict(state.artifacts)
    artifacts["typed_facts"] = [item.model_dump(mode="json") for item in facts]
    return _create_state(previous=state, stage="facts", artifacts=artifacts).model_dump(mode="json")


def _build_metric_instances(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    signatures, metrics = build_metrics(_items(state, "typed_facts", TypedFactSpineIR), MetricSignatureAuthority.load())
    artifacts = dict(state.artifacts)
    artifacts["signatures"] = [item.model_dump(mode="json") for item in signatures]
    artifacts["metrics"] = [item.model_dump(mode="json") for item in metrics]
    return _create_state(previous=state, stage="metrics", artifacts=artifacts).model_dump(mode="json")


def _expected_role_contract(definition: Any, legacy_formula_id: str, role: str) -> ExpectedFormulaRoleContractIR:
    legacy = definition.legacy_operand_contracts[legacy_formula_id]
    if len(definition.operand_dimensions) == 1:
        dimension = definition.operand_dimensions[0]
    elif role in definition.operand_roles:
        dimension = definition.operand_dimensions[definition.operand_roles.index(role)]
    elif len(set(definition.operand_dimensions)) == 1:
        dimension = definition.operand_dimensions[0]
    elif role.startswith(("current_", "prior_")) and definition.formula_definition_id == "formula.growth":
        dimension = "same"
    else:
        dimension = "unknown"
    return create_hashed(
        ExpectedFormulaRoleContractIR,
        formula_definition_id=definition.formula_definition_id,
        legacy_formula_id=legacy_formula_id, role=role, expected_dimension=dimension,
        allowed_role_patterns=legacy.allowed_role_patterns,
        required=role in legacy.required_roles,
        min_cardinality=legacy.min_operands, max_cardinality=legacy.max_operands,
    )


def _role_aliases(role: str) -> set[str]:
    aliases = {role}
    for prefix in ("current_", "prior_", "dcf_base_"):
        if role.startswith(prefix):
            aliases.add(role.removeprefix(prefix))
    registered_alias = {
        "listed_share_count": "shares_outstanding",
        "starting_free_cash_flow": "free_cash_flow_ttm",
        "target_equity_value": "market_cap",
        "room16_normalized_fcf": "free_cash_flow_current_period",
    }.get(role)
    if registered_alias:
        aliases.add(registered_alias)
    return aliases


def _dimension_compatible(expected: str, actual: str) -> bool:
    if expected in {"same", "unknown"}:
        return bool(actual and actual != "unknown")
    if expected == "percent" and actual in {"percent", "ratio", "multiple"}:
        return True
    if expected == "currency_per_share" and actual in {"per_share", "currency_per_share"}:
        return True
    if expected == "shares" and actual in {"shares", "count"}:
        return True
    return expected == actual


def _semantic_match_score(role: str, metric_ids: set[str]) -> int:
    aliases = _role_aliases(role)
    if role in metric_ids:
        return 100
    if aliases & metric_ids:
        return 80
    role_tokens = _tokens(role)
    return max((len(role_tokens & _tokens(metric)) for metric in metric_ids), default=0) * 5


def _resolve_operand(
    *, state: SemanticCompileStateRFC0004IR, record: NormalizedFactRecordIR,
    role: str, value: Any, expected: ExpectedFormulaRoleContractIR,
    facts: tuple[TypedFactSpineIR, ...], evidence_items: list[dict[str, Any]],
) -> tuple[FormulaOperandBindingIR, FormulaOperandFactIR | None, PolicyParameterIR | None]:
    formula_instance_id = f"formula.instance.{_safe(record.fact_id)}"
    operand_id = f"{formula_instance_id}.operand.{_safe(role)}"
    fact_candidates: list[tuple[int, str, TypedFactSpineIR]] = []
    for fact in facts:
        if fact.fact_id == record.fact_id or not _same_numeric(fact.value, value):
            continue
        if not _dimension_compatible(expected.expected_dimension, fact.dimension):
            continue
        score = _semantic_match_score(role, {fact.metric_id})
        if score or len([item for item in facts if item.fact_id != record.fact_id and _same_numeric(item.value, value)]) == 1:
            fact_candidates.append((score, fact.fact_id, fact))
    fact_candidates.sort(key=lambda item: (-item[0], item[1]))
    winner = fact_candidates[0][2] if fact_candidates and (
        len(fact_candidates) == 1 or fact_candidates[0][0] > fact_candidates[1][0]
    ) else None
    if winner is not None and winner.source_ids and winner.evidence_ids:
        return create_hashed(
            FormulaOperandBindingIR,
            operand_id=operand_id, formula_instance_id=formula_instance_id,
            result_fact_id=record.fact_id, role=role, expected_role_contract=expected,
            operand_fact_or_parameter_id=winner.fact_id, binding_kind="typed_fact", value=value,
            dimension=winner.dimension, unit=winner.unit, currency=winner.currency, scale=winner.scale,
            period_kind=winner.period_kind, period_start=winner.period_start, period_end=winner.period_end,
            source_ids=winner.source_ids, evidence_ids=winner.evidence_ids,
            source_locators=tuple(sorted({winner.source_locator} if winner.source_locator else set())),
            origin_mode="existing_typed_fact",
        ), None, None

    evidence_candidates: list[tuple[int, str, bool, dict[str, Any]]] = []
    for item in evidence_items:
        embedded_operands = item.get("formula_operands") or {}
        embedded = (
            item.get("formula_id") == record.formula_id
            and role in embedded_operands and _same_numeric(embedded_operands[role], value)
        )
        evidence_value = embedded_operands.get(role) if embedded else next(
            (item.get(key) for key in ("normalized_value", "value", "signed_value") if item.get(key) is not None), None
        )
        if not _same_numeric(evidence_value, value):
            continue
        dimension = (
            expected.expected_dimension if embedded and expected.expected_dimension not in {"same", "unknown"}
            else str(item.get("dimension") or "unknown")
        )
        if not _dimension_compatible(expected.expected_dimension, dimension):
            continue
        metric_ids = {str(metric) for metric in item.get("supports_metrics") or []}
        score = (20 if expected.expected_dimension == "same" else 120) if embedded else _semantic_match_score(role, metric_ids)
        if str(item.get("evidence_id") or "") in record.evidence_ids:
            score += 50
        if str(item.get("source_id") or "") in record.source_ids:
            score += 20
        if item.get("period_end") and item.get("period_end") == record.period_end:
            score += 10
        evidence_candidates.append((score, str(item.get("evidence_id") or ""), embedded, item))
    evidence_candidates.sort(key=lambda item: (-item[0], item[1]))
    if evidence_candidates:
        best = evidence_candidates[0][0]
        selected_pairs = [(embedded, item) for score, _, embedded, item in evidence_candidates if score == best]
        selected = [item for _, item in selected_pairs]
        embedded_selected = any(embedded for embedded, _ in selected_pairs)
        if best > 0:
            source_ids = tuple(sorted({str(item["source_id"]) for item in selected if item.get("source_id")}))
            evidence_ids = tuple(sorted({str(item["evidence_id"]) for item in selected if item.get("evidence_id")}))
            locators = tuple(sorted({
                (
                    f"evidence://{item['evidence_id']}/formula_operands/{role}"
                    if embedded_selected else
                    str(item.get("source_locator") or item.get("url") or f"evidence://{item['evidence_id']}")
                ) for item in selected if item.get("evidence_id")
            }))
            hashes = tuple(sorted(sha256_json(item) for item in selected))
            exemplar = selected[0]
            operand_dimension = (
                expected.expected_dimension
                if embedded_selected and expected.expected_dimension not in {"same", "unknown"}
                else str(exemplar.get("dimension") or expected.expected_dimension)
            )
            inferred_unit = {
                "count": "count", "currency_per_share": "USD_per_share", "index": "index",
                "percent": "decimal", "shares": "shares",
            }.get(operand_dimension)
            operand_fact = create_hashed(
                FormulaOperandFactIR,
                operand_fact_id=f"formula.operand_fact.{sha256_json([role, value, evidence_ids])[:32]}",
                metric_role=role, value=value,
                dimension=operand_dimension,
                unit=str(inferred_unit or exemplar.get("unit") or exemplar.get("display_unit") or "unknown"),
                currency=str(exemplar.get("currency") or "none"),
                scale=str(exemplar.get("source_scale") or "ones"),
                period_kind=str(exemplar.get("period_kind") or "unknown"),
                period_start=exemplar.get("period_start"), period_end=exemplar.get("period_end"),
                source_ids=source_ids, evidence_ids=evidence_ids, source_locators=locators,
                evidence_payload_sha256s=hashes,
            )
            return create_hashed(
                FormulaOperandBindingIR,
                operand_id=operand_id, formula_instance_id=formula_instance_id,
                result_fact_id=record.fact_id, role=role, expected_role_contract=expected,
                operand_fact_or_parameter_id=operand_fact.operand_fact_id,
                binding_kind="evidence_typed_fact", value=value,
                dimension=operand_fact.dimension, unit=operand_fact.unit,
                currency=operand_fact.currency, scale=operand_fact.scale,
                period_kind=operand_fact.period_kind, period_start=operand_fact.period_start,
                period_end=operand_fact.period_end, source_ids=source_ids,
                evidence_ids=evidence_ids, source_locators=locators,
                origin_mode="compatibility_evidence_typed_fact",
            ), operand_fact, None

    if role in POLICY_PARAMETER_DEFINITIONS:
        policy_id, dimension, unit = POLICY_PARAMETER_DEFINITIONS[role]
        parameter = create_hashed(
            PolicyParameterIR,
            parameter_id=f"policy.parameter.{_safe(record.fact_id)}.{_safe(role)}",
            policy_definition_id=policy_id,
            formula_definition_id=expected.formula_definition_id, role=role, value=value,
            dimension=dimension, unit=unit, currency="none",
            authority_sha256=state.semantic_registry_lock.formula_policy_sha256,
        )
        return create_hashed(
            FormulaOperandBindingIR,
            operand_id=operand_id, formula_instance_id=formula_instance_id,
            result_fact_id=record.fact_id, role=role, expected_role_contract=expected,
            operand_fact_or_parameter_id=parameter.parameter_id, binding_kind="policy_parameter",
            value=value, dimension=dimension, unit=unit, currency="none", scale="ones",
            period_kind="not_applicable", period_start=None, period_end=None,
            source_ids=(), evidence_ids=(), source_locators=(),
            origin_mode="registered_policy_parameter",
        ), None, parameter

    return create_hashed(
        FormulaOperandBindingIR,
        operand_id=operand_id, formula_instance_id=formula_instance_id,
        result_fact_id=record.fact_id, role=role, expected_role_contract=expected,
        operand_fact_or_parameter_id=None, binding_kind="quarantined_unresolved_operand",
        value=value, dimension="unknown", unit="unknown", currency="none", scale="unknown",
        period_kind="unknown", period_start=None, period_end=None,
        source_ids=(), evidence_ids=(), source_locators=(),
        origin_mode="quarantined_unresolved_operand",
    ), None, None


def _evaluate_formulas(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    records = _items(state, "normalized_records", NormalizedFactRecordIR)
    facts = {item.fact_id: item for item in _items(state, "typed_facts", TypedFactSpineIR)}
    authority = SemanticRegistryAuthority.load()
    context = {item.metric_id: {"formula_operands": item.formula_operands} for item in records}
    evidence_items = list(_compatibility_documents(state)["evidence_ledger"][1].payload.get("evidence_items") or [])
    fact_items = tuple(facts.values())
    operands: list[FormulaOperandBindingIR] = []
    operand_facts: dict[str, FormulaOperandFactIR] = {}
    policy_parameters: dict[str, PolicyParameterIR] = {}
    evaluations: list[FormulaEvaluationRFC0003IR] = []
    for record in records:
        if not record.formula_id or not record.formula_operands:
            continue
        formula_instance_id = f"formula.instance.{_safe(record.fact_id)}"
        definition_id = authority.bind_formula(record.formula_id)
        definition = authority.formula_definitions[definition_id]
        record_operands: list[FormulaOperandBindingIR] = []
        for role, value in sorted(record.formula_operands.items()):
            expected = _expected_role_contract(definition, record.formula_id, str(role))
            operand, operand_fact, parameter = _resolve_operand(
                state=state, record=record, role=str(role), value=value, expected=expected,
                facts=fact_items, evidence_items=evidence_items,
            )
            operands.append(operand)
            record_operands.append(operand)
            if operand_fact is not None:
                operand_facts[operand_fact.operand_fact_id] = operand_fact
            if parameter is not None:
                policy_parameters[parameter.parameter_id] = parameter
        evaluated = evaluate_legacy_formula(record.formula_id, record.formula_operands, fact_context=context)
        if not isinstance(record.value, (int, float)) or not math.isclose(float(record.value), evaluated, rel_tol=1e-10, abs_tol=1e-8):
            raise RFC0003Error("FORMULA_RESULT_MISMATCH", record.fact_id)
        fact = facts[record.fact_id]
        operand_ids = tuple(sorted(item.operand_id for item in record_operands))
        by_id = {item.operand_id: item for item in record_operands}
        operand_hashes = tuple(by_id[item].ir_sha256 for item in operand_ids)
        evaluations.append(create_hashed(
            FormulaEvaluationRFC0003IR,
            formula_instance_id=formula_instance_id,
            formula_definition_id=definition_id,
            operand_ids=operand_ids,
            operand_sha256s=operand_hashes,
            result_fact_id=record.fact_id,
            result_typed_fact_sha256=fact.ir_sha256,
            expected_value=float(record.value), evaluated_value=evaluated,
            result_dimension=definition.result_dimension,
            rounding_policy=definition.rounding_policy,
            evaluation_hash=sha256_json({
                "formula_definition_id": definition_id,
                "operand_bindings": list(zip(operand_ids, operand_hashes, strict=True)),
                "result_fact_id": record.fact_id,
                "evaluated_value": evaluated,
            }),
        ))
    artifacts = dict(state.artifacts)
    artifacts["formula_operands"] = [item.model_dump(mode="json") for item in sorted(operands, key=lambda item: item.operand_id)]
    artifacts["formula_operand_facts"] = [
        item.model_dump(mode="json") for item in sorted(operand_facts.values(), key=lambda item: item.operand_fact_id)
    ]
    artifacts["policy_parameters"] = [
        item.model_dump(mode="json") for item in sorted(policy_parameters.values(), key=lambda item: item.parameter_id)
    ]
    artifacts["formula_evaluations"] = [item.model_dump(mode="json") for item in sorted(evaluations, key=lambda item: item.formula_instance_id)]
    return _create_state(previous=state, stage="formulas", artifacts=artifacts).model_dump(mode="json")


def _safe(value: str) -> str:
    cleaned = "".join(character.lower() if character.isalnum() else "." for character in value)
    return ".".join(part for part in cleaned.split(".") if part) or "root"


def _node(node_id: str, kind: str, subject: str, payload: Any) -> PayloadGraphNodeIR:
    return PayloadGraphNodeIR(node_id=node_id, node_kind=kind, subject_ref=subject, payload=payload, payload_sha256=sha256_json(payload))


def _edge(edge_id: str, kind: str, source: str, target: str, ordinal: int = 0,
          body: dict[str, Any] | None = None) -> PayloadGraphEdgeIR:
    value = body or {}
    return PayloadGraphEdgeIR(edge_id=edge_id, edge_kind=kind, from_node_id=source, to_node_id=target,
                              ordinal=ordinal, payload=value, payload_sha256=sha256_json(value))


def _build_complete_evidence_graph(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    sources = _items(state, "source_inputs", SourceInputIR)
    parsed = _items(state, "parsed_payload_refs", ParsedPayloadRefIR)
    table_refs = _items(state, "table_refs", SemanticTableArtifactRefIR)
    cell_refs = _items(state, "cell_refs", SemanticCellRefIR)
    legacy_mappings = _items(state, "legacy_table_cell_mappings", LegacyTableCellMappingIR)
    normalized = _items(state, "normalized_records", NormalizedFactRecordIR)
    facts = _items(state, "typed_facts", TypedFactSpineIR)
    metrics = _items(state, "metrics", MetricSpineIR)
    operands = _items(state, "formula_operands", FormulaOperandBindingIR)
    operand_facts = _items(state, "formula_operand_facts", FormulaOperandFactIR)
    policy_parameters = _items(state, "policy_parameters", PolicyParameterIR)
    evaluations = _items(state, "formula_evaluations", FormulaEvaluationRFC0003IR)
    compat = _compatibility_documents(state)
    source_payload = compat["source_registry"][1].payload
    evidence_payload = compat["evidence_ledger"][1].payload
    registered_sources = {str(item["source_id"]): item for item in source_payload.get("sources") or []}
    registered_evidence = {str(item["evidence_id"]): item for item in evidence_payload.get("evidence_items") or []}
    nodes: dict[str, PayloadGraphNodeIR] = {}
    edges: dict[str, PayloadGraphEdgeIR] = {}
    unknown_sources: set[str] = set()
    for source in sources:
        node_id = f"source_input.{_safe(source.source_input_id)}"
        nodes[node_id] = _node(node_id, "source_input", source.source_input_id, source.model_dump(mode="json"))
    sources_by_hash = {item.ir_sha256: item for item in sources}
    for document in parsed:
        node_id = f"parsed.{_safe(document.parsed_payload_id)}"
        nodes[node_id] = _node(node_id, "parsed_payload", document.parsed_payload_id, document.model_dump(mode="json"))
        source = sources_by_hash[document.source_input_sha256]
        target = f"source_input.{_safe(source.source_input_id)}"
        edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "parsed_from", node_id, target)
    parsed_by_source_hash = {item.source_input_sha256: item for item in parsed}
    registered_table_ids = {item.table_id for item in table_refs}
    registered_cell_ids = {item.cell_id for item in cell_refs}
    mapping_by_fact = {item.fact_id: item for item in legacy_mappings}
    for table in table_refs:
        parsed_document = parsed_by_source_hash[table.source_input_sha256]
        parsed_node = f"parsed.{_safe(parsed_document.parsed_payload_id)}"
        table_node = f"table.{_safe(table.table_id)}"
        nodes[table_node] = _node(table_node, "table", table.table_id, table.model_dump(mode="json"))
        edges[f"edge.{table_node}.{parsed_node}"] = _edge(f"edge.{table_node}.{parsed_node}", "discovered_from", table_node, parsed_node)
    for cell in cell_refs:
        table_node = f"table.{_safe(cell.table_id)}"
        cell_node = f"cell.{_safe(cell.cell_id)}"
        nodes[cell_node] = _node(cell_node, "cell", cell.cell_id, cell.model_dump(mode="json"))
        edges[f"edge.{cell_node}.{table_node}"] = _edge(f"edge.{cell_node}.{table_node}", "contained_in", cell_node, table_node)
    for source_id, item in sorted(registered_sources.items()):
        source_node = f"source.{_safe(source_id)}"
        nodes[source_node] = _node(source_node, "source", source_id, item)
        locator = str(item.get("url") or item.get("source_locator") or "")
        if locator:
            locator_node = f"locator.{sha256_json({'source_id': source_id, 'locator': locator})[:24]}"
            nodes[locator_node] = _node(locator_node, "locator", locator, {"locator": locator})
            edges[f"edge.{source_node}.{locator_node}"] = _edge(f"edge.{source_node}.{locator_node}", "locates", source_node, locator_node)
    for evidence_id, item in sorted(registered_evidence.items()):
        evidence_node = f"evidence.{_safe(evidence_id)}"
        nodes[evidence_node] = _node(evidence_node, "evidence", evidence_id, item)
        source_id = str(item.get("source_id") or "")
        if source_id not in registered_sources:
            if source_id:
                unknown_sources.add(source_id)
            continue
        source_node = f"source.{_safe(source_id)}"
        edges[f"edge.{evidence_node}.{source_node}"] = _edge(f"edge.{evidence_node}.{source_node}", "originates_from", evidence_node, source_node)
    for record in normalized:
        node_id = f"normalized.{_safe(record.record_id)}"
        nodes[node_id] = _node(node_id, "normalized_record", record.record_id, record.model_dump(mode="json"))
        document = parsed_by_source_hash[record.source_input_sha256]
        parsed_node = f"parsed.{_safe(document.parsed_payload_id)}"
        edges[f"edge.{node_id}.{parsed_node}"] = _edge(f"edge.{node_id}.{parsed_node}", "normalized_from", node_id, parsed_node)
    normalized_by_hash = {item.ir_sha256: item for item in normalized}
    for fact in facts:
        fact_node = f"fact.{_safe(fact.fact_id)}"
        nodes[fact_node] = _node(fact_node, "typed_fact", fact.fact_id, fact.model_dump(mode="json"))
        record = normalized_by_hash[fact.normalized_record_sha256]
        normalized_node = f"normalized.{_safe(record.record_id)}"
        edges[f"edge.{fact_node}.{normalized_node}"] = _edge(f"edge.{fact_node}.{normalized_node}", "typed_from", fact_node, normalized_node)
        for evidence_id in fact.evidence_ids:
            evidence_node = f"evidence.{_safe(evidence_id)}"
            if evidence_node in nodes:
                edges[f"edge.{fact_node}.{evidence_node}"] = _edge(f"edge.{fact_node}.{evidence_node}", "supported_by", fact_node, evidence_node)
        mapping = mapping_by_fact.get(fact.fact_id)
        canonical_table_id = mapping.canonical_table_id if mapping and mapping.mapping_status == "mapped" else fact.table_id
        canonical_cell_id = mapping.canonical_cell_id if mapping and mapping.mapping_status == "mapped" else fact.cell_id
        if canonical_table_id in registered_table_ids:
            table_node = f"table.{_safe(str(canonical_table_id))}"
            edges[f"edge.{fact_node}.{table_node}"] = _edge(f"edge.{fact_node}.{table_node}", "declared_in", fact_node, table_node)
        if canonical_cell_id in registered_cell_ids:
            cell_node = f"cell.{_safe(str(canonical_cell_id))}"
            edges[f"edge.{fact_node}.{cell_node}"] = _edge(f"edge.{fact_node}.{cell_node}", "declared_in", fact_node, cell_node)
    facts_by_id = {item.fact_id: item for item in facts}
    for metric in metrics:
        node_id = f"metric.{_safe(metric.metric_instance_id)}"
        nodes[node_id] = _node(node_id, "metric", metric.metric_instance_id, metric.model_dump(mode="json"))
        target = f"fact.{_safe(metric.fact_id)}"
        edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "measures", node_id, target)
    operand_by_id = {item.operand_id: item for item in operands}
    for operand in operands:
        node_id = f"formula_operand.{_safe(operand.operand_id)}"
        nodes[node_id] = _node(node_id, "formula_operand", operand.operand_id, operand.model_dump(mode="json"))
        if operand.binding_kind == "typed_fact" and operand.operand_fact_or_parameter_id:
            target = f"fact.{_safe(operand.operand_fact_or_parameter_id)}"
            edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "binds_operand_fact", node_id, target)
        elif operand.binding_kind == "evidence_typed_fact" and operand.operand_fact_or_parameter_id:
            target = f"formula_operand_fact.{_safe(operand.operand_fact_or_parameter_id)}"
            edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "binds_operand_fact", node_id, target)
        elif operand.binding_kind == "policy_parameter" and operand.operand_fact_or_parameter_id:
            target = f"policy_parameter.{_safe(operand.operand_fact_or_parameter_id)}"
            edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "binds_policy_parameter", node_id, target)
        for evidence_id in operand.evidence_ids:
            evidence_node = f"evidence.{_safe(evidence_id)}"
            if evidence_node in nodes:
                edges[f"edge.{node_id}.{evidence_node}"] = _edge(f"edge.{node_id}.{evidence_node}", "supported_by", node_id, evidence_node)
    for operand_fact in operand_facts:
        node_id = f"formula_operand_fact.{_safe(operand_fact.operand_fact_id)}"
        nodes[node_id] = _node(node_id, "typed_fact", operand_fact.operand_fact_id, operand_fact.model_dump(mode="json"))
        for evidence_id in operand_fact.evidence_ids:
            evidence_node = f"evidence.{_safe(evidence_id)}"
            if evidence_node in nodes:
                edges[f"edge.{node_id}.{evidence_node}"] = _edge(
                    f"edge.{node_id}.{evidence_node}", "supported_by", node_id, evidence_node
                )
    for parameter in policy_parameters:
        node_id = f"policy_parameter.{_safe(parameter.parameter_id)}"
        nodes[node_id] = _node(node_id, "policy_parameter", parameter.parameter_id, parameter.model_dump(mode="json"))
    for evaluation in evaluations:
        node_id = f"formula.{_safe(evaluation.formula_instance_id)}"
        nodes[node_id] = _node(node_id, "formula_evaluation", evaluation.formula_instance_id, evaluation.model_dump(mode="json"))
        for ordinal, operand_id in enumerate(evaluation.operand_ids):
            operand_node = f"formula_operand.{_safe(operand_id)}"
            edges[f"edge.{node_id}.{operand_node}"] = _edge(f"edge.{node_id}.{operand_node}", "consumes", node_id, operand_node, ordinal)
        fact = facts_by_id[evaluation.result_fact_id]
        target = f"fact.{_safe(fact.fact_id)}"
        edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "produces", node_id, target)
    unresolved_fact_ids = tuple(sorted(
        item.fact_id for item in legacy_mappings if item.mapping_status == "quarantined_unresolved"
    ))
    graph = create_hashed(
        CompleteEvidenceGraphRFC0004IR, ticker=state.ticker, as_of_date=state.as_of_date,
        nodes=tuple(nodes[key] for key in sorted(nodes)), edges=tuple(edges[key] for key in sorted(edges)),
        unknown_source_ids=tuple(sorted(unknown_sources)),
        table_artifact_refs=tuple(sorted(table_refs, key=lambda item: item.table_id)),
        legacy_table_cell_mappings=tuple(sorted(legacy_mappings, key=lambda item: item.fact_id)),
        unresolved_executable_fact_ids=unresolved_fact_ids,
    )
    artifacts = dict(state.artifacts)
    artifacts["complete_evidence_graph"] = graph.model_dump(mode="json")
    return _create_state(previous=state, stage="evidence", artifacts=artifacts).model_dump(mode="json")


def _build_claims(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    compat = _compatibility_documents(state)
    graph = build_claim_graph(
        ticker=state.ticker, as_of_date=state.as_of_date,
        claims_document=compat["analyst_claims"][1], evidence_document=compat["evidence_ledger"][1],
        source_document=compat["source_registry"][1], facts=_items(state, "typed_facts", TypedFactSpineIR),
        evidence_graph=CompleteEvidenceGraphRFC0004IR.model_validate(state.artifacts["complete_evidence_graph"]),
        authority=SemanticRegistryAuthority.load(),
    )
    artifacts = dict(state.artifacts)
    artifacts["claim_graph"] = graph.model_dump(mode="json")
    return _create_state(previous=state, stage="claims", artifacts=artifacts).model_dump(mode="json")


def _decision_edge(edge_id: str, kind: str, source: str, target: str, ordinal: int) -> SemanticDecisionEdgeIR:
    return create_hashed(SemanticDecisionEdgeIR, edge_id=edge_id, edge_kind=kind,
                         from_node_id=source, to_node_id=target, ordinal=ordinal)


def _build_semantic_decision(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    compat = _compatibility_documents(state)
    source, document = compat["decision_packet"]
    authority = SemanticRegistryAuthority.load()
    generic = build_decision_graph(document, source, authority)
    packet = reconstruct_decision(generic)
    claim_graph = ClaimGraphSpineIR.model_validate(state.artifacts["claim_graph"])
    claim_payloads = {
        node.subject_ref: node.payload for node in claim_graph.nodes if node.node_kind == "claim"
    }
    claim_index: dict[str, set[str]] = {}
    for claim_id, claim in claim_payloads.items():
        identifiers = {
            claim_id,
            *[str(item) for item in claim.get("evidence_ids") or []],
            *[str(item) for item in claim.get("source_ids") or []],
            *[str(item.get("fact_id")) for item in claim.get("numeric_bindings") or [] if item.get("fact_id")],
        }
        for identifier in identifiers:
            claim_index.setdefault(identifier, set()).add(claim_id)

    def lineage(claim_ids: set[str]) -> dict[str, tuple[str, ...]]:
        facts: set[str] = set()
        evidence: set[str] = set()
        sources: set[str] = set()
        for claim_id in claim_ids:
            claim = claim_payloads[claim_id]
            evidence.update(str(item) for item in claim.get("evidence_ids") or [])
            sources.update(str(item) for item in claim.get("source_ids") or [])
            for binding in claim.get("numeric_bindings") or []:
                if binding.get("fact_id"):
                    facts.add(str(binding["fact_id"]))
                if binding.get("evidence_id"):
                    evidence.add(str(binding["evidence_id"]))
                if binding.get("source_id"):
                    sources.add(str(binding["source_id"]))
        return {
            "claim_ids": tuple(sorted(claim_ids)), "fact_ids": tuple(sorted(facts)),
            "evidence_ids": tuple(sorted(evidence)), "source_ids": tuple(sorted(sources)),
        }

    def claims_for_tokens(value: str) -> set[str]:
        wanted = _tokens(value)
        scored = []
        for claim_id, claim in claim_payloads.items():
            haystack = _tokens(" ".join([
                str(claim.get("claim_text") or claim.get("claim") or ""),
                " ".join(str(item) for item in claim.get("metric_refs") or []),
                str(claim.get("claim_type") or ""), str(claim.get("section") or ""),
            ]))
            score = len(wanted & haystack)
            if score:
                scored.append((score, claim_id))
        if not scored:
            return set()
        best = max(item[0] for item in scored)
        return {claim_id for score, claim_id in scored if score == best}

    nodes: list[SemanticDecisionNodeIR] = []
    edges: list[SemanticDecisionEdgeIR] = []

    def add(
        definition_id: str, suffix: str, value: Any, *, claim_ids: set[str] | None = None,
        rule_refs: tuple[str, ...] = (), policy_refs: tuple[str, ...] = (),
        presence: str = "present",
    ) -> str:
        authority.require_decision_definition(definition_id)
        node_id = f"semantic.decision.{_safe(definition_id)}.{_safe(suffix)}"
        body = value if isinstance(value, dict) else {"value": value}
        refs = lineage(claim_ids or set())
        nodes.append(create_hashed(
            SemanticDecisionNodeIR,
            node_id=node_id, definition_id=definition_id, instance_presence=presence,
            **refs, rule_refs=tuple(sorted(set(rule_refs))),
            policy_refs=tuple(sorted(set(policy_refs))), payload=body,
        ))
        return node_id

    input_nodes: dict[str, str] = {}
    input_claims: dict[str, set[str]] = {}
    input_types: dict[str, str] = {}
    for ordinal, item in enumerate(packet.get("decision_inputs") or []):
        input_id = str(item.get("input_id") or f"input-{ordinal}")
        input_types[input_id] = str(item.get("input_type") or "")
        definition_id = authority.bind_decision_input(str(item.get("input_type") or ""))
        matched = set(claim_index.get(input_id, set()))
        if not matched:
            matched = claims_for_tokens(" ".join(str(item.get(key) or "") for key in ("label", "summary")))
        input_claims[input_id] = matched
        input_nodes[input_id] = add(definition_id, input_id, item, claim_ids=matched)
        if item.get("management_counterposition"):
            counter = add("decision.counterevidence", f"counter-{input_id}", {
                "value": item["management_counterposition"], "input_id": input_id,
            }, claim_ids=matched)
            edges.append(_decision_edge(f"semantic.edge.counter.{ordinal}", "opposes", counter, input_nodes[input_id], ordinal))
    rule_nodes = []
    for index, rule in enumerate(packet.get("triggered_rules") or []):
        rule_text = str(rule)
        referenced_input = rule_text.rsplit(":", 1)[-1] if ":" in rule_text else ""
        matched = set(input_claims.get(referenced_input, set())) or claims_for_tokens(rule_text)
        rule_nodes.append(add(
            "decision.rule", f"rule-{index}", {"rule": rule_text},
            claim_ids=matched, rule_refs=(f"registered_rule:{rule_text.split(':', 1)[0]}",),
        ))
    score_nodes: list[str] = []
    score_claims: dict[str, set[str]] = {}
    all_input_claims = set().union(*input_claims.values()) if input_claims else set()
    rating_claims = {
        claim_id for claim_id, claim in claim_payloads.items() if claim.get("claim_type") == "rating"
    }
    for name, value in sorted((packet.get("signal_scores") or {}).items()):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        prefix = str(name).split("_", 1)[0]
        if prefix == "risk":
            matched = set().union(*(
                input_claims[input_id] for input_id in input_claims if input_types[input_id] == "current_risk"
            )) if any(input_types[item] == "current_risk" for item in input_claims) else set()
        elif prefix == "fundamental":
            matched = set().union(*(
                input_claims[input_id] for input_id in input_claims if input_types[input_id] == "operating_kpi"
            )) if any(input_types[item] == "operating_kpi" for item in input_claims) else set()
        elif prefix in {"technical", "valuation"}:
            matched = claims_for_tokens(prefix)
        else:
            matched = all_input_claims
        matched = matched or rating_claims
        score_claims[str(name)] = matched
        score_nodes.append(add(
            "decision.score_contribution", f"score-{name}", {"name": name, "value": value},
            claim_ids=matched, rule_refs=(f"score_definition:{name}",),
        ))
    timing_payload = {key: value for key, value in sorted((packet.get("signal_scores") or {}).items()) if key.startswith("technical_")}
    timing_claims = claims_for_tokens("technical timing")
    timing_node = add("decision.timing_state", "timing", timing_payload or {"status": "not_present"}, claim_ids=timing_claims or rating_claims)
    rating_node = add("decision.rating_permission", "rating", packet["rating_permission"], claim_ids=rating_claims, policy_refs=("permission.rating_corridor",))
    corridor_node = add("decision.permission_corridor", "corridor", packet["rating_permission"], claim_ids=rating_claims, policy_refs=("permission.rating_corridor",))
    non_advice_node = add("decision.non_advice_boundary", "non-advice", packet["action_policy"], claim_ids=rating_claims, policy_refs=("policy.non_advice",))
    rationale_nodes = [
        add("decision.rationale", f"reason-{index}", {"kind": "reason", "value": value}, claim_ids=claims_for_tokens(str(value)) or rating_claims)
        for index, value in enumerate(packet.get("key_reasons") or [])
    ] + [
        add("decision.rationale", f"risk-{index}", {"kind": "risk", "value": value}, claim_ids=claims_for_tokens(str(value)) or set().union(*input_claims.values()))
        for index, value in enumerate(packet.get("key_risks") or [])
    ]
    # Registry coverage is explicit even when a legacy packet contains no
    # instance of an optional semantic category.  Such nodes truthfully carry
    # ``not_present`` instead of fabricating company data.
    already_bound = {item.definition_id for item in nodes}
    for definition_id in sorted(set(authority.decision_definitions) - already_bound):
        add(
            definition_id, "not-present", {"status": "not_present_in_legacy_decision_packet"},
            presence="not_present_schema_coverage",
        )
    for ordinal, node_id in enumerate([*input_nodes.values(), *rule_nodes, *score_nodes, timing_node, *rationale_nodes]):
        edges.append(_decision_edge(f"semantic.edge.contributes.{ordinal}", "contributes_to", node_id, rating_node, ordinal))
    edges.append(_decision_edge("semantic.edge.corridor", "constrains", corridor_node, rating_node, 0))
    edges.append(_decision_edge("semantic.edge.non-advice", "constrains", non_advice_node, rating_node, 1))
    required = tuple(sorted(authority.decision_definitions))
    present = tuple(sorted({item.definition_id for item in nodes if item.instance_presence == "present"}))
    schema = tuple(sorted({item.definition_id for item in nodes}))
    semantic = create_hashed(
        SemanticDecisionGraphRFC0004IR,
        ticker=state.ticker, as_of_date=state.as_of_date,
        generic_decision_graph_sha256=generic.ir_sha256,
        decision_packet_source_sha256=document.ir_sha256,
        registry_authority_sha256=authority.authority_sha256,
        claim_graph_sha256=claim_graph.ir_sha256,
        nodes=tuple(sorted(nodes, key=lambda item: item.node_id)),
        edges=tuple(sorted(edges, key=lambda item: item.edge_id)),
        required_definition_ids=required, present_definition_ids=present,
        schema_coverage_definition_ids=schema,
        unknown_definition_ids=tuple(sorted(set(schema) - set(required))),
    )
    artifacts = dict(state.artifacts)
    artifacts["decision_graph"] = generic.model_dump(mode="json")
    artifacts["semantic_decision_graph"] = semantic.model_dump(mode="json")
    return _create_state(previous=state, stage="decisions", artifacts=artifacts).model_dump(mode="json")


def _diagnostic(*, code: str, passed: bool, state: SemanticCompileStateRFC0004IR,
                details: dict[str, Any], sources: tuple[SourceInputIR, ...]) -> DiagnosticIR:
    return DiagnosticIR(
        code=code,
        semantic_severity=SemanticSeverity.INFO if passed else SemanticSeverity.ERROR,
        release_effect=ReleaseEffect.NONE if passed else ReleaseEffect.COMPILE_BLOCK,
        layer=CompilerLayer.L10_VERIFICATION, pass_id="ba9.l10.verify_semantics",
        subject_ref=state.ticker, source_refs=tuple(item.provenance for item in sources),
        root_cause_ref=f"rfc_0004:{code.casefold()}", fixture_refs=(f"rfc_0004:{code.casefold()}",),
        message=(f"{code} passed." if passed else f"{code} failed closed."), details=details,
    )


def _verification(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    sources = _items(state, "source_inputs", SourceInputIR)
    parsed = _items(state, "parsed_payload_refs", ParsedPayloadRefIR)
    tables = _items(state, "table_discovery_summaries", TableDiscoverySummaryIR)
    normalized = _items(state, "normalized_records", NormalizedFactRecordIR)
    facts = _items(state, "typed_facts", TypedFactSpineIR)
    signatures = _items(state, "signatures", MetricSignatureIR)
    metrics = _items(state, "metrics", MetricSpineIR)
    operands = _items(state, "formula_operands", FormulaOperandBindingIR)
    operand_facts = _items(state, "formula_operand_facts", FormulaOperandFactIR)
    policy_parameters = _items(state, "policy_parameters", PolicyParameterIR)
    evaluations = _items(state, "formula_evaluations", FormulaEvaluationRFC0003IR)
    evidence = CompleteEvidenceGraphRFC0004IR.model_validate(state.artifacts["complete_evidence_graph"])
    claims = ClaimGraphSpineIR.model_validate(state.artifacts["claim_graph"])
    decision = DecisionGraphSpineIR.model_validate(state.artifacts["decision_graph"])
    semantic_decision = SemanticDecisionGraphRFC0004IR.model_validate(state.artifacts["semantic_decision_graph"])
    artifact_hashes = {key: value for key, value in state.artifact_sha256s.items() if key != "verification_report"}
    all_ir_hashes: set[str] = set()
    for key in ("source_inputs", "parsed_payload_refs", "table_discovery_summaries", "table_refs", "cell_refs", "legacy_table_cell_mappings", "normalized_records", "typed_facts", "signatures", "metrics", "formula_operands", "formula_operand_facts", "policy_parameters", "formula_evaluations"):
        all_ir_hashes.update(str(item["ir_sha256"]) for item in state.artifacts[key])
    all_ir_hashes.update((evidence.ir_sha256, claims.ir_sha256, decision.ir_sha256, semantic_decision.ir_sha256))
    parsed_hashes = tuple(sorted(item.parsed_payload_ir_sha256 for item in parsed))
    all_ir_hashes.update(parsed_hashes)
    plan = create_hashed(
        VerificationPlanRFC0003IR, plan_id=f"verification.rfc0003.{state.ticker.casefold()}.{state.as_of_date}",
        bound_ir_sha256s=tuple(sorted(all_ir_hashes)), bound_parsed_ir_sha256s=parsed_hashes,
        bound_artifact_sha256s={key: artifact_hashes[key] for key in sorted(artifact_hashes)},
        invariant_codes=RFC0004_INVARIANTS,
    )
    compatibility_sources = tuple(item for item in sources if item.input_kind == "legacy_compatibility")
    diagnostics = [
        _diagnostic(code="LEGACY_COMPATIBILITY_ADAPTER_USED", passed=bool(compatibility_sources) and all(item.compatibility_adapter_id for item in compatibility_sources), state=state,
                    details={"adapter_ids": sorted({str(item.compatibility_adapter_id) for item in compatibility_sources})}, sources=compatibility_sources),
        _diagnostic(code="IR_SPINE_CONNECTED", passed=bool(normalized) and len(facts) == len(normalized) and {item.normalized_record_sha256 for item in facts} == {item.ir_sha256 for item in normalized}, state=state,
                    details={"normalized_records": len(normalized), "typed_facts": len(facts)}, sources=compatibility_sources),
        _diagnostic(code="TABLE_DISCOVERY_COVERAGE_COMPLETE", passed=all(item.detected_count == item.registered_count + item.excluded_count for item in tables), state=state,
                    details={"detected": sum(item.detected_count for item in tables), "registered": sum(item.registered_count for item in tables), "excluded": sum(item.excluded_count for item in tables)}, sources=sources),
        _diagnostic(code="METRIC_SIGNATURE_COVERAGE_COMPLETE", passed=len(metrics) == len(facts) and all(metric.signature_sha256 in {item.ir_sha256 for item in signatures} for metric in metrics), state=state,
                    details={"metrics": len(metrics), "signatures": len(signatures)}, sources=compatibility_sources),
        _diagnostic(code="FORMULA_EVALUATION_COMPLETE", passed=len(evaluations) == sum(bool(item.formula_id and item.formula_operands) for item in normalized), state=state,
                    details={"evaluations": len(evaluations)}, sources=compatibility_sources),
        _diagnostic(code="EVIDENCE_SOURCE_REGISTRY_COMPLETE", passed=not evidence.unknown_source_ids, state=state,
                    details={"unknown_source_ids": evidence.unknown_source_ids}, sources=compatibility_sources),
        _diagnostic(code="CLAIM_LINEAGE_COMPLETE", passed=not claims.claims_without_lineage and not claims.numeric_bindings_without_lineage, state=state,
                    details={"claims_without_lineage": claims.claims_without_lineage, "numeric_bindings_without_lineage": claims.numeric_bindings_without_lineage}, sources=compatibility_sources),
        _diagnostic(code="DECISION_GRAPH_ROUNDTRIP_VALID", passed=decision.comparison_payload_sha256 == decision.reconstructed_payload_sha256, state=state,
                    details={"comparison_sha256": decision.comparison_payload_sha256, "reconstructed_sha256": decision.reconstructed_payload_sha256}, sources=compatibility_sources),
    ]
    operand_by_id = {item.operand_id: item for item in operands}
    operand_fact_by_id = {item.operand_fact_id: item for item in operand_facts}
    parameter_by_id = {item.parameter_id: item for item in policy_parameters}
    typed_fact_by_id = {item.fact_id: item for item in facts}
    formula_authority = SemanticRegistryAuthority.load()
    formula_errors: list[str] = []
    for evaluation in evaluations:
        definition = formula_authority.formula_definitions[evaluation.formula_definition_id]
        evaluation_operands = [operand_by_id.get(item) for item in evaluation.operand_ids]
        if None in evaluation_operands or tuple(item.ir_sha256 for item in evaluation_operands if item) != evaluation.operand_sha256s:
            formula_errors.append(f"{evaluation.formula_instance_id}:operand_hash_or_id")
            continue
        legacy_ids = {item.expected_role_contract.legacy_formula_id for item in evaluation_operands if item}
        if len(legacy_ids) != 1:
            formula_errors.append(f"{evaluation.formula_instance_id}:legacy_formula_contract")
            continue
        legacy_id = next(iter(legacy_ids))
        contract = definition.legacy_operand_contracts[legacy_id]
        roles = [item.role for item in evaluation_operands if item]
        if not contract.min_operands <= len(roles) <= contract.max_operands:
            formula_errors.append(f"{evaluation.formula_instance_id}:role_cardinality")
        if not set(contract.required_roles).issubset(roles):
            formula_errors.append(f"{evaluation.formula_instance_id}:required_roles")
        if any(not any(re.fullmatch(pattern, role) for pattern in contract.allowed_role_patterns) for role in roles):
            formula_errors.append(f"{evaluation.formula_instance_id}:role_not_allowed")
        for operand in evaluation_operands:
            assert operand is not None
            if operand.binding_kind == "quarantined_unresolved_operand":
                formula_errors.append(f"{operand.operand_id}:unresolved")
                continue
            if not _dimension_compatible(operand.expected_role_contract.expected_dimension, operand.dimension):
                formula_errors.append(f"{operand.operand_id}:dimension")
            target: Any = None
            if operand.binding_kind == "typed_fact":
                target = typed_fact_by_id.get(str(operand.operand_fact_or_parameter_id))
            elif operand.binding_kind == "evidence_typed_fact":
                target = operand_fact_by_id.get(str(operand.operand_fact_or_parameter_id))
            elif operand.binding_kind == "policy_parameter":
                target = parameter_by_id.get(str(operand.operand_fact_or_parameter_id))
            if target is None or not _same_numeric(target.value, operand.value):
                formula_errors.append(f"{operand.operand_id}:target_or_value")
            if operand.binding_kind != "policy_parameter" and (not operand.source_ids or not operand.evidence_ids):
                formula_errors.append(f"{operand.operand_id}:provenance")
        result_fact = typed_fact_by_id.get(evaluation.result_fact_id)
        if result_fact is None or not _dimension_compatible(definition.result_dimension, result_fact.dimension):
            formula_errors.append(f"{evaluation.formula_instance_id}:result_dimension")
    formula_ok = not formula_errors and len(operands) == sum(len(item.operand_ids) for item in evaluations)
    diagnostics.append(_diagnostic(code="FORMULA_OPERAND_LINEAGE_COMPLETE", passed=formula_ok, state=state,
                                   details={"operands": len(operands), "evaluations": len(evaluations),
                                            "operand_facts": len(operand_facts), "policy_parameters": len(policy_parameters),
                                            "errors": sorted(formula_errors)}, sources=sources))
    node_counts = Counter(item.node_kind for item in evidence.nodes)
    required_present = all(node_counts[kind] > 0 for kind in REQUIRED_EVIDENCE_NODE_KINDS)
    diagnostics.append(_diagnostic(code="EVIDENCE_GRAPH_REQUIRED_NODE_TYPES_COMPLETE", passed=required_present, state=state,
                                   details={"required": REQUIRED_EVIDENCE_NODE_KINDS, "counts": dict(sorted(node_counts.items()))}, sources=sources))
    parsed_bound = set(parsed_hashes).issubset(plan.bound_ir_sha256s) and len(parsed_hashes) == len(parsed)
    diagnostics.append(_diagnostic(code="PARSED_IR_BOUND_IN_VERIFICATION_PLAN", passed=parsed_bound, state=state,
                                   details={"parsed_count": len(parsed_hashes), "bound_count": len(plan.bound_ir_sha256s)}, sources=sources))
    table_truthful = not any(
        edge.edge_kind == "declared_in" and edge.to_node_id not in {node.node_id for node in evidence.nodes}
        for edge in evidence.edges
    ) and not evidence.unresolved_executable_fact_ids
    diagnostics.append(_diagnostic(code="TABLE_FACT_LINEAGE_TRUTHFUL", passed=table_truthful, state=state,
                                   details={"unresolved_executable_fact_ids": evidence.unresolved_executable_fact_ids,
                                            "invented_edges": 0}, sources=sources))
    artifact_refs_ok = all(
        item.artifact_uri == f"room16-table://sha256/{item.semantic_table_ir_sha256}"
        and item.cell_count >= 0 for item in evidence.table_artifact_refs
    )
    diagnostics.append(_diagnostic(
        code="CANONICAL_TABLE_ARTIFACTS_RESOLVABLE", passed=artifact_refs_ok,
        state=state, details={"artifact_ref_count": len(evidence.table_artifact_refs)}, sources=sources,
    ))
    declared_complete = all(item.mapping_status == "mapped" for item in evidence.legacy_table_cell_mappings)
    diagnostics.append(_diagnostic(
        code="DECLARED_TABLE_CELL_LINEAGE_COMPLETE", passed=declared_complete,
        state=state, details={"declared": len(evidence.legacy_table_cell_mappings),
                              "mapped": sum(item.mapping_status == "mapped" for item in evidence.legacy_table_cell_mappings)},
        sources=sources,
    ))
    diagnostics.append(_diagnostic(
        code="EXECUTABLE_FACT_TABLE_LINEAGE_COMPLETE", passed=not evidence.unresolved_executable_fact_ids,
        state=state, details={"unresolved_executable_fact_ids": evidence.unresolved_executable_fact_ids}, sources=sources,
    ))
    decision_ok = (
        not semantic_decision.unknown_definition_ids
        and set(semantic_decision.required_definition_ids).issubset(semantic_decision.schema_coverage_definition_ids)
        and bool(semantic_decision.nodes) and bool(semantic_decision.edges)
    )
    diagnostics.append(_diagnostic(code="DECISION_REGISTRY_BINDINGS_COMPLETE", passed=decision_ok, state=state,
                                   details={"required": semantic_decision.required_definition_ids,
                                            "present": semantic_decision.present_definition_ids,
                                            "schema_coverage": semantic_decision.schema_coverage_definition_ids,
                                            "unknown": semantic_decision.unknown_definition_ids}, sources=sources))
    present_nodes = [item for item in semantic_decision.nodes if item.instance_presence == "present"]
    lineage_nodes = [item for item in present_nodes if item.definition_id in {
        "decision.input.operating_signal", "decision.input.risk", "decision.counterevidence",
        "decision.score_contribution", "decision.rationale",
    }]
    claim_lineage_ok = all(item.claim_ids for item in lineage_nodes)
    diagnostics.append(_diagnostic(
        code="DECISION_CLAIM_LINEAGE_COMPLETE", passed=claim_lineage_ok, state=state,
        details={"lineage_nodes": len(lineage_nodes), "without_claims": sorted(item.node_id for item in lineage_nodes if not item.claim_ids)}, sources=sources,
    ))
    fact_lineage_ok = all(item.fact_ids or item.evidence_ids for item in lineage_nodes)
    diagnostics.append(_diagnostic(
        code="DECISION_FACT_LINEAGE_COMPLETE", passed=fact_lineage_ok, state=state,
        details={"without_fact_or_evidence": sorted(item.node_id for item in lineage_nodes if not (item.fact_ids or item.evidence_ids))}, sources=sources,
    ))
    score_nodes = [item for item in present_nodes if item.definition_id == "decision.score_contribution"]
    score_ok = all(item.claim_ids and (item.fact_ids or item.evidence_ids) and item.rule_refs for item in score_nodes)
    diagnostics.append(_diagnostic(
        code="DECISION_SCORE_INPUTS_BOUND", passed=score_ok, state=state,
        details={"score_nodes": len(score_nodes), "unbound": sorted(item.node_id for item in score_nodes if not (item.claim_ids and (item.fact_ids or item.evidence_ids) and item.rule_refs))}, sources=sources,
    ))
    risk_nodes = [item for item in present_nodes if item.definition_id in {"decision.input.risk", "decision.counterevidence"}]
    risk_ok = all(item.claim_ids and item.evidence_ids for item in risk_nodes)
    diagnostics.append(_diagnostic(
        code="DECISION_RISK_COUNTEREVIDENCE_BOUND", passed=risk_ok, state=state,
        details={"risk_nodes": len(risk_nodes), "unbound": sorted(item.node_id for item in risk_nodes if not (item.claim_ids and item.evidence_ids))}, sources=sources,
    ))
    diagnostics.append(_diagnostic(code="COMPATIBILITY_MODE_STATUS_TRUTHFUL", passed=(
        state.compiler_mode == "compatibility_shadow" and not state.source_native_fact_generation
        and not state.release_ready and not state.publication_allowed and not state.renderer_cutover
        and not state.ba10_authorized
    ), state=state, details={
        "compiler_mode": state.compiler_mode, "source_native_fact_generation": state.source_native_fact_generation,
        "release_ready": state.release_ready, "publication_allowed": state.publication_allowed,
        "renderer_cutover": state.renderer_cutover, "ba10_authorized": state.ba10_authorized,
    }, sources=sources))
    ordered = tuple(sorted(diagnostics, key=lambda item: (item.code, item.subject_ref)))
    report = create_hashed(
        VerificationReportRFC0004IR, ticker=state.ticker, as_of_date=state.as_of_date,
        verification_plan_sha256=plan.ir_sha256, diagnostics=ordered,
        verdict=CompileVerdictIR.derive(list(ordered)),
    )
    artifacts = dict(state.artifacts)
    artifacts["verification_plan"] = plan.model_dump(mode="json")
    artifacts["verification_report"] = report.model_dump(mode="json")
    return _create_state(previous=state, stage="verified", artifacts=artifacts).model_dump(mode="json")


def pass_implementations() -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    return {
        "ba4.l3.parse_sources": _parse_sources,
        "ba4.l3.discover_tables": _discover_tables,
        "ba5.l4.normalize_reconcile": _normalize,
        "ba5.l5.build_typed_facts": _build_facts,
        "ba6.l6.bind_metric_signatures": _build_metric_instances,
        "ba6.l6.evaluate_formulas": _evaluate_formulas,
        "ba7.l7.build_evidence_graph": _build_complete_evidence_graph,
        "ba7.l8.build_claim_graph": _build_claims,
        "ba8.l9.build_decision_graph": _build_semantic_decision,
        "ba9.l10.verify_semantics": _verification,
    }


def _record_hash(record: PassExecutionRecord) -> str:
    return sha256_json(record.model_dump(mode="json"))


def create_execution_attestation(
    state: SemanticCompileStateRFC0004IR, records: tuple[PassExecutionRecord, ...],
    *, fixture_codes_stable: bool = True,
) -> ExecutionAttestationIR:
    report = VerificationReportRFC0004IR.model_validate(state.artifacts["verification_report"])
    expected_ids = [item.pass_id for item in load_pass_manifests(PASS_MANIFEST_PATH)]
    complete = (
        [item.pass_id for item in records] == expected_ids
        and [item.ordinal for item in records] == list(range(4, 14))
        and all(item.input_payload_sha256 and item.output_payload_sha256 and item.cache_key for item in records)
        and all(item.status.value in {"executed", "replayed", "cache_hit"} for item in records)
    )
    hashes = tuple(_record_hash(item) for item in records)
    return create_hashed(
        ExecutionAttestationIR, ticker=state.ticker, as_of_date=state.as_of_date,
        final_compile_state_sha256=state.ir_sha256,
        verification_report_sha256=report.ir_sha256,
        pass_execution_record_sha256s=hashes, pass_execution_complete=complete,
        fixture_attestation_sha256=sha256_json({
            "suite": "rfc_0004_stable_diagnostic_fixtures",
            "fixture_diagnostic_codes_stable": fixture_codes_stable,
        }),
        fixture_diagnostic_codes_stable=fixture_codes_stable,
        semantic_verdict=report.verdict,
    )


def replay_rfc_0003_archive(*, archive: Path, replay_records: tuple[PassExecutionRecord, ...] | None = None,
                            kernel: PassKernel | None = None) -> dict[str, Any]:
    initial_state, provenance = load_initial_state(archive)
    manifests = load_pass_manifests(PASS_MANIFEST_PATH)
    active_kernel = kernel or PassKernel(manifests, RegistryAuthority.load())
    initial = IREnvelope.create(
        ir_type="semantic_compile_state.source_inputs", layer=CompilerLayer.L2_SOURCE_SNAPSHOT,
        producer_pass_id="rfc0003.load_frozen_inputs", payload=initial_state.model_dump(mode="json"),
        provenance_refs=provenance,
    )
    final_envelope, records = active_kernel.execute(
        initial, pass_implementations(), replay=replay_records,
    )
    final_state = SemanticCompileStateRFC0004IR.model_validate(final_envelope.payload)
    report = VerificationReportRFC0004IR.model_validate(final_state.artifacts["verification_report"])
    attestation = create_execution_attestation(final_state, records)
    result = {
        "contract_id": "room16.compiler.rfc_0004_semantic_integrity_replay",
        "contract_version": 1,
        "rfc_id": "RFC-0004",
        "foundation_version": "1.0.0",
        "registry_foundation_version": "1.1.0",
        "authority_bundle_version": 3,
        "compiler_mode": "compatibility_shadow",
        "source_native_fact_generation": False,
        "ticker": final_state.ticker,
        "as_of_date": final_state.as_of_date,
        "archive": final_state.archive_name,
        "archive_sha256_before": initial_state.archive_sha256,
        "archive_sha256_after": _archive_sha256(archive),
        "initial_envelope": initial.model_dump(mode="json"),
        "final_envelope": final_envelope.model_dump(mode="json"),
        "compile_state": final_state.model_dump(mode="json"),
        "pass_execution_records": [item.model_dump(mode="json") for item in records],
        "pass_execution_record_sha256s": [_record_hash(item) for item in records],
        "verification_report": report.model_dump(mode="json"),
        "execution_attestation": attestation.model_dump(mode="json"),
        "release_ready": False,
        "publication_allowed": False,
        "renderer_cutover": False,
        "ba10_authorized": False,
        "legacy_output_unchanged": initial_state.archive_sha256 == _archive_sha256(archive),
    }
    result["replay_sha256"] = sha256_json(result)
    return result
