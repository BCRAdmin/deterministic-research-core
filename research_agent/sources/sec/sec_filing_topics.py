"""Deterministically scan current SEC financial filings for material topics."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


TOPIC_PATTERNS = {
    "transactions": (
        r"\b(?:completed|closed|entered into|agreed to|acquired|sold|disposed of)\b.{0,120}"
        r"\b(?:acquisition|merger|business combination|transaction|subsidiary|assets?)\b",
        r"\b(?:purchase price|purchase consideration|business combination)\b.{0,120}\$",
        r"\b(?:preliminary allocation of (?:the )?fair value|purchase price allocation)\b",
        r"\bpro forma (?:condensed |consolidated )?(?:net sales|revenue|earnings)\b",
        r"\b(?:goodwill|acquired intangible assets?)\b.{0,160}\bbusiness combination\b",
    ),
    "financing": (
        r"\b(?:entered into|amended|refinanced|issued|borrowed|repaid)\b.{0,120}"
        r"\b(?:credit agreement|credit facility|senior notes|term loan|revolving facility|debt)\b",
        r"\b(?:principal amount|borrowings outstanding)\b.{0,120}\$",
    ),
    "legal_contingencies": (
        r"\b(?:legal proceedings|litigation|lawsuits?|class actions?|complaints?|government investigation|regulatory investigation)\b",
        r"\b(?:environmental remediation|environmental liability|contingent liabilities|commitments and contingencies)\b",
        r"\b(?:settled|settlement|fine|penalty|consent decree)\b.{0,120}\$",
        r"\b(?:environmental protection agency|epa|superfund|administrative order|"
        r"deferred prosecution agreement|consent order)\b",
        r"\b(?:issued|entered into|executed|received)\b.{0,160}"
        r"\b(?:order|agreement|subpoena|warrant)\b",
        r"\b(?:appeal of (?:this|the) order|appeal.{0,80}pending)\b",
        r"\b(?:remediation|remedial|liability|penalty)\b.{0,160}"
        r"(?:\$|million|billion|material(?:ly)?)\b",
    ),
}

TOPIC_HEADLINES = {
    "transactions": "Current filing contains a transaction disclosure",
    "financing": "Current filing contains a financing disclosure",
    "legal_contingencies": "Current filing contains a legal or contingency disclosure",
}
TOPIC_CONTRACT_ID = "room16.sec_filing_topics"
TOPIC_CONTRACT_VERSION = 3


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[str] = []
        self.parts: list[str] = []
        self.hidden = 0

    def _flush(self) -> None:
        text = " ".join("".join(self.parts).split())
        if text:
            self.blocks.append(text)
        self.parts = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in {"br", "div", "p", "li", "tr", "td", "th", "h1", "h2", "h3"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"div", "p", "li", "tr", "td", "th", "h1", "h2", "h3"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)

    def finish(self) -> list[str]:
        self._flush()
        return self.blocks


_TOPIC_NUMBER_RE = re.compile(
    r"(?P<currency>C\$|US\$|A\$|HK\$|S\$|[$€£¥])?\s*"
    r"(?P<number>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*"
    r"(?P<scale>billion|million|thousand|bn|mn|m|k)?\s*(?P<percent>%)?",
    re.IGNORECASE,
)


def build_sec_filing_topic_payload(
    *,
    ticker: str,
    cik: str,
    accession_number: str,
    filing_date: str,
    primary_document: str,
    html: str,
    retrieved_at: str,
) -> dict[str, Any]:
    """Return explicit found/no-specific-disclosure dispositions for each topic."""

    parser = _TextParser()
    parser.feed(html)
    blocks = parser.finish()
    document_currency_scale = _document_currency_scale(blocks)
    cik_digits = str(int(cik)).zfill(10)
    accession_digits = accession_number.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_digits}/{_document_name(primary_document)}"
    )
    dispositions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for topic, patterns in TOPIC_PATTERNS.items():
        candidates: list[tuple[int, int, str]] = []
        for source_index, block in enumerate(blocks):
            score = _topic_match_score(topic, block, patterns)
            if score <= 0:
                continue
            candidates.append(
                (
                    score,
                    -source_index,
                    _topic_context_excerpt(
                        blocks,
                        source_index=source_index,
                        block=block,
                        topic=topic,
                    ),
                )
            )
        matches = _distinct_topic_excerpts(candidates, limit=3)
        status = "found_specific_disclosure" if matches else "reviewed_no_specific_disclosure"
        source_id = f"SEC_CIK{cik_digits}_{accession_digits}_TOPIC_{topic.upper()}"
        dispositions.append(
            {
                "topic": topic,
                "status": status,
                "source_id": source_id,
                "match_count": len(matches),
                "excerpts": matches,
                "event_source_ids": [
                    f"{source_id}_{index:02d}"
                    for index in range(1, len(matches) + 1)
                ],
                "material": bool(matches),
                "report_requirement": (
                    "included_main_report_or_explicit_disposition"
                    if matches
                    else "reviewed_no_specific_disclosure"
                ),
            }
        )
        for match_index, summary in enumerate(matches, start=1):
            event_source_id = f"{source_id}_{match_index:02d}"
            events.append(
                {
                    "event_type": f"filing_{topic}",
                    "date": filing_date,
                    "headline": TOPIC_HEADLINES[topic],
                    "summary": summary,
                    "material": True,
                    "source_id": event_source_id,
                    "source_type": "sec_filing",
                    "authority_rank": 1,
                    "url": url,
                    "retrieved_at": retrieved_at,
                    "content_complete": True,
                    "dependency_status": "complete",
                    "report_disposition": "included_main_report",
                    "report_disposition_reason": (
                        "A specific material filing topic must be visible in the main report."
                    ),
                    "materiality_rationale": (
                        "A source-specific filing topic was found in a current "
                        "primary SEC filing and requires explicit report treatment."
                    ),
                    "inventory_filter_reason": "inside_analysis_window",
                    "semantic_disposition": "current_material_topic",
                    "numeric_evidence": _topic_numeric_evidence(
                        summary,
                        topic,
                        filing_date=filing_date,
                        document_currency_scale=document_currency_scale,
                    ),
                    "legal_context": (
                        _legal_context(summary)
                        if topic == "legal_contingencies"
                        else None
                    ),
                }
            )
    _disambiguate_event_metric_names(events)
    return {
        "contract_id": TOPIC_CONTRACT_ID,
        "contract_version": TOPIC_CONTRACT_VERSION,
        "coverage_status": "complete",
        "checked_at": retrieved_at,
        "window_start": filing_date,
        "window_end": filing_date,
        "sources_checked": [url],
        "filing": {
            "cik": cik_digits,
            "accession_number": accession_number,
            "filing_date": filing_date,
            "primary_document": _document_name(primary_document),
        },
        "all_topics_dispositioned": len(dispositions) == len(TOPIC_PATTERNS),
        "topic_dispositions": dispositions,
        "events": events,
    }


def _disambiguate_event_metric_names(events: list[dict[str, Any]]) -> None:
    """Keep ambiguous repeated labels in inventory without promoting them."""

    occurrences: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for event_index, event in enumerate(events, start=1):
        for metric in event.get("numeric_evidence") or []:
            metric_name = str(metric.get("metric_name") or "")
            if metric_name:
                occurrences.setdefault(metric_name, []).append((event_index, metric))
    for metric_name, matches in occurrences.items():
        if len(matches) < 2:
            continue
        for _event_index, metric in matches:
            metric["mapping_status"] = "unresolved"


def _condense_topic_excerpt(text: str, *, limit: int = 950) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    selected: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*selected, sentence]).strip()
        if selected and len(candidate) > limit:
            break
        selected.append(sentence)
        if len(candidate) >= limit * 0.72:
            break
    summary = " ".join(selected).strip()
    if not summary:
        summary = compact[:limit].rsplit(" ", 1)[0]
    return summary[:limit].rstrip()


def _distinct_topic_excerpts(
    candidates: list[tuple[int, int, str]],
    *,
    limit: int,
) -> list[str]:
    selected: list[str] = []
    for _score, _source_order, excerpt in sorted(
        candidates,
        key=lambda item: (item[0], len(item[2]), item[1]),
        reverse=True,
    ):
        if any(excerpt in existing or existing in excerpt for existing in selected):
            continue
        selected.append(excerpt)
        if len(selected) == limit:
            break
    return selected


def _topic_context_excerpt(
    blocks: list[str],
    *,
    source_index: int,
    block: str,
    topic: str,
) -> str:
    """Preserve an immediately preceding issuer assessment for legal topics."""

    context = block
    if topic == "transactions" and re.search(
        r"\b(?:preliminary allocation|purchase price allocation|pro forma|goodwill|"
        r"acquired intangible assets?)\b",
        block,
        re.IGNORECASE,
    ):
        # Purchase-accounting tables are split into adjacent HTML rows.  Keep
        # the heading and following rows together so PPA and pro-forma facts
        # cannot disappear between block boundaries.
        start = max(0, source_index - 1)
        context = " ".join(blocks[start : min(len(blocks), source_index + 14)])
    if topic == "legal_contingencies" and source_index > 0:
        preceding = " ".join(str(blocks[source_index - 1] or "").split())
        assessment = re.search(
            r"([^.!?]*(?:we do not (?:currently )?(?:expect|believe)|we believe|"
            r"management believes)[^.!?]*[.!?])\s*$",
            preceding,
            re.IGNORECASE,
        )
        if assessment:
            context = f"{assessment.group(1).strip()} {block}"
    return _condense_topic_excerpt(context, limit=2800)


def _topic_match_score(topic: str, text: str, patterns: tuple[str, ...]) -> int:
    folded = text.casefold()
    if topic == "legal_contingencies" and (
        "forward-looking statements" in folded
        and "can be identified because they contain words" in folded
    ):
        return 0
    if topic == "legal_contingencies" and (
        len(folded.strip()) < 60
        or folded.strip() in {"legal proceedings", "commitments and contingencies"}
        or re.match(r"^(?:corp\.,?\s+no\.|et al\.?\s+v\.)", folded.strip())
    ):
        return 0
    matched = sum(
        1 for pattern in patterns if re.search(pattern, folded, flags=re.IGNORECASE)
    )
    if not matched:
        return 0
    score = matched * 10
    if topic == "legal_contingencies":
        if "class actions were filed" in folded:
            score += 50
        if re.search(r"\bmotions? to dismiss\b", folded):
            score += 25
        if "tequila" in folded or "ieepa" in folded:
            score += 20
        score += 5 * len(
            re.findall(
                r"\b(?:order|agreement|investigation|proceeding|lawsuit|settlement|"
                r"penalty|fine|superfund|subpoena|warrant|appeal|obligation)\b",
                folded,
            )
        )
        score += 8 * len(
            re.findall(
                r"\b(?:epa|environmental protection agency|deferred prosecution)\b",
                folded,
            )
        )
        if re.search(
            r"\b(?:issued|entered into|executed|received)\b.{0,160}"
            r"\b(?:order|agreement|subpoena|warrant)\b",
            folded,
        ):
            score += 30
        if re.search(
            r"\b(?:appeal of (?:this|the) order|appeal.{0,80}pending)\b",
            folded,
        ):
            score += 20
        if re.search(r"(?:\$|\b(?:million|billion)\b)", folded):
            score += 6
        if re.search(
            r"\b(?:condensed consolidated|critical accounting|in preparing our financial statements)\b",
            folded,
        ):
            score -= 30
        if re.search(
            r"\b(?:issued|entered into|executed|received|appeal(?:ed| is pending)?)\b",
            folded,
        ) and re.search(r"\b20[0-9]{2}\b", folded):
            score += 12
        if re.search(r"\b\d+\s+(?:locations|sites)\b", folded) and "listed" in folded:
            score -= 20
        if re.search(
            r"\b(?:proceedings involving npl sites|cercla generally|"
            r"proceedings arising under superfund|typically involve numerous)\b",
            folded,
        ):
            score -= 25
    return score


def _topic_numeric_evidence(
    summary: str,
    topic: str,
    *,
    filing_date: str | None = None,
    document_currency_scale: str | None = None,
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    metric_occurrences: dict[str, int] = {}
    period_contract = _topic_period_contract(summary, filing_date=filing_date)
    for match in _TOPIC_NUMBER_RE.finditer(summary):
        raw = float(match.group("number").replace(",", ""))
        if _topic_number_is_non_metric(summary, match):
            continue
        scale = str(match.group("scale") or "").casefold()
        contextual_scale = _topic_context_scale(summary, match)
        if (
            not scale
            and (contextual_scale or document_currency_scale)
            and not _topic_is_base_currency_value(summary, match)
            and not (raw.is_integer() and 1900 <= raw <= 2100)
        ):
            scale = contextual_scale or document_currency_scale or ""
        percent = bool(match.group("percent"))
        if not (match.group("currency") or scale or percent):
            continue
        multiplier = {
            "billion": 1_000_000_000,
            "bn": 1_000_000_000,
            "million": 1_000_000,
            "mn": 1_000_000,
            "m": 1_000_000,
            "thousand": 1_000,
            "k": 1_000,
        }.get(scale, 1)
        value = raw / 100 if percent else raw * multiplier
        currency = {
            "C$": "CAD",
            "US$": "USD",
            "A$": "AUD",
            "HK$": "HKD",
            "S$": "SGD",
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
        }.get(str(match.group("currency") or ""))
        if not percent and not currency and scale and topic in {"transactions", "financing", "legal_contingencies"}:
            currency = "USD"
        metric_name = _topic_metric_name(
            summary,
            topic=topic,
            match=match,
            ordinal=len(values) + 1,
        )
        if currency:
            metric_name = f"{metric_name}_{currency.casefold()}"
        # ResearchClaim.metric_values is a mapping.  A repeated semantic label
        # must therefore receive a stable occurrence suffix instead of
        # silently overwriting a source number during promotion.
        metric_occurrences[metric_name] = metric_occurrences.get(metric_name, 0) + 1
        if metric_occurrences[metric_name] > 1:
            metric_name = f"{metric_name}_occurrence_{metric_occurrences[metric_name]:02d}"
        effective_asof_dates = (
            _effective_asof_dates(summary)
            if "legal_reserve" in metric_name
            else []
        )
        metric_period_contract = _topic_period_contract_for_match(
            summary,
            match,
            filing_date=filing_date,
        ) or dict(period_contract)
        transaction_date = (
            _nearest_preceding_date(summary, match)
            if topic in {"transactions", "financing"}
            else None
        )
        if transaction_date and (
            topic == "financing"
            or
            not metric_period_contract
            or any(
                marker in metric_name
                for marker in (
                    "acquisition_goodwill",
                    "acquisition_intangible_assets",
                    "acquisition_deferred_tax",
                    "acquisition_total_consideration",
                )
            )
        ):
            metric_period_contract = {
                "period_kind": "instant",
                "presentation_basis": "point_in_time",
                "period_start": None,
                "period_end": transaction_date,
            }
        if effective_asof_dates:
            metric_period_contract = {
                "period_kind": "instant",
                "presentation_basis": "point_in_time",
                "period_start": None,
                "period_end": max(effective_asof_dates),
            }
        values.append(
            {
                "metric_name": metric_name,
                "value": value,
                "raw_value": raw,
                "unit": "percent" if percent else currency or "count",
                "dimension": "percent" if percent else "currency" if currency else "count",
                "source_scale": "percent" if percent else scale or "base",
                "source_unit": "percent" if percent else currency or "count",
                "source_sign": 1,
                "currency": currency,
                "column_label": None,
                "effective_asof_dates": effective_asof_dates,
                "raw_text": _topic_numeric_clause(summary, match),
                "normalized_magnitude": abs(value),
                "signed_value": value,
                "direction": "neutral",
                "impact": "neutral",
                "mapping_status": (
                    "unresolved" if "_unmapped_" in metric_name else "mapped"
                ),
                **metric_period_contract,
            }
        )
    return values


def _document_currency_scale(blocks: list[str]) -> str | None:
    declarations = [
        match.group("scale").casefold().removesuffix("s")
        for block in blocks
        for match in re.finditer(
            r"\b(?:amounts?|dollars)\s+in\s+(?P<scale>billions?|millions?|thousands?)\b",
            block,
            re.IGNORECASE,
        )
    ]
    return declarations[0] if declarations and len(set(declarations)) == 1 else None


def _topic_context_scale(summary: str, match: re.Match[str]) -> str | None:
    declarations = list(
        re.finditer(
            r"\b(?:amounts?|dollars)\s+in\s+(?P<scale>billions?|millions?|thousands?)\b",
            summary[: match.start()],
            re.IGNORECASE,
        )
    )
    return declarations[-1].group("scale").casefold().removesuffix("s") if declarations else None


def _topic_number_is_non_metric(summary: str, match: re.Match[str]) -> bool:
    before = summary[max(0, match.start() - 24) : match.start()]
    after = summary[match.end() : match.end() + 18]
    if re.search(r"\bLevel\s*$", before, re.IGNORECASE) and re.match(
        r"\s*inputs?\b", after, re.IGNORECASE
    ):
        return True
    if re.search(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)$",
        before,
        re.IGNORECASE,
    ) and re.match(r",\s*20\d{2}\b", after):
        return True
    if (
        match.start() > 0
        and summary[match.start() - 1] == "("
        and re.match(r"\)\s*", after)
        and "," not in match.group("number")
        and float(match.group("number")) <= 99
    ):
        return True
    return False


def _nearest_preceding_date(summary: str, match: re.Match[str]) -> str | None:
    from datetime import datetime

    dates = list(
        re.finditer(
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+"
            r"\d{1,2},\s+20\d{2}\b",
            summary[: match.start()],
            re.IGNORECASE,
        )
    )
    if not dates:
        return None
    try:
        return datetime.strptime(dates[-1].group(0), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def _topic_is_base_currency_value(summary: str, match: re.Match[str]) -> bool:
    nearby = summary[max(0, match.start() - 70) : match.end() + 70]
    return re.search(
        r"\b(?:per (?:common )?share|annual fee|maximum reward)\b",
        nearby,
        re.IGNORECASE,
    ) is not None


def _topic_numeric_clause(summary: str, match: re.Match[str]) -> str:
    start = max(
        summary.rfind(".", 0, match.start()),
        summary.rfind(";", 0, match.start()),
    )
    end_candidates = [
        index
        for index in (
            summary.find(".", match.end()),
            summary.find(";", match.end()),
        )
        if index >= 0
    ]
    end = min(end_candidates) + 1 if end_candidates else len(summary)
    return " ".join(summary[start + 1 : end].split())


def _effective_asof_dates(summary: str) -> list[str]:
    month_names = (
        "January|February|March|April|May|June|July|August|September|October|November|December"
    )
    values = re.findall(
        rf"\b(?:{month_names})\s+\d{{1,2}},\s+20\d{{2}}\b",
        summary,
        re.IGNORECASE,
    )
    from datetime import datetime

    dates: list[str] = []
    for value in values:
        try:
            dates.append(datetime.strptime(value, "%B %d, %Y").date().isoformat())
        except ValueError:
            continue
    return list(dict.fromkeys(dates))


def _topic_period_contract(
    summary: str,
    *,
    filing_date: str | None,
) -> dict[str, Any]:
    ended = re.search(
        r"\b(three|six|nine|twelve) months ended "
        r"(January|February|March|April|May|June|July|August|September|October|November|December) "
        r"(\d{1,2}), (20\d{2})\b",
        summary,
        re.IGNORECASE,
    )
    if not ended:
        return {}
    from datetime import date

    months = {"three": 3, "six": 6, "nine": 9, "twelve": 12}[ended.group(1).casefold()]
    month = {
        name.casefold(): index
        for index, name in enumerate(
            ("", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
        )
        if name
    }[ended.group(2).casefold()]
    period_end = date(int(ended.group(4)), month, int(ended.group(3)))
    start_month_index = period_end.year * 12 + period_end.month - months
    start_year, month_zero = divmod(start_month_index, 12)
    period_start = date(start_year, month_zero + 1, 1)
    return {
        "period_kind": "duration",
        "presentation_basis": "period_total",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }


def _duration_period_contract(months: int, month_name: str, day: str, year: str) -> dict[str, Any]:
    from datetime import date

    month = {
        name.casefold(): index
        for index, name in enumerate(
            ("", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
        )
        if name
    }[month_name.casefold()]
    period_end = date(int(year), month, int(day))
    start_month_index = period_end.year * 12 + period_end.month - months
    start_year, month_zero = divmod(start_month_index, 12)
    return {
        "period_kind": "duration",
        "presentation_basis": "period_total",
        "period_start": date(start_year, month_zero + 1, 1).isoformat(),
        "period_end": period_end.isoformat(),
    }


def _topic_period_contract_for_match(
    summary: str,
    match: re.Match[str],
    *,
    filing_date: str | None,
) -> dict[str, Any]:
    """Bind a number to its own duration in multi-column prose disclosures."""

    month_names = (
        "January|February|March|April|May|June|July|August|September|October|November|December"
    )
    prior_boundaries = list(
        re.finditer(r"\.(?=\s+[A-Z])|;", summary[: match.start()])
    )
    sentence_start = prior_boundaries[-1].end() if prior_boundaries else 0
    following_boundaries = list(
        re.finditer(r"\.(?=\s+[A-Z]|\s*$)|;", summary[match.end() :])
    )
    sentence_end_candidates = [
        match.end() + boundary.start() for boundary in following_boundaries[:1]
    ]
    sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(summary)
    sentence = summary[sentence_start:sentence_end]
    local_start = match.start() - sentence_start

    paired = re.search(
        rf"\b(three|six|nine|twelve) and (three|six|nine|twelve) months ended "
        rf"({month_names}) (\d{{1,2}}), (20\d{{2}}),? respectively\b",
        sentence,
        re.IGNORECASE,
    )
    if paired and local_start < paired.start():
        prior = [
            item for item in _TOPIC_NUMBER_RE.finditer(sentence[: paired.start()])
            if not _topic_number_is_non_metric(sentence, item)
            and (item.group("currency") or item.group("scale") or item.group("percent"))
        ]
        current = next(
            (
                index
                for index, item in enumerate(prior)
                if item.start() <= local_start <= item.end()
                or local_start <= item.start() <= local_start + 1
            ),
            None,
        )
        if current is not None and len(prior) >= 2 and current >= len(prior) - 2:
            word = paired.group(1) if current == len(prior) - 2 else paired.group(2)
            months = {"three": 3, "six": 6, "nine": 9, "twelve": 12}[word.casefold()]
            return _duration_period_contract(
                months, paired.group(3), paired.group(4), paired.group(5)
            )

    direct = re.search(
        rf"\b(three|six|nine|twelve) months ended "
        rf"({month_names}) (\d{{1,2}}), (20\d{{2}})\b",
        sentence,
        re.IGNORECASE,
    )
    if direct:
        months = {"three": 3, "six": 6, "nine": 9, "twelve": 12}[direct.group(1).casefold()]
        return _duration_period_contract(
            months, direct.group(2), direct.group(3), direct.group(4)
        )
    return {}


def _topic_metric_name(
    summary: str,
    *,
    topic: str,
    match: re.Match[str],
    ordinal: int,
) -> str:
    if match.group("percent"):
        preceding = summary[max(0, match.start() - 160) : match.start()].casefold()
        following = summary[match.end() : match.end() + 100].casefold()
        if re.search(r"previously outstanding|redeem(?:ed|ing)?", preceding):
            role = "refinanced_interest_rate"
        elif re.search(r"senior notes", following) or re.search(r"issued", preceding):
            role = "issued_interest_rate"
        else:
            role = "interest_rate"
        return f"filing_{topic}_{role}"
    if topic == "legal_contingencies":
        before = summary[max(0, match.start() - 180) : match.start()].casefold()
        after = summary[match.end() : match.end() + 120].casefold()
        if re.search(r"\b(?:verdict|award(?:ed|ing)?)\b", before):
            return "filing_legal_contingencies_verdict_damages"
        if re.search(r"\brecorded accrual\b|\baccrual balance\b", before[-100:]):
            return "filing_legal_contingencies_recorded_accrual"
        if "range of possible loss" in before:
            if re.search(r"^\s*to\b", after):
                return "filing_legal_contingencies_possible_loss_range_low"
            return "filing_legal_contingencies_possible_loss_range_high"
    following_context = summary[match.end() : match.end() + 90].casefold()
    if re.search(r"holdbacks? related to prior", following_context):
        return f"filing_{topic}_acquisition_prior_period_holdback"
    rules = (
        ("acquisition_goodwill", r"\bgoodwill\b"),
        ("acquisition_intangible_assets", r"\b(?:acquired )?intangible assets?\b"),
        ("acquisition_deferred_tax", r"\bdeferred (?:income )?tax"),
        ("acquisition_pro_forma_net_sales", r"\bpro forma.{0,80}\b(?:net sales|revenue)\b"),
        ("acquisition_pro_forma_earnings", r"\bpro forma.{0,80}\b(?:earnings|income before taxes)\b"),
        ("acquisition_transaction_costs", r"\btransaction-related costs?\b"),
        ("acquisition_interest_expense", r"\binterest expense\b"),
        ("acquisition_amortization_expense", r"\bamortization expense\b"),
        ("acquisition_total_consideration", r"total consideration|purchase price"),
        ("acquisition_net_cash_paid", r"net cash paid"),
        ("acquisition_prior_period_holdback", r"holdbacks? related to prior"),
        ("acquisition_other_consideration", r"other consideration"),
        ("acquisition_stock_consideration", r"shares?.{0,55}(?:valued|value)"),
        ("acquisition_holdback", r"holdbacks?"),
        ("debt_repayment_principal", r"\brepaid\b.{0,90}\b(?:outstanding )?principal\b|\bredeem(?:ed|ing)?\b.{0,90}\b(?:outstanding )?principal\b"),
        ("debt_net_proceeds", r"net proceeds"),
        ("debt_redemption_principal", r"redeem|outstanding"),
        ("debt_principal", r"issued|senior notes"),
        ("interest_rate", r"senior notes|matured"),
        ("legal_reserve", r"recorded.{0,40}(?:liability|reserve)|reserve"),
        ("legal_payment", r"paid|payment"),
        ("legal_penalty", r"penalty|fine"),
    )
    candidates: list[tuple[int, int, str]] = []
    for priority, (name, pattern) in enumerate(rules):
        for label in re.finditer(pattern, summary, re.IGNORECASE):
            if name == "acquisition_intangible_assets" and re.search(
                r"\bamortization expense\b",
                summary[max(0, label.start() - 90) : label.start()],
                re.IGNORECASE,
            ):
                continue
            if not _same_topic_sentence(summary, label.span(), match.span()):
                continue
            if label.end() <= match.start():
                distance = match.start() - label.end()
                direction_penalty = 0
            elif match.end() <= label.start():
                distance = label.start() - match.end()
                bridge = summary[match.end() : label.start()]
                direction_penalty = (
                    0
                    if re.fullmatch(r"\s*(?:in|of|for)\s+", bridge, re.IGNORECASE)
                    else 180
                )
            else:
                distance = 0
                direction_penalty = 0
            if distance <= 120:
                candidates.append((distance + direction_penalty, priority, name))
    if candidates:
        return f"filing_{topic}_{min(candidates)[2]}"
    return f"filing_{topic}_unmapped_{ordinal:02d}"


def _same_topic_sentence(
    text: str,
    left: tuple[int, int],
    right: tuple[int, int],
) -> bool:
    start = min(left[1], right[1])
    end = max(left[0], right[0])
    between = text[start:end]
    return re.search(r"\.(?=\s+[A-Z])|;", between) is None


def _legal_context(summary: str) -> dict[str, Any]:
    folded = summary.casefold()
    return {
        "latest_status_present": bool(
            re.search(
                r"\b(?:settled|settlement|resolved|resolution|entered into|issued|"
                r"approved|pending|deferred prosecution agreement|dpa)\b",
                folded,
            )
        ),
        "reserve_or_obligation_present": bool(
            re.search(r"\b(?:reserve|liability|obligation|payment|penalty|fine)\b", folded)
        ),
        "uncertainty_present": bool(
            re.search(r"\b(?:uncertain|uncertainty|may be|could be|not been established)\b", folded)
        ),
        "continuing_obligations_present": bool(
            re.search(r"\b(?:continuing|ongoing|compliance|reporting|cooperation)\b", folded)
        ),
        "management_assessment_present": bool(
            re.search(
                r"\b(?:we believe|management believes|we do not (?:currently )?(?:expect|believe)|our estimate)\b",
                folded,
            )
        ),
    }


def _document_name(value: str) -> str:
    """Return the filing document basename without accepting path traversal."""

    name = value.rsplit("/", 1)[-1]
    if not name or name in {".", ".."}:
        raise ValueError("invalid SEC primary document")
    return name
