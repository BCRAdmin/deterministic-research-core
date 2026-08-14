"""Research-owned, fail-closed Registry Authority loader and mirror verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, sha256_bytes, sha256_json
from .contracts import ContractError, RegistryEnvelope

CONFIG_DIR = Path(__file__).with_name("config")
AUTHORITY_PATH = CONFIG_DIR / "registry_authority.json"


class RegistryAuthority:
    def __init__(self, payload: dict[str, Any]) -> None:
        if payload.get("contract_id") != "room16.compiler.registry_authority":
            raise ContractError("invalid Registry Authority contract id")
        if payload.get("contract_version") != 1 or payload.get("owner") != "research":
            raise ContractError("unsupported Registry Authority version or owner")
        raw_registries = payload.get("registries")
        if not isinstance(raw_registries, list) or not raw_registries:
            raise ContractError("Registry Authority must contain registries")
        self.registries = tuple(RegistryEnvelope.model_validate(item) for item in raw_registries)
        ids = [item.registry_id for item in self.registries]
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise ContractError("registries must be unique and sorted")
        for registry in self.registries:
            registry.verify_hash()
        declared = payload.get("authority_sha256")
        body = {key: value for key, value in payload.items() if key != "authority_sha256"}
        if not isinstance(declared, str) or declared != sha256_json(body):
            raise ContractError("Registry Authority hash mismatch")
        self.payload = payload
        self.authority_sha256 = declared

    @classmethod
    def load(cls, path: Path = AUTHORITY_PATH) -> "RegistryAuthority":
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def registry(self, registry_id: str) -> RegistryEnvelope:
        for registry in self.registries:
            if registry.registry_id == registry_id:
                return registry
        raise ContractError(f"unknown registry id: {registry_id}")

    def resolve(self, registry_id: str, entry_id: str) -> dict[str, Any]:
        return self.registry(registry_id).resolve(entry_id).definition

    def canonical_document(self) -> bytes:
        return canonical_bytes(self.payload)


def verify_product_mirror(authority_path: Path, mirror_path: Path, lock_path: Path) -> dict[str, Any]:
    authority = RegistryAuthority.load(authority_path)
    authority_bytes = authority.canonical_document()
    mirror_payload = json.loads(mirror_path.read_text(encoding="utf-8"))
    mirror_bytes = canonical_bytes(mirror_payload)
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    expected_bytes_sha = sha256_bytes(authority_bytes)
    checks = {
        "canonical_bytes_equal": mirror_bytes == authority_bytes,
        "authority_sha256_equal": mirror_payload.get("authority_sha256") == authority.authority_sha256,
        "lock_owner_is_research": lock.get("authority_owner") == "research",
        "lock_mode_is_hash_verified_mirror": lock.get("mirror_mode") == "hash_verified_read_only",
        "lock_canonical_sha256_equal": lock.get("canonical_document_sha256") == expected_bytes_sha,
    }
    if not all(checks.values()):
        raise ContractError(f"Product Registry mirror conformance failed: {checks}")
    return {"status": "pass", "authority_sha256": authority.authority_sha256, "checks": checks}
