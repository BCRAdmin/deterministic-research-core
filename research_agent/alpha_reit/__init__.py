"""Alpha-only REIT projection successor above the frozen BA12 runtime."""

from .compiler import build_alpha_reit_bundle
from .primary_text import PRIMARY_TEXT_SOURCE_PROFILE, UNSUPPORTED_TEXT_METRICS
from .projection import (
    FRESHNESS_POLICY,
    FORMULA_REGISTRY,
    MAPPING_REGISTRY,
    RANKING_PROFILE,
    build_reit_semantic_artifacts,
)
from .v2 import (
    ACCEPTANCE_THRESHOLDS_V2,
    ACCEPTANCE_THRESHOLDS_V2_SHA256,
    REIT_V2_DESCRIPTOR_HASH,
    REIT_V2_PROFILE,
    guard_reit_validation_action,
    seal_reit_v2_candidate,
    validate_raw_candidate,
)

__all__ = [
    "ACCEPTANCE_THRESHOLDS_V2",
    "ACCEPTANCE_THRESHOLDS_V2_SHA256",
    "FRESHNESS_POLICY",
    "FORMULA_REGISTRY",
    "MAPPING_REGISTRY",
    "PRIMARY_TEXT_SOURCE_PROFILE",
    "RANKING_PROFILE",
    "REIT_V2_DESCRIPTOR_HASH",
    "REIT_V2_PROFILE",
    "UNSUPPORTED_TEXT_METRICS",
    "build_alpha_reit_bundle",
    "build_reit_semantic_artifacts",
    "guard_reit_validation_action",
    "seal_reit_v2_candidate",
    "validate_raw_candidate",
]
