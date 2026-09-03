"""Append-only sector profile authority primitives for Room16."""

from .contracts import (
    build_sector_profile_contract,
    selection_receipt,
    validate_sector_profile_contract,
)
from .freeze_registry import FrozenProfileRegistry
from .integrity import canonical_sha256, validate_hashed_document

__all__ = [
    "FrozenProfileRegistry",
    "build_sector_profile_contract",
    "canonical_sha256",
    "selection_receipt",
    "validate_hashed_document",
    "validate_sector_profile_contract",
]
