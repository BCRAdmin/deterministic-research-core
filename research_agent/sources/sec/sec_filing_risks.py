from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source


_BLOCK_TAGS = {"br", "div", "h1", "h2", "h3", "h4", "li", "p", "table", "tr"}
_ITEM_HEADING = re.compile(r"^item\s+\d+[a-z]?(?:[.\s]|$)", re.IGNORECASE)
_RISK_LANGUAGE = re.compile(
    r"\b(could|may|might|failure|fail|unable|adverse|adversely|competition|"
    r"volatility|volatile|uncertain|uncertainty|unpredictable|risk|risks|"
    r"harm|harmed|strain|fraudulent|unlawful|"
    r"voting|concentrat(?:e|es|ed|ing|ion)|founders?|"
    r"fluctuations?|loss|losses|liabilit(?:y|ies)|suffer|suffers|unsuccessful|"
    r"expose|exposes|subject to|subjects us to|presents a number of risks)\b",
    re.IGNORECASE,
)
_GENERIC_RISK_CATEGORY = re.compile(
    r"^(?:(?!(?:we|our|the company)\b)[a-z,& -]+ risks?|"
    r"risks? (?:specific|applicable) to (?:our|the) company|"
    r"(?:other )?(?:risks?|risk factors?) (?:related|relating|associated) "
    r"(?:to|with)\b.+)$",
    re.IGNORECASE,
)
_GENERIC_PREFIXES = (
    "if any of the following risks",
    "if any of the risks described",
    "our business results are subject",
    "the risks described below",
    "the following is a summary",
    "risk factors should be read",
    "for a discussion of risk factors",
    "for a more complete discussion",
)
_GENERIC_RISK_HEADINGS = {
    "generalriskfactors",
    "riskfactorsgenerally",
    "riskfactorsummary",
    "riskfactorssummary",
    "summaryofriskfactors",
}
_RISK_DIVERSITY_PATTERNS = (
    re.compile(
        r"\b(?:multi(?:ple)?[- ]class|founder voting|voting power|controlled company|"
        r"corporate governance|stockholder approval)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:cyber|security breach|privacy|personal data)\b", re.IGNORECASE),
    re.compile(r"\b(?:regulat|legal proceedings|compliance|government polic)\w*\b", re.IGNORECASE),
    re.compile(r"\b(?:customer concentration|customer contracts?|sales cycle|deal value)\b", re.IGNORECASE),
    re.compile(r"\b(?:competition|competitive position|new technolog|artificial intelligence|\bAI\b)\b", re.IGNORECASE),
    re.compile(r"\b(?:personnel|employee|management|key person|retain|recruit)\w*\b", re.IGNORECASE),
    re.compile(r"\b(?:debt|financ|liquidity|capital resources|cash flow)\w*\b", re.IGNORECASE),
    re.compile(r"\b(?:international|foreign|geopolit|supply chain|third part|vendor)\w*\b", re.IGNORECASE),
)
_NON_RISK_DOCUMENT_HEADINGS = {
    "analysisoffinancialconditionandresultsofoperations",
    "criticalaccountingestimates",
    "liquidityandcapitalresources",
    "managementsdiscussionandanalysisoffinancialconditionandresultsofoperations",
    "quantitativeandqualitativedisclosuresaboutmarketrisk",
    "resultsofoperations",
}
_RISK_SECTION_END = re.compile(
    r"^(?:LEGAL PROCEEDINGS|MINE SAFETY DISCLOSURES|PROPERTIES|"
    r"UNRESOLVED STAFF COMMENTS)(?:[.:]|$)"
)
_BUSINESS_ABOUT_HEADING = re.compile(r"^ABOUT [A-Z][A-Z0-9&.,'’ -]{1,80}[.]\s+")
_TITLE_CASE_CONNECTORS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "our",
    "the",
    "to",
    "with",
}
_BUSINESS_LANGUAGE = re.compile(
    r"\b(business|customer|customers|develop|develops|offer|offers|operate|operating|"
    r"operation|operations|"
    r"product|products|service|services|solution|solutions|platform|platforms|"
    r"segment|segments|software|subscription|subscriptions|device|devices|"
    r"deliver|delivers|delivery|freight|logistics|network|package|packages|"
    r"supply chain|transport|transportation|"
    r"explore|explores|exploration|produce|produces|production|crude oil|"
    r"natural gas|bitumen|liquefied natural gas|lng|"
    r"manufacture|manufactures|distribute|distributes|market|markets|roast|"
    r"roaster|retail|retailer|sell|sells|store|stores|coffee)\b",
    re.IGNORECASE,
)
_BUSINESS_MODEL_LANGUAGE = re.compile(
    r"\b(franchis(?:e|es|ed|ing|or|ors|ee|ees)|restaurant|restaurants)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_IDENTITY = re.compile(
    r"^(?:we|the company|the issuer)\s+(?:are|is)\s+"
    r"(?:(?:one of the|a|an)\s+)?"
    r"(?:(?:leading|global|major|largest|specialty)\s+)?"
    r"(?:provider|manufacturer|operator|developer|retailer|franchisor|"
    r"(?:(?:[a-z]+|&)\s+){1,6}company)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_AS_IDENTITY = re.compile(
    r"^as\s+(?:an?|one of the)\s+.{0,100}\b"
    r"(?:airline|company|developer|manufacturer|operator|provider|retailer)\b"
    r".{0,100},\s+(?:we|the company|the issuer)\s+"
    r"(?:build|connect|create|deliver|design|develop|distribute|manufacture|"
    r"market|offer|operate|provide|sell|serve)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_NAMED_IDENTITY = re.compile(
    r"^(?!(?:We|Our)\b)[A-Z][A-Za-z0-9&.,'’ -]{1,60}\s+(?:is|are)\s+"
    r"(?:now\s+)?"
    r"(?:(?:one of the|a|an)\s+)?"
    r"(?:collection of businesses|group of companies|holding company|"
    r"provider|manufacturer|operator|developer|retailer|franchisor|"
    r"(?:(?:[A-Za-z&]+)\s+){1,6}company)\b"
)
_BUSINESS_CONTEXT_NAMED_LEADER_IDENTITY = re.compile(
    r"^(?!(?:We|Our|The)\b)[A-Z][A-Za-z0-9&.,'’ -]{1,60}\s+(?:is|are)\s+"
    r"(?:(?:one of the|a|an)\s+)?(?:(?:[A-Za-z&'’-]+)\s+){0,5}leader\b"
)
_BUSINESS_CONTEXT_PARENTHETICAL_IDENTITY = re.compile(
    r"^(?!(?:We|Our)\b)[A-Z][A-Za-z0-9&.,'’ -]{1,60}"
    r"\s+\([^)]{1,120}\)\s+(?:is|are)\s+"
    r"(?:(?:one of (?:the )?|a|an)\s+)?"
    r"(?:(?:[A-Za-z&'’-]+)\s+){0,6}"
    r"(?:leader|provider|operator|services?)\b"
)
_BUSINESS_CONTEXT_REVENUE_ACTIVITY = re.compile(
    r"^(?:(?:we|the company|the issuer)\s+"
    r"(?:generate|generates|derive|derives)\b.+\b"
    r"(?:revenue|revenues)\b.+\b(?:by|from)\b|"
    r"our\s+revenues?\s+(?:are|is)\s+(?:primarily\s+)?derived\b.+\bfrom\b)",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_SINGLE_SEGMENT = re.compile(
    r"^(?:we|the company|the issuer)\s+operate(?:s)?\s+"
    r"(?:(?:as\s+(?:one|a single)\s+(?:operating|reportable)\s+segment)|"
    r"(?:in\s+a single\s+segment))"
    r"(?:\s+engaged in\b.{20,240})?[.]?$",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_DIRECT_ACTIVITY = re.compile(
    r"^(?:we|the company|the issuer)\s+"
    r"(?:build|create|deliver|design|develop|distribute|explore|help|manufacture|"
    r"offer|operate|provide|sell|serve)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_CORE_OFFERING = re.compile(
    r"^(?:our|the company(?:'s)?|the issuer(?:'s)?)\s+"
    r"(?:(?:[A-Za-z0-9&.'’()-]+)\s+){0,5}"
    r"(?:products?(?:\s+and\s+services?)?|services?|offerings?|platforms?|suites?)\s+"
    r"(?:also\s+)?(?:include|includes|comprise|comprises|consist of|help|helps|"
    r"enable|enables|provide|provides|connect|connects|deliver|delivers)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_NAMED_ACTIVITY = re.compile(
    r"^(?!(?:The|We|Our)\b)[A-Z][A-Za-z0-9&.,'’() -]{1,90}\s+"
    r"(?:builds|creates|delivers|designs|develops|distributes|helps|"
    r"manufactures|offers|operates|provides|sells|serves)\b"
)
_BUSINESS_CONTEXT_NAMED_OFFERING = re.compile(
    r"^(?!(?:The|We|Our)\b)[A-Z][A-Za-z0-9&.,'’() -]{1,70}\s+"
    r"(?:products|services|platforms)(?:\s+and\s+(?:products|services|platforms))*\s+"
    r"(?:include|comprise)\b"
)
_BUSINESS_CONTEXT_SEGMENT_ACTIVITY = re.compile(
    r"^(?:the|our)\s+(?:[A-Za-z0-9&.'’()-]+\s+){0,5}segment"
    r"(?:,\s+which)?\s+(?:primarily\s+)?"
    r"(?:builds|creates|delivers|designs|develops|distributes|helps|"
    r"includes|comprises|consists of|manufactures|offers|operates|provides|"
    r"sells|serves)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_PROMOTIONAL_LANGUAGE = re.compile(
    r"\b(?:unmatched combination|unwavering focus|undisputable drive|"
    r"best possible service|best value|best network|"
    r"win in (?:its|our|their) markets|win together)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_SKIP_PREFIXES = (
    "accordingly",
    "as a result",
    "this report includes",
    "the following discussion",
    "information contained",
    "patents may cover",
    "see part",
    "additional information",
    "therefore",
    "driving",
)
_BUSINESS_CONTEXT_ACCOUNTING_LANGUAGE = re.compile(
    r"\b(?:segment information is prepared|chief operating decision maker|"
    r"evaluates financial results|makes key operating decisions)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_UNRESOLVED_REFERENCE = re.compile(
    r"\b(?:this|that|these|those|such) "
    r"(?:arrangements?|business|capabilities|customers?|markets?|products?|relationships?|segments?|services?)\b"
    r"|\b(?:see|refer to|under the heading)\b",
    re.IGNORECASE,
)
_BUSINESS_CONTEXT_ABBREVIATION = re.compile(
    r"\b(?:i\.e\.|e\.g\.|u\.s\.|u\.k\.|inc\.|corp\.|ltd\.|co\.)",
    re.IGNORECASE,
)
_PROTECTED_PERIOD = "\ue000"
_WRAPPED_LINE_END_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "by",
    "could",
    "for",
    "from",
    "in",
    "may",
    "might",
    "of",
    "on",
    "or",
    "our",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class SecFilingReference:
    cik: str
    form: str
    filing_date: str
    report_date: str
    accession_number: str
    primary_document: str
    url: str

    @property
    def source_id(self) -> str:
        accession = self.accession_number.replace("-", "")
        return f"SEC_CIK{str(int(self.cik)).zfill(10)}_{accession}"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class _SecTextBlocks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[tuple[str, bool]] = []
        self._parts: list[str] = []
        self._hidden_depth = 0
        self._bold_tags: list[str] = []
        self._bold_character_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._hidden_depth += 1
            return
        if tag in _BLOCK_TAGS:
            self._flush()
        style = str(dict(attrs).get("style") or "").lower().replace(" ", "")
        if (
            tag in {"b", "strong", "em", "i"}
            or "font-weight:700" in style
            or "font-weight:bold" in style
            or "font-style:italic" in style
        ):
            self._bold_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._hidden_depth = max(0, self._hidden_depth - 1)
            return
        if tag in _BLOCK_TAGS:
            self._flush()
        if tag in self._bold_tags:
            reverse_index = self._bold_tags[::-1].index(tag)
            self._bold_tags.pop(len(self._bold_tags) - 1 - reverse_index)

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth:
            self._parts.append(data)
            if self._bold_tags:
                self._bold_character_count += len(" ".join(data.split()))

    def finish(self) -> list[tuple[str, bool]]:
        self._flush()
        return self.blocks

    def _flush(self) -> None:
        text = " ".join(" ".join(self._parts).split())
        self._parts = []
        if text:
            emphasized = self._bold_character_count >= max(1, int(len(text) * 0.8))
            self.blocks.append((text, emphasized))
        self._bold_character_count = 0


def select_sec_risk_filing_candidates(
    submissions: dict[str, Any],
    *,
    cik: str,
    as_of_date: str,
) -> list[SecFilingReference]:
    """Return the latest filed 10-Q/10-K plus an annual fallback, never future data."""

    cutoff = date.fromisoformat(as_of_date)
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form") or []
    rows: list[SecFilingReference] = []
    for index, form in enumerate(forms):
        if form not in {"10-Q", "10-K"}:
            continue
        filing_date = _array_value(recent, "filingDate", index)
        report_date = _array_value(recent, "reportDate", index)
        accession = _array_value(recent, "accessionNumber", index)
        document = _array_value(recent, "primaryDocument", index)
        if not all((filing_date, accession, document)):
            continue
        try:
            if date.fromisoformat(filing_date) > cutoff:
                continue
        except ValueError:
            continue
        accession_digits = accession.replace("-", "")
        document_name = document.rsplit("/", 1)[-1]
        if not accession_digits.isdigit() or not document_name.lower().endswith((".htm", ".html")):
            continue
        cik_digits = str(int(cik))
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_digits}/"
            f"{accession_digits}/{document_name}"
        )
        rows.append(
            SecFilingReference(
                cik=cik_digits,
                form=form,
                filing_date=filing_date,
                report_date=report_date,
                accession_number=accession,
                primary_document=document_name,
                url=url,
            )
        )
    rows.sort(key=lambda row: (row.filing_date, row.form), reverse=True)
    if not rows:
        return []
    selected = [rows[0]]
    if rows[0].form != "10-K":
        annual = next((row for row in rows[1:] if row.form == "10-K"), None)
        if annual is not None:
            selected.append(annual)
    return selected


def extract_sec_risk_headings(html: str) -> list[str]:
    """Extract issuer-written risk headings from the substantive Risk Factors section."""

    parser = _SecTextBlocks()
    parser.feed(html)
    blocks = _join_wrapped_blocks(parser.finish())
    starts = [
        index for index, (block, _) in enumerate(blocks) if _is_risk_section_start(blocks, index)
    ]
    best: list[str] = []
    for start in starts:
        end = next(
            (
                index
                for index in range(start + 1, len(blocks))
                if _is_later_item_heading(blocks[index][0])
                or _RISK_SECTION_END.match(blocks[index][0].strip())
            ),
            len(blocks),
        )
        candidates: list[str] = []
        seen: set[str] = set()
        summary_mode = False
        summary_categories: set[str] = set()
        section_blocks = blocks[start + 1 : end]
        for block_index, (block, emphasized) in enumerate(section_blocks):
            compact = _compact_heading(block)
            if compact in {"riskfactorsummary", "riskfactorssummary"}:
                summary_mode = True
                summary_categories = set()
                continue
            is_category = bool(_GENERIC_RISK_CATEGORY.fullmatch(block.strip()))
            if summary_mode and emphasized and is_category:
                category_key = block.casefold()
                if category_key in summary_categories:
                    summary_mode = False
                else:
                    summary_categories.add(category_key)
                continue
            candidate = block
            candidate_emphasized = emphasized
            explicit_inline_heading = False
            if emphasized:
                topic_statement = _risk_statement_from_topic_heading(
                    section_blocks,
                    block_index,
                )
                if topic_statement is not None:
                    candidate = topic_statement
            if not emphasized:
                inline_heading = _inline_title_case_risk_heading(block)
                if inline_heading:
                    candidate = inline_heading
                    candidate_emphasized = True
                elif inline_heading := _inline_dash_risk_heading(block):
                    candidate = inline_heading
                    explicit_inline_heading = True
                elif not summary_mode:
                    continue
            candidate = _clean_risk_heading_marker(candidate)
            if not explicit_inline_heading and not _is_risk_heading(
                candidate,
                emphasized=candidate_emphasized,
            ):
                continue
            key = candidate.casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
        if len(candidates) > len(best):
            best = candidates
    return _diverse_risk_headings(best, limit=30)


def _diverse_risk_headings(headings: list[str], *, limit: int) -> list[str]:
    """Keep material risk families visible before filling by filing order."""

    if len(headings) <= limit:
        return headings
    selected_indices = set(range(limit))
    protected_indices: set[int] = set()
    for pattern in _RISK_DIVERSITY_PATTERNS:
        candidate_index = next(
            (index for index, heading in enumerate(headings) if pattern.search(heading)),
            None,
        )
        if candidate_index is None:
            continue
        if candidate_index in selected_indices:
            protected_indices.add(candidate_index)
            continue
        replacement = next(
            (
                index
                for index in sorted(selected_indices, reverse=True)
                if index not in protected_indices
            ),
            None,
        )
        if replacement is None:
            break
        selected_indices.remove(replacement)
        selected_indices.add(candidate_index)
        protected_indices.add(candidate_index)
    return [heading for index, heading in enumerate(headings) if index in selected_indices]


def extract_sec_business_context(html: str) -> list[str]:
    """Extract concise issuer-written business and segment context from Item 1."""

    parser = _SecTextBlocks()
    parser.feed(html)
    blocks = _join_wrapped_blocks(parser.finish())
    starts = [index for index, (block, _) in enumerate(blocks) if _is_business_section_start(block)]
    best: list[str] = []
    for start in starts:
        end = next(
            (
                index
                for index in range(start + 1, len(blocks))
                if _is_risk_section_start_text(blocks[index][0])
            ),
            len(blocks),
        )
        section = blocks[start : min(end, start + 81)]
        candidates = [
            (index, fragment)
            for index, (text, emphasized) in enumerate(section)
            if not emphasized
            for fragment in _business_context_fragments(text)
        ]
        if not candidates:
            continue
        activity = next(
            (text for _, text in candidates if _is_business_context_identity(text)),
            next(
                (text for _, text in candidates if _BUSINESS_CONTEXT_REVENUE_ACTIVITY.search(text)),
                next(
                    (
                        text
                        for _, text in candidates
                        if _BUSINESS_CONTEXT_CORE_OFFERING.search(text)
                        and _business_context_score(text) >= 3
                    ),
                    next(
                        (
                            text
                            for _, text in candidates
                            if (
                                _BUSINESS_CONTEXT_DIRECT_ACTIVITY.search(text)
                                or _BUSINESS_CONTEXT_NAMED_ACTIVITY.search(text)
                                or _BUSINESS_CONTEXT_NAMED_OFFERING.search(text)
                                or _BUSINESS_CONTEXT_SEGMENT_ACTIVITY.search(text)
                            )
                            and _business_context_score(text) >= 3
                        ),
                        next(
                            (text for _, text in candidates if _business_context_score(text) >= 3),
                            candidates[0][1],
                        ),
                    ),
                ),
            ),
        )
        activity_is_core_offering = bool(_BUSINESS_CONTEXT_CORE_OFFERING.search(activity))
        selected = [activity]
        segment_candidates = sorted(
            (
                (index, segment)
                for index, segment in candidates
                if _is_business_context_segment_description(segment)
            ),
            key=lambda item: (
                bool(_BUSINESS_CONTEXT_SEGMENT_ACTIVITY.search(item[1])),
                _business_context_score(item[1]),
                -item[0],
            ),
            reverse=True,
        )
        selected_segments: list[tuple[int, str]] = []
        for index, segment in segment_candidates:
            if _business_context_is_distinct(
                segment,
                selected + [item[1] for item in selected_segments],
            ):
                selected_segments.append((index, segment))
            if len(selected_segments) == 2:
                break
        selected.extend(
            segment for _, segment in sorted(selected_segments, key=lambda item: item[0])
        )
        if len(selected) < 3:
            ranked_context = sorted(
                candidates,
                key=lambda item: (
                    bool(_BUSINESS_CONTEXT_REVENUE_ACTIVITY.search(item[1])),
                    bool(_BUSINESS_CONTEXT_CORE_OFFERING.search(item[1])),
                    bool(
                        _BUSINESS_CONTEXT_DIRECT_ACTIVITY.search(item[1])
                        or _BUSINESS_CONTEXT_NAMED_ACTIVITY.search(item[1])
                        or _BUSINESS_CONTEXT_NAMED_OFFERING.search(item[1])
                        or _BUSINESS_CONTEXT_SEGMENT_ACTIVITY.search(item[1])
                    ),
                    _business_context_score(item[1]),
                    -item[0],
                ),
                reverse=True,
            )
            for _, context in ranked_context:
                revenue_context = bool(_BUSINESS_CONTEXT_REVENUE_ACTIVITY.search(context))
                segment_context = _is_business_context_segment_description(context)
                direct_context = bool(
                    _BUSINESS_CONTEXT_DIRECT_ACTIVITY.search(context)
                    or _BUSINESS_CONTEXT_NAMED_ACTIVITY.search(context)
                    or _BUSINESS_CONTEXT_NAMED_OFFERING.search(context)
                    or _BUSINESS_CONTEXT_SEGMENT_ACTIVITY.search(context)
                )
                core_context = bool(_BUSINESS_CONTEXT_CORE_OFFERING.search(context))
                if not (revenue_context or segment_context or direct_context or core_context):
                    continue
                if (
                    activity_is_core_offering
                    and direct_context
                    and not revenue_context
                    and not segment_context
                ):
                    continue
                if _business_context_is_distinct(context, selected):
                    selected.append(context)
                if len(selected) == 3:
                    break
        if len(selected) > len(best):
            best = selected
    return best[:3]


def build_sec_business_context_payload(
    *,
    ticker: str,
    filing: SecFilingReference,
    html: str,
    retrieved_at: str,
) -> dict[str, Any]:
    """Build the existing official-news contract from a filed annual Item 1."""

    statements = extract_sec_business_context(html) if filing.form == "10-K" else []
    accession = filing.accession_number.replace("-", "")
    symbol = ticker.strip().upper()
    return {
        "coverage_status": "partial" if statements else "unavailable",
        "checked_at": retrieved_at,
        "window_start": filing.report_date or filing.filing_date,
        "window_end": filing.filing_date,
        "sources_checked": [filing.url],
        "events": [
            {
                "date": filing.filing_date,
                "headline": f"SEC Item 1 describes {symbol}'s business",
                "event_type": "business_context",
                "material": True,
                "source_id": filing.source_id,
                "source_type": "sec_filing",
                "authority_rank": rank_source("sec_filing"),
                "url": filing.url,
                "retrieved_at": retrieved_at,
                "evidence_id": f"{symbol}_SEC_BUSINESS_{accession}_{index:02d}",
                "summary": statement,
            }
            for index, statement in enumerate(statements, start=1)
        ],
    }


def build_sec_risk_evidence(
    *,
    ticker: str,
    filing: SecFilingReference,
    html: str,
    retrieved_at: str,
) -> list[EvidenceItem]:
    symbol = ticker.strip().upper()
    period = (
        f"{filing.form} period ended {filing.report_date}" if filing.report_date else filing.form
    )
    return [
        EvidenceItem(
            evidence_id=f"{symbol}_SEC_RISK_{filing.accession_number.replace('-', '')}_{index:02d}",
            ticker=symbol,
            claim_type="risk",
            source_id=filing.source_id,
            source_type="sec_filing",
            authority_rank=rank_source("sec_filing"),
            statement=heading,
            period=period,
            date=filing.filing_date,
            url=filing.url,
            retrieved_at=retrieved_at,
            supports_categories=["company_risk_analysis"],
            confidence="high",
            amendment_status="original",
        )
        for index, heading in enumerate(extract_sec_risk_headings(html), start=1)
    ]


def save_sec_risk_evidence(
    path: str | Path,
    *,
    filing: SecFilingReference,
    evidence: list[EvidenceItem],
    filings: list[SecFilingReference] | None = None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "filing": filing.to_dict(),
        "filings": [item.to_dict() for item in (filings or [filing])],
        "evidence_items": [item.model_dump(mode="json") for item in evidence],
    }
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def load_sec_risk_evidence(path: str | Path, *, ticker: str) -> list[EvidenceItem]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = [EvidenceItem(**row) for row in payload.get("evidence_items") or []]
    symbol = ticker.strip().upper()
    if any(
        item.ticker != symbol or item.claim_type != "risk" or item.source_type != "sec_filing"
        for item in items
    ):
        raise ValueError("SEC risk evidence identity or authority mismatch")
    return items


def _array_value(payload: dict[str, Any], key: str, index: int) -> str:
    values = payload.get(key) or []
    if index >= len(values):
        return ""
    return str(values[index] or "").strip()


def _join_wrapped_blocks(
    blocks: list[tuple[str, bool]],
) -> list[tuple[str, bool]]:
    """Rejoin visual SEC line wraps without merging separate paragraphs."""

    joined: list[tuple[str, bool]] = []
    for text, emphasized in blocks:
        if joined and _is_visual_line_continuation(joined[-1], (text, emphasized)):
            previous, _ = joined[-1]
            joined[-1] = (f"{previous.rstrip()} {text.lstrip()}", emphasized)
        else:
            joined.append((text, emphasized))
    return joined


def _is_visual_line_continuation(
    previous: tuple[str, bool],
    current: tuple[str, bool],
) -> bool:
    previous_text, previous_emphasized = previous
    current_text, current_emphasized = current
    if previous_emphasized != current_emphasized:
        return False
    stripped = previous_text.rstrip()
    current_stripped = current_text.strip()
    if not stripped or not current_stripped:
        return False
    if current_stripped.startswith(("•", "●", "▪", "◦", "■")):
        return False
    if (
        stripped.isupper()
        or _is_risk_section_start_text(stripped)
        or _is_business_section_start(stripped)
        or _is_later_item_heading(stripped)
        or _GENERIC_RISK_CATEGORY.fullmatch(stripped)
    ):
        return False
    if stripped.endswith((",", ";", "-", "–", "—")):
        return True
    final_word = re.search(r"([A-Za-z]+)$", stripped)
    if final_word and final_word.group(1).lower() in _WRAPPED_LINE_END_WORDS:
        return True
    first_letter = re.search(r"[A-Za-z]", current_text)
    return bool(
        stripped[-1] not in ".!?"
        and first_letter
        and first_letter.group(0).islower()
    )


def _normalized_heading(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _compact_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _is_later_item_heading(text: str) -> bool:
    normalized = _normalized_heading(text)
    return bool(_ITEM_HEADING.match(normalized)) and not normalized.startswith("item 1a")


def _is_risk_section_start(
    blocks: list[tuple[str, bool]],
    index: int,
) -> bool:
    text, emphasized = blocks[index]
    compact = _compact_heading(text)
    if compact in {"item1ariskfactors", "item1a"}:
        return True
    if compact == "riskfactors":
        next_text = blocks[index + 1][0].strip() if index + 1 < len(blocks) else ""
        if not emphasized and re.fullmatch(r"(?:page\s*)?\d+(?:-\d+)?", next_text, re.IGNORECASE):
            return False
        return True
    return _is_risk_section_start_text(text)


def _is_risk_section_start_text(text: str) -> bool:
    stripped = text.strip()
    return bool(re.match(r"^(?:item\s*1a[.\s:-]*)?risk factors(?:[.:]|$)", stripped, re.IGNORECASE))


def _is_business_section_start(text: str) -> bool:
    if _compact_heading(text) in {
        "item1business",
        "items1and2businessandproperties",
        "businesssummary",
        "descriptionofthebusiness",
    }:
        return True
    return bool(_BUSINESS_ABOUT_HEADING.match(text.strip()))


def _is_risk_heading(text: str, *, emphasized: bool = False) -> bool:
    stripped = text.strip()
    lowered = stripped.lower()
    minimum_length = 20 if emphasized else 40
    if not minimum_length <= len(stripped) <= 320:
        return False
    if stripped[0].islower():
        return False
    if (
        _compact_heading(stripped)
        in {
            "riskfactors",
            "item1a",
            "item1ariskfactors",
        }
        | _GENERIC_RISK_HEADINGS
        | _NON_RISK_DOCUMENT_HEADINGS
    ):
        return False
    if stripped.startswith(("•", "●", "▪", "-")):
        return False
    if not emphasized and not stripped.endswith("."):
        return False
    if (
        stripped.isupper()
        or lowered.startswith(_GENERIC_PREFIXES)
        or _GENERIC_RISK_CATEGORY.fullmatch(stripped)
    ):
        return False
    if stripped.count(". ") > 1:
        return False
    return bool(_RISK_LANGUAGE.search(stripped))


def _risk_statement_from_topic_heading(
    blocks: list[tuple[str, bool]],
    index: int,
) -> str | None:
    """Resolve an emphasized all-caps topic to its first substantive risk sentence."""

    heading, emphasized = blocks[index]
    stripped = heading.strip()
    if (
        not emphasized
        or not stripped.isupper()
        or not 4 <= len(stripped) <= 120
        or _GENERIC_RISK_CATEGORY.fullmatch(stripped)
        or _compact_heading(stripped) in _GENERIC_RISK_HEADINGS
    ):
        return None
    for narrative, narrative_emphasized in blocks[index + 1 : index + 5]:
        if narrative_emphasized:
            break
        protected = _BUSINESS_CONTEXT_ABBREVIATION.sub(
            lambda match: match.group(0).replace(".", _PROTECTED_PERIOD),
            narrative,
        )
        for raw_sentence in re.split(r"(?<=[.!?])\s+", protected):
            sentence = raw_sentence.replace(_PROTECTED_PERIOD, ".").strip()
            standalone = _standalone_topic_risk_sentence(sentence)
            if standalone is not None:
                return standalone
    return None


def _standalone_topic_risk_sentence(sentence: str) -> str | None:
    """Keep topic-linked risk text only when it remains clear without its paragraph."""

    stripped = re.sub(
        r"^(?:Additionally|Also|Further|Similarly|For instance),\s+",
        "",
        sentence.strip(),
        flags=re.IGNORECASE,
    )
    stripped = stripped[:1].upper() + stripped[1:]
    if not 20 <= len(stripped) <= 320 or stripped.endswith(":"):
        return None
    if re.match(
        r"^(?:Accordingly\b|In particular\b|It\b|The outcome\b|They\b|"
        r"This\b|That\b|These\b|Those\b|To achieve\b|To the extent\b)",
        stripped,
        re.IGNORECASE,
    ):
        return None
    if re.search(
        r"\b(?:these|those|such)\s+(?:arrangements|developments|factors|"
        r"initiatives|matters|risks|transactions)\b",
        stripped,
        re.IGNORECASE,
    ):
        return None
    if _is_risk_heading(stripped, emphasized=True):
        return stripped
    if re.search(r"\b(?:uncertain|uncertainty|unpredictable)\b", stripped, re.I):
        return stripped
    return None


def _clean_risk_heading_marker(text: str) -> str:
    """Remove an issuer's decorative square from an otherwise valid heading."""

    return _clean_extracted_text(re.sub(r"^\s*■\s*", "", text))


def _clean_extracted_text(text: str) -> str:
    """Remove filing footnote markers and HTML spacing artifacts from prose."""

    cleaned = re.sub(
        r"(?<=[A-Za-z0-9’'])\*+(?=\s|[,.;:!?]|$)",
        "",
        str(text or ""),
    )
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return " ".join(cleaned.split())


def _inline_title_case_risk_heading(text: str) -> str | None:
    """Return an issuer heading when a filing merges it with body text."""

    prefix, separator, narrative = text.strip().partition(":")
    if not separator or not 20 <= len(prefix) <= 240 or len(narrative.strip()) < 20:
        return None
    if ". " in prefix or not _looks_like_title_case_heading(prefix):
        return None
    return prefix if _is_risk_heading(prefix, emphasized=True) else None


def _inline_dash_risk_heading(text: str) -> str | None:
    """Return a concise issuer label joined to its risk narrative by a dash."""

    prefix, separator, narrative = text.strip().partition(" - ")
    if not separator or not 4 <= len(prefix) <= 120 or len(narrative.strip()) < 40:
        return None
    if prefix.isupper() or any(character.isdigit() for character in prefix):
        return None
    if _compact_heading(prefix) in _NON_RISK_DOCUMENT_HEADINGS:
        return None
    words = re.findall(r"[A-Za-z][A-Za-z&/'’\-]*", prefix)
    if not 1 <= len(words) <= 12:
        return None
    if _GENERIC_RISK_CATEGORY.fullmatch(prefix) or not _RISK_LANGUAGE.search(narrative):
        return None
    return prefix


def _looks_like_title_case_heading(text: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z’'\-]*", text)
    meaningful = [word for word in words if word.lower().strip("’'") not in _TITLE_CASE_CONNECTORS]
    if len(meaningful) < 4:
        return False
    title_case_count = sum(word[0].isupper() for word in meaningful)
    return title_case_count / len(meaningful) >= 0.75


def _is_business_context_paragraph(text: str) -> bool:
    stripped = text.strip()
    lowered = stripped.lower()
    identity_statement = _is_business_context_identity(stripped)
    revenue_activity = bool(_BUSINESS_CONTEXT_REVENUE_ACTIVITY.search(stripped))
    single_segment = bool(_BUSINESS_CONTEXT_SINGLE_SEGMENT.search(stripped))
    segment_activity = bool(_BUSINESS_CONTEXT_SEGMENT_ACTIVITY.search(stripped))
    core_offering = bool(_BUSINESS_CONTEXT_CORE_OFFERING.search(stripped))
    minimum_length = (
        25 if single_segment else 45 if identity_statement or "segment" in lowered else 80
    )
    if not minimum_length <= len(stripped) <= 700:
        return False
    if any(character.isdigit() for character in stripped):
        numeric_identity_or_segment = identity_statement or "segment" in lowered
        numeric_financial_context = bool(
            re.search(
                r"(?:\$|%|\b(?:million|billion|assets|employ(?:ed|ees)|"
                r"production|year ended|as of)\b)",
                stripped,
                re.IGNORECASE,
            )
        )
        if not numeric_identity_or_segment or numeric_financial_context:
            return False
    if lowered.startswith(_BUSINESS_CONTEXT_SKIP_PREFIXES):
        return False
    if _BUSINESS_CONTEXT_ACCOUNTING_LANGUAGE.search(stripped):
        return False
    if _BUSINESS_CONTEXT_PROMOTIONAL_LANGUAGE.search(stripped):
        return False
    if _BUSINESS_CONTEXT_UNRESOLVED_REFERENCE.search(stripped):
        return False
    if stripped.isupper() or stripped.count(". ") > 3:
        return False
    score = _business_context_score(stripped)
    return (
        identity_statement
        or revenue_activity
        or single_segment
        or segment_activity
        or core_offering
        or score >= 3
        or ("segment" in lowered and score >= 2)
    )


def _business_context_fragments(text: str) -> list[str]:
    protected = _BUSINESS_CONTEXT_ABBREVIATION.sub(
        lambda match: match.group(0).replace(".", _PROTECTED_PERIOD),
        text.strip(),
    )
    fragments: list[str] = []
    for raw_fragment in re.split(r"(?<=[.!?])\s+", protected):
        fragment = _clean_extracted_text(
            raw_fragment.replace(_PROTECTED_PERIOD, ".")
        )
        fragment = re.sub(r"^[•●▪◦-]\s*", "", fragment).strip()
        fragment = re.sub(r"\b[1-9]\)\s*", "", fragment)
        fragment = re.sub(r";\s*(?:and)?$", "", fragment).strip()
        if fragment.endswith(":"):
            continue
        if fragment and fragment[-1] not in ".!?":
            fragment = f"{fragment}."
        if _is_business_context_paragraph(fragment):
            fragments.append(fragment)
    return fragments


def _business_context_score(text: str) -> int:
    terms = {match.group(0).lower() for match in _BUSINESS_LANGUAGE.finditer(text)}
    terms.update(match.group(0).lower() for match in _BUSINESS_MODEL_LANGUAGE.finditer(text))
    return len(terms)


def _is_business_context_identity(text: str) -> bool:
    return bool(
        _BUSINESS_CONTEXT_IDENTITY.search(text)
        or _BUSINESS_CONTEXT_AS_IDENTITY.search(text)
        or _BUSINESS_CONTEXT_NAMED_IDENTITY.search(text)
        or _BUSINESS_CONTEXT_NAMED_LEADER_IDENTITY.search(text)
        or _BUSINESS_CONTEXT_PARENTHETICAL_IDENTITY.search(text)
        or _BUSINESS_CONTEXT_SINGLE_SEGMENT.search(text)
    )


def _is_business_context_segment_description(text: str) -> bool:
    if _BUSINESS_CONTEXT_SINGLE_SEGMENT.search(text):
        return True
    if _BUSINESS_CONTEXT_SEGMENT_ACTIVITY.search(text):
        return True
    explicit_reporting_context = bool(
        re.search(
            r"\b(?:reportable|operating|reporting|business|geographic) segments?\b"
            r"|\b(?:report|reports|reported|reporting)\b.+\bsegments?\b"
            r"|\boperate(?:s)? through\b.+\bsegments?\b",
            text,
            re.IGNORECASE,
        )
    )
    return explicit_reporting_context and _business_context_score(text) >= 2


def _business_context_is_distinct(
    candidate: str,
    selected: list[str],
) -> bool:
    if candidate in selected:
        return False
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "business",
        "businesses",
        "collectively",
        "comprises",
        "for",
        "in",
        "is",
        "of",
        "our",
        "purposes",
        "report",
        "reported",
        "reporting",
        "segment",
        "segments",
        "the",
        "to",
        "two",
        "we",
    }
    candidate_tokens = set(re.findall(r"[a-z]+", candidate.casefold())) - stopwords
    if not candidate_tokens:
        return False
    for existing in selected:
        existing_tokens = set(re.findall(r"[a-z]+", existing.casefold())) - stopwords
        smaller = min(len(candidate_tokens), len(existing_tokens))
        if smaller and len(candidate_tokens & existing_tokens) / smaller >= 0.8:
            return False
    return True
