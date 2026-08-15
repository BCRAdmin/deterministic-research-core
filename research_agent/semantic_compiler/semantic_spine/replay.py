"""Frozen WM/COST/ABT RFC-0002 connected shadow replay."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import ProvenanceRef
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority
from research_agent.semantic_compiler.source_frontend.legacy_replay import replay_legacy_snapshot_zip

from .contracts import ParsedPayloadIR, SourceInputIR, create_hashed
from .pass_protocol import load_pass_contracts
from .signature_authority import MetricSignatureAuthority
from .semantics import (
    build_claim_graph,
    build_decision_graph,
    build_evidence_graph,
    build_metrics,
    build_typed_facts,
    evaluate_formulas,
    normalize_fact_ledger,
)
from .table_grammar import discover_tables, parse_payload
from .verification import verify_semantics


class RFC0002ReplayError(ValueError):
    pass


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _one(names: list[str], suffix: str) -> str:
    matches = [name for name in names if name.endswith(suffix)]
    if len(matches) != 1:
        raise RFC0002ReplayError(f"archive_artifact_count_invalid:{suffix}")
    return matches[0]


def _source_input(*, source_input_id: str, input_kind: str, archive_sha256: str, member_path: str, media_type: str, payload: bytes, adapter_id: str | None = None) -> SourceInputIR:
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


def replay_rfc_0002_archive(*, archive: Path, work_root: Path) -> dict[str, Any]:
    archive = archive.resolve()
    before = _archive_sha256(archive)
    authority = SemanticRegistryAuthority.load()
    signature_authority = MetricSignatureAuthority.load()
    _, pass_state = load_pass_contracts()
    ba3 = replay_legacy_snapshot_zip(archive=archive, work_root=work_root / "ba3")
    source_inputs: list[SourceInputIR] = []
    parsed_documents: list[ParsedPayloadIR] = []
    table_discoveries = []
    compatibility: dict[str, tuple[SourceInputIR, ParsedPayloadIR]] = {}
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        manifest_name = _one(names, "/authority_bundle/source_snapshot_manifest.json")
        manifest = json.loads(bundle.read(manifest_name))
        ticker = str(manifest["ticker"])
        as_of_date = str(manifest["as_of_date"])
        source_prefix = manifest_name.rsplit("source_snapshot_manifest.json", 1)[0] + "source_snapshots/"
        for artifact in sorted(manifest["artifacts"], key=lambda item: str(item["snapshot_id"])):
            member_path = f"{source_prefix}{artifact['path']}"
            payload = bundle.read(member_path)
            source = _source_input(
                source_input_id=str(artifact["snapshot_id"]),
                input_kind="source_snapshot",
                archive_sha256=before,
                member_path=str(artifact["path"]),
                media_type=str(artifact.get("media_type") or "application/octet-stream"),
                payload=payload,
            )
            if source.payload_sha256 != str(artifact["sha256"]) or source.payload_size != int(artifact["bytes"]):
                raise RFC0002ReplayError(f"source_snapshot_manifest_mismatch:{artifact['snapshot_id']}")
            parsed, candidates = parse_payload(source, payload)
            source_inputs.append(source)
            parsed_documents.append(parsed)
            table_discoveries.append(discover_tables(source, candidates))
        compatibility_members = {
            "fact_ledger": (_one(names, "/authority_bundle/fact_ledger.json"), "authority_bundle_v3.fact_ledger"),
            "evidence_ledger": (_one(names, "/authority_bundle/evidence_ledger.json"), "authority_bundle_v3.evidence_ledger"),
            "source_registry": (_one(names, f"/authority_bundle/{ticker}_{as_of_date}_source_registry.json"), "authority_bundle_v3.source_registry"),
            "analyst_claims": (_one(names, "/case/research/analyst_claims.json"), "authority_bundle_v3.analyst_claims"),
            "decision_packet": (_one(names, "/authority_bundle/decision_packet.json"), "authority_bundle_v3.decision_packet"),
        }
        for name, (member_path, adapter_id) in sorted(compatibility_members.items()):
            payload = bundle.read(member_path)
            source = _source_input(
                source_input_id=f"compat.{name}",
                input_kind="legacy_compatibility",
                archive_sha256=before,
                member_path=member_path,
                media_type="application/json",
                payload=payload,
                adapter_id=adapter_id,
            )
            parsed, _ = parse_payload(source, payload)
            source_inputs.append(source)
            parsed_documents.append(parsed)
            compatibility[name] = (source, parsed)
    fact_source, fact_document = compatibility["fact_ledger"]
    normalized = normalize_fact_ledger(fact_source, fact_document)
    facts = build_typed_facts(normalized, authority)
    signatures, metrics = build_metrics(facts, signature_authority)
    formula_evaluations = evaluate_formulas(normalized, authority)
    evidence_graph = build_evidence_graph(
        ticker=ticker,
        as_of_date=as_of_date,
        source_registry=compatibility["source_registry"][1],
        evidence_ledger=compatibility["evidence_ledger"][1],
        facts=facts,
    )
    claim_graph = build_claim_graph(
        ticker=ticker,
        as_of_date=as_of_date,
        claims_document=compatibility["analyst_claims"][1],
        evidence_document=compatibility["evidence_ledger"][1],
        source_document=compatibility["source_registry"][1],
        facts=facts,
        evidence_graph=evidence_graph,
        authority=authority,
    )
    decision_graph = build_decision_graph(
        compatibility["decision_packet"][1],
        compatibility["decision_packet"][0],
        authority,
    )
    formula_record_count = sum(bool(item.formula_id and item.formula_operands) for item in normalized)
    verification_plan, verification_report = verify_semantics(
        ticker=ticker,
        as_of_date=as_of_date,
        source_inputs=tuple(source_inputs),
        table_discoveries=tuple(table_discoveries),
        normalized=normalized,
        facts=facts,
        signatures=signatures,
        metrics=metrics,
        formula_evaluations=formula_evaluations,
        evidence_graph=evidence_graph,
        claim_graph=claim_graph,
        decision_graph=decision_graph,
        formula_record_count=formula_record_count,
    )
    after = _archive_sha256(archive)
    result = {
        "contract_id": "room16.compiler.rfc_0002_semantic_spine_replay",
        "contract_version": 1,
        "rfc_id": "RFC-0002",
        "foundation_version": "1.0.0",
        "registry_foundation_version": "1.1.0",
        "authority_bundle_version": 3,
        "pass_contracts_sha256": pass_state["pass_contracts_sha256"],
        "registry_authority_sha256": authority.authority_sha256,
        "metric_signature_authority_sha256": signature_authority.authority_sha256,
        "ticker": ticker,
        "as_of_date": as_of_date,
        "archive": archive.name,
        "archive_sha256_before": before,
        "archive_sha256_after": after,
        "ba3_source_snapshot_ir_sha256": ba3["source_snapshot_ir_sha256"],
        "source_inputs": [item.model_dump(mode="json") for item in source_inputs],
        "parsed_documents": [item.model_dump(mode="json") for item in parsed_documents],
        "table_discoveries": [item.model_dump(mode="json") for item in table_discoveries],
        "normalized_records": [item.model_dump(mode="json") for item in normalized],
        "typed_facts": [item.model_dump(mode="json") for item in facts],
        "signatures": [item.model_dump(mode="json") for item in signatures],
        "metrics": [item.model_dump(mode="json") for item in metrics],
        "formula_evaluations": [item.model_dump(mode="json") for item in formula_evaluations],
        "evidence_graph": evidence_graph.model_dump(mode="json"),
        "claim_graph": claim_graph.model_dump(mode="json"),
        "decision_graph": decision_graph.model_dump(mode="json"),
        "verification_plan": verification_plan.model_dump(mode="json"),
        "verification_report": verification_report.model_dump(mode="json"),
        "ba10_authorized": False,
        "renderer_cutover": False,
        "legacy_output_unchanged": before == after,
    }
    result["replay_sha256"] = sha256_json(result)
    return result
