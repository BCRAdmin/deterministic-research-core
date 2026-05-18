# Audit Rule Registry

The audit linter now has a lightweight registry in `research_agent/audit/rule_registry.py`.

Purpose:

- Keep every emitted audit issue code visible and testable.
- Attach each rule to a severity, category, fixture hint and public-gate effect.
- Prevent unregistered linter codes from silently appearing in reports.

Current verifier:

- `research_agent/tests/test_audit_rule_registry.py`
- CI runs the registry through `python -m coverage run -m pytest -q`.
