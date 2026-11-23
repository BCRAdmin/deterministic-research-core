"""Fail-closed, versioned contracts for the personal Room16 research OS.

These records are intentionally narrower than the compiler's internal IR.
They define the trust boundary between a verified compiler dossier and the
private cockpit, an optional public-edition draft, or an optional copilot.
No contract in this module can represent an order, a customer, a broker
connection, or an external publication.
"""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel


SHA256_PATTERN = r"^[0-9a-f]{64}$"
STABLE_ID_PATTERN = r"^[a-z][a-z0-9_.:-]*$"
SYMBOL_PATTERN = r"^[A-Z0-9.^-]{1,24}$"
ISO_CURRENCY_PATTERN = r"^[A-Z]{3}$"
ISO_COUNTRY_PATTERN = r"^[A-Z]{2}$"

COMPILER_PASS_ORDER = (
    "instrument_identity",
    "source_snapshot",
    "normalize_ir",
    "facts_evidence",
    "metrics_scenarios",
    "claims_decision",
    "quality_release",
    "sign_dossier",
)


class Room16OSContractError(ValueError):
    """Raised when a Room16 OS boundary would become ambiguous or unsafe."""


def _exact_iso_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("must be an ISO-8601 calendar date") from exc
    if parsed.isoformat() != value:
        raise ValueError("must be a canonical ISO-8601 calendar date")
    return value


def _aware_timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must contain an explicit timezone")
    return value


def _unique_sorted(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{field_name} must be unique and sorted")
    return values


def _hash_body(model: StrictModel, *, exclude: set[str]) -> str:
    return sha256_json(model.model_dump(mode="json", exclude=exclude))


class IssuerIdentity(StrictModel):
    """A compiler-resolved instrument identity, never a UI guess."""

    contract_id: Literal["room16.os.issuer_identity"] = "room16.os.issuer_identity"
    contract_version: Literal[1] = 1
    issuer_id: str = Field(pattern=STABLE_ID_PATTERN)
    legal_name: str = Field(min_length=1, max_length=500)
    jurisdiction: str = Field(pattern=ISO_COUNTRY_PATTERN)
    primary_symbol: str = Field(pattern=SYMBOL_PATTERN)
    primary_exchange: str = Field(min_length=1, max_length=80)
    identity_source_snapshot_id: str = Field(pattern=STABLE_ID_PATTERN)
    isin: str | None = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{10}$")
    wkn: str | None = Field(default=None, pattern=r"^[A-Z0-9]{6}$")
    identity_status: Literal["verified", "blocked"] = "verified"
    blocker_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def identity_is_fail_closed(self) -> "IssuerIdentity":
        _unique_sorted(self.blocker_codes, "blocker_codes")
        if self.identity_status == "verified" and self.blocker_codes:
            raise ValueError("a verified identity cannot carry blocker codes")
        if self.identity_status == "blocked" and not self.blocker_codes:
            raise ValueError("a blocked identity needs an explicit blocker code")
        return self


class ProviderEntitlement(StrictModel):
    """Provider licence and operator-authorisation state, separate from data."""

    contract_id: Literal["room16.os.provider_entitlement"] = "room16.os.provider_entitlement"
    contract_version: Literal[1] = 1
    entitlement_id: str = Field(pattern=STABLE_ID_PATTERN)
    provider_id: str = Field(pattern=STABLE_ID_PATTERN)
    provider_class: Literal["official", "issuer", "licensed_free", "licensed_paid"]
    status: Literal["active", "expired", "blocked"]
    allowed_uses: tuple[Literal["private_research", "public_edition"], ...]
    refresh_policy: Literal["manual", "operator_approved_scheduled"] = "manual"
    automatic_selection: Literal[False] = False
    operator_approval_receipt_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    approved_at: str | None = None
    expires_on: str | None = None

    @field_validator("approved_at")
    @classmethod
    def approval_timestamp_is_aware(cls, value: str | None) -> str | None:
        return _aware_timestamp(value) if value else value

    @field_validator("expires_on")
    @classmethod
    def expiry_is_date(cls, value: str | None) -> str | None:
        return _exact_iso_date(value) if value else value

    @model_validator(mode="after")
    def paid_data_needs_an_explicit_operator_grant(self) -> "ProviderEntitlement":
        if self.allowed_uses != tuple(sorted(set(self.allowed_uses))):
            raise ValueError("allowed_uses must be unique and sorted")
        if self.provider_class == "licensed_paid" and (
            not self.operator_approval_receipt_sha256 or not self.approved_at
        ):
            raise ValueError("paid provider use requires an operator approval receipt")
        if self.status != "active" and self.allowed_uses:
            raise ValueError("inactive provider entitlement cannot allow any use")
        return self


class SourceSnapshot(StrictModel):
    """A licensed, content-addressed source snapshot used by the compiler."""

    contract_id: Literal["room16.os.source_snapshot"] = "room16.os.source_snapshot"
    contract_version: Literal[1] = 1
    snapshot_id: str = Field(pattern=STABLE_ID_PATTERN)
    issuer_id: str = Field(pattern=STABLE_ID_PATTERN)
    provider_id: str = Field(pattern=STABLE_ID_PATTERN)
    entitlement_id: str | None = Field(default=None, pattern=STABLE_ID_PATTERN)
    source_kind: Literal[
        "regulator_filing",
        "issuer_ir",
        "exchange_market_data",
        "licensed_market_data",
        "official_registry",
    ]
    locator: str = Field(min_length=1, max_length=2_000)
    retrieved_at: str
    content_sha256: str = Field(pattern=SHA256_PATTERN)
    manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    private_research_rights: Literal["allowed", "blocked", "unknown"]
    public_edition_rights: Literal["allowed", "blocked", "unknown"]
    freshness_until: str | None = None
    snapshot_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("retrieved_at")
    @classmethod
    def retrieved_at_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)

    @field_validator("freshness_until")
    @classmethod
    def freshness_is_date(cls, value: str | None) -> str | None:
        return _exact_iso_date(value) if value else value

    @model_validator(mode="after")
    def snapshot_hash_matches(self) -> "SourceSnapshot":
        if _hash_body(self, exclude={"snapshot_sha256"}) != self.snapshot_sha256:
            raise ValueError("source snapshot hash mismatch")
        if self.private_research_rights != "allowed" and self.public_edition_rights == "allowed":
            raise ValueError("a source without private research rights cannot allow a public edition")
        return self

    @classmethod
    def create(cls, **payload: object) -> "SourceSnapshot":
        provisional = cls.model_construct(**payload, snapshot_sha256="0" * 64)
        return cls(**payload, snapshot_sha256=_hash_body(provisional, exclude={"snapshot_sha256"}))

    def verify_hash(self) -> None:
        if _hash_body(self, exclude={"snapshot_sha256"}) != self.snapshot_sha256:
            raise Room16OSContractError("source snapshot hash mismatch")


class FactLedgerEntry(StrictModel):
    """A typed fact that is either claimable or explicitly blocked."""

    contract_id: Literal["room16.os.fact_ledger_entry"] = "room16.os.fact_ledger_entry"
    contract_version: Literal[1] = 1
    fact_id: str = Field(pattern=STABLE_ID_PATTERN)
    metric_id: str | None = Field(default=None, pattern=STABLE_ID_PATTERN)
    source_snapshot_id: str | None = Field(default=None, pattern=STABLE_ID_PATTERN)
    period_basis: str | None = Field(default=None, max_length=80)
    currency: str | None = Field(default=None, pattern=ISO_CURRENCY_PATTERN)
    currency_required: bool = False
    period_required: bool = True
    value: int | float | str | None = None
    claimability: Literal["accepted", "blocked"]
    blocker_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unknown_semantics_block_a_fact(self) -> "FactLedgerEntry":
        _unique_sorted(self.blocker_codes, "blocker_codes")
        missing = []
        if not self.metric_id:
            missing.append("metric")
        if not self.source_snapshot_id:
            missing.append("source")
        if self.period_required and not self.period_basis:
            missing.append("period")
        if self.currency_required and not self.currency:
            missing.append("currency")
        if self.claimability == "accepted" and missing:
            raise ValueError(f"an accepted fact has unknown semantics: {','.join(missing)}")
        if self.claimability == "accepted" and self.blocker_codes:
            raise ValueError("an accepted fact cannot carry blocker codes")
        if self.claimability == "blocked" and not self.blocker_codes:
            raise ValueError("a blocked fact needs explicit blocker codes")
        return self


class ClaimRecord(StrictModel):
    """An output claim, visibly separated from facts and assumptions."""

    contract_id: Literal["room16.os.claim_record"] = "room16.os.claim_record"
    contract_version: Literal[1] = 1
    claim_id: str = Field(pattern=STABLE_ID_PATTERN)
    claim_kind: Literal["factual", "interpretive", "scenario"]
    supporting_fact_ids: tuple[str, ...]
    status: Literal["supported", "blocked"]
    blocker_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def claim_support_is_explicit(self) -> "ClaimRecord":
        _unique_sorted(self.supporting_fact_ids, "supporting_fact_ids")
        _unique_sorted(self.blocker_codes, "blocker_codes")
        if not self.supporting_fact_ids:
            raise ValueError("a claim needs at least one supporting fact reference")
        if self.status == "supported" and self.blocker_codes:
            raise ValueError("a supported claim cannot carry blocker codes")
        if self.status == "blocked" and not self.blocker_codes:
            raise ValueError("a blocked claim needs explicit blocker codes")
        return self


class EvidenceGraph(StrictModel):
    """Hash-bound fact and claim ledger for one research run."""

    contract_id: Literal["room16.os.evidence_graph"] = "room16.os.evidence_graph"
    contract_version: Literal[1] = 1
    graph_id: str = Field(pattern=STABLE_ID_PATTERN)
    facts: tuple[FactLedgerEntry, ...]
    claims: tuple[ClaimRecord, ...]
    status: Literal["verified", "blocked"]
    evidence_graph_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def evidence_is_closed_and_hash_bound(self) -> "EvidenceGraph":
        fact_ids = tuple(item.fact_id for item in self.facts)
        claim_ids = tuple(item.claim_id for item in self.claims)
        _unique_sorted(fact_ids, "fact ids")
        _unique_sorted(claim_ids, "claim ids")
        known_facts = set(fact_ids)
        for claim in self.claims:
            missing = set(claim.supporting_fact_ids) - known_facts
            if missing:
                raise ValueError(f"claim references unknown facts: {','.join(sorted(missing))}")
        if self.status == "verified" and (
            any(item.claimability != "accepted" for item in self.facts)
            or any(item.status != "supported" for item in self.claims)
        ):
            raise ValueError("verified evidence graph contains blocked facts or claims")
        if _hash_body(self, exclude={"evidence_graph_sha256"}) != self.evidence_graph_sha256:
            raise ValueError("evidence graph hash mismatch")
        return self

    @classmethod
    def create(cls, **payload: object) -> "EvidenceGraph":
        provisional = cls.model_construct(**payload, evidence_graph_sha256="0" * 64)
        return cls(
            **payload,
            evidence_graph_sha256=_hash_body(provisional, exclude={"evidence_graph_sha256"}),
        )

    def verify_hash(self) -> None:
        if _hash_body(self, exclude={"evidence_graph_sha256"}) != self.evidence_graph_sha256:
            raise Room16OSContractError("evidence graph hash mismatch")


class CompilerPassReceipt(StrictModel):
    """A deterministic receipt for a fixed compiler pass."""

    contract_id: Literal["room16.os.compiler_pass_receipt"] = "room16.os.compiler_pass_receipt"
    contract_version: Literal[1] = 1
    pass_id: Literal[
        "instrument_identity",
        "source_snapshot",
        "normalize_ir",
        "facts_evidence",
        "metrics_scenarios",
        "claims_decision",
        "quality_release",
        "sign_dossier",
    ]
    status: Literal["executed", "cache_hit", "replayed", "skipped", "failed"]
    input_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    output_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    diagnostic_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def receipt_is_deterministic_or_explicitly_failed(self) -> "CompilerPassReceipt":
        _unique_sorted(self.diagnostic_codes, "diagnostic_codes")
        if self.status in {"executed", "cache_hit", "replayed"} and (
            not self.input_sha256 or not self.output_sha256
        ):
            raise ValueError("completed pass receipts require input and output hashes")
        if self.status == "failed" and not self.diagnostic_codes:
            raise ValueError("failed pass receipts need diagnostics")
        return self


class ResearchRun(StrictModel):
    """A compiler run through the only supported source-native pass order."""

    contract_id: Literal["room16.os.research_run"] = "room16.os.research_run"
    contract_version: Literal[1] = 1
    run_id: str = Field(pattern=STABLE_ID_PATTERN)
    issuer_id: str = Field(pattern=STABLE_ID_PATTERN)
    as_of_date: str
    compiler_version: str = Field(min_length=1, max_length=120)
    input_sha256: str = Field(pattern=SHA256_PATTERN)
    authority_bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    pass_receipts: tuple[CompilerPassReceipt, ...]
    status: Literal["verified", "blocked", "failed"]
    release_verdict: Literal["verified", "blocked"]
    created_at: str
    run_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("as_of_date")
    @classmethod
    def run_date_is_date(cls, value: str) -> str:
        return _exact_iso_date(value)

    @field_validator("created_at")
    @classmethod
    def run_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)

    @model_validator(mode="after")
    def pass_order_and_run_hash_are_valid(self) -> "ResearchRun":
        pass_ids = tuple(item.pass_id for item in self.pass_receipts)
        if pass_ids != COMPILER_PASS_ORDER:
            raise ValueError("research run must contain the canonical compiler pass order exactly once")
        if self.status == "verified":
            if self.release_verdict != "verified":
                raise ValueError("a verified run requires a verified release verdict")
            if any(item.status not in {"executed", "cache_hit", "replayed"} for item in self.pass_receipts):
                raise ValueError("a verified run cannot skip or fail a compiler pass")
        if self.status != "verified" and self.release_verdict != "blocked":
            raise ValueError("non-verified runs must be release blocked")
        if _hash_body(self, exclude={"run_sha256"}) != self.run_sha256:
            raise ValueError("research run hash mismatch")
        return self

    @classmethod
    def create(cls, **payload: object) -> "ResearchRun":
        provisional = cls.model_construct(**payload, run_sha256="0" * 64)
        return cls(**payload, run_sha256=_hash_body(provisional, exclude={"run_sha256"}))

    def verify_hash(self) -> None:
        if _hash_body(self, exclude={"run_sha256"}) != self.run_sha256:
            raise Room16OSContractError("research run hash mismatch")


class DossierReference(StrictModel):
    """The immutable pointer that private and public layers may retain."""

    contract_id: Literal["room16.os.dossier_reference"] = "room16.os.dossier_reference"
    contract_version: Literal[1] = 1
    dossier_id: str = Field(pattern=STABLE_ID_PATTERN)
    dossier_version: int = Field(ge=1)
    as_of_date: str
    dossier_sha256: str = Field(pattern=SHA256_PATTERN)
    bundle_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("as_of_date")
    @classmethod
    def reference_date_is_date(cls, value: str) -> str:
        return _exact_iso_date(value)


class DossierVersion(StrictModel):
    """An immutable, signed compiler dossier—not a mutable app document."""

    contract_id: Literal["room16.os.dossier_version"] = "room16.os.dossier_version"
    contract_version: Literal[1] = 1
    dossier_id: str = Field(pattern=STABLE_ID_PATTERN)
    version: int = Field(ge=1)
    issuer_id: str = Field(pattern=STABLE_ID_PATTERN)
    as_of_date: str
    source_snapshot_sha256s: tuple[str, ...]
    research_run_sha256: str = Field(pattern=SHA256_PATTERN)
    evidence_graph_sha256: str = Field(pattern=SHA256_PATTERN)
    compiler_version: str = Field(min_length=1, max_length=120)
    quality_verdict: Literal["verified", "blocked", "historical_reference"]
    quality_blocker_codes: tuple[str, ...] = ()
    public_evidence_status: Literal["eligible", "blocked"]
    historical_reader_only: bool = False
    bundle_sha256: str = Field(pattern=SHA256_PATTERN)
    dossier_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("as_of_date")
    @classmethod
    def dossier_date_is_date(cls, value: str) -> str:
        return _exact_iso_date(value)

    @model_validator(mode="after")
    def dossier_is_immutable_and_consistent(self) -> "DossierVersion":
        _unique_sorted(self.source_snapshot_sha256s, "source_snapshot_sha256s")
        _unique_sorted(self.quality_blocker_codes, "quality_blocker_codes")
        if not self.source_snapshot_sha256s:
            raise ValueError("a dossier needs at least one source snapshot")
        if self.quality_verdict == "verified" and self.quality_blocker_codes:
            raise ValueError("a verified dossier cannot carry quality blockers")
        if self.quality_verdict == "blocked" and not self.quality_blocker_codes:
            raise ValueError("a blocked dossier needs quality blockers")
        if self.quality_verdict == "historical_reference" and not self.historical_reader_only:
            raise ValueError("a historical dossier must be reader-only")
        if self.historical_reader_only and self.public_evidence_status != "blocked":
            raise ValueError("historical reader-only dossiers cannot be public edition inputs")
        if _hash_body(self, exclude={"dossier_sha256"}) != self.dossier_sha256:
            raise ValueError("dossier hash mismatch")
        return self

    @classmethod
    def create(cls, **payload: object) -> "DossierVersion":
        provisional = cls.model_construct(**payload, dossier_sha256="0" * 64)
        return cls(**payload, dossier_sha256=_hash_body(provisional, exclude={"dossier_sha256"}))

    def reference(self) -> DossierReference:
        return DossierReference(
            dossier_id=self.dossier_id,
            dossier_version=self.version,
            as_of_date=self.as_of_date,
            dossier_sha256=self.dossier_sha256,
            bundle_sha256=self.bundle_sha256,
        )

    def verify_hash(self) -> None:
        if _hash_body(self, exclude={"dossier_sha256"}) != self.dossier_sha256:
            raise Room16OSContractError("dossier hash mismatch")


class ThesisVersion(StrictModel):
    """Private thesis notes that can cite, but never alter, a dossier."""

    contract_id: Literal["room16.os.thesis_version"] = "room16.os.thesis_version"
    contract_version: Literal[1] = 1
    thesis_id: str = Field(pattern=STABLE_ID_PATTERN)
    version: int = Field(ge=1)
    dossier: DossierReference
    thesis_text: str = Field(min_length=1, max_length=20_000)
    counterarguments: tuple[str, ...] = ()
    review_on: str | None = None
    created_at: str
    privacy_zone: Literal["private_local_only"] = "private_local_only"

    @field_validator("review_on")
    @classmethod
    def thesis_review_is_date(cls, value: str | None) -> str | None:
        return _exact_iso_date(value) if value else value

    @field_validator("created_at")
    @classmethod
    def thesis_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)


class DecisionRecord(StrictModel):
    """A private research decision record; deliberately never an order."""

    contract_id: Literal["room16.os.decision_record"] = "room16.os.decision_record"
    contract_version: Literal[1] = 1
    decision_id: str = Field(pattern=STABLE_ID_PATTERN)
    dossier: DossierReference
    thesis_id: str | None = Field(default=None, pattern=STABLE_ID_PATTERN)
    decision_kind: Literal["observe", "review", "research_continue", "thesis_update"]
    rationale: str = Field(min_length=1, max_length=20_000)
    review_on: str | None = None
    private_portfolio_context_ref: str | None = Field(default=None, pattern=STABLE_ID_PATTERN)
    created_at: str
    privacy_zone: Literal["private_local_only"] = "private_local_only"

    @field_validator("review_on")
    @classmethod
    def decision_review_is_date(cls, value: str | None) -> str | None:
        return _exact_iso_date(value) if value else value

    @field_validator("created_at")
    @classmethod
    def decision_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)


class PortfolioLedger(StrictModel):
    """A private ledger checksum; positions themselves never enter a dossier."""

    contract_id: Literal["room16.os.portfolio_ledger"] = "room16.os.portfolio_ledger"
    contract_version: Literal[1] = 1
    ledger_id: str = Field(pattern=STABLE_ID_PATTERN)
    ledger_sha256: str = Field(pattern=SHA256_PATTERN)
    updated_at: str
    privacy_zone: Literal["private_local_only"] = "private_local_only"
    external_share_allowed: Literal[False] = False

    @field_validator("updated_at")
    @classmethod
    def ledger_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)


class WatchRule(StrictModel):
    """An opt-in local observation rule with no automatic research action."""

    contract_id: Literal["room16.os.watch_rule"] = "room16.os.watch_rule"
    contract_version: Literal[1] = 1
    rule_id: str = Field(pattern=STABLE_ID_PATTERN)
    issuer_id: str = Field(pattern=STABLE_ID_PATTERN)
    kind: Literal["filing", "earnings", "price", "thesis", "risk"]
    enabled: bool = True
    next_action: Literal["create_review_alert_only"] = "create_review_alert_only"
    research_run_policy: Literal["manual_operator_approval_required"] = "manual_operator_approval_required"
    created_at: str

    @field_validator("created_at")
    @classmethod
    def watch_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)


class ReviewAlert(StrictModel):
    """An alert requests a review; it does not trigger a refresh or an export."""

    contract_id: Literal["room16.os.review_alert"] = "room16.os.review_alert"
    contract_version: Literal[1] = 1
    alert_id: str = Field(pattern=STABLE_ID_PATTERN)
    rule_id: str | None = Field(default=None, pattern=STABLE_ID_PATTERN)
    issuer_id: str = Field(pattern=STABLE_ID_PATTERN)
    category: Literal["filing", "earnings", "price", "thesis", "risk", "manual"]
    severity: Literal["info", "warning", "critical"]
    status: Literal["open", "reviewed", "dismissed"] = "open"
    detail: str = Field(min_length=1, max_length=8_000)
    review_required: Literal[True] = True
    research_run_policy: Literal["manual_operator_approval_required"] = "manual_operator_approval_required"
    created_at: str

    @field_validator("created_at")
    @classmethod
    def alert_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)


class ApprovalReceipt(StrictModel):
    """An immutable local approval—not evidence of an external publication."""

    contract_id: Literal["room16.os.approval_receipt"] = "room16.os.approval_receipt"
    contract_version: Literal[1] = 1
    approval_id: str = Field(pattern=STABLE_ID_PATTERN)
    edition_id: str = Field(pattern=STABLE_ID_PATTERN)
    dossier_id: str = Field(pattern=STABLE_ID_PATTERN)
    edition_content_sha256: str = Field(pattern=SHA256_PATTERN)
    operator_confirmation: Literal["APPROVE_PUBLIC_DRAFT"] = "APPROVE_PUBLIC_DRAFT"
    scope: Literal["adapter_draft_only_no_external_publication"] = (
        "adapter_draft_only_no_external_publication"
    )
    approved_at: str

    @field_validator("approved_at")
    @classmethod
    def approval_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)


class PublicationEdition(StrictModel):
    """A separate, compliance-gated derivative of an immutable dossier."""

    contract_id: Literal["room16.os.publication_edition"] = "room16.os.publication_edition"
    contract_version: Literal[1] = 1
    edition_id: str = Field(pattern=STABLE_ID_PATTERN)
    edition_version: int = Field(ge=1)
    dossier: DossierReference
    language: Literal["de-DE"] = "de-DE"
    headline: str = Field(min_length=1, max_length=300)
    factual_content: str = Field(min_length=1, max_length=80_000)
    interpretation: str = Field(min_length=1, max_length=80_000)
    assumptions: str = Field(min_length=1, max_length=30_000)
    uncertainty: str = Field(min_length=1, max_length=30_000)
    methodology: str = Field(min_length=1, max_length=30_000)
    conflicts_disclosure: str = Field(min_length=1, max_length=30_000)
    risk_warning: str = Field(min_length=1, max_length=30_000)
    source_rights_confirmed: Literal[True] = True
    public_evidence_status: Literal["eligible"] = "eligible"
    private_data_included: Literal[False] = False
    status: Literal["draft", "approved_for_adapter_draft", "retracted_internal_only"] = "draft"
    external_delivery_state: Literal["not_configured", "adapter_draft_created"] = "not_configured"
    approval_receipt: ApprovalReceipt | None = None
    created_at: str
    updated_at: str
    edition_content_sha256: str = Field(pattern=SHA256_PATTERN)
    edition_sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("created_at", "updated_at")
    @classmethod
    def edition_timestamps_are_aware(cls, value: str) -> str:
        return _aware_timestamp(value)

    @model_validator(mode="after")
    def edition_is_separate_private_safe_and_hash_bound(self) -> "PublicationEdition":
        content_exclude = {
            "approval_receipt",
            "status",
            "external_delivery_state",
            "created_at",
            "updated_at",
            "edition_content_sha256",
            "edition_sha256",
        }
        if _hash_body(self, exclude=content_exclude) != self.edition_content_sha256:
            raise ValueError("publication edition content hash mismatch")
        if _hash_body(self, exclude={"edition_sha256"}) != self.edition_sha256:
            raise ValueError("publication edition hash mismatch")
        if self.status == "approved_for_adapter_draft":
            if not self.approval_receipt:
                raise ValueError("approved edition requires an approval receipt")
            if self.approval_receipt.edition_id != self.edition_id:
                raise ValueError("approval receipt belongs to a different edition")
            if self.approval_receipt.dossier_id != self.dossier.dossier_id:
                raise ValueError("approval receipt belongs to a different dossier")
            if self.approval_receipt.edition_content_sha256 != self.edition_content_sha256:
                raise ValueError("approval receipt does not bind this edition content")
        elif self.approval_receipt is not None:
            raise ValueError("only an approved edition may have an approval receipt")
        if self.external_delivery_state == "adapter_draft_created" and self.status != "approved_for_adapter_draft":
            raise ValueError("adapter drafts require a locally approved edition")
        return self

    @classmethod
    def create(cls, **payload: object) -> "PublicationEdition":
        content_exclude = {
            "approval_receipt",
            "status",
            "external_delivery_state",
            "created_at",
            "updated_at",
            "edition_content_sha256",
            "edition_sha256",
        }
        provisional = cls.model_construct(
            **payload,
            edition_content_sha256="0" * 64,
            edition_sha256="0" * 64,
        )
        content_hash = _hash_body(provisional, exclude=content_exclude)
        full_with_content = provisional.model_copy(update={"edition_content_sha256": content_hash})
        return cls(
            **payload,
            edition_content_sha256=content_hash,
            edition_sha256=_hash_body(full_with_content, exclude={"edition_sha256"}),
        )

    def approve(self, *, approval_id: str, approved_at: str) -> "PublicationEdition":
        if self.status != "draft":
            raise Room16OSContractError("only a draft edition can be approved")
        receipt = ApprovalReceipt(
            approval_id=approval_id,
            edition_id=self.edition_id,
            dossier_id=self.dossier.dossier_id,
            edition_content_sha256=self.edition_content_sha256,
            approved_at=approved_at,
        )
        payload = self.model_dump(
            mode="python",
            exclude={
                "edition_content_sha256",
                "edition_sha256",
                "approval_receipt",
                "status",
                "updated_at",
            },
        )
        # model_dump intentionally turns nested models into dictionaries. Keep
        # the typed immutable reference while calculating the next edition hash.
        payload["dossier"] = self.dossier
        return PublicationEdition.create(
            **payload,
            status="approved_for_adapter_draft",
            approval_receipt=receipt,
            updated_at=approved_at,
        )


class CommissionBrief(StrictModel):
    """A manually fulfilled special-report brief without CRM or customer data."""

    contract_id: Literal["room16.os.commission_brief"] = "room16.os.commission_brief"
    contract_version: Literal[1] = 1
    brief_id: str = Field(pattern=STABLE_ID_PATTERN)
    reference: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{2,79}$")
    dossier_refs: tuple[DossierReference, ...]
    scope: str = Field(min_length=1, max_length=20_000)
    requirements: str = Field(min_length=1, max_length=20_000)
    status: Literal["draft", "approved_for_manual_delivery", "delivered_manual"] = "draft"
    delivery_mode: Literal["manual_only_no_customer_portal"] = "manual_only_no_customer_portal"
    created_at: str
    updated_at: str

    @field_validator("created_at", "updated_at")
    @classmethod
    def brief_timestamps_are_aware(cls, value: str) -> str:
        return _aware_timestamp(value)

    @model_validator(mode="after")
    def brief_requires_closed_dossier_set(self) -> "CommissionBrief":
        ids = tuple(f"{item.dossier_id}:{item.dossier_version}" for item in self.dossier_refs)
        _unique_sorted(ids, "dossier_refs")
        if not ids:
            raise ValueError("a commission brief needs at least one dossier reference")
        return self


class CopilotSession(StrictModel):
    """A consent-bound record for a source-limited future copilot interaction."""

    contract_id: Literal["room16.os.copilot_session"] = "room16.os.copilot_session"
    contract_version: Literal[1] = 1
    session_id: str = Field(pattern=STABLE_ID_PATTERN)
    privacy_zone: Literal["public_evidence"] = "public_evidence"
    source_snapshot_ids: tuple[str, ...]
    allowed_operation: Literal["navigate", "compare", "formulate"]
    provider_status: Literal["not_configured", "consented_configured"] = "not_configured"
    explicit_consent: Literal[True] = True
    created_at: str
    response_source_refs: tuple[str, ...] = ()

    @field_validator("created_at")
    @classmethod
    def copilot_timestamp_is_aware(cls, value: str) -> str:
        return _aware_timestamp(value)

    @model_validator(mode="after")
    def copilot_is_source_bound(self) -> "CopilotSession":
        _unique_sorted(self.source_snapshot_ids, "source_snapshot_ids")
        _unique_sorted(self.response_source_refs, "response_source_refs")
        if not self.source_snapshot_ids:
            raise ValueError("a copilot session needs explicit source snapshots")
        if set(self.response_source_refs) - set(self.source_snapshot_ids):
            raise ValueError("copilot response references must be part of the consented source set")
        return self
