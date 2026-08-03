from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


class ResolvedPeriod(BaseModel):
    period_label: str
    period_type: Literal["instant", "duration"]
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None
    period_bucket: Literal["instant", "annual", "quarterly", "ytd", "ttm", "duration_unknown"] = "duration_unknown"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration_days: Optional[int] = None
    frame: Optional[str] = None
    is_annual: bool = False
    is_quarterly: bool = False
    is_ytd: bool = False
    is_ttm: bool = False


INSTANT_METRICS = {
    "cash_and_equivalents",
    "short_term_investments",
    "current_assets",
    "current_liabilities",
    "total_assets",
    "total_liabilities",
    "stockholders_equity",
    "equity",
    "total_debt",
    "short_term_debt",
    "debt_current",
    "debt_noncurrent",
    "lease_liability_current",
    "lease_liability_noncurrent",
    "cash_and_investments",
    "treasury_stock_value",
    "treasury_share_count",
    "listed_share_count",
    "economic_share_count",
}


def infer_period_type(metric_name: str) -> str:
    return "instant" if metric_name in INSTANT_METRICS else "duration"


def resolve_period(metric_name: str, fact) -> ResolvedPeriod:
    period_type = infer_period_type(metric_name)
    start = getattr(fact, "start", None)
    end = getattr(fact, "end", None)
    fy = getattr(fact, "fy", None)
    fp = getattr(fact, "fp", None)
    frame = getattr(fact, "frame", None)
    duration_days = _duration_days(start, end)
    is_annual = _is_annual(fp, duration_days, frame)
    is_quarterly = _is_quarterly(fp, duration_days, frame)
    is_ttm = bool(duration_days is not None and 330 <= duration_days <= 380 and fp not in {"FY", "CY"})
    is_ytd = _is_ytd(fp, duration_days, is_annual=is_annual, is_quarterly=is_quarterly)
    period_bucket = _period_bucket(period_type, is_annual, is_quarterly, is_ytd, is_ttm)

    if frame:
        label = frame
    elif fy and fp:
        if period_bucket == "annual":
            label = f"FY{fy}"
        elif fp in {"FY", "CY"}:
            label = f"{end}_{period_bucket}" if end else f"FY{fy}_{period_bucket}"
        else:
            label = f"{fp}_FY{fy}_{period_bucket}"
    else:
        label = end or "unknown"

    return ResolvedPeriod(
        period_label=label,
        period_type=period_type,
        fiscal_year=fy,
        fiscal_period=fp,
        period_bucket=period_bucket,
        start_date=start,
        end_date=end,
        duration_days=duration_days,
        frame=frame,
        is_annual=is_annual,
        is_quarterly=is_quarterly,
        is_ytd=is_ytd,
        is_ttm=is_ttm,
    )


def validate_resolved_period(metric_name: str, resolved: ResolvedPeriod) -> list[dict]:
    issues: list[dict] = []
    if resolved.period_type == "duration" and not resolved.end_date:
        issues.append({
            "severity": "warning",
            "code": "MISSING_PERIOD_FOR_DURATION_METRIC",
            "metric": metric_name,
            "message": f"{metric_name} is a duration metric but has no period end date.",
        })
    if resolved.period_type == "instant" and resolved.duration_days is not None and resolved.duration_days > 1:
        issues.append({
            "severity": "warning",
            "code": "INSTANT_METRIC_HAS_DURATION_PERIOD",
            "metric": metric_name,
            "message": f"{metric_name} is an instant metric but has a duration period.",
        })
    return issues


def _duration_days(start: Optional[str], end: Optional[str]) -> Optional[int]:
    if not start or not end:
        return None
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def _is_annual(fp: Optional[str], duration_days: Optional[int], frame: Optional[str]) -> bool:
    if duration_days is not None:
        return 330 <= duration_days <= 380
    if fp in {"FY", "CY"}:
        return True
    if frame and frame.startswith("CY") and frame.endswith("I"):
        return False
    return False


def _is_quarterly(fp: Optional[str], duration_days: Optional[int], frame: Optional[str]) -> bool:
    if frame and "Q" in frame and frame.endswith("I"):
        return True
    if duration_days is not None and 70 <= duration_days <= 110:
        return True
    return False


def _is_ytd(
    fp: Optional[str],
    duration_days: Optional[int],
    is_annual: bool,
    is_quarterly: bool,
) -> bool:
    if is_annual or is_quarterly:
        return False
    if fp in {"Q2", "Q3", "Q4"} and duration_days is not None and 111 <= duration_days < 330:
        return True
    return False


def _period_bucket(
    period_type: str,
    is_annual: bool,
    is_quarterly: bool,
    is_ytd: bool,
    is_ttm: bool,
) -> str:
    if period_type == "instant":
        return "instant"
    if is_annual:
        return "annual"
    if is_quarterly:
        return "quarterly"
    if is_ytd:
        return "ytd"
    if is_ttm:
        return "ttm"
    return "duration_unknown"
