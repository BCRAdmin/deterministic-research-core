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
from research_agent.research_core.calculations.fundamentals import (
    current_operating_profit_decline_metrics,
)
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
    if any(
        warning.get("code") == "MULTI_CLASS_PRICE_BASIS_UNAVAILABLE"
        for warning in (reconciliation_warnings or [])
    ):
        lines.append(
            "- Market-cap-derived multiples are unavailable because the filing "
            "reports multiple stock classes, while the packet has only one "
            "traded-class price and no verified cross-class price equivalence."
        )
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
    valuation_status = decision_packet.signal_scores.valuation_status
    parts = [
        f"- Thesis anchor: `{preferred}` follows the measured fundamental and technical evidence plus the explicit valuation measurement status.",
    ]
    if revenue is not None:
        parts.append(f"- Fundamental basis: revenue scale is `{_fmt_money(revenue, currency)}`.")
    if fcf is not None:
        parts.append(f"- Cash-conversion basis: free cash flow is `{_fmt_money(fcf, currency)}`.")
    else:
        parts.append("- Cash-conversion basis: FCF is unavailable in the evidence set and should be treated as a data limitation.")
    if ev_sales is not None:
        if valuation_status == "unbenchmarked":
            parts.append(
                f"- Valuation observation: EV/Sales is `{ev_sales:.2f}x`; "
                "without benchmark evidence it is neutral for the rating."
            )
        elif valuation_status == "measured":
            parts.append(
                f"- Benchmarked valuation evidence includes EV/Sales of "
                f"`{ev_sales:.2f}x`."
            )
        else:
            parts.append(
                f"- Valuation observation: EV/Sales is `{ev_sales:.2f}x`, but "
                "valuation is not sufficiently measured to affect the rating."
            )
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
    scores = decision_packet.signal_scores
    rating_reason = (
        decision_packet.analytical_rating_reason
        or decision_packet.rating_permission.reason
    )
    if scores.valuation_status == "unbenchmarked":
        valuation_observations = [
            ("EV/Sales", v.ev_to_sales),
            ("P/FCF", v.price_to_fcf),
            ("trailing P/E", v.trailing_pe),
        ]
        available_observations = [
            f"{label} `{_fmt_multiple(value)}`"
            for label, value in valuation_observations
            if value is not None
        ]
        if available_observations:
            observation_text = " and ".join(available_observations)
            grammar = (
                "is an unbenchmarked observation"
                if len(available_observations) == 1
                else "are unbenchmarked observations"
            )
            effect_verb = "adds" if len(available_observations) == 1 else "add"
            valuation_line = (
                f"- Valuation status: {observation_text} {grammar} and {effect_verb} "
                "neither a positive nor a negative rating signal."
            )
        else:
            valuation_line = (
                "- Valuation status: no measured multiple is available; "
                "valuation cannot move the rating."
            )
    elif scores.valuation_status != "measured":
        valuation_line = (
            "- Valuation status: insufficiently measured; valuation cannot move "
            "the rating."
        )
    elif scores.valuation_score > 0:
        valuation_line = "- Valuation status: benchmarked evidence is constructive."
    elif scores.valuation_score < 0:
        valuation_line = "- Valuation status: benchmarked evidence is cautious."
    else:
        valuation_line = "- Valuation status: benchmarked evidence is neutral."
    current_profit_declines = [
        label
        for label, metric_name in (
            (
                "operating-income",
                "current_period_operating_income_growth_yoy",
            ),
            ("net-income", "current_period_net_income_growth_yoy"),
        )
        if metric_name in current_operating_profit_decline_metrics(f)
    ]
    if current_profit_declines and f.free_cash_flow_ttm is None:
        decline_text = " and ".join(current_profit_declines)
        technical_counterevidence = (
            " The bullish technical direction is counterevidence, but does not "
            "erase those declines."
            if scores.technical_score > 0
            else ""
        )
        why_not_constructive = (
            f"- Why not more constructive? Current-period {decline_text} declines "
            "are current downside evidence. FCF is unavailable, so cash conversion "
            "cannot offset or confirm the reported weakness. A more constructive "
            "rating requires improving profit comparisons and measurable cash-flow "
            "support."
        )
        why_not_cautious = (
            f"- Why not more cautious? The {decline_text} declines are not dismissed."
            f"{technical_counterevidence} One reported period does not establish "
            "the cause or durability of the weakness; a more cautious rating "
            "requires persistence or corroborating cash-flow deterioration once "
            "cash conversion is measurable."
        )
    elif (
        current_profit_declines
        and f.free_cash_flow_ttm is not None
        and f.free_cash_flow_ttm > 0
    ):
        decline_text = " and ".join(current_profit_declines)
        counterevidence_subject = (
            "positive FCF and the bullish technical direction are"
            if scores.technical_score > 0
            else "positive FCF is"
        )
        why_not_constructive = (
            f"- Why not more constructive? Current-period {decline_text} declines "
            "are current downside evidence; positive FCF does not erase those "
            "reported comparisons. A more constructive rating requires profit "
            "comparisons to improve, that improvement to persist, and benchmarked "
            "valuation support."
        )
        why_not_cautious = (
            f"- Why not more cautious? The {decline_text} declines are not dismissed, "
            f"but {counterevidence_subject} measured counterevidence. "
            "A more cautious rating requires the profit weakness to persist or be "
            "corroborated by weaker cash conversion."
        )
    else:
        why_not_constructive = (
            "- Why not more constructive? A rating change requires stronger measured "
            "fundamentals or technical confirmation and, where valuation is relevant, "
            "benchmark evidence."
        )
        why_not_cautious = (
            "- Why not more cautious? A raw multiple or an isolated price signal "
            "cannot establish business deterioration."
        )
    lines = [
        f"- Why this rating? `{preferred}`: {rating_reason}",
        f"- Fundamental anchors: revenue is `{_fmt_money(f.revenue_ttm, currency)}` and FCF is `{_fmt_money(f.free_cash_flow_ttm, currency)}`.",
        valuation_line,
        f"- Technical context: RSI is `{_fmt_number(t.rsi_14)}`; its directional role is limited to the measured technical score.",
        why_not_constructive,
        why_not_cautious,
        f"- Review condition: retain `{data_packet.ticker}` at `{preferred}` while the measured evidence state is unchanged; reassess only when new primary evidence changes fundamentals, benchmarked valuation or the technical trend.",
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
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:
        amount = f"{magnitude / 1_000_000_000:.2f}B"
    elif magnitude >= 1_000_000:
        amount = f"{magnitude / 1_000_000:.1f}M"
    else:
        amount = f"{magnitude:.2f}"
    sign = "-" if value < 0 else ""
    return (
        f"{sign}${amount}"
        if normalized_currency == "USD"
        else f"{sign}{amount} {normalized_currency}"
    )


def _fmt_multiple(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.2f}x"


def _fmt_number(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.2f}"
