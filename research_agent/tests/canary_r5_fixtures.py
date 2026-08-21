"""Deterministic multi-generation fixtures for the BA11 R5 closure."""

from __future__ import annotations

from dataclasses import replace

from research_agent.canary_governance.approval import sign_approval, sign_independent_review
from research_agent.canary_governance.authority_graph import AuthorityGraphObjects, build_authority_graph
from research_agent.canary_governance.contracts import (
    ArchiveReceipt,
    CanaryFreezeRecord,
    ChangeClassification,
    CompareEngineReceipt,
    ComparisonRequest,
    ComparisonResult,
    GovernanceEnvelope,
    PromotionCandidate,
    PromotionEvent,
    RegistryEvent,
    RegistryTransaction,
    TechnicalBaseline,
    domain_hash,
)
from research_agent.canary_governance.ledger import (
    build_debt_ledger_head,
    build_registry_ledger_head,
    ledger_to_snapshot,
)
from research_agent.tests.canary_r4_fixtures import H1, H2, H3, H4, H5, H6, H7, H8, R4Fixture, role_keys


def _event_values(
    prior: R4Fixture,
    *,
    sequence: int,
    suffix: str,
    event_type: str,
    version: str,
    change_class: str,
    technical_sha256: str,
    governance_sha256: str,
    freeze_sha256: str | None,
) -> dict:
    previous = prior.objects.registry_events[-1]
    return {
        "event_id": f"event.r5.{suffix}.{sequence}",
        "canary_id": previous.canary_id,
        "subject_namespace": previous.subject_namespace,
        "normalized_subject": previous.normalized_subject,
        "sequence": sequence,
        "event_type": event_type,
        "subject_sha256": previous.subject_sha256,
        "canary_type": previous.canary_type,
        "baseline_version": version,
        "change_class": change_class,
        "technical_baseline_sha256": technical_sha256,
        "governance_envelope_sha256": governance_sha256,
        "freeze_sha256": freeze_sha256,
        "previous_event_sha256": None,
        "effective_at_utc": f"2026-08-21T00:{sequence:02d}:00Z",
    }


def make_next_cycle(
    prior: R4Fixture,
    *,
    suffix: str,
    version: str,
    generation: int,
    base_head_sha256: str,
    previous_snapshot_sha256: str,
) -> R4Fixture:
    """Build one valid governance promotion over the complete prior history."""

    policy, operator_key, reviewer_key, _ = role_keys()
    previous = prior.objects.registry_events[-1]
    technical = TechnicalBaseline.create(
        canary_id=previous.canary_id,
        baseline_version=version,
        foundation_version_lock_sha256=H1,
        registry_authority_sha256=base_head_sha256,
        semantic_wave_version_lock_sha256=H2,
        ba10_freeze_identity_sha256=H3,
        compiler_artifact_bundle_contract="room16.compiler_artifact_bundle@1",
        source_contract_lock_sha256=H4,
        consumer_semantic_lock_sha256=H5,
        presentation_contract_sha256=H6,
        renderer_artifact_sha256=H7,
        artifact_set_sha256=domain_hash("room16.r5.artifact_set@1", suffix),
        semantic_output_sha256=domain_hash("room16.r5.semantic_output@1", suffix),
    )
    request = ComparisonRequest.create(
        request_id=f"comparison.r5.{suffix}",
        baseline_sha256=prior.objects.technical_baseline.artifact_set_sha256,
        candidate_sha256=technical.artifact_set_sha256,
        source_contract_lock_sha256=technical.source_contract_lock_sha256,
    )
    engine = CompareEngineReceipt.create(
        request_sha256=request.request_sha256,
        baseline_sha256=request.baseline_sha256,
        candidate_sha256=request.candidate_sha256,
        verdict="promotion_required",
        fact_diff_count=1,
        claim_diff_count=0,
        decision_diff_count=0,
        lineage_diff_count=0,
        diagnostic_codes=(),
        engine_version="1.0.0",
    )
    result = ComparisonResult.create(
        request_sha256=request.request_sha256,
        baseline_sha256=request.baseline_sha256,
        candidate_sha256=request.candidate_sha256,
        compare_engine_receipt_sha256=engine.receipt_sha256,
        verdict=engine.verdict,
        fact_diff_count=engine.fact_diff_count,
        claim_diff_count=engine.claim_diff_count,
        decision_diff_count=engine.decision_diff_count,
        lineage_diff_count=engine.lineage_diff_count,
        diagnostic_codes=engine.diagnostic_codes,
    )
    classification = ChangeClassification.from_comparison(
        classification_id=f"change.r5.{suffix}",
        change_class="governance",
        result=result,
        semantic_lock_changed=True,
        presentation_contract_changed=False,
        renderer_artifact_changed=False,
        source_contract_changed=False,
    )
    candidate = PromotionCandidate.create(
        candidate_id=f"candidate.r5.{suffix}",
        canary_id=previous.canary_id,
        subject_sha256=previous.subject_sha256,
        technical_baseline_sha256=technical.technical_baseline_sha256,
        comparison_request_sha256=request.request_sha256,
        comparison_result_sha256=result.result_sha256,
        change_classification_sha256=classification.classification_sha256,
        base_registry_head_sha256=base_head_sha256,
    )
    finding_set = domain_hash("room16.r5.finding_set@1", suffix)
    subject_ids = (candidate.candidate_id,)
    subject_hashes = (candidate.candidate_sha256,)
    review = sign_independent_review(
        {
            "review_id": f"review.r5.{suffix}",
            "reviewer_key_id": "reviewer.primary",
            "reviewer_role": "independent_architecture_reviewer",
            "scope": "ba11_canary_promotion",
            "subject_ids": subject_ids,
            "subject_sha256s": subject_hashes,
            "finding_set_sha256": finding_set,
            "previous_registry_head_sha256": base_head_sha256,
            "decision": "accepted",
            "nonce": f"reviewer-r5-{suffix}-nonce",
            "monotonic_counter": generation + 1,
            "issued_at_utc": "2026-08-20T00:00:00Z",
            "expires_at_utc": "2026-08-22T00:00:00Z",
        },
        reviewer_key,
    )
    approval = sign_approval(
        {
            "approval_id": f"approval.r5.{suffix}",
            "decision": "approve",
            "scope": "ba11_canary_promotion",
            "subject_ids": subject_ids,
            "subject_sha256s": subject_hashes,
            "review_finding_set_sha256": finding_set,
            "previous_registry_head_sha256": base_head_sha256,
            "approver_key_id": "operator.primary",
            "issued_at_utc": "2026-08-20T00:00:00Z",
            "expires_at_utc": "2026-08-22T00:00:00Z",
            "nonce": f"operator-r5-{suffix}-nonce",
            "monotonic_counter": generation + 1,
        },
        operator_key,
    )
    governance = GovernanceEnvelope.create(
        technical_baseline_sha256=technical.technical_baseline_sha256,
        accepted_debt_set_sha256=domain_hash("room16.canary_accepted_debt_set@1", []),
        change_classification_sha256=classification.classification_sha256,
        independent_review_sha256=review.attestation_sha256,
        operator_approval_sha256=approval.approval_sha256,
        previous_registry_head_sha256=base_head_sha256,
    )
    freeze = CanaryFreezeRecord.create(
        freeze_id=f"freeze.r5.{suffix}",
        canary_id=previous.canary_id,
        technical_baseline_sha256=technical.technical_baseline_sha256,
        governance_envelope_sha256=governance.governance_envelope_sha256,
        effective_at_utc="2026-08-21T00:10:00Z",
    )
    events = list(prior.objects.registry_events)
    for event_type in ("candidate", "review_accepted", "operator_approved"):
        values = _event_values(
            prior,
            sequence=len(events),
            suffix=suffix,
            event_type=event_type,
            version=version,
            change_class="governance",
            technical_sha256=technical.technical_baseline_sha256,
            governance_sha256=governance.governance_envelope_sha256,
            freeze_sha256=None,
        )
        values["previous_event_sha256"] = events[-1].event_sha256
        events.append(RegistryEvent.create(**values))
    values = _event_values(
        prior,
        sequence=len(events),
        suffix=suffix,
        event_type="frozen",
        version=version,
        change_class="governance",
        technical_sha256=technical.technical_baseline_sha256,
        governance_sha256=governance.governance_envelope_sha256,
        freeze_sha256=freeze.freeze_sha256,
    )
    values["previous_event_sha256"] = events[-1].event_sha256
    events.append(
        PromotionEvent.create(
            **values,
            promotion_candidate_sha256=candidate.candidate_sha256,
            comparison_result_sha256=result.result_sha256,
            independent_review_sha256=review.attestation_sha256,
            operator_approval_sha256=approval.approval_sha256,
        )
    )
    registry_events = tuple(events)
    registry_head = build_registry_ledger_head(
        registry_events,
        generation=prior.objects.registry_ledger_head.generation + 1,
        previous_head_sha256=prior.objects.registry_ledger_head.head_sha256,
    )
    snapshot = ledger_to_snapshot(
        registry_events,
        expected_head=registry_head,
        registry_generation=generation,
        previous_registry_sha256=previous_snapshot_sha256,
    )
    debt_events = prior.objects.debt_events
    debt_head = build_debt_ledger_head(
        debt_events,
        generation=prior.objects.debt_ledger_head.generation + 1,
        previous_head_sha256=prior.objects.debt_ledger_head.head_sha256,
    )
    archive = ArchiveReceipt.create(
        archive_content_sha256=domain_hash("room16.r5.archive@1", suffix),
        archive_member_manifest_sha256=H2,
        artifact_set_sha256=technical.artifact_set_sha256,
        source_date_epoch=1787270400,
        retention_class="governance_record",
        supersedes_archive_sha256=prior.objects.archive_receipt.receipt_sha256,
    )
    objects = AuthorityGraphObjects(
        technical_baseline=technical,
        governance_envelope=governance,
        promotion_candidate=candidate,
        comparison_request=request,
        compare_engine_receipt=engine,
        comparison_result=result,
        change_classification=classification,
        registry_events=registry_events,
        registry_ledger_head=registry_head,
        debt_events=debt_events,
        debt_ledger_head=debt_head,
        freeze=freeze,
        independent_review=review,
        operator_approval=approval,
        snapshot=snapshot,
        archive_receipt=archive,
    )
    graph = build_authority_graph(
        graph_id=f"authority.graph.r5.{suffix}",
        objects=objects,
        artifact_set_sha256=technical.artifact_set_sha256,
        finding_set_sha256=finding_set,
        base_registry_head_sha256=base_head_sha256,
    )
    transaction = RegistryTransaction.create(
        transaction_id=f"transaction.r5.{suffix}",
        registry_generation=generation,
        base_head_sha256=base_head_sha256,
        candidate_snapshot_sha256=snapshot.snapshot_sha256,
        registry_event_set_sha256=domain_hash(
            "room16.canary_registry_event_set@1",
            [event.model_dump(mode="json") for event in registry_events],
        ),
        registry_ledger_head_sha256=registry_head.head_sha256,
        freeze_sha256=freeze.freeze_sha256,
        comparison_result_sha256=result.result_sha256,
        independent_review_sha256=review.attestation_sha256,
        operator_approval_sha256=approval.approval_sha256,
        debt_ledger_head_sha256=debt_head.head_sha256,
        archive_receipt_sha256=archive.receipt_sha256,
        artifact_set_sha256=technical.artifact_set_sha256,
        authority_graph_sha256=graph.authority_graph_sha256,
        consumed_nonces=tuple(
            sorted((*prior.transaction.consumed_nonces, approval.nonce, review.nonce))
        ),
        operator_counter=approval.monotonic_counter,
        reviewer_counter=review.monotonic_counter,
    )
    return replace(prior, policy=policy, graph=graph, objects=objects, transaction=transaction)
