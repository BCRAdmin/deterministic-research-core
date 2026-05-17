from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Iterable, Optional

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.sources.earnings.earnings_event import EarningsEvent


def load_earnings_events(path: str | Path) -> list[EarningsEvent]:
    target = Path(path)
    if not target.exists():
        return []
    if target.suffix.lower() == ".json":
        payload = json.loads(target.read_text(encoding="utf-8"))
        rows = payload.get("events", payload) if isinstance(payload, dict) else payload
        return [EarningsEvent(**_normalize_event_row(row)) for row in rows]
    if target.suffix.lower() == ".csv":
        rows = csv.DictReader(target.read_text(encoding="utf-8").splitlines())
        return [EarningsEvent(**_normalize_event_row(row)) for row in rows]
    raise ValueError(f"Unsupported earnings calendar format: {target.suffix}")


def next_earnings_event(ticker: str, events: Iterable[EarningsEvent], as_of_date: str) -> Optional[EarningsEvent]:
    basis = date.fromisoformat(as_of_date[:10])
    future = [
        event for event in events
        if event.ticker.upper() == ticker.upper() and date.fromisoformat(event.report_date[:10]) >= basis
    ]
    if not future:
        return None
    return sorted(future, key=lambda event: event.report_date)[0]


def is_event_risk_window(event: Optional[EarningsEvent], as_of_date: str, max_trading_days: int = 10) -> bool:
    if event is None or not event.confirmed:
        return False
    basis = date.fromisoformat(as_of_date[:10])
    event_date = date.fromisoformat(event.report_date[:10])
    return 0 <= (event_date - basis).days <= max_trading_days


def earnings_event_to_evidence(event: EarningsEvent) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"{event.ticker.upper()}_{event.source_id}_EARNINGS_{event.report_date}",
        ticker=event.ticker.upper(),
        claim_type="event",
        source_id=event.source_id,
        source_type=event.source_type,
        authority_rank=rank_source(event.source_type),
        statement=f"{event.ticker.upper()} confirmed earnings date is {event.report_date}.",
        date=event.report_date,
        period=event.fiscal_period,
        url=event.url,
        retrieved_at=event.retrieved_at,
        supports_metrics=["next_earnings_date", "earnings_event"],
        confidence="high" if event.confirmed else "low",
    )


def _normalize_event_row(row: dict) -> dict:
    normalized = dict(row)
    if "date" in normalized and "report_date" not in normalized:
        normalized["report_date"] = normalized.pop("date")
    if "source" in normalized and "source_id" not in normalized:
        normalized["source_id"] = normalized.pop("source")
    normalized["ticker"] = str(normalized["ticker"]).upper()
    normalized["report_date"] = str(normalized["report_date"])[:10]
    normalized["confirmed"] = _as_bool(normalized.get("confirmed"))
    normalized.setdefault("source_id", "earnings_calendar")
    normalized.setdefault("source_type", "earnings_calendar")
    return normalized


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "confirmed"}
