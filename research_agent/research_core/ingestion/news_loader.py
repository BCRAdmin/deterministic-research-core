from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from research_agent.evidence.evidence_item import EvidenceItem


def load_news(ticker: str, raw_dir: Union[str, Path] = "research_agent/data/raw") -> list[dict[str, Any]]:
    path = Path(raw_dir) / f"{ticker.upper()}_news.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise ValueError(f"news input must be a list or object: {path}")
    events = payload.get("events") or []
    if not isinstance(events, list):
        raise ValueError(f"news events must be a list: {path}")
    coverage = {
        "event_type": "coverage_manifest",
        "status": payload.get("coverage_status") or "unavailable",
        "checked_at": payload.get("checked_at"),
        "window_start": payload.get("window_start"),
        "window_end": payload.get("window_end"),
        "sources_checked": payload.get("sources_checked") or [],
    }
    return [coverage, *events]


def news_evidence_items(
    ticker: str,
    events: list[dict[str, Any]],
) -> list[EvidenceItem]:
    symbol = ticker.upper()
    evidence: list[EvidenceItem] = []
    for index, event in enumerate(events, start=1):
        if event.get("event_type") == "coverage_manifest":
            continue
        source_id = str(event.get("source_id") or "").strip()
        source_type = str(event.get("source_type") or "").strip()
        event_date = str(event.get("date") or "")[:10]
        headline = str(event.get("headline") or "").strip()
        if not all((source_id, source_type, event_date, headline)):
            raise ValueError(
                "official news events require source_id, source_type, date, and headline"
            )
        rank = int(event.get("authority_rank") or 1)
        event_type = str(event.get("event_type") or "").strip()
        is_guidance = event_type in {"company_outlook", "guidance"}
        is_risk = event_type == "risk"
        claim_type = "news"
        if is_guidance:
            claim_type = "guidance"
        elif is_risk:
            claim_type = "risk"
        base_evidence_id = str(
            event.get("evidence_id")
            or f"{symbol}_NEWS_{event_date}_{index:02d}"
        )
        numeric_evidence = event.get("numeric_evidence")
        numeric_evidence = (
            numeric_evidence if isinstance(numeric_evidence, list) else []
        )
        evidence_records = numeric_evidence or [None]
        for numeric_index, numeric in enumerate(evidence_records, start=1):
            numeric = numeric if isinstance(numeric, dict) else {}
            metric_name = str(numeric.get("metric_name") or "")
            evidence.append(
                EvidenceItem(
                    evidence_id=(
                        f"{base_evidence_id}_KPI_{numeric_index:02d}"
                        if numeric_evidence
                        else base_evidence_id
                    ),
                    ticker=symbol,
                    claim_type=claim_type,
                    source_id=source_id,
                    source_type=source_type,
                    authority_rank=rank,
                    statement=str(event.get("summary") or headline),
                    value=numeric.get("value"),
                    raw_value=numeric.get("raw_value"),
                    normalized_value=numeric.get("value"),
                    unit=numeric.get("unit"),
                    source_scale=numeric.get("source_scale"),
                    source_unit=numeric.get("source_unit"),
                    source_sign=numeric.get("source_sign"),
                    currency=numeric.get("currency"),
                    column_label=numeric.get("column_label"),
                    date=event_date,
                    url=event.get("url"),
                    retrieved_at=event.get("retrieved_at"),
                    supports_claims=[
                        "material_news_coverage",
                        *(
                            ["business_model_operating_kpi"]
                            if event_type == "operating_kpi" and numeric_evidence
                            else []
                        ),
                        *(["company_guidance"] if is_guidance else []),
                        *(["issuer_risk_disclosure"] if is_risk else []),
                    ],
                    supports_metrics=[metric_name] if metric_name else [],
                    confidence="high" if rank <= 2 else "medium",
                )
            )
    return evidence
