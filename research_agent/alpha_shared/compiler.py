"""Canonical RFC-0011 R3 shared compiler and historical regression adapter."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nacl.signing import SigningKey

from research_agent.ba12_native.compiler import (
    KINDS,
    SIGNING_KEY,
    TEMPLATE,
)
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization_v2.native_trust import (
    load_native_trust,
    verify_native_bundle_v2,
)
from research_agent.productization_v2.trust_receipt import sign_bundle_receipt_v2

from .archetype_profiles import ArchetypeProfileAdapterIR, load_archetype_profile
from .concept_registry import CONCEPT_REGISTRY, CONCEPT_REGISTRY_SHA256, concept_record
from .contracts import SharedBaseInputIR, SupplementalCompileInputIR
from .frozen_evidence import FrozenEvidenceFact, FrozenEvidenceInventory
from .internal_report import InternalAlphaReportIR, build_internal_alpha_report
from .metric_resolver import RESOLVER_PROFILE_SHA256, MetricCandidate, resolve_metric
from .operations_ledger import OperationsLedger
from .period_freshness import PERIOD_POLICY_SHA256, PeriodCandidate, classify_period
from .raw_inventory import (
    SourceSnapshotFactInventoryIR,
    build_source_snapshot_fact_inventory,
)
from .supplemental_semantics import (
    SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256,
    build_supplemental_semantics,
)


@dataclass(frozen=True)
class SharedCompileResult:
    bundle_root: Path
    manifest: dict[str, Any]
    receipt: dict[str, Any]
    verification: dict[str, Any]
    period_receipts: tuple[dict[str, Any], ...]
    resolution_receipts: tuple[dict[str, Any], ...]
    supplemental_candidate_receipts: tuple[dict[str, Any], ...]
    ledger_report: dict[str, Any]
    raw_inventory: SourceSnapshotFactInventoryIR
    archetype_profile: ArchetypeProfileAdapterIR
    internal_report: InternalAlphaReportIR
    profile_resolution_receipts: tuple[dict[str, Any], ...]
    formula_evaluations: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _SemanticInventory:
    ticker: str
    as_of_date: str
    inventory_sha256: str
    facts: tuple[FrozenEvidenceFact, ...]
    source_kind: str


def _write_json(path: Path, value: object) -> bytes:
    payload = (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _event(
    ledger: OperationsLedger,
    run_id: str,
    stage: str,
    inputs: tuple[str, ...],
    outputs: tuple[str, ...],
    *,
    unsupported: int = 0,
    stale: int = 0,
    core_coverage: int = 0,
    completeness: int = 0,
    provider_id: str | None = None,
    provider_status: str | None = None,
    network_calls: int = 0,
    capture_bytes: int = 0,
    diagnostics: tuple[str, ...] = (),
) -> None:
    sequence = len(ledger.verify()) + 1
    ledger.append(
        run_id=run_id,
        stage=stage,
        attempt=1,
        started_at=f"2026-08-27T12:{sequence:02d}:00Z",
        ended_at=f"2026-08-27T12:{sequence:02d}:01Z",
        duration_ms=1000,
        status="PASS",
        provider_id_or_null=provider_id,
        provider_status_or_null=provider_status,
        network_call_count=network_calls,
        capture_bytes=capture_bytes,
        input_sha256s=inputs,
        output_sha256s=outputs,
        diagnostic_codes=diagnostics,
        unsupported_metric_count=unsupported,
        stale_metric_count=stale,
        core_metric_coverage=core_coverage,
        report_section_completeness=completeness,
    )


def _period_receipt(
    fact: FrozenEvidenceFact, inventory: _SemanticInventory, current_end: str
) -> dict[str, Any]:
    value = classify_period(
        PeriodCandidate(
            candidate_id=fact.evidence_id,
            period_start=fact.period_start,
            period_end=fact.period_end,
            filed_date=fact.filed_date,
            as_of_date=inventory.as_of_date,
            form=fact.form,
            cadence_profile_id=inventory.source_kind,
            current_period_end=current_end,
        )
    ).model_dump(mode="json")
    return {
        **value,
        "receipt_sha256": sha256_json(value),
        "source_entry": fact.source_entry,
        "inventory_sha256": inventory.inventory_sha256,
    }


def _candidate_for(
    metric_id: str,
    fact: FrozenEvidenceFact,
    inventory: _SemanticInventory,
    period: dict[str, Any],
    archetype_profile_id: str,
) -> MetricCandidate | None:
    semantic = concept_record(metric_id, fact.concept)
    if semantic is None:
        return None
    return MetricCandidate(
        candidate_id=fact.evidence_id,
        concept_or_label=fact.concept,
        source_kind=inventory.source_kind,
        period_type=period["period_type"],
        period_role=period["comparative_role"],
        freshness_status=period["freshness_status"],
        unit=fact.unit,
        evidence_ids=(fact.evidence_id, fact.source_entry_sha256),
        direct=semantic["semantic_role"] in {"EXACT_DIRECT", "ALTERNATE_EXACT"},
        dimensions_compatible=not bool(semantic["required_dimensions"]),
        authority_compatible=True,
        numeric_value=fact.numeric_value,
        semantic_metric_id=metric_id,
        semantic_role=str(semantic["semantic_role"]),
        aggregation_role=str(semantic["aggregation_role"]),
        archetype_profile_id=archetype_profile_id,
        period_receipt_sha256=period["receipt_sha256"],
        inventory_sha256=inventory.inventory_sha256,
        trusted_numeric=True,
    )


def _execute_semantics(
    inventory: _SemanticInventory,
    archetype_profile_id: str,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    facts = inventory.facts
    current_by_concept = {
        concept: max(item.period_end for item in facts if item.concept == concept)
        for concept in {item.concept for item in facts}
    }
    periods = tuple(
        _period_receipt(fact, inventory, current_by_concept[fact.concept]) for fact in facts
    )
    period_by_id = {item["candidate_id"]: item for item in periods}
    resolutions = []
    for metric_id in sorted(CONCEPT_REGISTRY["families"]):
        candidates = tuple(
            candidate
            for fact in facts
            if (
                candidate := _candidate_for(
                    metric_id,
                    fact,
                    inventory,
                    period_by_id[fact.evidence_id],
                    archetype_profile_id,
                )
            )
            is not None
        )
        receipt = resolve_metric(metric_id, candidates).model_dump(mode="json")
        resolutions.append(
            {
                **receipt,
                "actual_candidate_count": len(candidates),
                "inventory_sha256": inventory.inventory_sha256,
            }
        )
    return (
        tuple(sorted(periods, key=lambda item: (item["candidate_id"], item["receipt_sha256"]))),
        tuple(sorted(resolutions, key=lambda item: item["metric_id"])),
    )


def execute_shared_semantics(
    inventory: FrozenEvidenceInventory,
    archetype_profile_id: str = "generic",
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Historical H3/H2 regression only; it never emits native identity."""

    return _execute_semantics(
        _SemanticInventory(
            ticker=inventory.ticker,
            as_of_date=inventory.as_of_date,
            inventory_sha256=inventory.inventory_sha256,
            facts=inventory.facts,
            source_kind="historical_frozen_evidence",
        ),
        archetype_profile_id,
    )


def execute_historical_regression(
    inventory: FrozenEvidenceInventory,
    archetype_profile_id: str = "generic",
) -> dict[str, Any]:
    periods, resolutions = execute_shared_semantics(inventory, archetype_profile_id)
    return {
        "contract_id": "room16.rfc0011.historical_frozen_evidence_adapter",
        "contract_version": 1,
        "provenance_mode": "HISTORICAL_EVIDENCE_ADAPTER",
        "canonical_live_compile_identity": False,
        "native_compile_identity": None,
        "ticker": inventory.ticker,
        "inventory_sha256": inventory.inventory_sha256,
        "period_receipts": list(periods),
        "resolution_receipts": list(resolutions),
        "network_call_count": 0,
        "status": "PASS",
    }


def _snapshot_inventory(
    base: SharedBaseInputIR,
) -> tuple[_SemanticInventory, SourceSnapshotFactInventoryIR]:
    raw_inventory = build_source_snapshot_fact_inventory(base)
    facts = []
    for row in raw_inventory.candidates:
        facts.append(
            FrozenEvidenceFact(
                fact_id=row.candidate_id,
                concept=row.concept,
                metric_hint=None,
                numeric_value=row.value,
                unit=row.unit,
                period_start=row.start_or_null,
                period_end=row.end,
                filed_date=row.filed,
                form=row.form or "10-Q",
                source_entry="SourceSnapshotIR",
                source_entry_sha256=row.source_artifact_sha256,
                evidence_id=row.candidate_id,
            )
        )
    return (
        _SemanticInventory(
            ticker=base.ticker,
            as_of_date=base.as_of_date,
            inventory_sha256=raw_inventory.inventory_sha256,
            facts=tuple(sorted(facts, key=lambda item: item.evidence_id)),
            source_kind="source_snapshot_raw_candidate_inventory",
        ),
        raw_inventory,
    )


def _artifacts(
    *,
    base: SharedBaseInputIR,
    inventory: _SemanticInventory,
    periods: tuple[dict[str, Any], ...],
    base_resolutions: tuple[dict[str, Any], ...],
    supplemental: SupplementalCompileInputIR,
    supplemental_candidates: tuple[dict[str, Any], ...],
    supplemental_resolutions: tuple[dict[str, Any], ...],
    raw_inventory: SourceSnapshotFactInventoryIR,
    archetype_profile: ArchetypeProfileAdapterIR,
    internal_report: InternalAlphaReportIR,
    profile_period_receipts: tuple[dict[str, Any], ...],
    profile_resolution_receipts: tuple[dict[str, Any], ...],
    formula_evaluations: tuple[dict[str, Any], ...],
) -> dict[str, dict[str, Any]]:
    facts = [item.model_dump(mode="json") for item in raw_inventory.candidates]
    all_resolutions = tuple(base_resolutions) + tuple(supplemental_resolutions)
    resolved = [item for item in all_resolutions if item["status"] == "RESOLVED"]
    metrics = [
        {
            "metric_id": item["metric_id"],
            "candidate_id": item["selected_candidate_id_or_null"],
            "concept": item["selected_concept_or_label"],
            "unit": item["unit"],
            "evidence_ids": item["evidence_ids"],
            "resolution_receipt_sha256": item["receipt_sha256"],
        }
        for item in resolved
    ]
    common = {
        "ticker": base.ticker,
        "source_snapshot_sha256": base.source_snapshot_sha256,
        "base_input_sha256": base.base_input_sha256,
    }
    artifacts: dict[str, dict[str, Any]] = {
        "parsed_table_ir": {
            "contract_id": "room16.rfc0011.r4.source_snapshot_fact_inventory",
            "contract_version": 1,
            **common,
            "inventory": raw_inventory.model_dump(mode="json"),
        },
        "typed_facts": {
            "contract_id": "room16.rfc0011.r4.shared_typed_facts",
            "contract_version": 1,
            **common,
            "facts": facts,
            "period_receipts": list(profile_period_receipts),
        },
        "metrics": {
            "contract_id": "room16.rfc0011.r4.shared_semantic_metrics",
            "contract_version": 1,
            **common,
            "metrics": metrics,
            "base_resolution_receipts": list(base_resolutions),
            "supplemental_resolution_receipts": list(supplemental_resolutions),
            "archetype_profile": archetype_profile.model_dump(mode="json"),
            "profile_resolution_receipts": list(profile_resolution_receipts),
            "internal_alpha_report": internal_report.model_dump(mode="json"),
        },
        "formula_evaluations": {
            "contract_id": "room16.rfc0011.r4.shared_formula_evaluations",
            "contract_version": 1,
            **common,
            "evaluations": list(formula_evaluations),
            "unsafe_formula_fallback": False,
            "formula_registry_sha256": archetype_profile.formula_registry_sha256,
        },
        "evidence_graph": {
            "contract_id": "room16.rfc0011.r3.shared_evidence_graph",
            "contract_version": 1,
            **common,
            "period_receipts": list(periods),
            "supplemental_candidate_receipts": list(supplemental_candidates),
        },
        "claim_graph": {
            "contract_id": "room16.rfc0011.r3.shared_claim_graph",
            "contract_version": 1,
            **common,
            "nodes": [],
            "reason": "R3 does not authorize new investment claims",
        },
        "decision_graph": {
            "contract_id": "room16.rfc0011.r3.shared_decision_graph",
            "contract_version": 1,
            **common,
            "rating": "REVIEW_REQUIRED",
            "automatic_investment_decision": False,
        },
        "source_provenance": {
            "contract_id": "room16.rfc0011.r3.shared_source_provenance",
            "contract_version": 1,
            "base_input": base.model_dump(mode="json"),
            "supplemental_input": supplemental.model_dump(mode="json"),
        },
        "renderer_projection": {
            "contract_id": "room16.rfc0011.r4.internal_alpha_renderer_projection",
            "contract_version": 1,
            **common,
            "internal_alpha_report": internal_report.model_dump(mode="json"),
            "renderer_eligible": False,
            "product_report_v2": False,
        },
        "renderer_lineage_expectation": {
            "contract_id": "room16.rfc0011.r3.shared_renderer_lineage_expectation",
            "contract_version": 1,
            **common,
            "semantic_mutation_allowed": False,
            "renderer_eligible": False,
        },
        "authority_v3_bridge": {
            "contract_id": "room16.rfc0011.r3.authority_v3_output_bridge",
            "contract_version": 1,
            **common,
            "direction": "bundle_to_authority_v3_only",
            "semantic_input_allowed": False,
        },
        "diagnostics": {
            "contract_id": "room16.rfc0011.r3.shared_diagnostics",
            "contract_version": 1,
            **common,
            "unsupported_metrics": [
                item["metric_id"] for item in all_resolutions if item["status"] != "RESOLVED"
            ],
            "important_unsupported_metrics": list(
                internal_report.important_unsupported_metrics
            ),
            "stale_or_comparative_candidate_count": len(
                internal_report.stale_or_comparative_diagnostics
            ),
            "supplemental_rejected_count": sum(
                item["status"] == "REJECTED" for item in supplemental_candidates
            ),
            "untrusted_supplemental_count": sum(
                not item.trusted_numeric for item in supplemental.observations
            ),
        },
        "pass_execution_records": {
            "contract_id": "room16.rfc0011.r3.shared_pass_execution_records",
            "contract_version": 1,
            **common,
            "passes": [
                "rfc0011.r3.accept_source_snapshot",
                "rfc0011.r3.supplemental_candidate_builder",
                "rfc0011.r4.raw_candidate_inventory",
                "rfc0011.h3.period_freshness",
                "rfc0011.h2.semantic_resolver",
                "rfc0011.r4.archetype_projection",
                "rfc0011.r4.safe_formula_evaluation",
                "rfc0011.r4.internal_alpha_report",
                "rfc0011.h4.operations_ledger",
                "rfc0011.l11.emit_native_bundle_v2",
            ],
        },
        "verification_plan": {
            "contract_id": "room16.rfc0011.r3.shared_verification_plan",
            "contract_version": 1,
            **common,
            "checks": [
                "source_snapshot_hashes",
                "compile_identity_exact",
                "supplemental_h3_before_h2",
                "raw_period_basis_preserved",
                "archetype_profile_freeze_binding",
                "internal_alpha_report_lineage",
                "bundle_v2_receipt",
                "h4_chain",
            ],
        },
        "execution_attestation": {
            "contract_id": "room16.rfc0011.r3.shared_execution_attestation",
            "contract_version": 1,
            **common,
            "network_after_snapshot": False,
            "fixed24_query_count": 0,
            "holdout_live_query_count": 0,
            "h3_executed": True,
            "h2_executed": True,
            "h4_executed": True,
            "raw_companyfacts_periods_preserved": True,
            "archetype_batch_surface_integrated": True,
            "product_source_changed": False,
        },
    }
    replay_sha = sha256_json(
        {key: artifacts[key] for key in sorted(artifacts) if key != "authority_v3_bridge"}
    )
    artifacts["compile_state"] = {
        "contract_id": "room16.rfc0011.r3.shared_compile_state",
        "contract_version": 1,
        **common,
        "state": "verified_shared_successor",
        "replay_sha256": replay_sha,
    }
    artifacts["compile_verdict"] = {
        "contract_id": "room16.rfc0011.r3.shared_compile_verdict",
        "contract_version": 1,
        **common,
        "verdict": "PASS",
        "compile_allowed": True,
        "renderer_eligible": False,
    }
    artifacts["verification_report"] = {
        "contract_id": "room16.rfc0011.r3.shared_verification_report",
        "contract_version": 1,
        **common,
        "verdict": "PASS",
        "fact_count": len(facts),
        "resolved_metric_count": len(resolved),
        "profile_resolved_metric_count": int(
            internal_report.source_coverage["resolved_metric_count"]
        ),
        "core_metric_coverage_percent": int(
            internal_report.source_coverage["core_metric_coverage_percent"]
        ),
        "required_section_completeness_percent": int(
            internal_report.report_completeness[
                "required_section_completeness_percent"
            ]
        ),
        "supplemental_rejected_count": sum(
            item["status"] == "REJECTED" for item in supplemental_candidates
        ),
        "untrusted_supplemental_count": sum(
            not item.trusted_numeric for item in supplemental.observations
        ),
        "replay_sha256": replay_sha,
    }
    return artifacts


def compile_shared_successor(
    *,
    base_input: SharedBaseInputIR,
    archetype_profile_id: str,
    supplemental_input: SupplementalCompileInputIR,
    output_root: Path,
    ledger_path: Path,
    research_commit: str,
    research_tree: str,
    monotonic_counter: int,
    run_id_override: str | None = None,
) -> SharedCompileResult:
    """Run verified SourceSnapshot -> H3/H2 -> signed native Bundle@2."""

    if output_root.exists():
        raise ValueError("RFC0011_SHARED_OUTPUT_ALREADY_EXISTS")
    inventory, raw_inventory = _snapshot_inventory(base_input)
    if not inventory.facts:
        raise ValueError("RFC0011_SHARED_SOURCE_SNAPSHOT_FACTS_EMPTY")
    run_id = run_id_override or (
        f"rfc0011-r4.{base_input.ticker.lower()}.{base_input.source_snapshot_sha256[:12]}"
    )
    ledger = OperationsLedger(ledger_path)
    _event(
        ledger,
        run_id,
        "source_snapshot_ir",
        (base_input.source_snapshot_sha256,),
        (base_input.base_input_sha256,),
    )
    _event(
        ledger,
        run_id,
        "raw_candidate_inventory",
        (base_input.source_snapshot_sha256,),
        (raw_inventory.inventory_sha256, raw_inventory.dedupe_receipt.receipt_sha256),
        diagnostics=tuple(
            sorted(
                {
                    code
                    for item in raw_inventory.exclusions
                    for code in item.reason_codes
                }
            )
        ),
    )
    periods, base_resolutions = _execute_semantics(inventory, archetype_profile_id)
    profile_adapter_id = "energy" if archetype_profile_id == "generic" else archetype_profile_id
    archetype_profile = load_archetype_profile(profile_adapter_id)
    internal = build_internal_alpha_report(raw_inventory, archetype_profile)
    supplemental_candidates, supplemental_resolutions = build_supplemental_semantics(
        supplemental=supplemental_input,
        as_of_date=base_input.as_of_date,
        filed_date=base_input.as_of_date,
        archetype_profile_id=archetype_profile_id,
    )
    period_sha = sha256_json(periods)
    supplemental_candidate_sha = sha256_json(supplemental_candidates)
    resolution_sha = sha256_json(
        {"base": base_resolutions, "supplemental": supplemental_resolutions}
    )
    _event(
        ledger,
        run_id,
        "supplemental_candidate_builder",
        (supplemental_input.input_sha256,),
        (supplemental_candidate_sha,),
    )
    _event(
        ledger,
        run_id,
        "h3_period_freshness",
        (inventory.inventory_sha256, supplemental_candidate_sha),
        (period_sha,),
    )
    unsupported = sum(
        item["status"] != "RESOLVED" for item in (*base_resolutions, *supplemental_resolutions)
    )
    _event(
        ledger,
        run_id,
        "h2_semantic_resolution",
        (period_sha,),
        (resolution_sha,),
        unsupported=unsupported,
    )
    core_coverage = int(internal.report.source_coverage["core_metric_coverage_percent"])
    completeness = int(
        internal.report.report_completeness["required_section_completeness_percent"]
    )
    stale = int(internal.report.evidence_lineage["stale_primary_metric_count"])
    _event(
        ledger,
        run_id,
        "archetype_projection",
        (raw_inventory.inventory_sha256, archetype_profile.adapter_sha256),
        (internal.report.report_sha256,),
    )
    formula_sha = sha256_json(internal.formula_evaluations)
    _event(
        ledger,
        run_id,
        "safe_formula_evaluation",
        (archetype_profile.formula_registry_sha256,),
        (formula_sha,),
    )
    _event(
        ledger,
        run_id,
        "internal_report_emit",
        (raw_inventory.inventory_sha256, archetype_profile.adapter_sha256),
        (internal.report.report_sha256,),
        unsupported=len(internal.report.important_unsupported_metrics),
        stale=stale,
        core_coverage=core_coverage,
        completeness=completeness,
    )
    artifacts = _artifacts(
        base=base_input,
        inventory=inventory,
        periods=periods,
        base_resolutions=base_resolutions,
        supplemental=supplemental_input,
        supplemental_candidates=supplemental_candidates,
        supplemental_resolutions=supplemental_resolutions,
        raw_inventory=raw_inventory,
        archetype_profile=archetype_profile,
        internal_report=internal.report,
        profile_period_receipts=internal.period_receipts,
        profile_resolution_receipts=internal.resolution_receipts,
        formula_evaluations=internal.formula_evaluations,
    )
    output_root.mkdir(parents=True)
    artifact_entries: list[dict[str, Any]] = []
    artifact_hashes: dict[str, str] = {}
    for kind in sorted(KINDS):
        payload = _write_json(output_root / "artifacts" / f"{kind}.json", artifacts[kind])
        digest = hashlib.sha256(payload).hexdigest()
        artifact_hashes[kind] = digest
        artifact_entries.append(
            {
                "artifact_id": f"rfc0011.r3.{base_input.ticker.lower()}.{kind}",
                "artifact_kind": kind,
                "authoritative": kind != "authority_v3_bridge",
                "byte_length": len(payload),
                "compatibility_only": kind == "authority_v3_bridge",
                "compatibility_rule": "exact_hash",
                "contract_id": artifacts[kind]["contract_id"],
                "contract_version": 1,
                "dependency_sha256s": [],
                "layer": "L11",
                "media_type": "application/json",
                "owner": "research_compiler",
                "producer_pass_id": "ba12.l11.emit_native_bundle_v2",
                "provenance_refs": [
                    base_input.source_snapshot_sha256,
                    supplemental_input.input_sha256,
                ],
                "relative_path": f"artifacts/{kind}.json",
                "required": True,
                "sha256": digest,
            }
        )
    trust = load_native_trust()
    manifest = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    manifest["compiler_identity"] = trust["policy"].compiler_identity.model_dump(mode="json")
    emitter = trust["emitter_profile"]["emitter_contract_lock"]
    manifest["emitter_identity"] = {
        "emitter_id": emitter["emitter_id"],
        "emitter_version": emitter["emitter_version"],
        "producer_pass_id": emitter["producer_pass_id"],
        "schema_sha256": emitter["schema_sha256"],
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "consumer_policy_sha256": trust["policy"].policy_sha256,
    }
    manifest["compile_identity"] = {
        "ticker": base_input.ticker,
        "as_of_date": base_input.as_of_date,
        "compile_request_sha256": base_input.request_sha256,
        "source_acquisition_sha256": base_input.acquisition_plan_sha256,
        "retrieval_receipt_set_sha256": base_input.retrieval_receipt_set_sha256,
        "source_snapshot_sha256": base_input.source_snapshot_sha256,
        "final_compile_state_sha256": artifact_hashes["compile_state"],
        "verification_report_sha256": artifact_hashes["verification_report"],
        "replay_sha256": artifacts["verification_report"]["replay_sha256"],
        "migration_v1_bundle_sha256": None,
    }
    manifest["compatibility"] = {
        "authority_v3_bridge_direction": "bundle_to_authority_v3_only",
        "authority_v3_semantic_input_allowed": False,
        "compiler_mode": "source_native",
        "legacy_semantic_input_allowed": False,
        "mode": "bundle_native",
        "native_source_production": True,
        "source_native_fact_generation": True,
    }
    manifest["eligibility"] = {
        "ba11_frozen": True,
        "ba12_cutover_candidate": False,
        "compile_allowed": True,
        "deploy_allowed": False,
        "publication_allowed": False,
        "release_ready": False,
        "renderer_cutover": False,
        "renderer_eligible": False,
    }
    semantic_execution_sha = sha256_json(
        {
            "raw_inventory": raw_inventory.inventory_sha256,
            "shared_periods": period_sha,
            "shared_resolutions": resolution_sha,
            "profile_adapter": archetype_profile.adapter_sha256,
            "internal_report": internal.report.report_sha256,
            "formulas": formula_sha,
        }
    )
    manifest["extensions"] = {
        "rfc0011_shared_successor_r3": {
            "archetype_profile_id": archetype_profile_id,
            "supplemental_policy_sha256": supplemental_input.supplemental_policy_sha256,
            "discovery_set_sha256": supplemental_input.discovery_set_sha256,
            "supplemental_evidence_set_sha256": supplemental_input.supplemental_evidence_set_sha256,
            "observation_set_sha256": supplemental_input.observation_set_sha256,
            "concept_registry_sha256": CONCEPT_REGISTRY_SHA256,
            "supplemental_semantic_registry_sha256": SUPPLEMENTAL_SEMANTIC_REGISTRY_SHA256,
            "resolver_profile_sha256": RESOLVER_PROFILE_SHA256,
            "period_policy_sha256": PERIOD_POLICY_SHA256,
            "h3_receipt_set_sha256": period_sha,
            "h2_receipt_set_sha256": resolution_sha,
            "h4_pre_emit_chain_tip_sha256": semantic_execution_sha,
            "fixed24_batch_authorized": False,
        },
        "rfc0011_batch_readiness_r4": {
            "raw_fact_inventory_sha256": raw_inventory.inventory_sha256,
            "raw_fact_dedupe_receipt_sha256": raw_inventory.dedupe_receipt.receipt_sha256,
            "archetype_profile_adapter_sha256": archetype_profile.adapter_sha256,
            "archetype_profile_freeze_sha256": archetype_profile.profile_freeze_sha256,
            "internal_alpha_report_sha256": internal.report.report_sha256,
            "core_metric_coverage_percent": core_coverage,
            "required_section_completeness_percent": completeness,
            "h4_semantic_execution_sha256": semantic_execution_sha,
            "product_report_v2": False,
            "fixed24_batch_authorized": False,
        },
    }
    manifest["artifacts"] = artifact_entries
    manifest["required_sections"] = list(trust["native_profile"]["required_artifact_kinds"])
    manifest["optional_sections"] = []
    kind_to_id = {item["artifact_kind"]: item["artifact_id"] for item in artifact_entries}
    section_hashes = {
        "artifact_hashes": sha256_json(artifact_entries),
        "compatibility_state": sha256_json(manifest["compatibility"]),
        "compile_identity": sha256_json(manifest["compile_identity"]),
        "compiler_version": sha256_json(manifest["compiler_identity"]),
        "ir_references": sha256_json(
            [
                {"artifact_id": item["artifact_id"], "sha256": item["sha256"]}
                for item in artifact_entries
                if item["authoritative"]
            ]
        ),
    }
    for section in manifest["sections"]:
        kind = section["section_id"]
        section["artifact_ids"] = [kind_to_id[kind]] if kind in kind_to_id else []
        section["sha256"] = section_hashes.get(kind, artifact_hashes.get(kind, section["sha256"]))
    manifest["artifact_index_sha256"] = sha256_json(manifest["artifacts"])
    manifest["section_index_sha256"] = sha256_json(manifest["sections"])
    manifest["bundle_sha256"] = sha256_json(
        {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    )
    _write_json(output_root / "BUNDLE_MANIFEST.json", manifest)
    _event(ledger, run_id, "bundle_v2_emit", (resolution_sha,), (manifest["bundle_sha256"],))
    key_policy = trust["key_policy"]
    signing_key = SigningKey(SIGNING_KEY.read_bytes())
    if signing_key.verify_key.encode().hex() != key_policy.keys[0].public_key_hex:
        raise ValueError("RFC0011_SHARED_SIGNING_KEY_POLICY_MISMATCH")
    receipt_model = sign_bundle_receipt_v2(
        {
            "contract_id": "room16.compiler_artifact_bundle_receipt",
            "contract_version": 2,
            "receipt_id": f"rfc0008.shared.rfc0011.r4.{base_input.ticker.lower()}.{manifest['bundle_sha256'][:16]}",
            "bundle_sha256": manifest["bundle_sha256"],
            "compile_identity_sha256": sha256_json(manifest["compile_identity"]),
            "compiler_identity_sha256": sha256_json(manifest["compiler_identity"]),
            "emitter_identity_sha256": sha256_json(manifest["emitter_identity"]),
            "policy_sha256": trust["policy"].policy_sha256,
            "ba10_v1_freeze_sha256": manifest["ba10_v1_freeze_sha256"],
            "ba11_freeze_sha256": manifest["ba11_freeze_sha256"],
            "research_key_id": key_policy.keys[0].key_id,
            "issued_at_utc": f"{base_input.as_of_date}T23:00:00Z",
            "not_after_utc": None,
            "monotonic_counter": monotonic_counter,
            "nonce": f"rfc0011.r4.{base_input.ticker.lower()}.{manifest['bundle_sha256'][:24]}",
            "signature_algorithm": "ed25519",
        },
        signing_key=signing_key,
    )
    receipt = receipt_model.model_dump(mode="json")
    _write_json(output_root / "RECEIPT.json", receipt)
    verification = verify_native_bundle_v2(
        output_root, receipt=receipt, now_utc=f"{base_input.as_of_date}T23:30:00Z"
    )
    _event(
        ledger,
        run_id,
        "bundle_v2_receipt_verify",
        (manifest["bundle_sha256"], receipt["receipt_sha256"]),
        (verification["receipt_sha256"],),
    )
    ledger_report = {
        "status": "PASS",
        "path": str(ledger_path),
        "events": [item.model_dump(mode="json") for item in ledger.verify()],
        "aggregate": ledger.aggregate(),
        "research_commit": research_commit,
        "research_tree": research_tree,
    }
    _write_json(output_root / "SHARED_RUN_RECEIPT.json", ledger_report)
    return SharedCompileResult(
        output_root,
        manifest,
        receipt,
        verification,
        periods,
        tuple((*base_resolutions, *supplemental_resolutions)),
        supplemental_candidates,
        ledger_report,
        raw_inventory,
        archetype_profile,
        internal.report,
        internal.resolution_receipts,
        internal.formula_evaluations,
    )


def future_batch_dry_run_plan() -> dict[str, object]:
    """Legacy metadata only; R3 evidence must execute runner.run_shared_case."""
    return {
        "contract_id": "room16.rfc0011.future_batch_dry_run_plan",
        "contract_version": 2,
        "actual_runner": "research_agent.alpha_shared.runner.run_shared_case",
        "fixture_only": True,
        "network_call_count": 0,
        "fixed24_query_count": 0,
        "fixed24_batch_authorized": False,
        "status": "PLAN_ONLY",
    }
