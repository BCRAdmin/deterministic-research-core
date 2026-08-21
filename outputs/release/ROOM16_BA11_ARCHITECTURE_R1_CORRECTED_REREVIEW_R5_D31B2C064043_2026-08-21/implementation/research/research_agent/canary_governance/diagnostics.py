"""Stable BA11 fail-closed diagnostic registry."""

DIAGNOSTICS = {
    "BA11_APPROVAL_EXPIRED": "Approval validity window has ended.",
    "BA11_APPROVAL_REPLAY": "Approval nonce or counter was already consumed.",
    "BA11_APPROVAL_REVOKED": "Approval key is revoked.",
    "BA11_APPROVAL_SCOPE": "Approval does not bind the required scope or subjects.",
    "BA11_APPROVAL_SIGNATURE": "Approval signature is invalid.",
    "BA11_APPROVAL_DECISION": "Approval decision does not authorize the requested operation.",
    "BA11_APPROVAL_SUBJECT": "Approval subject IDs or hashes differ from the expected subjects.",
    "BA11_APPROVAL_FINDING_SET": "Approval does not bind the expected review finding set.",
    "BA11_APPROVAL_PREVIOUS_HEAD": "Approval does not bind the expected previous registry head.",
    "BA11_ATTESTATION_EXPIRED": "Independent review validity window has ended.",
    "BA11_ATTESTATION_REPLAY": "Independent review nonce or counter was already consumed.",
    "BA11_ATTESTATION_REVOKED": "Independent reviewer key is revoked.",
    "BA11_ATTESTATION_SCOPE": "Independent review does not bind the required scope.",
    "BA11_ATTESTATION_SIGNATURE": "Independent review signature is invalid.",
    "BA11_ATTESTATION_DECISION": "Independent review decision does not authorize promotion.",
    "BA11_ATTESTATION_SUBJECT": "Independent review subjects differ from the expected subjects.",
    "BA11_ATTESTATION_FINDING_SET": "Independent review finding set differs from the expected set.",
    "BA11_ATTESTATION_PREVIOUS_HEAD": "Independent review does not bind the expected registry head.",
    "BA11_REVIEWER_NOT_INDEPENDENT": "Reviewer key overlaps Research or Operator trust roles.",
    "BA11_ROLE_KEY_OVERLAP": "Operator, reviewer and Research key IDs and bytes must be pairwise disjoint.",
    "BA11_ARCHIVE_MUTATION": "Archive identity was reused with different bytes.",
    "BA11_CONSUMER_MIRROR_INVALID": "Product mirror differs from Research authority.",
    "BA11_DEBT_CHAIN_BROKEN": "Accepted-debt event chain is incomplete or mutated.",
    "BA11_DEBT_APPROVAL_REQUIRED": "Accepted debt lacks an authentic approval binding.",
    "BA11_DEBT_TRANSITION_INVALID": "Accepted-debt state transition is invalid.",
    "BA11_LEDGER_OBJECT_MISSING": "An immutable ledger head or event object is missing.",
    "BA11_LEDGER_ROLLBACK": "Ledger bytes do not match the required persistent authority head.",
    "BA11_LEDGER_FORK": "Ledger append does not extend the exact current head.",
    "BA11_DUPLICATE_ID": "A governance identifier is duplicated.",
    "BA11_EVENT_CHAIN_BROKEN": "Registry event chain is incomplete or mutated.",
    "BA11_EVENT_TRANSITION_INVALID": "Registry event transition is invalid.",
    "BA11_EVENT_CONTRACT_INVALID": "Registry event does not use its required specialized contract.",
    "BA11_FREEZE_LOCK_DRIFT": "A frozen BA0-BA10 authority lock differs.",
    "BA11_HASH_MISMATCH": "A declared content hash differs from canonical bytes.",
    "BA11_ID_COLLISION": "A shortened canary ID collides with a different normalized subject.",
    "BA11_CANARY_SUBJECT_MISMATCH": "A canary identifier changed its canonical subject identity.",
    "BA11_GENESIS_ALREADY_IMPORTED": "The one-time genesis import head already exists.",
    "BA11_REGISTRY_CAS_CONFLICT": "Registry head changed since candidate preparation.",
    "BA11_REGISTRY_ROLLBACK": "Registry current head is not the latest reachable published authority.",
    "BA11_REGISTRY_GENERATION_INVALID": "Registry generation is not monotonic by one.",
    "BA11_REGISTRY_PREDECESSOR_INVALID": "Registry snapshot does not extend the current snapshot.",
    "BA11_SNAPSHOT_NOT_DERIVED": "Registry snapshot is not the normative projection of its ledger.",
    "BA11_TRANSACTION_BINDING_INVALID": "Registry transaction does not bind the supplied authority graph.",
    "BA11_TRANSACTION_EVENT_AUTHORITY_MISSING": "Transaction event authority is not immutably persisted.",
    "BA11_TRANSACTION_RECOVERY_INVALID": "A prepared or swapped transaction cannot be recovered unambiguously.",
    "BA11_RECOVERY_GRAPH_INCOMPLETE": "Recovery authority graph is missing or incomplete.",
    "BA11_AUTHORITY_GRAPH_MISMATCH": "An authority graph edge does not resolve to the exact supplied object.",
    "BA11_COMPARISON_BINDING_MISMATCH": "Comparison request, result and candidate bindings differ.",
    "BA11_COMPARISON_COUNT_MISMATCH": "Comparison counts differ from the compare-engine receipt.",
    "BA11_ACCEPTANCE_REQUIREMENT_MISSING": "An authoritative acceptance requirement is missing.",
    "BA11_TEST_ID_UNRESOLVED": "An acceptance requirement references no exact source test.",
    "BA11_ACCEPTANCE_MAPPING_AMBIGUOUS": "Acceptance requirement coverage is generic or ambiguous.",
    "BA11_SELF_CERTIFICATION_FORBIDDEN": "Evidence collector attempted to certify its own closure.",
    "BA11_NONCE_COUNTER_CONFLICT": "Approval/review nonce or counter is stale at atomic commit time.",
    "BA11_RESEARCH_AUTHORITY_UNTRUSTED": "Product mirror lacks a trusted Research authority receipt.",
    "BA11_SCHEMA_INVALID": "A governance payload violates its strict schema.",
    "BA11_SOURCE_CONTRACT_DRIFT": "Required source-contract lock differs.",
    "BA11_VERSION_TRANSITION_INVALID": "Baseline SemVer transition is invalid.",
}


class CanaryGovernanceError(RuntimeError):
    """Fail-closed BA11 error carrying a stable diagnostic code."""

    def __init__(self, code: str, detail: str = "") -> None:
        if code not in DIAGNOSTICS:
            raise ValueError(f"unregistered diagnostic: {code}")
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}" if detail else code)
