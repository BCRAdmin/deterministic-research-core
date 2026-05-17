from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal, Optional


BatchMode = Literal["current_research", "historical_guardrail_test"]

STALE_PRICE_BASIS_FOR_CURRENT_REPORT = "STALE_PRICE_BASIS_FOR_CURRENT_REPORT"


@dataclass(frozen=True)
class FreshnessResult:
    price_basis_date: Optional[str]
    reference_date: str
    batch_mode: BatchMode
    trading_day_age: Optional[int]
    stale_price_basis: bool
    current_report_allowed: bool
    historical_qa_only: bool
    data_freshness_status: str
    issue_code: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "price_basis_date": self.price_basis_date,
            "reference_date": self.reference_date,
            "batch_mode": self.batch_mode,
            "trading_day_age": self.trading_day_age,
            "stale_price_basis": self.stale_price_basis,
            "current_report_allowed": self.current_report_allowed,
            "historical_qa_only": self.historical_qa_only,
            "data_freshness_status": self.data_freshness_status,
            "issue_code": self.issue_code,
        }


def evaluate_price_freshness(
    price_basis_date: Optional[str],
    *,
    batch_mode: BatchMode = "current_research",
    reference_date: Optional[str] = None,
    max_trading_day_age: int = 2,
) -> FreshnessResult:
    reference = _parse_date(reference_date) if reference_date else datetime.now(timezone.utc).date()
    reference_iso = reference.isoformat()
    price_date = _parse_date(price_basis_date)
    if price_date is None:
        return FreshnessResult(
            price_basis_date=price_basis_date,
            reference_date=reference_iso,
            batch_mode=batch_mode,
            trading_day_age=None,
            stale_price_basis=True,
            current_report_allowed=False,
            historical_qa_only=batch_mode == "historical_guardrail_test",
            data_freshness_status="missing_price_basis",
            issue_code=STALE_PRICE_BASIS_FOR_CURRENT_REPORT if batch_mode == "current_research" else None,
        )

    age = trading_day_age(price_date, reference)
    stale = age > max_trading_day_age
    if batch_mode == "historical_guardrail_test":
        return FreshnessResult(
            price_basis_date=price_date.isoformat(),
            reference_date=reference_iso,
            batch_mode=batch_mode,
            trading_day_age=age,
            stale_price_basis=stale,
            current_report_allowed=False,
            historical_qa_only=True,
            data_freshness_status="historical_qa_stale_price_basis" if stale else "historical_qa",
            issue_code=None,
        )

    if stale:
        return FreshnessResult(
            price_basis_date=price_date.isoformat(),
            reference_date=reference_iso,
            batch_mode=batch_mode,
            trading_day_age=age,
            stale_price_basis=True,
            current_report_allowed=False,
            historical_qa_only=True,
            data_freshness_status="stale_price_basis",
            issue_code=STALE_PRICE_BASIS_FOR_CURRENT_REPORT,
        )
    return FreshnessResult(
        price_basis_date=price_date.isoformat(),
        reference_date=reference_iso,
        batch_mode=batch_mode,
        trading_day_age=age,
        stale_price_basis=False,
        current_report_allowed=True,
        historical_qa_only=False,
        data_freshness_status="fresh",
        issue_code=None,
    )


def trading_day_age(price_date: date, reference_date: date) -> int:
    if price_date >= reference_date:
        return 0
    days = 0
    cursor_ord = price_date.toordinal() + 1
    while cursor_ord <= reference_date.toordinal():
        cursor = date.fromordinal(cursor_ord)
        if cursor.weekday() < 5:
            days += 1
        cursor_ord += 1
    return days


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
