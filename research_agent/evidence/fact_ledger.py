"""Build the canonical, reviewable fact ledger from structured research claims."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket


FACT_LEDGER_CONTRACT_ID = "room16-canonical-fact-ledger"
FACT_LEDGER_CONTRACT_VERSION = 2


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
                {"value": value, "research_claim_ids": []},
            )
            if claim.claim_id and claim.claim_id not in item["research_claim_ids"]:
                item["research_claim_ids"].append(claim.claim_id)

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
        fact = {
            "claim_id": f"{data_packet.ticker.upper()}_FACT_{metric_name.upper()}",
            "label": metric_name.replace("_", " "),
            "metric": metric_name,
            "value": metric_use["value"],
            "unit": _canonical_unit(
                metric_name,
                evidence.unit,
                data_packet.price_basis.currency,
            ),
            "period_type": _period_type(metric_name, evidence),
            "period_kind": _period_kind(evidence),
            "period_start": evidence.period_start,
            "period_end": evidence.period_end or evidence.date,
            "fiscal_label": evidence.period,
            "presentation_basis": _presentation_basis(metric_name, evidence),
            "asof": evidence.date or data_packet.as_of_date,
            "source_id": evidence.source_id,
            "source_ids": source_ids,
            "evidence_ids": [evidence.evidence_id],
            "research_claim_ids": sorted(metric_use["research_claim_ids"]),
        }
        if evidence.period:
            fact["period"] = evidence.period
        if evidence.formula_id:
            fact["formula_id"] = evidence.formula_id
            fact["formula_operands"] = dict(sorted(evidence.formula_operands.items()))
        facts.append(fact)

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
) -> EvidenceItem:
    candidates = [
        item
        for item in evidence_ledger.evidence_items
        if metric_name in item.supports_metrics
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
    if evidence.formula_id:
        return "calculated"
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
    return "spot"


def _period_kind(evidence: EvidenceItem) -> str:
    return "duration" if evidence.period_start or evidence.duration_days is not None else "instant"


def _presentation_basis(metric_name: str, evidence: EvidenceItem) -> str:
    lowered_period = str(evidence.period or "").lower()
    if metric_name.endswith("_ttm") or "ttm" in lowered_period:
        return "trailing_twelve_months"
    if evidence.duration_days is not None:
        if 70 <= evidence.duration_days <= 110:
            return "quarter"
        if 111 <= evidence.duration_days < 330:
            return "year_to_date"
        if 330 <= evidence.duration_days <= 380:
            return "full_year"
        return "duration_unknown"
    return "point_in_time"


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
    if normalized in {"reuters", "barrons", "marketwatch", "wsj"}:
        return "NEWSWIRE"
    if normalized == "social_media":
        return "SOCIAL"
    return "VENDOR"
