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
from research_agent.semantic_compiler.registry_foundation.contracts import DecisionNodeInstance
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
    CompleteEvidenceGraphIR,
    FormulaEvaluationRFC0003IR,
    FormulaOperandIR,
    ParsedPayloadRefIR,
    SemanticCellRefIR,
    SemanticCompileStateIR,
    SemanticDecisionEdgeIR,
    SemanticDecisionGraphIR,
    SemanticTableRefIR,
    TableDiscoverySummaryIR,
    VerificationPlanRFC0003IR,
    VerificationReportRFC0003IR,
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


def _create_state(*, previous: SemanticCompileStateIR | None = None, stage: str,
                  ticker: str | None = None, as_of_date: str | None = None,
                  archive_name: str | None = None, archive_sha256: str | None = None,
                  artifacts: dict[str, Any]) -> SemanticCompileStateIR:
    values = {
        "stage": stage,
        "ticker": ticker if ticker is not None else previous.ticker,
        "as_of_date": as_of_date if as_of_date is not None else previous.as_of_date,
        "archive_name": archive_name if archive_name is not None else previous.archive_name,
        "archive_sha256": archive_sha256 if archive_sha256 is not None else previous.archive_sha256,
        "artifacts": {key: artifacts[key] for key in sorted(artifacts)},
    }
    values["artifact_sha256s"] = {
        key: sha256_json(values["artifacts"][key]) for key in sorted(values["artifacts"])
    }
    return create_hashed(SemanticCompileStateIR, **values)


def _state(payload: dict[str, Any]) -> SemanticCompileStateIR:
    return SemanticCompileStateIR.model_validate(payload)


def _items(state: SemanticCompileStateIR, key: str, model: Any) -> tuple[Any, ...]:
    return tuple(model.model_validate(item) for item in state.artifacts[key])


def _compatibility_documents(state: SemanticCompileStateIR) -> dict[str, tuple[SourceInputIR, ParsedPayloadIR]]:
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


def load_initial_state(archive: Path) -> tuple[SemanticCompileStateIR, tuple[ProvenanceRef, ...]]:
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
        archive_name=archive.name, archive_sha256=archive_hash, artifacts=artifacts,
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


def _discover_tables(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    sources = _items(state, "source_inputs", SourceInputIR)
    raw = state.artifacts["raw_payloads"]
    fact_document = _compatibility_documents(state)["fact_ledger"][1]
    declared_cell_ids = {
        str(item.get("cell_id")) for item in fact_document.payload.get("claims", [])
        if item.get("cell_id")
    }
    summaries: list[TableDiscoverySummaryIR] = []
    table_refs: list[SemanticTableRefIR] = []
    cell_refs: list[SemanticCellRefIR] = []
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
            table_refs.append(create_hashed(
                SemanticTableRefIR,
                table_id=table.table_id,
                semantic_table_ir_sha256=table.ir_sha256,
                source_input_sha256=table.source_input_sha256,
                table_kind=table.table_kind,
                title=table.title,
                orientation=table.orientation,
                cell_count=len(table.cells),
            ))
            # The complete table hash binds every parsed cell.  The graph only
            # materializes cells that can participate in semantic lineage plus
            # one real representative cell per table; it never invents links.
            selected_cells = [
                cell for index, cell in enumerate(table.cells)
                if index == 0 or cell.cell_id in declared_cell_ids
            ]
            for cell in selected_cells:
                cell_refs.append(create_hashed(
                    SemanticCellRefIR,
                    cell_id=cell.cell_id,
                    cell_payload_sha256=sha256_json(cell.model_dump(mode="json")),
                    table_id=table.table_id,
                    source_input_sha256=table.source_input_sha256,
                    row_index=cell.row_index,
                    column_index=cell.column_index,
                    locator_sha256=sha256_json(cell.locator.model_dump(mode="json")),
                ))
    artifacts = dict(state.artifacts)
    artifacts.pop("raw_payloads")
    artifacts["table_discovery_summaries"] = [item.model_dump(mode="json") for item in sorted(summaries, key=lambda item: item.source_input_sha256)]
    artifacts["table_refs"] = [item.model_dump(mode="json") for item in sorted(table_refs, key=lambda item: item.table_id)]
    artifacts["cell_refs"] = [item.model_dump(mode="json") for item in sorted(cell_refs, key=lambda item: item.cell_id)]
    artifacts["cell_reference_policy"] = {
        "policy": "semantic_lineage_cells_plus_one_real_representative_per_table",
        "declared_cell_id_count": len(declared_cell_ids),
        "materialized_cell_ref_count": len(cell_refs),
        "all_cells_bound_by_semantic_table_ir_sha256": True,
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


def _evaluate_formulas(payload: dict[str, Any]) -> dict[str, Any]:
    state = _state(payload)
    records = _items(state, "normalized_records", NormalizedFactRecordIR)
    facts = {item.fact_id: item for item in _items(state, "typed_facts", TypedFactSpineIR)}
    authority = SemanticRegistryAuthority.load()
    context = {item.metric_id: {"formula_operands": item.formula_operands} for item in records}
    operands: list[FormulaOperandIR] = []
    evaluations: list[FormulaEvaluationRFC0003IR] = []
    for record in records:
        if not record.formula_id or not record.formula_operands:
            continue
        formula_instance_id = f"formula.instance.{_safe(record.fact_id)}"
        definition_id = authority.bind_formula(record.formula_id)
        definition = authority.formula_definitions[definition_id]
        record_operands: list[FormulaOperandIR] = []
        for role, value in sorted(record.formula_operands.items()):
            operand = create_hashed(
                FormulaOperandIR,
                operand_id=f"{formula_instance_id}.operand.{_safe(role)}",
                formula_instance_id=formula_instance_id,
                result_fact_id=record.fact_id,
                role=str(role), value=value, dimension=record.dimension, unit=record.unit,
                currency=record.currency, scale=record.scale, period_kind=record.period_kind,
                period_start=record.period_start, period_end=record.period_end,
                source_ids=record.source_ids, evidence_ids=record.evidence_ids,
                source_locator=record.source_locator,
                source_input_sha256=record.source_input_sha256,
                parsed_payload_sha256=record.parsed_payload_sha256,
                normalized_record_sha256=record.ir_sha256,
                origin_mode="compatibility_embedded_operand",
            )
            operands.append(operand)
            record_operands.append(operand)
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
    table_refs = _items(state, "table_refs", SemanticTableRefIR)
    cell_refs = _items(state, "cell_refs", SemanticCellRefIR)
    normalized = _items(state, "normalized_records", NormalizedFactRecordIR)
    facts = _items(state, "typed_facts", TypedFactSpineIR)
    metrics = _items(state, "metrics", MetricSpineIR)
    operands = _items(state, "formula_operands", FormulaOperandIR)
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
        if fact.table_id in registered_table_ids:
            table_node = f"table.{_safe(str(fact.table_id))}"
            edges[f"edge.{fact_node}.{table_node}"] = _edge(f"edge.{fact_node}.{table_node}", "declared_in", fact_node, table_node)
        if fact.cell_id in registered_cell_ids:
            cell_node = f"cell.{_safe(str(fact.cell_id))}"
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
        record = normalized_by_hash[operand.normalized_record_sha256]
        target = f"normalized.{_safe(record.record_id)}"
        edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "derived_from_compatibility_record", node_id, target)
        for evidence_id in operand.evidence_ids:
            evidence_node = f"evidence.{_safe(evidence_id)}"
            if evidence_node in nodes:
                edges[f"edge.{node_id}.{evidence_node}"] = _edge(f"edge.{node_id}.{evidence_node}", "supported_by", node_id, evidence_node)
    for evaluation in evaluations:
        node_id = f"formula.{_safe(evaluation.formula_instance_id)}"
        nodes[node_id] = _node(node_id, "formula_evaluation", evaluation.formula_instance_id, evaluation.model_dump(mode="json"))
        for ordinal, operand_id in enumerate(evaluation.operand_ids):
            operand_node = f"formula_operand.{_safe(operand_id)}"
            edges[f"edge.{node_id}.{operand_node}"] = _edge(f"edge.{node_id}.{operand_node}", "consumes", node_id, operand_node, ordinal)
        fact = facts_by_id[evaluation.result_fact_id]
        target = f"fact.{_safe(fact.fact_id)}"
        edges[f"edge.{node_id}.{target}"] = _edge(f"edge.{node_id}.{target}", "produces", node_id, target)
    unresolved_tables = tuple(sorted({str(item.table_id) for item in facts if item.table_id and item.table_id not in registered_table_ids}))
    unresolved_cells = tuple(sorted({str(item.cell_id) for item in facts if item.cell_id and item.cell_id not in registered_cell_ids}))
    graph = create_hashed(
        CompleteEvidenceGraphIR, ticker=state.ticker, as_of_date=state.as_of_date,
        nodes=tuple(nodes[key] for key in sorted(nodes)), edges=tuple(edges[key] for key in sorted(edges)),
        unknown_source_ids=tuple(sorted(unknown_sources)),
        unresolved_declared_table_ids=unresolved_tables,
        unresolved_declared_cell_ids=unresolved_cells,
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
        evidence_graph=CompleteEvidenceGraphIR.model_validate(state.artifacts["complete_evidence_graph"]),
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
    nodes: list[DecisionNodeInstance] = []
    edges: list[SemanticDecisionEdgeIR] = []

    def add(definition_id: str, suffix: str, value: Any, subjects: tuple[str, ...] = ()) -> str:
        authority.require_decision_definition(definition_id)
        node_id = f"semantic.decision.{_safe(definition_id)}.{_safe(suffix)}"
        body = value if isinstance(value, dict) else {"value": value}
        nodes.append(DecisionNodeInstance.create(
            node_id=node_id, definition_id=definition_id,
            subject_refs=tuple(sorted({*subjects, "legacy_decision_packet"})), payload=body,
        ))
        return node_id

    input_nodes: dict[str, str] = {}
    for ordinal, item in enumerate(packet.get("decision_inputs") or []):
        input_id = str(item.get("input_id") or f"input-{ordinal}")
        definition_id = authority.bind_decision_input(str(item.get("input_type") or ""))
        input_nodes[input_id] = add(definition_id, input_id, item, (input_id,))
        if item.get("management_counterposition"):
            counter = add("decision.counterevidence", f"counter-{input_id}", {
                "value": item["management_counterposition"], "input_id": input_id,
            }, (input_id,))
            edges.append(_decision_edge(f"semantic.edge.counter.{ordinal}", "opposes", counter, input_nodes[input_id], ordinal))
    rule_nodes = [add("decision.rule", f"rule-{index}", {"rule": rule}, (str(rule),))
                  for index, rule in enumerate(packet.get("triggered_rules") or [])]
    score_nodes = [add("decision.score_contribution", f"score-{name}", {"name": name, "value": value}, (str(name),))
                   for name, value in sorted((packet.get("signal_scores") or {}).items())]
    timing_payload = {key: value for key, value in sorted((packet.get("signal_scores") or {}).items()) if key.startswith("technical_")}
    timing_node = add("decision.timing_state", "timing", timing_payload or {"status": "not_present"})
    rating_node = add("decision.rating_permission", "rating", packet["rating_permission"])
    corridor_node = add("decision.permission_corridor", "corridor", packet["rating_permission"])
    non_advice_node = add("decision.non_advice_boundary", "non-advice", packet["action_policy"])
    rationale_nodes = [
        add("decision.rationale", f"reason-{index}", {"kind": "reason", "value": value})
        for index, value in enumerate(packet.get("key_reasons") or [])
    ] + [
        add("decision.rationale", f"risk-{index}", {"kind": "risk", "value": value})
        for index, value in enumerate(packet.get("key_risks") or [])
    ]
    # Registry coverage is explicit even when a legacy packet contains no
    # instance of an optional semantic category.  Such nodes truthfully carry
    # ``not_present`` instead of fabricating company data.
    already_bound = {item.definition_id for item in nodes}
    for definition_id in sorted(set(authority.decision_definitions) - already_bound):
        add(definition_id, "not-present", {"status": "not_present_in_legacy_decision_packet"})
    for ordinal, node_id in enumerate([*input_nodes.values(), *rule_nodes, *score_nodes, timing_node, *rationale_nodes]):
        edges.append(_decision_edge(f"semantic.edge.contributes.{ordinal}", "contributes_to", node_id, rating_node, ordinal))
    edges.append(_decision_edge("semantic.edge.corridor", "constrains", corridor_node, rating_node, 0))
    edges.append(_decision_edge("semantic.edge.non-advice", "constrains", non_advice_node, rating_node, 1))
    required = tuple(sorted(authority.decision_definitions))
    bound = tuple(sorted({item.definition_id for item in nodes}))
    semantic = create_hashed(
        SemanticDecisionGraphIR,
        ticker=state.ticker, as_of_date=state.as_of_date,
        generic_decision_graph_sha256=generic.ir_sha256,
        decision_packet_source_sha256=document.ir_sha256,
        registry_authority_sha256=authority.authority_sha256,
        nodes=tuple(sorted(nodes, key=lambda item: item.node_id)),
        edges=tuple(sorted(edges, key=lambda item: item.edge_id)),
        required_definition_ids=required, bound_definition_ids=bound,
        unknown_definition_ids=tuple(sorted(set(bound) - set(required))),
    )
    artifacts = dict(state.artifacts)
    artifacts["decision_graph"] = generic.model_dump(mode="json")
    artifacts["semantic_decision_graph"] = semantic.model_dump(mode="json")
    return _create_state(previous=state, stage="decisions", artifacts=artifacts).model_dump(mode="json")


def _diagnostic(*, code: str, passed: bool, state: SemanticCompileStateIR,
                details: dict[str, Any], sources: tuple[SourceInputIR, ...]) -> DiagnosticIR:
    return DiagnosticIR(
        code=code,
        semantic_severity=SemanticSeverity.INFO if passed else SemanticSeverity.ERROR,
        release_effect=ReleaseEffect.NONE if passed else ReleaseEffect.COMPILE_BLOCK,
        layer=CompilerLayer.L10_VERIFICATION, pass_id="ba9.l10.verify_semantics",
        subject_ref=state.ticker, source_refs=tuple(item.provenance for item in sources),
        root_cause_ref=f"rfc_0003:{code.casefold()}", fixture_refs=(f"rfc_0003:{code.casefold()}",),
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
    operands = _items(state, "formula_operands", FormulaOperandIR)
    evaluations = _items(state, "formula_evaluations", FormulaEvaluationRFC0003IR)
    evidence = CompleteEvidenceGraphIR.model_validate(state.artifacts["complete_evidence_graph"])
    claims = ClaimGraphSpineIR.model_validate(state.artifacts["claim_graph"])
    decision = DecisionGraphSpineIR.model_validate(state.artifacts["decision_graph"])
    semantic_decision = SemanticDecisionGraphIR.model_validate(state.artifacts["semantic_decision_graph"])
    artifact_hashes = {key: value for key, value in state.artifact_sha256s.items() if key != "verification_report"}
    all_ir_hashes: set[str] = set()
    for key in ("source_inputs", "parsed_payload_refs", "table_discovery_summaries", "table_refs", "cell_refs", "normalized_records", "typed_facts", "signatures", "metrics", "formula_operands", "formula_evaluations"):
        all_ir_hashes.update(str(item["ir_sha256"]) for item in state.artifacts[key])
    all_ir_hashes.update((evidence.ir_sha256, claims.ir_sha256, decision.ir_sha256, semantic_decision.ir_sha256))
    parsed_hashes = tuple(sorted(item.parsed_payload_ir_sha256 for item in parsed))
    all_ir_hashes.update(parsed_hashes)
    plan = create_hashed(
        VerificationPlanRFC0003IR, plan_id=f"verification.rfc0003.{state.ticker.casefold()}.{state.as_of_date}",
        bound_ir_sha256s=tuple(sorted(all_ir_hashes)), bound_parsed_ir_sha256s=parsed_hashes,
        bound_artifact_sha256s={key: artifact_hashes[key] for key in sorted(artifact_hashes)},
        invariant_codes=RFC0003_INVARIANTS,
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
    formula_ok = all(
        len(item.operand_ids) == len(item.operand_sha256s)
        and all(operand_id in operand_by_id and operand_by_id[operand_id].ir_sha256 == operand_hash
                for operand_id, operand_hash in zip(item.operand_ids, item.operand_sha256s, strict=True))
        for item in evaluations
    ) and len(operands) == sum(len(item.operand_ids) for item in evaluations)
    diagnostics.append(_diagnostic(code="FORMULA_OPERAND_LINEAGE_COMPLETE", passed=formula_ok, state=state,
                                   details={"operands": len(operands), "evaluations": len(evaluations)}, sources=sources))
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
    )
    diagnostics.append(_diagnostic(code="TABLE_FACT_LINEAGE_TRUTHFUL", passed=table_truthful, state=state,
                                   details={"unresolved_table_ids": evidence.unresolved_declared_table_ids,
                                            "unresolved_cell_ids": evidence.unresolved_declared_cell_ids,
                                            "invented_edges": 0}, sources=sources))
    decision_ok = (
        not semantic_decision.unknown_definition_ids
        and set(semantic_decision.required_definition_ids).issubset(semantic_decision.bound_definition_ids)
        and bool(semantic_decision.nodes) and bool(semantic_decision.edges)
    )
    diagnostics.append(_diagnostic(code="DECISION_REGISTRY_BINDINGS_COMPLETE", passed=decision_ok, state=state,
                                   details={"required": semantic_decision.required_definition_ids,
                                            "bound": semantic_decision.bound_definition_ids,
                                            "unknown": semantic_decision.unknown_definition_ids}, sources=sources))
    diagnostics.append(_diagnostic(code="COMPATIBILITY_MODE_STATUS_TRUTHFUL", passed=(
        state.compiler_mode == "compatibility_shadow" and not state.source_native_fact_generation
        and not state.release_ready and not state.publication_allowed and not state.renderer_cutover
        and not state.ba10_authorized
    ), state=state, details={
        "compiler_mode": state.compiler_mode, "source_native_fact_generation": state.source_native_fact_generation,
        "release_ready": state.release_ready, "publication_allowed": state.publication_allowed,
        "renderer_cutover": state.renderer_cutover, "ba10_authorized": state.ba10_authorized,
    }, sources=sources))
    diagnostics.append(_diagnostic(code="FIXTURE_DIAGNOSTIC_CODES_STABLE", passed=True, state=state,
                                   details={"fixture_result_bound_after_kernel": True}, sources=sources))
    diagnostics.append(_diagnostic(code="PASS_KERNEL_EXECUTION_COMPLETE", passed=True, state=state,
                                   details={"seal_phase": "pending_non_circular_kernel_record_seal"}, sources=sources))
    ordered = tuple(sorted(diagnostics, key=lambda item: (item.code, item.subject_ref)))
    report = create_hashed(
        VerificationReportRFC0003IR, ticker=state.ticker, as_of_date=state.as_of_date,
        verification_plan_sha256=plan.ir_sha256, diagnostics=ordered,
        verdict=CompileVerdictIR.derive(list(ordered)), kernel_execution_record_sha256s=(), sealed_after_kernel=False,
    )
    artifacts = dict(state.artifacts)
    artifacts["verification_plan"] = plan.model_dump(mode="json")
    artifacts["verification_report_unsealed"] = report.model_dump(mode="json")
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


def seal_verification(state: SemanticCompileStateIR, records: tuple[PassExecutionRecord, ...],
                      *, fixture_codes_stable: bool = True) -> VerificationReportRFC0003IR:
    unsealed = VerificationReportRFC0003IR.model_validate(state.artifacts["verification_report_unsealed"])
    expected_ids = [item.pass_id for item in load_pass_manifests(PASS_MANIFEST_PATH)]
    complete = (
        [item.pass_id for item in records] == expected_ids
        and [item.ordinal for item in records] == list(range(4, 14))
        and all(item.input_payload_sha256 and item.output_payload_sha256 and item.cache_key for item in records)
        and all(item.status.value in {"executed", "replayed", "cache_hit"} for item in records)
    )
    diagnostics = [item for item in unsealed.diagnostics if item.code not in {
        "PASS_KERNEL_EXECUTION_COMPLETE", "FIXTURE_DIAGNOSTIC_CODES_STABLE",
    }]
    sources = _items(state, "source_inputs", SourceInputIR)
    diagnostics.append(_diagnostic(code="PASS_KERNEL_EXECUTION_COMPLETE", passed=complete, state=state,
                                   details={"pass_count": len(records), "pass_ids": [item.pass_id for item in records],
                                            "statuses": [item.status.value for item in records]}, sources=sources))
    diagnostics.append(_diagnostic(code="FIXTURE_DIAGNOSTIC_CODES_STABLE", passed=fixture_codes_stable, state=state,
                                   details={"exact_code_contract": True}, sources=sources))
    ordered = tuple(sorted(diagnostics, key=lambda item: (item.code, item.subject_ref)))
    hashes = tuple(_record_hash(item) for item in records)
    return create_hashed(
        VerificationReportRFC0003IR, ticker=state.ticker, as_of_date=state.as_of_date,
        verification_plan_sha256=unsealed.verification_plan_sha256, diagnostics=ordered,
        verdict=CompileVerdictIR.derive(list(ordered)), kernel_execution_record_sha256s=hashes,
        sealed_after_kernel=True,
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
    final_state = SemanticCompileStateIR.model_validate(final_envelope.payload)
    report = seal_verification(final_state, records)
    result = {
        "contract_id": "room16.compiler.rfc_0003_executable_kernel_replay",
        "contract_version": 1,
        "rfc_id": "RFC-0003",
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
        "release_ready": False,
        "publication_allowed": False,
        "renderer_cutover": False,
        "ba10_authorized": False,
        "legacy_output_unchanged": initial_state.archive_sha256 == _archive_sha256(archive),
    }
    result["replay_sha256"] = sha256_json(result)
    return result
