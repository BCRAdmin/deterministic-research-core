from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from research_agent.decision.decision_packet import DecisionPacket
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.research_core.reporting.report_builder import render_metric_table


REPORT_SECTIONS = [
    "Executive Summary",
    "Data / Source Quality Note",
    "Business & Segment Context",
    "Fundamental Analysis",
    "Valuation / Multiples",
    "Technical Setup",
    "Bull Case",
    "Bear Case",
    "Key Risks",
    "Catalysts & Triggers",
    "Scenario View",
    "Final Rating & Action Plan",
    "Evidence Appendix",
]


def compose_research_report(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    validation_report: ValidationReport,
    decision_packet: DecisionPacket,
    evidence_ledger: EvidenceLedger,
    claims: Iterable[ResearchClaim],
    reconciliation_warnings: Optional[list[dict]] = None,
) -> str:
    claim_list = list(claims)
    grouped = _group_by_section(claim_list)
    preferred = decision_packet.rating_permission.preferred_rating.value
    allowed = ", ".join(rating.value for rating in decision_packet.rating_permission.allowed_ratings)
    blocked = ", ".join(rating.value for rating in decision_packet.rating_permission.blocked_ratings)

    sections = [
        f"# {data_packet.ticker} Research Report",
        "## Executive Summary",
        _render_claim_section(grouped, "Executive Summary"),
        "",
        "## Investment Thesis",
        _render_investment_thesis(data_packet, metrics_packet, decision_packet),
        "",
        "## Data / Source Quality Note",
        _render_data_note(data_packet, validation_report, reconciliation_warnings),
        "",
        "## Validated Metric Table",
        render_metric_table(metrics_packet, data_packet.price_basis.currency),
        "",
        "## Business & Segment Context",
        _render_claim_section(grouped, "Business & Segment Context"),
        "",
        *_render_optional_sections(
            grouped,
            [
                "Business Model Reality",
                "Revenue Scale and Backlog",
                "Contract / Backlog Materiality",
                "Segment Mix",
                "Execution Milestones",
                "FCF Path",
                "Capital Intensity",
                "Valuation vs Revenue/Backlog",
                "Technical Setup only as timing",
                "Final Internal View",
            ],
        ),
        "## Fundamental Analysis",
        _render_claim_section(grouped, "Fundamental Analysis"),
        "",
        "## Valuation / Multiples",
        _render_claim_section(grouped, "Valuation / Multiples"),
        "",
        "## Technical Setup",
        _render_claim_section(grouped, "Technical Setup"),
        "",
        "## Bull Case",
        _render_claim_section(grouped, "Bull Case"),
        "",
        "## Bear Case",
        _render_claim_section(grouped, "Bear Case"),
        "",
        "## Key Risks",
        _render_claim_section(grouped, "Key Risks"),
        "",
        "## Catalysts & Triggers",
        _render_claim_section(grouped, "Catalysts & Triggers"),
        _render_event_limit(data_packet),
        "",
        "## Scenario View",
        _render_scenario_view(decision_packet),
        "",
        "## Final Rating & Action Plan",
        f"Final Rating: {preferred}",
        "",
        _render_final_rating_logic(data_packet, metrics_packet, decision_packet),
        "",
        _render_action_policy(decision_packet),
        "",
        _render_claim_section(grouped, "Final Rating & Action Plan"),
        "",
        "## Rating Permission Appendix",
        f"Allowed ratings: {allowed}. Blocked ratings: {blocked}.",
        "",
        "## Evidence Appendix",
        _render_evidence_appendix(claim_list, evidence_ledger),
    ]
    return _clean_main_body_mechanical_language("\n".join(section for section in sections if section is not None)).strip() + "\n"


def save_research_claims(claims: Iterable[ResearchClaim], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        claim.model_dump(mode="json") if hasattr(claim, "model_dump") else claim.dict()
        for claim in claims
    ]
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _group_by_section(claims: list[ResearchClaim]) -> dict[str, list[ResearchClaim]]:
    grouped: dict[str, list[ResearchClaim]] = {}
    for claim in claims:
        grouped.setdefault(claim.section or "Unassigned", []).append(claim)
    return grouped


def _render_claim_section(grouped: dict[str, list[ResearchClaim]], section: str) -> str:
    claims = grouped.get(section, [])
    if not claims:
        return "- No evidence-backed claim is available for this section."
    lines = []
    for claim in claims:
        lines.append(f"- **{claim.claim_id}**: {claim.claim}")
        if claim.counterargument:
            lines.append(f"  Counterargument: {claim.counterargument}")
        if claim.investment_implication:
            lines.append(f"  Investment implication: {claim.investment_implication}")
        lines.append(f"  Source labels: `{_short_source_labels(claim)}`.")
    return "\n".join(lines)


def _render_optional_sections(grouped: dict[str, list[ResearchClaim]], section_names: list[str]) -> list[str]:
    sections: list[str] = []
    for section in section_names:
        if not grouped.get(section):
            continue
        sections.extend([f"## {section}", _render_claim_section(grouped, section), ""])
    return sections


def _render_data_note(
    data_packet: DataPacket,
    validation_report: ValidationReport,
    reconciliation_warnings: Optional[list[dict]],
) -> str:
    lines = [
        f"- Report as-of date: `{data_packet.as_of_date}`.",
        f"- Price basis: `{data_packet.price_basis.date}` close via `{data_packet.price_basis.source}`.",
    ]
    if data_packet.as_of_date != data_packet.price_basis.date:
        lines.append(
            f"- Technical indicators are based on the closing price from `{data_packet.price_basis.date}`, not on the report creation date `{data_packet.as_of_date}`."
        )
    if validation_report.issues:
        lines.append(f"- Validation issues in packet: `{len(validation_report.issues)}`.")
    true_disagreements = [
        warning for warning in (reconciliation_warnings or [])
        if warning.get("code") == "TRUE_SOURCE_VALUE_DISAGREEMENT"
    ]
    lines.append(f"- True unresolved source disagreements: `{len(true_disagreements)}`.")
    return "\n".join(lines)


def _render_investment_thesis(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    decision_packet: DecisionPacket,
) -> str:
    preferred = decision_packet.rating_permission.preferred_rating.value
    revenue = metrics_packet.fundamentals.revenue_ttm
    fcf = metrics_packet.fundamentals.free_cash_flow_ttm
    ev_sales = metrics_packet.valuation.ev_to_sales
    currency = data_packet.price_basis.currency
    parts = [
        f"- Thesis anchor: `{preferred}` reflects the balance between business momentum, valuation discipline and technical timing.",
    ]
    if revenue is not None:
        parts.append(f"- Fundamental basis: revenue scale is `{_fmt_money(revenue, currency)}`.")
    if fcf is not None:
        parts.append(f"- Cash-conversion basis: free cash flow is `{_fmt_money(fcf, currency)}`.")
    else:
        parts.append("- Cash-conversion basis: FCF is unavailable in the evidence set and should be treated as a data limitation.")
    if ev_sales is not None:
        parts.append(f"- Valuation constraint: EV/Sales is `{ev_sales:.2f}x`.")
    parts.append(
        f"- Research implication: the stance for `{data_packet.ticker}` remains conditional on the business, valuation and technical evidence."
    )
    return "\n".join(parts)


def _render_event_limit(data_packet: DataPacket) -> str:
    event = data_packet.next_events
    if not event.next_earnings_date or not event.confirmed:
        return "\n- Earnings date unavailable in the evidence set; no earnings event-risk claim is made."
    return f"\n- Confirmed earnings date: `{event.next_earnings_date}` via `{event.source}`."


def _render_scenario_view(decision_packet: DecisionPacket) -> str:
    preferred = decision_packet.rating_permission.preferred_rating.value
    return "\n".join(
        [
            f"- Base case: `{preferred}` is the appropriate current stance.",
            "- Bull case: become more constructive only if fundamentals and technical confirmation improve.",
            "- Bear case: become more defensive only if new blocking evidence or trend deterioration appears.",
        ]
    )


def _render_action_policy(decision_packet: DecisionPacket) -> str:
    policy = decision_packet.action_policy or {}
    research_stance = policy.get("research_stance", "Manual review required")
    lines = [f"Research stance: {research_stance}."]
    conditions = policy.get("confirmation_conditions") or []
    if conditions:
        lines.append("Confirmation conditions: " + "; ".join(str(item) for item in conditions) + ".")
    return "\n".join(lines)


def _render_final_rating_logic(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    decision_packet: DecisionPacket,
) -> str:
    preferred = decision_packet.rating_permission.preferred_rating.value
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    t = metrics_packet.technical
    currency = data_packet.price_basis.currency
    lines = [
        f"- Why this rating? `{preferred}` balances revenue of `{_fmt_money(f.revenue_ttm, currency)}` against valuation and technical timing.",
        f"- Cash conversion: FCF is `{_fmt_money(f.free_cash_flow_ttm, currency)}` and determines whether growth converts into equity value.",
        f"- Why not more bullish? EV/Sales `{_fmt_multiple(v.ev_to_sales)}` limits new-money urgency unless current-period KPIs accelerate.",
        f"- Additional valuation/technical constraint: P/FCF `{_fmt_multiple(v.price_to_fcf)}` and RSI `{_fmt_number(t.rsi_14)}` argue against chasing without a better setup.",
        "- Why not more bearish? The report avoids a harsher stance unless validated fundamentals deteriorate, source reconciliation breaks, or technical weakness confirms a deeper drawdown.",
        "- What would change the rating? Cleaner current-period KPI acceleration, better FCF conversion, lower valuation risk or confirmed technical recovery would support a more constructive action.",
        f"- Plain-language action plan: keep `{data_packet.ticker}` inside the stated action plan; add only on better risk/reward or trim if current-period evidence weakens.",
    ]
    return "\n".join(lines)


def _clean_main_body_mechanical_language(markdown: str) -> str:
    if "## Evidence Appendix" in markdown:
        main, appendix = markdown.split("## Evidence Appendix", 1)
        return f"{_replace_mechanical_language(main).rstrip()}\n\n## Evidence Appendix{appendix}"
    return _replace_mechanical_language(markdown)


def _replace_mechanical_language(text: str) -> str:
    replacements = {
        "validated packet": "available evidence",
        "Validated packet": "Available evidence",
        "validated close": "latest close",
        "Validated close": "Latest close",
        "confirmed packet inputs": "confirmed evidence",
        "Confirmed packet inputs": "Confirmed evidence",
        "packet inputs": "evidence inputs",
        "Packet inputs": "Evidence inputs",
        "Packet-derived": "Derived",
        "packet-derived": "derived",
        "sanity guards": "data-quality checks",
        "sanity guard": "data-quality check",
        "blocking audit errors": "blocking data issues",
        "Blocking audit errors": "Blocking data issues",
        "audit issues": "data-quality issues",
        "audit has": "review has",
        "Source-quality limitations": "Source limitations",
        "source-quality limitations": "source limitations",
        "source-quality issues": "source concerns",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _render_evidence_appendix(claims: list[ResearchClaim], evidence_ledger: EvidenceLedger) -> str:
    lines = [
        "| Claim ID | Claim | Evidence IDs | Source Type | Confidence | Metric Refs |",
        "|---|---|---|---|---|---|",
    ]
    evidence_by_id = {item.evidence_id: item for item in evidence_ledger.evidence_items}
    for claim in claims:
        source_types = sorted({
            evidence_by_id[item_id].source_type
            for item_id in claim.evidence_ids
            if item_id in evidence_by_id
        })
        lines.append(
            "| {claim_id} | {claim_text} | {evidence_ids} | {source_types} | {confidence} | {metrics} |".format(
                claim_id=claim.claim_id or "",
                claim_text=_table_text(claim.claim),
                evidence_ids=", ".join(claim.evidence_ids),
                source_types=", ".join(source_types),
                confidence=claim.confidence,
                metrics=", ".join(claim.metric_refs or claim.evidence_metrics),
            )
        )
    return "\n".join(lines)


def _short_source_labels(claim: ResearchClaim) -> str:
    labels = []
    for source_id in claim.source_ids[:3]:
        if "CSV_PRICE" in source_id or "PRICE_PROVIDER" in source_id:
            labels.append("CSV OHLCV price")
        elif source_id.startswith("SEC_") or "_SEC_" in source_id:
            labels.append("SEC filing")
        elif "IR" in source_id or "EARNINGS" in source_id:
            labels.append("Company IR release")
        else:
            labels.append(source_id)
    return ", ".join(dict.fromkeys(labels)) if labels else "validated evidence"


def _paragraph(text: str) -> str:
    return text


def _table_text(text: str) -> str:
    return " ".join(text.replace("|", "/").split())


def _fmt_money(value: float, currency: str = "USD") -> str:
    if value is None:
        return "unavailable"
    normalized_currency = str(currency or "USD").strip().upper()
    if abs(value) >= 1_000_000_000:
        amount = f"{value / 1_000_000_000:.2f}B"
    elif abs(value) >= 1_000_000:
        amount = f"{value / 1_000_000:.1f}M"
    else:
        amount = f"{value:.2f}"
    return f"${amount}" if normalized_currency == "USD" else f"{amount} {normalized_currency}"


def _fmt_multiple(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.2f}x"


def _fmt_number(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.2f}"
