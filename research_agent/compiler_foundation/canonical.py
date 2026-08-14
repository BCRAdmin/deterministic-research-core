"""Cross-language canonical JSON and SHA-256 semantics for compiler IR."""

from __future__ import annotations

import hashlib
import json
import math
from enum import Enum
from typing import Any

from pydantic import BaseModel


class CanonicalizationError(ValueError):
    """Raised when a value has no portable canonical JSON representation."""


def normalize(value: Any) -> Any:
    """Return a recursively normalized, JSON-safe value.

    Object keys are sorted during serialization, array order is preserved,
    negative zero is normalized to zero, and non-finite numbers fail closed.
    """

    if isinstance(value, BaseModel):
        return normalize(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return normalize(value.value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise CanonicalizationError("unpaired UTF-16 surrogates are forbidden")
        return value
    if isinstance(value, int):
        if abs(value) > 9_007_199_254_740_991:
            raise CanonicalizationError("integers outside the cross-language safe range are forbidden")
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError("non-finite numbers are forbidden")
        return 0 if value == 0 else value
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError("object keys must be strings")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in key):
                raise CanonicalizationError("unpaired UTF-16 surrogates are forbidden")
        for key in sorted(value, key=lambda item: item.encode("utf-16-be", "surrogatepass")):
            item = value[key]
            result[key] = normalize(item)
        return result
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    raise CanonicalizationError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        normalize(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=False,
    )


def canonical_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))
