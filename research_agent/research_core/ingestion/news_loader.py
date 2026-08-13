from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Union

from research_agent.evidence.evidence_item import EvidenceItem


def load_news(ticker: str, raw_dir: Union[str, Path] = "research_agent/data/raw") -> list[dict[str, Any]]:
    path = Path(raw_dir) / f"{ticker.upper()}_news.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return _deduplicate_economic_event_facts(payload)
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
    return [coverage, *_deduplicate_economic_event_facts(events)]


def _deduplicate_economic_event_facts(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prefer exact event-date facts over reporting-period restatements."""

    instant_keys = {
        key
        for event in events
        for numeric in (event.get("numeric_evidence") or [])
        if isinstance(numeric, dict)
        and numeric.get("period_kind") == "instant"
        and (key := _economic_event_fact_key(numeric)) is not None
    }
    canonical: list[dict[str, Any]] = []
    for event in events:
        copied = dict(event)
        numeric_evidence = event.get("numeric_evidence") or []
        copied["numeric_evidence"] = [
            numeric
            for numeric in numeric_evidence
            if not (
                isinstance(numeric, dict)
                and numeric.get("period_kind") != "instant"
                and _economic_event_fact_key(numeric) in instant_keys
            )
        ]
        canonical.append(copied)
    return canonical


def _economic_event_fact_key(numeric: dict[str, Any]) -> tuple[Any, ...] | None:
    metric = str(numeric.get("metric_name") or "").casefold()
    concept = next(
        (
            item
            for item in (
                "acquisition_assumed_debt",
                "acquisition_total_consideration",
                "acquisition_net_cash_paid",
            )
            if item in metric
        ),
        None,
    )
    if not concept or numeric.get("value") is None:
        return None
    raw_text = re.sub(
        r"\s+",
        " ",
        str(numeric.get("raw_text") or "").casefold(),
    ).strip()
    if not raw_text:
        return None
    return concept, float(numeric["value"]), raw_text


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
        if numeric_evidence:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"{base_evidence_id}_NARRATIVE",
                    ticker=symbol,
                    claim_type=claim_type,
                    source_id=source_id,
                    source_type=source_type,
                    authority_rank=rank,
                    statement=str(event.get("summary") or headline),
                    date=event_date,
                    url=event.get("url"),
                    retrieved_at=event.get("retrieved_at"),
                    supports_categories=["material_news_coverage", "source_narrative"],
                    source_sign=1,
                    confidence="high" if rank <= 2 else "medium",
                )
            )
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
                    fact_type=numeric.get("fact_type"),
                    raw_text=numeric.get("raw_text"),
                    normalized_magnitude=numeric.get("normalized_magnitude"),
                    signed_value=numeric.get("signed_value"),
                    direction=numeric.get("direction") or "neutral",
                    impact=numeric.get("impact") or "neutral",
                    rate_basis=numeric.get("rate_basis"),
                    unit=numeric.get("unit"),
                    source_scale=numeric.get("source_scale"),
                    source_unit=numeric.get("source_unit"),
                    source_sign=numeric.get("source_sign"),
                    currency=numeric.get("currency"),
                    column_label=numeric.get("column_label"),
                    row_metric=numeric.get("row_metric"),
                    column_metric=numeric.get("column_metric"),
                    segment=numeric.get("segment"),
                    source_cell_status=numeric.get("source_cell_status"),
                    table_id=numeric.get("table_id"),
                    cell_id=numeric.get("cell_id"),
                    row_key=numeric.get("row_key"),
                    column_key=numeric.get("column_key"),
                    source_locator=numeric.get("source_locator"),
                    is_zero=bool(numeric.get("is_zero")),
                    is_not_applicable=bool(numeric.get("is_not_applicable")),
                    is_missing=bool(numeric.get("is_missing")),
                    source_accession_number=event.get("source_accession_number"),
                    source_document=event.get("source_document"),
                    source_document_role=event.get("source_document_role"),
                    source_snapshot_path=event.get("source_snapshot_path"),
                    source_content_sha256=event.get("source_content_sha256"),
                    source_content_bytes=event.get("source_content_bytes"),
                    dimension=numeric.get("dimension"),
                    display_unit=numeric.get("display_unit"),
                    period_kind=numeric.get("period_kind"),
                    presentation_basis=numeric.get("presentation_basis"),
                    period_start=numeric.get("period_start"),
                    period_end=numeric.get("period_end"),
                    current_period_start=numeric.get("current_period_start"),
                    current_period_end=numeric.get("current_period_end"),
                    comparison_period_start=numeric.get("comparison_period_start"),
                    comparison_period_end=numeric.get("comparison_period_end"),
                    effective_asof_dates=numeric.get("effective_asof_dates") or [],
                    date=event_date,
                    url=event.get("url"),
                    retrieved_at=event.get("retrieved_at"),
                    supports_categories=[
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
