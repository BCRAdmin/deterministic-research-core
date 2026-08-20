"""End-to-end resolution and verification of the BA11 promotion authority graph."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    AcceptedDebtEvent,
    ArchiveReceipt,
    CanaryFreezeRecord,
    ChangeClassification,
    CompareEngineReceipt,
    ComparisonRequest,
    ComparisonResult,
    DebtLedgerHead,
    GovernanceEnvelope,
    IndependentReviewAttestation,
    OperatorApprovalReceipt,
    PromotionCandidate,
    PromotionEvent,
    RegistryAuthorityGraph,
    RegistryEvent,
    RegistryLedgerHead,
    RegistrySnapshot,
    RegistryTransaction,
    TechnicalBaseline,
)
from .diagnostics import CanaryGovernanceError


@dataclass(frozen=True)
class AuthorityGraphObjects:
    technical_baseline: TechnicalBaseline
    governance_envelope: GovernanceEnvelope
    promotion_candidate: PromotionCandidate
    comparison_request: ComparisonRequest
    compare_engine_receipt: CompareEngineReceipt
    comparison_result: ComparisonResult
    change_classification: ChangeClassification
    registry_events: tuple[RegistryEvent, ...]
    registry_ledger_head: RegistryLedgerHead
    debt_events: tuple[AcceptedDebtEvent, ...]
    debt_ledger_head: DebtLedgerHead
    freeze: CanaryFreezeRecord
    independent_review: IndependentReviewAttestation
    operator_approval: OperatorApprovalReceipt
    snapshot: RegistrySnapshot
    archive_receipt: ArchiveReceipt


def derive_promotion_subjects(
    candidate: PromotionCandidate,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the only approval/review subject set accepted for a promotion."""

    return (candidate.candidate_id,), (candidate.candidate_sha256,)


def verify_comparison_chain(
    request: ComparisonRequest,
    engine_receipt: CompareEngineReceipt,
    result: ComparisonResult,
    classification: ChangeClassification,
) -> None:
    if (
        engine_receipt.request_sha256 != request.request_sha256
        or engine_receipt.baseline_sha256 != request.baseline_sha256
        or engine_receipt.candidate_sha256 != request.candidate_sha256
        or result.request_sha256 != request.request_sha256
        or result.baseline_sha256 != request.baseline_sha256
        or result.candidate_sha256 != request.candidate_sha256
        or result.compare_engine_receipt_sha256 != engine_receipt.receipt_sha256
    ):
        raise CanaryGovernanceError("BA11_COMPARISON_BINDING_MISMATCH")
    result_values = (
        result.verdict,
        result.fact_diff_count,
        result.claim_diff_count,
        result.decision_diff_count,
        result.lineage_diff_count,
        result.diagnostic_codes,
    )
    engine_values = (
        engine_receipt.verdict,
        engine_receipt.fact_diff_count,
        engine_receipt.claim_diff_count,
        engine_receipt.decision_diff_count,
        engine_receipt.lineage_diff_count,
        engine_receipt.diagnostic_codes,
    )
    if result_values != engine_values:
        raise CanaryGovernanceError("BA11_COMPARISON_COUNT_MISMATCH")
    if (
        classification.comparison_request_sha256 != request.request_sha256
        or classification.comparison_result_sha256 != result.result_sha256
        or (
            classification.fact_diff_count,
            classification.claim_diff_count,
            classification.decision_diff_count,
            classification.lineage_diff_count,
        )
        != (
            result.fact_diff_count,
            result.claim_diff_count,
            result.decision_diff_count,
            result.lineage_diff_count,
        )
    ):
        raise CanaryGovernanceError("BA11_COMPARISON_COUNT_MISMATCH")


def build_authority_graph(
    *,
    graph_id: str,
    objects: AuthorityGraphObjects,
    artifact_set_sha256: str,
    finding_set_sha256: str,
    base_registry_head_sha256: str | None,
) -> RegistryAuthorityGraph:
    promotion = _promotion_event(objects.registry_events)
    return RegistryAuthorityGraph.create(
        graph_id=graph_id,
        technical_baseline_sha256=objects.technical_baseline.technical_baseline_sha256,
        governance_envelope_sha256=objects.governance_envelope.governance_envelope_sha256,
        promotion_candidate_sha256=objects.promotion_candidate.candidate_sha256,
        comparison_request_sha256=objects.comparison_request.request_sha256,
        compare_engine_receipt_sha256=objects.compare_engine_receipt.receipt_sha256,
        comparison_result_sha256=objects.comparison_result.result_sha256,
        change_classification_sha256=objects.change_classification.classification_sha256,
        promotion_event_sha256=promotion.event_sha256,
        freeze_sha256=objects.freeze.freeze_sha256,
        independent_review_sha256=objects.independent_review.attestation_sha256,
        operator_approval_sha256=objects.operator_approval.approval_sha256,
        candidate_snapshot_sha256=objects.snapshot.snapshot_sha256,
        registry_event_sha256s=tuple(event.event_sha256 for event in objects.registry_events),
        registry_ledger_head_sha256=objects.registry_ledger_head.head_sha256,
        debt_event_sha256s=tuple(event.event_sha256 for event in objects.debt_events),
        debt_ledger_head_sha256=objects.debt_ledger_head.head_sha256,
        archive_receipt_sha256=objects.archive_receipt.receipt_sha256,
        artifact_set_sha256=artifact_set_sha256,
        finding_set_sha256=finding_set_sha256,
        base_registry_head_sha256=base_registry_head_sha256,
    )


def _promotion_event(events: tuple[RegistryEvent, ...]) -> PromotionEvent:
    promotions = [event for event in events if isinstance(event, PromotionEvent)]
    if len(promotions) != 1:
        raise CanaryGovernanceError("BA11_AUTHORITY_GRAPH_MISMATCH", "promotion_event_count")
    return promotions[0]


def _assert_equal(actual, expected, edge: str) -> None:
    if actual != expected:
        raise CanaryGovernanceError("BA11_AUTHORITY_GRAPH_MISMATCH", edge)


def verify_authority_graph(
    graph: RegistryAuthorityGraph,
    transaction: RegistryTransaction,
    objects: AuthorityGraphObjects,
) -> None:
    """Resolve and verify every normative promotion edge before any store write."""

    verify_comparison_chain(
        objects.comparison_request,
        objects.compare_engine_receipt,
        objects.comparison_result,
        objects.change_classification,
    )
    promotion = _promotion_event(objects.registry_events)
    expected_graph = build_authority_graph(
        graph_id=graph.graph_id,
        objects=objects,
        artifact_set_sha256=graph.artifact_set_sha256,
        finding_set_sha256=graph.finding_set_sha256,
        base_registry_head_sha256=graph.base_registry_head_sha256,
    )
    _assert_equal(graph, expected_graph, "graph_preimage")

    transaction_edges = {
        "candidate_snapshot_sha256": objects.snapshot.snapshot_sha256,
        "registry_ledger_head_sha256": objects.registry_ledger_head.head_sha256,
        "freeze_sha256": objects.freeze.freeze_sha256,
        "comparison_result_sha256": objects.comparison_result.result_sha256,
        "independent_review_sha256": objects.independent_review.attestation_sha256,
        "operator_approval_sha256": objects.operator_approval.approval_sha256,
        "debt_ledger_head_sha256": objects.debt_ledger_head.head_sha256,
        "archive_receipt_sha256": objects.archive_receipt.receipt_sha256,
        "artifact_set_sha256": graph.artifact_set_sha256,
        "authority_graph_sha256": graph.authority_graph_sha256,
        "base_head_sha256": graph.base_registry_head_sha256,
    }
    for field, expected in transaction_edges.items():
        _assert_equal(getattr(transaction, field), expected, f"transaction.{field}")

    candidate = objects.promotion_candidate
    technical = objects.technical_baseline
    governance = objects.governance_envelope
    freeze = objects.freeze
    _assert_equal(candidate.canary_id, technical.canary_id, "candidate.canary")
    _assert_equal(candidate.technical_baseline_sha256, technical.technical_baseline_sha256, "candidate.technical")
    _assert_equal(candidate.comparison_request_sha256, objects.comparison_request.request_sha256, "candidate.request")
    _assert_equal(candidate.comparison_result_sha256, objects.comparison_result.result_sha256, "candidate.result")
    _assert_equal(
        candidate.change_classification_sha256,
        objects.change_classification.classification_sha256,
        "candidate.classification",
    )
    _assert_equal(candidate.base_registry_head_sha256, graph.base_registry_head_sha256 or "0" * 64, "candidate.base_head")
    _assert_equal(objects.comparison_request.candidate_sha256, technical.artifact_set_sha256, "request.candidate_artifact")
    _assert_equal(governance.technical_baseline_sha256, technical.technical_baseline_sha256, "governance.technical")
    _assert_equal(governance.change_classification_sha256, objects.change_classification.classification_sha256, "governance.classification")
    _assert_equal(governance.independent_review_sha256, objects.independent_review.attestation_sha256, "governance.review")
    _assert_equal(governance.operator_approval_sha256, objects.operator_approval.approval_sha256, "governance.approval")
    _assert_equal(governance.previous_registry_head_sha256, graph.base_registry_head_sha256, "governance.base_head")
    _assert_equal(freeze.canary_id, candidate.canary_id, "freeze.canary")
    _assert_equal(freeze.technical_baseline_sha256, technical.technical_baseline_sha256, "freeze.technical")
    _assert_equal(freeze.governance_envelope_sha256, governance.governance_envelope_sha256, "freeze.governance")

    _assert_equal(promotion.canary_id, candidate.canary_id, "promotion.canary")
    _assert_equal(promotion.subject_sha256, candidate.subject_sha256, "promotion.subject")
    _assert_equal(promotion.technical_baseline_sha256, technical.technical_baseline_sha256, "promotion.technical")
    _assert_equal(promotion.governance_envelope_sha256, governance.governance_envelope_sha256, "promotion.governance")
    _assert_equal(promotion.freeze_sha256, freeze.freeze_sha256, "promotion.freeze")
    _assert_equal(promotion.promotion_candidate_sha256, candidate.candidate_sha256, "promotion.candidate")
    _assert_equal(promotion.comparison_result_sha256, objects.comparison_result.result_sha256, "promotion.comparison")
    _assert_equal(promotion.independent_review_sha256, objects.independent_review.attestation_sha256, "promotion.review")
    _assert_equal(promotion.operator_approval_sha256, objects.operator_approval.approval_sha256, "promotion.approval")

    expected_subject_ids, expected_subject_hashes = derive_promotion_subjects(candidate)
    _assert_equal(objects.operator_approval.subject_ids, expected_subject_ids, "approval.subject_ids")
    _assert_equal(objects.operator_approval.subject_sha256s, expected_subject_hashes, "approval.subject_hashes")
    _assert_equal(objects.independent_review.subject_ids, expected_subject_ids, "review.subject_ids")
    _assert_equal(objects.independent_review.subject_sha256s, expected_subject_hashes, "review.subject_hashes")
    _assert_equal(objects.operator_approval.review_finding_set_sha256, graph.finding_set_sha256, "approval.findings")
    _assert_equal(objects.independent_review.finding_set_sha256, graph.finding_set_sha256, "review.findings")
    expected_previous = graph.base_registry_head_sha256 or "0" * 64
    _assert_equal(objects.operator_approval.previous_registry_head_sha256, expected_previous, "approval.base_head")
    _assert_equal(objects.independent_review.previous_registry_head_sha256, expected_previous, "review.base_head")

    _assert_equal(objects.snapshot.ledger_head_sha256, objects.registry_ledger_head.head_sha256, "snapshot.ledger")
    entries = {entry.canary_id: entry for entry in objects.snapshot.entries}
    entry = entries.get(candidate.canary_id)
    if entry is None:
        raise CanaryGovernanceError("BA11_AUTHORITY_GRAPH_MISMATCH", "snapshot.entry")
    _assert_equal(entry.subject_sha256, candidate.subject_sha256, "snapshot.subject")
    _assert_equal(entry.technical_baseline_sha256, technical.technical_baseline_sha256, "snapshot.technical")
    _assert_equal(entry.governance_envelope_sha256, governance.governance_envelope_sha256, "snapshot.governance")
    _assert_equal(entry.freeze_sha256, freeze.freeze_sha256, "snapshot.freeze")
    _assert_equal(objects.archive_receipt.artifact_set_sha256, graph.artifact_set_sha256, "archive.artifact_set")
    _assert_equal(technical.artifact_set_sha256, graph.artifact_set_sha256, "technical.artifact_set")
