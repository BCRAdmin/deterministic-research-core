"""Read-only projections between existing authority bundles and Room16 OS.

The existing authority-bundle contract is still a valid, hash-verifiable
reader/migration source.  It is not silently promoted to the new source-native
compiler truth.  Therefore its projection is permanently marked historical
and reader-only.  New verified dossiers can only be built through
``build_verified_dossier`` from explicit source-native contracts.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel
from research_agent.integration.authority_bundle import verify_authority_bundle

from .contracts import (
    ClaimRecord,
    CompilerPassReceipt,
    DossierVersion,
    EvidenceGraph,
    FactLedgerEntry,
    IssuerIdentity,
    ResearchRun,
    SourceSnapshot,
)


class AuthorityProjectionError(ValueError):
    """An existing bundle cannot be safely projected into the new boundary."""


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AuthorityProjectionError(f"required authority artifact missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AuthorityProjectionError(f"invalid authority artifact JSON: {path}") from exc
    if not isinstance(value, dict):
        raise AuthorityProjectionError(f"authority artifact must be an object: {path}")
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_id(prefix: str, value: object) -> str:
    normalized = re.sub(r"[^a-z0-9_.:-]+", ".", str(value).strip().lower())
    normalized = normalized.strip(".")
    if not normalized:
        raise AuthorityProjectionError(f"cannot derive stable identifier for {prefix}")
    candidate = f"{prefix}.{normalized}"
    if not re.fullmatch(r"[a-z][a-z0-9_.:-]*", candidate):
        raise AuthorityProjectionError(f"invalid projected identifier: {candidate}")
    return candidate


def _source_kind(source_type: object) -> str:
    mapping = {
        "sec_filing": "regulator_filing",
        "company_ir": "issuer_ir",
        "exchange_ohlcv": "exchange_market_data",
        "trusted_market_data_vendor": "licensed_market_data",
        "official_registry": "official_registry",
        "bse_filing": "official_registry",
    }
    resolved = mapping.get(str(source_type or ""))
    if not resolved:
        raise AuthorityProjectionError(f"unknown source type has no Room16 adapter: {source_type!r}")
    return resolved


def _historical_pass_receipts() -> tuple[CompilerPassReceipt, ...]:
    return tuple(
        CompilerPassReceipt(pass_id=pass_id, status="skipped")
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


class HistoricalAuthorityProjection(StrictModel):
    """A non-promoting migration record for a verified legacy authority bundle."""

    contract_id: Literal["room16.os.historical_authority_projection"] = (
        "room16.os.historical_authority_projection"
    )
    contract_version: Literal[1] = 1
    origin_contract: Literal["room16.research_authority_bundle@3"] = (
        "room16.research_authority_bundle@3"
    )
    migration_mode: Literal["hash_verified_reader_only"] = "hash_verified_reader_only"
    authority_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshots: tuple[SourceSnapshot, ...]
    evidence_graph: EvidenceGraph
    research_run: ResearchRun
    dossier: DossierVersion
    projection_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def reader_projection_cannot_become_authority(self) -> "HistoricalAuthorityProjection":
        if self.dossier.quality_verdict != "historical_reference":
            raise ValueError("historical authority projection must remain a historical reference")
        if not self.dossier.historical_reader_only:
            raise ValueError("historical authority projection must be reader-only")
        if self.dossier.public_evidence_status != "blocked":
            raise ValueError("historical authority projection must not feed a public edition")
        expected = sha256_json(self.model_dump(mode="json", exclude={"projection_sha256"}))
        if expected != self.projection_sha256:
            raise ValueError("historical projection hash mismatch")
        return self

    @classmethod
    def create(cls, **payload: object) -> "HistoricalAuthorityProjection":
        provisional = cls.model_construct(**payload, projection_sha256="0" * 64)
        return cls(
            **payload,
            projection_sha256=sha256_json(
                provisional.model_dump(mode="json", exclude={"projection_sha256"})
            ),
        )


def project_historical_authority_bundle(bundle_dir: str | Path) -> HistoricalAuthorityProjection:
    """Import one valid v3 authority bundle as immutable reader-only history.

    No value in the result is eligible to run a new analysis, become a public
    edition, or overwrite a current source-native dossier.
    """

    root = Path(bundle_dir).expanduser().resolve()
    verification = verify_authority_bundle(root)
    if verification.get("status") != "pass":
        failures = ",".join(verification.get("blocking_failures") or [])
        raise AuthorityProjectionError(
            "authority bundle failed hash/quality verification"
            + (f": {failures}" if failures else "")
        )
    manifest = _read_json(root / "authority_manifest.json")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        raise AuthorityProjectionError("authority manifest has no artifact index")
    snapshot_manifest_record = artifacts.get("source_snapshot_manifest")
    if not isinstance(snapshot_manifest_record, dict):
        raise AuthorityProjectionError("authority manifest lacks source snapshot manifest")
    snapshot_manifest = _read_json(root / str(snapshot_manifest_record.get("path") or ""))
    registry_record = artifacts.get("source_registry")
    if not isinstance(registry_record, dict):
        raise AuthorityProjectionError("authority manifest lacks source registry")
    registry = _read_json(root / str(registry_record.get("path") or ""))
    ticker = str(manifest.get("ticker") or "").strip().upper()
    as_of_date = str(manifest.get("as_of_date") or "").strip()
    if not re.fullmatch(r"[A-Z0-9.^-]{1,24}", ticker) or not as_of_date:
        raise AuthorityProjectionError("authority bundle has an invalid ticker or as-of date")
    issuer_id = _stable_id("issuer", ticker)
    manifest_sha256 = _file_sha256(root / "authority_manifest.json")
    snapshot_manifest_sha256 = str(snapshot_manifest_record.get("sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot_manifest_sha256):
        raise AuthorityProjectionError("source snapshot manifest hash is missing")

    registry_by_id = {
        str(item.get("source_id") or ""): item
        for item in registry.get("sources") or []
        if isinstance(item, dict) and str(item.get("source_id") or "")
    }
    artifacts_by_id = {
        str(item.get("snapshot_id") or ""): item
        for item in snapshot_manifest.get("artifacts") or []
        if isinstance(item, dict) and str(item.get("snapshot_id") or "")
    }
    source_snapshots: list[SourceSnapshot] = []
    for disposition in snapshot_manifest.get("source_dispositions") or []:
        if not isinstance(disposition, dict):
            raise AuthorityProjectionError("invalid source disposition in authority bundle")
        if disposition.get("disposition") != "material_evidence":
            continue
        source_id = str(disposition.get("source_id") or "")
        registry_source = registry_by_id.get(source_id)
        if not registry_source:
            raise AuthorityProjectionError(f"source disposition has no registry record: {source_id}")
        retrieved = disposition.get("retrieved_at")
        retrieved_at = retrieved.get("value") if isinstance(retrieved, dict) else None
        if not retrieved_at:
            raise AuthorityProjectionError(f"source retrieval time is unknown: {source_id}")
        for snapshot_id in disposition.get("snapshot_ids") or []:
            artifact = artifacts_by_id.get(str(snapshot_id))
            if not artifact:
                raise AuthorityProjectionError(f"source disposition references missing snapshot: {snapshot_id}")
            content_sha256 = str(artifact.get("sha256") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
                raise AuthorityProjectionError(f"source snapshot hash is invalid: {snapshot_id}")
            locator = str(disposition.get("url") or "").strip()
            if not locator:
                # This is a local immutable locator, not an invented public URL.
                locator = f"room16://historical-source/{source_id}/{snapshot_id}"
            source_snapshots.append(
                SourceSnapshot.create(
                    snapshot_id=str(snapshot_id),
                    issuer_id=issuer_id,
                    provider_id=_stable_id("provider", source_id),
                    source_kind=_source_kind(registry_source.get("source_type")),
                    locator=locator,
                    retrieved_at=str(retrieved_at),
                    content_sha256=content_sha256,
                    manifest_sha256=snapshot_manifest_sha256,
                    private_research_rights="blocked",
                    public_edition_rights="blocked",
                )
            )
    source_snapshots = sorted(source_snapshots, key=lambda item: item.snapshot_id)
    if not source_snapshots:
        raise AuthorityProjectionError("authority bundle contains no material source snapshots")

    facts = tuple(
        FactLedgerEntry(
            fact_id=f"legacy.fact.{item.snapshot_id}",
            metric_id="legacy_source_reference",
            source_snapshot_id=item.snapshot_id,
            period_basis="historical_reference",
            period_required=True,
            claimability="blocked",
            blocker_codes=("LEGACY_AUTHORITY_READER_ONLY",),
        )
        for item in source_snapshots
    )
    claims = tuple(
        ClaimRecord(
            claim_id=f"legacy.claim.{item.snapshot_id}",
            claim_kind="factual",
            supporting_fact_ids=(f"legacy.fact.{item.snapshot_id}",),
            status="blocked",
            blocker_codes=("LEGACY_AUTHORITY_READER_ONLY",),
        )
        for item in source_snapshots
    )
    evidence_graph = EvidenceGraph.create(
        graph_id=f"legacy.evidence.{ticker.lower()}.{as_of_date.replace('-', '.')}",
        facts=facts,
        claims=claims,
        status="blocked",
    )
    run = ResearchRun.create(
        run_id=f"legacy.run.{ticker.lower()}.{as_of_date.replace('-', '.')}",
        issuer_id=issuer_id,
        as_of_date=as_of_date,
        compiler_version="authority_bundle_v3_reader_migration",
        input_sha256=manifest_sha256,
        authority_bundle_sha256=manifest_sha256,
        pass_receipts=_historical_pass_receipts(),
        status="blocked",
        release_verdict="blocked",
        created_at=str(manifest.get("generated_at") or ""),
    )
    dossier = DossierVersion.create(
        dossier_id=f"legacy.dossier.{ticker.lower()}.{as_of_date.replace('-', '.')}",
        version=1,
        issuer_id=issuer_id,
        as_of_date=as_of_date,
        source_snapshot_sha256s=tuple(
            sorted(item.snapshot_sha256 for item in source_snapshots)
        ),
        research_run_sha256=run.run_sha256,
        evidence_graph_sha256=evidence_graph.evidence_graph_sha256,
        compiler_version=run.compiler_version,
        quality_verdict="historical_reference",
        public_evidence_status="blocked",
        historical_reader_only=True,
        bundle_sha256=manifest_sha256,
    )
    return HistoricalAuthorityProjection.create(
        authority_manifest_sha256=manifest_sha256,
        source_snapshots=tuple(source_snapshots),
        evidence_graph=evidence_graph,
        research_run=run,
        dossier=dossier,
    )


def build_verified_dossier(
    *,
    dossier_id: str,
    version: int,
    identity: IssuerIdentity,
    sources: tuple[SourceSnapshot, ...],
    evidence_graph: EvidenceGraph,
    research_run: ResearchRun,
    bundle_sha256: str,
) -> DossierVersion:
    """Build the only current, public-edition-capable dossier form.

    This intentionally accepts compiler-native contracts only.  A historical
    authority bundle must go through ``project_historical_authority_bundle``
    instead and will remain reader-only.
    """

    if identity.identity_status != "verified":
        raise AuthorityProjectionError("issuer identity is blocked")
    if research_run.status != "verified" or research_run.release_verdict != "verified":
        raise AuthorityProjectionError("research run is not release-verified")
    if evidence_graph.status != "verified":
        raise AuthorityProjectionError("evidence graph is not verified")
    if research_run.issuer_id != identity.issuer_id:
        raise AuthorityProjectionError("research run identity differs from dossier identity")
    if not sources:
        raise AuthorityProjectionError("verified dossier requires source snapshots")
    source_ids = {item.snapshot_id for item in sources}
    if any(item.issuer_id != identity.issuer_id for item in sources):
        raise AuthorityProjectionError("source snapshot identity differs from dossier identity")
    if any(item.private_research_rights != "allowed" for item in sources):
        raise AuthorityProjectionError("a source snapshot lacks private-research rights")
    fact_sources = {item.source_snapshot_id for item in evidence_graph.facts}
    if None in fact_sources or not fact_sources <= source_ids:
        raise AuthorityProjectionError("evidence graph references unknown source snapshots")
    public_status = (
        "eligible"
        if all(item.public_edition_rights == "allowed" for item in sources)
        else "blocked"
    )
    return DossierVersion.create(
        dossier_id=dossier_id,
        version=version,
        issuer_id=identity.issuer_id,
        as_of_date=research_run.as_of_date,
        source_snapshot_sha256s=tuple(sorted(item.snapshot_sha256 for item in sources)),
        research_run_sha256=research_run.run_sha256,
        evidence_graph_sha256=evidence_graph.evidence_graph_sha256,
        compiler_version=research_run.compiler_version,
        quality_verdict="verified",
        public_evidence_status=public_status,
        bundle_sha256=bundle_sha256,
    )
