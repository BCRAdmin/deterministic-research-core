"""Persistent-head ledger verification, deterministic IDs and projections."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .contracts import (
    AcceptedDebtEvent,
    CanaryRegistryEntry,
    DebtLedgerHead,
    MirrorReceipt,
    PromotionEvent,
    RecoveryEvent,
    RegistryEvent,
    RegistryLedgerHead,
    RegistrySnapshot,
    RejectionEvent,
    StaleEvent,
    SupersessionEvent,
    domain_hash,
    parse_semver,
)
from .diagnostics import CanaryGovernanceError

GENESIS = {None: {"genesis"}}
TRANSITIONS = {
    "genesis": {"candidate"},
    "candidate": {"review_accepted", "rejected", "stale"},
    "review_accepted": {"operator_approved", "rejected", "stale"},
    "operator_approved": {"frozen", "rejected", "stale"},
    "frozen": {"stale", "superseded"},
    "stale": {"recovered", "superseded", "rejected"},
    "recovered": {"frozen", "stale", "superseded"},
    "rejected": set(),
    "superseded": set(),
}

EVENT_MODEL_BY_TYPE = {
    "frozen": PromotionEvent,
    "rejected": RejectionEvent,
    "stale": StaleEvent,
    "recovered": RecoveryEvent,
    "superseded": SupersessionEvent,
}


def normalize_subject_key(subject_key: str) -> str:
    normalized = unicodedata.normalize("NFC", subject_key)
    normalized = " ".join(normalized.strip().split()).casefold()
    if not normalized:
        raise ValueError("empty normalized subject")
    return normalized


def derive_canary_identity(namespace: str, subject_key: str) -> tuple[str, str, str]:
    if not re.fullmatch(r"[a-z][a-z0-9_.:-]*", namespace):
        raise ValueError("invalid canary namespace")
    normalized = normalize_subject_key(subject_key)
    subject_sha256 = domain_hash("room16.canary_subject@1", normalized)
    digest = domain_hash(
        "room16.canary_id@2",
        {"namespace": namespace, "normalized_subject": normalized, "subject_sha256": subject_sha256},
    )
    return f"canary.{namespace}.{digest[:24]}", normalized, subject_sha256


def derive_canary_id(namespace: str, subject_key: str) -> str:
    return derive_canary_identity(namespace, subject_key)[0]


def assert_no_canary_id_collision(
    namespace: str, subject_key: str, existing_subject_hashes: dict[str, str]
) -> str:
    canary_id, _normalized, subject_sha256 = derive_canary_identity(namespace, subject_key)
    existing = existing_subject_hashes.get(canary_id)
    if existing is not None and existing != subject_sha256:
        raise CanaryGovernanceError("BA11_ID_COLLISION", canary_id)
    return canary_id


def validate_version_transition(
    previous: str | None,
    candidate: str,
    *,
    change_class: str | None = None,
    genesis: bool = False,
) -> None:
    current = parse_semver(candidate)
    if previous is None:
        if not genesis or current != (1, 0, 0):
            raise CanaryGovernanceError("BA11_VERSION_TRANSITION_INVALID", "genesis_requires_1.0.0")
        return
    old = parse_semver(previous)
    expected = {
        "ordinary": (old[0], old[1], old[2] + 1),
        "governance": (old[0], old[1] + 1, 0),
        "breaking": (old[0] + 1, 0, 0),
    }.get(change_class)
    if expected is None or current != expected:
        raise CanaryGovernanceError("BA11_VERSION_TRANSITION_INVALID", str(change_class))


def _verify_chain(
    events: Iterable,
    *,
    hash_attr: str,
    previous_attr: str,
    id_attr: str,
) -> tuple:
    ordered = tuple(events)
    ids: set[str] = set()
    previous_hash = None
    for index, event in enumerate(ordered):
        event_id = getattr(event, id_attr)
        if event_id in ids:
            raise CanaryGovernanceError("BA11_DUPLICATE_ID", event_id)
        ids.add(event_id)
        if event.sequence != index or getattr(event, previous_attr) != previous_hash:
            raise CanaryGovernanceError("BA11_EVENT_CHAIN_BROKEN", event_id)
        previous_hash = getattr(event, hash_attr)
    return ordered


def _ledger_content_sha256(domain: str, ordered: tuple) -> str:
    return domain_hash(domain, [event.model_dump(mode="json") for event in ordered])


def build_registry_ledger_head(
    events: Iterable[RegistryEvent],
    *,
    generation: int,
    previous_head_sha256: str | None,
) -> RegistryLedgerHead:
    ordered = _verify_chain(
        events, hash_attr="event_sha256", previous_attr="previous_event_sha256", id_attr="event_id"
    )
    return RegistryLedgerHead.create(
        generation=generation,
        event_count=len(ordered),
        previous_head_sha256=previous_head_sha256,
        current_event_sha256=ordered[-1].event_sha256 if ordered else None,
        ledger_content_sha256=_ledger_content_sha256("room16.canary_registry_ledger_content@1", ordered),
    )


def _assert_registry_head(ordered: tuple, expected_head: RegistryLedgerHead) -> None:
    actual = build_registry_ledger_head(
        ordered,
        generation=expected_head.generation,
        previous_head_sha256=expected_head.previous_head_sha256,
    )
    if actual != expected_head:
        raise CanaryGovernanceError("BA11_LEDGER_ROLLBACK", "registry")


def fold_registry_events(
    events: Iterable[RegistryEvent], *, expected_head: RegistryLedgerHead
) -> dict[str, str]:
    ordered = _verify_chain(
        events, hash_attr="event_sha256", previous_attr="previous_event_sha256", id_attr="event_id"
    )
    _assert_registry_head(ordered, expected_head)
    states: dict[str, str] = {}
    for event in ordered:
        required_model = EVENT_MODEL_BY_TYPE.get(event.event_type)
        if required_model and not isinstance(event, required_model):
            raise CanaryGovernanceError("BA11_SCHEMA_INVALID", f"{event.event_type}_record")
        previous_state = states.get(event.canary_id)
        allowed = GENESIS[None] if previous_state is None else TRANSITIONS[previous_state]
        if event.event_type not in allowed:
            raise CanaryGovernanceError(
                "BA11_EVENT_TRANSITION_INVALID", f"{previous_state}->{event.event_type}"
            )
        states[event.canary_id] = event.event_type
    return states


def ledger_to_snapshot(
    events: Iterable[RegistryEvent],
    *,
    expected_head: RegistryLedgerHead,
    registry_generation: int,
    previous_registry_sha256: str | None,
) -> RegistrySnapshot:
    ordered = tuple(events)
    states = fold_registry_events(ordered, expected_head=expected_head)
    latest: dict[str, RegistryEvent] = {}
    for event in ordered:
        latest[event.canary_id] = event
    projection = {
        "genesis": "candidate",
        "candidate": "candidate",
        "review_accepted": "candidate",
        "operator_approved": "candidate",
        "frozen": "frozen",
        "rejected": "rejected",
        "stale": "stale",
        "recovered": "stale",
        "superseded": "superseded",
    }
    entries = []
    for canary_id in sorted(latest):
        event = latest[canary_id]
        entries.append(
            CanaryRegistryEntry.create(
                canary_id=canary_id,
                canary_type=event.canary_type,
                baseline_version=event.baseline_version,
                technical_baseline_sha256=event.technical_baseline_sha256,
                governance_envelope_sha256=event.governance_envelope_sha256,
                freeze_sha256=event.freeze_sha256,
                derived_state=projection[states[canary_id]],
                latest_event_sha256=event.event_sha256,
            )
        )
    return RegistrySnapshot.create(
        registry_generation=registry_generation,
        previous_registry_sha256=previous_registry_sha256,
        ledger_head_sha256=expected_head.head_sha256,
        entries=tuple(entries),
    )


def verify_derived_snapshot(
    snapshot: RegistrySnapshot,
    events: Iterable[RegistryEvent],
    *,
    expected_head: RegistryLedgerHead,
) -> None:
    derived = ledger_to_snapshot(
        events,
        expected_head=expected_head,
        registry_generation=snapshot.registry_generation,
        previous_registry_sha256=snapshot.previous_registry_sha256,
    )
    if derived != snapshot:
        raise CanaryGovernanceError("BA11_SNAPSHOT_NOT_DERIVED")


def build_debt_ledger_head(
    events: Iterable[AcceptedDebtEvent],
    *,
    generation: int,
    previous_head_sha256: str | None,
) -> DebtLedgerHead:
    ordered = _verify_chain(
        events, hash_attr="event_sha256", previous_attr="previous_event_sha256", id_attr="event_id"
    )
    return DebtLedgerHead.create(
        generation=generation,
        event_count=len(ordered),
        previous_head_sha256=previous_head_sha256,
        current_event_sha256=ordered[-1].event_sha256 if ordered else None,
        ledger_content_sha256=_ledger_content_sha256("room16.canary_debt_ledger_content@1", ordered),
    )


def verify_debt_ledger(
    events: Iterable[AcceptedDebtEvent],
    *,
    expected_head: DebtLedgerHead,
    authentic_approval_sha256s: set[str],
) -> dict[str, str]:
    ordered = _verify_chain(
        events, hash_attr="event_sha256", previous_attr="previous_event_sha256", id_attr="event_id"
    )
    actual = build_debt_ledger_head(
        ordered,
        generation=expected_head.generation,
        previous_head_sha256=expected_head.previous_head_sha256,
    )
    if actual != expected_head:
        raise CanaryGovernanceError("BA11_LEDGER_ROLLBACK", "debt")
    states: dict[str, str] = {}
    allowed = {
        None: {"opened"},
        "opened": {"accepted", "amended", "closed"},
        "accepted": {"amended", "superseded", "closed"},
        "amended": {"amended", "accepted", "superseded", "closed"},
        "superseded": set(),
        "closed": set(),
    }
    for event in ordered:
        current = states.get(event.debt_id)
        if event.event_type not in allowed[current] or event.state_before != current:
            raise CanaryGovernanceError("BA11_DEBT_CHAIN_BROKEN", event.event_id)
        if event.state_after != event.event_type:
            raise CanaryGovernanceError("BA11_DEBT_CHAIN_BROKEN", "state_after")
        if event.event_type == "accepted" and (
            not event.approval_receipt_sha256
            or event.approval_receipt_sha256 not in authentic_approval_sha256s
        ):
            raise CanaryGovernanceError("BA11_DEBT_APPROVAL_REQUIRED", event.event_id)
        states[event.debt_id] = event.state_after
    return states


def mirror_receipt(
    *,
    research_authority_receipt_sha256: str,
    research_snapshot_sha256: str,
    mirrored_snapshot_sha256: str,
    product_commit: str,
) -> MirrorReceipt:
    state = "valid" if research_snapshot_sha256 == mirrored_snapshot_sha256 else "consumer_mirror_invalid"
    return MirrorReceipt.create(
        research_authority_receipt_sha256=research_authority_receipt_sha256,
        research_snapshot_sha256=research_snapshot_sha256,
        mirrored_snapshot_sha256=mirrored_snapshot_sha256,
        product_commit=product_commit,
        receipt_state=state,
    )
