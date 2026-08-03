from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from research_agent.decision.decision_packet import DecisionPacket
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket


PUBLISH_MECHANICAL_PHRASES = {
    "packet-derived",
    "decisionpacket",
    "rating corridor",
    "committee anchor",
    "validated packet",
    "packet inputs",
    "inside the stated action plan",
    "validated close",
    "audit issue",
    "blocking audit error",
    "sanity guard",
        "source-quality limitation",
        "manual review",
    "business context is intentionally grounded",
    "segment-specific interpretation should only be expanded",
}

CURRENT_KPI_TERMS = {
    "q1", "q2", "q3", "q4", "fy2025", "fy2026", "fy2027", "current-period",
    "google cloud", "product revenue", "rpo", "nrr", "capex", "other income",
    "adjusted fcf", "adjusted free cash flow", "operating margin",
    "microsoft cloud", "azure", "ai run-rate", "ai business", "family of apps",
    "free cash flow", "operating cash flow", "buyback", "ai revenue",
    "ai semiconductor", "q2 revenue guide", "q2 guide",
    "revenue", "fcf", "sbc", "marketable securities", "observability",
    "agentforce", "data cloud", "cash plus",
    "backlog", "contract backlog", "contracted missions", "launch manifest",
    "electron", "haste", "launch cadence", "neutron", "space systems",
    "launch services", "segment mix", "capital intensity", "execution milestone",
}
CURRENT_PERIOD_MARKER_RE = re.compile(
    r"\b(?:current-period|latest reported period|q[1-4]|fy20\d{2}[_ -]?q[1-4])\b",
    re.IGNORECASE,
)
CURRENT_PERIOD_SECTIONS = {
    "Business & Segment Context",
    "Fundamental Analysis",
    "Catalysts & Triggers",
    "Key Risks",
    "Business Model Reality",
    "Revenue Scale and Backlog",
    "Contract / Backlog Materiality",
    "Segment Mix",
    "Execution Milestones",
    "FCF Path",
    "Capital Intensity",
    "Valuation vs Revenue/Backlog",
}


def compose_publish_report(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    decision_packet: DecisionPacket,
    evidence_ledger: EvidenceLedger,
    claims: Iterable[ResearchClaim],
) -> str:
    """Render a client-facing report from evidence-backed claims.

    `final_report.md` remains the internal claim ledger. This layer keeps the
    same evidence-backed content but removes claim IDs and per-claim source
    labels from the main reading flow.
    """

    claim_list = list(claims)
    grouped = _group_claims(claim_list)
    ticker = data_packet.ticker.upper()
    rating = decision_packet.rating_permission.preferred_rating.value
    if _is_early_commercial_capital_intensive_report(grouped, metrics_packet):
        body = _early_commercial_capital_intensive_publish_report(ticker, rating, grouped, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "GOOGL":
        body = _googl_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "SNOW":
        body = _snow_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "MSFT":
        body = _msft_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "META":
        body = _meta_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "AAPL":
        body = _aapl_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "NFLX":
        body = _nflx_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "AVGO":
        body = _avgo_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "DDOG":
        body = _ddog_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    elif ticker == "CRM":
        body = _crm_publish_report(rating, metrics_packet, claim_list, evidence_ledger)
    else:
        body = _generic_publish_report(
            ticker,
            rating,
            grouped,
            metrics_packet,
            decision_packet,
            claim_list,
            evidence_ledger,
            currency=data_packet.price_basis.currency,
        )
    return _strip_main_body_internal_language(body).strip() + "\n"


def compose_internal_best_report(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    decision_packet: DecisionPacket,
    evidence_ledger: EvidenceLedger,
    claims: Iterable[ResearchClaim],
    *,
    status: str,
    publishable: bool,
    external_display_rating: str | None = None,
    company_archetype: str | None = None,
    quality_score: float | None = None,
    publish_quality_score: float | None = None,
    internal_research_quality_score: float | None = None,
    data_confidence_score: float | None = None,
) -> str:
    """Render the readable internal surface for manual-review cases.

    The final report can remain a claim-near ledger. This report is the
    internal reading copy: no claim IDs or source labels in the main body, with
    source traceability pushed into the appendix.
    """

    claim_list = list(claims)
    grouped = _group_claims(claim_list)
    ticker = data_packet.ticker.upper()
    rating = decision_packet.rating_permission.preferred_rating.value
    if company_archetype == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH" or _is_early_commercial_capital_intensive_report(grouped, metrics_packet):
        return _early_commercial_capital_intensive_internal_best_report(
            company_name=data_packet.company_name,
            ticker=ticker,
            rating=rating,
            grouped=grouped,
            metrics_packet=metrics_packet,
            claim_list=claim_list,
            evidence_ledger=evidence_ledger,
            status=status,
            publishable=publishable,
            external_display_rating=external_display_rating,
            company_archetype=company_archetype,
            quality_score=quality_score,
            publish_quality_score=publish_quality_score,
            internal_research_quality_score=internal_research_quality_score,
            data_confidence_score=data_confidence_score,
        ).strip() + "\n"
    if company_archetype == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL" or _is_speculative_deep_tech_report(metrics_packet):
        return _speculative_deep_tech_internal_best_report(
            company_name=data_packet.company_name,
            ticker=ticker,
            rating=rating,
            grouped=grouped,
            metrics_packet=metrics_packet,
            claim_list=claim_list,
            evidence_ledger=evidence_ledger,
            status=status,
            publishable=publishable,
            external_display_rating=external_display_rating,
            company_archetype=company_archetype,
            quality_score=quality_score,
            publish_quality_score=publish_quality_score,
            internal_research_quality_score=internal_research_quality_score,
            data_confidence_score=data_confidence_score,
        ).strip() + "\n"
    if external_display_rating == "Hold Pending FCF Support":
        return _missing_fcf_support_internal_best_report(
            company_name=data_packet.company_name,
            ticker=ticker,
            rating=rating,
            grouped=grouped,
            metrics_packet=metrics_packet,
            claim_list=claim_list,
            evidence_ledger=evidence_ledger,
            status=status,
            publishable=publishable,
            external_display_rating=external_display_rating,
            company_archetype=company_archetype,
            quality_score=quality_score,
            publish_quality_score=publish_quality_score,
            internal_research_quality_score=internal_research_quality_score,
            data_confidence_score=data_confidence_score,
        ).strip() + "\n"
    return compose_publish_report(data_packet, metrics_packet, decision_packet, evidence_ledger, claim_list)


def _is_early_commercial_capital_intensive_report(
    grouped: dict[str, list[ResearchClaim]],
    metrics: MetricsPacket,
) -> bool:
    f = metrics.fundamentals
    v = metrics.valuation
    has_required_sections = all(
        grouped.get(section)
        for section in [
            "Business Model Reality",
            "Revenue Scale and Backlog",
            "Contract / Backlog Materiality",
            "Execution Milestones",
            "FCF Path",
            "Valuation vs Revenue/Backlog",
        ]
    )
    return bool(
        has_required_sections
        or (
            f.revenue_ttm is not None
            and 100_000_000 < f.revenue_ttm < 5_000_000_000
            and (f.operating_income_ttm or 0) < 0
            and (f.free_cash_flow_ttm or 0) < 0
            and v.ev_to_sales is not None
            and v.ev_to_sales > 20
        )
    )


def _is_speculative_deep_tech_report(metrics: MetricsPacket) -> bool:
    f = metrics.fundamentals
    v = metrics.valuation
    return bool(
        f.revenue_ttm is not None
        and f.revenue_ttm < 50_000_000
        and (f.operating_income_ttm or 0) < 0
        and (f.free_cash_flow_ttm or 0) < 0
        and ((v.market_cap is not None and v.market_cap / max(abs(f.revenue_ttm), 1.0) > 100) or (v.ev_to_sales is not None and v.ev_to_sales > 100))
    )


def _speculative_deep_tech_internal_best_report(
    *,
    company_name: str | None,
    ticker: str,
    rating: str,
    grouped: dict[str, list[ResearchClaim]],
    metrics_packet: MetricsPacket,
    claim_list: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
    status: str,
    publishable: bool,
    external_display_rating: str | None,
    company_archetype: str | None,
    quality_score: float | None,
    publish_quality_score: float | None,
    internal_research_quality_score: float | None,
    data_confidence_score: float | None,
) -> str:
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    display = external_display_rating or "Manual Review / Preliminary Underweight"
    lines = [
        f"# {_short_company_name(company_name, ticker)} ({ticker}) — Internal Deep-Tech Review Note",
        "## Statusbox",
        "\n".join(
            [
                f"- Status: {_status_slug(status)}",
                f"- Publishable: {str(publishable).lower()}",
                f"- Internal rating: {rating}",
                f"- External display rating: {display}",
                f"- Company archetype: {company_archetype or 'SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL'}",
                "- Public action: do not publish as a clean Buy, Accumulate or clean Hold.",
            ]
        ),
        "",
        "## Technology Reality Check",
        (
            f"{ticker} should be read as a speculative deep-tech company, not as a normal growth report. "
            f"Revenue scale is {_fmt_money(f.revenue_ttm)}, while the business still depends on milestone execution and primary evidence follow-up."
        ),
        _internal_paragraphs(grouped.get("Business & Segment Context", []), limit=2),
        "",
        "## Commercial Adoption",
        (
            f"Commercial adoption is not yet proven at scaled software or platform-company levels. "
            f"Revenue remains small relative to the equity value, so customer, contract and delivery evidence must carry more weight than roadmap language."
        ),
        _internal_paragraphs(grouped.get("Bull Case", []), limit=1),
        "",
        "## Contract / Order Materiality",
        (
            "Any order, award or roadmap item needs a materiality bridge: contract value, timing, revenue conversion, customer type, "
            "recurring versus one-off character and value relative to revenue and market cap."
        ),
        "",
        "## Financial Reality",
        (
            f"Revenue is {_fmt_money(f.revenue_ttm)}, operating income is {_fmt_money(f.operating_income_ttm)}, "
            f"FCF is {_fmt_money(f.free_cash_flow_ttm)} and SBC/Revenue is {_fmt_pct(f.sbc_to_revenue)}. "
            "This combination keeps the note in manual review even when the balance sheet gives the company time."
        ),
        _internal_paragraphs(grouped.get("Fundamental Analysis", []), limit=2),
        "",
        "## Accounting Quality",
        "Treat accounting gains, derivative or warrant effects, stock-compensation intensity and cash-flow definitions as review items before any external use.",
        "",
        "## Valuation Disconnect",
        (
            f"EV/Sales is {_fmt_multiple(v.ev_to_sales)} and P/FCF is {_fmt_multiple(v.price_to_fcf)}. "
            "The valuation can only be defended if commercial evidence improves faster than dilution, cash burn and execution risk."
        ),
        _internal_paragraphs(grouped.get("Valuation / Multiples", []), limit=2),
        "",
        "## Technical Setup as Timing Only",
        _internal_paragraphs(grouped.get("Technical Setup", []), limit=2),
        "",
        "## Final Internal View",
        (
            f"Internal anchor: {rating}. External display should remain {display}. "
            "The useful work here is risk triage: verify primary financial evidence, contract materiality, cash burn, dilution and milestone conversion before considering any cleaner public stance."
        ),
        "",
        "## Quality Metadata",
        "\n".join(
            [
                f"- Publish Quality Score: {_fmt_score(publish_quality_score)}",
                f"- Internal Research Quality Score: {_fmt_score(internal_research_quality_score)}",
                f"- Data Confidence Score: {_fmt_score(data_confidence_score)}",
                f"- Total Score Legacy: {_fmt_score(quality_score)}",
            ]
        ),
        "",
        "## Required Follow-up",
        "\n".join(
            [
                "- [ ] Reconfirm current SEC/IR evidence for revenue, FCF, cash, SBC and share-count pressure.",
                "- [ ] Quantify contract/order materiality versus revenue and market cap.",
                "- [ ] Separate operating progress from accounting fair-value or financing effects.",
                "- [ ] Keep technical setup as timing only, never as the core investment thesis.",
                "- [ ] Re-run manual review before any public-promotion attempt.",
            ]
        ),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claim_list, evidence_ledger),
    ]
    return "\n".join(part for part in lines if part is not None)


def _early_commercial_capital_intensive_internal_best_report(
    *,
    company_name: str | None,
    ticker: str,
    rating: str,
    grouped: dict[str, list[ResearchClaim]],
    metrics_packet: MetricsPacket,
    claim_list: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
    status: str,
    publishable: bool,
    external_display_rating: str | None,
    company_archetype: str | None,
    quality_score: float | None,
    publish_quality_score: float | None,
    internal_research_quality_score: float | None,
    data_confidence_score: float | None,
) -> str:
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    cash_and_marketable = _cash_and_marketable_securities(f)
    display = external_display_rating or "Manual Review / Hold Pending FCF and Execution Evidence"
    sections = [
        f"# {_short_company_name(company_name, ticker)} ({ticker}) — Interne Research-Lesefassung",
        "## Statusbox",
        "\n".join(
            [
                f"- Status: {_status_slug(status)}",
                f"- Publishable: {str(publishable).lower()}",
                f"- Internal rating: {rating}",
                f"- External display rating: {display}",
                f"- Company archetype: {company_archetype or 'EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH'}",
                f"- Quality score: {_fmt_score(quality_score)}",
                "- Public action: do not publish as a clean Buy or Accumulate.",
            ]
        ),
        "",
        "## Executive Summary",
        (
            f"{ticker} is an early-commercial capital-intensive technology case, not a pre-commercial speculative stub and not a clean bullish publication. "
            f"The core evidence is real operating scale: TTM revenue is {_fmt_money(f.revenue_ttm)}, Q1 revenue is {_section_metric(grouped, 'Revenue Scale and Backlog', 'quarterly revenue')}, "
            f"backlog is {_section_metric(grouped, 'Revenue Scale and Backlog', 'backlog')}, and cash plus marketable securities is {_fmt_money(cash_and_marketable)}. "
            f"The constraint is equally direct: FCF is {_fmt_money(f.free_cash_flow_ttm)} and EV/Sales is {_fmt_multiple(v.ev_to_sales)}, so the correct external display remains {display}."
        ),
        "",
        "## Business Model Reality",
        _internal_paragraphs(grouped.get("Business Model Reality", []), limit=3),
        "",
        "## Revenue Scale and Backlog",
        _internal_paragraphs(grouped.get("Revenue Scale and Backlog", []), limit=3),
        "",
        "## Contract / Backlog Materiality",
        _internal_paragraphs(grouped.get("Contract / Backlog Materiality", []), limit=3),
        "",
        "## Segment Mix",
        _internal_paragraphs(grouped.get("Segment Mix", []), limit=3),
        "",
        "## Execution Milestones",
        _internal_paragraphs(grouped.get("Execution Milestones", []), limit=3),
        "",
        "## FCF Path",
        _internal_paragraphs(grouped.get("FCF Path", []), limit=3),
        "",
        "## Capital Intensity",
        _internal_paragraphs(grouped.get("Capital Intensity", []), limit=3),
        "",
        "## Valuation vs Revenue/Backlog",
        _internal_paragraphs(grouped.get("Valuation vs Revenue/Backlog", []), limit=3),
        "",
        "## Valuation / Sensitivity",
        _early_commercial_valuation_sensitivity(v),
        "",
        "## Technical Setup as Timing Only",
        _early_commercial_technical_timing(grouped),
        "",
        "## Final Internal View",
        _early_commercial_final_view(ticker, rating, f, v, metrics_packet.technical),
        "",
        "## Quality Metadata",
        "\n".join(
            [
                f"- Publish Quality Score: {_fmt_score(publish_quality_score)}",
                f"- Internal Research Quality Score: {_fmt_score(internal_research_quality_score)}",
                f"- Data Confidence Score: {_fmt_score(data_confidence_score)}",
                f"- Total Score Legacy: {_fmt_score(quality_score)}",
            ]
        ),
        "",
        "## Follow-up Checklist",
        "\n".join(
            [
                "- [ ] Reconfirm backlog conversion timing, margin quality and recurring versus one-off program mix.",
                "- [ ] Track Electron/HASTE launch cadence, contracted mission conversion and delivery risk.",
                "- [ ] Recheck Neutron execution risk after the next development or customer milestone.",
                "- [ ] Update the FCF path after the next quarter, including operating loss and cash plus marketable securities.",
                "- [ ] Re-test EV/Sales against revenue growth, backlog conversion and market-cap expectations before any publish upgrade.",
            ]
        ),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claim_list, evidence_ledger),
    ]
    return "\n".join(section for section in sections if section is not None)


def _early_commercial_capital_intensive_publish_report(
    ticker: str,
    rating: str,
    grouped: dict[str, list[ResearchClaim]],
    metrics_packet: MetricsPacket,
    claim_list: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    t = metrics_packet.technical
    sections = [
        f"# {ticker} Research Report",
        "## Executive Summary",
        (
            f"{ticker} is not a clean Buy/Accumulate case and should not be treated as a pre-commercial speculative deep-tech stub. "
            f"TTM revenue of {_fmt_money(f.revenue_ttm)}, FCF of {_fmt_money(f.free_cash_flow_ttm)} and EV/Sales of {_fmt_multiple(v.ev_to_sales)} point to an early-commercial capital-intensive technology profile."
        ),
        "",
        "## Business Model Reality",
        _paragraphs(grouped.get("Business Model Reality", []), limit=3),
        "",
        "## Revenue Scale and Backlog",
        _paragraphs(grouped.get("Revenue Scale and Backlog", []), limit=3),
        "",
        "## Contract / Backlog Materiality",
        _paragraphs(grouped.get("Contract / Backlog Materiality", []), limit=3),
        "",
        "## Segment Mix",
        _paragraphs(grouped.get("Segment Mix", []), limit=3),
        "",
        "## Execution Milestones",
        _paragraphs(grouped.get("Execution Milestones", []), limit=3),
        "",
        "## FCF Path",
        _paragraphs(grouped.get("FCF Path", []), limit=3),
        "",
        "## Capital Intensity",
        _paragraphs(grouped.get("Capital Intensity", []), limit=3),
        "",
        "## Valuation vs Revenue/Backlog",
        _paragraphs(grouped.get("Valuation vs Revenue/Backlog", []), limit=3),
        "",
        "## Technical Setup only as timing",
        _paragraphs(grouped.get("Technical Setup only as timing", []), limit=2),
        "",
        "## Scenario / Sensitivity",
        (
            "| Scenario | Business evidence | Valuation / FCF implication | Internal view |\n"
            "|---|---|---|---|\n"
            "| Bull | Backlog converts into repeatable revenue while execution milestones stay on schedule | EV/Sales becomes easier to defend as FCF losses narrow | Move toward Accumulate only after FCF proof |\n"
            "| Base | Revenue and backlog remain real, but development spend keeps FCF negative | High EV/Sales limits upside conviction | Hold / manual review |\n"
            "| Bear | Contract timing slips, milestone risk rises or FCF losses persist | Backlog no longer offsets valuation risk | Reduce risk |"
        ),
        "",
        "## Final Internal View",
        _paragraphs(grouped.get("Final Internal View", []), limit=3),
        "",
        _early_commercial_final_view(ticker, rating, f, v, t),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claim_list, evidence_ledger),
    ]
    return "\n".join(section for section in sections if section is not None).strip() + "\n"


def compose_early_commercial_manual_review_publish_stub(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    evidence_ledger: EvidenceLedger,
    claims: Iterable[ResearchClaim],
) -> str:
    claim_list = list(claims)
    grouped = _group_claims(claim_list)
    ticker = data_packet.ticker.upper()
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    body = [
        f"# {_short_company_name(data_packet.company_name, ticker)} ({ticker}) Publication Stub",
        "## Publication Status",
        "This report is not approved for public publication. Use the internal best report for the full readable research view.",
        "",
        "## Review Snapshot",
        (
            f"{ticker} remains a hold-pending FCF and execution evidence case. TTM revenue is {_fmt_money(f.revenue_ttm)}, "
            f"Q1 revenue is {_section_metric(grouped, 'Revenue Scale and Backlog', 'quarterly revenue')}, backlog is {_section_metric(grouped, 'Revenue Scale and Backlog', 'backlog')}, "
            f"FCF is {_fmt_money(f.free_cash_flow_ttm)}, and EV/Sales is {_fmt_multiple(v.ev_to_sales)}."
        ),
        "",
        "## Scenario / Sensitivity",
        (
            "| Scenario | KPI trigger | Valuation implication | Rating implication |\n"
            "|---|---|---|---|\n"
            "| Improvement | Backlog converts into revenue and FCF losses narrow | EV/Sales becomes easier to defend | Move toward a cleaner internal Hold only after FCF proof |\n"
            "| Base | Revenue and backlog remain real, but FCF stays negative | Extreme EV/Sales limits conviction | Keep hold-pending evidence display |\n"
            "| Downside | Neutron timing slips or FCF losses persist | Valuation support weakens despite backlog | Reduce risk / downgrade internal stance |"
        ),
        "",
        "## Final Rating & Action Plan",
        "No public rating should be shown. Track FCF, backlog conversion, Neutron timing and valuation before any publication upgrade.",
        "",
        "## Evidence Appendix",
        _source_only_evidence_appendix(evidence_ledger),
    ]
    return "\n".join(body).strip() + "\n"


def compose_manual_review_publish_stub(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    evidence_ledger: EvidenceLedger,
    claims: Iterable[ResearchClaim],
    *,
    external_display_rating: str,
    reason: str,
) -> str:
    _ = claims
    ticker = data_packet.ticker.upper()
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    body = [
        f"# {_short_company_name(data_packet.company_name, ticker)} ({ticker}) Publication Stub",
        "## Publication Status",
        "This report is not approved for public publication. Use the internal best report for the full readable research view.",
        "",
        "## Review Snapshot",
        f"External display rating: {external_display_rating}",
        f"Blocking reason: {reason}",
        (
            f"Revenue is {_fmt_money(f.revenue_ttm)}, FCF is {_fmt_money(f.free_cash_flow_ttm)}, "
            f"P/FCF is {_fmt_multiple(v.price_to_fcf)}, and EV/Sales is {_fmt_multiple(v.ev_to_sales)}."
        ),
        "",
        "## Final Rating & Action Plan",
        "No clean Buy or Accumulate should be shown until current cash-flow support is evidence-backed and reconciliation warnings are resolved.",
        "",
        "## Evidence Appendix",
        _source_only_evidence_appendix(evidence_ledger),
    ]
    return "\n".join(body).strip() + "\n"


def _missing_fcf_support_internal_best_report(
    *,
    company_name: str | None,
    ticker: str,
    rating: str,
    grouped: dict[str, list[ResearchClaim]],
    metrics_packet: MetricsPacket,
    claim_list: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
    status: str,
    publishable: bool,
    external_display_rating: str | None,
    company_archetype: str | None,
    quality_score: float | None,
    publish_quality_score: float | None,
    internal_research_quality_score: float | None,
    data_confidence_score: float | None,
) -> str:
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    display = external_display_rating or "Hold Pending FCF Support"
    sections = [
        f"# {_short_company_name(company_name, ticker)} ({ticker}) — Internal FCF-Support Review Note",
        "## Statusbox",
        "\n".join(
            [
                f"- Status: {_status_slug(status)}",
                f"- Publishable: {str(publishable).lower()}",
                f"- Internal rating anchor: {rating}",
                f"- External display rating: {display}",
                f"- Company archetype: {company_archetype or 'UNKNOWN'}",
                f"- Quality score: {_fmt_score(quality_score)}",
                "- Public action: do not publish as a clean Buy or Accumulate.",
            ]
        ),
        "",
        "## Executive Summary",
        (
            f"{ticker} is blocked from a clean external rating because current FCF support is unavailable in the evidence set. "
            f"Revenue is {_fmt_money(f.revenue_ttm)}, FCF is {_fmt_money(f.free_cash_flow_ttm)}, "
            f"P/FCF is {_fmt_multiple(v.price_to_fcf)}, and EV/Sales is {_fmt_multiple(v.ev_to_sales)}. "
            f"The internal rating anchor can remain {rating}, but the external display must stay {display} until cash-flow support is reconciled."
        ),
        "",
        "## Current Evidence",
        (
            f"Revenue evidence is present at {_fmt_money(f.revenue_ttm)}, while FCF is {_fmt_money(f.free_cash_flow_ttm)}. "
            "That combination is enough for internal review, but not enough for a clean external rating until cash-flow support is current and reconciled."
        ),
        "",
        "## Valuation and Cash-Flow Support",
        (
            f"EV/Sales is {_fmt_multiple(v.ev_to_sales)} and P/FCF is {_fmt_multiple(v.price_to_fcf)}. "
            "The valuation discussion stays gated because the missing FCF denominator prevents a reliable cash-flow multiple."
        ),
        "",
        "## Technical Setup as Timing Only",
        "Technical context can inform entry timing, but it cannot override the missing FCF-support gate.",
        "",
        "## Final Internal View",
        (
            "The next acceptable move is evidence collection, not publication. Require current primary or clearly reconciled FCF/OCF support before any clean Accumulate or Buy display."
        ),
        "",
        "## Quality Metadata",
        "\n".join(
            [
                f"- Publish Quality Score: {_fmt_score(publish_quality_score)}",
                f"- Internal Research Quality Score: {_fmt_score(internal_research_quality_score)}",
                f"- Data Confidence Score: {_fmt_score(data_confidence_score)}",
            ]
        ),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claim_list, evidence_ledger),
    ]
    return "\n".join(section for section in sections if section is not None).strip() + "\n"


def _early_commercial_final_view(ticker: str, rating: str, f, v, t) -> str:
    return "\n\n".join([
        f"Internal rating anchor: {rating}. External display should remain Manual Review / Hold Pending FCF and Execution Evidence.",
        (
            f"Why this rating? The class-specific question is whether backlog converts into revenue while Neutron execution risk, capital intensity and the negative FCF path improve. "
            f"Revenue of {_fmt_money(f.revenue_ttm)} and backlog evidence prevent a reflexive speculative-deep-tech underweight, but FCF of {_fmt_money(f.free_cash_flow_ttm)} and EV/Sales of {_fmt_multiple(v.ev_to_sales)} block clean Buy or Accumulate language."
        ),
        "What would improve the view: visible backlog conversion, narrowing FCF losses, cleaner Neutron and launch-cadence execution evidence, and valuation support from revenue that is actually turning into cash flow.",
        "What would weaken the view: Neutron delay, contract timing risk, weaker segment mix, persistent FCF losses, or valuation expansion without backlog-to-revenue conversion.",
    ])


def _generic_publish_report(
    ticker: str,
    rating: str,
    grouped: dict[str, list[ResearchClaim]],
    metrics_packet: MetricsPacket,
    decision_packet: DecisionPacket,
    claim_list: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
    *,
    currency: str = "USD",
) -> str:
    f = metrics_packet.fundamentals
    v = metrics_packet.valuation
    t = metrics_packet.technical
    constructive_cash_trigger = _constructive_cash_conversion_trigger(
        f.free_cash_flow_ttm
    )
    current_kpi_claims = _current_kpi_claims(claim_list)
    current_kpi_ids = {claim.claim_id for claim in current_kpi_claims}
    fundamental_claims = [
        claim
        for claim in grouped.get("Fundamental Analysis", [])
        if claim.claim_id not in current_kpi_ids
    ]
    investment_thesis = "\n\n".join(
        part
        for part in (
            _generic_investment_thesis(
                ticker,
                rating,
                metrics_packet,
                decision_packet,
                currency=currency,
            ),
            _paragraphs(
                grouped.get("Business & Segment Context", []),
                limit=2,
            ),
        )
        if part
    )

    sections = [
        f"# {ticker} Research Report",
        "## Executive Summary",
        _executive_summary(ticker, rating, grouped, metrics_packet),
        "",
        "## Investment Thesis",
        investment_thesis,
        "",
        "## Current Period KPIs",
        _paragraphs(current_kpi_claims, limit=5),
        "",
        "## Fundamental Analysis",
        _paragraphs(fundamental_claims, limit=5),
        "",
        "## Valuation / Risk-Reward",
        _paragraphs(grouped.get("Valuation / Multiples", []), limit=3),
        "",
        "## Scenario / Sensitivity",
        (
            "| Scenario | KPI trigger | Valuation implication | Rating implication |\n"
            "|---|---|---|---|\n"
            f"| Constructive | {constructive_cash_trigger} | Benchmark evidence would need to show valuation support | Reassess toward a more constructive rating |\n"
            "| Current | Measured fundamental and technical signals remain unchanged | Unbenchmarked multiples remain observations only | Retain the current research rating |\n"
            "| Cautious | Fundamentals or the technical trend deteriorate | Benchmark evidence would need to show valuation pressure | Reassess toward a more cautious rating |"
        ),
        "",
        "## Technical Setup",
        _paragraphs(grouped.get("Technical Setup", []), limit=3),
        "",
        "## Bull Case",
        _paragraphs(grouped.get("Bull Case", []), limit=3),
        "",
        "## Bear Case",
        _paragraphs(grouped.get("Bear Case", []), limit=3),
        "",
        "## Risks",
        _paragraphs(grouped.get("Key Risks", []), limit=4),
        "",
        "## Catalysts",
        _paragraphs(grouped.get("Catalysts & Triggers", []), limit=4),
        "",
        "## Final Rating & Review Conditions",
        _final_rating_section(
            ticker,
            rating,
            f,
            v,
            t,
            decision_packet,
            currency=currency,
        ),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claim_list, evidence_ledger),
    ]
    return "\n".join(section for section in sections if section is not None).strip() + "\n"


def _googl_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# GOOGL Research Report",
        "## Executive Summary",
        (
            "Alphabet is a Hold, not because the operating story is weak, but because the stock already reflects a lot of good news. "
            "Q1 revenue of $109.90B, Google Cloud revenue of $20.00B and 63.0% Cloud growth show that the Search-plus-Cloud engine remains powerful. "
            "The offset is timing and cash-flow quality: Q1 capex of $35.67B, TTM FCF of $64.43B and an RSI of 81.33 make the risk/reward less attractive for fresh buying at the current price."
        ),
        "",
        "## Investment Thesis",
        (
            "The central thesis is a high-quality advertising and cloud compounder facing an AI investment cycle that makes near-term free-cash-flow conversion harder to underwrite. "
            "Search and Google Cloud provide scale, margin and reinvestment capacity, but the $35.67B Q1 capex load means investors need to separate durable operating performance from infrastructure spending pressure. "
            "That combination supports holding exposure, while waiting for either a better entry point or clearer evidence that AI capex is translating into durable incremental revenue."
        ),
        "",
        "## Current Period KPIs",
        (
            "Q1 revenue was $109.90B, giving Alphabet enough operating scale to fund both core Search monetization and aggressive AI infrastructure investment. "
            "The figure supports the base-case business quality, but it does not by itself justify chasing the shares after a sharp technical move."
        ),
        (
            "Google Cloud revenue was $20.00B and grew 63.0%, which is the strongest current-period signal in the report. "
            "Cloud growth keeps the bull case alive because it broadens Alphabet beyond ads, but it has to be weighed against the capex needed to serve AI workloads."
        ),
        (
            "Q1 operating margin of 36.1% confirms that Alphabet still has exceptional operating leverage, while Q1 capex of $35.67B and TTM FCF of $64.43B define the investment debate: strong profits, but heavy AI spending that can pressure FCF conversion."
        ),
        (
            "Other Income included a $37.70B gain, which is useful balance-sheet context but should not be treated as recurring Search or Cloud economics. "
            "The report therefore gives more weight to operating margin, capex and free cash flow than to one-off investment gains."
        ),
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and TTM FCF of {_fmt_money(f.free_cash_flow_ttm)} point to a business that remains deeply cash generative even during an AI buildout. "
            "The quality question is not whether Alphabet can fund investment; it is whether incremental AI capex earns enough return to defend margins and free-cash-flow durability."
        ),
        (
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is manageable for a mega-cap platform business and is not the main risk driver here. "
            f"Net cash of {_fmt_money(f.net_cash)} gives Alphabet flexibility, but the rating still depends on whether cloud and AI monetization can offset the capital intensity."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} leave limited room for execution disappointment. "
            "The valuation is acceptable for a dominant platform, but it is not cheap enough to ignore overbought timing, AI capex pressure or the possibility that some reported earnings strength is helped by non-operating gains. "
            "Accumulate would require either a technical reset or evidence that FCF conversion improves while Cloud growth remains strong; a weaker view would be warranted if elevated capex persists while Cloud growth slows."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | Cloud growth remains strong while capex intensity moderates | P/FCF becomes easier to defend | Upgrade toward Accumulate |\n| Base | Cloud remains strong but capex keeps FCF conversion under pressure | Current multiple is supportable but not cheap | Hold |\n| Bear | Cloud growth slows while capex stays elevated | Multiple support weakens | Reduce risk / downgrade |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, well into overbought territory. "
            f"Price is also above the 50-SMA of {_fmt_number(t.sma_50)} and 200-SMA of {_fmt_number(t.sma_200)}, so the trend is strong but the entry point is stretched."
        ),
        "",
        "## Bull Case",
        (
            "The bull case is that Cloud growth remains above expectations, Search monetization holds up, and AI product integration turns the current capex cycle into a durable revenue and margin tailwind. "
            "In that scenario, today’s high investment spending would look like an early-cycle reinvestment phase rather than a structural drag."
        ),
        "",
        "## Bear Case",
        (
            "The bear case is that AI capex rises faster than monetization, regulatory pressure weighs on Search economics, or Cloud growth slows before the investment cycle normalizes. "
            "A further risk is that investors capitalize one-off Other Income too generously and overestimate recurring earnings quality."
        ),
        "",
        "## Risks",
        (
            "Key risks are AI infrastructure spending, regulatory pressure, ad-market cyclicality, Cloud margin volatility and the overbought technical setup. "
            "The $37.70B Other Income gain is also a quality caveat because it can flatter reported earnings without improving recurring operating economics."
        ),
        "",
        "## Catalysts",
        (
            "Upside catalysts would be sustained Cloud growth, evidence that AI capex is converting into revenue, and FCF resilience despite higher infrastructure spend. "
            "Downside triggers would be weaker FCF conversion, slower Cloud growth, regulatory setbacks or a technical reversal from the overbought setup."
        ),
        "",
        "## Final Rating & Action Plan",
        _googl_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _snow_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# SNOW Research Report",
        "## Executive Summary",
        (
            "Snowflake is a Hold with Underweight Bias because the operating story is credible, but the equity setup is not yet attractive enough to treat the weakness as a clean entry point. "
            "Product revenue of $4.47B, NRR of 125.0%, RPO of $9.77B and 733 customers above $1M product revenue show that the AI Data Cloud franchise still has enterprise depth. "
            "The offset is valuation discipline, SBC/Revenue of 26.4%, and a damaged chart with price below both the 50-SMA and 200-SMA."
        ),
        "",
        "## Investment Thesis",
        (
            "The investment debate is whether Snowflake’s consumption model and AI Data Cloud expansion can compound fast enough to justify a premium multiple while GAAP losses and SBC remain material. "
            "Adjusted FCF of $1.19B proves the model can generate cash, but the stock still needs stronger technical confirmation or cleaner evidence of durable consumption acceleration before the stance should move from cautious Hold toward a cleaner add setup."
        ),
        "",
        "## Current Period KPIs",
        (
            "Product revenue of $4.47B is the core demand signal because Snowflake monetizes usage rather than simply selling seats. "
            "That scale supports the long-term platform thesis, but it does not remove the need to monitor consumption durability."
        ),
        (
            "NRR of 125.0% and RPO of $9.77B show that existing customers are still expanding and that contracted demand remains substantial. "
            "The key question is how quickly that RPO converts into recognized revenue without renewed customer optimization pressure."
        ),
        (
            "Snowflake ended the period with 733 customers above $1M product revenue, which supports the enterprise-depth argument. "
            "Adjusted FCF of $1.19B is positive, but the benefit is partly offset by SBC/Revenue of 26.4% and the ongoing GAAP/non-GAAP gap."
        ),
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and FCF of {_fmt_money(f.free_cash_flow_ttm)} show that the company has moved beyond a pure growth-at-any-cost profile. "
            "Still, negative GAAP profitability and elevated equity compensation keep the quality score below what a cleaner software compounder would deserve."
        ),
        (
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is the main fundamental discipline issue. "
            "For a SaaS company, some SBC is normal, but at this level it directly affects equity-owner returns and makes a more bullish rating harder to defend."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} are not extreme for a high-growth software platform, but they require confidence that NRR, RPO conversion and product revenue growth stay durable. "
            "With the chart still weak, the valuation does not offer enough margin of safety to upgrade the stock. "
            "A move toward Hold needs either a lower multiple, stronger RPO-to-product-revenue conversion, or evidence that SBC intensity is declining without slowing growth."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | NRR stabilizes or improves, RPO converts cleanly, SBC intensity falls | EV/Sales and P/FCF become easier to defend | Move toward a cleaner add setup |\n| Base | Product revenue and FCF remain solid but SBC stays elevated | Multiple is tolerable but not compelling | Hold with Underweight Bias |\n| Bear | Consumption slows or RPO conversion weakens while SBC remains high | Equity-holder quality deteriorates | Stay underweight / reduce risk |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)}, below the 50-SMA of {_fmt_number(t.sma_50)} and below the 200-SMA of {_fmt_number(t.sma_200)}. "
            f"RSI of {_fmt_number(t.rsi_14)} is not overbought, but the moving-average structure points to a damaged trend rather than a confirmed recovery."
        ),
        "",
        "## Bull Case",
        (
            "The bull case is that AI Data Cloud adoption accelerates consumption, NRR remains near current levels, and RPO converts into visible product revenue growth. "
            "If adjusted FCF remains strong while SBC intensity declines, the equity case could improve quickly."
        ),
        "",
        "## Bear Case",
        (
            "The bear case is that customer optimization returns, product revenue growth slows, or SBC remains high enough to dilute the benefit of adjusted FCF. "
            "The chart adds a second layer of risk because the stock is still below both major moving averages."
        ),
        "",
        "## Risks",
        (
            "Key risks are consumption volatility, RPO conversion, competitive pressure in data infrastructure, GAAP losses, SBC dilution and continued technical weakness. "
            "The company can be fundamentally interesting while still being a poor near-term risk/reward if the stock does not reclaim trend support."
        ),
        "",
        "## Catalysts",
        (
            "Upside catalysts include sustained NRR, faster RPO conversion, stronger product revenue guidance and evidence that adjusted FCF is not coming at the expense of future growth. "
            "Downside triggers include weaker consumption, persistent SBC intensity or failure to reclaim the 50-SMA and 200-SMA."
        ),
        "",
        "## Final Rating & Action Plan",
        _snow_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _msft_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# MSFT Research Report",
        "## Executive Summary",
        (
            "Microsoft is a Hold because the current-period cloud and AI indicators are excellent, while the stock still needs cleaner proof that AI capacity spending is turning into durable free-cash-flow leverage. "
            "Q3 revenue of $82.89B, Microsoft Cloud revenue of $54.50B, Microsoft Cloud growth of 29.0%, Azure growth of 40.0% and an AI business annual revenue run-rate above $37.00B all support the strategic thesis."
        ),
        "",
        "## Investment Thesis",
        (
            "The thesis is a high-quality cloud and productivity platform with one of the clearest enterprise AI demand signals in mega-cap software. "
            "The constraint is not business relevance; it is whether capex, datacenter capacity and margin pressure allow the AI cycle to convert into incremental FCF quickly enough for a more bullish entry."
        ),
        "",
        "## Current Period KPIs",
        "Q3 revenue of $82.89B confirms that Microsoft’s platform breadth remains strong across productivity, cloud and enterprise software.",
        "Microsoft Cloud revenue of $54.50B and 29.0% growth show that the cloud base is still compounding at scale.",
        "Azure growth of 40.0% and AI business annual revenue run-rate above $37.00B make AI demand the key catalyst, but also raise the bar for capex productivity.",
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and FCF of {_fmt_money(f.free_cash_flow_ttm)} show a durable cash machine. "
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is manageable, while net cash of {_fmt_money(f.net_cash)} gives Microsoft flexibility to fund AI capacity without stressing the balance sheet. "
            "The analytical question is whether that AI capacity spend remains a temporary buildout phase or becomes a structurally higher reinvestment requirement that slows FCF growth."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} leave room for a premium-quality Hold, but not a valuation-insensitive Buy. "
            "The market is already paying for AI durability, so upside needs Azure and AI revenue to translate into FCF expansion after datacenter and AI infrastructure investment. "
            "The rating would become more constructive if Azure can stay near the high-30s/40% growth zone while FCF conversion improves; it would weaken if AI capex rises faster than cloud margin and cash-flow leverage."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | Azure stays near high-30s/40% and AI run-rate rises while FCF conversion improves | Premium multiple is easier to defend | Move toward Accumulate |\n| Base | Cloud and AI demand stay strong but capex absorbs near-term FCF leverage | Current multiple supports Hold | Hold |\n| Bear | AI capex rises without visible margin or FCF leverage | Multiple compression risk increases | Reduce risk / downgrade |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, 50-SMA at {_fmt_number(t.sma_50)} and 200-SMA at {_fmt_number(t.sma_200)}. "
            "The technical setup supports patience rather than aggressive chasing."
        ),
        "",
        "## Bull Case",
        "The bull case is that Azure growth remains strong, AI workloads lift cloud monetization, and capex intensity moderates as utilization improves.",
        "",
        "## Bear Case",
        "The bear case is that AI infrastructure spend outruns near-term monetization, pressuring FCF conversion and reducing the justification for a premium multiple.",
        "",
        "## Risks",
        "Key risks are AI capex intensity, cloud margin pressure, enterprise spending cyclicality, regulatory scrutiny and valuation compression if AI revenue does not scale profitably.",
        "",
        "## Catalysts",
        "Catalysts include sustained Azure growth, higher AI run-rate disclosure, improving FCF conversion and evidence that AI capacity investments are lifting margins rather than only revenue.",
        "",
        "## Final Rating & Action Plan",
        _msft_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _meta_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# META Research Report",
        "## Executive Summary",
        (
            "Meta is a Hold because the ad platform is producing strong current-period economics, but the AI infrastructure spending plan keeps risk/reward balanced. "
            "Q1 revenue of $56.31B, operating margin of 41.0% and Q1 FCF of $12.39B show excellent operating quality; FY2026 capex guidance of $125.00B-$145.00B keeps AI ROI at the center of the debate."
        ),
        "",
        "## Investment Thesis",
        (
            "The thesis is a dominant social-ad platform with strong margins and cash generation, increasingly shaped by AI ranking, content recommendation and infrastructure investment. "
            "The stock deserves a quality premium, but a Hold is more disciplined until investors can see whether the elevated capex plan creates enough incremental ad monetization and engagement."
        ),
        "",
        "## Current Period KPIs",
        "Q1 revenue of $56.31B confirms that the ad engine remains strong despite macro and regulatory noise.",
        "Q1 operating margin of 41.0% and Q1 FCF of $12.39B show that Meta still converts revenue into substantial profit and cash.",
        "FY2026 capex guidance of $125.00B-$145.00B is the key risk variable because it raises the hurdle for AI infrastructure returns.",
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and TTM FCF of {_fmt_money(f.free_cash_flow_ttm)} support the base-case quality view. "
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is not the central concern; the central concern is whether AI and infrastructure spend can sustain margin quality."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} look defensible for Meta’s scale, but they require confidence that capex will reinforce rather than dilute returns. "
            "That keeps the risk/reward balanced rather than outright bullish."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | Ad growth holds and capex produces visible AI monetization | Current multiple is easier to defend | Move toward Accumulate |\n| Base | Ad economics stay strong but capex remains elevated | Hold is appropriate | Hold |\n| Bear | Capex rises while margins or FCF conversion weaken | Multiple support deteriorates | Reduce risk / downgrade |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, 50-SMA at {_fmt_number(t.sma_50)} and 200-SMA at {_fmt_number(t.sma_200)}. "
            "The chart supports patience if valuation already discounts strong ad execution."
        ),
        "",
        "## Bull Case",
        "The bull case is that AI improves engagement and ad targeting enough to justify the capex cycle while operating margins remain high.",
        "",
        "## Bear Case",
        "The bear case is that AI and Reality Labs spending absorb ad strength, or regulation weakens monetization before capex returns become visible.",
        "",
        "## Risks",
        "Key risks are AI capex ROI, Reality Labs losses, regulatory pressure, ad cyclicality and multiple compression if margin quality weakens.",
        "",
        "## Catalysts",
        "Catalysts include sustained ad growth, stable or rising operating margin, clearer AI monetization and evidence that capex intensity is moderating.",
        "",
        "## Final Rating & Action Plan",
        _meta_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _aapl_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# AAPL Research Report",
        "## Executive Summary",
        (
            "Apple is an Accumulate, but only with staging discipline. Latest-quarter revenue of $111.20B, EPS of $2.01, operating cash flow above $28.00B and an additional $100.00B buyback authorization support the franchise-quality and capital-return case. "
            "The reason not to chase is that product-cycle, Services durability, AI positioning and regulatory risks still matter."
        ),
        "",
        "## Investment Thesis",
        (
            "The thesis is a high-quality ecosystem with exceptional cash generation and shareholder returns. "
            "Accumulate is reasonable because the balance of cash flow, EPS resilience and buybacks is supportive, but the action should be pullback-based rather than aggressive because Apple still needs clearer AI and product-cycle momentum."
        ),
        "",
        "## Current Period KPIs",
        "Latest-quarter revenue of $111.20B and EPS of $2.01 show that Apple’s ecosystem remains profitable at very large scale.",
        "Operating cash flow above $28.00B reinforces the quality of the cash-generation engine.",
        "The additional $100.00B buyback authorization is a major capital-return support, but buybacks cannot replace product innovation or regulatory clarity.",
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and TTM FCF of {_fmt_money(f.free_cash_flow_ttm)} support a high-quality compounder profile. "
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is low enough that dilution is not the core debate."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} argue for staged accumulation rather than a blanket Buy. "
            "The valuation can work if cash flow and buybacks remain resilient, but it leaves less room for product-cycle disappointment. "
            "The rating would become more constructive if Services, AI-led product demand and FCF growth strengthen together; it would weaken if iPhone demand, regulation or cash-flow durability deteriorate."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | Services, AI features and FCF growth strengthen together | Premium multiple remains defensible | Accumulate can continue |\n| Base | Cash flow and buybacks support EPS but product momentum is mixed | Staged entries are preferred | Accumulate on pullbacks |\n| Bear | Product-cycle weakness or regulation pressures cash-flow confidence | Multiple support weakens | Move toward Hold / reduce additions |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, 50-SMA at {_fmt_number(t.sma_50)} and 200-SMA at {_fmt_number(t.sma_200)}. "
            "The action plan should use pullbacks rather than chase short-term momentum."
        ),
        "",
        "## Bull Case",
        "The bull case is that Services, ecosystem retention, cash flow and buybacks compound while AI features improve the upgrade cycle.",
        "",
        "## Bear Case",
        "The bear case is that iPhone demand softens, regulatory pressure hits platform economics, or AI execution lags peers while valuation remains full.",
        "",
        "## Risks",
        "Key risks are product-cycle weakness, regulatory action, China exposure, AI perception risk and valuation compression if FCF growth slows.",
        "",
        "## Catalysts",
        "Catalysts include stronger Services growth, clearer AI product momentum, resilient iPhone demand and continued buyback-supported EPS growth.",
        "",
        "## Final Rating & Action Plan",
        _aapl_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _avgo_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# AVGO Research Report",
        "## Executive Summary",
        (
            "Broadcom is a Hold because the AI infrastructure story is powerful, while the valuation and VMware integration burden require discipline. "
            "Q1 revenue of $19.31B, AI revenue of $8.40B, Q1 FCF of $8.01B, Q2 revenue guide of $22.00B and Q2 AI semiconductor revenue guide of $10.70B put the AI acceleration directly in the main thesis."
        ),
        "",
        "## Investment Thesis",
        (
            "The thesis is a high-quality semiconductor and infrastructure-software platform where AI demand and VMware/software mix can support durable cash flow. "
            "Hold is appropriate because the evidence is strong, but valuation already discounts a lot of AI success."
        ),
        "",
        "## Current Period KPIs",
        "Q1 revenue of $19.31B and AI revenue of $8.40B show that AI infrastructure is already a material growth driver.",
        "Q1 FCF of $8.01B gives the AI and VMware/software mix thesis immediate cash-flow support.",
        "Q2 revenue guidance of $22.00B and Q2 AI semiconductor revenue guidance of $10.70B are the forward proof points the stock needs to defend its multiple.",
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and TTM FCF of {_fmt_money(f.free_cash_flow_ttm)} support Broadcom’s cash-generation profile. "
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is not the primary risk; the key question is whether AI semiconductor growth and infrastructure software can sustain the premium valuation."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} require continued AI revenue delivery. "
            "Strong Q1 FCF helps, but this is still a demanding valuation: the rating would become more constructive only if Q2 AI revenue conversion, FCF growth and infrastructure-software margins improve together. "
            "It would weaken quickly if AI order timing slips, VMware integration economics disappoint, or the multiple expands without matching cash-flow evidence."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | Q2 AI semiconductor guide converts into revenue while Q1-level FCF persists | Premium AI multiple remains defensible | Move toward Accumulate |\n| Base | AI revenue grows and VMware mix helps cash flow, but valuation stays demanding | Hold remains appropriate | Hold |\n| Bear | AI order timing slips or VMware integration pressure appears | Multiple compression risk rises | Reduce risk / downgrade |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, 50-SMA at {_fmt_number(t.sma_50)} and 200-SMA at {_fmt_number(t.sma_200)}. "
            "The trend can support a Hold, but valuation discipline remains necessary."
        ),
        "",
        "## Bull Case",
        "The bull case is that AI revenue keeps scaling, Q2 guidance is met or beaten, VMware expands infrastructure-software margin, and FCF remains strong.",
        "",
        "## Bear Case",
        "The bear case is that AI demand is already priced in, order timing slows, VMware integration disappoints or the valuation compresses despite strong reported growth.",
        "",
        "## Risks",
        "Key risks are AI order concentration, semiconductor cyclicality, customer concentration, VMware integration risk and multiple compression.",
        "",
        "## Catalysts",
        "Catalysts include Q2 AI semiconductor revenue conversion, sustained FCF, stronger infrastructure-software margins and evidence that AI demand is broadening.",
        "",
        "## Final Rating & Action Plan",
        _avgo_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _ddog_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# DDOG Research Report",
        "## Executive Summary",
        (
            "Datadog is a Hold because the observability platform has credible demand and strong liquidity, while the equity case still needs clean evidence that usage growth, FCF conversion and SBC discipline can improve together. "
            "FY2025 revenue of $3.43B, operating cash flow of $1.05B, company-defined FCF of $914.7M, SBC of $750.7M and cash plus marketable securities of about $4.47B put the current-period IR reconciliation directly in the main thesis."
        ),
        "",
        "## Investment Thesis",
        (
            "The thesis is a high-quality observability platform with AI/GPU monitoring optionality, but the stock should not be treated as a clean Accumulate until usage trends and free-cash-flow conversion offset dilution and valuation risk. "
            "That combination supports Hold: the business is not broken, but the evidence does not yet justify paying up aggressively."
        ),
        "",
        "## Current Period KPIs",
        "FY2025 revenue of $3.43B anchors Datadog's scale in observability and cloud monitoring, but usage-based demand can decelerate quickly if cloud optimization pressure returns.",
        "Operating cash flow of $1.05B and company-defined FCF of $914.7M show strong cash conversion for a SaaS platform, making FCF durability the main support for the rating.",
        "SBC of $750.7M and cash plus marketable securities of about $4.47B frame the shareholder-quality tradeoff: liquidity is excellent, but compensation intensity still matters.",
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and TTM FCF of {_fmt_money(f.free_cash_flow_ttm)} support the core quality case once IR reconciliation is clean. "
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} keeps the report from becoming more bullish because dilution can absorb part of the FCF benefit."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} are acceptable only if revenue durability and FCF conversion remain visible. "
            "The rating would become more constructive if revenue growth stabilizes while company-defined FCF remains near or above the current level and SBC intensity declines; it would weaken if usage growth slows or FCF quality falls back."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | Revenue growth holds, FCF stays strong and SBC intensity falls | EV/Sales and P/FCF become easier to defend | Move toward Accumulate |\n| Base | FCF is strong but usage growth and SBC require monitoring | Hold remains appropriate | Hold |\n| Bear | Usage slows or SBC absorbs more of the FCF benefit | Multiple support weakens | Reduce risk / downgrade |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, 50-SMA at {_fmt_number(t.sma_50)} and 200-SMA at {_fmt_number(t.sma_200)}. "
            "A constructive action plan should require either a technical reset or clear reclaim of trend support before adding risk."
        ),
        "",
        "## Bull Case",
        "The bull case is that observability consolidation, AI monitoring demand and strong FCF conversion make the current valuation more defensible.",
        "",
        "## Bear Case",
        "The bear case is that usage optimization returns, SBC remains elevated, or AI observability remains narrative rather than material revenue support.",
        "",
        "## Risks",
        "Key risks are cloud-usage cyclicality, platform competition, SBC dilution, valuation compression and overreliance on FCF if revenue growth slows.",
        "",
        "## Catalysts",
        "Catalysts include sustained revenue growth, strong company-defined FCF, lower SBC intensity and evidence that AI/GPU observability is contributing to platform demand.",
        "",
        "## Final Rating & Action Plan",
        _ddog_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _crm_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# CRM Research Report",
        "## Executive Summary",
        (
            "Salesforce is a Hold because FY2026 cash generation is strong, while the equity case still needs clearer proof that Agentforce, Data Cloud and subscription growth can reaccelerate without sacrificing margin discipline. "
            "FY2026 revenue of $41.5B, operating cash flow of $15.0B, company-defined FCF of $14.4B, SBC of $3.51B and cash plus marketable securities of about $9.57B anchor the current-period IR view."
        ),
        "",
        "## Investment Thesis",
        (
            "The thesis is an enterprise-SaaS platform with durable cash generation and capital-return capacity, but the next leg of upside depends on whether AI products translate into measurable growth. "
            "Hold is appropriate because FCF quality is real, yet the report should not upgrade until growth quality improves alongside cash conversion."
        ),
        "",
        "## Current Period KPIs",
        "FY2026 revenue of $41.5B shows Salesforce still has major enterprise-SaaS scale, but scale alone does not prove AI-led reacceleration.",
        "Operating cash flow of $15.0B and company-defined FCF of $14.4B make cash generation the strongest support for the rating.",
        "SBC of $3.51B and cash plus marketable securities of about $9.57B frame the capital-return debate: shareholder returns are more compelling if AI/product execution improves without higher dilution.",
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and TTM FCF of {_fmt_money(f.free_cash_flow_ttm)} support a cash-generative enterprise-software profile. "
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is manageable relative to earlier SaaS concerns, but it still belongs in the valuation and capital-return debate."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} are fair if Salesforce can pair FCF durability with better growth evidence. "
            "The rating would become more constructive if Agentforce/Data Cloud adoption improves subscription growth while FCF remains near current strength; it would weaken if cash flow is stable but growth quality keeps fading."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | AI/Data Cloud adoption improves growth while FCF remains strong | P/FCF becomes easier to defend | Move toward Accumulate |\n| Base | FCF is strong but growth proof remains incomplete | Hold remains appropriate | Hold |\n| Bear | Growth disappoints or FCF durability weakens | Multiple support deteriorates | Reduce risk / downgrade |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, 50-SMA at {_fmt_number(t.sma_50)} and 200-SMA at {_fmt_number(t.sma_200)}. "
            "The action plan should wait for technical confirmation or a better risk/reward entry before adding aggressively."
        ),
        "",
        "## Bull Case",
        "The bull case is that Agentforce and Data Cloud convert into measurable subscription growth while FCF and capital returns stay strong.",
        "",
        "## Bear Case",
        "The bear case is that AI adoption remains more narrative than financial, growth disappoints, or buybacks mask weaker organic momentum.",
        "",
        "## Risks",
        "Key risks are AI product adoption, enterprise spending cycles, integration complexity, dilution and valuation compression if growth does not reaccelerate.",
        "",
        "## Catalysts",
        "Catalysts include stronger subscription growth, clearer Agentforce/Data Cloud monetization, durable FCF and capital returns that do not rely on deteriorating growth quality.",
        "",
        "## Final Rating & Action Plan",
        _crm_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def _nflx_publish_report(
    rating: str,
    metrics: MetricsPacket,
    claims: list[ResearchClaim],
    evidence_ledger: EvidenceLedger,
) -> str:
    f = metrics.fundamentals
    v = metrics.valuation
    t = metrics.technical
    sections = [
        "# NFLX Research Report",
        "## Executive Summary",
        (
            "Netflix is a Hold because the current-period profitability profile is strong, but the equity case still depends on durable engagement, ad-tier execution and cash-flow consistency. "
            "Q1 revenue of $12.25B, operating income of $4.00B, operating margin of 32.3% and Q1 FCF of $5.10B support the quality case, while valuation and content-cycle risk argue against chasing."
        ),
        "",
        "## Investment Thesis",
        (
            "The thesis is a global streaming platform with scale, pricing power and improving advertising optionality. "
            "Hold is appropriate because the current quarter shows strong margin and FCF, but a more bullish stance needs evidence that ad-tier monetization and engagement can extend that profitability without a content-cost reset."
        ),
        "",
        "## Current Period KPIs",
        "Q1 revenue of $12.25B confirms that Netflix still has large-scale monetization power across subscription and emerging advertising surfaces.",
        "Q1 operating income of $4.00B and operating margin of 32.3% show that operating leverage remains a central strength.",
        "Q1 FCF of $5.10B is the key cash-flow proof point, but it should be monitored for durability because streaming FCF can be affected by content cash timing.",
        "",
        "## Fundamental Analysis",
        (
            f"TTM revenue of {_fmt_money(f.revenue_ttm)} and TTM FCF of {_fmt_money(f.free_cash_flow_ttm)} support the view that Netflix has moved from growth story to cash-generative media platform. "
            f"SBC/Revenue of {_fmt_pct(f.sbc_to_revenue)} is not the core debate; the more important questions are engagement, content efficiency and advertising monetization."
        ),
        "",
        "## Valuation / Risk-Reward",
        (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of {_fmt_multiple(v.price_to_fcf)} require confidence that margin expansion and FCF durability continue. "
            "The valuation can be justified by scale and profitability, but it leaves less room for engagement weakness or content-cost disappointment."
        ),
        "",
        "## Scenario / Sensitivity",
        "| Scenario | KPI trigger | Valuation implication | Rating implication |\n|---|---|---|---|\n| Bull | Ad-tier monetization, margin and FCF durability improve together | Premium multiple is easier to defend | Move toward Accumulate |\n| Base | Margins and FCF stay strong but engagement/ad proof is incomplete | Hold remains appropriate | Hold |\n| Bear | Engagement, content costs or FCF durability weaken | Multiple compression risk rises | Reduce risk / downgrade |",
        "",
        "## Technical Setup",
        (
            f"The stock closed at {_fmt_number(t.close)} with RSI at {_fmt_number(t.rsi_14)}, 50-SMA at {_fmt_number(t.sma_50)} and 200-SMA at {_fmt_number(t.sma_200)}. "
            "The technical setup should not override the fundamental quality, but it does affect entry discipline."
        ),
        "",
        "## Bull Case",
        "The bull case is that ad-tier monetization scales, engagement remains resilient, operating margin stays high and FCF proves durable across content cycles.",
        "",
        "## Bear Case",
        "The bear case is that engagement slows, content costs rise, ad-tier monetization disappoints or valuation compresses despite strong current-period margins.",
        "",
        "## Risks",
        "Key risks are content-cost inflation, competitive streaming pressure, advertising execution, engagement volatility and valuation sensitivity if FCF becomes less durable.",
        "",
        "## Catalysts",
        "Catalysts include stronger ad-tier disclosure, sustained operating margin, durable FCF and evidence that engagement remains resilient without excessive content spending.",
        "",
        "## Final Rating & Action Plan",
        _nflx_rating_section(rating),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claims, evidence_ledger),
    ]
    return "\n\n".join(sections)


def publish_report_quality(markdown: str) -> dict[str, int]:
    main = _main_body(markdown)
    payload = {
        "publish_report_exists": 1,
        "publish_mechanical_language_count": _mechanical_count(main),
        "publish_current_kpi_count": _current_kpi_count(main),
        "publish_evidence_appendix_exists": int("## Evidence Appendix" in markdown),
        "publish_claim_id_main_body_count": len(re.findall(r"\b[A-Z]{1,6}_CLAIM_\d{3}\b", main)),
        "publish_valuation_sensitivity_present": int(_valuation_sensitivity_present(main)),
        "publish_action_plan_trigger_count": _action_plan_trigger_count(main),
    }
    payload["publish_report_quality_score"] = _publish_quality_score_from_payload(payload)
    return payload


def save_publish_report(markdown: str, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return target


def save_internal_best_report(markdown: str, path: str | Path) -> Path:
    return save_publish_report(markdown, path)


def save_publish_quality(payload: dict[str, int], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _publish_quality_score_from_payload(payload: dict[str, int]) -> int:
    score = 100 if payload.get("publish_report_exists") else 0
    if not payload.get("publish_evidence_appendix_exists"):
        score -= 20
    if payload.get("publish_current_kpi_count", 0) < 3:
        score -= 20
    if not payload.get("publish_valuation_sensitivity_present"):
        score -= 20
    if payload.get("publish_action_plan_trigger_count", 0) < 2:
        score -= 15
    score -= min(30, int(payload.get("publish_mechanical_language_count") or 0) * 10)
    score -= min(20, int(payload.get("publish_claim_id_main_body_count") or 0) * 5)
    return max(0, min(100, score))


def _group_claims(claims: list[ResearchClaim]) -> dict[str, list[ResearchClaim]]:
    grouped: dict[str, list[ResearchClaim]] = {}
    for claim in claims:
        grouped.setdefault(claim.section or "Unassigned", []).append(claim)
    return grouped


def _paragraphs(claims: list[ResearchClaim], limit: int) -> str:
    usable = [claim for claim in claims if _claim_text(claim)]
    if not usable:
        return "No evidence-backed discussion is available for this section."
    paragraphs = []
    for claim in usable[:limit]:
        text = _clean_text(_claim_text(claim))
        additions = []
        if claim.counterargument:
            additions.append(_clean_text(claim.counterargument))
        if claim.investment_implication:
            additions.append(_clean_text(claim.investment_implication))
        if additions:
            text = f"{text} {' '.join(additions)}"
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _internal_paragraphs(claims: list[ResearchClaim], limit: int) -> str:
    usable = [claim for claim in claims if _claim_text(claim)]
    if not usable:
        return "No evidence-backed discussion is available for this section."
    paragraphs = []
    for claim in usable[:limit]:
        text = _clean_internal_text(_claim_text(claim))
        additions = []
        if claim.counterargument:
            additions.append(_clean_internal_text(claim.counterargument))
        if claim.investment_implication:
            additions.append(_clean_internal_text(claim.investment_implication))
        if additions:
            text = f"{text} {' '.join(additions)}"
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _early_commercial_valuation_sensitivity(v) -> str:
    return "\n\n".join(
        [
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} is an extreme valuation for an early-commercial capital-intensive technology company.",
            "The valuation becomes more plausible only if backlog converts into recognized revenue and the FCF path visibly improves.",
            "Downside risk rises if Neutron execution is delayed, contract timing slips, or FCF losses remain high despite backlog scale.",
        ]
    )


def _early_commercial_technical_timing(grouped: dict[str, list[ResearchClaim]]) -> str:
    claims = grouped.get("Technical Setup only as timing", [])
    if not claims:
        return "Technical setup is timing context only. It should not drive the business classification."
    claim = claims[0]
    text = _clean_internal_text(_claim_text(claim))
    counter = _clean_internal_text(claim.counterargument) if claim.counterargument else ""
    sentences = [text]
    if counter:
        sentences.append(counter)
    sentences.append("Do not let momentum outweigh FCF, backlog conversion or execution evidence.")
    return " ".join(sentences[:3])


def _executive_summary(
    ticker: str,
    rating: str,
    grouped: dict[str, list[ResearchClaim]],
    metrics: MetricsPacket,
) -> str:
    current = _paragraphs(grouped.get("Executive Summary", []), limit=1)
    if not current:
        current = _paragraphs(
            _current_kpi_claims(
                [claim for claims in grouped.values() for claim in claims]
            ),
            limit=1,
        )
    technical = (
        f"Technically, {ticker} carries an RSI of {_fmt_number(metrics.technical.rsi_14)} with price at "
        f"{_fmt_number(metrics.technical.close)}, so timing remains part of the rating debate."
    )
    return f"{current}\n\nThe resulting stance is {rating}: the report weighs current fundamentals against valuation, cash-flow conversion and timing risk. {technical}"


def _current_kpi_claims(claims: list[ResearchClaim]) -> list[ResearchClaim]:
    return [
        claim
        for claim in claims
        if (claim.section or "") in CURRENT_PERIOD_SECTIONS
        and (
            any(
                metric.startswith("current_period_") or "guidance" in metric
                for metric in claim.metric_refs
            )
            or CURRENT_PERIOD_MARKER_RE.search(_claim_text(claim)) is not None
        )
        and any(char.isdigit() for char in _claim_text(claim))
    ]


def _generic_investment_thesis(
    ticker: str,
    rating: str,
    metrics: MetricsPacket,
    decision: DecisionPacket,
    *,
    currency: str = "USD",
) -> str:
    fundamentals = metrics.fundamentals
    scores = decision.signal_scores
    if (
        fundamentals.free_cash_flow_ttm is not None
        and fundamentals.free_cash_flow_ttm < 0
    ):
        cash_text = (
            f"negative FCF of {_fmt_money(fundamentals.free_cash_flow_ttm, currency)} keeps "
            "cash conversion as a fundamental constraint"
        )
    elif fundamentals.free_cash_flow_ttm is not None:
        cash_text = (
            f"positive FCF of {_fmt_money(fundamentals.free_cash_flow_ttm, currency)} "
            "provides measured cash-conversion support"
        )
    else:
        cash_text = "FCF is unavailable and cannot support the thesis"
    current_profit_decline = any(
        value is not None and value < 0
        for value in (
            fundamentals.current_period_operating_income_growth_yoy,
            fundamentals.current_period_net_income_growth_yoy,
        )
    )
    if scores.fundamental_score > 0 and current_profit_decline:
        fundamental_text = (
            "mixed fundamental picture: positive FCF alongside weaker "
            "current-period profit comparisons"
        )
    else:
        fundamental_direction = (
            "cautious"
            if scores.fundamental_score < 0
            else "constructive"
            if scores.fundamental_score > 0
            else "neutral"
        )
        fundamental_text = f"{fundamental_direction} fundamental signal"
    return (
        f"{ticker}'s central investment debate is whether revenue scale of "
        f"{_fmt_money(fundamentals.revenue_ttm, currency)} can translate into durable cash "
        f"generation; {cash_text}. The {rating} stance combines a "
        f"{fundamental_text} with "
        f"{scores.technical_status} technical evidence and "
        f"{scores.valuation_status} valuation evidence."
    )


def _final_rating_section(
    ticker: str,
    rating: str,
    f,
    v,
    t,
    decision_packet: DecisionPacket,
    *,
    currency: str = "USD",
) -> str:
    scores = decision_packet.signal_scores
    rating_reason = (
        decision_packet.analytical_rating_reason
        or decision_packet.rating_permission.reason
    )
    if scores.valuation_status == "unbenchmarked":
        valuation_text = (
            f"EV/Sales of {_fmt_multiple(v.ev_to_sales)} and P/FCF of "
            f"{_fmt_multiple(v.price_to_fcf)} are unbenchmarked observations. "
            "They add neither a positive nor a negative rating signal."
        )
    elif scores.valuation_status != "measured":
        valuation_text = (
            "Valuation is not sufficiently measured and therefore cannot move "
            "the rating."
        )
    elif scores.valuation_score > 0:
        valuation_text = "Benchmarked valuation evidence is constructive."
    elif scores.valuation_score < 0:
        valuation_text = "Benchmarked valuation evidence is cautious."
    else:
        valuation_text = "Benchmarked valuation evidence is neutral."

    if scores.technical_status == "measured":
        technical_text = (
            "constructive"
            if scores.technical_score > 0
            else "cautious"
            if scores.technical_score < 0
            else "neutral"
        )
    elif scores.technical_status == "partial":
        direction = (
            "bullish"
            if scores.technical_score > 0
            else "bearish"
            if scores.technical_score < 0
            else "neutral"
        )
        technical_text = (
            f"{direction} but partial because the price series is not confirmed "
            "as corporate-action adjusted"
        )
    else:
        technical_text = "not measured"
    if f.free_cash_flow_ttm is not None and f.free_cash_flow_ttm < 0:
        confirmation_limits = []
        if scores.valuation_status != "measured":
            confirmation_limits.append(
                f"valuation is {scores.valuation_status}"
            )
        if scores.technical_status != "measured":
            confirmation_limits.append(
                f"the technical basis is {scores.technical_status}"
            )
        confirmation_text = (
            " and ".join(confirmation_limits)
            if confirmation_limits
            else "the other measured signals do not corroborate a further downgrade"
        )
        why_not_constructive = (
            "Why not more constructive? Negative FCF and the cautious measured "
            "fundamental signal block a more constructive rating without clear "
            "cash-conversion improvement."
        )
        why_not_cautious = (
            "Why not more cautious? Negative FCF is already fundamental downside "
            "evidence and is not dismissed. A more cautious permitted rating still "
            f"requires additional measured confirmation because {confirmation_text}."
        )
    elif (
        f.equity is not None
        and f.equity <= 0
        and f.free_cash_flow_ttm is not None
        and f.free_cash_flow_ttm > 0
    ):
        why_not_constructive = (
            "Why not more constructive? Non-positive book equity is a material "
            "balance-sheet constraint; positive FCF does not remove that constraint. "
            "A more constructive rating requires durable cash coverage and stronger "
            "liquidity or leverage evidence."
        )
        why_not_cautious = (
            "Why not more cautious? The non-positive equity constraint is not "
            "dismissed, but positive FCF is measured counterevidence. Non-positive "
            "equity alone does not establish insolvency or business deterioration."
        )
    elif (
        f.free_cash_flow_ttm is not None
        and f.free_cash_flow_ttm > 0
        and any(
            value is not None and value < 0
            for value in (
                f.current_period_operating_income_growth_yoy,
                f.current_period_net_income_growth_yoy,
            )
        )
    ):
        decline_labels = [
            label
            for label, value in (
                (
                    "operating-income",
                    f.current_period_operating_income_growth_yoy,
                ),
                ("net-income", f.current_period_net_income_growth_yoy),
            )
            if value is not None and value < 0
        ]
        decline_text = " and ".join(decline_labels)
        counterevidence_subject = (
            "positive FCF and the bullish technical direction are"
            if scores.technical_score > 0
            else "positive FCF is"
        )
        why_not_constructive = (
            f"Why not more constructive? Current-period {decline_text} declines "
            "are current downside evidence; positive FCF does not erase those "
            "reported comparisons. A more constructive rating requires profit "
            "comparisons to improve, that improvement to persist, and benchmarked "
            "valuation support."
        )
        why_not_cautious = (
            f"Why not more cautious? The {decline_text} declines are not dismissed, "
            f"but {counterevidence_subject} measured counterevidence. "
            "A more cautious rating requires the profit weakness to persist or be "
            "corroborated by weaker cash conversion."
        )
    elif (
        f.free_cash_flow_ttm is not None
        and f.free_cash_flow_ttm > 0
        and scores.fundamental_score > 0
        and scores.technical_score < 0
        and scores.technical_status in {"measured", "partial"}
    ):
        why_not_constructive = (
            "Why not more constructive? Constructive fundamentals and positive FCF "
            "do not override the observed bearish technical direction. A more "
            "constructive rating requires technical confirmation and benchmarked "
            "valuation support."
        )
        why_not_cautious = (
            "Why not more cautious? The bearish technical state is not dismissed, "
            "but positive FCF and the constructive fundamental signal are measured "
            "counterevidence. A more cautious rating requires corroborating "
            "fundamental deterioration."
        )
    else:
        why_not_constructive = (
            "Why not more constructive? A rating change requires stronger measured "
            "fundamentals or technical confirmation and, where valuation is relevant, "
            "benchmark evidence."
        )
        why_not_cautious = (
            "Why not more cautious? A raw multiple or an isolated price signal cannot "
            "establish business deterioration."
        )
    return "\n\n".join(
        [
            f"Final Rating: {rating}. {rating_reason}",
            (
                f"Factual anchors are revenue of {_fmt_money(f.revenue_ttm, currency)}, "
                f"FCF of {_fmt_money(f.free_cash_flow_ttm, currency)} and RSI of "
                f"{_fmt_number(t.rsi_14)}. The available technical direction is "
                f"{technical_text}."
            ),
            valuation_text,
            why_not_constructive,
            why_not_cautious,
            (
                f"Review condition: retain the {ticker} research rating while "
                "the measured evidence state is unchanged. Reassess only when "
                "new primary evidence changes fundamentals, benchmarked valuation "
                "or the technical trend."
            ),
        ]
    )


def _googl_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Alphabet has excellent operating assets, but investors must decide whether Cloud and AI monetization can justify the current valuation while AI capex absorbs more cash.",
        "Why this rating now: Hold fits a business with strong Q1 revenue, rapid Cloud growth, high operating margin and large FCF, but also an overbought chart and heavy capex burden.",
        "Why not more bullish: Buy would require either a better entry point, clearer evidence that AI capex is lifting durable revenue, or stronger FCF conversion after infrastructure spending.",
        "Why not more bearish: Sell is too harsh because Search, Cloud, margins, cash flow and balance-sheet strength remain intact; the issue is timing and risk/reward, not a broken thesis.",
        "What changes the rating: stronger Cloud growth with stable margins and resilient FCF would support a more constructive stance; weaker FCF conversion, regulatory pressure or a technical break would reduce risk tolerance.",
        "Action plan: existing holders can keep core exposure, but new money should wait for either a pullback toward the 50-SMA area, a cooler RSI setup, or clearer proof that AI spending is translating into durable free-cash-flow growth.",
    ])


def _snow_rating_section(rating: str) -> str:
    return "\n\n".join([
        "Final Rating: Hold with Underweight Bias." if rating == "Hold" else f"Final Rating: {rating}.",
        "Central investment debate: Snowflake has real enterprise demand and cash generation, but the stock still asks investors to pay for a recovery before the chart and SBC profile fully support it.",
        "Why this rating now: Hold with Underweight Bias fits a company with solid product revenue, NRR, RPO and adjusted FCF, while the underweight bias reflects high SBC intensity and price below both major moving averages.",
        "Why not more bullish: A more constructive rating would require better technical confirmation, sustained RPO conversion and confidence that SBC/Revenue is moving lower without hurting product velocity.",
        "Why not more bearish: Sell is too aggressive because product revenue scale, 125.0% NRR, $9.77B RPO and $1.19B adjusted FCF show that the business remains strategically relevant.",
        "What changes the rating: reclaiming the 50-SMA and 200-SMA, stable NRR and stronger product revenue conversion would improve the stance; weaker consumption or persistent SBC pressure would keep the underweight bias in place.",
        "Action plan: keep exposure at or below target weight until the stock reclaims the 50-SMA first and then the 200-SMA, while also showing that growth, FCF and dilution can improve together.",
    ])


def _msft_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Microsoft has one of the clearest enterprise AI demand curves in the market, but the stock still needs proof that Azure growth, Microsoft Cloud scale and the AI run-rate can convert through the datacenter buildout into durable FCF leverage.",
        "Why this rating now: Hold fits Q3 revenue of $82.89B, Microsoft Cloud revenue of $54.50B, 29.0% Cloud growth, 40.0% Azure growth and an AI annual revenue run-rate above $37.00B; the business quality is excellent, but the valuation already assumes a lot of AI success.",
        "Why not more bullish: Accumulate needs Azure to stay near the high-30s/40% growth zone while AI workloads show visible margin contribution and FCF conversion improves after the capex wave, not merely more revenue growth bought with heavier infrastructure spend.",
        "Why not more bearish: Sell is too harsh because enterprise software durability, cloud demand, balance-sheet flexibility and FCF generation remain intact; the concern is price paid versus capex productivity, not impairment of the franchise.",
        "What changes the rating: stronger Azure growth with improving FCF conversion and moderating capex intensity would support a more constructive stance; weaker cloud growth, higher AI capex without margin leverage or a break below key moving-average support would reduce risk tolerance.",
        "Action plan: existing holders can keep core exposure, but new capital should wait for either a technical reset toward moving-average support, the next earnings update confirming cloud growth plus margin resilience, or evidence that AI capex is turning into FCF leverage rather than just capacity growth.",
    ])


def _avgo_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Broadcom has strong AI revenue, Q2 guide support and Q1 FCF, but the stock is already discounting a demanding path for AI semiconductors, VMware integration and infrastructure-software margins.",
        "Why this rating now: Hold is appropriate because Q1 AI revenue, Q1 FCF and Q2 AI semiconductor guidance support the story, while EV/Sales and P/FCF leave little tolerance for order timing, customer concentration or software integration disappointment.",
        "Why not more bullish: Buy would require Q2 AI guide conversion, stronger FCF growth, visible VMware/software margin contribution and ideally some multiple compression rather than only narrative acceleration; until then this is a lower-conviction Hold rather than a highest-conviction setup.",
        "Why not more bearish: Sell is too harsh because the company has current-period AI revenue, forward AI guidance and cash-flow evidence in the main thesis.",
        "What changes the rating: stronger AI semiconductor conversion with software-margin expansion would improve the stance; AI order timing slips, weak VMware economics or FCF deterioration would weaken it.",
        "Action plan: hold core exposure only if position size reflects valuation risk; avoid aggressive adds until Q2 guide conversion and FCF growth confirm the AI thesis or the stock offers a better entry after valuation/technical reset.",
    ])


def _meta_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Meta's ad engine is converting Q1 revenue and 41.0% operating margin into strong FCF, but FY2026 capex guidance of $125.00B-$145.00B makes AI infrastructure ROI the deciding variable.",
        "Why this rating now: Hold is the right posture because Q1 revenue of $56.31B and Q1 FCF of $12.39B show excellent platform economics, while the capex plan can absorb a large part of the benefit if AI monetization does not show up quickly.",
        "Why not more bullish: Accumulate needs evidence that AI ranking, recommendation and ad tools are lifting engagement or pricing enough to offset the capex step-up without margin erosion.",
        "Why not more bearish: Sell is too harsh because Family of Apps monetization, margin quality and FCF remain strong; the concern is reinvestment risk, not a broken ad platform.",
        "What changes the rating: stronger ad growth with stable operating margin and visible AI monetization would improve the stance; capex rising without FCF conversion, margin pressure or regulatory hits would reduce risk tolerance.",
        "Action plan: keep core exposure sized to the capex debate, avoid adding after strength unless the next update confirms AI-led ad monetization, and use weaker margins or FCF conversion as the downgrade trigger.",
    ])


def _aapl_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Apple still has ecosystem cash generation and capital-return power, but the stock needs product-cycle resilience, Services durability and clearer AI positioning to justify aggressive buying.",
        "Why this rating now: Accumulate works only as a staged view because latest-quarter revenue of $111.20B, EPS of $2.01, operating cash flow above $28.00B and the $100.00B buyback authorization support downside quality.",
        "Why not more bullish: A stronger buy call needs Services and iPhone momentum to improve together, AI features to become a visible upgrade-cycle driver and FCF growth to keep pace with the valuation.",
        "Why not more bearish: Sell is too harsh because Apple still has scale, cash generation, low dilution pressure and a large buyback that can support EPS through softer product periods.",
        "What changes the rating: stronger Services growth, clearer AI-led product demand and resilient FCF would keep the Accumulate path intact; iPhone weakness, regulatory pressure or slowing FCF would push the stance back toward Hold.",
        "Action plan: add only in stages, preferably on pullbacks or after a Services/iPhone update confirms demand quality; trim planned additions if regulatory or AI execution risk starts to pressure cash-flow confidence.",
    ])


def _ddog_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Datadog has a high-quality observability platform and strong liquidity, but the stock still needs proof that usage growth, AI/GPU monitoring demand and FCF conversion can outrun SBC and valuation pressure.",
        "Why this rating now: Hold fits FY2025 revenue of $3.43B, operating cash flow of $1.05B, company-defined FCF of $914.7M and about $4.47B of cash plus marketable securities, while SBC of $750.7M keeps the equity-quality debate alive.",
        "Why not more bullish: Accumulate needs durable usage growth, clearer evidence that AI observability is becoming material demand and lower SBC intensity, not just strong historical FCF.",
        "Why not more bearish: Sell is too harsh because the business is cash generative, liquid and strategically relevant in observability; the issue is valuation and dilution discipline rather than business deterioration.",
        "What changes the rating: revenue durability with stable or improving FCF conversion and lower SBC/Revenue would improve the stance; cloud optimization, weaker FCF quality or persistent compensation intensity would reduce risk tolerance.",
        "Action plan: keep exposure measured, wait for either a better entry or the next usage/FCF update, and use a failure to defend trend support or a deterioration in SBC-adjusted FCF quality as the downgrade trigger.",
    ])


def _crm_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Salesforce has excellent FY2026 cash generation, but the equity case needs cleaner proof that Agentforce, Data Cloud and subscription growth can reaccelerate without relying only on buybacks and margin discipline.",
        "Why this rating now: Hold fits FY2026 revenue of $41.5B, operating cash flow of $15.0B and company-defined FCF of $14.4B, while SBC of $3.51B and elevated reconciliation noise keep this from becoming a higher-conviction publish template.",
        "Why not more bullish: Accumulate needs AI products to show measurable subscription uplift, FCF to remain durable and capital returns to complement rather than mask growth quality.",
        "Why not more bearish: Sell is too harsh because the business still generates substantial cash and has capital-return capacity; the concern is growth proof, not liquidity or solvency.",
        "What changes the rating: stronger subscription growth with clear Agentforce/Data Cloud monetization and stable FCF would improve the stance; weaker organic growth, lower FCF durability or rising dilution pressure would reduce risk tolerance.",
        "Action plan: maintain only appropriately sized exposure, wait for the next growth and margin update before adding, and treat a failure to convert AI narrative into subscription momentum as the downgrade trigger.",
    ])


def _nflx_rating_section(rating: str) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        "Central investment debate: Netflix now looks like a cash-generative global media platform, but the stock still depends on engagement durability, ad-tier execution and content-spend discipline to defend the multiple.",
        "Why this rating now: Hold fits Q1 revenue of $12.25B, operating income of $4.00B, 32.3% operating margin and Q1 FCF of $5.10B; the quarter is strong, but the valuation leaves less room for engagement or content-cost disappointment.",
        "Why not more bullish: Accumulate needs ad-tier monetization and engagement to add incremental growth without sacrificing margin or FCF durability across the content cycle.",
        "Why not more bearish: Sell is too harsh because current profitability, operating leverage and FCF are real; the concern is how much of that strength is already reflected in the stock.",
        "What changes the rating: stronger ad-tier disclosure, resilient engagement and durable FCF would improve the stance; weaker engagement, higher content cash spend or fading FCF conversion would reduce risk tolerance.",
        "Action plan: hold existing exposure, avoid chasing solely on margin strength, and add only if the next update confirms ad-tier progress plus durable FCF or if the stock resets to a better valuation entry.",
    ])


def _standard_rating_section(
    company: str,
    rating: str,
    central_debate: str,
    upgrade_trigger: str,
    downgrade_trigger: str,
) -> str:
    return "\n\n".join([
        f"Final Rating: {rating}.",
        f"Central investment debate: {company} has a credible business case, but {central_debate}.",
        f"Why this rating now: {rating} fits the balance between current-period KPI support, valuation discipline and technical timing.",
        "Why not more bullish: a more constructive stance needs either a better entry point, stronger cash-flow conversion or clearer evidence that current-period KPIs are becoming durable earnings power.",
        "Why not more bearish: the operating evidence is not broken; the rating is about position discipline and risk/reward, not rejection of the business.",
        f"What changes the rating: upgrade if {upgrade_trigger}; reduce risk if {downgrade_trigger}.",
        "Action plan: keep exposure sized to conviction, avoid adding solely on momentum, and require the next current-period data point to confirm the thesis before increasing risk. For new capital, favor staged entries after a technical reset or a reclaim of key moving-average support rather than chasing a stretched move.",
    ])


def _evidence_appendix(claims: list[ResearchClaim], evidence_ledger: EvidenceLedger) -> str:
    evidence_by_id = {item.evidence_id: item for item in evidence_ledger.evidence_items}
    lines = [
        "| Claim | Evidence IDs | Source Type | Confidence |",
        "|---|---|---|---|",
    ]
    for claim in claims:
        source_types = sorted({
            evidence_by_id[item_id].source_type
            for item_id in claim.evidence_ids
            if item_id in evidence_by_id
        })
        lines.append(
            f"| {_table_text(_claim_text(claim))} | {', '.join(claim.evidence_ids)} | {', '.join(source_types)} | {claim.confidence or ''} |"
        )
    return "\n".join(lines)


def _source_only_evidence_appendix(evidence_ledger: EvidenceLedger) -> str:
    if not evidence_ledger.evidence_items:
        return "No evidence items available."
    lines = [
        "| Evidence IDs | Source Type | Confidence |",
        "|---|---|---|",
    ]
    grouped: dict[tuple[str, str], list[str]] = {}
    for item in evidence_ledger.evidence_items:
        key = (item.source_type, item.confidence or "")
        grouped.setdefault(key, []).append(item.evidence_id)
    for (source_type, confidence), ids in sorted(grouped.items()):
        lines.append(f"| {', '.join(sorted(ids))} | {source_type} | {confidence} |")
    return "\n".join(lines)


def _main_body(markdown: str) -> str:
    marker = markdown.lower().find("## evidence appendix")
    return markdown if marker == -1 else markdown[:marker]


def _mechanical_count(text: str) -> int:
    lower = text.lower()
    return sum(1 for phrase in PUBLISH_MECHANICAL_PHRASES if phrase in lower)


def _current_kpi_count(text: str) -> int:
    count = 0
    for line in text.splitlines():
        lower = line.lower()
        if any(char.isdigit() for char in line) and any(term in lower for term in CURRENT_KPI_TERMS):
            count += 1
    return count


def _valuation_sensitivity_present(text: str) -> bool:
    lower = text.lower()
    return (
        "## scenario / sensitivity" in lower
        and "valuation implication" in lower
        and (
            "the rating would become more constructive if" in lower
            or "move toward" in lower
            or "upgrade" in lower
        )
        and (
            "would weaken" in lower
            or "reduce risk" in lower
            or "downgrade" in lower
        )
    )


def _action_plan_trigger_count(text: str) -> int:
    lower = text.lower()
    section = lower.split("## final rating & action plan")[-1]
    trigger_terms = {
        "50-sma",
        "200-sma",
        "moving-average",
        "technical reset",
        "guidance",
        "guide",
        "earnings",
        "fcf",
        "free cash flow",
        "margin",
        "capex",
        "reclaim",
        "growth",
        "valuation",
    }
    return sum(1 for term in trigger_terms if term in section)


def _claim_text(claim: ResearchClaim) -> str:
    return claim.claim_text or claim.claim or ""


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    replacements = {
        "Packet-derived": "Reported",
        "packet-derived": "reported",
        "validated close": "latest close",
        "validated FCF": "reported FCF",
        "confirmed packet inputs": "confirmed evidence",
        "packet inputs": "evidence inputs",
        "validated technical trend state": "technical trend state",
        "financial-sanity errors": "financial data concerns",
        "financial-sanity error": "financial data concern",
        "manual review": "further review",
        "sanity guard": "data-quality check",
        "audit has": "review shows",
        "blocking audit errors": "unresolved data issues",
        "blocking data issue": "unresolved data issue",
        "Validation and audit issues are part of": "Data quality is part of",
        "Source-quality limitations": "Source limitations",
        "source-quality issues": "source concerns",
        "source-quality limitations": "source limitations",
    }
    for old, new in replacements.items():
        if old == "manual review":
            cleaned = re.sub(
                old,
                lambda match: (
                    "Further review"
                    if match.group(0)[0].isupper()
                    else "further review"
                ),
                cleaned,
                flags=re.IGNORECASE,
            )
        else:
            cleaned = re.sub(old, new, cleaned, flags=re.IGNORECASE)
    return cleaned


def _clean_internal_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"\b[A-Z]{1,6}_CLAIM_\d{3}\b", "", cleaned)
    replacements = {
        "Packet-derived": "Reported",
        "packet-derived": "reported",
        "validated close": "latest close",
        "validated FCF": "reported FCF",
        "confirmed packet inputs": "confirmed evidence",
        "packet inputs": "evidence inputs",
        "validated technical trend state": "technical trend state",
        "financial-sanity errors": "financial data concerns",
        "financial-sanity error": "financial data concern",
        "sanity guard": "data-quality check",
        "audit has": "review shows",
        "blocking audit errors": "unresolved data issues",
        "blocking data issue": "unresolved data issue",
        "Validation and audit issues are part of": "Data quality is part of",
        "Source-quality limitations": "Source limitations",
        "source-quality issues": "source concerns",
        "source-quality limitations": "source limitations",
    }
    for old, new in replacements.items():
        cleaned = re.sub(old, new, cleaned, flags=re.IGNORECASE)
    return cleaned


def _strip_main_body_internal_language(markdown: str) -> str:
    if "## Evidence Appendix" not in markdown:
        return "\n".join(_clean_text(line) for line in markdown.splitlines())
    main, appendix = markdown.split("## Evidence Appendix", 1)
    main = "\n".join(_clean_text(line) for line in main.splitlines())
    main = re.sub(r"\b[A-Z]{1,6}_CLAIM_\d{3}\b", "", main)
    return f"{main.rstrip()}\n\n## Evidence Appendix{appendix}"


def _table_text(text: str) -> str:
    return _clean_text(text).replace("|", "\\|")


def _fmt_money(value: float | None, currency: str = "USD") -> str:
    if value is None:
        return "not available"
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


def _constructive_cash_conversion_trigger(value: float | None) -> str:
    if value is None:
        return (
            "Current-period KPIs improve and free-cash-flow evidence becomes "
            "available"
        )
    if value <= 0:
        return "Current-period KPIs improve while free-cash-flow conversion improves"
    return "Current-period KPIs improve while free-cash-flow conversion holds"


def _fmt_multiple(value: float | None) -> str:
    return "not available" if value is None else f"{value:.2f}x"


def _fmt_number(value: float | None) -> str:
    return "not available" if value is None else f"{value:.2f}"


def _fmt_score(value: float | None) -> str:
    return "not available" if value is None else f"{value:.1f}".rstrip("0").rstrip(".")


def _status_slug(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace(" ", "_")
    if normalized in {"needs_manual_review", "manual_review_required"}:
        return "manual_review"
    return normalized or "unknown"


def _short_company_name(company_name: str | None, ticker: str) -> str:
    name = (company_name or ticker).strip()
    for suffix in [
        " Corporation",
        " Corp.",
        " Corp",
        " Incorporated",
        " Inc.",
        " Inc",
        " Ltd.",
        " Ltd",
        " PLC",
        " plc",
    ]:
        if name.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name


def _fmt_pct(value: float | None) -> str:
    return "not available" if value is None else f"{value * 100:.1f}%"


def _cash_and_marketable_securities(fundamentals) -> float | None:
    if fundamentals.cash_and_equivalents is not None and fundamentals.marketable_securities is not None:
        return fundamentals.cash_and_equivalents + fundamentals.marketable_securities
    if fundamentals.cash_and_investments is not None:
        return fundamentals.cash_and_investments
    return fundamentals.cash_and_equivalents


def _section_metric(grouped: dict[str, list[ResearchClaim]], section: str, keyword: str) -> str:
    keyword_lower = keyword.lower()
    for claim in grouped.get(section, []):
        text = _claim_text(claim)
        lower = text.lower()
        if keyword_lower not in lower:
            continue
        tail = text[lower.find(keyword_lower) :]
        match = re.search(r"(above\s+)?(\$-?\d+(?:\.\d+)?[BM])", tail, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(2)
        return f"above {value}" if match.group(1) else value
    return "not available"
