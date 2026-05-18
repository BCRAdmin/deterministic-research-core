import re
from pathlib import Path

from research_agent.audit.rule_registry import REGISTERED_AUDIT_RULES, registered_audit_rule_ids


def test_audit_rule_registry_ids_are_unique_and_actionable():
    rule_ids = [rule.rule_id for rule in REGISTERED_AUDIT_RULES]

    assert len(rule_ids) == len(set(rule_ids))
    assert all(rule.default_severity in {"error", "warning"} for rule in REGISTERED_AUDIT_RULES)
    assert all(rule.fixture_hint for rule in REGISTERED_AUDIT_RULES)
    assert all(rule.public_gate_effect in {"blocks_publish", "requires_review"} for rule in REGISTERED_AUDIT_RULES)


def test_report_linter_codes_are_registered():
    linter_path = Path(__file__).resolve().parents[1] / "audit" / "report_linter.py"
    linter_source = linter_path.read_text(encoding="utf-8")
    literal_codes = set(re.findall(r'code="([A-Z0-9_]+)"', linter_source))

    assert literal_codes <= registered_audit_rule_ids()
