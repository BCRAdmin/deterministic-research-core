from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from research_agent.audit.rule_registry import assert_registered_audit_rule_ids


BLOCKING_AUDIT_CODES = {
    "CURRENCY_MISMATCH",
    "NUMERIC_MISMATCH",
    "PERIOD_MISMATCH",
    "INVALID_TRADE_LEVEL",
    "NO_NEWS_WITH_AVAILABLE_SOURCES",
    "RATING_TOO_HARSH_FOR_ACTION",
    "RATING_ACTION_MISMATCH",
    "OVERSTATED_CAUSALITY",
    "UNVERIFIED_HARD_METRIC",
    "MISSING_EVIDENCE_FOR_HARD_CLAIM",
    "UNSUPPORTED_CAUSALITY_CLAIM",
    "GUIDANCE_CONSENSUS_CONFLATION",
    "UNSUPPORTED_GUIDANCE_CLAIM",
    "UNSUPPORTED_EARNINGS_EVENT_CLAIM",
    "FINANCIAL_SANITY_EV_SALES_ABSURD",
    "FINANCIAL_SANITY_SBC_REVENUE_ANOMALY",
    "FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY",
    "FINANCIAL_SANITY_FCF_MARGIN_ANOMALY",
    "EXTREME_VALUATION_REQUIRES_REVIEW",
    "TRUE_VALUATION_ANOMALY",
    "CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED",
    "COMPANY_DEFINED_FCF_MISMATCH",
    "FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT",
    "MISSING_CURRENT_PERIOD_CONTEXT",
    "MISSING_CURRENT_PERIOD_KPI_CONTEXT",
    "AVGO_CURRENT_KPI_CONTEXT_REQUIRED",
    "MALFORMED_SEC_DISCLOSURE_FRAGMENT",
    "LEASE_DEBT_DOUBLE_COUNT_RISK",
    "MISSING_FCF_SUPPORT_FOR_ACCUMULATE",
    "PERIOD_DENOMINATOR_BUG",
    "TRUE_FINANCIAL_ANOMALY",
}


class ExtractedNumericClaim(BaseModel):
    raw_text: str
    normalized_value: Optional[float] = None
    unit: Optional[str] = None
    nearby_text: str
    line_number: int
    possible_metric: Optional[str] = None
    period_hint: Optional[str] = None


class AuditIssue(BaseModel):
    severity: str
    code: str
    message: str
    metric: Optional[str] = None
    reported: Optional[float] = None
    validated: Optional[float] = None
    line_number: Optional[int] = None
    raw_text: Optional[str] = None


class AuditReport(BaseModel):
    ticker: Optional[str] = None
    has_blocking_errors: bool
    issues: List[AuditIssue] = Field(default_factory=list)
    numeric_claims: List[ExtractedNumericClaim] = Field(default_factory=list)

    @classmethod
    def from_issues(
        cls,
        issues: List[AuditIssue],
        numeric_claims: Optional[List[ExtractedNumericClaim]] = None,
        ticker: Optional[str] = None,
    ) -> "AuditReport":
        assert_registered_audit_rule_ids((issue.code for issue in issues), source="AuditReport")
        return cls(
            ticker=ticker,
            has_blocking_errors=any(
                issue.severity == "error" or issue.code in BLOCKING_AUDIT_CODES
                for issue in issues
            ),
            issues=issues,
            numeric_claims=numeric_claims or [],
        )

    def has_issue(self, code: str, metric: Optional[str] = None) -> bool:
        return any(
            issue.code == code and (metric is None or issue.metric == metric)
            for issue in self.issues
        )
