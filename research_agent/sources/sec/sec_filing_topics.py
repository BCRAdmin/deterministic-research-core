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
    ),
    "financing": (
        r"\b(?:entered into|amended|refinanced|issued|borrowed|repaid)\b.{0,120}"
        r"\b(?:credit agreement|credit facility|senior notes|term loan|revolving facility|debt)\b",
        r"\b(?:principal amount|borrowings outstanding)\b.{0,120}\$",
    ),
    "legal_contingencies": (
        r"\b(?:legal proceedings|litigation|lawsuit|government investigation|regulatory investigation)\b",
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
        elif not self.hidden and tag in {"br", "div", "p", "li", "tr", "h1", "h2", "h3"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"div", "p", "li", "tr", "h1", "h2", "h3"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)

    def finish(self) -> list[str]:
        self._flush()
        return self.blocks


_TOPIC_NUMBER_RE = re.compile(
    r"(?P<currency>[$€£])?\s*"
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
            candidates.append((score, -source_index, block[:1800]))
        matches = [
            excerpt
            for _, _, excerpt in sorted(candidates, reverse=True)[:3]
        ]
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
                    "numeric_evidence": _topic_numeric_evidence(summary, topic),
                }
            )
    return {
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


def _topic_match_score(topic: str, text: str, patterns: tuple[str, ...]) -> int:
    folded = text.casefold()
    matched = sum(
        1 for pattern in patterns if re.search(pattern, folded, flags=re.IGNORECASE)
    )
    if not matched:
        return 0
    score = matched * 10
    if topic == "legal_contingencies":
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


def _topic_numeric_evidence(summary: str, topic: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for match in _TOPIC_NUMBER_RE.finditer(summary):
        raw = float(match.group("number").replace(",", ""))
        scale = str(match.group("scale") or "").casefold()
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
        values.append(
            {
                "metric_name": f"filing_{topic}_{len(values) + 1:02d}",
                "value": value,
                "raw_value": raw,
                "unit": "percent" if percent else "currency" if match.group("currency") else "count",
                "source_scale": "percent" if percent else scale or "base",
                "source_unit": "percent" if percent else "currency" if match.group("currency") else "count",
                "source_sign": 1,
                "currency": {
                    "$": "USD",
                    "€": "EUR",
                    "£": "GBP",
                }.get(str(match.group("currency") or "")),
                "column_label": None,
            }
        )
    return values


def _document_name(value: str) -> str:
    """Return the filing document basename without accepting path traversal."""

    name = value.rsplit("/", 1)[-1]
    if not name or name in {".", ".."}:
        raise ValueError("invalid SEC primary document")
    return name
