from __future__ import annotations

from copy import deepcopy

import pytest

from research_agent.capabilities.market_registry import (
    MarketCapabilityError,
    get_jurisdiction_capability,
    get_provider_capability,
    load_market_capability_registry,
    supported_jurisdiction_codes,
    validate_market_capability_registry,
)


def test_registry_separates_supported_recognized_and_manual_capabilities() -> None:
    registry = load_market_capability_registry()
    assert registry["contractId"] == "room16.market_capability_registry"
    assert supported_jurisdiction_codes() == {"US", "HU"}
    assert supported_jurisdiction_codes(include_recognized=True) == {"US", "HU", "JP", "KR"}
    assert get_jurisdiction_capability("JP")["requiredAdapterId"] == "edinet"
    assert get_jurisdiction_capability("KR")["requiredAdapterId"] == "opendart"
    assert get_provider_capability("fred")["integrationStatus"] == "candidate_not_integrated"
    assert get_provider_capability("tradingview")["automaticUse"] == "forbidden"


def test_paid_and_dormant_providers_cannot_be_selected_automatically() -> None:
    registry = load_market_capability_registry()
    for provider in registry["providers"]:
        if provider["variableCost"] == "possible":
            assert provider["automaticUse"] in {
                "explicit_only",
                "forbidden_without_data_go",
                "forbidden_until_gap_review",
            }
        if provider["integrationStatus"] in {
            "candidate_not_integrated",
            "paused_no_cost",
            "reserve_not_integrated",
            "manual_only",
        }:
            assert provider["authorityUse"] is False


def test_registry_rejects_paid_provider_auto_selection() -> None:
    registry = deepcopy(load_market_capability_registry())
    massive = next(item for item in registry["providers"] if item["providerId"] == "massive")
    massive["automaticUse"] = "allowed"
    with pytest.raises(MarketCapabilityError, match="paid_provider_must_be_explicit"):
        validate_market_capability_registry(registry)


def test_registry_rejects_silent_vendor_fallback_policy() -> None:
    registry = deepcopy(load_market_capability_registry())
    registry["policies"]["vendorFundamentalsFallbackAllowed"] = True
    with pytest.raises(MarketCapabilityError, match="market_capability_registry_contract_invalid"):
        validate_market_capability_registry(registry)
