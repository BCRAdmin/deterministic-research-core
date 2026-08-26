"""Frozen-safe REIT primary-text capability declaration.

The current BA3/RFC-0010 plan binds the SEC CompanyFacts and exchange-price
captures only.  Adding filing-index or exhibit identities would change the
frozen acquisition contract, so Alpha v1 deliberately exposes no text metric.
"""

from __future__ import annotations

PRIMARY_TEXT_SOURCE_PROFILE = {
    "contract_id": "room16.alpha.reit_primary_text_source_profile",
    "contract_version": 1,
    "status": "TEXT_SOURCE_PROFILE_UNAVAILABLE_WITHOUT_FROZEN_CHANGE",
    "provider": "sec",
    "capture_before_extraction_required": True,
    "live_response_parsing_allowed": False,
    "ticker_specific_urls_or_rules": False,
    "reason": (
        "The frozen SourceAcquisitionIR has no optional, dynamically discovered "
        "SEC filing-index/exhibit acquisition stage."
    ),
    "frozen_contracts_modified": False,
}

UNSUPPORTED_TEXT_METRICS = (
    "reported_ffo",
    "reported_core_ffo",
    "reported_affo",
    "reported_noi",
    "reported_same_store_noi",
    "reported_occupancy",
    "reported_rent_growth",
    "reported_development_pipeline",
    "reported_dispositions",
)

