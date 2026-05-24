from dataclasses import replace
from pathlib import Path

from research_agent.ops.coding_guardrails import (
    REQUIRED_GUARDRAIL_IDS,
    default_coding_guardrails,
    render_coding_guardrails_markdown,
    validate_coding_guardrails,
)


def test_default_coding_guardrails_are_valid() -> None:
    contract = default_coding_guardrails()
    validation = validate_coding_guardrails(contract)

    assert validation.valid is True
    assert not validation.errors
    assert tuple(item.guardrail_id for item in contract.items) == REQUIRED_GUARDRAIL_IDS
    assert contract.runtime_policy == "playbook_only"
    assert "global_session_hook" in contract.blocked_defaults
    assert "auto_subagent_driven_development" in contract.blocked_defaults


def test_verification_and_debugging_guardrails_are_hard_gates() -> None:
    contract = default_coding_guardrails()
    by_id = {item.guardrail_id: item for item in contract.items}

    assert by_id["evidence_before_completion"].gate_level == "hard"
    assert by_id["root_cause_before_fix"].gate_level == "hard"
    assert "fresh verification evidence" in by_id["evidence_before_completion"].required_evidence
    assert "root cause note" in by_id["root_cause_before_fix"].required_evidence


def test_missing_required_guardrail_invalidates_contract() -> None:
    contract = default_coding_guardrails()
    broken = replace(
        contract,
        items=tuple(item for item in contract.items if item.guardrail_id != "minimal_surgical_change"),
    )

    validation = validate_coding_guardrails(broken)

    assert validation.valid is False
    assert "missing_guardrail:minimal_surgical_change" in validation.errors


def test_runtime_activation_requires_operator_gate() -> None:
    contract = default_coding_guardrails()
    broken = replace(contract, runtime_policy="global_install")

    validation = validate_coding_guardrails(broken)

    assert validation.valid is False
    assert "runtime_policy_not_playbook_only" in validation.errors


def test_markdown_renders_source_mapping_and_boundaries() -> None:
    contract = default_coding_guardrails()
    validation = validate_coding_guardrails(contract)
    markdown = render_coding_guardrails_markdown(contract, validation)

    assert "Gueltig: `true`" in markdown
    assert "`karpathy-guidelines`" in markdown
    assert "`superpowers:verification-before-completion`" in markdown
    assert "`global_session_hook`" in markdown
    assert "`playbook_only`" in markdown


def test_document_contract_mentions_coding_guardrails_doc() -> None:
    doc = Path("docs/agent_os/AGENT_CODING_GUARDRAILS.md")

    assert doc.exists()
