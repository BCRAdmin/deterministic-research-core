"""Deterministic, internally cross-bound BA11 R4 test authority graph."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from nacl.signing import SigningKey

from research_agent.canary_governance.approval import (
    TrustedRoleKeyPolicy,
    sign_approval,
    sign_independent_review,
)
from research_agent.canary_governance.authority_graph import (
    AuthorityGraphObjects,
    build_authority_graph,
)
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
    RegistryAuthorityGraph,
    RegistryEvent,
    RegistryTransaction,
    TechnicalBaseline,
    domain_hash,
)
from research_agent.canary_governance.ledger import (
    build_debt_ledger_head,
    build_registry_ledger_head,
    derive_canary_identity,
    ledger_to_snapshot,
)
from research_agent.canary_governance.storage import ContentAddressedRegistryStore

H1, H2, H3, H4, H5, H6, H7, H8 = (str(index) * 64 for index in range(1, 9))
ZERO = "0" * 64
NOW = "2026-08-20T12:00:00Z"


@dataclass(frozen=True)
class R4Fixture:
    store: ContentAddressedRegistryStore
    policy: TrustedRoleKeyPolicy
    graph: RegistryAuthorityGraph
    objects: AuthorityGraphObjects
    transaction: RegistryTransaction

    def commit_kwargs(self) -> dict:
        return {
            "authority_graph": self.graph,
            "authority_objects": self.objects,
            "trusted_role_key_policy": self.policy,
            "revoked_key_ids": set(),
            "fixed_now_utc": NOW,
        }

    def with_objects(self, **changes) -> R4Fixture:
        return replace(self, objects=replace(self.objects, **changes))


def role_keys() -> tuple[TrustedRoleKeyPolicy, SigningKey, SigningKey, SigningKey]:
    operator = SigningKey(bytes.fromhex("01" * 32))
    reviewer = SigningKey(bytes.fromhex("02" * 32))
    research = SigningKey(bytes.fromhex("03" * 32))
    return (
        TrustedRoleKeyPolicy(
            operator_keys={"operator.primary": operator.verify_key},
            reviewer_keys={"reviewer.primary": reviewer.verify_key},
            research_keys={"research.primary": research.verify_key},
        ),
        operator,
        reviewer,
        research,
    )


def _event_values(
    *,
    sequence: int,
    event_type: str,
    previous: str | None,
    canary_id: str,
    normalized_subject: str,
    subject_sha256: str,
    technical_sha256: str,
    governance_sha256: str,
    freeze_sha256: str | None,
) -> dict:
    return {
        "event_id": f"event.r4.{sequence}",
        "canary_id": canary_id,
        "subject_namespace": "company",
        "normalized_subject": normalized_subject,
        "sequence": sequence,
        "event_type": event_type,
        "subject_sha256": subject_sha256,
        "canary_type": "company_regression",
        "baseline_version": "1.0.0",
        "change_class": None,
        "technical_baseline_sha256": technical_sha256,
        "governance_envelope_sha256": governance_sha256,
        "freeze_sha256": freeze_sha256,
        "previous_event_sha256": previous,
        "effective_at_utc": f"2026-08-20T00:00:{sequence:02d}Z",
    }


def make_r4_fixture(root: Path) -> R4Fixture:
    policy, operator_key, reviewer_key, _ = role_keys()
    canary_id, normalized_subject, subject_sha256 = derive_canary_identity("company", "Acme AG")
    technical = TechnicalBaseline.create(
        canary_id=canary_id,
        baseline_version="1.0.0",
        foundation_version_lock_sha256=H1,
        registry_authority_sha256=ZERO,
        semantic_wave_version_lock_sha256=H2,
        ba10_freeze_identity_sha256=H3,
        compiler_artifact_bundle_contract="room16.compiler_artifact_bundle@1",
        source_contract_lock_sha256=H4,
        consumer_semantic_lock_sha256=H5,
        presentation_contract_sha256=H6,
        renderer_artifact_sha256=H7,
        artifact_set_sha256=H8,
        semantic_output_sha256=H1,
    )
    request = ComparisonRequest.create(
        request_id="comparison.r4",
        baseline_sha256=H6,
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
        classification_id="change.r4",
        change_class="governance",
        result=result,
        semantic_lock_changed=True,
        presentation_contract_changed=False,
        renderer_artifact_changed=False,
        source_contract_changed=False,
    )
    candidate = PromotionCandidate.create(
        candidate_id="candidate.r4",
        canary_id=canary_id,
        subject_sha256=subject_sha256,
        technical_baseline_sha256=technical.technical_baseline_sha256,
        comparison_request_sha256=request.request_sha256,
        comparison_result_sha256=result.result_sha256,
        change_classification_sha256=classification.classification_sha256,
        base_registry_head_sha256=ZERO,
    )
    finding_set = H2
    subject_ids = (candidate.candidate_id,)
    subject_hashes = (candidate.candidate_sha256,)
    review = sign_independent_review(
        {
            "review_id": "review.r4",
            "reviewer_key_id": "reviewer.primary",
            "reviewer_role": "independent_architecture_reviewer",
            "scope": "ba11_canary_promotion",
            "subject_ids": subject_ids,
            "subject_sha256s": subject_hashes,
            "finding_set_sha256": finding_set,
            "previous_registry_head_sha256": ZERO,
            "decision": "accepted",
            "nonce": "reviewer-r4-nonce-0001",
            "monotonic_counter": 1,
            "issued_at_utc": "2026-08-20T00:00:00Z",
            "expires_at_utc": "2026-08-21T00:00:00Z",
        },
        reviewer_key,
    )
    approval = sign_approval(
        {
            "approval_id": "approval.r4",
            "decision": "approve",
            "scope": "ba11_canary_promotion",
            "subject_ids": subject_ids,
            "subject_sha256s": subject_hashes,
            "review_finding_set_sha256": finding_set,
            "previous_registry_head_sha256": ZERO,
            "approver_key_id": "operator.primary",
            "issued_at_utc": "2026-08-20T00:00:00Z",
            "expires_at_utc": "2026-08-21T00:00:00Z",
            "nonce": "operator-r4-nonce-0001",
            "monotonic_counter": 1,
        },
        operator_key,
    )
    governance = GovernanceEnvelope.create(
        technical_baseline_sha256=technical.technical_baseline_sha256,
        accepted_debt_set_sha256=domain_hash("room16.canary_accepted_debt_set@1", []),
        change_classification_sha256=classification.classification_sha256,
        independent_review_sha256=review.attestation_sha256,
        operator_approval_sha256=approval.approval_sha256,
        previous_registry_head_sha256=None,
    )
    freeze = CanaryFreezeRecord.create(
        freeze_id="freeze.r4",
        canary_id=canary_id,
        technical_baseline_sha256=technical.technical_baseline_sha256,
        governance_envelope_sha256=governance.governance_envelope_sha256,
        effective_at_utc="2026-08-20T00:00:04Z",
    )

    events: list[RegistryEvent] = []
    previous = None
    for sequence, event_type in enumerate(
        ("genesis", "candidate", "review_accepted", "operator_approved")
    ):
        event = RegistryEvent.create(
            **_event_values(
                sequence=sequence,
                event_type=event_type,
                previous=previous,
                canary_id=canary_id,
                normalized_subject=normalized_subject,
                subject_sha256=subject_sha256,
                technical_sha256=technical.technical_baseline_sha256,
                governance_sha256=governance.governance_envelope_sha256,
                freeze_sha256=None,
            )
        )
        events.append(event)
        previous = event.event_sha256
    promotion = PromotionEvent.create(
        **_event_values(
            sequence=4,
            event_type="frozen",
            previous=previous,
            canary_id=canary_id,
            normalized_subject=normalized_subject,
            subject_sha256=subject_sha256,
            technical_sha256=technical.technical_baseline_sha256,
            governance_sha256=governance.governance_envelope_sha256,
            freeze_sha256=freeze.freeze_sha256,
        ),
        promotion_candidate_sha256=candidate.candidate_sha256,
        comparison_result_sha256=result.result_sha256,
        independent_review_sha256=review.attestation_sha256,
        operator_approval_sha256=approval.approval_sha256,
    )
    events.append(promotion)
    registry_events = tuple(events)
    registry_head = build_registry_ledger_head(
        registry_events, generation=0, previous_head_sha256=None
    )
    snapshot = ledger_to_snapshot(
        registry_events,
        expected_head=registry_head,
        registry_generation=0,
        previous_registry_sha256=None,
    )
    debt_events = ()
    debt_head = build_debt_ledger_head(debt_events, generation=0, previous_head_sha256=None)
    archive = ArchiveReceipt.create(
        archive_content_sha256=H1,
        archive_member_manifest_sha256=H2,
        artifact_set_sha256=technical.artifact_set_sha256,
        source_date_epoch=1787184000,
        retention_class="governance_record",
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
        graph_id="authority.graph.r4",
        objects=objects,
        artifact_set_sha256=technical.artifact_set_sha256,
        finding_set_sha256=finding_set,
        base_registry_head_sha256=None,
    )
    event_set = domain_hash(
        "room16.canary_registry_event_set@1",
        [event.model_dump(mode="json") for event in registry_events],
    )
    transaction = RegistryTransaction.create(
        transaction_id="transaction.r4",
        registry_generation=0,
        base_head_sha256=None,
        candidate_snapshot_sha256=snapshot.snapshot_sha256,
        registry_event_set_sha256=event_set,
        registry_ledger_head_sha256=registry_head.head_sha256,
        freeze_sha256=freeze.freeze_sha256,
        comparison_result_sha256=result.result_sha256,
        independent_review_sha256=review.attestation_sha256,
        operator_approval_sha256=approval.approval_sha256,
        debt_ledger_head_sha256=debt_head.head_sha256,
        archive_receipt_sha256=archive.receipt_sha256,
        artifact_set_sha256=technical.artifact_set_sha256,
        authority_graph_sha256=graph.authority_graph_sha256,
        consumed_nonces=tuple(sorted((approval.nonce, review.nonce))),
        operator_counter=approval.monotonic_counter,
        reviewer_counter=review.monotonic_counter,
    )
    return R4Fixture(
        store=ContentAddressedRegistryStore(root),
        policy=policy,
        graph=graph,
        objects=objects,
        transaction=transaction,
    )
