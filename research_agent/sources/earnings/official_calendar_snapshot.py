"""Validate and resolve point-in-time official issuer calendar snapshots."""

from __future__ import annotations

import json
import hashlib
import mimetypes
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


CONTRACT_ID = "room16.official_calendar_snapshot"
CONTRACT_VERSION = 2
DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "config" / "official_calendar_snapshots"
OFFICIAL_SOURCE_TYPES = {
    "company_ir",
    "official_press_release",
    "exchange_calendar",
    "exchange_notice",
}


def resolve_official_calendar_snapshot(
    ticker: str,
    as_of_date: str,
    *,
    root: str | Path = DEFAULT_ROOT,
) -> Path | None:
    symbol = ticker.strip().upper()
    target = Path(root) / f"{symbol}_{as_of_date}.json"
    if not target.is_file():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    verification = verify_official_calendar_snapshot(
        payload,
        ticker=symbol,
        as_of_date=as_of_date,
        snapshot_root=target.parent,
        allow_capture_template=True,
    )
    return target if verification["verified"] else None


def verify_official_calendar_snapshot(
    payload: Mapping[str, Any],
    *,
    ticker: str,
    as_of_date: str,
    snapshot_root: str | Path | None = None,
    allow_capture_template: bool = False,
) -> dict[str, Any]:
    failures: list[str] = []
    symbol = ticker.strip().upper()
    if (
        payload.get("contract_id") != CONTRACT_ID
        or payload.get("contract_version") != CONTRACT_VERSION
    ):
        failures.append("calendar_contract_identity")
    if (
        str(payload.get("ticker") or "").upper() != symbol
        or str(payload.get("as_of_date") or "") != as_of_date
    ):
        failures.append("calendar_identity")
    checked_at = str(payload.get("checked_at") or "")
    try:
        checked_date = datetime.fromisoformat(checked_at.replace("Z", "+00:00")).date()
        if checked_date != date.fromisoformat(as_of_date):
            failures.append("calendar_point_in_time_capture")
    except ValueError:
        failures.append("calendar_checked_at")
    sources = payload.get("sources_checked")
    sources = sources if isinstance(sources, list) else []
    if not sources:
        failures.append("calendar_sources_checked")
    origin_capture_verified = True
    proxy_transports: list[str] = []
    for source in sources:
        url = str(source.get("url") or "") if isinstance(source, Mapping) else ""
        parsed = urlsplit(url)
        facts = source.get("observed_facts") if isinstance(source, Mapping) else None
        transport = str(source.get("capture_transport") or "") if isinstance(source, Mapping) else ""
        if "proxy" in transport.casefold():
            origin_capture_verified = False
            proxy_transports.append(transport)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not isinstance(facts, list)
            or not facts
            or any(not str(item).strip() for item in facts)
        ):
            failures.append("calendar_source_snapshot")
            break
        artifact = source.get("snapshot_artifact") if isinstance(source, Mapping) else None
        if not isinstance(artifact, Mapping):
            capture_url = str(source.get("capture_url") or "")
            capture_target = urlsplit(capture_url)
            if (
                allow_capture_template
                and capture_target.scheme == "https"
                and bool(capture_target.hostname)
                and bool(str(source.get("capture_transport") or ""))
            ):
                continue
            failures.append("calendar_physical_snapshot_metadata")
            break
        relative = str(artifact.get("path") or "")
        artifact_retrieved_at = str(artifact.get("retrieved_at") or "")
        if (
            not relative
            or relative.startswith("/")
            or ".." in Path(relative).parts
            or not str(artifact.get("sha256") or "")
            or not isinstance(artifact.get("bytes"), int)
            or artifact.get("bytes", 0) <= 0
            or not str(artifact.get("media_type") or "")
            or not artifact_retrieved_at
            or not str(source.get("capture_transport") or "")
        ):
            failures.append("calendar_physical_snapshot_metadata")
            break
        try:
            if (
                datetime.fromisoformat(
                    artifact_retrieved_at.replace("Z", "+00:00")
                ).date()
                != date.fromisoformat(as_of_date)
            ):
                failures.append("calendar_physical_snapshot_not_point_in_time")
                break
        except ValueError:
            failures.append("calendar_physical_snapshot_metadata")
            break
        if snapshot_root is not None:
            root = Path(snapshot_root).expanduser().resolve()
            path = (root / relative).resolve()
            if (
                root not in path.parents
                or not path.is_file()
                or path.stat().st_size != artifact.get("bytes")
                or _sha256(path.read_bytes()) != artifact.get("sha256")
            ):
                failures.append("calendar_physical_snapshot_integrity")
                break
    events = payload.get("events")
    events = events if isinstance(events, list) else []
    coverage_status = str(payload.get("coverage_status") or "")
    if coverage_status == "complete_no_candidates":
        if events:
            failures.append("calendar_no_candidate_consistency")
    elif coverage_status == "complete":
        if not events:
            failures.append("calendar_events_present")
        for event in events:
            if not isinstance(event, Mapping):
                failures.append("calendar_event_schema")
                continue
            event_url = urlsplit(str(event.get("url") or ""))
            try:
                event_date = date.fromisoformat(str(event.get("report_date") or "")[:10])
            except ValueError:
                failures.append("calendar_event_date")
                continue
            if (
                str(event.get("ticker") or "").upper() != symbol
                or event_date < date.fromisoformat(as_of_date)
                or event.get("confirmed") is not True
                or str(event.get("source_type") or "") not in OFFICIAL_SOURCE_TYPES
                or event_url.scheme != "https"
                or not event_url.hostname
                or not str(event.get("source_id") or "")
                or not str(event.get("retrieved_at") or "")
            ):
                failures.append("calendar_event_authority")
    else:
        failures.append("calendar_coverage_status")
    return {
        "verified": not failures,
        "status": "pass" if not failures else "fail",
        "blocking_failures": sorted(set(failures)),
        "content_snapshot_verified": not failures,
        "origin_capture_verified": bool(not failures and origin_capture_verified),
        "transport_assurance": (
            "origin_capture_verified"
            if not failures and origin_capture_verified
            else "proxy_observation_origin_response_unverified"
            if not failures and proxy_transports
            else "unverified"
        ),
        "proxy_transports": sorted(set(proxy_transports)),
    }


def materialize_official_calendar_snapshot(
    template_path: str | Path,
    *,
    output_root: str | Path,
    user_agent: str,
) -> Path:
    """Capture immutable page bytes and return a self-contained runtime snapshot."""

    template = Path(template_path).expanduser().resolve()
    payload = json.loads(template.read_text(encoding="utf-8"))
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    evidence_root = root / "evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().astimezone().isoformat()
    analysis_date = date.fromisoformat(str(payload.get("as_of_date") or ""))
    for index, source in enumerate(payload.get("sources_checked") or [], start=1):
        artifact = source.get("snapshot_artifact")
        if isinstance(artifact, Mapping):
            relative = str(artifact.get("path") or "")
            source_artifact = (template.parent / relative).resolve()
            if template.parent not in source_artifact.parents or not source_artifact.is_file():
                raise ValueError("configured official calendar snapshot artifact is unavailable")
            content = source_artifact.read_bytes()
            if (
                _sha256(content) != artifact.get("sha256")
                or len(content) != artifact.get("bytes")
            ):
                raise ValueError("configured official calendar snapshot artifact failed integrity")
            media_type = str(artifact.get("media_type") or "application/octet-stream")
            captured_at = str(artifact.get("retrieved_at") or "")
        else:
            capture_url = str(source.get("capture_url") or "")
            if not capture_url:
                raise ValueError(
                    "official calendar template has neither an immutable artifact nor an explicit capture URL"
                )
            if datetime.now().astimezone().date() != analysis_date:
                raise ValueError(
                    "official calendar live capture cannot be reconstructed for a past analysis date"
                )
            request = urllib.request.Request(
                capture_url,
                headers={"User-Agent": user_agent or "Room16 research snapshot"},
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                content = response.read()
                media_type = response.headers.get_content_type() or "application/octet-stream"
            captured_at = checked_at
        if not content:
            raise ValueError("official calendar capture returned no bytes")
        suffix = mimetypes.guess_extension(media_type) or ".bin"
        if media_type in {"text/markdown", "text/plain"}:
            suffix = ".md"
        filename = f"source-{index:02d}{suffix}"
        target = evidence_root / filename
        target.write_bytes(content)
        source["capture_transport"] = str(
            source.get("capture_transport") or "direct_https"
        )
        source["snapshot_artifact"] = {
            "path": f"evidence/{filename}",
            "sha256": _sha256(content),
            "bytes": len(content),
            "media_type": media_type,
            "retrieved_at": captured_at,
        }
    target = root / template.name
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    verification = verify_official_calendar_snapshot(
        payload,
        ticker=str(payload.get("ticker") or ""),
        as_of_date=str(payload.get("as_of_date") or ""),
        snapshot_root=root,
    )
    if not verification["verified"]:
        raise ValueError(
            "official calendar runtime snapshot failed: "
            + ", ".join(verification["blocking_failures"])
        )
    return target


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
