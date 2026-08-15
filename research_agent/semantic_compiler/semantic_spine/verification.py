"""BA9/L10 fail-closed verification and computed cross-company gates."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from research_agent.compiler_foundation.contracts import (
    CompileVerdictIR,
    CompilerLayer,
    DiagnosticIR,
    ReleaseEffect,
    SemanticSeverity,
)

from .contracts import (
    ClaimGraphSpineIR,
    DecisionGraphSpineIR,
    EvidenceGraphSpineIR,
    MetricSignatureIR,
    MetricSpineIR,
    NormalizedFactRecordIR,
    SourceInputIR,
    TableDiscoveryIR,
    TypedFactSpineIR,
    VerificationPlanIR,
    VerificationReportIR,
    create_hashed,
)
from .semantics import reconstruct_decision


INVARIANT_CODES = (
    "CLAIM_LINEAGE_COMPLETE",
    "DECISION_GRAPH_ROUNDTRIP_VALID",
    "EVIDENCE_SOURCE_REGISTRY_COMPLETE",
    "FORMULA_EVALUATION_COMPLETE",
    "IR_SPINE_CONNECTED",
    "LEGACY_COMPATIBILITY_ADAPTER_USED",
    "METRIC_SIGNATURE_COVERAGE_COMPLETE",
    "TABLE_DISCOVERY_COVERAGE_COMPLETE",
)


def _diagnostic(*, code: str, passed: bool, subject: str, message: str, details: dict[str, Any], sources: tuple[SourceInputIR, ...], compatibility_notice: bool = False) -> DiagnosticIR:
    return DiagnosticIR(
        code=code,
        semantic_severity=SemanticSeverity.INFO if passed else SemanticSeverity.ERROR,
        release_effect=ReleaseEffect.NONE if passed else ReleaseEffect.COMPILE_BLOCK,
        layer=CompilerLayer.L10_VERIFICATION,
        pass_id="ba9.l10.verify_semantics",
        subject_ref=subject,
        source_refs=tuple(item.provenance for item in sources),
        root_cause_ref=("rfc_0002:explicit_legacy_compatibility" if compatibility_notice else f"rfc_0002:{code.casefold()}"),
        fixture_refs=(f"rfc_0002:{code.casefold()}",),
        message=message,
        details=details,
    )


def verify_semantics(*, ticker: str, as_of_date: str, source_inputs: tuple[SourceInputIR, ...], table_discoveries: tuple[TableDiscoveryIR, ...], normalized: tuple[NormalizedFactRecordIR, ...], facts: tuple[TypedFactSpineIR, ...], signatures: tuple[MetricSignatureIR, ...], metrics: tuple[MetricSpineIR, ...], formula_evaluations: tuple[Any, ...], evidence_graph: EvidenceGraphSpineIR, claim_graph: ClaimGraphSpineIR, decision_graph: DecisionGraphSpineIR, formula_record_count: int) -> tuple[VerificationPlanIR, VerificationReportIR]:
    bound = tuple(sorted({
        *[item.ir_sha256 for item in source_inputs],
        *[item.ir_sha256 for item in table_discoveries],
        *[item.ir_sha256 for item in normalized],
        *[item.ir_sha256 for item in facts],
        *[item.ir_sha256 for item in signatures],
        *[item.ir_sha256 for item in metrics],
        *[item.ir_sha256 for item in formula_evaluations],
        evidence_graph.ir_sha256,
        claim_graph.ir_sha256,
        decision_graph.ir_sha256,
    }))
    plan = create_hashed(
        VerificationPlanIR,
        plan_id=f"verification.{ticker.casefold()}.{as_of_date}",
        bound_ir_sha256s=bound,
        invariant_codes=INVARIANT_CODES,
    )
    diagnostics: list[DiagnosticIR] = []
    compatibility_sources = tuple(item for item in source_inputs if item.input_kind == "legacy_compatibility")
    diagnostics.append(_diagnostic(
        code="LEGACY_COMPATIBILITY_ADAPTER_USED",
        passed=bool(compatibility_sources) and all(item.compatibility_adapter_id for item in compatibility_sources),
        subject=ticker,
        message="Legacy Authority Bundle v3 inputs are explicit, hash-bound compatibility sources; no unlabelled bypass is present.",
        details={"adapter_ids": sorted({str(item.compatibility_adapter_id) for item in compatibility_sources}), "unlabelled_bypass_count": sum(not item.compatibility_adapter_id for item in compatibility_sources)},
        sources=compatibility_sources,
        compatibility_notice=True,
    ))
    normalized_hashes = {item.ir_sha256 for item in normalized}
    connected = bool(normalized) and len(facts) == len(normalized) and all(item.normalized_record_sha256 in normalized_hashes for item in facts)
    diagnostics.append(_diagnostic(
        code="IR_SPINE_CONNECTED", passed=connected, subject=ticker,
        message="Every Typed Fact consumes a hash-bound normalized record produced from the parsed compatibility source.",
        details={"normalized_records": len(normalized), "typed_facts": len(facts)}, sources=compatibility_sources,
    ))
    detected = sum(item.detected_count for item in table_discoveries)
    registered = sum(item.registered_count for item in table_discoveries)
    excluded = sum(item.excluded_count for item in table_discoveries)
    diagnostics.append(_diagnostic(
        code="TABLE_DISCOVERY_COVERAGE_COMPLETE", passed=detected == registered + excluded,
        subject=ticker, message="Every detected source table is registered or explicitly excluded.",
        details={"detected": detected, "registered": registered, "excluded": excluded}, sources=tuple(item for item in source_inputs if item.input_kind == "source_snapshot"),
    ))
    signature_by_id = {item.signature_id: item for item in signatures}
    signature_covered = len(metrics) == len(facts) and all(item.signature_id in signature_by_id and item.signature_sha256 == signature_by_id[item.signature_id].ir_sha256 for item in metrics)
    diagnostics.append(_diagnostic(
        code="METRIC_SIGNATURE_COVERAGE_COMPLETE", passed=signature_covered, subject=ticker,
        message="Every metric instance is bound to one narrow semantic signature and expected contract hash.",
        details={"metric_instances": len(metrics), "signature_instances": len(signatures)}, sources=compatibility_sources,
    ))
    formula_complete = len(formula_evaluations) == formula_record_count
    diagnostics.append(_diagnostic(
        code="FORMULA_EVALUATION_COMPLETE", passed=formula_complete, subject=ticker,
        message="All executable formula records were evaluated from normalized operands.",
        details={"expected": formula_record_count, "evaluated": len(formula_evaluations)}, sources=compatibility_sources,
    ))
    diagnostics.append(_diagnostic(
        code="EVIDENCE_SOURCE_REGISTRY_COMPLETE", passed=not evidence_graph.unknown_source_ids, subject=ticker,
        message="Evidence references only registered sources; missing sources are never synthesized.",
        details={"unknown_source_ids": list(evidence_graph.unknown_source_ids)}, sources=compatibility_sources,
    ))
    lineage_ok = not claim_graph.claims_without_lineage and not claim_graph.numeric_bindings_without_lineage
    diagnostics.append(_diagnostic(
        code="CLAIM_LINEAGE_COMPLETE", passed=lineage_ok, subject=ticker,
        message="Claims and numeric spans have complete Claim→Fact→Evidence→Source→Locator lineage.",
        details={"numeric_lineages": len(claim_graph.numeric_lineages), "claims_without_lineage": list(claim_graph.claims_without_lineage), "numeric_bindings_without_lineage": list(claim_graph.numeric_bindings_without_lineage)}, sources=compatibility_sources,
    ))
    try:
        reconstructed = reconstruct_decision(decision_graph)
        decision_ok = decision_graph.reconstructed_payload_sha256 == decision_graph.comparison_payload_sha256
    except ValueError as exc:
        reconstructed = None
        decision_ok = False
        decision_error = str(exc)
    else:
        decision_error = None
    diagnostics.append(_diagnostic(
        code="DECISION_GRAPH_ROUNDTRIP_VALID", passed=decision_ok, subject=ticker,
        message="Decision packet is reconstructed from graph nodes and edges, not an embedded payload copy.",
        details={"comparison_sha256": decision_graph.comparison_payload_sha256, "reconstructed_sha256": decision_graph.reconstructed_payload_sha256, "error": decision_error, "top_level_keys": sorted(reconstructed) if isinstance(reconstructed, dict) else []}, sources=compatibility_sources,
    ))
    verdict = CompileVerdictIR.derive(diagnostics)
    report = create_hashed(
        VerificationReportIR,
        ticker=ticker,
        as_of_date=as_of_date,
        verification_plan_sha256=plan.ir_sha256,
        diagnostics=tuple(diagnostics),
        verdict=verdict,
    )
    return plan, report


def compute_cross_company_gates(replays: dict[str, dict[str, Any]]) -> dict[str, Any]:
    companies = sorted(replays)
    metric_total = sum(len(item["metrics"]) for item in replays.values())
    covered = sum(
        sum(metric["signature_id"] in {signature["signature_id"] for signature in item["signatures"]} for metric in item["metrics"])
        for item in replays.values()
    )
    diagnostic_counts = Counter(
        diagnostic["code"]
        for item in replays.values()
        for diagnostic in item["verification_report"]["diagnostics"]
        if diagnostic["release_effect"] in {"compile_block", "release_block"}
    )
    signature_contracts: dict[str, set[str]] = defaultdict(set)
    legacy_signatures: dict[str, set[str]] = defaultdict(set)
    for item in replays.values():
        for signature in item["signatures"]:
            signature_contracts[signature["signature_id"]].add(signature["expected_contract_sha256"])
            legacy_signatures[signature["legacy_metric_id"]].add(signature["signature_id"])
    unresolved_collisions = sum(len(values) > 1 for values in signature_contracts.values())
    decision_losses = sum(item["decision_graph"]["comparison_payload_sha256"] != item["decision_graph"]["reconstructed_payload_sha256"] for item in replays.values())
    changed_archives = sum(item["archive_sha256_before"] != item["archive_sha256_after"] for item in replays.values())
    compile_blocks = sum(not item["verification_report"]["verdict"]["compile_allowed"] for item in replays.values())
    gates = {
        "company_count": len(companies),
        "metric_instance_count": metric_total,
        "metric_signature_coverage_percent": (100.0 * covered / metric_total) if metric_total else 0.0,
        "unknown_executable_ids": diagnostic_counts.get("METRIC_SIGNATURE_COVERAGE_COMPLETE", 0),
        "unresolved_signature_collisions": unresolved_collisions,
        "disambiguated_legacy_aliases": sum(len(values) > 1 for values in legacy_signatures.values()),
        "lossy_decision_roundtrips": decision_losses,
        "changed_canary_archives": changed_archives,
        "compile_blocked_canaries": compile_blocks,
        "blocking_diagnostic_count": sum(diagnostic_counts.values()),
    }
    gates["status"] = "pass" if (
        gates["metric_signature_coverage_percent"] == 100.0
        and gates["unknown_executable_ids"] == 0
        and gates["unresolved_signature_collisions"] == 0
        and gates["lossy_decision_roundtrips"] == 0
        and gates["changed_canary_archives"] == 0
        and gates["compile_blocked_canaries"] == 0
        and gates["blocking_diagnostic_count"] == 0
    ) else "fail"
    return gates
