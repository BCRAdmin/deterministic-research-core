"""Validate and resolve point-in-time official issuer calendar snapshots."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit


CONTRACT_ID = "room16.official_calendar_snapshot"
CONTRACT_VERSION = 1
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
    )
    return target if verification["verified"] else None


def verify_official_calendar_snapshot(
    payload: Mapping[str, Any],
    *,
    ticker: str,
    as_of_date: str,
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
    for source in sources:
        url = str(source.get("url") or "") if isinstance(source, Mapping) else ""
        parsed = urlsplit(url)
        facts = source.get("observed_facts") if isinstance(source, Mapping) else None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not isinstance(facts, list)
            or not facts
            or any(not str(item).strip() for item in facts)
        ):
            failures.append("calendar_source_snapshot")
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
    }
