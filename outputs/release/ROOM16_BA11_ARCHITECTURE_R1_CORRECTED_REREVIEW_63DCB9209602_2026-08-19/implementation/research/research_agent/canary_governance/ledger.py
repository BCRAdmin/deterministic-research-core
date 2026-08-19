"""Append-only registry/debt folds, deterministic IDs, and mirror separation."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .contracts import (
    AcceptedDebtEvent,
    MirrorReceipt,
    RegistryEvent,
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


def derive_canary_id(namespace: str, subject_key: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_.:-]*", namespace):
        raise ValueError("invalid canary namespace")
    digest = domain_hash("room16.canary_id@1", {"namespace": namespace, "subject": subject_key})
    return f"canary.{namespace}.{digest[:24]}"


def validate_version_transition(previous: str | None, candidate: str, *, genesis: bool = False) -> None:
    current = parse_semver(candidate)
    if previous is None:
        if not genesis or current != (1, 0, 0):
            raise CanaryGovernanceError("BA11_VERSION_TRANSITION_INVALID", "genesis_requires_1.0.0")
        return
    old = parse_semver(previous)
    allowed = {
        (old[0], old[1], old[2] + 1),
        (old[0], old[1] + 1, 0),
        (old[0] + 1, 0, 0),
    }
    if current not in allowed:
        raise CanaryGovernanceError("BA11_VERSION_TRANSITION_INVALID")


def _verify_chain(events: Iterable, *, hash_attr: str, previous_attr: str, id_attr: str) -> tuple:
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


def fold_registry_events(events: Iterable[RegistryEvent]) -> dict[str, str]:
    ordered = _verify_chain(
        events, hash_attr="event_sha256", previous_attr="previous_event_sha256", id_attr="event_id"
    )
    states: dict[str, str] = {}
    for event in ordered:
        previous_state = states.get(event.canary_id)
        allowed = GENESIS[None] if previous_state is None else TRANSITIONS[previous_state]
        if event.event_type not in allowed:
            raise CanaryGovernanceError(
                "BA11_EVENT_TRANSITION_INVALID", f"{previous_state}->{event.event_type}"
            )
        state = {
            "genesis": "genesis",
            "candidate": "candidate",
            "review_accepted": "review_accepted",
            "operator_approved": "operator_approved",
            "frozen": "frozen",
            "rejected": "rejected",
            "stale": "stale",
            "recovered": "recovered",
            "superseded": "superseded",
        }[event.event_type]
        states[event.canary_id] = state
    return states


def verify_debt_ledger(events: Iterable[AcceptedDebtEvent]) -> dict[str, str]:
    ordered = _verify_chain(
        events, hash_attr="event_sha256", previous_attr="previous_event_sha256", id_attr="event_id"
    )
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
        if event.event_type not in allowed[current]:
            raise CanaryGovernanceError("BA11_DEBT_CHAIN_BROKEN", event.event_id)
        if event.state_before != current:
            raise CanaryGovernanceError("BA11_DEBT_CHAIN_BROKEN", "state_before")
        states[event.debt_id] = event.state_after
    return states


def mirror_receipt(
    *, research_snapshot_sha256: str, mirrored_snapshot_sha256: str, product_commit: str
) -> MirrorReceipt:
    state = "valid" if research_snapshot_sha256 == mirrored_snapshot_sha256 else "consumer_mirror_invalid"
    return MirrorReceipt.create(
        research_snapshot_sha256=research_snapshot_sha256,
        mirrored_snapshot_sha256=mirrored_snapshot_sha256,
        product_commit=product_commit,
        receipt_state=state,
    )
