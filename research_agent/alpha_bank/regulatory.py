"""Capture-first regulatory source policy for the Alpha Bank archetype."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable


REGULATORY_SOURCE_PROFILE: dict[str, Any] = {
    "contract_id": "room16.alpha.bank_regulatory_source_profile",
    "contract_version": 1,
    "provider": "ffiec_nic_holding_company",
    "report_family": "FR_Y_9C",
    "capture_before_parse_required": True,
    "offline_replay_required": True,
    "status": "REGULATORY_SOURCE_UNAVAILABLE_WITHOUT_FROZEN_CHANGE",
    "reason": (
        "The current FFIEC/NIC bulk distribution is not represented by the "
        "frozen RFC-0010 acquisition planner; direct parser-side fetches are forbidden."
    ),
    "live_response_parsing_allowed": False,
    "ticker_or_rssd_hardcoding_allowed": False,
}

REGULATORY_MAPPING_REGISTRY: dict[str, Any] = {
    "contract_id": "room16.alpha.bank_regulatory_mapping_registry",
    "contract_version": 1,
    "active": False,
    "activation_condition": "captured FFIEC/NIC bytes plus official current MDRM dictionary",
    "mappings": [],
    "required_lineage": [
        "mdrm_code", "official_label", "report_family", "report_period",
        "value", "unit", "regulatory_basis", "source_file_sha256",
        "row_rssd_id", "mapping_registry_sha256",
    ],
    "standardized_advanced_conflation_allowed": False,
}

REGULATORY_TARGETS = (
    "cet1_capital",
    "cet1_ratio_standardized",
    "cet1_ratio_advanced",
    "tier1_capital_ratio",
    "total_capital_ratio",
    "risk_weighted_assets",
    "tier1_leverage_ratio",
    "supplementary_leverage_ratio",
)


def normalize_legal_name(value: str) -> str:
    """Normalize issuer names without encoding issuer-specific aliases."""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", normalized).upper().split())


def resolve_unique_top_tier_entity(
    rows: Iterable[dict[str, Any]],
    legal_name: str,
    *,
    name_field: str = "legal_name",
    top_tier_field: str = "is_top_tier",
) -> dict[str, Any] | None:
    """Return one exact normalized top-tier match; ambiguity is unsupported."""
    target = normalize_legal_name(legal_name)
    matches = [
        row for row in rows
        if bool(row.get(top_tier_field))
        and normalize_legal_name(str(row.get(name_field) or "")) == target
    ]
    return dict(matches[0]) if len(matches) == 1 else None


def regulatory_diagnostics() -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "metric_id": metric,
            "status": "UNSUPPORTED",
            "reason": REGULATORY_SOURCE_PROFILE["status"],
            "regulatory_basis": "UNRESOLVED",
        }
        for metric in REGULATORY_TARGETS
    )
