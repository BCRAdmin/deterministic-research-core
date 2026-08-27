"""Immutable RFC-0011 supplemental source and observation contracts."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel
from research_agent.semantic_compiler.source_frontend.contracts import SourceSnapshotIR
from research_agent.semantic_compiler.source_frontend.offline import verify_source_snapshot

SHA256 = r"^[0-9a-f]{64}$"
SOURCE_FAMILIES = Literal[
    "sec_primary_document", "sec_filed_exhibit", "structured_regulatory_dataset"
]
NumericRole = Literal[
    "MEASURE_VALUE",
    "PERIOD_VALUE",
    "DATE_VALUE",
    "FOOTNOTE_MARKER",
    "NOTE_REFERENCE",
    "SECTION_REFERENCE",
    "ORDINAL_OR_COUNT",
    "AMBIGUOUS",
]


def _body(model: StrictModel, hash_field: str) -> dict[str, object]:
    value = model.model_dump(mode="json")
    value.pop(hash_field)
    return value


class SupplementalSourceError(RuntimeError):
    """Fail-closed source-authority error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class SupplementalSourcePolicyIR(StrictModel):
    contract_id: Literal["room16.rfc0011.supplemental_source_policy"] = (
        "room16.rfc0011.supplemental_source_policy"
    )
    contract_version: Literal[1] = 1
    base_request_sha256: str = Field(pattern=SHA256)
    ticker: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,9}$")
    canonical_company_name: str = Field(min_length=1)
    issuer_cik: str = Field(pattern=r"^[0-9]{1,10}$")
    as_of_date: str
    allowed_source_family_ids: tuple[SOURCE_FAMILIES, ...]
    allowed_domains: tuple[str, ...]
    allowed_media_types: tuple[str, ...]
    allowed_sec_forms: tuple[str, ...]
    max_discovery_requests: int = Field(ge=1, le=20)
    max_candidates: int = Field(ge=1, le=500)
    max_selected_documents: int = Field(ge=1, le=50)
    max_bytes_per_document: int = Field(ge=1, le=50_000_000)
    discovery_lookback_days: int = Field(ge=1, le=3650)
    paid_provider_ids_allowed: tuple[str, ...] = ()
    network_mode: Literal["live_acquisition", "offline_replay"]
    policy_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "SupplementalSourcePolicyIR":
        body = {
            "contract_id": "room16.rfc0011.supplemental_source_policy",
            "contract_version": 1,
            **values,
        }
        return cls(**body, policy_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_policy(self) -> "SupplementalSourcePolicyIR":
        date.fromisoformat(self.as_of_date)
        if tuple(sorted(set(self.allowed_domains))) != self.allowed_domains:
            raise ValueError("allowed domains must be unique and sorted")
        if tuple(sorted(set(self.allowed_source_family_ids))) != self.allowed_source_family_ids:
            raise ValueError("source families must be unique and sorted")
        if tuple(sorted(set(self.allowed_sec_forms))) != self.allowed_sec_forms:
            raise ValueError("SEC forms must be unique and sorted")
        if self.paid_provider_ids_allowed:
            raise ValueError("RFC-0011 candidate does not authorize paid providers")
        if sha256_json(_body(self, "policy_sha256")) != self.policy_sha256:
            raise ValueError("supplemental source policy self-hash mismatch")
        return self


class DiscoveryRequestIR(StrictModel):
    contract_id: Literal["room16.rfc0011.discovery_request"] = "room16.rfc0011.discovery_request"
    contract_version: Literal[1] = 1
    request_id: str
    policy_sha256: str = Field(pattern=SHA256)
    source_family_id: SOURCE_FAMILIES
    locator: str
    request_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "DiscoveryRequestIR":
        body = {"contract_id": "room16.rfc0011.discovery_request", "contract_version": 1, **values}
        return cls(**body, request_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "DiscoveryRequestIR":
        if sha256_json(_body(self, "request_sha256")) != self.request_sha256:
            raise ValueError("discovery request self-hash mismatch")
        return self


class DiscoveryCaptureReceiptIR(StrictModel):
    contract_id: Literal["room16.rfc0011.discovery_capture_receipt"] = (
        "room16.rfc0011.discovery_capture_receipt"
    )
    contract_version: Literal[1] = 1
    request_sha256: str = Field(pattern=SHA256)
    capture_artifact_sha256: str = Field(pattern=SHA256)
    payload_sha256: str = Field(pattern=SHA256)
    payload_bytes: int = Field(ge=1)
    original_locator: str
    final_locator: str
    media_type: str
    fetched_at_utc: str
    status: Literal["captured"] = "captured"
    receipt_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "DiscoveryCaptureReceiptIR":
        body = {
            "contract_id": "room16.rfc0011.discovery_capture_receipt",
            "contract_version": 1,
            "status": "captured",
            **values,
        }
        return cls(**body, receipt_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "DiscoveryCaptureReceiptIR":
        if sha256_json(_body(self, "receipt_sha256")) != self.receipt_sha256:
            raise ValueError("discovery receipt self-hash mismatch")
        return self


class DiscoveredSourceCandidateIR(StrictModel):
    contract_id: Literal["room16.rfc0011.discovered_source_candidate"] = (
        "room16.rfc0011.discovered_source_candidate"
    )
    contract_version: Literal[1] = 1
    candidate_id: str
    source_family_id: SOURCE_FAMILIES
    issuer_cik: str
    accession_number: str
    filing_date: str
    report_date: str | None = None
    form: str
    document_name: str
    locator: str
    parent_discovery_receipt_sha256: str = Field(pattern=SHA256)
    candidate_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "DiscoveredSourceCandidateIR":
        seed = {
            "source_family_id": values["source_family_id"],
            "issuer_cik": values["issuer_cik"],
            "accession_number": values["accession_number"],
            "report_date": values.get("report_date"),
            "document_name": values["document_name"],
            "parent_discovery_receipt_sha256": values["parent_discovery_receipt_sha256"],
        }
        candidate_id = f"supplemental.{sha256_json(seed)}"
        body = {
            "contract_id": "room16.rfc0011.discovered_source_candidate",
            "contract_version": 1,
            "candidate_id": candidate_id,
            **values,
        }
        return cls(**body, candidate_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "DiscoveredSourceCandidateIR":
        if sha256_json(_body(self, "candidate_sha256")) != self.candidate_sha256:
            raise ValueError("candidate self-hash mismatch")
        return self


class DiscoveredSourceSetIR(StrictModel):
    contract_id: Literal["room16.rfc0011.discovered_source_set"] = (
        "room16.rfc0011.discovered_source_set"
    )
    contract_version: Literal[1] = 1
    policy_sha256: str = Field(pattern=SHA256)
    discovery_receipt_sha256s: tuple[str, ...]
    candidates: tuple[DiscoveredSourceCandidateIR, ...]
    set_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(
        cls,
        *,
        policy_sha256: str,
        discovery_receipt_sha256s: tuple[str, ...],
        candidates: tuple[DiscoveredSourceCandidateIR, ...],
    ) -> "DiscoveredSourceSetIR":
        ordered = tuple(sorted(candidates, key=lambda item: item.candidate_id))
        body = {
            "contract_id": "room16.rfc0011.discovered_source_set",
            "contract_version": 1,
            "policy_sha256": policy_sha256,
            "discovery_receipt_sha256s": tuple(sorted(discovery_receipt_sha256s)),
            "candidates": [item.model_dump(mode="json") for item in ordered],
        }
        return cls(**body, set_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "DiscoveredSourceSetIR":
        if tuple(item.candidate_id for item in self.candidates) != tuple(
            sorted(item.candidate_id for item in self.candidates)
        ):
            raise ValueError("candidate set must be sorted")
        if sha256_json(_body(self, "set_sha256")) != self.set_sha256:
            raise ValueError("candidate set self-hash mismatch")
        return self


class SupplementalCaptureReceiptIR(StrictModel):
    contract_id: Literal["room16.rfc0011.supplemental_capture_receipt"] = (
        "room16.rfc0011.supplemental_capture_receipt"
    )
    contract_version: Literal[1] = 1
    candidate_id: str
    candidate_set_sha256: str = Field(pattern=SHA256)
    capture_artifact_sha256: str = Field(pattern=SHA256)
    payload_sha256: str = Field(pattern=SHA256)
    payload_bytes: int = Field(ge=1)
    original_locator: str
    final_locator: str
    media_type: str
    fetched_at_utc: str
    receipt_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "SupplementalCaptureReceiptIR":
        body = {
            "contract_id": "room16.rfc0011.supplemental_capture_receipt",
            "contract_version": 1,
            **values,
        }
        return cls(**body, receipt_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "SupplementalCaptureReceiptIR":
        if sha256_json(_body(self, "receipt_sha256")) != self.receipt_sha256:
            raise ValueError("supplemental capture receipt self-hash mismatch")
        return self


class SupplementalEvidenceSetIR(StrictModel):
    contract_id: Literal["room16.rfc0011.supplemental_evidence_set"] = (
        "room16.rfc0011.supplemental_evidence_set"
    )
    contract_version: Literal[1] = 1
    policy_sha256: str = Field(pattern=SHA256)
    candidate_set_sha256: str = Field(pattern=SHA256)
    capture_receipts: tuple[SupplementalCaptureReceiptIR, ...]
    evidence_set_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(
        cls,
        *,
        policy_sha256: str,
        candidate_set_sha256: str,
        capture_receipts: tuple[SupplementalCaptureReceiptIR, ...],
    ) -> "SupplementalEvidenceSetIR":
        ordered = tuple(sorted(capture_receipts, key=lambda item: item.candidate_id))
        body = {
            "contract_id": "room16.rfc0011.supplemental_evidence_set",
            "contract_version": 1,
            "policy_sha256": policy_sha256,
            "candidate_set_sha256": candidate_set_sha256,
            "capture_receipts": [item.model_dump(mode="json") for item in ordered],
        }
        return cls(**body, evidence_set_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "SupplementalEvidenceSetIR":
        if tuple(item.candidate_id for item in self.capture_receipts) != tuple(
            sorted(item.candidate_id for item in self.capture_receipts)
        ):
            raise ValueError("capture receipts must be sorted")
        if sha256_json(_body(self, "evidence_set_sha256")) != self.evidence_set_sha256:
            raise ValueError("supplemental evidence set self-hash mismatch")
        return self


class DocumentObservationIR(StrictModel):
    contract_id: Literal["room16.rfc0011.document_observation"] = (
        "room16.rfc0011.document_observation"
    )
    contract_version: Literal[1] = 1
    observation_id: str
    source_document_sha256: str = Field(pattern=SHA256)
    locator_type: Literal["table_cell", "table_row", "text_span"]
    locator: str
    row_index_or_null: int | None = Field(default=None, ge=0)
    column_index_or_null: int | None = Field(default=None, ge=0)
    header_path: tuple[str, ...] = ()
    reported_label: str
    raw_value_text: str
    parsed_numeric_value_or_null: str | None = None
    reported_unit_text_or_null: str | None = None
    reported_period_text_or_null: str | None = None
    reported_basis_text_or_null: str | None = None
    context_text: str
    numeric_role: NumericRole = "AMBIGUOUS"
    ambiguity_codes: tuple[str, ...] = ()
    trusted_numeric: bool = False
    observation_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "DocumentObservationIR":
        seed = {
            "source_document_sha256": values["source_document_sha256"],
            "locator": values["locator"],
            "reported_label": values["reported_label"],
            "raw_value_text": values["raw_value_text"],
        }
        body = {
            "contract_id": "room16.rfc0011.document_observation",
            "contract_version": 1,
            "observation_id": f"observation.{sha256_json(seed)}",
            "row_index_or_null": None,
            "column_index_or_null": None,
            "header_path": (),
            "parsed_numeric_value_or_null": None,
            "reported_unit_text_or_null": None,
            "reported_period_text_or_null": None,
            "reported_basis_text_or_null": None,
            "numeric_role": "AMBIGUOUS",
            "ambiguity_codes": (),
            "trusted_numeric": False,
            **values,
        }
        return cls(**body, observation_sha256=sha256_json(body))

    @model_validator(mode="after")
    def numeric_safety(self) -> "DocumentObservationIR":
        if self.trusted_numeric and (
            self.parsed_numeric_value_or_null is None
            or self.ambiguity_codes
            or self.numeric_role != "MEASURE_VALUE"
            or self.locator_type != "table_cell"
            or self.row_index_or_null is None
            or self.column_index_or_null is None
            or not self.header_path
        ):
            raise ValueError("only unambiguous structure-bound measure values can be trusted")
        if sha256_json(_body(self, "observation_sha256")) != self.observation_sha256:
            raise ValueError("document observation self-hash mismatch")
        return self


class SharedBaseInputIR(StrictModel):
    """Canonical RFC-0011 input bound directly to a verified BA3 snapshot."""

    contract_id: Literal["room16.rfc0011.shared_base_input_ir"] = (
        "room16.rfc0011.shared_base_input_ir"
    )
    contract_version: Literal[1] = 1
    ticker: str
    as_of_date: str
    request_sha256: str = Field(pattern=SHA256)
    acquisition_plan_sha256: str = Field(pattern=SHA256)
    retrieval_receipt_set_sha256: str = Field(pattern=SHA256)
    source_snapshot_sha256: str = Field(pattern=SHA256)
    snapshot_ir: SourceSnapshotIR
    snapshot_root: str
    base_input_sha256: str = Field(pattern=SHA256)

    @classmethod
    def from_snapshot(
        cls, *, snapshot: SourceSnapshotIR, snapshot_root: Path
    ) -> "SharedBaseInputIR":
        root = snapshot_root.resolve()
        verify_source_snapshot(snapshot, snapshot_root=root)
        receipt_set_sha256 = sha256_json(
            [item.model_dump(mode="json") for item in snapshot.retrieval_receipts]
        )
        body = {
            "contract_id": "room16.rfc0011.shared_base_input_ir",
            "contract_version": 1,
            "ticker": snapshot.ticker,
            "as_of_date": snapshot.as_of_date,
            "request_sha256": snapshot.request_sha256,
            "acquisition_plan_sha256": snapshot.acquisition_plan_sha256,
            "retrieval_receipt_set_sha256": receipt_set_sha256,
            "source_snapshot_sha256": snapshot.snapshot_sha256,
            "snapshot_ir": snapshot.model_dump(mode="json"),
            "snapshot_root": str(root),
        }
        return cls(**body, base_input_sha256=sha256_json(body))

    @model_validator(mode="after")
    def exact_snapshot_identity(self) -> "SharedBaseInputIR":
        snapshot = self.snapshot_ir
        if (
            self.ticker != snapshot.ticker
            or self.as_of_date != snapshot.as_of_date
            or self.request_sha256 != snapshot.request_sha256
            or self.acquisition_plan_sha256 != snapshot.acquisition_plan_sha256
            or self.source_snapshot_sha256 != snapshot.snapshot_sha256
            or self.retrieval_receipt_set_sha256
            != sha256_json([item.model_dump(mode="json") for item in snapshot.retrieval_receipts])
        ):
            raise ValueError("shared base input does not exactly bind SourceSnapshotIR")
        root = Path(self.snapshot_root)
        if not root.is_absolute():
            raise ValueError("shared base snapshot root must be absolute")
        verify_source_snapshot(snapshot, snapshot_root=root)
        if sha256_json(_body(self, "base_input_sha256")) != self.base_input_sha256:
            raise ValueError("shared base input self-hash mismatch")
        return self


class SupplementalCompileInputIR(StrictModel):
    """Hash-bound RFC-0011 authority and observations offered to H3/H2."""

    contract_id: Literal["room16.rfc0011.supplemental_compile_input_ir"] = (
        "room16.rfc0011.supplemental_compile_input_ir"
    )
    contract_version: Literal[1] = 1
    supplemental_policy_sha256: str = Field(pattern=SHA256)
    discovery_set_sha256: str = Field(pattern=SHA256)
    supplemental_evidence_set_sha256: str = Field(pattern=SHA256)
    observations: tuple[DocumentObservationIR, ...]
    observation_set_sha256: str = Field(pattern=SHA256)
    input_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(
        cls,
        *,
        supplemental_policy_sha256: str,
        discovery_set_sha256: str,
        supplemental_evidence_set_sha256: str,
        observations: tuple[DocumentObservationIR, ...],
    ) -> "SupplementalCompileInputIR":
        ordered = tuple(sorted(observations, key=lambda item: item.observation_id))
        observation_set_sha256 = sha256_json([item.model_dump(mode="json") for item in ordered])
        body = {
            "contract_id": "room16.rfc0011.supplemental_compile_input_ir",
            "contract_version": 1,
            "supplemental_policy_sha256": supplemental_policy_sha256,
            "discovery_set_sha256": discovery_set_sha256,
            "supplemental_evidence_set_sha256": supplemental_evidence_set_sha256,
            "observations": [item.model_dump(mode="json") for item in ordered],
            "observation_set_sha256": observation_set_sha256,
        }
        return cls(**body, input_sha256=sha256_json(body))

    @model_validator(mode="after")
    def exact_observation_identity(self) -> "SupplementalCompileInputIR":
        if tuple(item.observation_id for item in self.observations) != tuple(
            sorted(item.observation_id for item in self.observations)
        ):
            raise ValueError("supplemental observations must be sorted")
        expected_set = sha256_json([item.model_dump(mode="json") for item in self.observations])
        if expected_set != self.observation_set_sha256:
            raise ValueError("supplemental observation set hash mismatch")
        if sha256_json(_body(self, "input_sha256")) != self.input_sha256:
            raise ValueError("supplemental compile input self-hash mismatch")
        return self
