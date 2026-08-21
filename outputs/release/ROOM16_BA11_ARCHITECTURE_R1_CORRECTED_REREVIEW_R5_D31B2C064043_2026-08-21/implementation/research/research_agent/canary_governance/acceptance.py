"""Independent R4 acceptance coverage and self-certification gates."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

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
    """Require one exact collected and executed pytest node for every row."""
    required_rows = required.get("rows", [])
    executed_rows = executed.get("rows", [])
    required_ids = [row.get("test_id") for row in required_rows]
    executed_ids = [row.get("test_id") for row in executed_rows]
    if set(required_ids) - set(executed_ids):
        raise CanaryGovernanceError("BA11_ACCEPTANCE_REQUIREMENT_MISSING")
    if any(count != 1 for count in Counter(executed_ids).values()):
        raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS")
    nodeids = [row.get("pytest_nodeid") for row in executed_rows]
    if any(not nodeid or "::test_" not in nodeid for nodeid in nodeids):
        raise CanaryGovernanceError("BA11_TEST_ID_UNRESOLVED")
    if any(count != 1 for count in Counter(nodeids).values()):
        raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS", "duplicate_nodeid")

    collection = executed.get("collection_manifest", {})
    collected_nodeids = tuple(collection.get("nodeids", ()))
    execution_report = executed.get("execution_report", {})
    execution_results = execution_report.get("results", [])
    result_by_nodeid = {
        row.get("pytest_nodeid"): row for row in execution_results if row.get("pytest_nodeid")
    }
    for nodeid in nodeids:
        if nodeid not in collected_nodeids or nodeid not in result_by_nodeid:
            raise CanaryGovernanceError("BA11_TEST_ID_UNRESOLVED", str(nodeid))
    expected_collection_sha = sha256_json(
        {key: value for key, value in collection.items() if key != "manifest_sha256"}
    )
    expected_report_sha = sha256_json(
        {key: value for key, value in execution_report.items() if key != "report_sha256"}
    )
    if (
        collection.get("manifest_sha256") != expected_collection_sha
        or execution_report.get("report_sha256") != expected_report_sha
    ):
        raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS", "report_hash")
    by_id = {row["test_id"]: row for row in executed_rows}
    for specification in required_rows:
        row = by_id[specification["test_id"]]
        nodeid = row["pytest_nodeid"]
        source_name = nodeid.split("::")[-1].split("[")[0]
        if source_name in {"test_full_suite", "test_generic_suite", "test_pytest"}:
            raise CanaryGovernanceError("BA11_ACCEPTANCE_MAPPING_AMBIGUOUS", source_name)
        if source_name not in source_test_names:
            raise CanaryGovernanceError("BA11_TEST_ID_UNRESOLVED", nodeid)
        result = result_by_nodeid[nodeid]
        required_receipt_fields = (
            "command_receipt",
            "collect_manifest_sha256",
            "execution_result_sha256",
            "raw_stdout_sha256",
            "raw_stderr_sha256",
            "git_tree",
        )
        if (
            row.get("status") != "PASS"
            or result.get("status") != "PASS"
            or result.get("exit_code") != 0
            or row.get("collect_manifest_sha256") != collection["manifest_sha256"]
            or row.get("execution_result_sha256") != sha256_json(result)
            or any(not row.get(field) for field in required_receipt_fields)
        ):
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
