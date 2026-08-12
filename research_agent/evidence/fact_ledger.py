"""Build the canonical, reviewable fact ledger from structured research claims."""

from __future__ import annotations

import json
import math
import re
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket


FACT_LEDGER_CONTRACT_ID = "room16-canonical-fact-ledger"
FACT_LEDGER_CONTRACT_VERSION = 4


class FactLedgerError(ValueError):
    """Raised when a report fact cannot be tied to an exact evidence value."""


def build_fact_ledger(
    *,
    data_packet: DataPacket,
    claims: Iterable[ResearchClaim],
    evidence_ledger: EvidenceLedger,
    source_registry: SourceRegistry,
) -> dict[str, Any]:
    """Create one exact, source-bound fact per metric used by the report.

    The function never parses prose and never chooses a replacement value. The
    raw value captured when a claim was composed must match an evidence-ledger
    item that explicitly supports the same metric.
    """

    metric_uses: dict[str, dict[str, Any]] = {}
    for claim in claims:
        for metric_name, raw_value in claim.metric_values.items():
            value = float(raw_value)
            existing = metric_uses.get(metric_name)
            if existing and not _same_number(existing["value"], value):
                raise FactLedgerError(
                    f"conflicting claim values for {metric_name}: "
                    f"{existing['value']} != {value}"
                )
            item = metric_uses.setdefault(
                metric_name,
                {
                    "value": value,
                    "research_claim_ids": [],
                    "claim_evidence_ids": [],
                },
            )
            if claim.claim_id and claim.claim_id not in item["research_claim_ids"]:
                item["research_claim_ids"].append(claim.claim_id)
            item["claim_evidence_ids"] = list(
                dict.fromkeys(
                    [*item["claim_evidence_ids"], *claim.evidence_ids]
                )
            )

    if len(metric_uses) < 5:
        raise FactLedgerError(
            f"fact ledger needs at least 5 exact metrics; found {len(metric_uses)}"
        )

    registry_by_id = {
        source.source_id: source
        for source in source_registry.sources
    }
    facts: list[dict[str, Any]] = []
    used_source_ids: list[str] = []
    for metric_name in sorted(metric_uses):
        metric_use = metric_uses[metric_name]
        evidence = _select_exact_evidence(
            evidence_ledger=evidence_ledger,
            metric_name=metric_name,
            value=metric_use["value"],
            as_of_date=data_packet.as_of_date,
            allowed_evidence_ids=set(metric_use["claim_evidence_ids"]),
        )
        source_ids = _resolve_registered_source_ids(
            [evidence.source_id, *evidence.source_lineage],
            registry_by_id,
        )
        if evidence.source_id not in source_ids:
            raise FactLedgerError(
                f"evidence source {evidence.source_id} for {metric_name} "
                "is not registered"
            )
        used_source_ids.extend(source_ids)
        period_metadata = _period_metadata(metric_name, evidence)
        dimension, display_unit, currency = _typed_unit(evidence)
        presentation_basis = _presentation_basis(
            metric_name,
            evidence,
            period_kind=str(period_metadata["period_kind"]),
        )
        fact = {
            "claim_id": f"{data_packet.ticker.upper()}_FACT_{metric_name.upper()}",
            "label": metric_name.replace("_", " "),
            "metric": metric_name,
            "value": metric_use["value"],
            "unit": display_unit,
            "display_unit": display_unit,
            "dimension": dimension,
            "currency": currency,
            "period_type": _period_type(metric_name, evidence),
            **period_metadata,
            "fiscal_label": evidence.period,
            "presentation_basis": presentation_basis,
            "asof": (
                max(evidence.effective_asof_dates)
                if evidence.effective_asof_dates
                else evidence.date or data_packet.as_of_date
            ),
            "effective_asof_dates": list(evidence.effective_asof_dates),
            "source_id": evidence.source_id,
            "source_ids": source_ids,
            "evidence_ids": [evidence.evidence_id],
            "claim_bound_evidence_ids": sorted(metric_use["claim_evidence_ids"]),
            "source_value": evidence.raw_value,
            "source_scale": evidence.source_scale,
            "source_sign": evidence.source_sign,
            "row_metric": evidence.row_metric,
            "column_metric": evidence.column_metric,
            "segment": evidence.segment,
            "source_cell_status": evidence.source_cell_status,
            "source_accession_number": evidence.source_accession_number,
            "source_document": evidence.source_document,
            "source_document_role": evidence.source_document_role,
            "source_snapshot_path": evidence.source_snapshot_path,
            "source_content_sha256": evidence.source_content_sha256,
            "source_content_bytes": evidence.source_content_bytes,
            "research_claim_ids": sorted(metric_use["research_claim_ids"]),
        }
        if evidence.period:
            fact["period"] = evidence.period
        if evidence.formula_id:
            fact["formula_id"] = evidence.formula_id
            fact["formula_operands"] = dict(sorted(evidence.formula_operands.items()))
        facts.append(fact)

    _validate_typed_facts(facts)

    sources = [
        _source_record(
            registry_by_id[source_id],
            report_as_of=data_packet.as_of_date,
        )
        for source_id in dict.fromkeys(used_source_ids)
    ]
    if len(sources) < 2:
        raise FactLedgerError(
            f"fact ledger needs at least 2 registered sources; found {len(sources)}"
        )
    if not any(source["source_type"] in {"SEC", "IR"} for source in sources):
        raise FactLedgerError("fact ledger has no primary SEC or IR source")

    return {
        "contract_id": FACT_LEDGER_CONTRACT_ID,
        "contract_version": FACT_LEDGER_CONTRACT_VERSION,
        "ticker": data_packet.ticker.upper(),
        "company": data_packet.company_name or data_packet.ticker.upper(),
        "report_asof": data_packet.as_of_date,
        "claims": facts,
        "sources": sources,
    }


def save_fact_ledger(payload: dict[str, Any], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def _select_exact_evidence(
    *,
    evidence_ledger: EvidenceLedger,
    metric_name: str,
    value: float,
    as_of_date: str,
    allowed_evidence_ids: set[str],
) -> EvidenceItem:
    candidates = [
        item
        for item in evidence_ledger.evidence_items
        if (not allowed_evidence_ids or item.evidence_id in allowed_evidence_ids)
        and metric_name in item.supports_metrics
        and item.value is not None
        and _same_number(float(item.value), value)
        and _has_numeric_authority(item)
    ]
    if not candidates:
        raise FactLedgerError(
            f"no exact evidence value for {metric_name}={value}"
        )
    return sorted(
        candidates,
        key=lambda item: (
            0 if item.formula_id else 1,
            0 if item.normalized_value is not None else 1,
            0 if item.date == as_of_date else 1,
            item.authority_rank,
            item.evidence_id,
        ),
    )[0]


def _has_numeric_authority(item: EvidenceItem) -> bool:
    return bool(
        item.formula_id
        or item.raw_value is not None
        or item.normalized_value is not None
        or (item.date and item.period)
    )


def _same_number(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def _resolve_registered_source_ids(
    source_ids: Iterable[str],
    registry_by_id: dict[str, Any],
) -> list[str]:
    """Resolve compact SEC lineage IDs to their registered canonical IDs."""

    resolved: list[str] = []
    for raw_source_id in source_ids:
        source_id = str(raw_source_id or "").strip()
        if not source_id:
            continue
        if source_id in registry_by_id:
            resolved.append(source_id)
            continue
        suffix = source_id.removeprefix("SEC_")
        matches = sorted(
            candidate
            for candidate in registry_by_id
            if suffix and candidate.endswith(suffix)
        )
        if len(matches) == 1:
            resolved.append(matches[0])
    return list(dict.fromkeys(resolved))


def _period_type(metric_name: str, evidence: EvidenceItem) -> str:
    if evidence.period_kind == "guidance":
        return "range"
    if evidence.period_kind == "comparison":
        return "comparison"
    if evidence.period_kind == "trailing_twelve_months":
        return "ttm"
    if evidence.formula_id:
        return "calculated"
    if evidence.period_kind == "duration" and evidence.duration_days is None:
        return "duration"
    if evidence.period_kind == "instant":
        return "instant"
    lowered_period = str(evidence.period or "").lower()
    if metric_name.endswith("_ttm") or "ttm" in lowered_period:
        return "ttm"
    if "guidance" in metric_name:
        return "range"
    if "run_rate" in metric_name:
        return "run_rate"
    if evidence.duration_days is not None:
        if 70 <= evidence.duration_days <= 110:
            return "quarterly"
        if 111 <= evidence.duration_days < 330:
            return "ytd"
        if 330 <= evidence.duration_days <= 380:
            return "annual"
        return "duration"
    if metric_name.startswith("current_q_") or "quarter" in lowered_period:
        return "quarterly"
    return "unknown"


def _period_metadata(metric_name: str, evidence: EvidenceItem) -> dict[str, Any]:
    period = str(evidence.period or "")
    lowered = period.casefold()
    period_end = evidence.period_end or evidence.date
    period_start = evidence.period_start
    comparison = _comparison_periods(period)
    if evidence.period_kind == "unknown" and evidence.value is not None:
        raise FactLedgerError(
            f"material numeric fact {metric_name} has unknown period semantics"
        )
    if evidence.period_kind == "guidance":
        if not evidence.period_start or not (evidence.period_end or evidence.date):
            raise FactLedgerError(
                f"guidance fact {metric_name} lacks a complete guidance period"
            )
        return {
            "period_kind": "guidance",
            "period_start": evidence.period_start,
            "period_end": evidence.period_end or evidence.date,
        }
    if evidence.period_kind == "comparison" and all(
        (
            evidence.current_period_start,
            evidence.current_period_end,
            evidence.comparison_period_start,
            evidence.comparison_period_end,
        )
    ):
        return {
            "period_kind": "comparison",
            "period_start": evidence.current_period_start,
            "period_end": evidence.current_period_end,
            "comparison_period_start": evidence.comparison_period_start,
            "comparison_period_end": evidence.comparison_period_end,
            "current_period_start": evidence.current_period_start,
            "current_period_end": evidence.current_period_end,
        }
    if comparison is not None or metric_name.endswith("_yoy"):
        comparison = comparison or _comparison_from_evidence(evidence)
        if comparison is None:
            raise FactLedgerError(
                f"comparison fact {metric_name} lacks machine-readable comparison periods"
            )
        return {
            "period_kind": "comparison",
            # Generic period fields always describe the primary/current
            # measurement.  The comparator is orthogonal metadata.
            "period_start": comparison[1][0],
            "period_end": comparison[1][1],
            "comparison_period_start": comparison[0][0],
            "comparison_period_end": comparison[0][1],
            "current_period_start": comparison[1][0],
            "current_period_end": comparison[1][1],
        }
    if metric_name.endswith("_ttm") or "ttm" in lowered or "trailing twelve" in lowered:
        if not period_end:
            raise FactLedgerError(f"TTM fact {metric_name} lacks a period end")
        if not period_start:
            range_dates = _iso_period_range(period)
            period_start = range_dates[0] if range_dates else (
                date.fromisoformat(period_end) - timedelta(days=364)
            ).isoformat()
        return {
            "period_kind": "trailing_twelve_months",
            "period_start": period_start,
            "period_end": period_end,
        }
    range_dates = _iso_period_range(period)
    if period_start or evidence.duration_days is not None or range_dates:
        period_start = period_start or (range_dates[0] if range_dates else None)
        period_end = period_end or (range_dates[1] if range_dates else None)
        if not period_start or not period_end:
            raise FactLedgerError(f"duration fact {metric_name} lacks start/end dates")
        return {
            "period_kind": "duration",
            "period_start": period_start,
            "period_end": period_end,
        }
    if not period_end:
        raise FactLedgerError(f"instant fact {metric_name} lacks an as-of date")
    return {
        "period_kind": "instant",
        "period_start": None,
        "period_end": period_end,
    }


def _iso_period_range(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})", value.strip())
    return (match.group(1), match.group(2)) if match else None


def _comparison_periods(value: str) -> tuple[tuple[str, str], tuple[str, str]] | None:
    match = re.fullmatch(r"CY(\d{4})Q([1-4])\.\.CY(\d{4})Q([1-4])", value.strip())
    if not match:
        return None
    return (
        _quarter_bounds(int(match.group(1)), int(match.group(2))),
        _quarter_bounds(int(match.group(3)), int(match.group(4))),
    )


def _comparison_from_evidence(
    evidence: EvidenceItem,
) -> tuple[tuple[str, str], tuple[str, str]] | None:
    """Recover comparison bounds only from explicit deterministic metadata.

    Legacy calculation evidence sometimes stored an ISO start/end range rather
    than the two fiscal labels.  The start is the prior-period start and the end
    is the current-period end.  Formula identity tells us whether both matched
    periods are quarters or full years; no date is inferred from prose.
    """

    if not evidence.period_start or not (evidence.period_end or evidence.date):
        return None
    prior_start = date.fromisoformat(evidence.period_start)
    current_end = date.fromisoformat(str(evidence.period_end or evidence.date))
    formula_id = str(evidence.formula_id or "")
    if not any(
        token in formula_id
        for token in ("quarter", "annual", "fiscal_year", "matching_period")
    ):
        return None
    prior_end = _shift_year(current_end, -1)
    current_start = _shift_year(prior_start, 1)
    return (
        (prior_start.isoformat(), prior_end.isoformat()),
        (current_start.isoformat(), current_end.isoformat()),
    )


def _shift_year(value: date, years: int) -> date:
    target_year = value.year + years
    return date(target_year, value.month, min(value.day, monthrange(target_year, value.month)[1]))


def _quarter_bounds(year: int, quarter: int) -> tuple[str, str]:
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    return (
        date(year, start_month, 1).isoformat(),
        date(year, end_month, monthrange(year, end_month)[1]).isoformat(),
    )


def _presentation_basis(
    metric_name: str,
    evidence: EvidenceItem,
    *,
    period_kind: str,
) -> str:
    if evidence.presentation_basis and evidence.presentation_basis != "unknown":
        expected = {
            "instant": "point_in_time",
            "duration": {"period_total", "period_average"},
            "comparison": "period_over_period_comparison",
            "trailing_twelve_months": "trailing_twelve_months",
            "guidance": "guidance_range",
        }.get(period_kind)
        if isinstance(expected, set):
            if evidence.presentation_basis in expected:
                return evidence.presentation_basis
        elif expected == evidence.presentation_basis:
            return evidence.presentation_basis
    lowered_period = str(evidence.period or "").lower()
    if period_kind == "comparison":
        return "period_over_period_comparison"
    if period_kind == "trailing_twelve_months":
        return "trailing_twelve_months"
    if period_kind == "guidance":
        return "guidance_range"
    if period_kind == "duration":
        if evidence.duration_days is None:
            return "period_total"
        if 70 <= evidence.duration_days <= 110:
            return "period_total"
        if 111 <= evidence.duration_days < 330:
            return "period_total"
        if 330 <= evidence.duration_days <= 380:
            return "period_total"
        return "period_total"
    if evidence.duration_days is not None:
        if 70 <= evidence.duration_days <= 110:
            return "quarter"
        if 111 <= evidence.duration_days < 330:
            return "year_to_date"
        if 330 <= evidence.duration_days <= 380:
            return "full_year"
        return "duration_unknown"
    return "point_in_time"


def _typed_unit(evidence: EvidenceItem) -> tuple[str, str, str | None]:
    """Preserve the evidence dimension; never reclassify it by metric name."""

    dimension = str(evidence.dimension or "unknown")
    display_unit = str(evidence.display_unit or evidence.unit or "").strip()
    currency = str(evidence.currency or "").strip().upper() or None
    if dimension == "currency":
        if currency is None and re.fullmatch(r"[A-Z]{3}", display_unit.upper()):
            currency = display_unit.upper()
        if currency is None:
            raise FactLedgerError(
                f"currency evidence {evidence.evidence_id} lacks ISO currency"
            )
        display_unit = currency
    if not display_unit:
        display_unit = dimension
    if dimension == "unknown":
        raise FactLedgerError(
            f"numeric evidence {evidence.evidence_id} has unknown dimension"
        )
    return dimension, display_unit, currency


def _validate_typed_facts(facts: list[dict[str, Any]]) -> None:
    for fact in facts:
        metric = str(fact.get("metric") or "<unknown>")
        period_kind = fact.get("period_kind")
        basis = fact.get("presentation_basis")
        if period_kind == "instant" and basis != "point_in_time":
            raise FactLedgerError(
                f"instant fact {metric} has incompatible presentation basis {basis}"
            )
        if period_kind == "duration" and basis not in {
            "period_total",
            "period_average",
        }:
            raise FactLedgerError(
                f"duration fact {metric} has incompatible presentation basis {basis}"
            )
        if period_kind == "comparison":
            required = {
                "current_period_start",
                "current_period_end",
                "comparison_period_start",
                "comparison_period_end",
            }
            if any(not fact.get(key) for key in required):
                raise FactLedgerError(
                    f"comparison fact {metric} lacks complete current/comparison periods"
                )
            if (
                fact["period_start"] != fact["current_period_start"]
                or fact["period_end"] != fact["current_period_end"]
            ):
                raise FactLedgerError(
                    f"comparison fact {metric} generic period is not the current period"
                )
        if fact.get("dimension") == "currency" and not fact.get("currency"):
            raise FactLedgerError(f"currency fact {metric} lacks ISO currency")


def _canonical_unit(
    metric_name: str,
    evidence_unit: str | None,
    price_currency: str,
) -> str:
    if (
        "margin" in metric_name
        or "growth" in metric_name
        or "yield" in metric_name
        or metric_name.startswith("sbc_to_")
        or metric_name.endswith("_pct")
    ):
        return "fraction (1.0 = 100%)"
    if metric_name in {
        "ev_to_sales",
        "price_to_fcf",
        "ev_to_ebit",
        "ev_to_ebitda",
        "trailing_pe",
        "forward_pe_consensus",
        "forward_pe_guidance",
        "peg_ratio",
        "current_ratio",
        "debt_to_equity",
    }:
        return "multiple"
    if metric_name == "rsi_14":
        return "index"
    if metric_name.endswith("share_count_yoy"):
        return "ratio"
    if "share_count" in metric_name or "volume" in metric_name or metric_name.startswith("customers_"):
        return "shares" if "customers_" not in metric_name else "count"
    if metric_name == "close" or metric_name.startswith(("sma_", "ema_")):
        return price_currency.upper()
    if evidence_unit:
        return str(evidence_unit).upper()
    return "count"


def _source_record(source: Any, *, report_as_of: str) -> dict[str, Any]:
    source_type = _promotion_source_type(str(source.source_type))
    title = (
        f"{source.owner}: {source.source_id}"
        if source.owner
        else source.source_id
    )
    payload = {
        "source_id": source.source_id,
        "source_type": source_type,
        "title": title,
        "asof": source.retrieved_at or report_as_of,
        "original_source_type": source.source_type,
    }
    if source.url:
        payload["url"] = source.url
    return payload


def _promotion_source_type(source_type: str) -> str:
    normalized = source_type.strip().lower()
    if normalized == "sec_filing":
        return "SEC"
    if normalized in {"company_ir", "official_press_release"}:
        return "IR"
    if normalized == "earnings_transcript":
        return "TRANSCRIPT"
    if normalized in {"exchange_ohlcv", "trusted_market_data_vendor"}:
        return "PRICE_VENDOR"
    if normalized in {"deterministic_calculation", "derived_calculation"}:
        return "DERIVED_CALCULATION"
    if normalized in {"reuters", "barrons", "marketwatch", "wsj"}:
        return "NEWSWIRE"
    if normalized == "social_media":
        return "SOCIAL"
    return "VENDOR"
