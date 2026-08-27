"""Read-only, hash-bound extraction from frozen Alpha evidence ZIPs."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256 = r"^[0-9a-f]{64}$"


class FrozenEvidenceFact(StrictModel):
    fact_id: str
    concept: str
    metric_hint: str | None = None
    numeric_value: str
    unit: str
    period_start: str | None = None
    period_end: str
    filed_date: str
    form: str
    source_entry: str
    source_entry_sha256: str = Field(pattern=SHA256)
    evidence_id: str


class FrozenEvidenceInventory(StrictModel):
    contract_id: str = "room16.rfc0011.frozen_evidence_inventory"
    contract_version: int = 1
    ticker: str
    as_of_date: str
    source_zip_name: str
    source_zip_sha256: str = Field(pattern=SHA256)
    source_manifest_sha256: str = Field(pattern=SHA256)
    authority_binding_sha256: str = Field(pattern=SHA256)
    inspected_entry_sha256s: dict[str, str]
    facts: tuple[FrozenEvidenceFact, ...]
    inventory_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "FrozenEvidenceInventory":
        ordered_facts = tuple(
            sorted(
                values.pop("facts"),
                key=lambda item: (item.fact_id, item.period_end, item.evidence_id),
            )
        )
        ordered_entries = dict(sorted(values.pop("inspected_entry_sha256s").items()))
        body = {
            "contract_id": "room16.rfc0011.frozen_evidence_inventory",
            "contract_version": 1,
            **values,
            "inspected_entry_sha256s": ordered_entries,
            "facts": [item.model_dump(mode="json") for item in ordered_facts],
        }
        return cls(**body, inventory_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_hash(self) -> "FrozenEvidenceInventory":
        body = self.model_dump(mode="json", exclude={"inventory_sha256"})
        if sha256_json(body) != self.inventory_sha256:
            raise ValueError("frozen evidence inventory hash mismatch")
        return self


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _authority_binding(values: list[dict[str, Any]], fallback: str) -> str:
    keys = (
        "source_snapshot_sha256",
        "snapshot_sha256",
        "ba3_source_snapshot_sha256_or_null",
        "bundle_sha256",
    )
    for value in values:
        for record in _walk(value):
            for key in keys:
                candidate = record.get(key)
                if isinstance(candidate, str) and len(candidate) == 64:
                    return candidate
    return fallback


def _bound_bundle_payloads(
    artifact_root: Path,
    *,
    package_values: list[dict[str, Any]],
) -> tuple[list[tuple[str, bytes]], str]:
    manifest_path = artifact_root / "BUNDLE_MANIFEST.json"
    typed_facts_path = artifact_root / "artifacts/typed_facts.json"
    if not manifest_path.is_file() or not typed_facts_path.is_file():
        raise ValueError("FROZEN_EVIDENCE_BOUND_BUNDLE_MISSING")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    bundle_sha = manifest.get("bundle_sha256")
    expected_bundle_sha = sha256_json(
        {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    )
    if bundle_sha != expected_bundle_sha:
        raise ValueError("FROZEN_EVIDENCE_BOUND_BUNDLE_HASH_INVALID")
    if not any(bundle_sha in json.dumps(value, sort_keys=True) for value in package_values):
        raise ValueError("FROZEN_EVIDENCE_BOUND_BUNDLE_NOT_IN_AUTHORITY")
    artifact = next(
        (
            item
            for item in manifest.get("artifacts", [])
            if item.get("relative_path") == "artifacts/typed_facts.json"
        ),
        None,
    )
    typed_bytes = typed_facts_path.read_bytes()
    if artifact is None or artifact.get("sha256") != _sha(typed_bytes):
        raise ValueError("FROZEN_EVIDENCE_BOUND_TYPED_FACTS_DRIFT")
    payloads = [
        ("bound_bundle/BUNDLE_MANIFEST.json", manifest_bytes),
        ("bound_bundle/artifacts/typed_facts.json", typed_bytes),
    ]
    provenance_path = artifact_root / "artifacts/source_provenance.json"
    if provenance_path.is_file():
        payloads.append(
            ("bound_bundle/artifacts/source_provenance.json", provenance_path.read_bytes())
        )
    authority = str(
        manifest.get("compile_identity", {}).get("source_snapshot_sha256") or bundle_sha
    )
    return payloads, authority


def load_frozen_evidence(
    zip_path: Path,
    *,
    ticker: str,
    as_of_date: str,
    artifact_root: Path | None = None,
) -> FrozenEvidenceInventory:
    """Extract actual fact-like records without network access or synthetic gaps."""

    payload = zip_path.read_bytes()
    outer_sha = _sha(payload)
    inspected: dict[str, str] = {}
    parsed_values: list[dict[str, Any]] = []
    facts: dict[tuple[str, str, str, str], FrozenEvidenceFact] = {}
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"FROZEN_EVIDENCE_ZIP_INVALID:{bad}")
        manifest_name = next(
            (
                name
                for name in archive.namelist()
                if name.endswith("MANIFEST.json")
                and ("/" not in name.rstrip("/") or name.count("/") <= 1)
            ),
            None,
        )
        if manifest_name is None:
            raise ValueError("FROZEN_EVIDENCE_MANIFEST_MISSING")
        manifest_bytes = archive.read(manifest_name)
        manifest_sha = _sha(manifest_bytes)
        manifest = json.loads(manifest_bytes)
        for item in manifest.get("files", []):
            if isinstance(item, dict) and item.get("path") in archive.namelist():
                if _sha(archive.read(item["path"])) != item.get("sha256"):
                    raise ValueError(f"FROZEN_EVIDENCE_MANIFEST_DRIFT:{item['path']}")
        archive_payloads: list[tuple[str, bytes]] = []
        for name in archive.namelist():
            if not name.endswith(".json") or name.startswith("independent_verifier/"):
                continue
            raw = archive.read(name)
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(value, dict):
                continue
            inspected[name] = _sha(raw)
            parsed_values.append(value)
            archive_payloads.append((name, raw))
        if artifact_root is not None:
            fact_payloads, authority = _bound_bundle_payloads(
                artifact_root,
                package_values=parsed_values,
            )
        else:
            typed_names = [
                name for name, _ in archive_payloads if name.endswith("/artifacts/typed_facts.json")
            ]
            ticker_names = [
                name for name in typed_names if f"/{ticker.upper()}/" in f"/{name.upper()}"
            ]
            if ticker_names:
                selected = sorted(ticker_names, key=lambda name: ("REPLAY" in name.upper(), name))[
                    0
                ]
                fact_payloads = [(name, raw) for name, raw in archive_payloads if name == selected]
            elif len(typed_names) == 1:
                fact_payloads = [
                    (name, raw) for name, raw in archive_payloads if name == typed_names[0]
                ]
            else:
                fact_payloads = [
                    (name, raw)
                    for name, raw in archive_payloads
                    if ticker.upper() in name.upper()
                    and ("OBSERVATION_REPORT" in name.upper() or "METRIC_LINEAGE" in name.upper())
                ]
                if not fact_payloads:
                    fact_payloads = [
                        (name, raw)
                        for name, raw in archive_payloads
                        if any(
                            "fact_id" in record
                            and "value" in record
                            and "period_end" in record
                            and "concept" in record
                            for record in _walk(json.loads(raw))
                        )
                    ]
            authority = _authority_binding(parsed_values, outer_sha)
            if len(fact_payloads) == 1 and fact_payloads[0][0].endswith(
                "/artifacts/typed_facts.json"
            ):
                selected_name, selected_bytes = fact_payloads[0]
                bundle_manifest_name = (
                    selected_name.rsplit("/artifacts/", 1)[0] + "/BUNDLE_MANIFEST.json"
                )
                bundle_manifest_raw = next(
                    (raw for name, raw in archive_payloads if name == bundle_manifest_name),
                    None,
                )
                if bundle_manifest_raw is None:
                    raise ValueError("FROZEN_EVIDENCE_BUNDLE_MANIFEST_MISSING")
                bundle_manifest = json.loads(bundle_manifest_raw)
                artifact = next(
                    (
                        item
                        for item in bundle_manifest.get("artifacts", [])
                        if item.get("relative_path") == "artifacts/typed_facts.json"
                    ),
                    None,
                )
                if artifact is None or artifact.get("sha256") != _sha(selected_bytes):
                    raise ValueError("FROZEN_EVIDENCE_TYPED_FACTS_DRIFT")
                authority = str(
                    bundle_manifest.get("compile_identity", {}).get("source_snapshot_sha256")
                    or bundle_manifest.get("bundle_sha256")
                    or authority
                )
            selected_names = {item[0] for item in fact_payloads}
            fact_payloads.extend(
                (name, raw)
                for name, raw in archive_payloads
                if ticker.upper() in name.upper()
                and any(
                    marker in name.upper()
                    for marker in (
                        "METRIC_SOURCE_CLASSIFICATION",
                        "METRIC_LINEAGE",
                        "OBSERVATION_REPORT",
                    )
                )
                and name not in selected_names
            )
        for name, raw in fact_payloads:
            value = json.loads(raw)
            inspected[name] = _sha(raw)
            for record in _walk(value):
                numeric = record.get("value", record.get("observed_value"))
                concept = (
                    record.get("concept") or record.get("exact_concept") or record.get("metric")
                )
                if numeric is None or "period_end" not in record:
                    continue
                if not isinstance(concept, str) or not concept:
                    continue
                fact_id = str(
                    record.get("fact_id")
                    or f"classified.{sha256_json({'entry': name, 'record': record})}"
                )
                period_end = str(record["period_end"])
                period_start = record.get("period_start") or record.get("start")
                numeric_value = str(numeric)
                key = (fact_id, str(period_start or ""), period_end, numeric_value)
                source_sha = inspected[name]
                evidence_id = (
                    f"frozen.{sha256_json({'zip': outer_sha, 'entry': name, 'fact': key})}"
                )
                candidate = FrozenEvidenceFact(
                    fact_id=fact_id,
                    concept=concept,
                    metric_hint=str(
                        record.get("semantic_metric_id")
                        or record.get("metric")
                        or record.get("metric_id")
                        or ""
                    )
                    or None,
                    numeric_value=numeric_value,
                    unit=str(record.get("unit") or record.get("units") or "unknown"),
                    period_start=str(period_start) if period_start else None,
                    period_end=period_end,
                    filed_date=str(
                        record.get("filed_date")
                        or record.get("filing_date")
                        or record.get("filed")
                        or as_of_date
                    ),
                    form=str(record.get("form") or record.get("filing_form") or "10-Q"),
                    source_entry=name,
                    source_entry_sha256=source_sha,
                    evidence_id=evidence_id,
                )
                prior = facts.get(key)
                if prior is None or (
                    candidate.period_start is not None and prior.period_start is None
                ):
                    facts[key] = candidate
    return FrozenEvidenceInventory.create(
        ticker=ticker,
        as_of_date=as_of_date,
        source_zip_name=zip_path.name,
        source_zip_sha256=outer_sha,
        source_manifest_sha256=manifest_sha,
        authority_binding_sha256=authority,
        inspected_entry_sha256s=inspected,
        facts=tuple(facts.values()),
    )
