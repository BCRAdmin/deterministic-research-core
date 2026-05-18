from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RuleSeverity = Literal["error", "warning"]
RuleCategory = Literal[
    "numeric",
    "period",
    "evidence",
    "rating",
    "causality",
    "guidance",
    "earnings",
    "financial_sanity",
    "current_period",
]


@dataclass(frozen=True)
class AuditRuleDefinition:
    rule_id: str
    default_severity: RuleSeverity
    category: RuleCategory
    fixture_hint: str
    public_gate_effect: str


REGISTERED_AUDIT_RULES: tuple[AuditRuleDefinition, ...] = (
    AuditRuleDefinition("NUMERIC_MISMATCH", "error", "numeric", "numeric mismatch golden fixture", "blocks_publish"),
    AuditRuleDefinition("UNVERIFIED_HARD_METRIC", "warning", "numeric", "unmapped hard metric fixture", "requires_review"),
    AuditRuleDefinition("MISSING_EVIDENCE_FOR_HARD_CLAIM", "error", "evidence", "missing evidence ledger fixture", "blocks_publish"),
    AuditRuleDefinition("LOW_AUTHORITY_EVIDENCE_FOR_HARD_CLAIM", "warning", "evidence", "vendor-only evidence fixture", "requires_review"),
    AuditRuleDefinition("VENDOR_SOURCE_USED_AS_PRIMARY", "warning", "evidence", "vendor primary source fixture", "requires_review"),
    AuditRuleDefinition("PERIOD_MISMATCH", "error", "period", "Q4 versus TTM mismatch fixture", "blocks_publish"),
    AuditRuleDefinition("CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED", "error", "current_period", "current-period IR reconciliation fixture", "blocks_publish"),
    AuditRuleDefinition("MISSING_CURRENT_PERIOD_CONTEXT", "warning", "current_period", "missing current-period context fixture", "requires_review"),
    AuditRuleDefinition("MISSING_CURRENT_PERIOD_KPI_CONTEXT", "warning", "current_period", "missing current-period KPI fixture", "requires_review"),
    AuditRuleDefinition("AVGO_CURRENT_KPI_CONTEXT_REQUIRED", "warning", "current_period", "AVGO KPI context fixture", "requires_review"),
    AuditRuleDefinition("INVALID_TRADE_LEVEL", "error", "rating", "invalid stop/entry/take-profit fixture", "blocks_publish"),
    AuditRuleDefinition("RATING_TOO_HARSH_FOR_ACTION", "warning", "rating", "rating/action mismatch fixture", "requires_review"),
    AuditRuleDefinition("RATING_ACTION_MISMATCH", "warning", "rating", "rating/action class fixture", "requires_review"),
    AuditRuleDefinition("RATING_BLOCKED_BY_DECISION_PACKET", "error", "rating", "blocked rating fixture", "blocks_publish"),
    AuditRuleDefinition("MISSING_FCF_SUPPORT_FOR_ACCUMULATE", "error", "rating", "accumulate without FCF support fixture", "blocks_publish"),
    AuditRuleDefinition("OVERSTATED_CAUSALITY", "warning", "causality", "news-price causality fixture", "requires_review"),
    AuditRuleDefinition("NO_NEWS_WITH_AVAILABLE_SOURCES", "error", "causality", "no-news contradiction fixture", "blocks_publish"),
    AuditRuleDefinition("WEAK_NEWS_CAUSALITY", "warning", "causality", "weak same-day causality fixture", "requires_review"),
    AuditRuleDefinition("UNSUPPORTED_GUIDANCE_CLAIM", "error", "guidance", "guidance without primary evidence fixture", "blocks_publish"),
    AuditRuleDefinition("UNSUPPORTED_EARNINGS_EVENT_CLAIM", "error", "earnings", "earnings date unavailable fixture", "blocks_publish"),
    AuditRuleDefinition("PERIOD_DENOMINATOR_BUG", "error", "financial_sanity", "valuation denominator bug fixture", "blocks_publish"),
    AuditRuleDefinition("EXTREME_VALUATION_REQUIRES_REVIEW", "error", "financial_sanity", "extreme valuation fixture", "blocks_publish"),
    AuditRuleDefinition("TRUE_VALUATION_ANOMALY", "error", "financial_sanity", "true valuation anomaly fixture", "blocks_publish"),
    AuditRuleDefinition("TRUE_FINANCIAL_ANOMALY", "error", "financial_sanity", "true financial anomaly fixture", "blocks_publish"),
    AuditRuleDefinition("GUARD_THRESHOLD_REVIEW", "warning", "financial_sanity", "threshold review fixture", "requires_review"),
    AuditRuleDefinition("FINANCIAL_SANITY_FCF_MARGIN_ANOMALY", "error", "financial_sanity", "FCF margin anomaly fixture", "blocks_publish"),
    AuditRuleDefinition("FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY", "error", "financial_sanity", "price-to-FCF anomaly fixture", "blocks_publish"),
    AuditRuleDefinition("COMPANY_DEFINED_FCF_MISMATCH", "error", "financial_sanity", "company-defined FCF mismatch fixture", "blocks_publish"),
    AuditRuleDefinition("COMPANY_DEFINED_FCF_OCF_INCONSISTENCY", "warning", "financial_sanity", "FCF versus OCF inconsistency fixture", "requires_review"),
    AuditRuleDefinition("FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT", "error", "financial_sanity", "FCF unavailable without IR support fixture", "blocks_publish"),
)


AUDIT_RULE_BY_ID = {rule.rule_id: rule for rule in REGISTERED_AUDIT_RULES}


def registered_audit_rule_ids() -> set[str]:
    return set(AUDIT_RULE_BY_ID)
