"""Stable BA11 fail-closed diagnostic registry."""

DIAGNOSTICS = {
    "BA11_APPROVAL_EXPIRED": "Approval validity window has ended.",
    "BA11_APPROVAL_REPLAY": "Approval nonce or counter was already consumed.",
    "BA11_APPROVAL_REVOKED": "Approval key is revoked.",
    "BA11_APPROVAL_SCOPE": "Approval does not bind the required scope or subjects.",
    "BA11_APPROVAL_SIGNATURE": "Approval signature is invalid.",
    "BA11_ARCHIVE_MUTATION": "Archive identity was reused with different bytes.",
    "BA11_CONSUMER_MIRROR_INVALID": "Product mirror differs from Research authority.",
    "BA11_DEBT_CHAIN_BROKEN": "Accepted-debt event chain is incomplete or mutated.",
    "BA11_DUPLICATE_ID": "A governance identifier is duplicated.",
    "BA11_EVENT_CHAIN_BROKEN": "Registry event chain is incomplete or mutated.",
    "BA11_EVENT_TRANSITION_INVALID": "Registry event transition is invalid.",
    "BA11_FREEZE_LOCK_DRIFT": "A frozen BA0-BA10 authority lock differs.",
    "BA11_HASH_MISMATCH": "A declared content hash differs from canonical bytes.",
    "BA11_REGISTRY_CAS_CONFLICT": "Registry head changed since candidate preparation.",
    "BA11_REGISTRY_GENERATION_INVALID": "Registry generation is not monotonic by one.",
    "BA11_REGISTRY_PREDECESSOR_INVALID": "Registry snapshot does not extend the current snapshot.",
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
