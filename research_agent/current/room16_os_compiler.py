"""Compile a verified current authority bundle into Room16's source-native OS IR.

This compiler is intentionally a strict adapter over hash-verified source
snapshots, typed evidence and the current deterministic bundle.  It never
parses a rendered Markdown report.  A missing identity, source, period,
currency or source-rights decision produces a blocked dossier receipt rather
than a guessed interpretation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.integration.authority_bundle import verify_authority_bundle
from research_agent.room16_os.contracts import (
    ClaimRecord,
    CompilerPassReceipt,
    DossierVersion,
    EvidenceGraph,
    FactLedgerEntry,
    IssuerIdentity,
    ResearchRun,
    SourceSnapshot,
)


ROOM16_OS_RECEIPT_CONTRACT_ID = "room16.os.source_native_dossier_receipt"
ROOM16_OS_RECEIPT_CONTRACT_VERSION = 1
ROOM16_OS_COMPILER_VERSION = "research_agent.current.source_native@1"
ROOM16_OS_RECEIPT_FIELDS = frozenset(
    {
        "contract_id",
        "contract_version",
        "compiler_version",
        "status",
        "authority_manifest_sha256",
        "issuer_identity",
        "source_snapshots",
        "evidence_graph",
        "research_run",
        "dossier",
        "public_edition_policy",
        "receipt_sha256",
    }
)
ROOM16_OS_PUBLIC_EDITION_POLICY = (
    "blocked_until_provider_entitlements_and_publication_policy_are_approved"
)


class CurrentRoom16OSCompilerError(ValueError):
    """The authority bundle cannot produce a safe Room16 OS dossier receipt."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CurrentRoom16OSCompilerError(f"authority artifact missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CurrentRoom16OSCompilerError(f"authority artifact is invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise CurrentRoom16OSCompilerError(f"authority artifact must be an object: {path}")
    return payload


def _stable_id(prefix: str, value: object) -> str:
    normalized = re.sub(r"[^a-z0-9_.:-]+", ".", str(value or "").strip().lower())
    normalized = normalized.strip(".")
    if not normalized:
        raise CurrentRoom16OSCompilerError(f"missing identifier for {prefix}")
    candidate = f"{prefix}.{normalized}"
    if not re.fullmatch(r"[a-z][a-z0-9_.:-]*", candidate):
        raise CurrentRoom16OSCompilerError(f"unsafe compiler identifier: {candidate}")
    return candidate


def _required_artifact(manifest: Mapping[str, Any], root: Path, role: str) -> tuple[Path, str]:
    artifacts = manifest.get("artifacts")
    item = artifacts.get(role) if isinstance(artifacts, Mapping) else None
    if not isinstance(item, Mapping):
        raise CurrentRoom16OSCompilerError(f"authority manifest lacks required artifact: {role}")
    relative = str(item.get("path") or "")
    digest = str(item.get("sha256") or "")
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise CurrentRoom16OSCompilerError(f"authority artifact path is unsafe: {role}")
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise CurrentRoom16OSCompilerError(f"authority artifact hash is invalid: {role}")
    target = (root / relative).resolve()
    if root not in target.parents or not target.is_file():
        raise CurrentRoom16OSCompilerError(f"authority artifact is outside the bundle: {role}")
    return target, digest


def _source_kind(source_type: object) -> str:
    mapping = {
        "sec_filing": "regulator_filing",
        "company_ir": "issuer_ir",
        "official_press_release": "issuer_ir",
        "exchange_ohlcv": "exchange_market_data",
        "trusted_market_data_vendor": "licensed_market_data",
        "official_registry": "official_registry",
        "bse_filing": "official_registry",
    }
    resolved = mapping.get(str(source_type or ""))
    if not resolved:
        raise CurrentRoom16OSCompilerError(
            f"source type has no Room16 source-native adapter: {source_type!r}"
        )
    return resolved


def _currency_from_evidence(item: Mapping[str, Any]) -> str | None:
    direct = str(item.get("currency") or "").strip().upper()
    if re.fullmatch(r"[A-Z]{3}", direct):
        return direct
    unit = str(item.get("unit") or item.get("source_unit") or "").strip().upper()
    if re.fullmatch(r"[A-Z]{3}", unit):
        return unit
    match = re.fullmatch(r"([A-Z]{3})(?:_PER_SHARE|/SHARE)", unit)
    return match.group(1) if match else None


def _currency_is_required(item: Mapping[str, Any]) -> bool:
    dimension = str(item.get("dimension") or "").strip().lower()
    if dimension in {"currency", "per_share"}:
        return True
    unit = str(item.get("unit") or item.get("source_unit") or "").strip().upper()
    return bool(re.fullmatch(r"[A-Z]{3}(?:_PER_SHARE|/SHARE)?", unit))


def _interoperable_fact_value(value: object) -> object:
    """Preserve fact values without Python/JavaScript number-hash drift.

    The private dossier receipt is verified by the macOS product in Node.
    JSON has no distinction between e.g. Python's ``100.0`` and JavaScript's
    ``100`` after parsing, and values outside JavaScript's safe integer range
    can silently change as well. Facts are therefore represented as their
    source-native decimal lexical value whenever they arrive as a number.
    Downstream metric passes already retain their typed calculation packet;
    this evidence ledger is the cross-language, auditable record.
    """

    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in {float("inf"), float("-inf")}:
            raise CurrentRoom16OSCompilerError("fact value is not a finite number")
        return repr(value)
    return value


def _rights_for_source(source_type: object) -> str:
    """Current research may only reuse sources whose private use is known."""

    if str(source_type or "") == "trusted_market_data_vendor":
        # A paid/vendor source needs a ProviderEntitlement before it can be
        # promoted into a current dossier; never assume a subscription licence.
        return "blocked"
    return "allowed"


def _manifest_hash(manifest: Mapping[str, Any]) -> str:
    """The canonical manifest hash is stable even when the directory moves."""

    return sha256_json(dict(manifest))


def _pass_receipts(
    *,
    identity: IssuerIdentity,
    sources: tuple[SourceSnapshot, ...],
    evidence: EvidenceGraph,
    data_packet_sha256: str,
    metrics_sha256: str,
    decision_sha256: str,
    authority_manifest_sha256: str,
    blockers: tuple[str, ...],
    dossier_id: str,
) -> tuple[CompilerPassReceipt, ...]:
    completed = not blockers
    quality_status = "executed" if completed else "failed"
    sign_status = "executed" if completed else "skipped"
    source_hash = sha256_json([item.model_dump(mode="json") for item in sources])
    identity_hash = sha256_json(identity.model_dump(mode="json"))
    signing_input_hash = sha256_json(
        {
            "dossier_id": dossier_id,
            "authority_manifest_sha256": authority_manifest_sha256,
            "evidence_graph_sha256": evidence.evidence_graph_sha256,
        }
    )
    return (
        CompilerPassReceipt(
            pass_id="instrument_identity",
            status="executed",
            input_sha256=data_packet_sha256,
            output_sha256=identity_hash,
        ),
        CompilerPassReceipt(
            pass_id="source_snapshot",
            status="executed",
            input_sha256=authority_manifest_sha256,
            output_sha256=source_hash,
        ),
        CompilerPassReceipt(
            pass_id="normalize_ir",
            status="executed",
            input_sha256=data_packet_sha256,
            output_sha256=sha256_json(
                {
                    "identity": identity_hash,
                    "source_snapshot_hash": source_hash,
                    "metrics_artifact_sha256": metrics_sha256,
                }
            ),
        ),
        CompilerPassReceipt(
            pass_id="facts_evidence",
            status="executed",
            input_sha256=source_hash,
            output_sha256=evidence.evidence_graph_sha256,
        ),
        CompilerPassReceipt(
            pass_id="metrics_scenarios",
            status="executed",
            input_sha256=evidence.evidence_graph_sha256,
            output_sha256=metrics_sha256,
        ),
        CompilerPassReceipt(
            pass_id="claims_decision",
            status="executed",
            input_sha256=metrics_sha256,
            output_sha256=decision_sha256,
        ),
        CompilerPassReceipt(
            pass_id="quality_release",
            status=quality_status,
            input_sha256=authority_manifest_sha256,
            output_sha256=authority_manifest_sha256 if completed else None,
            diagnostic_codes=blockers if not completed else (),
        ),
        CompilerPassReceipt(
            pass_id="sign_dossier",
            status=sign_status,
            input_sha256=signing_input_hash if completed else None,
            output_sha256=signing_input_hash if completed else None,
        ),
    )


def compile_current_authority_bundle(
    *,
    authority_bundle_dir: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compile a current authority bundle into a source-native dossier receipt.

    A receipt is always emitted when the authority bundle itself verifies.  Its
    ``status`` is ``blocked`` if a source-native semantic prerequisite is
    unknown.  Product must not render a blocked receipt as an analysis.
    """

    root = Path(authority_bundle_dir).expanduser().resolve()
    verification = verify_authority_bundle(root)
    if verification.get("status") != "pass":
        failures = ",".join(verification.get("blocking_failures") or [])
        raise CurrentRoom16OSCompilerError(
            "authority bundle is not verified" + (f": {failures}" if failures else "")
        )
    manifest_path = root / "authority_manifest.json"
    manifest = _read_json(manifest_path)
    data_path, data_sha256 = _required_artifact(manifest, root, "data_packet")
    registry_path, _ = _required_artifact(manifest, root, "source_registry")
    snapshot_path, snapshot_sha256 = _required_artifact(manifest, root, "source_snapshot_manifest")
    evidence_path, _ = _required_artifact(manifest, root, "evidence_ledger")
    metrics_path, metrics_sha256 = _required_artifact(manifest, root, "metrics_packet")
    decision_path, decision_sha256 = _required_artifact(manifest, root, "decision_packet")
    data_packet = _read_json(data_path)
    source_registry = _read_json(registry_path)
    snapshot_manifest = _read_json(snapshot_path)
    evidence_ledger = _read_json(evidence_path)
    _read_json(metrics_path)
    _read_json(decision_path)

    ticker = str(data_packet.get("ticker") or "").strip().upper()
    as_of_date = str(data_packet.get("as_of_date") or "").strip()
    company_name = str(data_packet.get("company_name") or "").strip()
    jurisdiction = str(data_packet.get("jurisdiction") or "").strip().upper()
    exchange = str(data_packet.get("exchange") or "").strip()
    if not re.fullmatch(r"[A-Z0-9.^-]{1,24}", ticker):
        raise CurrentRoom16OSCompilerError("current authority bundle has no valid ticker identity")
    if not company_name or not re.fullmatch(r"[A-Z]{2}", jurisdiction) or not exchange:
        raise CurrentRoom16OSCompilerError(
            "issuer identity is incomplete; company name, jurisdiction and exchange are required"
        )
    issuer_id = _stable_id("issuer", ticker)
    registry_by_id = {
        str(item.get("source_id") or ""): item
        for item in source_registry.get("sources") or []
        if isinstance(item, Mapping) and str(item.get("source_id") or "")
    }
    artifact_by_snapshot_id = {
        str(item.get("snapshot_id") or ""): item
        for item in snapshot_manifest.get("artifacts") or []
        if isinstance(item, Mapping) and str(item.get("snapshot_id") or "")
    }
    sources: list[SourceSnapshot] = []
    snapshot_for_source: dict[str, str] = {}
    source_types: dict[str, str] = {}
    blockers: set[str] = set()
    for disposition in snapshot_manifest.get("source_dispositions") or []:
        if not isinstance(disposition, Mapping) or disposition.get("disposition") != "material_evidence":
            continue
        source_id = str(disposition.get("source_id") or "")
        registry_source = registry_by_id.get(source_id)
        if not registry_source:
            raise CurrentRoom16OSCompilerError(f"material source is missing from registry: {source_id}")
        snapshot_ids = sorted(str(item) for item in disposition.get("snapshot_ids") or [] if str(item))
        if not snapshot_ids:
            blockers.add("SOURCE_SNAPSHOT_UNKNOWN")
            continue
        artifact_hashes = []
        captured_at = None
        for snapshot_id in snapshot_ids:
            artifact = artifact_by_snapshot_id.get(snapshot_id)
            if not artifact:
                raise CurrentRoom16OSCompilerError(f"material source references unknown snapshot: {snapshot_id}")
            artifact_hash = str(artifact.get("sha256") or "")
            if not re.fullmatch(r"[a-f0-9]{64}", artifact_hash):
                raise CurrentRoom16OSCompilerError(f"snapshot hash is invalid: {snapshot_id}")
            artifact_hashes.append(artifact_hash)
            captured_at = captured_at or str(artifact.get("captured_at") or "")
        retrieval = disposition.get("retrieved_at")
        retrieved_at = retrieval.get("value") if isinstance(retrieval, Mapping) else None
        retrieved_at = str(retrieved_at or captured_at or "")
        if not retrieved_at:
            blockers.add("SOURCE_RETRIEVAL_TIME_UNKNOWN")
            continue
        source_type = str(registry_source.get("source_type") or "")
        source_types[source_id] = source_type
        source_snapshot_id = _stable_id("source", source_id)
        locator = str(disposition.get("url") or "").strip()
        if not locator:
            locator = f"room16://source-snapshot/{source_snapshot_id}"
        private_rights = _rights_for_source(source_type)
        if private_rights != "allowed":
            blockers.add("SOURCE_PRIVATE_RIGHTS_UNCONFIRMED")
        # No source may enter a public edition until the explicit provider and
        # publication-rights registry has been implemented and reviewed.
        sources.append(
            SourceSnapshot.create(
                snapshot_id=source_snapshot_id,
                issuer_id=issuer_id,
                provider_id=_stable_id("provider", source_id),
                source_kind=_source_kind(source_type),
                locator=locator,
                retrieved_at=retrieved_at,
                content_sha256=sha256_json({"snapshot_artifact_sha256s": artifact_hashes}),
                manifest_sha256=snapshot_sha256,
                private_research_rights=private_rights,
                public_edition_rights="blocked",
            )
        )
        snapshot_for_source[source_id] = source_snapshot_id
    sources = sorted(sources, key=lambda item: item.snapshot_id)
    if not sources:
        blockers.add("SOURCE_SNAPSHOT_UNKNOWN")

    identity_source = next(
        (
            snapshot_for_source[source_id]
            for source_id in sorted(snapshot_for_source)
            if source_types.get(source_id)
            in {"sec_filing", "company_ir", "official_press_release", "official_registry", "bse_filing"}
        ),
        None,
    )
    if not identity_source:
        raise CurrentRoom16OSCompilerError("issuer identity source cannot be bound to a primary snapshot")
    identity = IssuerIdentity(
        issuer_id=issuer_id,
        legal_name=company_name,
        jurisdiction=jurisdiction,
        primary_symbol=ticker,
        primary_exchange=exchange,
        identity_source_snapshot_id=identity_source,
        isin=str(data_packet.get("isin") or "").strip().upper() or None,
        wkn=str(data_packet.get("wkn") or "").strip().upper() or None,
    )

    facts: list[FactLedgerEntry] = []
    claims: list[ClaimRecord] = []
    evidence_items = evidence_ledger.get("evidence_items")
    if not isinstance(evidence_items, list):
        raise CurrentRoom16OSCompilerError("evidence ledger has no evidence item list")
    for evidence_index, item in enumerate(evidence_items):
        if not isinstance(item, Mapping):
            raise CurrentRoom16OSCompilerError("evidence ledger contains a non-object item")
        source_id = str(item.get("source_id") or "")
        source_snapshot_id = snapshot_for_source.get(source_id)
        metrics = item.get("supports_metrics")
        if not isinstance(metrics, list):
            metrics = []
        for metric_index, raw_metric in enumerate(metrics):
            metric = str(raw_metric or "").strip()
            fact_id = _stable_id("fact", f"{evidence_index}.{metric_index}.{item.get('evidence_id') or source_id}.{metric or 'unknown'}")
            blocker_codes: set[str] = set()
            metric_id = _stable_id("metric", metric) if metric else None
            if not metric_id:
                blocker_codes.add("METRIC_UNKNOWN")
            if not source_snapshot_id:
                blocker_codes.add("SOURCE_UNKNOWN")
            period = str(item.get("period") or item.get("period_kind") or "").strip()
            if not period or period == "unknown":
                blocker_codes.add("PERIOD_BASIS_UNKNOWN")
                period = None
            currency_required = _currency_is_required(item)
            currency = _currency_from_evidence(item)
            if currency_required and not currency:
                blocker_codes.add("CURRENCY_UNKNOWN")
            claimability = "blocked" if blocker_codes else "accepted"
            facts.append(
                FactLedgerEntry(
                    fact_id=fact_id,
                    metric_id=metric_id,
                    source_snapshot_id=source_snapshot_id,
                    period_basis=period,
                    currency=currency,
                    currency_required=currency_required,
                    period_required=True,
                    value=_interoperable_fact_value(
                        item.get("normalized_value", item.get("value"))
                    ),
                    claimability=claimability,
                    blocker_codes=tuple(sorted(blocker_codes)),
                )
            )
            claim_id = _stable_id("claim", f"{evidence_index}.{metric_index}.{metric or 'unknown'}")
            claims.append(
                ClaimRecord(
                    claim_id=claim_id,
                    claim_kind="factual",
                    supporting_fact_ids=(fact_id,),
                    status="blocked" if blocker_codes else "supported",
                    blocker_codes=tuple(sorted(blocker_codes)),
                )
            )
            blockers.update(blocker_codes)
    facts = sorted(facts, key=lambda item: item.fact_id)
    claims = sorted(claims, key=lambda item: item.claim_id)
    if not facts:
        blockers.add("FACT_LEDGER_EMPTY")
    evidence_graph = EvidenceGraph.create(
        graph_id=_stable_id("evidence", f"{ticker}.{as_of_date}"),
        facts=tuple(facts),
        claims=tuple(claims),
        status="blocked" if blockers else "verified",
    )

    manifest_sha256 = _manifest_hash(manifest)
    dossier_id = _stable_id("dossier", f"{ticker}.{as_of_date}")
    ordered_blockers = tuple(sorted(blockers))
    pass_receipts = _pass_receipts(
        identity=identity,
        sources=tuple(sources),
        evidence=evidence_graph,
        data_packet_sha256=data_sha256,
        metrics_sha256=metrics_sha256,
        decision_sha256=decision_sha256,
        authority_manifest_sha256=manifest_sha256,
        blockers=ordered_blockers,
        dossier_id=dossier_id,
    )
    research_run = ResearchRun.create(
        run_id=_stable_id("run", f"{ticker}.{as_of_date}"),
        issuer_id=issuer_id,
        as_of_date=as_of_date,
        compiler_version=ROOM16_OS_COMPILER_VERSION,
        input_sha256=data_sha256,
        authority_bundle_sha256=manifest_sha256,
        pass_receipts=pass_receipts,
        status="blocked" if ordered_blockers else "verified",
        release_verdict="blocked" if ordered_blockers else "verified",
        created_at=str(manifest.get("generated_at") or ""),
    )
    dossier = DossierVersion.create(
        dossier_id=dossier_id,
        version=1,
        issuer_id=issuer_id,
        as_of_date=as_of_date,
        source_snapshot_sha256s=tuple(sorted(item.snapshot_sha256 for item in sources)),
        research_run_sha256=research_run.run_sha256,
        evidence_graph_sha256=evidence_graph.evidence_graph_sha256,
        compiler_version=ROOM16_OS_COMPILER_VERSION,
        quality_verdict="blocked" if ordered_blockers else "verified",
        quality_blocker_codes=ordered_blockers,
        public_evidence_status="blocked",
        bundle_sha256=manifest_sha256,
    )
    body = {
        "contract_id": ROOM16_OS_RECEIPT_CONTRACT_ID,
        "contract_version": ROOM16_OS_RECEIPT_CONTRACT_VERSION,
        "compiler_version": ROOM16_OS_COMPILER_VERSION,
        "status": "blocked" if ordered_blockers else "verified_private",
        "authority_manifest_sha256": manifest_sha256,
        "issuer_identity": identity.model_dump(mode="json"),
        "source_snapshots": [item.model_dump(mode="json") for item in sources],
        "evidence_graph": evidence_graph.model_dump(mode="json"),
        "research_run": research_run.model_dump(mode="json"),
        "dossier": dossier.model_dump(mode="json"),
        "public_edition_policy": ROOM16_OS_PUBLIC_EDITION_POLICY,
    }
    receipt = {**body, "receipt_sha256": sha256_json(body)}
    target = Path(output_path).expanduser().resolve() if output_path else root.parent / "room16_os_dossier.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def verify_current_room16_os_receipt(path: str | Path) -> dict[str, Any]:
    """Verify a source-native dossier receipt without touching its sources."""

    receipt_path = Path(path).expanduser().resolve()
    receipt = _read_json(receipt_path)
    failures: list[str] = []
    if set(receipt) != ROOM16_OS_RECEIPT_FIELDS:
        failures.append("receipt_schema")
    if (
        receipt.get("contract_id") != ROOM16_OS_RECEIPT_CONTRACT_ID
        or receipt.get("contract_version") != ROOM16_OS_RECEIPT_CONTRACT_VERSION
    ):
        failures.append("receipt_contract_identity")
    if receipt.get("compiler_version") != ROOM16_OS_COMPILER_VERSION:
        failures.append("receipt_compiler_version")
    status = receipt.get("status")
    if status not in {"verified_private", "blocked"}:
        failures.append("receipt_status")
    if receipt.get("public_edition_policy") != ROOM16_OS_PUBLIC_EDITION_POLICY:
        failures.append("receipt_public_edition_policy")
    authority_manifest_sha256 = receipt.get("authority_manifest_sha256")
    if not isinstance(authority_manifest_sha256, str) or not re.fullmatch(
        r"[a-f0-9]{64}", authority_manifest_sha256
    ):
        failures.append("receipt_authority_manifest_sha256")
    expected_hash = sha256_json({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    if receipt.get("receipt_sha256") != expected_hash:
        failures.append("receipt_hash")
    try:
        identity = IssuerIdentity.model_validate(receipt.get("issuer_identity"))
        sources = tuple(SourceSnapshot.model_validate(item) for item in receipt.get("source_snapshots") or [])
        evidence = EvidenceGraph.model_validate(receipt.get("evidence_graph"))
        run = ResearchRun.model_validate(receipt.get("research_run"))
        dossier = DossierVersion.model_validate(receipt.get("dossier"))
        if identity.issuer_id != dossier.issuer_id or run.issuer_id != dossier.issuer_id:
            failures.append("receipt_identity_binding")
        source_ids = {item.snapshot_id for item in sources}
        if identity.identity_source_snapshot_id not in source_ids:
            failures.append("receipt_identity_source_binding")
        if tuple(sorted(item.snapshot_sha256 for item in sources)) != dossier.source_snapshot_sha256s:
            failures.append("receipt_source_binding")
        if any(
            fact.source_snapshot_id not in source_ids
            for fact in evidence.facts
            if fact.source_snapshot_id is not None
        ):
            failures.append("receipt_fact_source_binding")
        if evidence.evidence_graph_sha256 != dossier.evidence_graph_sha256:
            failures.append("receipt_evidence_binding")
        if run.run_sha256 != dossier.research_run_sha256:
            failures.append("receipt_run_binding")
        if (
            authority_manifest_sha256 != run.authority_bundle_sha256
            or authority_manifest_sha256 != dossier.bundle_sha256
        ):
            failures.append("receipt_authority_binding")
        if run.compiler_version != receipt.get("compiler_version") or dossier.compiler_version != receipt.get("compiler_version"):
            failures.append("receipt_compiler_binding")
        if status == "verified_private":
            if (
                dossier.quality_verdict != "verified"
                or run.status != "verified"
                or run.release_verdict != "verified"
                or evidence.status != "verified"
                or any(item.private_research_rights != "allowed" for item in sources)
            ):
                failures.append("receipt_verified_status")
        if status == "blocked" and (
            dossier.quality_verdict != "blocked"
            or run.status not in {"blocked", "failed"}
            or run.release_verdict != "blocked"
            or evidence.status != "blocked"
        ):
            failures.append("receipt_blocked_status")
    except Exception:
        failures.append("receipt_contract_payload")
    return {
        "status": "pass" if not failures else "fail",
        "verified": not failures,
        "blocking_failures": failures,
        "receipt": receipt,
    }
