from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from research_agent.content.claim_generator import named_current_risk_label
from research_agent.content.report_composer import render_instrument_identity
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.decision.signal_scores import TECHNICAL_SCORING_BASES
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.calculations.fundamentals import (
    current_operating_profit_decline_metrics,
)


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
    "Material Events & Governance",
    "Business Model Reality",
    "Revenue Scale and Backlog",
    "Contract / Backlog Materiality",
    "Segment Mix",
    "Execution Milestones",
    "FCF Path",
    "Capital Intensity",
    "Valuation vs Revenue/Backlog",
}

OPERATING_DRIVER_PATTERNS = {
    "Pricing / yield": re.compile(
        r"\b(?:pricing|price|yield|collection and disposal)\b",
        re.IGNORECASE,
    ),
    "Volume": re.compile(r"\bvolume\b", re.IGNORECASE),
    "Margin": re.compile(
        r"\b(?:margin|operating ebitda|adjusted ebitda)\b",
        re.IGNORECASE,
    ),
    "Capital allocation": re.compile(
        r"\b(?:returned?|returning)\b.{0,100}\bshareholders?\b|"
        r"\b(?:share repurchases?|stock repurchases?|cash dividends?|buybacks?|"
        r"capital returned|return of capital)\b",
        re.IGNORECASE,
    ),
    "Internalization": re.compile(r"\binternalization\b", re.IGNORECASE),
    "Landfill depletable tons": re.compile(
        r"\blandfill\s+depletable\s+tons\b",
        re.IGNORECASE,
    ),
    "Acquired annualized revenue": re.compile(
        r"\b(?:gross\s+)?annualized\s+revenue\s+acquired\b|"
        r"\bacquired\s+annualized\s+revenue\b",
        re.IGNORECASE,
    ),
}

OPERATING_DRIVER_METRIC_MARKERS = {
    "Pricing / yield": ("yield", "pricing"),
    "Volume": ("volume",),
    "Margin": ("margin", "operating_ebitda", "adjusted_ebitda"),
    "Capital allocation": (
        "capital_allocation",
        "share_repurchase",
        "stock_repurchase",
        "cash_dividend",
    ),
    "Internalization": ("internalization",),
    "Landfill depletable tons": ("landfill_depletable_tons",),
    "Acquired annualized revenue": ("acquired_annualized_revenue",),
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
    rating = (
        decision_packet.rating_permission.display_rating
        or decision_packet.rating_permission.preferred_rating.value
    )
    if _is_early_commercial_capital_intensive_report(grouped, metrics_packet):
        body = _early_commercial_capital_intensive_publish_report(
            ticker,
            rating,
            grouped,
            metrics_packet,
            claim_list,
            evidence_ledger,
        )
    else:
        body = _generic_publish_report(
            data_packet,
            ticker,
            rating,
            grouped,
            metrics_packet,
            decision_packet,
            claim_list,
            evidence_ledger,
            currency=data_packet.price_basis.currency,
        )
    body = _attach_instrument_identity(body, data_packet)
    body = _attach_material_events(body, grouped)
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
    manual_review_reasons: Iterable[str] | None = None,
    review_issue_details: Iterable[dict] | None = None,
) -> str:
    """Render the readable internal surface for manual-review cases.

    The final report remains a claim-near ledger. The internal reading copy
    keeps the prose readable while retaining the complete claim and evidence
    join beside each material paragraph.
    """

    claim_list = list(claims)
    grouped = _group_claims(claim_list)
    ticker = data_packet.ticker.upper()
    rating = (
        decision_packet.rating_permission.display_rating
        or decision_packet.rating_permission.preferred_rating.value
    )
    if company_archetype == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH" or _is_early_commercial_capital_intensive_report(grouped, metrics_packet):
        report = _early_commercial_capital_intensive_internal_best_report(
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
        )
    elif company_archetype == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL" or _is_speculative_deep_tech_report(metrics_packet):
        report = _speculative_deep_tech_internal_best_report(
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
        )
    elif external_display_rating == "Hold Pending FCF Support":
        report = _missing_fcf_support_internal_best_report(
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
        )
    else:
        report = compose_publish_report(data_packet, metrics_packet, decision_packet, evidence_ledger, claim_list)
    report = _attach_instrument_identity(report, data_packet)
    report = _attach_material_events(report, grouped)
    return _attach_data_limits_and_review_status(
        report,
        status=status,
        publishable=publishable,
        manual_review_reasons=manual_review_reasons,
        review_issue_details=review_issue_details,
    ).strip() + "\n"


def _attach_instrument_identity(markdown: str, data_packet: DataPacket) -> str:
    """Make canonical instrument identity visible in every report archetype."""

    if "## Instrument Identity" in markdown:
        return markdown
    title, separator, remainder = markdown.partition("\n")
    identity = "\n".join(
        [
            "## Instrument Identity",
            render_instrument_identity(data_packet),
        ]
    )
    if not separator:
        return f"{title}\n\n{identity}\n"
    return f"{title}\n\n{identity}\n\n{remainder.lstrip()}"


def _attach_material_events(
    markdown: str,
    grouped: dict[str, list[ResearchClaim]],
) -> str:
    """Surface material issuer events before the appendix in every archetype."""

    claims = grouped.get("Material Events & Governance", [])
    if not claims or "## Material Events & Governance" in markdown:
        return markdown
    section = "\n".join(
        [
            "## Material Events & Governance",
            "",
            _paragraphs(claims, limit=6),
        ]
    )
    marker = "## Evidence Appendix"
    if marker in markdown:
        main, appendix = markdown.split(marker, 1)
        return f"{main.rstrip()}\n\n{section}\n\n{marker}{appendix}"
    return f"{markdown.rstrip()}\n\n{section}\n"


def _attach_data_limits_and_review_status(
    markdown: str,
    *,
    status: str,
    publishable: bool,
    manual_review_reasons: Iterable[str] | None,
    review_issue_details: Iterable[dict] | None,
) -> str:
    """Make every active review limitation visible in the reading copy."""

    reasons = list(dict.fromkeys(str(reason) for reason in (manual_review_reasons or []) if reason))
    if not reasons and publishable:
        return markdown
    detail_by_code: dict[str, str] = {}
    for detail in review_issue_details or []:
        code = str(detail.get("code") or "")
        message = str(detail.get("message") or "").strip()
        if code and message and code not in detail_by_code:
            detail_by_code[code] = message
    lines = [
        "## Data Limits & Review Status",
        "",
        f"- Internal status: `{status}`.",
        f"- Public release: `{'allowed' if publishable else 'blocked'}`.",
    ]
    if reasons:
        lines.append("- Active review points:")
        for reason in reasons:
            message = detail_by_code.get(reason) or "Independent review is still required for this point."
            lines.append(f"  - `{reason}`: {message}")
    else:
        lines.append("- No coded data limitation is active; independent human review remains open.")
    section = "\n".join(lines)
    marker = "## Evidence Appendix"
    if marker in markdown:
        main, appendix = markdown.split(marker, 1)
        return f"{main.rstrip()}\n\n{section}\n\n{marker}{appendix}"
    return f"{markdown.rstrip()}\n\n{section}\n"


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
    data_packet: DataPacket,
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
    current_kpi_claims = _current_kpi_claims(claim_list)
    current_kpi_ids = {claim.claim_id for claim in current_kpi_claims}
    operating_driver_claims = _operating_driver_claims(claim_list)
    operating_driver_ids = {
        claim.claim_id for _, claim in operating_driver_claims
    }
    fundamental_claims = [
        claim
        for claim in grouped.get("Fundamental Analysis", [])
        if claim.claim_id not in current_kpi_ids
    ]
    business_context_claims = [
        claim
        for claim in grouped.get("Business & Segment Context", [])
        if claim.claim_id not in current_kpi_ids
        and claim.claim_id not in operating_driver_ids
    ]
    investment_thesis = "\n\n".join(
        part
        for part in (
            _generic_investment_thesis(
                ticker,
                rating,
                metrics_packet,
                decision_packet,
                operating_driver_claims=operating_driver_claims,
                currency=currency,
            ),
            _paragraphs(
                business_context_claims,
                limit=2,
            ),
        )
        if part
    )
    projected_fcf_bridge = _projected_fcf_guidance_bridge(
        evidence_ledger,
        currency=currency,
    )

    sections = [
        f"# {ticker} Research Report",
        "## Instrument Identity",
        render_instrument_identity(data_packet),
        "",
        "## Executive Summary",
        _executive_summary(ticker, rating, grouped, metrics_packet),
        "",
        "## Investment Thesis",
        investment_thesis,
        "",
        "## Current Period KPIs",
        _paragraphs(current_kpi_claims, limit=5),
        "",
        *(
            [
                "## Operating Drivers & Capital Allocation",
                _operating_driver_section(operating_driver_claims),
                "",
            ]
            if operating_driver_claims
            else []
        ),
        "## Fundamental Analysis",
        _paragraphs(fundamental_claims, limit=5),
        "",
        "## Free Cash Flow Definitions",
        _fcf_definition_reconciliation(evidence_ledger, currency=currency),
        "",
        *(
            [
                "## Projected FCF Guidance Bridge",
                projected_fcf_bridge,
                "",
            ]
            if projected_fcf_bridge
            else []
        ),
        *(
            [
                "## Capital Allocation, Transactions & Contingencies",
                _paragraphs(
                    grouped.get("Capital Allocation, Transactions & Contingencies", []),
                    limit=8,
                ),
                "",
            ]
            if grouped.get("Capital Allocation, Transactions & Contingencies")
            else []
        ),
        "## Valuation / Risk-Reward",
        _paragraphs(grouped.get("Valuation / Multiples", []), limit=3),
        "",
        "## Scenario / Sensitivity",
        _valuation_scenario_table(
            v,
            rating,
            currency=currency,
            evidence_ledger=evidence_ledger,
        ),
        "",
        "## Technical Setup",
        _paragraphs(grouped.get("Technical Setup", []), limit=3),
        "",
        "## Bull Case",
        "\n\n".join(
            part
            for part in (
                _paragraphs(grouped.get("Bull Case", []), limit=3),
                _issuer_specific_operating_test(
                    operating_driver_claims,
                    heading="Issuer-specific confirmation path",
                ),
            )
            if part
        ),
        "",
        "## Bear Case",
        _paragraphs(grouped.get("Bear Case", []), limit=3),
        "",
        *(
            [
                "## Material Events & Governance",
                _paragraphs(grouped.get("Material Events & Governance", []), limit=6),
                "",
            ]
            if grouped.get("Material Events & Governance")
            else []
        ),
        "## Risks",
        _paragraphs(grouped.get("Key Risks", []), limit=5),
        "",
        "## Catalysts",
        _paragraphs(grouped.get("Catalysts & Triggers", []), limit=4),
        "",
        "## Final Rating & Review Conditions",
        "\n\n".join(
            part
            for part in (
                _final_rating_section(
                    ticker,
                    rating,
                    f,
                    v,
                    t,
                    decision_packet,
                    currency=currency,
                ),
                _required_claim_bindings(
                    grouped.get("Final Rating & Action Plan", []),
                    limit=2,
                ),
            )
            if part
        ),
        "",
        "## Evidence Appendix",
        _evidence_appendix(claim_list, evidence_ledger),
    ]
    return "\n".join(section for section in sections if section is not None).strip() + "\n"


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
        evidence_reference = _claim_evidence_reference(claim)
        if evidence_reference:
            text = f"{text} {evidence_reference}"
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _required_claim_bindings(claims: list[ResearchClaim], limit: int) -> str:
    """Render required section-local provenance without duplicating synthesis."""

    bindings = [
        f"**Formal rating evidence binding:** {_claim_evidence_reference(claim)}"
        for claim in claims
        if claim.claim_id and claim.evidence_ids
    ][:limit]
    return "\n\n".join(bindings)


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
        evidence_reference = _claim_evidence_reference(claim)
        if evidence_reference:
            text = f"{text} {evidence_reference}"
        paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _claim_evidence_reference(claim: ResearchClaim, limit: int | None = None) -> str:
    evidence_ids = [str(item) for item in claim.evidence_ids if str(item).strip()]
    if not evidence_ids:
        return ""
    selected = evidence_ids if limit is None else evidence_ids[:limit]
    claim_id = str(claim.claim_id or "UNIDENTIFIED_CLAIM")
    return (
        f"<!-- room16-lineage claim={claim_id} "
        f"evidence={','.join(selected)} -->"
    )


def _combined_evidence_reference(
    claims: list[ResearchClaim], limit: int | None = None
) -> str:
    evidence_ids: list[str] = []
    for claim in claims:
        for item in claim.evidence_ids:
            value = str(item).strip()
            if value and value not in evidence_ids:
                evidence_ids.append(value)
            if limit is not None and len(evidence_ids) >= limit:
                return f"Evidence: `{', '.join(evidence_ids)}`."
    return f"Evidence: `{', '.join(evidence_ids)}`." if evidence_ids else ""


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
    technical_basis_verified = (
        metrics.technical.price_series_basis in TECHNICAL_SCORING_BASES
    )
    if technical_basis_verified:
        technical = (
            f"Technically, {ticker} carries an RSI of "
            f"{_fmt_number(metrics.technical.rsi_14)} with price at "
            f"{_fmt_number(metrics.technical.close)}, so verified timing remains "
            "a separate review overlay."
        )
        debate = "valuation, cash-flow conversion and verified timing risk"
    else:
        technical = (
            "Technical inputs are unscored raw observations. They do not enter "
            "the rating or timing until corporate-action adjustment of the price "
            "series is confirmed."
        )
        debate = "valuation and cash-flow conversion"
    return (
        f"{current}\n\nThe resulting stance is {rating}: the report weighs "
        f"current fundamentals against {debate}. {technical}"
    )


def _current_kpi_claims(claims: list[ResearchClaim]) -> list[ResearchClaim]:
    return [
        claim
        for claim in claims
        if (claim.section or "") in CURRENT_PERIOD_SECTIONS
        and (claim.section or "") != "Catalysts & Triggers"
        and (
            any(
                metric.startswith("current_period_") or "guidance" in metric
                for metric in claim.metric_refs
            )
            or CURRENT_PERIOD_MARKER_RE.search(_claim_text(claim)) is not None
        )
        and any(char.isdigit() for char in _claim_text(claim))
    ]


def _operating_driver_claims(
    claims: list[ResearchClaim],
) -> list[tuple[str, ResearchClaim]]:
    """Select one source-bound current operating claim per material driver.

    The selection is deliberately semantic instead of ticker-specific. It only
    considers claims produced from the structured operating-KPI adapter and
    prefers claims whose metrics are dedicated to the requested driver over
    mixed context blocks. This keeps the readable report short while ensuring
    that material operating evidence does not disappear into the appendix.
    """

    candidates = [
        claim
        for claim in claims
        if (claim.section or "") == "Business & Segment Context"
        and any(metric.startswith("operating_kpi_") for metric in claim.metric_refs)
        and any(char.isdigit() for char in _claim_text(claim))
    ]
    selected: list[tuple[str, ResearchClaim]] = []
    used_claim_ids: set[str] = set()
    for label, pattern in OPERATING_DRIVER_PATTERNS.items():
        matching = [
            claim
            for claim in candidates
            if claim.claim_id not in used_claim_ids
            and pattern.search(_claim_text(claim)) is not None
        ]
        if not matching:
            continue
        claim = max(matching, key=lambda item: _operating_driver_score(label, item))
        selected.append((label, claim))
        used_claim_ids.add(claim.claim_id)
    return selected


def _operating_driver_score(
    label: str,
    claim: ResearchClaim,
) -> tuple[int, float, int, int, int]:
    metric_markers = OPERATING_DRIVER_METRIC_MARKERS[label]
    operating_metrics = [
        metric for metric in claim.metric_refs if metric.startswith("operating_kpi_")
    ]
    direct_metrics = [
        metric
        for metric in operating_metrics
        if any(marker in metric for marker in metric_markers)
    ]
    direct_ratio = len(direct_metrics) / max(len(operating_metrics), 1)
    text = _claim_text(claim)
    category_materiality = 0
    if label == "Capital allocation":
        aggregate_return = int(
            re.search(
                r"\b(?:returned?|returning)\b.{0,100}\bshareholders?\b",
                text,
                re.IGNORECASE,
            )
            is not None
        )
        allocation_components = sum(
            int(re.search(pattern, text, re.IGNORECASE) is not None)
            for pattern in (
                r"\b(?:share|stock) repurchases?\b",
                r"\bcash dividends?\b",
            )
        )
        category_materiality = aggregate_return * 10 + allocation_components
    term_count = len(
        {
            match.group(0).casefold()
            for match in OPERATING_DRIVER_PATTERNS[label].finditer(text)
        }
    )
    numeric_count = len(
        re.findall(
            r"(?:[$€£]\s*)?\d[\d,.]*\s*(?:%|million|billion|basis points?)?",
            text,
            re.IGNORECASE,
        )
    )
    return category_materiality, direct_ratio, term_count, -len(text), numeric_count


def _operating_driver_section(
    selected: list[tuple[str, ResearchClaim]],
) -> str:
    if not selected:
        return "No source-bound current operating drivers are available."
    return "\n".join(
        f"- **{label}:** {_clean_text(_claim_text(claim))} "
        f"{_claim_evidence_reference(claim)}"
        for label, claim in selected
    )


def _generic_investment_thesis(
    ticker: str,
    rating: str,
    metrics: MetricsPacket,
    decision: DecisionPacket,
    *,
    operating_driver_claims: list[tuple[str, ResearchClaim]] | None = None,
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
        if (
            fundamentals.sbc_to_fcf is not None
            and fundamentals.sbc_to_fcf >= 1
        ):
            cash_text = (
                f"positive FCF of {_fmt_money(fundamentals.free_cash_flow_ttm, currency)} "
                f"is measured, but SBC equals {_fmt_pct(fundamentals.sbc_to_fcf)} "
                "of FCF and therefore qualifies shareholder-level cash conversion"
            )
        else:
            cash_text = (
                f"positive FCF of {_fmt_money(fundamentals.free_cash_flow_ttm, currency)} "
                "provides measured cash-conversion support"
            )
    else:
        cash_text = "FCF is unavailable and cannot support the thesis"
    current_profit_decline = bool(
        current_operating_profit_decline_metrics(fundamentals)
    )
    if current_profit_decline:
        if fundamentals.free_cash_flow_ttm is None:
            fundamental_text = (
                "pressured but incomplete fundamental picture driven by weaker "
                "current-period profit comparisons and unavailable FCF"
            )
        elif fundamentals.free_cash_flow_ttm > 0:
            fundamental_text = (
                "mixed fundamental picture: positive FCF alongside weaker "
                "current-period profit comparisons"
            )
        else:
            fundamental_text = (
                "pressured fundamental picture: weaker current-period profit "
                "comparisons without positive FCF support"
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
    technical_basis_verified = (
        metrics.technical.price_series_basis in TECHNICAL_SCORING_BASES
    )
    valuation_text = _valuation_status_label(scores.valuation_status)
    if technical_basis_verified:
        evidence_mix = (
            f"The {rating} stance combines a {fundamental_text} with "
            f"{scores.technical_status} verified technical evidence and "
            f"{valuation_text} valuation evidence."
        )
    else:
        evidence_mix = (
            f"The {rating} stance combines a {fundamental_text} with "
            f"{valuation_text} valuation evidence. Technical inputs are excluded "
            "from rating and timing because the price-series adjustment is unconfirmed."
        )
    core = (
        f"{ticker}'s central investment debate is whether revenue scale of "
        f"{_fmt_money(fundamentals.revenue_ttm, currency)} can translate into durable cash "
        f"generation; {cash_text}. {evidence_mix}"
    )
    operating_test = _issuer_specific_operating_test(
        operating_driver_claims or [],
        heading="Issuer-specific proof test",
    )
    return "\n\n".join(part for part in (core, operating_test) if part)


def _issuer_specific_operating_test(
    selected: list[tuple[str, ResearchClaim]],
    *,
    heading: str,
) -> str:
    preferred = [
        item
        for item in selected
        if item[0] in {"Pricing / yield", "Volume", "Margin", "Integration effects"}
    ][:4]
    if not preferred:
        preferred = selected[:3]
    if not preferred:
        return ""
    is_confirmation = "confirmation" in heading.casefold()
    observations: list[str] = []
    for label, claim in preferred:
        source_text = _clean_internal_text(_claim_text(claim))
        source_text = re.split(r"(?<=[.!?])\s+", source_text, maxsplit=1)[0].strip()
        source_text = source_text.rstrip(".!?")
        observations.append(
            f"**{label}:** Reported evidence: {source_text}; "
            + (
                "The next comparable filing must confirm that direction."
                if is_confirmation
                else "This is the source-bound operating test for the thesis."
            )
            + f" {_claim_evidence_reference(claim)}"
        )
    conclusion = (
        "A stronger case requires these issuer-bound signals to confirm one another "
        "and continue converting into cash."
        if is_confirmation
        else "The thesis weakens if these source-bound drivers stop persisting or no "
        "longer translate into cash conversion."
    )
    return "\n".join(
        [f"**{heading}.**", *observations, conclusion]
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
    technical_basis_verified = t.price_series_basis in TECHNICAL_SCORING_BASES
    rating_reason = (
        decision_packet.analytical_rating_reason
        or decision_packet.rating_permission.reason
    )
    if scores.valuation_status == "unbenchmarked":
        available_valuation = [
            f"{label} of {_fmt_multiple(value)}"
            for label, value in (
                ("EV/Sales", v.ev_to_sales),
                ("P/FCF", v.price_to_fcf),
                ("trailing P/E", v.trailing_pe),
                ("forward P/E consensus", v.forward_pe_consensus),
                ("forward P/E guidance", v.forward_pe_guidance),
            )
            if value is not None
        ]
        if available_valuation:
            valuation_subject = " and ".join(available_valuation)
            valuation_text = (
                f"{valuation_subject} "
                f"{'is an unbenchmarked observation' if len(available_valuation) == 1 else 'are unbenchmarked observations'}. "
                f"{'It adds' if len(available_valuation) == 1 else 'They add'} neither "
                "a positive nor a negative rating signal."
            )
        else:
            valuation_text = (
                "No measured valuation multiple is available; unbenchmarked "
                "valuation cannot move the rating."
            )
    elif scores.valuation_status in {"scenario_measured", "illustrative_only"}:
        sensitivity = v.sensitivity
        qualifier = (
            "company-calibrated scenario evidence"
            if scores.valuation_status == "scenario_measured"
            else "an uncalibrated illustration outside the rating logic"
        )
        valuation_text = (
            "The standardized equity-DCF range is "
            f"{_fmt_money(sensitivity.model_range_low, currency)} to "
            f"{_fmt_money(sensitivity.model_range_high, currency)}. It is "
            f"{qualifier} and does not create an automatic rating signal."
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
        if t.price_series_basis == "post_corporate_action_only":
            direction = (
                "bullish"
                if scores.technical_score > 0
                else "bearish"
                if scores.technical_score < 0
                else "neutral"
            )
            technical_text = (
                f"{direction} on a series bounded after the latest identified "
                "corporate action; longer-horizon comparisons remain limited"
            )
        else:
            technical_text = (
                "not activated because corporate-action adjustment is not "
                "confirmed; raw indicators remain provisional observations"
            )
    else:
        technical_text = "not measured"
    if f.free_cash_flow_ttm is not None and f.free_cash_flow_ttm < 0:
        confirmation_limits = []
        if scores.valuation_status != "measured":
            confirmation_limits.append(
                f"valuation is {scores.valuation_status}"
            )
        if scores.risk_status != "measured":
            confirmation_limits.append(
                f"the issuer-risk basis is {scores.risk_status}"
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
        f.free_cash_flow_ttm is None
        and current_operating_profit_decline_metrics(f)
    ):
        decline_metrics = set(current_operating_profit_decline_metrics(f))
        decline_labels = [
            label
            for label, metric_name in (
                (
                    "operating-income",
                    "current_period_operating_income_growth_yoy",
                ),
                ("net-income", "current_period_net_income_growth_yoy"),
            )
            if metric_name in decline_metrics
        ]
        decline_text = " and ".join(decline_labels)
        decline_subject = f"{decline_text} {'decline' if len(decline_labels) == 1 else 'declines'}"
        decline_verb = "is" if len(decline_labels) == 1 else "are"
        why_not_constructive = (
            f"Why not more constructive? Current-period {decline_subject} "
            f"{decline_verb} current downside evidence. FCF is unavailable, so cash conversion "
            "cannot offset or confirm the reported weakness. A more constructive "
            "rating requires improving profit comparisons and measurable cash-flow "
            "support."
        )
        why_not_cautious = (
            f"Why not more cautious? The {decline_subject} {decline_verb} not dismissed."
            " One reported period does not establish "
            "the cause or durability of the weakness; a more cautious rating "
            "requires persistence or corroborating cash-flow deterioration once "
            "cash conversion is measurable."
        )
    elif (
        f.equity is not None
        and f.equity <= 0
        and f.free_cash_flow_ttm is not None
        and f.free_cash_flow_ttm > 0
        and not current_operating_profit_decline_metrics(f)
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
        and current_operating_profit_decline_metrics(f)
    ):
        decline_metrics = set(current_operating_profit_decline_metrics(f))
        decline_labels = [
            label
            for label, metric_name in (
                (
                    "operating-income",
                    "current_period_operating_income_growth_yoy",
                ),
                ("net-income", "current_period_net_income_growth_yoy"),
            )
            if metric_name in decline_metrics
        ]
        decline_text = " and ".join(decline_labels)
        decline_subject = f"{decline_text} {'decline' if len(decline_labels) == 1 else 'declines'}"
        decline_verb = "is" if len(decline_labels) == 1 else "are"
        why_not_constructive = (
            f"Why not more constructive? Current-period {decline_subject} "
            f"{decline_verb} current downside evidence; positive FCF does not erase those "
            "reported comparisons. A more constructive rating requires profit "
            "comparisons to improve, that improvement to persist, and benchmarked "
            "valuation support."
        )
        why_not_cautious = (
            f"Why not more cautious? The {decline_subject} {decline_verb} not dismissed, "
            "but positive FCF is measured counterevidence. "
            "A more cautious rating requires the profit weakness to persist or be "
            "corroborated by weaker cash conversion."
        )
    elif (
        f.free_cash_flow_ttm is not None
        and f.free_cash_flow_ttm > 0
        and scores.fundamental_score > 0
    ):
        why_not_constructive = (
            (
                "Why not more constructive? Constructive fundamentals and positive "
                "FCF are not enough without calibrated valuation support. Verified "
                "technical direction can affect timing confidence but not the "
                "company rating."
            )
            if technical_basis_verified
            else (
                "Why not more constructive? Constructive fundamentals and positive "
                "FCF are not enough without calibrated valuation support. Technical "
                "timing is unavailable until the price-series basis is confirmed."
            )
        )
        why_not_cautious = (
            "Why not more cautious? Positive FCF and the constructive fundamental "
            "signal are measured counterevidence. A more cautious rating requires "
            "corroborating fundamental, valuation or issuer-risk deterioration."
        )
    else:
        why_not_constructive = (
            (
                "Why not more constructive? A rating change requires stronger "
                "measured fundamentals and calibrated valuation support. Verified "
                "technical confirmation can improve timing confidence but cannot "
                "change the company rating."
            )
            if technical_basis_verified
            else (
                "Why not more constructive? A rating change requires stronger "
                "measured fundamentals and calibrated valuation support. Technical "
                "timing is unavailable until the price-series basis is confirmed."
            )
        )
        why_not_cautious = (
            "Why not more cautious? A raw multiple or an isolated price signal cannot "
            "establish business deterioration."
        )
    current_risk_context = _current_risk_rating_context(decision_packet)
    if current_risk_context:
        why_not_cautious = f"{why_not_cautious} {current_risk_context}"
    fcf_anchor = (
        f"FCF of {_fmt_money(f.free_cash_flow_ttm, currency)}"
        if f.free_cash_flow_ttm is not None
        else "FCF unavailable"
    )
    technical_anchor = (
        f"Separately, the verified technical timing overlay has RSI of "
        f"{_fmt_number(t.rsi_14)} and direction {technical_text}; it does not "
        "enter the long-term composite score."
        if technical_basis_verified
        else (
            f"Separately, raw technical observations include RSI of "
            f"{_fmt_number(t.rsi_14)}; direction and timing are {technical_text}."
        )
    )
    review_condition = (
        f"Review condition: retain the {ticker} research rating while the measured "
        "evidence state is unchanged. Reassess only when new primary evidence "
        "changes fundamentals, calibrated valuation or issuer risk; reassess "
        "timing separately when the verified technical trend changes."
        if technical_basis_verified
        else (
            f"Review condition: retain the {ticker} research rating while the "
            "measured evidence state is unchanged. Reassess only when new primary "
            "evidence changes fundamentals, calibrated valuation or issuer risk. "
            "Technical timing remains unavailable until the price-series basis is "
            "confirmed."
        )
    )
    return "\n\n".join(
        [
            f"Final Rating: {rating}. {rating_reason}",
            (
                f"Factual anchors are revenue of {_fmt_money(f.revenue_ttm, currency)}, "
                f"{fcf_anchor}. {technical_anchor}"
            ),
            valuation_text,
            why_not_constructive,
            why_not_cautious,
            review_condition,
        ]
    )


def _current_risk_rating_context(decision_packet: DecisionPacket) -> str:
    risks = [
        item
        for item in decision_packet.decision_inputs
        if item.input_type == "current_risk"
    ][:3]
    if not risks:
        return ""
    labels = [
        named_current_risk_label(
            str(item.summary or ""),
            fallback=str(item.label or item.input_id),
        ).rstrip(".")
        for item in risks
    ]
    return (
        "The rating already monitors these named current risks: "
        + "; ".join(labels)
        + ". A more cautious rating requires new primary evidence that their "
        "reserve, compliance, operating or cash-flow transmission outweighs "
        "the measured counterevidence; an issuer counterposition is context, "
        "not independent proof."
    )


def _valuation_scenario_table(
    v,
    rating: str,
    *,
    currency: str,
    evidence_ledger: EvidenceLedger,
) -> str:
    scenarios = v.sensitivity.scenarios
    if not scenarios:
        return (
            "| Scenario | KPI trigger | Valuation implication | Rating implication |\n"
            "|---|---|---|---|\n"
            "| Constructive | Cash-flow evidence improves | Benchmark evidence would need to show valuation support | The rating would become more constructive if primary evidence supports the change |\n"
            "| Current | Measured evidence remains unchanged | Unbenchmarked multiples remain observations only | Retain the current research rating |\n"
            "| Cautious | Fundamentals deteriorate | Missing valuation support would weaken the case | Reassess toward a more cautious rating |"
        )
    rating_implications = {
        "bear": "Would weaken the case only if primary evidence supports the adverse assumptions",
        "base": f"No automatic change to the current {rating} research rating",
        "bull": "The rating would become more constructive if primary evidence supports the assumptions",
    }
    lines = [
        "| Scenario | FCF growth | Discount rate | Terminal growth | Valuation implication | Rating implication |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for scenario in scenarios:
        lines.append(
            f"| {scenario.name.title()} | {scenario.free_cash_flow_growth_rate:.1%} | "
            f"{scenario.discount_rate:.1%} | {scenario.terminal_growth_rate:.1%} | "
            f"Equity value {_fmt_money(scenario.equity_value, currency)} | "
            f"{rating_implications[scenario.name]} |"
        )
    lines.append(
        "\nThe table is a standardized sensitivity, not management guidance or a precise price target."
    )
    evidence_ids = [
        item.evidence_id
        for item in evidence_ledger.evidence_items
        if any(metric.startswith("dcf_") for metric in item.supports_metrics)
    ]
    lines.append(
        "<!-- room16-table-lineage id=DCF_SCENARIO_VIEW evidence="
        + ",".join(dict.fromkeys(evidence_ids))
        + " -->"
    )
    return "\n".join(lines)


def _evidence_appendix(claims: list[ResearchClaim], evidence_ledger: EvidenceLedger) -> str:
    def display_label(value: object) -> str:
        return re.sub(r"[_-]+", " ", str(value or "")).strip()

    evidence_by_id = {item.evidence_id: item for item in evidence_ledger.evidence_items}
    lines = [
        (
            "The complete claim text, evidence IDs, metric mappings and source IDs are "
            "stored in the separately hash-bound `analyst_claims.json`. This appendix is "
            "the compact human-readable index."
        ),
        "",
        "| Claim ID | Section | Claim Type | Evidence Count | Source Types | Confidence |",
        "|---|---|---|---:|---|---|",
    ]
    for claim in claims:
        source_types = sorted({
            evidence_by_id[item_id].source_type
            for item_id in claim.evidence_ids
            if item_id in evidence_by_id
        })
        claim_type = getattr(claim.claim_type, "value", claim.claim_type)
        lines.append(
            "| {claim_id} | {section} | {claim_type} | {evidence_count} | "
            "{source_types} | {confidence} |".format(
                claim_id=_table_text(claim.claim_id or ""),
                section=_table_text(claim.section or "Unassigned"),
                claim_type=_table_text(display_label(claim_type)),
                evidence_count=len(claim.evidence_ids),
                source_types=_table_text(", ".join(display_label(item) for item in source_types)),
                confidence=_table_text(str(claim.confidence or "")),
            )
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
    return f"{main.rstrip()}\n\n## Evidence Appendix{appendix}"


def _table_text(text: str) -> str:
    return _clean_text(text).replace("|", "\\|")


def _measurement_window(start: str | None, end: str | None, fallback: str) -> str:
    """Render an interval as reader-facing prose, not internal range syntax."""
    if start and end:
        return f"{start} to {end}"
    return re.sub(
        r"\b(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})\b",
        r"\1 to \2",
        fallback,
    )


def _fcf_definition_reconciliation(
    evidence_ledger: EvidenceLedger,
    *,
    currency: str,
) -> str:
    normalized = [
        item
        for item in evidence_ledger.evidence_items
        if "free_cash_flow_ttm" in item.supports_metrics
        and item.value is not None
        and item.formula_id
    ]
    issuer = [
        item
        for item in evidence_ledger.evidence_items
        if item.value is not None
        and item.provenance_class == "primary_source"
        and any(
            "free_cash_flow" in metric
            for metric in item.supports_metrics
        )
        and not item.formula_id
    ]
    lines = [
        "| Definition | Measurement window | Value | Use in this report |",
        "|---|---|---:|---|",
    ]
    if normalized:
        item = sorted(normalized, key=lambda value: value.evidence_id)[0]
        normalized_window = _measurement_window(
            item.period_start,
            item.period_end,
            item.period or "TTM",
        )
        lines.append(
            "| Room16 normalized FCF (operating cash flow minus capital expenditure) "
            f"| {normalized_window} | {_fmt_money(item.value, item.currency or currency)} "
            "| Valuation denominator and normalized cash-conversion analysis |"
        )
    else:
        lines.append(
            "| Room16 normalized FCF | unavailable | unavailable | Not used until the formula is source-bound |"
        )
    guidance_items = [
        item
        for item in issuer
        if item.period_kind == "guidance"
        and any("guidance" in metric for metric in item.supports_metrics)
    ]
    guidance_by_window: dict[tuple[str, str, str], list[EvidenceItem]] = {}
    for item in guidance_items:
        key = (
            str(item.period_start or ""),
            str(item.period_end or item.date or ""),
            str(item.currency or currency).upper(),
        )
        guidance_by_window.setdefault(key, []).append(item)
    guidance_used_ids: set[str] = set()
    for (start, end, row_currency), items in sorted(guidance_by_window.items(), reverse=True):
        values = sorted({float(item.value) for item in items if item.value is not None})
        if len(values) < 2:
            continue
        guidance_used_ids.update(item.evidence_id for item in items)
        lines.append(
            f"| Issuer-defined FCF guidance | {_measurement_window(start, end, 'period not mapped')} | "
            f"{_fmt_money(values[0], row_currency)}–{_fmt_money(values[-1], row_currency)} | "
            "Forward-looking issuer range; not substituted for normalized TTM FCF |"
        )

    seen_issuer_rows: set[tuple[str, float, str]] = set()
    issuer_rows: list[EvidenceItem] = []
    for item in sorted(
        issuer,
        key=lambda value: (value.period_end or value.date or "", value.evidence_id),
        reverse=True,
    ):
        if item.evidence_id in guidance_used_ids:
            continue
        row_key = (
            str(item.period_end or item.date or "period not mapped"),
            float(item.value),
            str(item.currency or currency).upper(),
        )
        if row_key in seen_issuer_rows:
            continue
        seen_issuer_rows.add(row_key)
        issuer_rows.append(item)
        if len(issuer_rows) == 3:
            break
    for item in issuer_rows:
        measurement_window = _measurement_window(
            item.period_start,
            item.period_end,
            item.period or item.period_kind or "period not mapped",
        )
        lines.append(
            "| Issuer-defined FCF | "
            f"{measurement_window} | "
            f"{_fmt_money(item.value, item.currency or currency)} | "
            "Issuer presentation only; not substituted for normalized TTM FCF without a period-matched bridge |"
        )
    lines.append(
        "Room16 and issuer-defined FCF are separate measures. Differences can reflect measurement windows, "
        "capital-expenditure definitions, sustainability investments or other issuer adjustments."
    )
    evidence_ids = [item.evidence_id for item in [*normalized[:1], *guidance_items, *issuer_rows]]
    if evidence_ids:
        lines.append(
            "<!-- room16-table-lineage id=FCF_DEFINITION_RECONCILIATION evidence="
            + ",".join(evidence_ids)
            + " -->"
        )
    return "\n".join(lines)


def _projected_fcf_guidance_bridge(
    evidence_ledger: EvidenceLedger,
    *,
    currency: str,
) -> str:
    prefix = "guidance_fcf_bridge_"
    values: dict[str, EvidenceItem] = {}
    for item in evidence_ledger.evidence_items:
        if item.value is None:
            continue
        for metric in item.supports_metrics:
            if metric.startswith(prefix):
                values[metric.removeprefix(prefix)] = item
    if not values:
        return ""
    components = (
        ("Operating cash flow", "operating_cash_flow"),
        ("Support capital expenditure", "support_capex"),
        ("Divestiture proceeds", "divestiture_proceeds"),
        ("FCF before sustainability growth", "fcf_before_sustainability_growth"),
        ("Sustainability-growth capital expenditure", "sustainability_growth_capex"),
        ("Issuer-defined free cash flow", "free_cash_flow"),
    )
    required = {
        f"{metric}_scenario_{scenario}"
        for _, metric in components
        for scenario in (1, 2)
    }
    missing = required - set(values)
    if missing:
        raise ValueError(
            "projected FCF guidance bridge evidence is incomplete: "
            + ", ".join(sorted(missing))
        )
    lines = [
        "| Issuer bridge component | Scenario 1 | Scenario 2 |",
        "|---|---:|---:|",
    ]
    for label, metric in components:
        first = values[f"{metric}_scenario_1"]
        second = values[f"{metric}_scenario_2"]
        lines.append(
            f"| {label} | {_fmt_money(first.value, first.currency or currency)} "
            f"| {_fmt_money(second.value, second.currency or currency)} |"
        )
    checks: list[str] = []
    for scenario in (1, 2):
        def amount(metric: str) -> float:
            return float(values[f"{metric}_scenario_{scenario}"].value or 0.0)

        pre_growth = (
            amount("operating_cash_flow")
            + amount("support_capex")
            + amount("divestiture_proceeds")
        )
        final_fcf = pre_growth + amount("sustainability_growth_capex")
        checks.append(
            "PASS"
            if abs(pre_growth - amount("fcf_before_sustainability_growth")) <= 1.0
            and abs(final_fcf - amount("free_cash_flow")) <= 1.0
            else "FAIL"
        )
    if checks != ["PASS", "PASS"]:
        raise ValueError("projected FCF guidance bridge arithmetic does not reconcile")
    lines.append(
        "Both issuer scenarios reconcile arithmetically. These forward-looking "
        "non-GAAP scenarios remain separate from Room16 normalized trailing-twelve-month FCF."
    )
    evidence_ids = list(
        dict.fromkeys(
            values[key].evidence_id
            for key in sorted(required)
        )
    )
    lines.append(
        "<!-- room16-table-lineage id=PROJECTED_FCF_GUIDANCE_BRIDGE evidence="
        + ",".join(evidence_ids)
        + " -->"
    )
    return "\n".join(lines)


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


def _valuation_status_label(status: str) -> str:
    labels = {
        "measured": "calibrated",
        "scenario_measured": "company-calibrated scenario",
        "illustrative_only": "illustrative-only",
        "unbenchmarked": "unbenchmarked",
        "not_measured": "not-sufficiently-measured",
    }
    return labels.get(status, "review-pending")


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
    if fundamentals.cash_and_investments is not None:
        return fundamentals.cash_and_investments
    components = (
        fundamentals.cash_and_equivalents,
        fundamentals.short_term_investments,
        fundamentals.marketable_securities,
    )
    if all(value is None for value in components):
        return None
    return sum(value or 0.0 for value in components)


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
