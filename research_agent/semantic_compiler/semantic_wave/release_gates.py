"""Semantic-wave release gates that operate above the frozen registries."""

from __future__ import annotations

import re
from typing import Any


class SemanticReleaseGateError(ValueError):
    """Raised when a semantic-wave candidate violates a release invariant."""


CANARY_NAMESPACE = re.compile(r"(^|[._:-])(wm|cost|abt)($|[._:-])", re.IGNORECASE)


def assert_no_canary_specific_registry_branch(payload: dict[str, Any]) -> None:
    """Block definitions or bindings whose namespace is tied to a canary ticker."""

    surfaces: list[tuple[str, str]] = []
    for item in payload.get("metric_definitions") or []:
        surfaces.append(("metric_definition", str(item.get("definition_id") or "")))
        surfaces.extend(
            ("metric_pattern", str(value)) for value in item.get("instance_patterns") or []
        )
    for item in payload.get("formula_definitions") or []:
        surfaces.append(
            ("formula_definition", str(item.get("formula_definition_id") or ""))
        )
        surfaces.extend(
            ("formula_alias", str(value)) for value in item.get("legacy_aliases") or []
        )
    for key, identifier in (
        ("claim_kind_definitions", "claim_kind_id"),
        ("decision_node_definitions", "decision_node_definition_id"),
        ("risk_definitions", "risk_definition_id"),
        ("permission_corridor_definitions", "permission_corridor_definition_id"),
    ):
        surfaces.extend(
            (key, str(item.get(identifier) or "")) for item in payload.get(key) or []
        )
    violations = sorted(
        f"{surface}:{value}" for surface, value in surfaces if CANARY_NAMESPACE.search(value)
    )
    if violations:
        raise SemanticReleaseGateError(
            f"canary_specific_registry_branch:{'|'.join(violations)}"
        )


def assert_release_gate(
    *,
    replay_results: dict[str, dict[str, Any]],
    registry_payload: dict[str, Any],
) -> None:
    assert_no_canary_specific_registry_branch(registry_payload)
    expected = {"WM", "COST", "ABT"}
    if set(replay_results) != expected:
        raise SemanticReleaseGateError("cross_company_replay_set_incomplete")
    for ticker, result in sorted(replay_results.items()):
        if not all(result.get("gates", {}).values()):
            raise SemanticReleaseGateError(f"semantic_replay_gate_failed:{ticker}")
        if result.get("archive_sha256_before") != result.get("archive_sha256_after"):
            raise SemanticReleaseGateError(f"canary_archive_changed:{ticker}")
        if result.get("ba9", {}).get("roundtrip_sha256") != result.get("ba9", {}).get(
            "legacy_payload_sha256"
        ):
            raise SemanticReleaseGateError(f"lossy_decision_roundtrip:{ticker}")
