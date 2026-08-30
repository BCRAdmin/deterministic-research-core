"""Measured, fail-closed disk guard for sequential live capture workloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


GIB = 1024**3


@dataclass(frozen=True)
class DiskGuardPolicy:
    absolute_floor: int = 2 * GIB
    safety_factor: int = 3
    package_reserve: int = 512 * 1024**2
    rollback_margin: int = 512 * 1024**2
    protected_floor: int = 0

    def __post_init__(self) -> None:
        if self.absolute_floor < 2 * GIB:
            raise ValueError("DYNAMIC_DISK_ABSOLUTE_FLOOR_BELOW_2_GIB")
        if self.safety_factor < 3:
            raise ValueError("DYNAMIC_DISK_SAFETY_FACTOR_BELOW_3")
        if self.package_reserve <= 0:
            raise ValueError("DYNAMIC_DISK_PACKAGE_RESERVE_MISSING")


def evaluate_disk_guard(
    *,
    free_before: int,
    measured_case_peaks: Iterable[int],
    comparator_peaks: Iterable[int] = (),
    policy: DiskGuardPolicy = DiskGuardPolicy(),
    evidence_refs: Iterable[str] = (),
) -> dict[str, object]:
    measured = tuple(int(value) for value in measured_case_peaks)
    comparators = tuple(int(value) for value in comparator_peaks)
    if not measured or min(measured) <= 0 or (comparators and min(comparators) <= 0):
        raise RuntimeError("DYNAMIC_DISK_MEASUREMENTS_MISSING")
    predicted_peak = max((*measured, *comparators))
    safety_margin = predicted_peak * (policy.safety_factor - 1)
    required_free = max(
        policy.absolute_floor,
        policy.protected_floor
        + predicted_peak
        + safety_margin
        + policy.package_reserve
        + policy.rollback_margin,
    )
    headroom = int(free_before) - required_free
    body: dict[str, object] = {
        "contract_id": "room16.dynamic_disk_guard_receipt",
        "contract_version": 1,
        "free_before": int(free_before),
        "predicted_peak": predicted_peak,
        "safety_factor": policy.safety_factor,
        "package_reserve": policy.package_reserve,
        "rollback_margin": policy.rollback_margin,
        "protected_floor": policy.protected_floor,
        "absolute_floor": policy.absolute_floor,
        "required_free": required_free,
        "headroom": headroom,
        "decision": "PASS" if headroom >= 0 else "STOP",
        "evidence_refs": list(evidence_refs),
        "measured_case_peaks": list(measured),
        "comparator_peaks": list(comparators),
    }
    return body

