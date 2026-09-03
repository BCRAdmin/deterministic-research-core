"""Append-only registry and fail-closed guard for frozen profile authorities."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .integrity import SHA256_RE, validate_hashed_document, with_self_hash

FREEZE_CONTRACT_ID = "room16.profile_freeze_authority@1"


def build_freeze_authority(**fields: Any) -> dict[str, Any]:
    body = {"contract_id": FREEZE_CONTRACT_ID, "contract_version": 1, **fields}
    return with_self_hash(body, "freeze_authority_sha256")


class FrozenProfileRegistry:
    """In-memory append-only view; durable callers persist each authority by full hash."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, int], dict[str, Any]] = {}
        self._by_hash: dict[str, dict[str, Any]] = {}

    def register(self, authority: Mapping[str, Any]) -> str:
        digest = validate_freeze_authority(authority)
        key = (str(authority["profile_family"]), int(authority["profile_version"]))
        current = self._by_key.get(key)
        if current is not None and current["freeze_authority_sha256"] != digest:
            raise ValueError("FROZEN_FAMILY_VERSION_MUTATION_BLOCKED")
        self._by_key[key] = deepcopy(dict(authority))
        self._by_hash[digest] = deepcopy(dict(authority))
        return digest

    def resolve(self, digest: str) -> dict[str, Any]:
        if digest not in self._by_hash:
            raise ValueError("UNKNOWN_FREEZE_AUTHORITY")
        return deepcopy(self._by_hash[digest])

    def resolve_version(self, family: str, version: int) -> dict[str, Any]:
        value = self._by_key.get((family, version))
        if value is None:
            raise ValueError("UNKNOWN_FROZEN_PROFILE_VERSION")
        return deepcopy(value)


def validate_freeze_authority(authority: Mapping[str, Any]) -> str:
    if authority.get("contract_id") != FREEZE_CONTRACT_ID:
        raise ValueError("UNKNOWN_FREEZE_AUTHORITY")
    required_true = (
        "immutable",
        "semantic_mutation_requires_new_profile_version",
        "threshold_mutation_requires_new_profile_version",
    )
    if any(authority.get(field) is not True for field in required_true):
        raise ValueError("FREEZE_IMMUTABILITY_REQUIRED")
    if any(
        authority.get(field) is not False
        for field in ("product_cutover_authorized", "release_authorized")
    ):
        raise ValueError("FREEZE_SCOPE_ESCALATION_BLOCKED")
    for field, value in authority.items():
        if field.endswith("_sha256") and field != "freeze_authority_sha256":
            if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
                raise ValueError(f"FREEZE_BINDING_INVALID:{field}")
    return validate_hashed_document(authority, hash_field="freeze_authority_sha256")


def guard_frozen_profile(
    authority: Mapping[str, Any], *, expected_bindings: Mapping[str, str]
) -> str:
    digest = validate_freeze_authority(authority)
    for field, expected in expected_bindings.items():
        if authority.get(field) != expected:
            raise ValueError(f"FROZEN_PROFILE_BINDING_MISMATCH:{field}")
    return digest
