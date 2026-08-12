from __future__ import annotations

from datetime import date
from typing import Optional

from research_agent.research_core.models.data_packet import DataPacket


def validate_price_date(as_of_date: str, price_date: str):
    as_of = _parse_date(as_of_date)
    price = _parse_date(price_date)

    if price > as_of:
        return {
            "severity": "error",
            "code": "PRICE_DATE_AFTER_AS_OF_DATE",
            "message": "Price date cannot be after report as-of date.",
        }

    if price < as_of and _trading_day_age(price, as_of) > 0:
        return {
            "severity": "warning",
            "code": "PRICE_DATE_BEFORE_AS_OF_DATE",
            "message": "Report uses a prior close. Must disclose this in report.",
        }

    return None


def validate_indicator_date(price_date: str, indicator_date: str):
    if _parse_date(price_date) != _parse_date(indicator_date):
        return {
            "severity": "error",
            "code": "INDICATOR_DATE_MISMATCH",
            "message": "Technical indicator date must match the price basis date.",
        }
    return None


def validate_ttm_quarter_count(metric_name: str, quarterly_values: list[float]):
    if len(quarterly_values) != 4:
        return {
            "severity": "error",
            "code": "TTM_REQUIRES_FOUR_QUARTERS",
            "metric": metric_name,
            "message": f"{metric_name} TTM requires exactly 4 quarterly values.",
        }
    return None


def validate_q4_not_labeled_ttm(metric_name: str, period_type: str, quarterly_values: list[float]):
    if period_type.lower() == "ttm" and len(quarterly_values) == 1:
        return {
            "severity": "error",
            "code": "Q4_LABELED_AS_TTM",
            "metric": metric_name,
            "message": f"{metric_name} has one quarterly value but is labeled TTM.",
        }
    return None


def validate_cash_investments_separation(
    cash_and_equivalents: Optional[float],
    cash_and_investments: Optional[float],
    short_term_investments: Optional[float],
    marketable_securities: Optional[float],
):
    if cash_and_investments is None:
        return None
    computed = (cash_and_equivalents or 0) + (short_term_investments or 0) + (marketable_securities or 0)
    if abs(computed - cash_and_investments) > max(abs(computed) * 0.01, 1e-6):
        return {
            "severity": "warning",
            "code": "CASH_INVESTMENTS_NOT_RECONCILED",
            "metric": "cash_and_investments",
            "computed": computed,
            "reported": cash_and_investments,
            "message": "Cash + investments must be reconciled separately from cash-only.",
        }
    return None


def validate_net_debt_sign(
    cash_and_investments: Optional[float],
    total_debt: Optional[float],
    reported_net_debt: Optional[float],
):
    if cash_and_investments is None or total_debt is None or reported_net_debt is None:
        return None
    if cash_and_investments > total_debt and reported_net_debt > 0:
        return {
            "severity": "error",
            "code": "NET_DEBT_SIGN_CONFLICT",
            "metric": "net_debt",
            "reported": reported_net_debt,
            "message": "Net debt cannot be positive when cash + investments exceed debt.",
        }
    return None


def validate_earnings_date(
    next_earnings_date: Optional[str],
    confirmed: bool,
    source: Optional[str],
    limitation_detail: Optional[str] = None,
):
    if next_earnings_date is None:
        return {
            "severity": "warning",
            "code": "EARNINGS_DATE_UNAVAILABLE",
            "message": (
                "Next earnings date is unavailable. "
                + (
                    limitation_detail
                    or "No confirmed issuer or exchange date was captured."
                )
            ),
        }
    if not confirmed or not source:
        return {
            "severity": "warning",
            "code": "EARNINGS_DATE_UNCONFIRMED",
            "message": "Next earnings date must be treated as unconfirmed unless a source confirms it.",
        }
    return None


def validate_data_packet(data_packet: DataPacket) -> list[dict]:
    issues: list[dict] = []
    if data_packet.price_basis is None:
        issues.append(
            {
                "severity": "error",
                "code": "MISSING_PRICE_BASIS",
                "message": "DataPacket requires an explicit price_basis.",
            }
        )
        return issues

    for issue in [
        validate_price_date(data_packet.as_of_date, data_packet.price_basis.date),
        validate_earnings_date(
            data_packet.next_events.next_earnings_date,
            data_packet.next_events.confirmed,
            data_packet.next_events.source,
            data_packet.next_events.limitation_detail,
        ),
    ]:
        if issue is not None:
            issues.append(issue)
    return issues


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _trading_day_age(price_date: date, as_of_date: date) -> int:
    if price_date >= as_of_date:
        return 0
    days = 0
    cursor_ord = price_date.toordinal() + 1
    while cursor_ord <= as_of_date.toordinal():
        cursor = date.fromordinal(cursor_ord)
        if cursor.weekday() < 5:
            days += 1
        cursor_ord += 1
    return days
