from __future__ import annotations

import pytest
from pydantic import ValidationError

from research_agent.room16_os.contracts import (
    ClaimRecord,
    CompilerPassReceipt,
    CopilotSession,
    DossierVersion,
    EvidenceGraph,
    FactLedgerEntry,
    IssuerIdentity,
    ProviderEntitlement,
    PublicationEdition,
    ResearchRun,
    SourceSnapshot,
)
from research_agent.room16_os.projection import build_verified_dossier


def _hash(character: str) -> str:
    return character * 64


def _source() -> SourceSnapshot:
    return SourceSnapshot.create(
        snapshot_id="sec.acme.2026-11-20",
        issuer_id="acme",
        provider_id="sec",
        source_kind="regulator_filing",
        locator="https://www.sec.gov/Archives/example",
        retrieved_at="2026-11-20T12:00:00+00:00",
        content_sha256=_hash("a"),
        manifest_sha256=_hash("b"),
        private_research_rights="allowed",
        public_edition_rights="allowed",
    )


def _evidence() -> EvidenceGraph:
    fact = FactLedgerEntry(
        fact_id="revenue.ttm",
        metric_id="revenue_ttm",
        source_snapshot_id="sec.acme.2026-11-20",
        period_basis="TTM",
        currency="USD",
        currency_required=True,
        value=100.0,
        claimability="accepted",
    )
    claim = ClaimRecord(
        claim_id="revenue.statement",
        claim_kind="factual",
        supporting_fact_ids=("revenue.ttm",),
        status="supported",
    )
    return EvidenceGraph.create(
        graph_id="acme.evidence.2026-11-20",
        facts=(fact,),
        claims=(claim,),
        status="verified",
    )


def _run() -> ResearchRun:
    receipts = tuple(
        CompilerPassReceipt(
            pass_id=pass_id,
            status="executed",
            input_sha256=_hash("c"),
            output_sha256=_hash("d"),
        )
        for pass_id in (
            "instrument_identity",
            "source_snapshot",
            "normalize_ir",
            "facts_evidence",
            "metrics_scenarios",
            "claims_decision",
            "quality_release",
            "sign_dossier",
        )
    )
    return ResearchRun.create(
        run_id="acme.run.2026-11-20",
        issuer_id="acme",
        as_of_date="2026-11-20",
        compiler_version="research_agent.current@1",
        input_sha256=_hash("e"),
        authority_bundle_sha256=_hash("f"),
        pass_receipts=receipts,
        status="verified",
        release_verdict="verified",
        created_at="2026-11-20T12:00:00+00:00",
    )


def _dossier(*, public_evidence_status: str = "eligible") -> DossierVersion:
    source = _source()
    evidence = _evidence()
    run = _run()
    return DossierVersion.create(
        dossier_id="acme.dossier",
        version=1,
        issuer_id="acme",
        as_of_date="2026-11-20",
        source_snapshot_sha256s=(source.snapshot_sha256,),
        research_run_sha256=run.run_sha256,
        evidence_graph_sha256=evidence.evidence_graph_sha256,
        compiler_version=run.compiler_version,
        quality_verdict="verified",
        public_evidence_status=public_evidence_status,
        bundle_sha256=_hash("1"),
    )


def test_hash_bound_dossier_references_the_verified_compiler_inputs() -> None:
    dossier = _dossier()

    dossier.verify_hash()
    reference = dossier.reference()

    assert reference.dossier_id == "acme.dossier"
    assert reference.dossier_sha256 == dossier.dossier_sha256
    assert reference.bundle_sha256 == _hash("1")


def test_unknown_currency_or_source_cannot_be_claimable() -> None:
    with pytest.raises(ValidationError, match="unknown semantics"):
        FactLedgerEntry(
            fact_id="revenue.ttm",
            metric_id="revenue_ttm",
            source_snapshot_id="sec.acme.2026-11-20",
            period_basis="TTM",
            currency_required=True,
            claimability="accepted",
        )

    blocked = FactLedgerEntry(
        fact_id="revenue.ttm",
        metric_id="revenue_ttm",
        source_snapshot_id=None,
        period_basis="TTM",
        currency="USD",
        currency_required=True,
        claimability="blocked",
        blocker_codes=("SOURCE_UNKNOWN",),
    )
    assert blocked.claimability == "blocked"


def test_paid_provider_cannot_be_selected_without_a_receipt() -> None:
    with pytest.raises(ValidationError, match="paid provider"):
        ProviderEntitlement(
            entitlement_id="vendor.paid",
            provider_id="vendor",
            provider_class="licensed_paid",
            status="active",
            allowed_uses=("private_research",),
        )


def test_public_edition_is_a_separate_gated_derivative_and_never_publishable() -> None:
    edition = PublicationEdition.create(
        edition_id="acme.public.1",
        edition_version=1,
        dossier=_dossier().reference(),
        headline="Acme: Research-Notiz",
        factual_content="Die Fakten sind quellengebunden dargestellt.",
        interpretation="Die Einordnung ist klar als Interpretation gekennzeichnet.",
        assumptions="Die Annahmen sind sichtbar.",
        uncertainty="Die Unsicherheit ist sichtbar.",
        methodology="Die Bewertungsmethodik ist erläutert.",
        conflicts_disclosure="Kein offengelegter Konflikt.",
        risk_warning="Keine Anlageempfehlung; Risiken sind eigenständig zu prüfen.",
        created_at="2026-11-20T12:00:00+00:00",
        updated_at="2026-11-20T12:00:00+00:00",
    )

    approved = edition.approve(
        approval_id="approval.acme.public.1",
        approved_at="2026-11-20T12:05:00+00:00",
    )

    assert approved.status == "approved_for_adapter_draft"
    assert approved.approval_receipt is not None
    assert approved.approval_receipt.scope == "adapter_draft_only_no_external_publication"
    assert approved.external_delivery_state == "not_configured"

    with pytest.raises(ValidationError):
        PublicationEdition.create(
            edition_id="acme.public.private",
            edition_version=1,
            dossier=_dossier().reference(),
            headline="Unzulässig",
            factual_content="Fakten",
            interpretation="Interpretation",
            assumptions="Annahmen",
            uncertainty="Unsicherheit",
            methodology="Methode",
            conflicts_disclosure="Konflikte",
            risk_warning="Risiko",
            private_data_included=True,
            created_at="2026-11-20T12:00:00+00:00",
            updated_at="2026-11-20T12:00:00+00:00",
        )


def test_copilot_contract_rejects_private_zone_and_unbound_sources() -> None:
    with pytest.raises(ValidationError):
        CopilotSession(
            session_id="copilot.acme.1",
            privacy_zone="private_portfolio",
            source_snapshot_ids=("sec.acme.2026-11-20",),
            allowed_operation="compare",
            created_at="2026-11-20T12:00:00+00:00",
        )

    with pytest.raises(ValidationError, match="response references"):
        CopilotSession(
            session_id="copilot.acme.2",
            source_snapshot_ids=("sec.acme.2026-11-20",),
            response_source_refs=("other.source",),
            allowed_operation="compare",
            created_at="2026-11-20T12:00:00+00:00",
        )


def test_only_source_native_verified_contracts_can_create_a_current_dossier() -> None:
    identity = IssuerIdentity(
        issuer_id="acme",
        legal_name="Acme Corp.",
        jurisdiction="US",
        primary_symbol="ACME",
        primary_exchange="NYSE",
        identity_source_snapshot_id="sec.acme.2026-11-20",
    )
    dossier = build_verified_dossier(
        dossier_id="acme.current",
        version=1,
        identity=identity,
        sources=(_source(),),
        evidence_graph=_evidence(),
        research_run=_run(),
        bundle_sha256=_hash("2"),
    )

    assert dossier.quality_verdict == "verified"
    assert dossier.public_evidence_status == "eligible"

    private_only_payload = _source().model_dump(
        mode="python", exclude={"snapshot_sha256"}
    )
    private_only_payload["public_edition_rights"] = "blocked"
    private_only_source = SourceSnapshot.create(
        **private_only_payload,
    )
    private_only_dossier = build_verified_dossier(
        dossier_id="acme.private-only",
        version=1,
        identity=identity,
        sources=(private_only_source,),
        evidence_graph=_evidence(),
        research_run=_run(),
        bundle_sha256=_hash("3"),
    )
    assert private_only_dossier.public_evidence_status == "blocked"
