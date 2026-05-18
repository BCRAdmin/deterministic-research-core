import ast
import re
from pathlib import Path

import pytest

from research_agent.audit.audit_report import BLOCKING_AUDIT_CODES, AuditIssue, AuditReport
from research_agent.audit.report_linter import _audit_trade_rule_code
from research_agent.audit.rule_registry import REGISTERED_AUDIT_RULES, registered_audit_rule_ids
from research_agent.quality import deeptech_manual_review


def test_audit_rule_registry_ids_are_unique_and_actionable():
    rule_ids = [rule.rule_id for rule in REGISTERED_AUDIT_RULES]

    assert len(rule_ids) == len(set(rule_ids))
    assert all(rule.default_severity in {"error", "warning"} for rule in REGISTERED_AUDIT_RULES)
    assert all(rule.fixture_hint for rule in REGISTERED_AUDIT_RULES)
    assert all(rule.public_gate_effect in {"blocks_publish", "requires_review"} for rule in REGISTERED_AUDIT_RULES)


def test_report_linter_codes_are_registered():
    linter_path = Path(__file__).resolve().parents[1] / "audit" / "report_linter.py"
    linter_source = linter_path.read_text(encoding="utf-8")
    literal_codes = _literal_audit_issue_codes(linter_source)

    assert literal_codes <= registered_audit_rule_ids()


def test_blocking_audit_codes_are_registered():
    assert BLOCKING_AUDIT_CODES <= registered_audit_rule_ids()


def test_deeptech_audit_profile_codes_are_registered():
    profile_codes = {
        deeptech_manual_review.SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE,
        deeptech_manual_review.EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE,
        deeptech_manual_review.ACCOUNTING_GAIN_NOT_OPERATING_TURNAROUND,
        deeptech_manual_review.EVIDENCE_INCOMPLETE_FOR_GOLD,
        deeptech_manual_review.VENDOR_ONLY_HARD_METRICS,
        deeptech_manual_review.ORDER_MATERIALITY_MISSING,
        deeptech_manual_review.TECHNICAL_OVERWEIGHT_IN_FUNDAMENTAL_THESIS,
        deeptech_manual_review.CLEAN_BUY_ACCUMULATE_BLOCKED,
        deeptech_manual_review.CLEAN_HOLD_BLOCKED_FOR_SPECULATIVE_DEEP_TECH,
    }

    assert profile_codes <= registered_audit_rule_ids()


def test_audit_report_rejects_unregistered_rule_ids():
    issue = AuditIssue(severity="error", code="NEW_UNREGISTERED_AUDIT_RULE", message="drift")

    with pytest.raises(ValueError, match="NEW_UNREGISTERED_AUDIT_RULE"):
        AuditReport.from_issues([issue], ticker="DRIFT")


@pytest.mark.parametrize(
    "trade_rule_code",
    [
        "LONG_STOP_ABOVE_ENTRY",
        "LONG_TAKE_PROFIT_BELOW_ENTRY",
        "SHORT_STOP_BELOW_ENTRY",
        "SHORT_TAKE_PROFIT_ABOVE_ENTRY",
        "UNKNOWN_POSITION_TYPE",
    ],
)
def test_trade_validation_codes_are_normalized_to_registered_audit_code(trade_rule_code):
    assert _audit_trade_rule_code(trade_rule_code) == "INVALID_TRADE_LEVEL"
    assert _audit_trade_rule_code(trade_rule_code) in registered_audit_rule_ids()


def _literal_audit_issue_codes(source: str) -> set[str]:
    tree = ast.parse(source)
    codes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "AuditIssue":
            continue
        for keyword in node.keywords:
            if keyword.arg == "code":
                codes.update(_uppercase_string_literals(keyword.value))
    return codes


def _uppercase_string_literals(node: ast.AST) -> set[str]:
    values = {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and re.fullmatch(r"[A-Z0-9_]+", child.value)
    }
    return values
