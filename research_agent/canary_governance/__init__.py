"""BA11 additive canary-governance contracts and fail-closed runtime."""

from .approval import (
    TrustedRoleKeyPolicy,
    sign_approval,
    sign_independent_review,
    sign_research_snapshot_receipt,
    verify_approval,
    verify_independent_review,
    verify_research_snapshot_receipt,
)
from .archive import FixedClock, build_deterministic_zip, build_package_identity
from .contracts import CONTRACT_MODELS
from .ledger import (
    build_debt_ledger_head,
    build_registry_ledger_head,
    derive_canary_id,
    fold_registry_events,
    ledger_to_snapshot,
    verify_debt_ledger,
)
from .storage import ContentAddressedRegistryStore

__all__ = [
    "CONTRACT_MODELS",
    "ContentAddressedRegistryStore",
    "FixedClock",
    "TrustedRoleKeyPolicy",
    "build_debt_ledger_head",
    "build_deterministic_zip",
    "build_package_identity",
    "build_registry_ledger_head",
    "derive_canary_id",
    "fold_registry_events",
    "ledger_to_snapshot",
    "sign_approval",
    "sign_independent_review",
    "sign_research_snapshot_receipt",
    "verify_approval",
    "verify_debt_ledger",
    "verify_independent_review",
    "verify_research_snapshot_receipt",
]
