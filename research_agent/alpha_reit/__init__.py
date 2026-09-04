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
from .v3 import REIT_V3_PROFILE, SOURCE_EXTENSION_CONTRACT

# BEGIN ROOM16 REIT V4 PRIMARY TEXT EXPORTS
from .primary_text_v4 import (
    PARSER_CONTRACT as PRIMARY_TEXT_PARSER_V4_CONTRACT,
    PARSER_CONTRACT_SHA256 as PRIMARY_TEXT_PARSER_V4_SHA256,
    classify_ffo_label as classify_ffo_label_v4,
    parse_primary_text_candidates_v4,
    select_reported_ffo_v4,
    validate_primary_text_candidate_v4,
)

__all__ = [
    "ACCEPTANCE_THRESHOLDS_V2",
    "ACCEPTANCE_THRESHOLDS_V2_SHA256",
    "FRESHNESS_POLICY",
    "FORMULA_REGISTRY",
    "MAPPING_REGISTRY",
    "PRIMARY_TEXT_SOURCE_PROFILE",
    "PRIMARY_TEXT_PARSER_V4_CONTRACT",
    "PRIMARY_TEXT_PARSER_V4_SHA256",
    "RANKING_PROFILE",
    "REIT_V2_DESCRIPTOR_HASH",
    "REIT_V2_PROFILE",
    "REIT_V3_PROFILE",
    "SOURCE_EXTENSION_CONTRACT",
    "UNSUPPORTED_TEXT_METRICS",
    "build_alpha_reit_bundle",
    "build_reit_semantic_artifacts",
    "classify_ffo_label_v4",
    "guard_reit_validation_action",
    "parse_primary_text_candidates_v4",
    "seal_reit_v2_candidate",
    "select_reported_ffo_v4",
    "validate_raw_candidate",
    "validate_primary_text_candidate_v4",
]
# END ROOM16 REIT V4 PRIMARY TEXT EXPORTS
