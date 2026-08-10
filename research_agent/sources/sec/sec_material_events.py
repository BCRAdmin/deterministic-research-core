from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from typing import Any


MATERIAL_8K_ITEMS = {
    "1.01",  # material agreement
    "1.02",  # termination of material agreement
    "1.03",  # bankruptcy or receivership
    "1.05",  # material cybersecurity incident
    "2.01",  # acquisition or disposition
    "2.03",  # direct financial obligation
    "2.04",  # acceleration or trigger event
    "2.05",  # exit or disposal plan
    "2.06",  # material impairment
    "3.01",  # listing or continued-listing notice
    "3.02",  # unregistered sale of securities
    "4.01",  # auditor change
    "4.02",  # non-reliance on financial statements
    "5.01",  # change in control
    "5.02",  # director or officer change
    "5.03",  # charter/bylaw change
    "5.07",  # shareholder vote
    "7.01",  # Regulation FD disclosure
    "8.01",  # other material event
}

ITEM_EVENT_TYPES = {
    "1.01": ("material_agreement", "Issuer disclosed a material agreement"),
    "1.02": ("agreement_termination", "Issuer disclosed termination of a material agreement"),
    "1.03": ("bankruptcy_or_receivership", "Issuer disclosed a bankruptcy or receivership event"),
    "1.05": ("cyber_incident", "Issuer filed a material cybersecurity disclosure"),
    "2.01": ("acquisition_or_disposition", "Issuer disclosed an acquisition or disposition"),
    "2.03": ("financing_obligation", "Issuer disclosed a material financial obligation"),
    "2.04": ("financing_trigger", "Issuer disclosed a financing trigger or acceleration event"),
    "2.05": ("restructuring", "Issuer disclosed an exit or disposal plan"),
    "2.06": ("impairment", "Issuer disclosed a material impairment"),
    "3.01": ("listing_notice", "Issuer disclosed a listing-status notice"),
    "3.02": ("securities_issuance", "Issuer disclosed an unregistered securities sale"),
    "4.01": ("auditor_change", "Issuer disclosed an auditor change"),
    "4.02": ("financial_statement_non_reliance", "Issuer disclosed non-reliance on financial statements"),
    "5.01": ("change_in_control", "Issuer disclosed a change in control"),
    "5.02": ("leadership_change", "Issuer disclosed a director or officer change"),
    "5.03": ("governance_change", "Issuer disclosed a charter or bylaw change"),
    "5.07": ("shareholder_vote", "Issuer disclosed shareholder voting results"),
    "7.01": ("regulation_fd_disclosure", "Issuer furnished a Regulation FD disclosure"),
    "8.01": ("other_material_event", "Issuer disclosed another material event"),
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
        return "\n".join(
            line for line in (" ".join(part.split()) for part in "".join(self.parts).splitlines()) if line
        )


def select_material_event_filings(
    submissions: dict[str, Any],
    *,
    as_of_date: str,
    lookback_days: int = 120,
) -> list[dict[str, str]]:
    return [
        {
            "filing_date": row["filing_date"],
            "accession_number": row["accession_number"],
            "primary_document": row["primary_document"],
            "items": row["material_items"],
        }
        for row in inventory_recent_8k_filings(
            submissions,
            as_of_date=as_of_date,
            lookback_days=lookback_days,
        )
        if row["disposition"] == "material_candidate"
    ]


def inventory_recent_8k_filings(
    submissions: dict[str, Any],
    *,
    as_of_date: str,
    lookback_days: int = 120,
) -> list[dict[str, str]]:
    """Disposition every 8-K returned by the scanned SEC submissions payload."""

    recent = submissions.get("filings", {}).get("recent", {})
    cutoff = date.fromisoformat(as_of_date).toordinal() - lookback_days
    rows: list[dict[str, str]] = []
    seen_accessions: set[str] = set()
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
        material_items = items.intersection(MATERIAL_8K_ITEMS)
        if not accession or not primary_document:
            disposition = "invalid_metadata"
            reason = "accession number or primary document is missing"
        elif accession in seen_accessions:
            disposition = "duplicate_accession"
            reason = "duplicate SEC accession in submissions payload"
        else:
            seen_accessions.add(accession)
            try:
                filing_day = date.fromisoformat(filing_date)
            except ValueError:
                disposition = "invalid_metadata"
                reason = "filing date is missing or invalid"
            else:
                if filing_date > as_of_date:
                    disposition = "excluded_after_as_of"
                    reason = "filing occurred after the analysis cutoff"
                elif filing_day.toordinal() < cutoff:
                    disposition = "excluded_outside_lookback"
                    reason = f"filing is older than the {lookback_days}-day event window"
                elif material_items:
                    disposition = "material_candidate"
                    reason = "SEC item requires primary-document materiality review"
                else:
                    disposition = "non_material_with_reason"
                    reason = "8-K contains no Room16 material-event item"
        rows.append(
            {
                "filing_date": filing_date,
                "accession_number": accession,
                "primary_document": primary_document,
                "items": ",".join(sorted(items)),
                "material_items": ",".join(sorted(material_items)),
                "disposition": disposition,
                "reason": reason,
            }
        )
    return sorted(
        rows,
        key=lambda row: (row["filing_date"], row["accession_number"]),
    )


def build_material_event_payload(
    *,
    ticker: str,
    cik: str,
    filings: list[tuple[dict[str, str], str]],
    retrieved_at: str,
    candidate_inventory: list[dict[str, str]] | None = None,
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
        items = {
            item for item in str(filing.get("items") or "").split(",") if item
        }
        classified = classify_material_event_text(parser.text(), items=items)
        if classified is None:
            raise ValueError(
                "selected SEC material-event filing has no deterministic disposition"
            )
        event_type, headline, summary = classified
        source_id = f"SEC_CIK{cik_digits.zfill(10)}_{accession_digits}"
        events.append(
            {
                "event_type": event_type,
                "date": filing["filing_date"],
                "headline": headline,
                "summary": summary,
                "material": True,
                "source_id": source_id,
                "source_type": "sec_filing",
                "authority_rank": 1,
                "url": url,
                "retrieved_at": retrieved_at,
            }
        )
    material_dispositions = [
        {
            "source_id": event["source_id"],
            "filing_date": event["date"],
            "items": next(
                filing["items"]
                for filing, _html in filings
                if event["source_id"].endswith(
                    filing["accession_number"].replace("-", "")
                )
            ),
            "disposition": "material_event",
            "event_type": event["event_type"],
        }
        for event in events
    ]
    if candidate_inventory is None:
        dispositions = material_dispositions
    else:
        by_accession = {
            str(item["source_id"]).rsplit("_", 1)[-1]: item
            for item in material_dispositions
        }
        dispositions = []
        for candidate in candidate_inventory:
            accession_digits = str(
                candidate.get("accession_number") or ""
            ).replace("-", "")
            resolved = by_accession.get(accession_digits)
            if candidate.get("disposition") == "material_candidate" and resolved:
                dispositions.append(resolved)
            else:
                inventory_disposition = str(candidate.get("disposition") or "")
                final_disposition = {
                    "duplicate_accession": "duplicate",
                    "invalid_metadata": "parse_failed",
                    "excluded_after_as_of": "non_material_with_reason",
                    "excluded_outside_lookback": "superseded",
                    "non_material_with_reason": "non_material_with_reason",
                    "material_candidate": "parse_failed",
                }.get(inventory_disposition, "parse_failed")
                dispositions.append(
                    {
                        "source_id": (
                            f"SEC_ACCESSION_{accession_digits}"
                            if accession_digits
                            else "SEC_ACCESSION_MISSING"
                        ),
                        "filing_date": candidate.get("filing_date"),
                        "items": candidate.get("items"),
                        "disposition": final_disposition,
                        "inventory_disposition": inventory_disposition,
                        "reason": candidate.get("reason"),
                    }
                )
    unresolved = [
        item
        for item in dispositions
        if item.get("disposition") == "parse_failed"
    ]
    allowed_dispositions = {
        "material_event",
        "non_material_with_reason",
        "duplicate",
        "superseded",
        "parse_failed",
    }
    if any(
        item.get("disposition") not in allowed_dispositions for item in dispositions
    ):
        raise ValueError("SEC filing inventory contains a non-canonical disposition")
    return {
        "coverage_status": "complete" if not unresolved else "incomplete",
        "checked_at": retrieved_at,
        "window_start": min((row[0]["filing_date"] for row in filings), default=None),
        "window_end": max((row[0]["filing_date"] for row in filings), default=None),
        "sources_checked": sources_checked,
        "candidate_count": len(dispositions),
        "fetched_material_candidate_count": len(filings),
        "all_candidates_dispositioned": not unresolved,
        "filing_dispositions": dispositions,
        "events": events,
    }


def classify_material_event_text(
    text: str,
    *,
    items: set[str] | None = None,
) -> tuple[str, str, str] | None:
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
        recognized_items = sorted((items or set()).intersection(ITEM_EVENT_TYPES))
        if not recognized_items:
            return None
        primary_item = recognized_items[0]
        event_type, headline = ITEM_EVENT_TYPES[primary_item]
        sentences = re.split(r"(?<=[.!?])\s+", compact)
        substantive = next(
            (
                sentence
                for sentence in sentences
                if len(sentence.split()) >= 8
                and not sentence.casefold().startswith("item ")
            ),
            "",
        )
        summary = (
            f"SEC Form 8-K Item {', '.join(recognized_items)}. {substantive}"
        ).strip()
        return event_type, headline, summary[:1800]
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
