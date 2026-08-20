"""Strict machine contracts for BA11 R3 canary governance.

All authority records are immutable, reject unknown fields, and use
domain-separated canonical SHA-256 identities. The identity graph is
deliberately acyclic: FreezeCore never references the snapshot containing its
hash; a transaction binds freeze, ledgers and snapshot; the registry head
binds the transaction; and a commit receipt binds the published head.
"""

from __future__ import annotations

import re
from typing import Any, ClassVar, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"
UTC_PATTERN = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
ID_PATTERN = r"^[a-z][a-z0-9_.:-]*$"
SEMVER_PATTERN = r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"


def domain_hash(domain: str, payload: Any) -> str:
    return sha256_json({"domain": domain, "payload": payload})


def complete_model_body(
    model_type: type[StrictModel], values: dict[str, Any], hash_field: str
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    for name, field in model_type.model_fields.items():
        if name == hash_field:
            continue
        if name in values:
            body[name] = values[name]
        elif not field.is_required():
            body[name] = field.get_default(call_default_factory=True)
    body.update({key: value for key, value in values.items() if key != hash_field})
    return body


class HashBoundModel(StrictModel):
    hash_field: ClassVar[str]
    hash_domain: ClassVar[str]

    @classmethod
    def create(cls, **values: Any):
        body = complete_model_body(cls, values, cls.hash_field)
        body[cls.hash_field] = domain_hash(cls.hash_domain, body)
        return cls(**body)

    @model_validator(mode="after")
    def valid_declared_hash(self):
        body = self.model_dump(mode="json", exclude={self.hash_field})
        if domain_hash(self.hash_domain, body) != getattr(self, self.hash_field):
            raise ValueError(f"{self.hash_field} mismatch")
        return self


class SourceContractBinding(HashBoundModel):
    contract_id: Literal["room16.canary.source_contract_binding"] = "room16.canary.source_contract_binding"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    source_contract_id: str = Field(pattern=ID_PATTERN)
    source_contract_sha256: str = Field(pattern=SHA256_PATTERN)
    binding_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "binding_sha256"
    hash_domain = "room16.canary.source_contract_binding@1"


class SourceContractLock(HashBoundModel):
    contract_id: Literal["room16.canary.source_contract_lock"] = "room16.canary.source_contract_lock"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    bindings: tuple[SourceContractBinding, ...]
    lock_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "lock_sha256"
    hash_domain = "room16.canary.source_contract_lock@2"

    @model_validator(mode="after")
    def ordered_sources(self):
        ids = tuple(item.source_contract_id for item in self.bindings)
        hashes = tuple(item.source_contract_sha256 for item in self.bindings)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("source contract bindings must be unique and sorted by id")
        if len(set(hashes)) != len(hashes):
            raise ValueError("source contract id/hash bindings must be bijective")
        return self


class TechnicalBaseline(HashBoundModel):
    contract_id: Literal["room16.canary.technical_baseline"] = "room16.canary.technical_baseline"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    canary_id: str = Field(pattern=ID_PATTERN)
    baseline_version: str = Field(pattern=SEMVER_PATTERN)
    foundation_version_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_authority_sha256: str = Field(pattern=SHA256_PATTERN)
    semantic_wave_version_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    ba10_freeze_identity_sha256: str = Field(pattern=SHA256_PATTERN)
    compiler_artifact_bundle_contract: Literal["room16.compiler_artifact_bundle@1"]
    source_contract_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    consumer_semantic_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    presentation_contract_sha256: str = Field(pattern=SHA256_PATTERN)
    renderer_artifact_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_set_sha256: str = Field(pattern=SHA256_PATTERN)
    semantic_output_sha256: str = Field(pattern=SHA256_PATTERN)
    technical_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "technical_baseline_sha256"
    hash_domain = "room16.canary.technical_baseline@1"


class GovernanceEnvelope(HashBoundModel):
    contract_id: Literal["room16.canary.governance_envelope"] = "room16.canary.governance_envelope"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    technical_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    accepted_debt_set_sha256: str = Field(pattern=SHA256_PATTERN)
    change_classification_sha256: str = Field(pattern=SHA256_PATTERN)
    independent_review_sha256: str = Field(pattern=SHA256_PATTERN)
    operator_approval_sha256: str = Field(pattern=SHA256_PATTERN)
    previous_registry_head_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    governance_envelope_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "governance_envelope_sha256"
    hash_domain = "room16.canary.governance_envelope@1"


class CanaryFreezeRecord(HashBoundModel):
    contract_id: Literal["room16.canary_freeze"] = "room16.canary_freeze"
    schema_version: Literal[2] = 2
    compatibility: Literal["first_contract_no_predecessor"] = "first_contract_no_predecessor"
    authority_owner: Literal["research"] = "research"
    freeze_id: str = Field(pattern=ID_PATTERN)
    canary_id: str = Field(pattern=ID_PATTERN)
    technical_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    governance_envelope_sha256: str = Field(pattern=SHA256_PATTERN)
    effective_at_utc: str = Field(pattern=UTC_PATTERN)
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "freeze_sha256"
    hash_domain = "room16.canary_freeze@2"


CanaryType = Literal["company_regression", "archetype_regression", "technical_release_regression"]


class CanaryRegistryEntry(HashBoundModel):
    contract_id: Literal["room16.canary_registry_entry"] = "room16.canary_registry_entry"
    schema_version: Literal[3] = 3
    authority_owner: Literal["research"] = "research"
    canary_id: str = Field(pattern=ID_PATTERN)
    subject_namespace: str = Field(pattern=ID_PATTERN)
    normalized_subject: str = Field(min_length=1)
    subject_sha256: str = Field(pattern=SHA256_PATTERN)
    canary_type: CanaryType
    baseline_version: str = Field(pattern=SEMVER_PATTERN)
    technical_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    governance_envelope_sha256: str = Field(pattern=SHA256_PATTERN)
    freeze_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    derived_state: Literal["candidate", "frozen", "rejected", "stale", "superseded"]
    latest_event_sha256: str = Field(pattern=SHA256_PATTERN)
    entry_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "entry_sha256"
    hash_domain = "room16.canary_registry_entry@3"

    @model_validator(mode="after")
    def freeze_required_for_promoted_states(self):
        if self.derived_state in {"frozen", "stale", "superseded"} and not self.freeze_sha256:
            raise ValueError("promoted registry states require freeze_sha256")
        return self


class RegistryEvent(HashBoundModel):
    contract_id: Literal["room16.canary_registry_event"] = "room16.canary_registry_event"
    schema_version: Literal[3] = 3
    authority_owner: Literal["research"] = "research"
    event_id: str = Field(pattern=ID_PATTERN)
    canary_id: str = Field(pattern=ID_PATTERN)
    subject_namespace: str = Field(pattern=ID_PATTERN)
    normalized_subject: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    event_type: Literal[
        "genesis", "candidate", "review_accepted", "operator_approved", "frozen",
        "rejected", "stale", "recovered", "superseded"
    ]
    subject_sha256: str = Field(pattern=SHA256_PATTERN)
    canary_type: CanaryType
    baseline_version: str = Field(pattern=SEMVER_PATTERN)
    change_class: Literal["ordinary", "governance", "breaking"] | None = None
    technical_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    governance_envelope_sha256: str = Field(pattern=SHA256_PATTERN)
    freeze_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    previous_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    effective_at_utc: str = Field(pattern=UTC_PATTERN)
    event_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "event_sha256"
    hash_domain = "room16.canary_registry_event@3"


class PromotionEvent(RegistryEvent):
    contract_id: Literal["room16.canary_promotion_event"] = "room16.canary_promotion_event"
    event_type: Literal["frozen"] = "frozen"
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    promotion_candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_result_sha256: str = Field(pattern=SHA256_PATTERN)
    independent_review_sha256: str = Field(pattern=SHA256_PATTERN)
    operator_approval_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_domain = "room16.canary_promotion_event@2"


class RejectionEvent(RegistryEvent):
    contract_id: Literal["room16.canary_rejection_event"] = "room16.canary_rejection_event"
    event_type: Literal["rejected"] = "rejected"
    rejection_reason: str = Field(min_length=1)
    review_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_domain = "room16.canary_rejection_event@2"


class StaleEvent(RegistryEvent):
    contract_id: Literal["room16.canary_stale_event"] = "room16.canary_stale_event"
    event_type: Literal["stale"] = "stale"
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    stale_reason: str = Field(min_length=1)
    detected_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_domain = "room16.canary_stale_event@2"


class RecoveryEvent(RegistryEvent):
    contract_id: Literal["room16.canary_recovery_event"] = "room16.canary_recovery_event"
    event_type: Literal["recovered"] = "recovered"
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    recovery_review_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_domain = "room16.canary_recovery_event@2"


class SupersessionEvent(RegistryEvent):
    contract_id: Literal["room16.canary_supersession_event"] = "room16.canary_supersession_event"
    event_type: Literal["superseded"] = "superseded"
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    superseding_canary_id: str = Field(pattern=ID_PATTERN)
    superseding_freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_domain = "room16.canary_supersession_event@2"


class LedgerHeadPointer(HashBoundModel):
    contract_id: Literal["room16.canary_ledger_head_pointer"] = "room16.canary_ledger_head_pointer"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    ledger_kind: Literal["registry", "debt"]
    head_sha256: str = Field(pattern=SHA256_PATTERN)
    generation: int = Field(ge=0)
    pointer_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "pointer_sha256"
    hash_domain = "room16.canary_ledger_head_pointer@1"


class RegistryLedgerHead(HashBoundModel):
    contract_id: Literal["room16.canary_registry_ledger_head"] = "room16.canary_registry_ledger_head"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    generation: int = Field(ge=0)
    event_count: int = Field(ge=0)
    previous_head_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    current_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    ledger_content_sha256: str = Field(pattern=SHA256_PATTERN)
    head_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "head_sha256"
    hash_domain = "room16.canary_registry_ledger_head@1"


class RegistrySnapshot(HashBoundModel):
    contract_id: Literal["room16.canary_registry_snapshot"] = "room16.canary_registry_snapshot"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    registry_generation: int = Field(ge=0)
    previous_registry_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    ledger_head_sha256: str = Field(pattern=SHA256_PATTERN)
    entries: tuple[CanaryRegistryEntry, ...]
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "snapshot_sha256"
    hash_domain = "room16.canary_registry_snapshot@2"

    @model_validator(mode="after")
    def sorted_entries(self):
        ids = tuple(entry.canary_id for entry in self.entries)
        if ids != tuple(sorted(set(ids))):
            raise ValueError("registry entries must be unique and sorted")
        return self


class RegistryHead(HashBoundModel):
    contract_id: Literal["room16.canary_registry_head"] = "room16.canary_registry_head"
    schema_version: Literal[3] = 3
    authority_owner: Literal["research"] = "research"
    registry_generation: int = Field(ge=0)
    previous_head_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_ledger_head_sha256: str = Field(pattern=SHA256_PATTERN)
    debt_ledger_head_sha256: str = Field(pattern=SHA256_PATTERN)
    transaction_sha256: str = Field(pattern=SHA256_PATTERN)
    authority_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    prepared_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    consumed_nonce_set_sha256: str = Field(pattern=SHA256_PATTERN)
    operator_counter: int = Field(ge=0)
    reviewer_counter: int = Field(ge=0)
    head_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "head_sha256"
    hash_domain = "room16.canary_registry_head@3"


class GenesisImportReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_genesis_import"] = "room16.canary_genesis_import"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    import_id: str = Field(pattern=ID_PATTERN)
    source_records_sha256: str = Field(pattern=SHA256_PATTERN)
    imported_canary_ids: tuple[str, ...]
    target_registry_generation: Literal[0] = 0
    previous_genesis_head_sha256: None = None
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "receipt_sha256"
    hash_domain = "room16.canary_genesis_import@2"

    @model_validator(mode="after")
    def unique_sorted_imports(self):
        if self.imported_canary_ids != tuple(sorted(set(self.imported_canary_ids))):
            raise ValueError("imported canary ids must be unique and sorted")
        return self


class GenesisImportHead(HashBoundModel):
    contract_id: Literal["room16.canary_genesis_import_head"] = "room16.canary_genesis_import_head"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    import_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    head_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "head_sha256"
    hash_domain = "room16.canary_genesis_import_head@1"


class ComparisonRequest(HashBoundModel):
    contract_id: Literal["room16.canary_comparison_request"] = "room16.canary_comparison_request"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    request_id: str = Field(pattern=ID_PATTERN)
    baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    source_contract_lock_sha256: str = Field(pattern=SHA256_PATTERN)
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "request_sha256"
    hash_domain = "room16.canary_comparison_request@1"


class ComparisonResult(HashBoundModel):
    contract_id: Literal["room16.canary_comparison_result"] = "room16.canary_comparison_result"
    schema_version: Literal[3] = 3
    authority_owner: Literal["research"] = "research"
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    compare_engine_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    verdict: Literal["identical", "ordinary_change", "promotion_required", "blocked"]
    fact_diff_count: int = Field(ge=0)
    claim_diff_count: int = Field(ge=0)
    decision_diff_count: int = Field(ge=0)
    lineage_diff_count: int = Field(ge=0)
    diagnostic_codes: tuple[str, ...]
    result_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "result_sha256"
    hash_domain = "room16.canary_comparison_result@3"

    @model_validator(mode="after")
    def verdict_matches_counts(self):
        semantic_diffs = self.fact_diff_count + self.claim_diff_count + self.decision_diff_count + self.lineage_diff_count
        if self.verdict in {"identical", "ordinary_change"} and semantic_diffs:
            raise ValueError("no-new-truth verdict requires zero semantic diffs")
        if self.verdict == "identical" and self.baseline_sha256 != self.candidate_sha256:
            raise ValueError("identical verdict requires identical artifact hashes")
        return self


class ChangeClassification(HashBoundModel):
    contract_id: Literal["room16.canary_change_classification"] = "room16.canary_change_classification"
    schema_version: Literal[3] = 3
    authority_owner: Literal["research"] = "research"
    classification_id: str = Field(pattern=ID_PATTERN)
    change_class: Literal["ordinary", "governance", "breaking"]
    comparison_request_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_result_sha256: str = Field(pattern=SHA256_PATTERN)
    fact_diff_count: int = Field(ge=0)
    claim_diff_count: int = Field(ge=0)
    decision_diff_count: int = Field(ge=0)
    lineage_diff_count: int = Field(ge=0)
    semantic_lock_changed: bool
    presentation_contract_changed: bool
    renderer_artifact_changed: bool
    source_contract_changed: bool
    classification_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "classification_sha256"
    hash_domain = "room16.canary_change_classification@3"

    @model_validator(mode="after")
    def ordinary_is_presentation_only(self):
        if self.change_class == "ordinary" and (
            self.semantic_lock_changed or self.source_contract_changed or self.fact_diff_count
            or self.claim_diff_count or self.decision_diff_count or self.lineage_diff_count
        ):
            raise ValueError("ordinary change must be independently no-new-truth")
        return self

    @classmethod
    def from_comparison(cls, *, classification_id: str, change_class: str, result: ComparisonResult,
                        semantic_lock_changed: bool, presentation_contract_changed: bool,
                        renderer_artifact_changed: bool, source_contract_changed: bool):
        return cls.create(
            classification_id=classification_id, change_class=change_class,
            comparison_request_sha256=result.request_sha256,
            comparison_result_sha256=result.result_sha256,
            fact_diff_count=result.fact_diff_count, claim_diff_count=result.claim_diff_count,
            decision_diff_count=result.decision_diff_count, lineage_diff_count=result.lineage_diff_count,
            semantic_lock_changed=semantic_lock_changed,
            presentation_contract_changed=presentation_contract_changed,
            renderer_artifact_changed=renderer_artifact_changed,
            source_contract_changed=source_contract_changed,
        )


class PromotionCandidate(HashBoundModel):
    contract_id: Literal["room16.canary_promotion_candidate"] = "room16.canary_promotion_candidate"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    candidate_id: str = Field(pattern=ID_PATTERN)
    canary_id: str = Field(pattern=ID_PATTERN)
    subject_sha256: str = Field(pattern=SHA256_PATTERN)
    technical_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_request_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_result_sha256: str = Field(pattern=SHA256_PATTERN)
    change_classification_sha256: str = Field(pattern=SHA256_PATTERN)
    base_registry_head_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "candidate_sha256"
    hash_domain = "room16.canary_promotion_candidate@2"


class CompareEngineReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_compare_engine_receipt"] = "room16.canary_compare_engine_receipt"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    verdict: Literal["identical", "ordinary_change", "promotion_required", "blocked"]
    fact_diff_count: int = Field(ge=0)
    claim_diff_count: int = Field(ge=0)
    decision_diff_count: int = Field(ge=0)
    lineage_diff_count: int = Field(ge=0)
    diagnostic_codes: tuple[str, ...]
    engine_version: str = Field(pattern=SEMVER_PATTERN)
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "receipt_sha256"
    hash_domain = "room16.canary_compare_engine_receipt@1"


class IndependentReviewAttestation(HashBoundModel):
    contract_id: Literal["room16.canary_independent_review_attestation"] = "room16.canary_independent_review_attestation"
    schema_version: Literal[2] = 2
    authority_owner: Literal["external_reviewer"] = "external_reviewer"
    review_id: str = Field(pattern=ID_PATTERN)
    reviewer_key_id: str = Field(pattern=ID_PATTERN)
    reviewer_role: Literal["independent_architecture_reviewer"]
    scope: Literal["ba11_canary_promotion"] = "ba11_canary_promotion"
    subject_ids: tuple[str, ...]
    subject_sha256s: tuple[str, ...]
    finding_set_sha256: str = Field(pattern=SHA256_PATTERN)
    previous_registry_head_sha256: str = Field(pattern=SHA256_PATTERN)
    decision: Literal["accepted", "changes_required"]
    nonce: str = Field(min_length=16)
    monotonic_counter: int = Field(ge=1)
    issued_at_utc: str = Field(pattern=UTC_PATTERN)
    expires_at_utc: str | None = Field(default=None, pattern=UTC_PATTERN)
    signature_algorithm: Literal["ed25519"] = "ed25519"
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")
    attestation_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "attestation_sha256"
    hash_domain = "room16.canary.independent_review_attestation@2"

    @model_validator(mode="after")
    def subject_bijection(self):
        if self.subject_ids != tuple(sorted(set(self.subject_ids))):
            raise ValueError("review subject ids must be unique and sorted")
        if len(self.subject_ids) != len(self.subject_sha256s):
            raise ValueError("review subject ids and hashes must be bijective")
        return self


class OperatorApprovalReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_operator_approval"] = "room16.canary_operator_approval"
    schema_version: Literal[2] = 2
    authority_owner: Literal["operator"] = "operator"
    approval_id: str = Field(pattern=ID_PATTERN)
    decision: Literal["approve", "reject"]
    scope: Literal["ba11_canary_promotion", "ba11_correction_execution"]
    subject_ids: tuple[str, ...]
    subject_sha256s: tuple[str, ...]
    review_finding_set_sha256: str = Field(pattern=SHA256_PATTERN)
    previous_registry_head_sha256: str = Field(pattern=SHA256_PATTERN)
    approver_key_id: str = Field(pattern=ID_PATTERN)
    approver_role: Literal["room16_operator"] = "room16_operator"
    issued_at_utc: str = Field(pattern=UTC_PATTERN)
    expires_at_utc: str | None = Field(default=None, pattern=UTC_PATTERN)
    nonce: str = Field(min_length=16)
    monotonic_counter: int = Field(ge=1)
    signature_algorithm: Literal["ed25519"] = "ed25519"
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")
    approval_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "approval_sha256"
    hash_domain = "room16.canary.operator_approval@2"

    @model_validator(mode="after")
    def subject_bijection(self):
        if self.subject_ids != tuple(sorted(set(self.subject_ids))):
            raise ValueError("approval subject ids must be unique and sorted")
        if len(self.subject_ids) != len(self.subject_sha256s):
            raise ValueError("approval subject ids and hashes must be bijective")
        return self


class AcceptedDebtEvent(HashBoundModel):
    contract_id: Literal["room16.canary_accepted_debt_event"] = "room16.canary_accepted_debt_event"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    debt_id: str = Field(pattern=ID_PATTERN)
    event_id: str = Field(pattern=ID_PATTERN)
    sequence: int = Field(ge=0)
    event_type: Literal["opened", "accepted", "amended", "superseded", "closed"]
    previous_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    finding_id: str
    debt_type: str = Field(pattern=ID_PATTERN)
    scope: str = Field(min_length=1)
    state_before: str | None
    state_after: str
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...]
    approval_receipt_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    recorded_at_utc: str = Field(pattern=UTC_PATTERN)
    event_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "event_sha256"
    hash_domain = "room16.canary_accepted_debt_event@2"


class DebtLedgerHead(HashBoundModel):
    contract_id: Literal["room16.canary_debt_ledger_head"] = "room16.canary_debt_ledger_head"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    generation: int = Field(ge=0)
    event_count: int = Field(ge=0)
    previous_head_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    current_event_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    ledger_content_sha256: str = Field(pattern=SHA256_PATTERN)
    head_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "head_sha256"
    hash_domain = "room16.canary_debt_ledger_head@1"


class DebtMembership(HashBoundModel):
    contract_id: Literal["room16.canary_debt_membership"] = "room16.canary_debt_membership"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    debt_ids: tuple[str, ...]
    accepted_debt_set_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "accepted_debt_set_sha256"
    hash_domain = "room16.canary_accepted_debt_set@1"

    @model_validator(mode="after")
    def sorted_debts(self):
        if self.debt_ids != tuple(sorted(set(self.debt_ids))):
            raise ValueError("debt ids must be unique and sorted")
        return self


class DebtResolution(HashBoundModel):
    contract_id: Literal["room16.canary_debt_resolution"] = "room16.canary_debt_resolution"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    resolution_id: str = Field(pattern=ID_PATTERN)
    debt_id: str = Field(pattern=ID_PATTERN)
    root_cause: str = Field(min_length=1)
    fix_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    review_sha256: str = Field(pattern=SHA256_PATTERN)
    approval_receipt_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    resolved_at_utc: str = Field(pattern=UTC_PATTERN)
    resolution_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "resolution_sha256"
    hash_domain = "room16.canary_debt_resolution@1"


class ArchiveReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_archive_receipt"] = "room16.canary_archive_receipt"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    archive_content_sha256: str = Field(pattern=SHA256_PATTERN)
    archive_contract_version: Literal[1] = 1
    archive_member_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_set_sha256: str = Field(pattern=SHA256_PATTERN)
    source_date_epoch: int = Field(ge=315532800)
    retention_class: Literal["permanent_evidence", "governance_record"]
    supersedes_archive_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "receipt_sha256"
    hash_domain = "room16.canary_archive_receipt@2"


class RegistryAuthorityGraph(HashBoundModel):
    contract_id: Literal["room16.canary_registry_authority_graph"] = "room16.canary_registry_authority_graph"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    graph_id: str = Field(pattern=ID_PATTERN)
    technical_baseline_sha256: str = Field(pattern=SHA256_PATTERN)
    governance_envelope_sha256: str = Field(pattern=SHA256_PATTERN)
    promotion_candidate_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_request_sha256: str = Field(pattern=SHA256_PATTERN)
    compare_engine_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_result_sha256: str = Field(pattern=SHA256_PATTERN)
    change_classification_sha256: str = Field(pattern=SHA256_PATTERN)
    promotion_event_sha256: str = Field(pattern=SHA256_PATTERN)
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    independent_review_sha256: str = Field(pattern=SHA256_PATTERN)
    operator_approval_sha256: str = Field(pattern=SHA256_PATTERN)
    candidate_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_event_sha256s: tuple[str, ...]
    registry_ledger_head_sha256: str = Field(pattern=SHA256_PATTERN)
    debt_event_sha256s: tuple[str, ...]
    debt_ledger_head_sha256: str = Field(pattern=SHA256_PATTERN)
    archive_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_set_sha256: str = Field(pattern=SHA256_PATTERN)
    finding_set_sha256: str = Field(pattern=SHA256_PATTERN)
    base_registry_head_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    authority_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "authority_graph_sha256"
    hash_domain = "room16.canary_registry_authority_graph@1"

    @model_validator(mode="after")
    def ordered_unique_event_sets(self):
        if len(self.registry_event_sha256s) != len(set(self.registry_event_sha256s)):
            raise ValueError("registry event hashes must be unique")
        if len(self.debt_event_sha256s) != len(set(self.debt_event_sha256s)):
            raise ValueError("debt event hashes must be unique")
        return self


class RegistryTransaction(HashBoundModel):
    contract_id: Literal["room16.canary_registry_transaction"] = "room16.canary_registry_transaction"
    schema_version: Literal[3] = 3
    authority_owner: Literal["research"] = "research"
    transaction_id: str = Field(pattern=ID_PATTERN)
    registry_generation: int = Field(ge=0)
    base_head_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    candidate_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_event_set_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_ledger_head_sha256: str = Field(pattern=SHA256_PATTERN)
    freeze_sha256: str = Field(pattern=SHA256_PATTERN)
    comparison_result_sha256: str = Field(pattern=SHA256_PATTERN)
    independent_review_sha256: str = Field(pattern=SHA256_PATTERN)
    operator_approval_sha256: str = Field(pattern=SHA256_PATTERN)
    debt_ledger_head_sha256: str = Field(pattern=SHA256_PATTERN)
    archive_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    artifact_set_sha256: str = Field(pattern=SHA256_PATTERN)
    authority_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    consumed_nonces: tuple[str, ...]
    operator_counter: int = Field(ge=1)
    reviewer_counter: int = Field(ge=1)
    transaction_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "transaction_sha256"
    hash_domain = "room16.canary_registry_transaction@3"

    @model_validator(mode="after")
    def nonces_are_unique_and_sorted(self):
        if self.consumed_nonces != tuple(sorted(set(self.consumed_nonces))):
            raise ValueError("consumed nonces must be unique and sorted")
        return self


class RegistryCommitReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_registry_commit_receipt"] = "room16.canary_registry_commit_receipt"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    transaction_sha256: str = Field(pattern=SHA256_PATTERN)
    published_head_sha256: str = Field(pattern=SHA256_PATTERN)
    authority_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    prepared_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    commit_state: Literal["committed", "recovered"]
    committed_at_utc: str = Field(pattern=UTC_PATTERN)
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "receipt_sha256"
    hash_domain = "room16.canary_registry_commit_receipt@2"


class RegistryPreparedReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_registry_prepared_receipt"] = "room16.canary_registry_prepared_receipt"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    transaction_sha256: str = Field(pattern=SHA256_PATTERN)
    expected_base_head_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    authority_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    prepared_at_utc: str = Field(pattern=UTC_PATTERN)
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "receipt_sha256"
    hash_domain = "room16.canary_registry_prepared_receipt@2"


class MirrorReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_consumer_mirror_receipt"] = "room16.canary_consumer_mirror_receipt"
    schema_version: Literal[2] = 2
    authority_owner: Literal["product_consumer"] = "product_consumer"
    research_authority_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    research_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    mirrored_snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    product_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    receipt_state: Literal["valid", "consumer_mirror_invalid"]
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "receipt_sha256"
    hash_domain = "room16.canary_consumer_mirror_receipt@2"


class ResearchSnapshotAuthorityReceipt(HashBoundModel):
    contract_id: Literal["room16.canary_research_snapshot_authority_receipt"] = "room16.canary_research_snapshot_authority_receipt"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    receipt_id: str = Field(pattern=ID_PATTERN)
    research_key_id: str = Field(pattern=ID_PATTERN)
    research_role: Literal["canary_registry_authority"] = "canary_registry_authority"
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)
    registry_head_sha256: str = Field(pattern=SHA256_PATTERN)
    issued_at_utc: str = Field(pattern=UTC_PATTERN)
    signature_algorithm: Literal["ed25519"] = "ed25519"
    signature: str = Field(pattern=r"^[0-9a-f]{128}$")
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "receipt_sha256"
    hash_domain = "room16.canary.research_snapshot_authority_receipt@1"


class EvidenceManifestEntry(StrictModel):
    path: str = Field(min_length=1)
    bytes: int = Field(ge=0)
    sha256: str = Field(pattern=SHA256_PATTERN)


class EvidenceManifest(HashBoundModel):
    contract_id: Literal["room16.canary_evidence_manifest"] = "room16.canary_evidence_manifest"
    schema_version: Literal[2] = 2
    authority_owner: Literal["research"] = "research"
    payload_rule: Literal["all members except MANIFEST.json"] = "all members except MANIFEST.json"
    manifest_hash_preimage_rule: Literal["canonical JSON of this object without manifest_sha256"] = "canonical JSON of this object without manifest_sha256"
    source_date_epoch: int = Field(ge=315532800)
    files: tuple[EvidenceManifestEntry, ...]
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "manifest_sha256"
    hash_domain = "room16.canary_evidence_manifest@2"

    @model_validator(mode="after")
    def files_are_unique_and_sorted(self):
        names = tuple(item.path for item in self.files)
        if names != tuple(sorted(set(names))) or "MANIFEST.json" in names:
            raise ValueError("manifest payload must be unique, sorted and self-excluding")
        if any(name.startswith("/") or ".." in name.split("/") for name in names):
            raise ValueError("unsafe manifest path")
        return self


class EvidencePackageIdentity(HashBoundModel):
    contract_id: Literal["room16.canary_evidence_package_identity"] = "room16.canary_evidence_package_identity"
    schema_version: Literal[1] = 1
    authority_owner: Literal["research"] = "research"
    package_filename: str = Field(pattern=r"^[A-Za-z0-9_.-]+\.zip$")
    package_bytes: int = Field(gt=0)
    package_sha256: str = Field(pattern=SHA256_PATTERN)
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    detached_sha256_filename: str = Field(pattern=r"^[A-Za-z0-9_.-]+\.zip\.sha256$")
    identity_sha256: str = Field(pattern=SHA256_PATTERN)
    hash_field = "identity_sha256"
    hash_domain = "room16.canary_evidence_package_identity@1"


CONTRACT_MODELS = (
    SourceContractBinding, SourceContractLock, TechnicalBaseline, GovernanceEnvelope,
    CanaryFreezeRecord, CanaryRegistryEntry, RegistryEvent, PromotionEvent,
    RejectionEvent, StaleEvent, RecoveryEvent, SupersessionEvent, RegistryLedgerHead,
    LedgerHeadPointer, RegistrySnapshot, RegistryHead, GenesisImportReceipt, GenesisImportHead,
    ChangeClassification, ComparisonRequest, CompareEngineReceipt, ComparisonResult,
    PromotionCandidate, RegistryAuthorityGraph,
    IndependentReviewAttestation, OperatorApprovalReceipt, AcceptedDebtEvent,
    DebtLedgerHead, DebtMembership, DebtResolution, ArchiveReceipt,
    RegistryTransaction, RegistryPreparedReceipt, RegistryCommitReceipt, MirrorReceipt,
    ResearchSnapshotAuthorityReceipt, EvidenceManifest, EvidencePackageIdentity,
)


def parse_semver(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(SEMVER_PATTERN, value)
    if not match:
        raise ValueError("invalid semantic version")
    return tuple(int(part) for part in match.groups())
