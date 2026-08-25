"""Deterministic BA12 cutover and recovery state machine."""

from __future__ import annotations

from .contracts import CutoverState, create_record

ALLOWED = {
    "shadow_native": {"dual_run_compare"},
    "dual_run_compare": {"shadow_native", "cutover_candidate"},
    "cutover_candidate": {"dual_run_compare", "native_authoritative"},
    "native_authoritative": set(),
}


def transition(*, current: str, target: str, transition_receipt_sha256: str, comparison_passed: bool = False, operator_approval_bound: bool = False, independent_acceptance_sha256: str | None = None, frozen: bool = False) -> CutoverState:
    if target not in ALLOWED.get(current, set()):
        raise ValueError("BA12_CUTOVER_TRANSITION_FORBIDDEN")
    if frozen and target != current:
        raise ValueError("BA12_FROZEN_STATE_IMMUTABLE")
    if target == "cutover_candidate" and (not comparison_passed or not operator_approval_bound):
        raise ValueError("BA12_CUTOVER_CANDIDATE_GATE_BLOCK")
    if target == "native_authoritative" and independent_acceptance_sha256 is None:
        raise ValueError("BA12_INDEPENDENT_ACCEPTANCE_REQUIRED")
    return create_record(CutoverState, state=target, previous_state=current, transition_receipt_sha256=transition_receipt_sha256, independent_acceptance_sha256=independent_acceptance_sha256, frozen=frozen)
