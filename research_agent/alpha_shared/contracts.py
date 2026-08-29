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
FilingIntentRole = Literal["EARNINGS_RESULTS"]
SelectionContextTag = Literal[
    "CURRENT_PRIMARY",
    "ITEM_2_02_PARENT_PRIMARY",
    "ITEM_2_02_EXHIBIT",
    "OTHER_FILED_EXHIBIT",
    "OTHER_PRIMARY",
]
SelectionContextV3Tag = Literal[
    "CURRENT_PRIMARY",
    "ITEM_2_02_REFERENCED_EXHIBIT",
    "ITEM_2_02_PARENT_PRIMARY",
    "OTHER_FILED_EXHIBIT",
    "OTHER_PRIMARY",
]
ExhibitReferenceRole = Literal["ITEM_2_02_EXHIBIT_REFERENCE"]


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


class SecFilingIntentIR(StrictModel):
    """Captured-submissions filing semantics kept separate from candidate v1."""

    contract_id: Literal["room16.reit.sec_filing_intent"] = "room16.reit.sec_filing_intent"
    contract_version: Literal[1] = 1
    accession_number: str
    filing_date: str
    report_date: str | None = None
    form: str
    primary_document: str
    primary_document_description: str
    filing_items: tuple[str, ...]
    intent_roles: tuple[FilingIntentRole, ...]
    parent_submissions_receipt_sha256: str = Field(pattern=SHA256)
    intent_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "SecFilingIntentIR":
        body = {
            "contract_id": "room16.reit.sec_filing_intent",
            "contract_version": 1,
            **values,
        }
        return cls(**body, intent_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_intent(self) -> "SecFilingIntentIR":
        date.fromisoformat(self.filing_date)
        if self.report_date:
            date.fromisoformat(self.report_date)
        if tuple(sorted(set(self.filing_items))) != self.filing_items:
            raise ValueError("filing items must be unique and sorted")
        expected_roles = (
            ("EARNINGS_RESULTS",) if self.form == "8-K" and "2.02" in self.filing_items else ()
        )
        if self.intent_roles != expected_roles:
            raise ValueError("filing intent roles do not match exact SEC item semantics")
        if sha256_json(_body(self, "intent_sha256")) != self.intent_sha256:
            raise ValueError("filing intent self-hash mismatch")
        return self


class SecFilingIntentSetIR(StrictModel):
    contract_id: Literal["room16.reit.sec_filing_intent_set"] = "room16.reit.sec_filing_intent_set"
    contract_version: Literal[1] = 1
    policy_sha256: str = Field(pattern=SHA256)
    submissions_receipt_sha256: str = Field(pattern=SHA256)
    intents: tuple[SecFilingIntentIR, ...]
    intent_set_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(
        cls,
        *,
        policy_sha256: str,
        submissions_receipt_sha256: str,
        intents: tuple[SecFilingIntentIR, ...],
    ) -> "SecFilingIntentSetIR":
        ordered = tuple(sorted(intents, key=lambda item: item.accession_number))
        body = {
            "contract_id": "room16.reit.sec_filing_intent_set",
            "contract_version": 1,
            "policy_sha256": policy_sha256,
            "submissions_receipt_sha256": submissions_receipt_sha256,
            "intents": [item.model_dump(mode="json") for item in ordered],
        }
        return cls(**body, intent_set_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "SecFilingIntentSetIR":
        if tuple(item.accession_number for item in self.intents) != tuple(
            sorted(item.accession_number for item in self.intents)
        ):
            raise ValueError("filing intent set must be accession-sorted")
        if any(
            item.parent_submissions_receipt_sha256 != self.submissions_receipt_sha256
            for item in self.intents
        ):
            raise ValueError("filing intent submissions binding mismatch")
        if sha256_json(_body(self, "intent_set_sha256")) != self.intent_set_sha256:
            raise ValueError("filing intent set self-hash mismatch")
        return self


class SecExhibitReferenceIR(StrictModel):
    """Hash-bound reference parsed from a captured Item 2.02 parent document."""

    contract_id: Literal["room16.reit.sec_exhibit_reference"] = (
        "room16.reit.sec_exhibit_reference"
    )
    contract_version: Literal[1] = 1
    parent_accession_number: str
    parent_filing_intent_sha256: str = Field(pattern=SHA256)
    parent_document_sha256: str = Field(pattern=SHA256)
    parent_document_name: str
    exhibit_number: str = Field(pattern=r"^99\.[0-9]+$")
    referenced_href: str
    referenced_document_name: str
    description: str
    reference_locator: str
    sec_extract_exhibit_attribute: bool
    reference_role: ExhibitReferenceRole
    reference_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "SecExhibitReferenceIR":
        body = {
            "contract_id": "room16.reit.sec_exhibit_reference",
            "contract_version": 1,
            **values,
        }
        return cls(**body, reference_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "SecExhibitReferenceIR":
        if sha256_json(_body(self, "reference_sha256")) != self.reference_sha256:
            raise ValueError("SEC exhibit reference self-hash mismatch")
        return self


class SecExhibitReferenceSetIR(StrictModel):
    contract_id: Literal["room16.reit.sec_exhibit_reference_set"] = (
        "room16.reit.sec_exhibit_reference_set"
    )
    contract_version: Literal[1] = 1
    policy_sha256: str = Field(pattern=SHA256)
    parent_filing_intent_sha256: str = Field(pattern=SHA256)
    parent_document_sha256: str = Field(pattern=SHA256)
    references: tuple[SecExhibitReferenceIR, ...]
    reference_set_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "SecExhibitReferenceSetIR":
        references = tuple(
            sorted(values["references"], key=lambda item: item.reference_sha256)
        )
        body = {
            "contract_id": "room16.reit.sec_exhibit_reference_set",
            "contract_version": 1,
            **values,
            "references": [item.model_dump(mode="json") for item in references],
        }
        return cls(**body, reference_set_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_bindings(self) -> "SecExhibitReferenceSetIR":
        if tuple(item.reference_sha256 for item in self.references) != tuple(
            sorted({item.reference_sha256 for item in self.references})
        ):
            raise ValueError("SEC exhibit references must be unique and hash-sorted")
        if any(
            item.parent_filing_intent_sha256 != self.parent_filing_intent_sha256
            or item.parent_document_sha256 != self.parent_document_sha256
            for item in self.references
        ):
            raise ValueError("SEC exhibit reference parent binding mismatch")
        if sha256_json(_body(self, "reference_set_sha256")) != self.reference_set_sha256:
            raise ValueError("SEC exhibit reference set self-hash mismatch")
        return self


class ReferencedExhibitCandidateBindingIR(StrictModel):
    contract_id: Literal["room16.reit.referenced_exhibit_candidate_binding"] = (
        "room16.reit.referenced_exhibit_candidate_binding"
    )
    contract_version: Literal[1] = 1
    candidate_id: str
    candidate_sha256: str = Field(pattern=SHA256)
    exhibit_reference_sha256: str = Field(pattern=SHA256)
    index_receipt_sha256: str = Field(pattern=SHA256)
    exhibit_number: str = Field(pattern=r"^99\.[0-9]+$")
    binding_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "ReferencedExhibitCandidateBindingIR":
        body = {
            "contract_id": "room16.reit.referenced_exhibit_candidate_binding",
            "contract_version": 1,
            **values,
        }
        return cls(**body, binding_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "ReferencedExhibitCandidateBindingIR":
        if sha256_json(_body(self, "binding_sha256")) != self.binding_sha256:
            raise ValueError("referenced exhibit candidate binding self-hash mismatch")
        return self


class CandidateSelectionContextIR(StrictModel):
    """Hash-bound semantic context for immutable candidate-v1 objects."""

    contract_id: Literal["room16.reit.candidate_selection_context"] = (
        "room16.reit.candidate_selection_context"
    )
    contract_version: Literal[2] = 2
    policy_sha256: str = Field(pattern=SHA256)
    candidate_set_sha256: str = Field(pattern=SHA256)
    filing_intent_set_sha256: str = Field(pattern=SHA256)
    candidate_tags: tuple[tuple[str, SelectionContextTag], ...]
    context_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "CandidateSelectionContextIR":
        tags = tuple(sorted(values["candidate_tags"], key=lambda item: item[0]))
        body = {
            "contract_id": "room16.reit.candidate_selection_context",
            "contract_version": 2,
            **values,
            "candidate_tags": tags,
        }
        return cls(**body, context_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_hash(self) -> "CandidateSelectionContextIR":
        candidate_ids = tuple(item[0] for item in self.candidate_tags)
        if candidate_ids != tuple(sorted(set(candidate_ids))):
            raise ValueError("candidate selection tags must be unique and sorted")
        if sha256_json(_body(self, "context_sha256")) != self.context_sha256:
            raise ValueError("candidate selection context self-hash mismatch")
        return self


class CandidateSelectionContextV3IR(StrictModel):
    """Selection authority whose exhibit tier is backed by explicit references."""

    contract_id: Literal["room16.reit.candidate_selection_context"] = (
        "room16.reit.candidate_selection_context"
    )
    contract_version: Literal[3] = 3
    policy_sha256: str = Field(pattern=SHA256)
    candidate_set_sha256: str = Field(pattern=SHA256)
    filing_intent_set_sha256: str = Field(pattern=SHA256)
    exhibit_reference_set_sha256s: tuple[str, ...]
    reference_candidate_bindings: tuple[ReferencedExhibitCandidateBindingIR, ...]
    candidate_tags: tuple[tuple[str, SelectionContextV3Tag], ...]
    context_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "CandidateSelectionContextV3IR":
        tags = tuple(sorted(values["candidate_tags"], key=lambda item: item[0]))
        bindings = tuple(
            sorted(values["reference_candidate_bindings"], key=lambda item: item.candidate_id)
        )
        reference_sets = tuple(sorted(set(values["exhibit_reference_set_sha256s"])))
        body = {
            "contract_id": "room16.reit.candidate_selection_context",
            "contract_version": 3,
            **values,
            "candidate_tags": tags,
            "reference_candidate_bindings": [item.model_dump(mode="json") for item in bindings],
            "exhibit_reference_set_sha256s": reference_sets,
        }
        return cls(**body, context_sha256=sha256_json(body))

    @model_validator(mode="after")
    def validate_bindings(self) -> "CandidateSelectionContextV3IR":
        candidate_ids = tuple(item[0] for item in self.candidate_tags)
        if candidate_ids != tuple(sorted(set(candidate_ids))):
            raise ValueError("candidate selection tags must be unique and sorted")
        binding_ids = tuple(item.candidate_id for item in self.reference_candidate_bindings)
        if binding_ids != tuple(sorted(set(binding_ids))):
            raise ValueError("reference candidate bindings must be unique and sorted")
        tag_map = dict(self.candidate_tags)
        if any(
            tag_map.get(item.candidate_id) != "ITEM_2_02_REFERENCED_EXHIBIT"
            for item in self.reference_candidate_bindings
        ):
            raise ValueError("reference binding requires referenced-exhibit tag")
        if sha256_json(_body(self, "context_sha256")) != self.context_sha256:
            raise ValueError("candidate selection context v3 self-hash mismatch")
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
