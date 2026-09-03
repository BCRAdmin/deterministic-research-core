"""Canonical integrity checks shared by candidate and freeze authorities."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def with_self_hash(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    if field in value:
        raise ValueError(f"SELF_HASH_FIELD_ALREADY_PRESENT:{field}")
    body = dict(value)
    return {**body, field: canonical_sha256(body)}


def validate_hashed_document(
    value: Mapping[str, Any], *, hash_field: str, expected_hash: str | None = None
) -> str:
    supplied = value.get(hash_field)
    if not isinstance(supplied, str) or not SHA256_RE.fullmatch(supplied):
        raise ValueError(f"INVALID_SELF_HASH:{hash_field}")
    calculated = canonical_sha256({key: item for key, item in value.items() if key != hash_field})
    if supplied != calculated:
        raise ValueError(f"SELF_HASH_MISMATCH:{hash_field}")
    if expected_hash is not None and supplied != expected_hash:
        raise ValueError(f"AUTHORITY_HASH_NOT_AUTHORIZED:{hash_field}")
    return supplied
