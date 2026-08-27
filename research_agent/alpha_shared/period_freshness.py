"""Shared deterministic period, comparative, and freshness classification."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

PeriodType = Literal["INSTANT", "DURATION"]
DurationRole = Literal["STANDALONE_QUARTER", "YEAR_TO_DATE", "ANNUAL", "OTHER_DURATION"]
ComparativeRole = Literal["CURRENT_PRIMARY", "CURRENT_YTD", "COMPARATIVE", "HISTORICAL"]
FreshnessStatus = Literal["CURRENT", "AGING", "STALE"]


class PeriodCandidate(StrictModel):
    candidate_id: str
    period_start: str | None = None
    period_end: str
    filed_date: str
    as_of_date: str
    form: str
    cadence_profile_id: str
    current_period_end: str
    newer_same_basis_exists: bool = False


class PeriodFreshnessReceipt(StrictModel):
    contract_id: str = "room16.alpha.period_freshness_receipt"
    contract_version: int = 1
    candidate_id: str
    period_type: PeriodType
    duration_role: DurationRole | None
    comparative_role: ComparativeRole
    freshness_status: FreshnessStatus
    age_days: int = Field(ge=0)
    newer_same_basis_exists: bool
    cadence_profile_id: str
    reason_codes: tuple[str, ...]
    policy_sha256: str


PERIOD_POLICY = {
    "contract_id": "room16.alpha.period_freshness_policy",
    "contract_version": 1,
    "aging_after_days": 120,
    "stale_after_days": 370,
    "recent_filing_does_not_override_economic_period": True,
}
PERIOD_POLICY_SHA256 = sha256_json(PERIOD_POLICY)


def classify_period(candidate: PeriodCandidate) -> PeriodFreshnessReceipt:
    end = date.fromisoformat(candidate.period_end)
    current_end = date.fromisoformat(candidate.current_period_end)
    as_of = date.fromisoformat(candidate.as_of_date)
    date.fromisoformat(candidate.filed_date)
    age_days = max(0, (as_of - end).days)
    reason_codes: list[str] = []
    if candidate.period_start is None:
        period_type: PeriodType = "INSTANT"
        duration_role = None
    else:
        period_type = "DURATION"
        start = date.fromisoformat(candidate.period_start)
        duration_days = (end - start).days + 1
        if 70 <= duration_days <= 105:
            duration_role = "STANDALONE_QUARTER"
        elif 150 <= duration_days <= 285:
            duration_role = "YEAR_TO_DATE"
        elif 330 <= duration_days <= 380:
            duration_role = "ANNUAL"
        else:
            duration_role = "OTHER_DURATION"
        reason_codes.append(f"DURATION_{duration_role}")
    if end == current_end:
        comparative_role: ComparativeRole = (
            "CURRENT_YTD" if duration_role == "YEAR_TO_DATE" else "CURRENT_PRIMARY"
        )
    elif end < current_end:
        comparative_role = "COMPARATIVE" if candidate.form in {"10-Q", "10-K"} else "HISTORICAL"
        reason_codes.append("ECONOMIC_PERIOD_PRECEDES_CURRENT")
    else:
        comparative_role = "HISTORICAL"
        reason_codes.append("PERIOD_AFTER_DECLARED_CURRENT")
    if age_days > int(PERIOD_POLICY["stale_after_days"]):
        freshness: FreshnessStatus = "STALE"
        reason_codes.append("AGE_EXCEEDS_STALE_THRESHOLD")
    elif age_days > int(PERIOD_POLICY["aging_after_days"]):
        freshness = "AGING"
        reason_codes.append("AGE_EXCEEDS_AGING_THRESHOLD")
    else:
        freshness = "CURRENT"
    if candidate.newer_same_basis_exists:
        reason_codes.append("NEWER_SAME_BASIS_EXISTS")
        if freshness == "CURRENT":
            freshness = "AGING"
    return PeriodFreshnessReceipt(
        candidate_id=candidate.candidate_id,
        period_type=period_type,
        duration_role=duration_role,
        comparative_role=comparative_role,
        freshness_status=freshness,
        age_days=age_days,
        newer_same_basis_exists=candidate.newer_same_basis_exists,
        cadence_profile_id=candidate.cadence_profile_id,
        reason_codes=tuple(reason_codes),
        policy_sha256=PERIOD_POLICY_SHA256,
    )


def derived_inputs_compatible(receipts: tuple[PeriodFreshnessReceipt, ...]) -> bool:
    if not receipts:
        return False
    roles = {(item.period_type, item.duration_role, item.comparative_role) for item in receipts}
    return len(roles) == 1 and all(item.freshness_status != "STALE" for item in receipts)
