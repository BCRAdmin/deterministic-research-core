from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
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
    "archetype",
]


@dataclass(frozen=True)
class AuditRuleDefinition:
    rule_id: str
    default_severity: RuleSeverity
    category: RuleCategory
    fixture_hint: str
    public_gate_effect: str


REGISTERED_AUDIT_RULES: tuple[AuditRuleDefinition, ...] = (
    AuditRuleDefinition("CURRENCY_MISMATCH", "error", "numeric", "report versus evidence currency fixture", "blocks_publish"),
    AuditRuleDefinition("NUMERIC_MISMATCH", "error", "numeric", "numeric mismatch golden fixture", "blocks_publish"),
    AuditRuleDefinition("UNVERIFIED_HARD_METRIC", "warning", "numeric", "unmapped hard metric fixture", "requires_review"),
    AuditRuleDefinition("MISSING_EVIDENCE_FOR_HARD_CLAIM", "error", "evidence", "missing evidence ledger fixture", "blocks_publish"),
    AuditRuleDefinition("LOW_AUTHORITY_EVIDENCE_FOR_HARD_CLAIM", "warning", "evidence", "vendor-only evidence fixture", "requires_review"),
    AuditRuleDefinition("VENDOR_SOURCE_USED_AS_PRIMARY", "warning", "evidence", "vendor primary source fixture", "requires_review"),
    AuditRuleDefinition("VENDOR_ONLY_HARD_METRICS", "warning", "evidence", "vendor-only hard metrics manual-review fixture", "requires_review"),
    AuditRuleDefinition("EVIDENCE_INCOMPLETE_FOR_GOLD", "warning", "evidence", "incomplete primary-evidence gold fixture", "requires_review"),
    AuditRuleDefinition("PERIOD_MISMATCH", "error", "period", "Q4 versus TTM mismatch fixture", "blocks_publish"),
    AuditRuleDefinition("CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED", "error", "current_period", "current-period IR reconciliation fixture", "blocks_publish"),
    AuditRuleDefinition("MISSING_CURRENT_PERIOD_CONTEXT", "warning", "current_period", "missing current-period context fixture", "requires_review"),
    AuditRuleDefinition("MISSING_CURRENT_PERIOD_KPI_CONTEXT", "warning", "current_period", "missing current-period KPI fixture", "requires_review"),
    AuditRuleDefinition("AVGO_CURRENT_KPI_CONTEXT_REQUIRED", "warning", "current_period", "AVGO KPI context fixture", "requires_review"),
    AuditRuleDefinition("MALFORMED_SEC_DISCLOSURE_FRAGMENT", "error", "evidence", "broken SEC disclosure fragment fixture", "blocks_publish"),
    AuditRuleDefinition("INVALID_TRADE_LEVEL", "error", "rating", "invalid stop/entry/take-profit fixture", "blocks_publish"),
    AuditRuleDefinition("RATING_TOO_HARSH_FOR_ACTION", "warning", "rating", "rating/action mismatch fixture", "requires_review"),
    AuditRuleDefinition("RATING_ACTION_MISMATCH", "warning", "rating", "rating/action class fixture", "requires_review"),
    AuditRuleDefinition("RATING_BLOCKED_BY_DECISION_PACKET", "error", "rating", "blocked rating fixture", "blocks_publish"),
    AuditRuleDefinition("UNBENCHMARKED_VALUATION_DIRECTION", "error", "rating", "unbenchmarked multiple used directionally fixture", "blocks_publish"),
    AuditRuleDefinition("MEASURED_VALUATION_MISSINGNESS_CONTRADICTION", "error", "rating", "measured multiple described as unavailable fixture", "blocks_publish"),
    AuditRuleDefinition("MISSING_FCF_SUPPORT_FOR_ACCUMULATE", "error", "rating", "accumulate without FCF support fixture", "blocks_publish"),
    AuditRuleDefinition("CLEAN_BUY_ACCUMULATE_BLOCKED", "warning", "rating", "deep-tech clean buy/accumulate block fixture", "requires_review"),
    AuditRuleDefinition("CLEAN_HOLD_BLOCKED_FOR_SPECULATIVE_DEEP_TECH", "warning", "rating", "speculative deep-tech clean hold block fixture", "requires_review"),
    AuditRuleDefinition("TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS", "warning", "rating", "technical-overweight thesis fixture", "requires_review"),
    AuditRuleDefinition("OVERSTATED_CAUSALITY", "warning", "causality", "news-price causality fixture", "requires_review"),
    AuditRuleDefinition("NO_NEWS_WITH_AVAILABLE_SOURCES", "error", "causality", "no-news contradiction fixture", "blocks_publish"),
    AuditRuleDefinition("WEAK_NEWS_CAUSALITY", "warning", "causality", "weak same-day causality fixture", "requires_review"),
    AuditRuleDefinition("UNSUPPORTED_CAUSALITY_CLAIM", "error", "causality", "unsupported causality legacy fixture", "blocks_publish"),
    AuditRuleDefinition("UNSUPPORTED_GUIDANCE_CLAIM", "error", "guidance", "guidance without primary evidence fixture", "blocks_publish"),
    AuditRuleDefinition("FORWARD_EPS_GUIDANCE_MISMATCH", "error", "guidance", "forward EPS guidance mismatch fixture", "blocks_publish"),
    AuditRuleDefinition("GUIDANCE_CONSENSUS_CONFLATION", "error", "guidance", "guidance versus consensus conflation fixture", "blocks_publish"),
    AuditRuleDefinition("UNSUPPORTED_EARNINGS_EVENT_CLAIM", "error", "earnings", "earnings date unavailable fixture", "blocks_publish"),
    AuditRuleDefinition("SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE", "warning", "archetype", "speculative deep-tech manual-review profile fixture", "requires_review"),
    AuditRuleDefinition("EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE", "warning", "archetype", "early-commercial capital-intensive profile fixture", "requires_review"),
    AuditRuleDefinition("ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND", "warning", "archetype", "non-operating accounting gain caveat fixture", "requires_review"),
    AuditRuleDefinition("ORDER_MATERIALITY_MISSING", "warning", "archetype", "orders/contracts materiality fixture", "requires_review"),
    AuditRuleDefinition("PERIOD_DENOMINATOR_BUG", "error", "financial_sanity", "valuation denominator bug fixture", "blocks_publish"),
    AuditRuleDefinition("FINANCIAL_SANITY_EV_SALES_ABSURD", "error", "financial_sanity", "legacy EV/Sales absurdity fixture", "blocks_publish"),
    AuditRuleDefinition("FINANCIAL_SANITY_SBC_REVENUE_ANOMALY", "error", "financial_sanity", "legacy SBC/revenue anomaly fixture", "blocks_publish"),
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


def unregistered_audit_rule_ids(rule_ids: Iterable[str]) -> set[str]:
    return {rule_id for rule_id in rule_ids if rule_id not in AUDIT_RULE_BY_ID}


def assert_registered_audit_rule_ids(rule_ids: Iterable[str], *, source: str = "audit") -> None:
    unknown = sorted(unregistered_audit_rule_ids(rule_ids))
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"{source} emitted unregistered audit rule id(s): {joined}")
