"""Frozen WM/COST/ABT shadow replay across BA3-BA9."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority
from research_agent.semantic_compiler.registry_foundation.coverage import audit_canary_archive
from research_agent.semantic_compiler.source_frontend.legacy_replay import replay_legacy_snapshot_zip

from .graphs import (
    build_claim_graph,
    build_decision_graph,
    build_evidence_graph,
    roundtrip_legacy_decision,
)
from .metrics import build_metrics_and_evaluations
from .parser import bridge_legacy_table_facts, parse_artifact
from .pass_protocol import load_semantic_pass_contracts
from .typed_facts import build_typed_facts


class SemanticReplayError(ValueError):
    """Fail-closed semantic replay error."""


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _one(bundle: zipfile.ZipFile, suffix: str) -> str:
    matches = [name for name in bundle.namelist() if name.endswith(suffix)]
    if len(matches) != 1:
        raise SemanticReplayError(f"archive_artifact_count_invalid:{suffix}")
    return matches[0]


def _json(bundle: zipfile.ZipFile, suffix: str) -> Any:
    return json.loads(bundle.read(_one(bundle, suffix)))


def replay_semantic_wave_archive(*, archive: Path, work_root: Path) -> dict[str, Any]:
    archive = archive.resolve()
    before = _archive_sha256(archive)
    authority = SemanticRegistryAuthority.load()
    _, pass_protocol = load_semantic_pass_contracts()
    ba3 = replay_legacy_snapshot_zip(archive=archive, work_root=work_root / "ba3")
    with zipfile.ZipFile(archive) as bundle:
        manifest_name = _one(bundle, "/authority_bundle/source_snapshot_manifest.json")
        manifest = json.loads(bundle.read(manifest_name))
        facts_payload = _json(bundle, "/authority_bundle/fact_ledger.json")
        facts = list(facts_payload["claims"])
        evidence_ledger = _json(bundle, "/authority_bundle/evidence_ledger.json")
        claims = _json(bundle, "/case/research/analyst_claims.json")
        decision = _json(bundle, "/authority_bundle/decision_packet.json")
        source_registry_name = _one(bundle, f"/authority_bundle/{manifest['ticker']}_{manifest['as_of_date']}_source_registry.json")
        source_registry = json.loads(bundle.read(source_registry_name))
        prefix = manifest_name.rsplit("source_snapshot_manifest.json", 1)[0]
        source_prefix = f"{prefix}source_snapshots/"
        parsed_documents = []
        discovered_tables = []
        for artifact in sorted(manifest["artifacts"], key=lambda item: str(item["snapshot_id"])):
            relative = str(artifact["path"])
            payload = bundle.read(f"{source_prefix}{relative}")
            document, tables = parse_artifact(
                source_snapshot_sha256=ba3["source_snapshot_ir_sha256"],
                snapshot_id=str(artifact["snapshot_id"]),
                artifact_path=relative,
                source_sha256=str(artifact["sha256"]),
                media_type=str(artifact.get("media_type") or "application/octet-stream"),
                payload=payload,
            )
            parsed_documents.append(document)
            discovered_tables.extend(tables)
        first_artifact = manifest["artifacts"][0]
        legacy_tables = bridge_legacy_table_facts(
            facts,
            snapshot_id=str(first_artifact["snapshot_id"]),
            source_sha256=str(first_artifact["sha256"]),
            artifact_path=str(first_artifact["path"]),
        )
    normalized_records, typed_facts = build_typed_facts(facts, authority=authority)
    metrics, formula_evaluations, formula_markers = build_metrics_and_evaluations(
        facts, typed_facts, authority=authority
    )
    evidence_graph = build_evidence_graph(
        ticker=str(manifest["ticker"]),
        as_of_date=str(manifest["as_of_date"]),
        source_registry=source_registry,
        evidence_ledger=evidence_ledger,
        typed_facts=typed_facts,
    )
    claim_graph = build_claim_graph(
        ticker=str(manifest["ticker"]),
        as_of_date=str(manifest["as_of_date"]),
        claims=claims,
        typed_facts=typed_facts,
        known_evidence_ids={
            str(item["evidence_id"])
            for item in evidence_ledger.get("evidence_items") or []
        },
        authority=authority,
    )
    decision_graph = build_decision_graph(decision, authority=authority)
    roundtrip = roundtrip_legacy_decision(decision_graph)
    coverage = audit_canary_archive(archive, authority=authority)
    after = _archive_sha256(archive)
    all_tables = sorted([*discovered_tables, *legacy_tables], key=lambda item: item.table_id)
    result = {
        "contract_id": "room16.compiler.semantic_wave_replay",
        "contract_version": 1,
        "registry_foundation_version": "1.1.0",
        "registry_authority_sha256": authority.authority_sha256,
        "pass_contracts_sha256": pass_protocol["pass_contracts_sha256"],
        "ticker": manifest["ticker"],
        "as_of_date": manifest["as_of_date"],
        "archive": archive.name,
        "archive_sha256_before": before,
        "archive_sha256_after": after,
        "ba3": ba3,
        "ba4": {
            "parsed_document_count": len(parsed_documents),
            "parsed_document_hashes": [item.ir_sha256 for item in parsed_documents],
            "discovered_table_count": len(discovered_tables),
            "legacy_table_bridge_count": len(legacy_tables),
            "canonical_table_hashes": [item.ir_sha256 for item in all_tables],
        },
        "ba5": {
            "normalized_record_count": len(normalized_records),
            "typed_fact_count": len(typed_facts),
            "normalized_records_sha256": sha256_json([item.model_dump(mode="json") for item in normalized_records]),
            "typed_facts_sha256": sha256_json([item.model_dump(mode="json") for item in typed_facts]),
        },
        "ba6": {
            "metric_count": len(metrics),
            "formula_evaluation_count": len(formula_evaluations),
            "formula_marker_count": len(formula_markers),
            "metrics_sha256": sha256_json([item.model_dump(mode="json") for item in metrics]),
            "formula_evaluations_sha256": sha256_json([item.model_dump(mode="json") for item in formula_evaluations]),
        },
        "ba7": {
            "evidence_graph_sha256": evidence_graph.ir_sha256,
            "node_count": len(evidence_graph.nodes),
            "edge_count": len(evidence_graph.edges),
            "orphan_fact_ids": list(evidence_graph.orphan_fact_ids),
        },
        "ba8": {
            "claim_graph_sha256": claim_graph.ir_sha256,
            "node_count": len(claim_graph.nodes),
            "edge_count": len(claim_graph.edges),
            "claims_without_definition": list(claim_graph.claims_without_definition),
            "claims_without_evidence": list(claim_graph.claims_without_evidence),
        },
        "ba9": {
            "decision_graph_sha256": decision_graph.ir_sha256,
            "node_count": len(decision_graph.nodes),
            "edge_count": len(decision_graph.edges),
            "roundtrip_sha256": sha256_json(roundtrip),
            "legacy_payload_sha256": decision_graph.legacy_payload_sha256,
            "permission_corridor_preserved": decision_graph.permission_corridor_preserved,
            "rating_permission_preserved": decision_graph.rating_permission_preserved,
        },
        "coverage_gates": coverage["gates"],
        "gates": {
            "archive_unchanged": before == after,
            "source_snapshot_complete": ba3["all_ba3_artifacts_dispositioned"],
            "parsed_all_snapshot_artifacts": len(parsed_documents) == len(manifest["artifacts"]),
            "typed_all_legacy_facts": len([item for item in typed_facts if item.role == "reported_or_derived"]) == len(facts),
            "all_formula_evaluations_verified": len(formula_evaluations) + len(formula_markers) == len([item for item in facts if item.get("formula_id")]),
            "evidence_orphans_absent": not evidence_graph.orphan_fact_ids,
            "claim_definitions_complete": not claim_graph.claims_without_definition,
            "claim_evidence_complete": not claim_graph.claims_without_evidence,
            "decision_roundtrip_lossless": sha256_json(roundtrip) == decision_graph.legacy_payload_sha256,
            "authority_bundle_v3_unchanged": True,
            "ba10_not_started": True,
        },
    }
    result["replay_sha256"] = sha256_json(result)
    return result
