"""Research-owned loader and binders for Registry Foundation 1.1.0."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_bytes, sha256_json

from .contracts import (
    ClaimKindDefinition,
    DecisionNodeDefinition,
    FormulaDefinition,
    MetricDefinition,
    PermissionCorridorDefinition,
    RiskDefinition,
)

AUTHORITY_PATH = Path(__file__).with_name("config") / "registry_foundation_v1_1.json"


class SemanticRegistryError(ValueError):
    """Raised when vNext authority or an identifier binding is invalid."""


class SemanticRegistryAuthority:
    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("contract_id") != "room16.compiler.registry_foundation":
            raise SemanticRegistryError("invalid_registry_foundation_contract")
        if payload.get("contract_version") != 1 or payload.get("version") != "1.1.0":
            raise SemanticRegistryError("registry_foundation_version_unsupported")
        if payload.get("owner") != "research" or payload.get("authority_bundle_version") != 3:
            raise SemanticRegistryError("registry_foundation_owner_or_abi_invalid")
        declared = payload.get("authority_sha256")
        body = {key: value for key, value in payload.items() if key != "authority_sha256"}
        if declared != sha256_json(body):
            raise SemanticRegistryError("registry_foundation_hash_mismatch")
        self.payload = payload
        self.authority_sha256 = str(declared)
        self.metric_definitions = self._models("metric_definitions", MetricDefinition, "definition_id")
        self.formula_definitions = self._models(
            "formula_definitions", FormulaDefinition, "formula_definition_id"
        )
        self.claim_definitions = self._models("claim_kind_definitions", ClaimKindDefinition, "claim_kind_id")
        self.decision_definitions = self._models(
            "decision_node_definitions", DecisionNodeDefinition, "decision_node_definition_id"
        )
        self.risk_definitions = self._models("risk_definitions", RiskDefinition, "risk_definition_id")
        self.permission_definitions = self._models(
            "permission_corridor_definitions",
            PermissionCorridorDefinition,
            "permission_corridor_definition_id",
        )

    def _models(self, key: str, model: Any, id_field: str) -> dict[str, Any]:
        values = [model.model_validate(item) for item in self.payload.get(key, [])]
        ids = [getattr(item, id_field) for item in values]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise SemanticRegistryError(f"{key}_must_be_unique_and_sorted")
        return dict(zip(ids, values, strict=True))

    @classmethod
    def load(cls, path: Path = AUTHORITY_PATH) -> "SemanticRegistryAuthority":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def canonical_document(self) -> bytes:
        return canonical_bytes(self.payload)

    def canonical_document_sha256(self) -> str:
        return sha256_bytes(self.canonical_document())

    def bind_metric(self, legacy_id: str) -> tuple[str, str]:
        blocked = ("event_", "unmapped_", "unknown_", "positional_")
        if legacy_id.startswith(blocked):
            return "metric.quarantined_unknown", "quarantined_unknown"
        matches: list[str] = []
        for definition in self.metric_definitions.values():
            for pattern in definition.instance_patterns:
                if re.fullmatch(pattern, legacy_id):
                    matches.append(definition.definition_id)
                    break
        matches = sorted(set(matches))
        if len(matches) != 1:
            if not matches:
                return "metric.quarantined_unknown", "quarantined_unknown"
            return "metric.semantic_collision", "semantic_collision"
        definition_id = matches[0]
        binding_type = "canonical_definition" if legacy_id == definition_id.removeprefix("metric.") else "instance_binding"
        return definition_id, binding_type

    def bind_formula(self, legacy_id: str) -> str:
        matches = [
            item.formula_definition_id
            for item in self.formula_definitions.values()
            if legacy_id == item.formula_definition_id.removeprefix("formula.")
            or legacy_id in item.legacy_aliases
        ]
        if len(matches) != 1:
            raise SemanticRegistryError(
                "formula_semantic_collision" if matches else "unknown_formula_id"
            )
        return matches[0]

    def bind_claim_kind(self, legacy_id: str) -> str:
        candidate = f"claim.{legacy_id}"
        if candidate not in self.claim_definitions:
            raise SemanticRegistryError("unknown_claim_kind")
        return candidate

    def require_decision_definition(self, definition_id: str) -> DecisionNodeDefinition:
        try:
            return self.decision_definitions[definition_id]
        except KeyError as exc:
            raise SemanticRegistryError("unknown_decision_node") from exc

    def bind_decision_input(self, input_type: str) -> str:
        bindings = {
            "current_risk": "decision.input.risk",
            "operating_kpi": "decision.input.operating_signal",
        }
        try:
            definition_id = bindings[input_type]
        except KeyError as exc:
            raise SemanticRegistryError("unknown_decision_input_kind") from exc
        self.require_decision_definition(definition_id)
        return definition_id

    def require_risk_definition(self, definition_id: str) -> RiskDefinition:
        try:
            return self.risk_definitions[definition_id]
        except KeyError as exc:
            raise SemanticRegistryError("unknown_risk_definition") from exc

    def require_permission_definition(
        self, definition_id: str
    ) -> PermissionCorridorDefinition:
        try:
            return self.permission_definitions[definition_id]
        except KeyError as exc:
            raise SemanticRegistryError("unknown_permission_corridor_definition") from exc


def verify_product_mirror(*, authority_path: Path, mirror_path: Path, lock_path: Path) -> dict[str, Any]:
    authority = SemanticRegistryAuthority.load(authority_path)
    mirror = json.loads(mirror_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    checks = {
        "canonical_bytes_equal": canonical_bytes(mirror) == authority.canonical_document(),
        "authority_sha256_equal": mirror.get("authority_sha256") == authority.authority_sha256,
        "authority_owner_research": lock.get("authority_owner") == "research",
        "mirror_mode_read_only": lock.get("mirror_mode") == "hash_verified_read_only",
        "canonical_sha256_equal": lock.get("canonical_document_sha256") == authority.canonical_document_sha256(),
        "registry_version_equal": lock.get("registry_foundation_version") == "1.1.0",
    }
    if not all(checks.values()):
        raise SemanticRegistryError(f"product_mirror_conformance_failed:{checks}")
    return {"status": "pass", "checks": checks, "authority_sha256": authority.authority_sha256}
