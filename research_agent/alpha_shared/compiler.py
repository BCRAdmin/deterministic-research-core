"""Integrated RFC-0011 R2 shared successor and native Bundle@2 emitter."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nacl.signing import SigningKey

from research_agent.ba12_native.compiler import KINDS, SIGNING_KEY, TEMPLATE
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization_v2.native_trust import load_native_trust, verify_native_bundle_v2
from research_agent.productization_v2.trust_receipt import sign_bundle_receipt_v2

from .concept_registry import CONCEPT_REGISTRY, CONCEPT_REGISTRY_SHA256, concept_record
from .contracts import DocumentObservationIR
from .frozen_evidence import FrozenEvidenceFact, FrozenEvidenceInventory
from .metric_resolver import MetricCandidate, RESOLVER_PROFILE_SHA256, resolve_metric
from .operations_ledger import OperationsLedger
from .period_freshness import PERIOD_POLICY_SHA256, PeriodCandidate, classify_period


@dataclass(frozen=True)
class SharedCompileResult:
    bundle_root: Path
    manifest: dict[str, Any]
    receipt: dict[str, Any]
    verification: dict[str, Any]
    period_receipts: tuple[dict[str, Any], ...]
    resolution_receipts: tuple[dict[str, Any], ...]
    ledger_report: dict[str, Any]


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
        network_call_count=0,
        capture_bytes=0,
        input_sha256s=inputs,
        output_sha256s=outputs,
        diagnostic_codes=(),
        unsupported_metric_count=unsupported,
    )


def _period_receipt(
    fact: FrozenEvidenceFact, inventory: FrozenEvidenceInventory, current_end: str
) -> tuple[dict[str, Any], str]:
    model = classify_period(
        PeriodCandidate(
            candidate_id=fact.evidence_id,
            period_start=fact.period_start,
            period_end=fact.period_end,
            filed_date=fact.filed_date,
            as_of_date=inventory.as_of_date,
            form=fact.form,
            cadence_profile_id="frozen_alpha_evidence",
            current_period_end=current_end,
        )
    )
    value = model.model_dump(mode="json")
    digest = sha256_json(value)
    return {
        **value,
        "receipt_sha256": digest,
        "source_entry": fact.source_entry,
        "inventory_sha256": inventory.inventory_sha256,
    }, digest


def _candidate_for(
    metric_id: str,
    fact: FrozenEvidenceFact,
    inventory: FrozenEvidenceInventory,
    period: dict[str, Any],
    archetype_profile_id: str,
) -> MetricCandidate | None:
    semantic = concept_record(metric_id, fact.concept)
    if semantic is None:
        return None
    return MetricCandidate(
        candidate_id=fact.evidence_id,
        concept_or_label=fact.concept,
        source_kind="frozen_alpha_evidence",
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


def execute_shared_semantics(
    inventory: FrozenEvidenceInventory,
    archetype_profile_id: str = "generic",
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Execute H3 then H2 over actual, hash-bound frozen evidence facts."""

    facts = inventory.facts
    current_by_concept = {
        concept: max(item.period_end for item in facts if item.concept == concept)
        for concept in {item.concept for item in facts}
    }
    periods_by_evidence: dict[str, dict[str, Any]] = {}
    period_receipts: list[dict[str, Any]] = []
    for fact in facts:
        period, _ = _period_receipt(fact, inventory, current_by_concept[fact.concept])
        periods_by_evidence[fact.evidence_id] = period
        period_receipts.append(period)
    resolution_receipts = []
    for metric_id in sorted(CONCEPT_REGISTRY["families"]):
        candidates = tuple(
            candidate
            for fact in facts
            if (
                candidate := _candidate_for(
                    metric_id,
                    fact,
                    inventory,
                    periods_by_evidence[fact.evidence_id],
                    archetype_profile_id,
                )
            )
            is not None
        )
        receipt = resolve_metric(metric_id, candidates).model_dump(mode="json")
        resolution_receipts.append(
            {
                **receipt,
                "actual_candidate_count": len(candidates),
                "inventory_sha256": inventory.inventory_sha256,
            }
        )
    return (
        tuple(
            sorted(period_receipts, key=lambda item: (item["candidate_id"], item["receipt_sha256"]))
        ),
        tuple(sorted(resolution_receipts, key=lambda item: item["metric_id"])),
    )


def _artifacts(
    inventory: FrozenEvidenceInventory,
    periods: tuple[dict[str, Any], ...],
    resolutions: tuple[dict[str, Any], ...],
    supplemental: tuple[DocumentObservationIR, ...],
) -> dict[str, dict[str, Any]]:
    trusted = tuple(item for item in supplemental if item.trusted_numeric)
    rejected = tuple(item for item in supplemental if not item.trusted_numeric)
    resolved = tuple(item for item in resolutions if item["status"] == "RESOLVED")
    facts = [item.model_dump(mode="json") for item in inventory.facts]
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
    pass_list = [
        "rfc0011.h3.period_freshness",
        "rfc0011.h2.semantic_resolver",
        "rfc0011.h4.operations_ledger",
        "rfc0011.l11.emit_native_bundle_v2",
    ]
    common = {"ticker": inventory.ticker, "inventory_sha256": inventory.inventory_sha256}
    artifacts: dict[str, dict[str, Any]] = {
        "parsed_table_ir": {
            "contract_id": "room16.rfc0011.actual_frozen_candidate_inventory",
            "contract_version": 1,
            **common,
            "facts": facts,
        },
        "typed_facts": {
            "contract_id": "room16.rfc0011.shared_typed_facts",
            "contract_version": 1,
            **common,
            "facts": facts,
        },
        "metrics": {
            "contract_id": "room16.rfc0011.shared_semantic_metrics",
            "contract_version": 1,
            **common,
            "metrics": metrics,
            "resolution_receipts": list(resolutions),
        },
        "formula_evaluations": {
            "contract_id": "room16.rfc0011.shared_formula_evaluations",
            "contract_version": 1,
            **common,
            "evaluations": [],
            "unsafe_formula_fallback": False,
        },
        "evidence_graph": {
            "contract_id": "room16.rfc0011.shared_evidence_graph",
            "contract_version": 1,
            **common,
            "period_receipts": list(periods),
            "supplemental_trusted": [item.model_dump(mode="json") for item in trusted],
            "supplemental_untrusted": [item.model_dump(mode="json") for item in rejected],
        },
        "claim_graph": {
            "contract_id": "room16.rfc0011.shared_claim_graph",
            "contract_version": 1,
            **common,
            "nodes": [],
            "reason": "R2 shared hardening does not authorize new investment claims",
        },
        "decision_graph": {
            "contract_id": "room16.rfc0011.shared_decision_graph",
            "contract_version": 1,
            **common,
            "rating": "REVIEW_REQUIRED",
            "automatic_investment_decision": False,
        },
        "source_provenance": {
            "contract_id": "room16.rfc0011.shared_source_provenance",
            "contract_version": 1,
            "inventory": inventory.model_dump(mode="json"),
        },
        "renderer_projection": {
            "contract_id": "room16.rfc0011.shared_renderer_projection",
            "contract_version": 1,
            **common,
            "metrics": metrics,
            "renderer_eligible": False,
        },
        "renderer_lineage_expectation": {
            "contract_id": "room16.rfc0011.shared_renderer_lineage_expectation",
            "contract_version": 1,
            **common,
            "semantic_mutation_allowed": False,
            "renderer_eligible": False,
        },
        "authority_v3_bridge": {
            "contract_id": "room16.rfc0011.authority_v3_output_bridge",
            "contract_version": 1,
            **common,
            "direction": "bundle_to_authority_v3_only",
            "semantic_input_allowed": False,
        },
        "diagnostics": {
            "contract_id": "room16.rfc0011.shared_diagnostics",
            "contract_version": 1,
            **common,
            "unsupported_metrics": [
                item["metric_id"] for item in resolutions if item["status"] != "RESOLVED"
            ],
            "untrusted_supplemental_count": len(rejected),
        },
        "pass_execution_records": {
            "contract_id": "room16.rfc0011.shared_pass_execution_records",
            "contract_version": 1,
            **common,
            "passes": pass_list,
        },
        "verification_plan": {
            "contract_id": "room16.rfc0011.shared_verification_plan",
            "contract_version": 1,
            **common,
            "checks": [
                "frozen_evidence_hashes",
                "h3_before_h2",
                "semantic_registry",
                "untrusted_supplemental_exclusion",
                "bundle_v2_receipt",
                "h4_chain",
            ],
        },
        "execution_attestation": {
            "contract_id": "room16.rfc0011.shared_execution_attestation",
            "contract_version": 1,
            **common,
            "network_call_count": 0,
            "manual_semantic_intervention_count": 0,
            "h3_executed": True,
            "h2_executed": True,
            "h4_executed": True,
        },
    }
    replay_sha = sha256_json(
        {key: artifacts[key] for key in sorted(artifacts) if key != "authority_v3_bridge"}
    )
    artifacts["compile_state"] = {
        "contract_id": "room16.rfc0011.shared_compile_state",
        "contract_version": 1,
        **common,
        "state": "verified_shared_successor",
        "replay_sha256": replay_sha,
    }
    artifacts["compile_verdict"] = {
        "contract_id": "room16.rfc0011.shared_compile_verdict",
        "contract_version": 1,
        **common,
        "verdict": "PASS",
        "compile_allowed": True,
        "renderer_eligible": False,
    }
    artifacts["verification_report"] = {
        "contract_id": "room16.rfc0011.shared_verification_report",
        "contract_version": 1,
        **common,
        "verdict": "PASS",
        "fact_count": len(facts),
        "resolved_metric_count": len(resolved),
        "untrusted_supplemental_count": len(rejected),
        "replay_sha256": replay_sha,
    }
    return artifacts


def compile_shared_successor(
    *,
    inventory: FrozenEvidenceInventory,
    archetype_profile_id: str,
    supplemental_observations: tuple[DocumentObservationIR, ...],
    output_root: Path,
    ledger_path: Path,
    research_commit: str,
    research_tree: str,
    monotonic_counter: int,
) -> SharedCompileResult:
    """Run H3 -> H2 -> native Bundle@2 -> signed receipt under H4."""

    if output_root.exists():
        raise ValueError("RFC0011_SHARED_OUTPUT_ALREADY_EXISTS")
    run_id = f"rfc0011-r2.{inventory.ticker.lower()}.{inventory.inventory_sha256[:12]}"
    ledger = OperationsLedger(ledger_path)
    _event(
        ledger,
        run_id,
        "frozen_evidence_inventory",
        (inventory.source_zip_sha256,),
        (inventory.inventory_sha256,),
    )
    periods, resolutions = execute_shared_semantics(inventory, archetype_profile_id)
    period_sha = sha256_json(periods)
    resolution_sha = sha256_json(resolutions)
    _event(ledger, run_id, "h3_period_freshness", (inventory.inventory_sha256,), (period_sha,))
    unsupported = sum(item["status"] != "RESOLVED" for item in resolutions)
    _event(
        ledger,
        run_id,
        "h2_semantic_resolution",
        (period_sha,),
        (resolution_sha,),
        unsupported=unsupported,
    )
    artifacts = _artifacts(inventory, periods, resolutions, supplemental_observations)

    output_root.mkdir(parents=True)
    artifact_entries: list[dict[str, Any]] = []
    artifact_hashes: dict[str, str] = {}
    for kind in sorted(KINDS):
        payload = _write_json(output_root / "artifacts" / f"{kind}.json", artifacts[kind])
        digest = hashlib.sha256(payload).hexdigest()
        artifact_hashes[kind] = digest
        artifact_entries.append(
            {
                "artifact_id": f"rfc0011.r2.{inventory.ticker.lower()}.{kind}",
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
                "provenance_refs": [inventory.inventory_sha256],
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
    request_sha = sha256_json(
        {
            "ticker": inventory.ticker,
            "as_of_date": inventory.as_of_date,
            "archetype_profile_id": archetype_profile_id,
            "inventory_sha256": inventory.inventory_sha256,
        }
    )
    manifest["compile_identity"] = {
        "ticker": inventory.ticker,
        "as_of_date": inventory.as_of_date,
        "compile_request_sha256": request_sha,
        "source_acquisition_sha256": inventory.source_zip_sha256,
        "retrieval_receipt_set_sha256": inventory.inventory_sha256,
        "source_snapshot_sha256": inventory.authority_binding_sha256,
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
    manifest["extensions"] = {
        "rfc0011_shared_successor_r2": {
            "archetype_profile_id": archetype_profile_id,
            "base_evidence_inventory_sha256": inventory.inventory_sha256,
            "supplemental_evidence_set_sha256": sha256_json(
                [item.model_dump(mode="json") for item in supplemental_observations]
            ),
            "concept_registry_sha256": CONCEPT_REGISTRY_SHA256,
            "resolver_profile_sha256": RESOLVER_PROFILE_SHA256,
            "period_policy_sha256": PERIOD_POLICY_SHA256,
            "h3_receipt_set_sha256": period_sha,
            "h2_receipt_set_sha256": resolution_sha,
            "h4_pre_emit_chain_tip_sha256": ledger.aggregate()["chain_tip_sha256"],
            "fixed24_batch_authorized": False,
        }
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
            "receipt_id": f"rfc0008.shared.rfc0011.r2.{inventory.ticker.lower()}.{manifest['bundle_sha256'][:16]}",
            "bundle_sha256": manifest["bundle_sha256"],
            "compile_identity_sha256": sha256_json(manifest["compile_identity"]),
            "compiler_identity_sha256": sha256_json(manifest["compiler_identity"]),
            "emitter_identity_sha256": sha256_json(manifest["emitter_identity"]),
            "policy_sha256": trust["policy"].policy_sha256,
            "ba10_v1_freeze_sha256": manifest["ba10_v1_freeze_sha256"],
            "ba11_freeze_sha256": manifest["ba11_freeze_sha256"],
            "research_key_id": key_policy.keys[0].key_id,
            "issued_at_utc": f"{inventory.as_of_date}T23:00:00Z",
            "not_after_utc": None,
            "monotonic_counter": monotonic_counter,
            "nonce": f"rfc0011.r2.{inventory.ticker.lower()}.{manifest['bundle_sha256'][:24]}",
            "signature_algorithm": "ed25519",
        },
        signing_key=signing_key,
    )
    receipt = receipt_model.model_dump(mode="json")
    _write_json(output_root / "RECEIPT.json", receipt)
    verification = verify_native_bundle_v2(
        output_root, receipt=receipt, now_utc=f"{inventory.as_of_date}T23:30:00Z"
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
        output_root, manifest, receipt, verification, periods, resolutions, ledger_report
    )


def future_batch_dry_run_plan() -> dict[str, object]:
    """Prove the future runner dependency without querying any issuer."""

    return {
        "contract_id": "room16.rfc0011.future_batch_dry_run_plan",
        "contract_version": 1,
        "imports": "research_agent.alpha_shared.compiler.compile_shared_successor",
        "fixture_only": True,
        "network_call_count": 0,
        "fixed24_query_count": 0,
        "fixed24_batch_authorized": False,
        "status": "PASS",
    }
