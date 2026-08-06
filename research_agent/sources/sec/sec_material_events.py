from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from typing import Any


MATERIAL_8K_ITEMS = {"1.05", "8.01"}


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
        return "\n".join(
            line for line in (" ".join(part.split()) for part in "".join(self.parts).splitlines()) if line
        )


def select_material_event_filings(
    submissions: dict[str, Any],
    *,
    as_of_date: str,
    lookback_days: int = 120,
) -> list[dict[str, str]]:
    recent = submissions.get("filings", {}).get("recent", {})
    cutoff = date.fromisoformat(as_of_date).toordinal() - lookback_days
    rows: list[dict[str, str]] = []
    forms = recent.get("form") or []
    for index, form in enumerate(forms):
        if form != "8-K":
            continue
        filing_date = _at(recent, "filingDate", index)
        accession = _at(recent, "accessionNumber", index)
        primary_document = _at(recent, "primaryDocument", index)
        items = {
            value.strip()
            for value in _at(recent, "items", index).replace(" ", "").split(",")
            if value.strip()
        }
        try:
            filing_day = date.fromisoformat(filing_date)
        except ValueError:
            continue
        if (
            not accession
            or not primary_document
            or filing_date > as_of_date
            or filing_day.toordinal() < cutoff
            or not items.intersection(MATERIAL_8K_ITEMS)
        ):
            continue
        rows.append(
            {
                "filing_date": filing_date,
                "accession_number": accession,
                "primary_document": primary_document,
                "items": ",".join(sorted(items.intersection(MATERIAL_8K_ITEMS))),
            }
        )
    return sorted(rows, key=lambda row: (row["filing_date"], row["accession_number"]))


def build_material_event_payload(
    *,
    ticker: str,
    cik: str,
    filings: list[tuple[dict[str, str], str]],
    retrieved_at: str,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    sources_checked: list[str] = []
    cik_digits = str(int(cik))
    for filing, html in filings:
        accession_digits = filing["accession_number"].replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_digits}/"
            f"{accession_digits}/{filing['primary_document']}"
        )
        sources_checked.append(url)
        parser = _TextParser()
        parser.feed(html)
        classified = classify_material_event_text(parser.text())
        if classified is None:
            continue
        event_type, headline, summary = classified
        events.append(
            {
                "event_type": event_type,
                "date": filing["filing_date"],
                "headline": headline,
                "summary": summary,
                "material": True,
                "source_id": f"SEC_CIK{cik_digits.zfill(10)}_{accession_digits}",
                "source_type": "sec_filing",
                "authority_rank": 1,
                "url": url,
                "retrieved_at": retrieved_at,
            }
        )
    return {
        "coverage_status": "available",
        "checked_at": retrieved_at,
        "window_start": min((row[0]["filing_date"] for row in filings), default=None),
        "window_end": max((row[0]["filing_date"] for row in filings), default=None),
        "sources_checked": sources_checked,
        "events": events,
    }


def classify_material_event_text(text: str) -> tuple[str, str, str] | None:
    compact = " ".join(str(text or "").split())
    folded = compact.casefold()
    cyber = any(
        token in folded
        for token in (
            "ransomware",
            "cybersecurity incident",
            "cyber incident",
            "unauthorized access",
        )
    )
    disrupted = bool(
        re.search(
            r"\b(?:temporarily suspended|production operations.{0,80}suspended|"
            r"operational disruption|business interruption)\b",
            folded,
        )
    )
    restored = bool(
        re.search(
            r"\b(?:resumed (?:the )?majority|has resumed|operations have resumed|"
            r"significant progress in restoring|restoration progress|recovery progress)\b",
            folded,
        )
    )
    recalled = "recall" in folded and any(
        token in folded for token in ("product", "safety", "consumer")
    )
    if not any((cyber, disrupted, restored, recalled)):
        return None
    if restored:
        event_type = "operational_recovery"
        headline = "Issuer disclosed operational recovery progress"
    elif cyber:
        event_type = "cyber_incident"
        headline = "Issuer disclosed a cybersecurity incident"
    elif recalled:
        event_type = "product_recall"
        headline = "Issuer disclosed a product recall"
    else:
        event_type = "operational_disruption"
        headline = "Issuer disclosed an operational disruption"
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    selected = [
        sentence
        for sentence in sentences
        if any(
            token in sentence.casefold()
            for token in (
                "ransomware",
                "unauthorized access",
                "temporarily suspended",
                "production operations",
                "resumed the majority",
                "restore impacted",
                "material impact",
                "product quality",
                "recall",
            )
        )
    ][:4]
    summary = " ".join(selected)
    if not summary:
        summary = headline + "."
    return event_type, headline, summary[:1800]


def _at(payload: dict[str, Any], key: str, index: int) -> str:
    values = payload.get(key) or []
    return str(values[index] or "") if index < len(values) else ""
