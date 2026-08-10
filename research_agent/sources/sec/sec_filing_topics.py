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
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        elif not self.hidden and tag in {"br", "div", "p", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in {"div", "p", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)

    def text(self) -> str:
        return " ".join("".join(self.parts).split())


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
    text = parser.text()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]
    cik_digits = str(int(cik)).zfill(10)
    accession_digits = accession_number.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_digits}/{_document_name(primary_document)}"
    )
    dispositions: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for topic, patterns in TOPIC_PATTERNS.items():
        matches: list[str] = []
        for sentence in sentences:
            folded = sentence.casefold()
            if any(re.search(pattern, folded, flags=re.IGNORECASE) for pattern in patterns):
                excerpt = sentence[:600]
                if excerpt not in matches:
                    matches.append(excerpt)
            if len(matches) == 3:
                break
        status = "found_specific_disclosure" if matches else "reviewed_no_specific_disclosure"
        source_id = f"SEC_CIK{cik_digits}_{accession_digits}_TOPIC_{topic.upper()}"
        dispositions.append(
            {
                "topic": topic,
                "status": status,
                "source_id": source_id,
                "match_count": len(matches),
                "excerpts": matches,
            }
        )
        if matches:
            events.append(
                {
                    "event_type": f"filing_{topic}",
                    "date": filing_date,
                    "headline": TOPIC_HEADLINES[topic],
                    "summary": " ".join(matches)[:1800],
                    "material": True,
                    "source_id": source_id,
                    "source_type": "sec_filing",
                    "authority_rank": 1,
                    "url": url,
                    "retrieved_at": retrieved_at,
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


def _document_name(value: str) -> str:
    """Return the filing document basename without accepting path traversal."""

    name = value.rsplit("/", 1)[-1]
    if not name or name in {".", ".."}:
        raise ValueError("invalid SEC primary document")
    return name
