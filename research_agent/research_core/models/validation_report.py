from typing import List, Optional

from pydantic import BaseModel, Field


BLOCKING_ERROR_CODES = {
    "TTM_SUM_MISMATCH",
    "MARGIN_MISMATCH",
    "PRICE_DATE_AFTER_AS_OF_DATE",
    "LONG_STOP_ABOVE_ENTRY",
    "SHORT_STOP_BELOW_ENTRY",
    "MISSING_PRICE_BASIS",
    "MISSING_PRIMARY_FINANCIAL_SOURCE",
}


class ValidationIssue(BaseModel):
    severity: str
    code: str
    message: str
    metric: Optional[str] = None
    computed: Optional[float] = None
    reported: Optional[float] = None


class ValidationReport(BaseModel):
    ticker: str
    as_of_date: str
    has_blocking_errors: bool
    issues: List[ValidationIssue] = Field(default_factory=list)

    @classmethod
    def from_issues(
        cls,
        ticker: str,
        as_of_date: str,
        issues: List[ValidationIssue],
    ) -> "ValidationReport":
        has_blocking = any(
            issue.severity == "error" or issue.code in BLOCKING_ERROR_CODES
            for issue in issues
        )
        return cls(
            ticker=ticker,
            as_of_date=as_of_date,
            has_blocking_errors=has_blocking,
            issues=issues,
        )
