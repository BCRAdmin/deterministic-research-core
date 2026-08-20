"""Independent R4 acceptance coverage and self-certification gates."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .diagnostics import CanaryGovernanceError


def discover_source_tests(source_root: Path) -> set[str]:
    """Discover concrete pytest function names without importing test modules."""
    names: set[str] = set()
    for path in sorted(source_root.rglob("test_*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("def test_"):
                names.add(stripped[4 : stripped.index("(")])
    return names


def verify_acceptance_register(
    required: dict[str, Any],
    executed: dict[str, Any],
    *,
    source_test_names: set[str],
) -> None:
    """Require a unique, concrete, passing receipt for every authoritative row."""
    required_rows = required.get("rows", [])
    executed_rows = executed.get("rows", [])
    required_ids = [row.get("test_id") for row in required_rows]
    executed_ids = [row.get("test_id") for row in executed_rows]
    if set(required_ids) - set(executed_ids):
        raise CanaryGovernanceError("BA11_ACCEPTANCE_REQUIREMENT_MISSING")
    if any(count != 1 for count in Counter(executed_ids).values()):
        raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS")
    by_id = {row["test_id"]: row for row in executed_rows}
    for specification in required_rows:
        row = by_id[specification["test_id"]]
        source_name = row.get("source_test_name")
        if not source_name or source_name not in source_test_names:
            raise CanaryGovernanceError("BA11_TEST_ID_UNRESOLVED", str(source_name))
        if source_name in {"full_suite", "generic_suite", "pytest"}:
            raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS", source_name)
        required_receipt_fields = (
            "command_receipt",
            "raw_stdout_sha256",
            "raw_stderr_sha256",
            "git_tree",
        )
        if row.get("status") != "PASS" or any(not row.get(field) for field in required_receipt_fields):
            raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS", row["test_id"])
        expected_diagnostic = specification.get("expected_diagnostic")
        if expected_diagnostic and row.get("actual_diagnostic") != expected_diagnostic:
            raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS", row["test_id"])


def assert_independent_closure(
    closure_register: dict[str, Any], verifier_receipt: dict[str, Any] | None
) -> None:
    """Forbid a builder-owned or missing receipt from claiming verified closure."""
    claims_closed = any(
        finding.get("closure_status") == "closed_verified"
        for finding in closure_register.get("findings", [])
    )
    if not claims_closed:
        return
    if (
        verifier_receipt is None
        or verifier_receipt.get("status") != "PASS"
        or verifier_receipt.get("verifier_owner") != "independent_verifier"
    ):
        raise CanaryGovernanceError("BA11_SELF_CERTIFICATION_FORBIDDEN")
