"""BA3 L0-L2 compiler IR contracts.

These contracts extend, but do not modify, Compiler Foundation v1.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"
STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]*$"
FOUNDATION_VERSION = "1.0.0"
FOUNDATION_VERSION_LOCK = "8b9b7b2f59aa2cfed8280389f14c0e4edd11846d56c1d78e0dbf2c574da7d518"
MARKET_CAPABILITY_REGISTRY_SHA256 = "214ac512317bd1a179f8815e152ff3e1a5649fd2ccdf3ae39494d73a2a278d9f"


def _sorted_unique(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    if values != tuple(sorted(values)) or len(values) != len(set(values)):
        raise ValueError(f"{field} must be unique and sorted")
    return values


def _iso_datetime(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return value


class ResolvedInstrumentIR(StrictModel):
    contract_id: Literal["room16.compiler.resolved_instrument_ir"] = (
        "room16.compiler.resolved_instrument_ir"
    )
    contract_version: Literal[1] = 1
    resolution_status: Literal["supported"] = "supported"
    input_value: str = Field(min_length=1, max_length=256)
    input_kind: Literal["wkn", "isin", "ticker", "name"]
    ticker: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
    company_name: str = Field(min_length=1, max_length=256)
    exchange: str = Field(min_length=1, max_length=128)
    exchange_code: str | None = Field(default=None, max_length=32)
    jurisdiction: str = Field(pattern=r"^[A-Z]{2}$")
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
    wkn: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6}$")
    resolution_source: str = Field(min_length=1, max_length=128)
    resolver_evidence_allowed: Literal[False] = False


class CompilePolicyIR(StrictModel):
    contract_id: Literal["room16.compiler.compile_policy_ir"] = "room16.compiler.compile_policy_ir"
    contract_version: Literal[1] = 1
    network_mode: Literal["offline_replay", "live_acquisition"] = "offline_replay"
    allowed_provider_ids: tuple[str, ...]
    approved_paid_provider_ids: tuple[str, ...] = ()
    available_configuration_ids: tuple[str, ...] = ()
    output_backends: tuple[Literal["authority_bundle_v3", "compiler_shadow_evidence"], ...] = (
        "authority_bundle_v3",
        "compiler_shadow_evidence",
    )
    automatic_provider_fallback_allowed: Literal[False] = False
    automatic_paid_provider_selection_allowed: Literal[False] = False
    unsupported_market_analysis_allowed: Literal[False] = False

    @model_validator(mode="after")
    def sorted_and_scoped(self) -> "CompilePolicyIR":
        _sorted_unique(self.allowed_provider_ids, "allowed_provider_ids")
        _sorted_unique(self.approved_paid_provider_ids, "approved_paid_provider_ids")
        _sorted_unique(self.available_configuration_ids, "available_configuration_ids")
        if not set(self.approved_paid_provider_ids) <= set(self.allowed_provider_ids):
            raise ValueError("approved paid providers must be explicitly allowed")
        return self


class CompileRequestIR(StrictModel):
    contract_id: Literal["room16.compiler.compile_request_ir"] = "room16.compiler.compile_request_ir"
    contract_version: Literal[1] = 1
    foundation_version: Literal["1.0.0"] = FOUNDATION_VERSION
    foundation_version_lock_sha256: str = Field(
        default=FOUNDATION_VERSION_LOCK,
        pattern=SHA256_PATTERN,
    )
    market_capability_registry_sha256: str = Field(pattern=SHA256_PATTERN)
    instrument: ResolvedInstrumentIR
    as_of_date: str
    policy: CompilePolicyIR
    request_sha256: str = Field(pattern=SHA256_PATTERN)

    @staticmethod
    def hash_body(
        *,
        instrument: ResolvedInstrumentIR,
        as_of_date: str,
        policy: CompilePolicyIR,
        market_capability_registry_sha256: str,
    ) -> dict[str, object]:
        return {
            "as_of_date": as_of_date,
            "foundation_version": FOUNDATION_VERSION,
            "foundation_version_lock_sha256": FOUNDATION_VERSION_LOCK,
            "instrument": instrument.model_dump(mode="json"),
            "market_capability_registry_sha256": market_capability_registry_sha256,
            "policy": policy.model_dump(mode="json"),
        }

    @classmethod
    def create(
        cls,
        *,
        instrument: ResolvedInstrumentIR,
        as_of_date: str,
        policy: CompilePolicyIR,
        market_capability_registry_sha256: str = MARKET_CAPABILITY_REGISTRY_SHA256,
    ) -> "CompileRequestIR":
        normalized_date = date.fromisoformat(as_of_date).isoformat()
        body = cls.hash_body(
            instrument=instrument,
            as_of_date=normalized_date,
            policy=policy,
            market_capability_registry_sha256=market_capability_registry_sha256,
        )
        return cls(
            instrument=instrument,
            as_of_date=normalized_date,
            policy=policy,
            market_capability_registry_sha256=market_capability_registry_sha256,
            request_sha256=sha256_json(body),
        )

    @model_validator(mode="after")
    def valid_hash(self) -> "CompileRequestIR":
        date.fromisoformat(self.as_of_date)
        expected = sha256_json(
            self.hash_body(
                instrument=self.instrument,
                as_of_date=self.as_of_date,
                policy=self.policy,
                market_capability_registry_sha256=self.market_capability_registry_sha256,
            )
        )
        if expected != self.request_sha256:
            raise ValueError("compile request hash mismatch")
        return self


class SourceAcquisitionItemIR(StrictModel):
    acquisition_id: str = Field(pattern=STABLE_ID_PATTERN)
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    adapter_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    adapter_contract_version: Literal[1] = 1
    implementation_ref: str = Field(pattern=r"^[A-Za-z0-9_.]+:[A-Za-z][A-Za-z0-9_]+$")
    required_methods: tuple[str, ...]
    roles: tuple[str, ...]
    allowed_source_types: tuple[str, ...]
    authority_use: Literal[True] = True
    variable_cost: str
    retrieval_mode: Literal["offline_replay", "live_acquisition"]
    required_configuration_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def sorted_fields(self) -> "SourceAcquisitionItemIR":
        _sorted_unique(self.roles, "roles")
        _sorted_unique(self.required_methods, "required_methods")
        _sorted_unique(self.allowed_source_types, "allowed_source_types")
        _sorted_unique(self.required_configuration_ids, "required_configuration_ids")
        return self


class SourceAcquisitionIR(StrictModel):
    contract_id: Literal["room16.compiler.source_acquisition_ir"] = (
        "room16.compiler.source_acquisition_ir"
    )
    contract_version: Literal[1] = 1
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    market_capability_registry_sha256: str = Field(pattern=SHA256_PATTERN)
    jurisdiction: str = Field(pattern=r"^[A-Z]{2}$")
    acquisitions: tuple[SourceAcquisitionItemIR, ...]
    required_roles: tuple[str, ...]
    all_required_roles_mapped: Literal[True] = True
    provider_fallback_allowed: Literal[False] = False
    plan_sha256: str = Field(pattern=SHA256_PATTERN)

    @staticmethod
    def hash_body(
        *,
        request_sha256: str,
        market_capability_registry_sha256: str,
        jurisdiction: str,
        acquisitions: tuple[SourceAcquisitionItemIR, ...],
        required_roles: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "acquisitions": [item.model_dump(mode="json") for item in acquisitions],
            "all_required_roles_mapped": True,
            "jurisdiction": jurisdiction,
            "market_capability_registry_sha256": market_capability_registry_sha256,
            "provider_fallback_allowed": False,
            "request_sha256": request_sha256,
            "required_roles": list(required_roles),
        }

    @classmethod
    def create(
        cls,
        *,
        request_sha256: str,
        market_capability_registry_sha256: str,
        jurisdiction: str,
        acquisitions: tuple[SourceAcquisitionItemIR, ...],
        required_roles: tuple[str, ...],
    ) -> "SourceAcquisitionIR":
        ordered = tuple(sorted(acquisitions, key=lambda item: item.acquisition_id))
        roles = tuple(sorted(required_roles))
        body = cls.hash_body(
            request_sha256=request_sha256,
            market_capability_registry_sha256=market_capability_registry_sha256,
            jurisdiction=jurisdiction,
            acquisitions=ordered,
            required_roles=roles,
        )
        return cls(
            request_sha256=request_sha256,
            market_capability_registry_sha256=market_capability_registry_sha256,
            jurisdiction=jurisdiction,
            acquisitions=ordered,
            required_roles=roles,
            plan_sha256=sha256_json(body),
        )

    @model_validator(mode="after")
    def valid_plan(self) -> "SourceAcquisitionIR":
        ids = tuple(item.acquisition_id for item in self.acquisitions)
        _sorted_unique(ids, "acquisitions")
        _sorted_unique(self.required_roles, "required_roles")
        expected = sha256_json(
            self.hash_body(
                request_sha256=self.request_sha256,
                market_capability_registry_sha256=self.market_capability_registry_sha256,
                jurisdiction=self.jurisdiction,
                acquisitions=self.acquisitions,
                required_roles=self.required_roles,
            )
        )
        if expected != self.plan_sha256:
            raise ValueError("source acquisition plan hash mismatch")
        return self


class RetrievalReceiptIR(StrictModel):
    contract_id: Literal["room16.compiler.retrieval_receipt_ir"] = (
        "room16.compiler.retrieval_receipt_ir"
    )
    contract_version: Literal[1] = 1
    receipt_id: str = Field(pattern=STABLE_ID_PATTERN)
    acquisition_id: str = Field(pattern=STABLE_ID_PATTERN)
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    original_locator: str = Field(min_length=1)
    media_type: str = Field(min_length=3, max_length=128)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    payload_bytes: int = Field(ge=1)
    retrieved_at: str
    available_at: str
    published_at: str | None = None
    filing_date: str | None = None
    availability_basis: Literal["public_timestamp", "accepted_authority_v3_snapshot"] = (
        "public_timestamp"
    )
    transport: Literal["offline_replay", "offline_fixture"]
    variable_cost_incurred: Literal[False] = False

    @model_validator(mode="after")
    def valid_times(self) -> "RetrievalReceiptIR":
        _iso_datetime(self.retrieved_at, "retrieved_at")
        _iso_datetime(self.available_at, "available_at")
        if self.published_at is not None:
            _iso_datetime(self.published_at, "published_at")
        if self.filing_date is not None:
            date.fromisoformat(self.filing_date)
        if self.availability_basis == "accepted_authority_v3_snapshot" and (
            self.transport != "offline_replay"
            or not self.original_locator.startswith("authority-v3://")
        ):
            raise ValueError(
                "accepted Authority-v3 availability basis is replay-only"
            )
        return self


class SourceArtifactIR(StrictModel):
    snapshot_id: str = Field(pattern=STABLE_ID_PATTERN)
    path: str = Field(pattern=r"^sources/[0-9a-f]{2}/[0-9a-f]{64}(\.[a-z0-9]{1,10})?$")
    sha256: str = Field(pattern=SHA256_PATTERN)
    bytes: int = Field(ge=1)
    media_type: str = Field(min_length=3, max_length=128)


class SourceDispositionIR(StrictModel):
    source_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
    source_type: str = Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")
    provider_id: str = Field(pattern=r"^[a-z][a-z0-9_]{1,31}$")
    receipt_id: str = Field(pattern=STABLE_ID_PATTERN)
    snapshot_ids: tuple[str, ...]
    disposition: Literal["material_evidence", "supporting_material"]

    @model_validator(mode="after")
    def sorted_snapshots(self) -> "SourceDispositionIR":
        _sorted_unique(self.snapshot_ids, "snapshot_ids")
        if not self.snapshot_ids:
            raise ValueError("source disposition requires a snapshot")
        return self


class SourceSnapshotIR(StrictModel):
    contract_id: Literal["room16.compiler.source_snapshot_ir"] = "room16.compiler.source_snapshot_ir"
    contract_version: Literal[1] = 1
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    acquisition_plan_sha256: str = Field(pattern=SHA256_PATTERN)
    ticker: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{0,23}$")
    as_of_date: str
    source_root: Literal["."] = "."
    artifacts: tuple[SourceArtifactIR, ...]
    retrieval_receipts: tuple[RetrievalReceiptIR, ...]
    source_dispositions: tuple[SourceDispositionIR, ...]
    all_sources_dispositioned: Literal[True] = True
    all_artifacts_hash_verified: Literal[True] = True
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)

    @staticmethod
    def hash_body(
        *,
        request_sha256: str,
        acquisition_plan_sha256: str,
        ticker: str,
        as_of_date: str,
        artifacts: tuple[SourceArtifactIR, ...],
        retrieval_receipts: tuple[RetrievalReceiptIR, ...],
        source_dispositions: tuple[SourceDispositionIR, ...],
    ) -> dict[str, object]:
        return {
            "acquisition_plan_sha256": acquisition_plan_sha256,
            "all_artifacts_hash_verified": True,
            "all_sources_dispositioned": True,
            "artifacts": [item.model_dump(mode="json") for item in artifacts],
            "as_of_date": as_of_date,
            "request_sha256": request_sha256,
            "retrieval_receipts": [
                item.model_dump(mode="json") for item in retrieval_receipts
            ],
            "source_dispositions": [
                item.model_dump(mode="json") for item in source_dispositions
            ],
            "source_root": ".",
            "ticker": ticker,
        }

    @classmethod
    def create(
        cls,
        *,
        request_sha256: str,
        acquisition_plan_sha256: str,
        ticker: str,
        as_of_date: str,
        artifacts: tuple[SourceArtifactIR, ...],
        retrieval_receipts: tuple[RetrievalReceiptIR, ...],
        source_dispositions: tuple[SourceDispositionIR, ...],
    ) -> "SourceSnapshotIR":
        ordered_artifacts = tuple(sorted(artifacts, key=lambda item: item.snapshot_id))
        ordered_receipts = tuple(sorted(retrieval_receipts, key=lambda item: item.receipt_id))
        ordered_dispositions = tuple(
            sorted(source_dispositions, key=lambda item: (item.source_id, item.receipt_id))
        )
        body = cls.hash_body(
            request_sha256=request_sha256,
            acquisition_plan_sha256=acquisition_plan_sha256,
            ticker=ticker,
            as_of_date=date.fromisoformat(as_of_date).isoformat(),
            artifacts=ordered_artifacts,
            retrieval_receipts=ordered_receipts,
            source_dispositions=ordered_dispositions,
        )
        return cls(
            request_sha256=request_sha256,
            acquisition_plan_sha256=acquisition_plan_sha256,
            ticker=ticker,
            as_of_date=as_of_date,
            artifacts=ordered_artifacts,
            retrieval_receipts=ordered_receipts,
            source_dispositions=ordered_dispositions,
            snapshot_sha256=sha256_json(body),
        )

    @model_validator(mode="after")
    def complete_and_hashed(self) -> "SourceSnapshotIR":
        date.fromisoformat(self.as_of_date)
        artifact_ids = tuple(item.snapshot_id for item in self.artifacts)
        receipt_ids = tuple(item.receipt_id for item in self.retrieval_receipts)
        _sorted_unique(artifact_ids, "artifacts")
        _sorted_unique(receipt_ids, "retrieval_receipts")
        known_artifacts = set(artifact_ids)
        known_receipts = set(receipt_ids)
        disposition_receipts = {item.receipt_id for item in self.source_dispositions}
        disposition_artifacts = {
            snapshot_id
            for item in self.source_dispositions
            for snapshot_id in item.snapshot_ids
        }
        if disposition_receipts != known_receipts:
            raise ValueError("every retrieval receipt must have exactly one disposition path")
        if disposition_artifacts != known_artifacts:
            raise ValueError("every source artifact must be dispositioned")
        for item in self.source_dispositions:
            if not set(item.snapshot_ids) <= known_artifacts or item.receipt_id not in known_receipts:
                raise ValueError("source disposition references an unknown artifact or receipt")
        expected = sha256_json(
            self.hash_body(
                request_sha256=self.request_sha256,
                acquisition_plan_sha256=self.acquisition_plan_sha256,
                ticker=self.ticker,
                as_of_date=self.as_of_date,
                artifacts=self.artifacts,
                retrieval_receipts=self.retrieval_receipts,
                source_dispositions=self.source_dispositions,
            )
        )
        if expected != self.snapshot_sha256:
            raise ValueError("source snapshot hash mismatch")
        return self


def safe_suffix(locator: str) -> str:
    suffix = locator.rsplit("/", 1)[-1].rsplit(".", 1)
    if len(suffix) == 2 and re.fullmatch(r"[A-Za-z0-9]{1,10}", suffix[1]):
        return f".{suffix[1].lower()}"
    return ""
