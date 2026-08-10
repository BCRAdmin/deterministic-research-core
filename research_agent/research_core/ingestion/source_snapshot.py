"""Build and verify immutable source snapshots for Room16 authority bundles.

The source registry explains *which* authorities support the analysis.  This
module adds the missing physical evidence contract: every external registry
entry must resolve to at least one hashed local artifact.  Deterministic
calculation entries are explicitly dispositioned but never masquerade as an
external source.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    load_source_registry,
)


SOURCE_SNAPSHOT_CONTRACT_ID = "room16.source_snapshot_manifest"
SOURCE_SNAPSHOT_CONTRACT_VERSION = 2
SNAPSHOT_PARSER_VERSION = "room16.source_snapshot_parser@2"
DEFAULT_CODE_VERSION = "research_agent_v0.1.0"
DERIVED_SOURCE_TYPES = {"deterministic_calculation"}
TEXT_SUFFIXES = {".csv", ".htm", ".html", ".json", ".md", ".txt", ".xml"}


class SourceSnapshotError(ValueError):
    """Raised when the physical source evidence cannot satisfy the contract."""


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_accessions(value: str) -> set[str]:
    return {
        match.replace("-", "")
        for match in re.findall(r"\b\d{10}-?\d{2}-?\d{6}\b", value)
    }


def _read_searchable(path: Path) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _first_metadata_value(payload: Any, keys: set[str]) -> str | None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in keys:
                if isinstance(value, list):
                    value = next(
                        (item for item in value if item is not None and item != ""),
                        None,
                    )
                if value is not None and value != "":
                    return str(value)
        for value in payload.values():
            found = _first_metadata_value(value, keys)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _first_metadata_value(value, keys)
            if found:
                return found
    return None


def _source_time_metadata(paths: list[Path]) -> dict[str, str | None]:
    published_keys = {
        "publishedat",
        "publisheddate",
        "publicationdate",
        "datepublished",
        "filingdate",
    }
    accepted_keys = {
        "acceptedat",
        "acceptancedatetime",
        "acceptancedate",
    }
    published_at: str | None = None
    accepted_at: str | None = None
    for path in paths:
        if path.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        published_at = published_at or _first_metadata_value(payload, published_keys)
        accepted_at = accepted_at or _first_metadata_value(payload, accepted_keys)
        if published_at and accepted_at:
            break
    return {"published_at": published_at, "accepted_at": accepted_at}


def _time_record(
    value: str | None,
    *,
    available_status: str,
    unavailable_status: str = "unavailable_in_source",
) -> dict[str, str | None]:
    return {
        "value": value,
        "status": available_status if value else unavailable_status,
    }


def _artifact_matches_source(
    *,
    path: Path,
    text: str,
    source: Any,
    ticker: str,
) -> bool:
    source_id = str(source.source_id or "")
    url = str(source.url or "")
    if source_id and source_id in text:
        return True
    if url and url in text:
        return True
    accessions = _normalized_accessions(f"{source_id} {url}")
    if accessions:
        compact_text = text.replace("-", "")
        if any(accession in compact_text for accession in accessions):
            return True
    if source.source_type in {"exchange_ohlcv", "trusted_market_data_vendor"}:
        return path.suffix.lower() == ".csv" and path.stem.upper() == ticker
    return False


def build_source_snapshot_manifest(
    *,
    source_root: str | Path,
    source_registry: SourceRegistry | str | Path,
    ticker: str,
    as_of_date: str,
    retrieved_at: str | None = None,
    parser_version: str = SNAPSHOT_PARSER_VERSION,
    code_version: str = DEFAULT_CODE_VERSION,
) -> dict[str, Any]:
    """Hash the source tree and bind every registry source to physical bytes."""

    root = Path(source_root).expanduser().resolve()
    if not root.is_dir():
        raise SourceSnapshotError(f"source artifact root is missing: {root}")
    registry = (
        load_source_registry(source_registry)
        if isinstance(source_registry, (str, Path))
        else source_registry
    )
    symbol = ticker.strip().upper()
    timestamp = retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise SourceSnapshotError(f"source artifact root is empty: {root}")

    artifacts: list[dict[str, Any]] = []
    searchable: dict[str, str] = {}
    for path in files:
        relative = path.relative_to(root).as_posix()
        digest = file_sha256(path)
        identity_digest = hashlib.sha256(
            f"{relative}\0{digest}".encode("utf-8")
        ).hexdigest()
        searchable[relative] = _read_searchable(path)
        artifacts.append(
            {
                "snapshot_id": f"snapshot_{identity_digest[:20]}",
                "path": relative,
                "sha256": digest,
                "bytes": path.stat().st_size,
                "media_type": mimetypes.guess_type(path.name)[0]
                or "application/octet-stream",
                "captured_at": timestamp,
                "parser_version": parser_version,
                "code_version": code_version,
            }
        )

    artifact_by_path = {item["path"]: item for item in artifacts}
    dispositions: list[dict[str, Any]] = []
    for source in registry.sources:
        if source.ticker.strip().upper() != symbol:
            disposition = "identity_mismatch"
            matched_paths: list[str] = []
            reason = f"registry ticker {source.ticker!r} does not match {symbol}"
        elif source.source_type in DERIVED_SOURCE_TYPES:
            disposition = "derived_calculation"
            matched_paths = []
            reason = "deterministic result derived from separately snapshotted inputs"
        else:
            matched_paths = [
                relative
                for relative, text in searchable.items()
                if _artifact_matches_source(
                    path=root / relative,
                    text=text,
                    source=source,
                    ticker=symbol,
                )
            ]
            if matched_paths:
                disposition = "material_evidence"
                reason = "registry authority is bound to immutable local source bytes"
            else:
                disposition = "undispositioned"
                reason = "no local source artifact could be bound to this registry entry"
        source_times = _source_time_metadata(
            [root / path for path in matched_paths]
        )
        source_retrieved_at = str(source.retrieved_at or timestamp)
        if source.source_type in DERIVED_SOURCE_TYPES:
            published_record = _time_record(
                None,
                available_status="not_applicable",
                unavailable_status="not_applicable",
            )
            accepted_record = dict(published_record)
        else:
            published_record = _time_record(
                source_times["published_at"],
                available_status="extracted_from_snapshot",
            )
            accepted_record = _time_record(
                source_times["accepted_at"],
                available_status="extracted_from_snapshot",
            )
        dispositions.append(
            {
                "source_id": source.source_id,
                "source_type": source.source_type,
                "url": source.url,
                "disposition": disposition,
                "reason": reason,
                "snapshot_ids": [
                    artifact_by_path[path]["snapshot_id"] for path in matched_paths
                ],
                "retrieved_at": _time_record(
                    source_retrieved_at,
                    available_status=(
                        "source_registry"
                        if source.retrieved_at
                        else "snapshot_capture_fallback"
                    ),
                ),
                "published_at": published_record,
                "accepted_at": accepted_record,
                "parser_version": parser_version,
                "code_version": code_version,
            }
        )

    blocking = [
        item["source_id"]
        for item in dispositions
        if item["disposition"] in {"identity_mismatch", "undispositioned"}
    ]
    return {
        "contract_id": SOURCE_SNAPSHOT_CONTRACT_ID,
        "contract_version": SOURCE_SNAPSHOT_CONTRACT_VERSION,
        "ticker": symbol,
        "as_of_date": as_of_date,
        "generated_at": timestamp,
        "parser_version": parser_version,
        "code_version": code_version,
        "source_root": str(root),
        "all_sources_dispositioned": not blocking,
        "blocking_source_ids": blocking,
        "artifacts": artifacts,
        "source_dispositions": dispositions,
    }


def save_source_snapshot_manifest(
    manifest: Mapping[str, Any], path: str | Path
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(dict(manifest), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def verify_source_snapshot_manifest(
    manifest: Mapping[str, Any],
    *,
    source_root: str | Path,
) -> dict[str, Any]:
    """Verify contract identity, artifact hashes, and disposition completeness."""

    root = Path(source_root).expanduser().resolve()
    failures: list[str] = []
    if (
        manifest.get("contract_id") != SOURCE_SNAPSHOT_CONTRACT_ID
        or manifest.get("contract_version") != SOURCE_SNAPSHOT_CONTRACT_VERSION
    ):
        failures.append("contract_identity")

    artifact_ids: set[str] = set()
    generated_at = str(manifest.get("generated_at") or "")
    parser_version = str(manifest.get("parser_version") or "")
    code_version = str(manifest.get("code_version") or "")
    if not generated_at or not parser_version or not code_version:
        failures.append("source_capture_provenance")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        failures.append("source_artifacts_present")
        artifacts = []
    for item in artifacts:
        if not isinstance(item, Mapping):
            failures.append("source_artifact_schema")
            continue
        snapshot_id = str(item.get("snapshot_id") or "")
        relative = str(item.get("path") or "")
        path = (root / relative).resolve()
        if not snapshot_id or snapshot_id in artifact_ids:
            failures.append("source_snapshot_identity")
        artifact_ids.add(snapshot_id)
        if (
            str(item.get("captured_at") or "") != generated_at
            or str(item.get("parser_version") or "") != parser_version
            or str(item.get("code_version") or "") != code_version
        ):
            failures.append(f"source_artifact_provenance:{relative}")
        if root not in path.parents or not path.is_file():
            failures.append(f"source_artifact_missing:{relative}")
            continue
        if file_sha256(path) != str(item.get("sha256") or ""):
            failures.append(f"source_artifact_hash:{relative}")
        if path.stat().st_size != item.get("bytes"):
            failures.append(f"source_artifact_size:{relative}")

    dispositions = manifest.get("source_dispositions")
    if not isinstance(dispositions, list) or not dispositions:
        failures.append("source_dispositions_present")
        dispositions = []
    derived = 0
    disposition_ids: set[str] = set()
    for item in dispositions:
        if not isinstance(item, Mapping):
            failures.append("source_disposition_schema")
            continue
        disposition = str(item.get("disposition") or "")
        source_id = str(item.get("source_id") or "")
        if not source_id or source_id in disposition_ids:
            failures.append("source_disposition_identity")
        disposition_ids.add(source_id)
        if (
            str(item.get("parser_version") or "") != parser_version
            or str(item.get("code_version") or "") != code_version
        ):
            failures.append(f"source_disposition_provenance:{source_id}")
        for field in ("retrieved_at", "published_at", "accepted_at"):
            record = item.get(field)
            if not isinstance(record, Mapping):
                failures.append(f"source_time_metadata:{source_id}:{field}")
                continue
            value = record.get("value")
            status = str(record.get("status") or "")
            value_missing = value is None or value == ""
            if not status or (
                status in {"unavailable_in_source", "not_applicable"}
            ) != value_missing:
                failures.append(f"source_time_metadata:{source_id}:{field}")
        linked = item.get("snapshot_ids")
        linked = linked if isinstance(linked, list) else []
        if disposition == "derived_calculation":
            derived += 1
            continue
        if disposition != "material_evidence":
            failures.append(f"source_undispositioned:{item.get('source_id')}")
        elif not linked or any(str(value) not in artifact_ids for value in linked):
            failures.append(f"source_snapshot_unbound:{item.get('source_id')}")

    if bool(manifest.get("all_sources_dispositioned")) is bool(failures):
        failures.append("source_disposition_gate_consistency")
    return {
        "status": "pass" if not failures else "fail",
        "verified": not failures,
        "blocking_failures": sorted(set(failures)),
        "artifact_count": len(artifacts),
        "source_count": len(dispositions),
        "derived_source_count": derived,
    }
