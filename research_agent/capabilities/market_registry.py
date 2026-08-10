from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional


REGISTRY_PATH = Path(__file__).with_name("market_capabilities.json")
CONTRACT_ID = "room16.market_capability_registry"
JURISDICTION_FIELDS = frozenset(
    {
        "code",
        "label",
        "status",
        "identityProviderId",
        "fundamentalsProviderId",
        "priceProviderIds",
        "defaultPriceProviderId",
        "requiredAdapterId",
        "requiredConfiguration",
        "message",
    }
)
PROVIDER_FIELDS = frozenset(
    {
        "providerId",
        "label",
        "roles",
        "integrationStatus",
        "authorityUse",
        "variableCost",
        "credentialMode",
        "automaticUse",
        "semantics",
        "limitations",
    }
)
POLICY_FIELDS = frozenset(
    {
        "vendorFundamentalsFallbackAllowed",
        "tickerSpecificAdapterExceptionsAllowed",
        "automaticPaidProviderSelectionAllowed",
        "automaticCountryAdapterCreationAllowed",
        "unsupportedMarketAnalysisAllowed",
        "resolverEvidenceMayBecomeReportEvidence",
    }
)


class MarketCapabilityError(RuntimeError):
    """Raised when the canonical capability registry is invalid or incomplete."""


def _string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def validate_market_capability_registry(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "contractId",
        "contractVersion",
        "updatedAt",
        "jurisdictions",
        "providers",
        "policies",
    }:
        raise MarketCapabilityError("market_capability_registry_shape_invalid")
    if not (
        value.get("schemaVersion") == 1
        and value.get("contractId") == CONTRACT_ID
        and value.get("contractVersion") == 1
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value.get("updatedAt") or ""))
        and isinstance(value.get("jurisdictions"), list)
        and isinstance(value.get("providers"), list)
        and isinstance(value.get("policies"), dict)
        and set(value["policies"]) == POLICY_FIELDS
        and all(item is False for item in value["policies"].values())
    ):
        raise MarketCapabilityError("market_capability_registry_contract_invalid")
    providers: dict[str, dict[str, Any]] = {}
    for provider in value["providers"]:
        if not isinstance(provider, dict) or set(provider) != PROVIDER_FIELDS:
            raise MarketCapabilityError("market_provider_capability_invalid")
        provider_id = str(provider.get("providerId") or "")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,31}", provider_id) or provider_id in providers:
            raise MarketCapabilityError("market_provider_id_invalid")
        if not (
            isinstance(provider.get("label"), str)
            and provider["label"]
            and _string_list(provider.get("roles"))
            and isinstance(provider.get("integrationStatus"), str)
            and isinstance(provider.get("authorityUse"), bool)
            and isinstance(provider.get("variableCost"), str)
            and isinstance(provider.get("credentialMode"), str)
            and isinstance(provider.get("automaticUse"), str)
            and _string_list(provider.get("semantics"))
            and _string_list(provider.get("limitations"))
        ):
            raise MarketCapabilityError("market_provider_capability_invalid")
        if provider["variableCost"] == "possible" and provider["automaticUse"] not in {
            "explicit_only",
            "forbidden_without_data_go",
            "forbidden_until_gap_review",
        }:
            raise MarketCapabilityError("paid_provider_must_be_explicit")
        if provider["integrationStatus"] in {
            "candidate_not_integrated",
            "paused_no_cost",
            "reserve_not_integrated",
            "manual_only",
        } and provider["authorityUse"]:
            raise MarketCapabilityError("inactive_provider_cannot_be_authority")
        providers[provider_id] = provider
    jurisdictions: dict[str, dict[str, Any]] = {}
    for jurisdiction in value["jurisdictions"]:
        if not isinstance(jurisdiction, dict) or set(jurisdiction) != JURISDICTION_FIELDS:
            raise MarketCapabilityError("market_jurisdiction_capability_invalid")
        code = str(jurisdiction.get("code") or "")
        status = jurisdiction.get("status")
        if not re.fullmatch(r"[A-Z]{2}", code) or code in jurisdictions or status not in {
            "supported",
            "recognized_unsupported",
        }:
            raise MarketCapabilityError("market_jurisdiction_capability_invalid")
        if not (
            isinstance(jurisdiction.get("label"), str)
            and jurisdiction["label"]
            and _string_list(jurisdiction.get("priceProviderIds"))
            and isinstance(jurisdiction.get("requiredConfiguration"), list)
            and all(isinstance(item, str) and item for item in jurisdiction["requiredConfiguration"])
            and isinstance(jurisdiction.get("message"), str)
            and jurisdiction["message"]
        ):
            raise MarketCapabilityError("market_jurisdiction_capability_invalid")
        referenced = [
            jurisdiction.get("identityProviderId"),
            jurisdiction.get("fundamentalsProviderId"),
            jurisdiction.get("defaultPriceProviderId"),
            *jurisdiction["priceProviderIds"],
        ]
        for provider_id in {item for item in referenced if item and item != "resolver_only"}:
            if provider_id not in providers:
                raise MarketCapabilityError(f"market_provider_reference_missing:{provider_id}")
        if status == "supported":
            if not jurisdiction.get("fundamentalsProviderId") or not jurisdiction.get(
                "defaultPriceProviderId"
            ):
                raise MarketCapabilityError("supported_jurisdiction_provider_missing")
            if jurisdiction.get("requiredAdapterId") is not None:
                raise MarketCapabilityError("supported_jurisdiction_adapter_gap_invalid")
        elif not jurisdiction.get("requiredAdapterId") or jurisdiction.get(
            "fundamentalsProviderId"
        ) is not None:
            raise MarketCapabilityError("unsupported_jurisdiction_gap_invalid")
        jurisdictions[code] = jurisdiction
    if set(jurisdictions) != {"US", "HU", "JP", "KR"}:
        raise MarketCapabilityError("market_jurisdiction_baseline_incomplete")
    return value


@lru_cache(maxsize=1)
def load_market_capability_registry(path: Optional[Path] = None) -> dict[str, Any]:
    target = path or REGISTRY_PATH
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketCapabilityError("market_capability_registry_unreadable") from exc
    return validate_market_capability_registry(value)


def get_jurisdiction_capability(code: str) -> dict[str, Any]:
    normalized = str(code or "").strip().upper()
    for item in load_market_capability_registry()["jurisdictions"]:
        if item["code"] == normalized:
            return item
    raise MarketCapabilityError(f"jurisdiction_not_registered:{normalized or 'missing'}")


def get_provider_capability(provider_id: str) -> dict[str, Any]:
    normalized = str(provider_id or "").strip().lower()
    for item in load_market_capability_registry()["providers"]:
        if item["providerId"] == normalized:
            return item
    raise MarketCapabilityError(f"provider_not_registered:{normalized or 'missing'}")


def supported_jurisdiction_codes(*, include_recognized: bool = False) -> set[str]:
    allowed_statuses = {"supported", "recognized_unsupported"} if include_recognized else {"supported"}
    return {
        item["code"]
        for item in load_market_capability_registry()["jurisdictions"]
        if item["status"] in allowed_statuses
    }
