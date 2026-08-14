"""Deterministic BA3 compile-intake and source-acquisition planning."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from research_agent.capabilities.market_registry import (
    REGISTRY_PATH,
    get_jurisdiction_capability,
    get_provider_capability,
    load_market_capability_registry,
)
from research_agent.compiler_foundation.contracts import (
    CompilerLayer,
    DiagnosticIR,
    ReleaseEffect,
    SemanticSeverity,
)
from research_agent.compiler_foundation.registry import RegistryAuthority

from .adapter_contract import SourceAdapterContractError, verify_adapter_implementation
from .contracts import (
    MARKET_CAPABILITY_REGISTRY_SHA256,
    CompilePolicyIR,
    CompileRequestIR,
    ResolvedInstrumentIR,
    SourceAcquisitionIR,
    SourceAcquisitionItemIR,
)
from .registry_binding import SourceAdapterBindingError, source_types_for_provider

REQUIRED_FRONTEND_ROLES = ("fundamentals", "issuer_identity", "market_prices")
REGISTERED_DIAGNOSTICS = {
    "CONTRACT_HASH_MISMATCH": "contract_hash_mismatch",
    "UNKNOWN_REGISTRY_ID": "unknown_registry_id",
    "VERSION_UNSUPPORTED": "version_unsupported",
}


class SourceFrontendError(RuntimeError):
    """Fail-closed BA3 failure carrying a Foundation DiagnosticIR."""

    def __init__(self, diagnostic: DiagnosticIR) -> None:
        self.diagnostic = diagnostic
        super().__init__(f"{diagnostic.code}: {diagnostic.message}")


def _fail(
    *,
    code: str,
    layer: CompilerLayer,
    pass_id: str,
    subject: str,
    message: str,
    root_cause: str,
) -> SourceFrontendError:
    if code not in REGISTERED_DIAGNOSTICS:
        raise RuntimeError(f"unregistered BA3 diagnostic code: {code}")
    return SourceFrontendError(
        DiagnosticIR(
            code=code,
            semantic_severity=SemanticSeverity.ERROR,
            release_effect=ReleaseEffect.COMPILE_BLOCK,
            layer=layer,
            pass_id=pass_id,
            subject_ref=subject,
            root_cause_ref=root_cause,
            fixture_refs=(f"ba3:negative:{root_cause}",),
            message=message,
            details={"diagnostic_registry_id": REGISTERED_DIAGNOSTICS[code]},
        )
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_capability_registry() -> dict[str, Any]:
    if _file_sha256(REGISTRY_PATH) != MARKET_CAPABILITY_REGISTRY_SHA256:
        raise _fail(
            code="CONTRACT_HASH_MISMATCH",
            layer=CompilerLayer.L0_COMPILE_INTAKE,
            pass_id="ba3.l0.freeze_compile_request",
            subject="room16.market_capability_registry",
            message="market capability registry differs from the BA3 bound snapshot",
            root_cause="market_capability_registry_hash_mismatch",
        )
    return load_market_capability_registry()


def _normalize_resolution(resolution: dict[str, Any]) -> ResolvedInstrumentIR:
    status = str(resolution.get("status") or "")
    if status != "supported" or resolution.get("runtimeReady") is False:
        required = str(resolution.get("requiredAdapter") or resolution.get("adapter") or "adapter")
        raise _fail(
            code="UNKNOWN_REGISTRY_ID",
            layer=CompilerLayer.L0_COMPILE_INTAKE,
            pass_id="ba3.l0.freeze_compile_request",
            subject=required,
            message=(
                "resolved instrument is not backed by a supported and ready official adapter; "
                "no compile request was created"
            ),
            root_cause="resolved_instrument_adapter_unavailable",
        )
    input_kind = str(resolution.get("inputKind") or resolution.get("input_kind") or "")
    input_value = str(resolution.get("input") or resolution.get("input_value") or "").strip()
    company_name = str(
        resolution.get("companyName") or resolution.get("company_name") or ""
    ).strip()
    if not company_name:
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L0_COMPILE_INTAKE,
            pass_id="ba3.l0.freeze_compile_request",
            subject=str(resolution.get("ticker") or "instrument"),
            message="resolver output is missing the canonical company name required by CompileRequestIR@1",
            root_cause="resolved_instrument_company_name_missing",
        )
    return ResolvedInstrumentIR(
        input_value=input_value,
        input_kind=input_kind,
        ticker=str(resolution.get("ticker") or "").upper(),
        company_name=company_name,
        exchange=str(resolution.get("exchange") or ""),
        exchange_code=(
            str(resolution.get("exchangeCode") or resolution.get("exchange_code") or "").upper()
            or None
        ),
        jurisdiction=str(resolution.get("jurisdiction") or "").upper(),
        isin=(str(resolution.get("isin") or "").upper() or None),
        wkn=(str(resolution.get("wkn") or "").upper() or None),
        resolution_source=str(
            resolution.get("source") or resolution.get("resolution_source") or ""
        ),
    )


def build_compile_request(
    resolution: dict[str, Any],
    *,
    as_of_date: str,
    allowed_provider_ids: tuple[str, ...],
    approved_paid_provider_ids: tuple[str, ...] = (),
    available_configuration_ids: tuple[str, ...] = (),
    network_mode: str = "offline_replay",
) -> CompileRequestIR:
    """Freeze trusted resolver output and compile policy before acquisition."""

    _validate_capability_registry()
    instrument = _normalize_resolution(resolution)
    capability = get_jurisdiction_capability(instrument.jurisdiction)
    if capability["status"] != "supported":
        raise _fail(
            code="UNKNOWN_REGISTRY_ID",
            layer=CompilerLayer.L0_COMPILE_INTAKE,
            pass_id="ba3.l0.freeze_compile_request",
            subject=str(capability.get("requiredAdapterId") or instrument.jurisdiction),
            message=capability["message"],
            root_cause="jurisdiction_adapter_not_integrated",
        )
    policy = CompilePolicyIR(
        network_mode=network_mode,
        allowed_provider_ids=tuple(sorted(allowed_provider_ids)),
        approved_paid_provider_ids=tuple(sorted(approved_paid_provider_ids)),
        available_configuration_ids=tuple(sorted(available_configuration_ids)),
    )
    return CompileRequestIR.create(
        instrument=instrument,
        as_of_date=as_of_date,
        policy=policy,
    )


def _allowed_source_types(provider_id: str) -> tuple[str, ...]:
    try:
        source_types = source_types_for_provider(provider_id)
    except SourceAdapterBindingError as exc:
        raise _fail(
            code="UNKNOWN_REGISTRY_ID",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.plan_source_acquisition",
            subject=provider_id,
            message="provider has no BA3 source-type binding",
            root_cause="source_adapter_binding_missing",
        ) from exc
    authority = RegistryAuthority.load()
    for source_type in source_types:
        try:
            authority.resolve("room16.registry.source", source_type)
        except ValueError as exc:
            raise _fail(
                code="UNKNOWN_REGISTRY_ID",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.plan_source_acquisition",
                subject=source_type,
                message="provider references an unknown Foundation source type",
                root_cause="foundation_source_type_unknown",
            ) from exc
    return source_types


def plan_source_acquisition(
    request: CompileRequestIR,
    *,
    price_provider_id: str | None = None,
) -> SourceAcquisitionIR:
    """Create a deterministic, no-fallback source plan from bound capabilities."""

    _validate_capability_registry()
    if request.market_capability_registry_sha256 != MARKET_CAPABILITY_REGISTRY_SHA256:
        raise _fail(
            code="CONTRACT_HASH_MISMATCH",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.plan_source_acquisition",
            subject="compile_request.market_capability_registry_sha256",
            message="compile request capability hash does not match the active bound registry",
            root_cause="compile_request_capability_hash_mismatch",
        )
    capability = get_jurisdiction_capability(request.instrument.jurisdiction)
    if capability["status"] != "supported":
        raise _fail(
            code="UNKNOWN_REGISTRY_ID",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.plan_source_acquisition",
            subject=str(capability.get("requiredAdapterId") or request.instrument.jurisdiction),
            message=capability["message"],
            root_cause="jurisdiction_adapter_not_integrated",
        )

    selected_price = str(price_provider_id or capability["defaultPriceProviderId"])
    if selected_price not in capability["priceProviderIds"]:
        raise _fail(
            code="UNKNOWN_REGISTRY_ID",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.plan_source_acquisition",
            subject=selected_price,
            message="requested price provider is not registered for this jurisdiction",
            root_cause="jurisdiction_provider_reference_unknown",
        )
    provider_ids = tuple(
        sorted(
            {
                str(capability["identityProviderId"]),
                str(capability["fundamentalsProviderId"]),
                selected_price,
            }
        )
    )
    if not set(provider_ids) <= set(request.policy.allowed_provider_ids):
        missing = sorted(set(provider_ids) - set(request.policy.allowed_provider_ids))
        raise _fail(
            code="UNKNOWN_REGISTRY_ID",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.plan_source_acquisition",
            subject=",".join(missing),
            message="acquisition plan requires a provider not explicitly allowed by compile policy",
            root_cause="provider_not_explicitly_allowed",
        )
    missing_configuration = sorted(
        set(capability["requiredConfiguration"])
        - set(request.policy.available_configuration_ids)
    )
    if missing_configuration:
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.plan_source_acquisition",
            subject=",".join(missing_configuration),
            message="required adapter configuration is absent from the compile request capability snapshot",
            root_cause="adapter_configuration_missing",
        )

    acquisitions: list[SourceAcquisitionItemIR] = []
    covered_roles: set[str] = set()
    for provider_id in provider_ids:
        provider = get_provider_capability(provider_id)
        try:
            adapter = verify_adapter_implementation(provider_id)
        except SourceAdapterContractError as exc:
            raise _fail(
                code="VERSION_UNSUPPORTED",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.plan_source_acquisition",
                subject=provider_id,
                message="selected source adapter does not satisfy the BA3 implementation contract",
                root_cause="source_adapter_contract_failed",
            ) from exc
        if not provider["authorityUse"] or provider["integrationStatus"] not in {
            "live_supported",
            "optional_integrated",
        }:
            raise _fail(
                code="UNKNOWN_REGISTRY_ID",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.plan_source_acquisition",
                subject=provider_id,
                message="selected provider is not enabled for authority use",
                root_cause="provider_not_authority_capable",
            )
        if provider["variableCost"] == "possible" and provider_id not in set(
            request.policy.approved_paid_provider_ids
        ):
            raise _fail(
                code="VERSION_UNSUPPORTED",
                layer=CompilerLayer.L1_SOURCE_ACQUISITION,
                pass_id="ba3.l1.plan_source_acquisition",
                subject=provider_id,
                message="possible-cost provider lacks explicit compile-request approval",
                root_cause="paid_provider_not_approved",
            )
        roles = tuple(sorted(set(provider["roles"])))
        covered_roles.update(roles)
        acquisitions.append(
            SourceAcquisitionItemIR(
                acquisition_id=f"source.{provider_id}",
                provider_id=provider_id,
                adapter_id=provider_id,
                implementation_ref=adapter["implementation_ref"],
                required_methods=tuple(adapter["required_methods"]),
                roles=roles,
                allowed_source_types=_allowed_source_types(provider_id),
                variable_cost=provider["variableCost"],
                retrieval_mode=request.policy.network_mode,
                required_configuration_ids=tuple(
                    sorted(capability["requiredConfiguration"])
                    if provider_id
                    in {capability["identityProviderId"], capability["fundamentalsProviderId"]}
                    else ()
                ),
            )
        )
    if not set(REQUIRED_FRONTEND_ROLES) <= covered_roles:
        missing = sorted(set(REQUIRED_FRONTEND_ROLES) - covered_roles)
        raise _fail(
            code="VERSION_UNSUPPORTED",
            layer=CompilerLayer.L1_SOURCE_ACQUISITION,
            pass_id="ba3.l1.plan_source_acquisition",
            subject=",".join(missing),
            message="source plan does not cover every required BA3 role",
            root_cause="source_role_coverage_incomplete",
        )
    return SourceAcquisitionIR.create(
        request_sha256=request.request_sha256,
        market_capability_registry_sha256=request.market_capability_registry_sha256,
        jurisdiction=request.instrument.jurisdiction,
        acquisitions=tuple(acquisitions),
        required_roles=REQUIRED_FRONTEND_ROLES,
    )
