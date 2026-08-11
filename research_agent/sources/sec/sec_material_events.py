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
    "2.02",  # results of operations and financial condition
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
    "2.02": ("results_announcement", "Issuer disclosed results of operations"),
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
    lookback_days: int | None = None,
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
    lookback_days: int | None = None,
) -> list[dict[str, str]]:
    """Disposition every 8-K in the protocol year through the as-of date."""

    recent = submissions.get("filings", {}).get("recent", {})
    as_of = date.fromisoformat(as_of_date)
    cutoff = (
        as_of.toordinal() - lookback_days
        if lookback_days is not None
        else date(as_of.year, 1, 1).toordinal()
    )
    horizon_label = (
        f"{lookback_days}-day event window"
        if lookback_days is not None
        else f"{as_of.year} protocol year"
    )
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
                    reason = f"filing is outside the {horizon_label}"
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
    as_of_date: str | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    material_dispositions: list[dict[str, Any]] = []
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
        classifications = classify_material_event_sections(parser.text(), items=items)
        recognized_items = sorted(items.intersection(ITEM_EVENT_TYPES))
        classified_items = {item for item, *_rest in classifications if item}
        if not classifications or (
            recognized_items and classified_items != set(recognized_items)
        ):
            raise ValueError(
                "selected SEC material-event filing has no complete item-specific disposition"
            )
        base_source_id = f"SEC_CIK{cik_digits.zfill(10)}_{accession_digits}"
        filing_events: list[dict[str, Any]] = []
        for item, event_type, headline, summary in classifications:
            source_id = (
                base_source_id
                if len(classifications) == 1
                else f"{base_source_id}_ITEM_{item.replace('.', '') or 'EVENT'}"
            )
            event = {
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
                "filing_items": [item] if item else [],
                "content_complete": True,
            }
            events.append(event)
            filing_events.append(event)
        material_dispositions.append(
            {
                "source_id": base_source_id,
                "filing_date": filing["filing_date"],
                "items": filing["items"],
                "disposition": "material_event",
                "event_types": [event["event_type"] for event in filing_events],
                "content_complete": True,
                "item_dispositions": [
                    {
                        "item": item,
                        "status": "content_complete",
                    }
                    for item in recognized_items
                ],
            }
        )
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
    inferred_as_of = as_of_date or max(
        (
            str(row.get("filing_date") or "")
            for row in (candidate_inventory or [])
            if str(row.get("filing_date") or "") <= retrieved_at[:10]
        ),
        default=retrieved_at[:10],
    )
    protocol_start = f"{inferred_as_of[:4]}-01-01"
    protocol_candidate_count = sum(
        protocol_start <= str(row.get("filing_date") or "") <= inferred_as_of
        for row in dispositions
    )
    payload = {
        "coverage_status": "complete" if not unresolved else "incomplete",
        "checked_at": retrieved_at,
        "protocol_window_start": protocol_start,
        "protocol_window_end": inferred_as_of,
        "window_start": protocol_start,
        "window_end": inferred_as_of,
        "sources_checked": sources_checked,
        "candidate_count": len(dispositions),
        "protocol_candidate_count": protocol_candidate_count,
        "fetched_material_candidate_count": len(filings),
        "all_candidates_dispositioned": not unresolved,
        "source_inventory_complete": not unresolved,
        "material_event_content_complete": all(
            event.get("content_complete") is True for event in events
        ),
        "filing_dispositions": dispositions,
        "events": events,
    }
    verification = verify_material_event_payload(payload)
    payload["coverage_status"] = "complete" if verification["verified"] else "incomplete"
    payload["source_inventory_complete"] = verification["source_inventory_complete"]
    payload["material_event_content_complete"] = verification[
        "material_event_content_complete"
    ]
    return payload


def verify_material_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    start = str(payload.get("protocol_window_start") or payload.get("window_start") or "")
    end = str(payload.get("protocol_window_end") or payload.get("window_end") or "")
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        failures.append("protocol_horizon_invalid")
        start_date = end_date = date.min
    dispositions = payload.get("filing_dispositions") or []
    if not isinstance(dispositions, list):
        dispositions = []
        failures.append("filing_dispositions_missing")
    protocol_rows = [
        item
        for item in dispositions
        if isinstance(item, dict)
        and start <= str(item.get("filing_date") or "") <= end
    ]
    expected_protocol_count = payload.get("protocol_candidate_count")
    inventory_complete = (
        isinstance(expected_protocol_count, int)
        and expected_protocol_count == len(protocol_rows)
        and not any(
        item.get("disposition") in {"superseded", "parse_failed"}
        for item in protocol_rows
        )
    )
    if not inventory_complete:
        failures.append("source_inventory_incomplete")
    events = payload.get("events") or []
    if not isinstance(events, list):
        events = []
    event_ids = [str(item.get("source_id") or "") for item in events if isinstance(item, dict)]
    content_complete = len(event_ids) == len(set(event_ids)) and all(
        isinstance(event, dict)
        and event.get("content_complete") is True
        and bool(str(event.get("summary") or "").strip())
        and all(
            _item_content_complete(
                str(item),
                str(event.get("summary") or ""),
            )
            for item in event.get("filing_items") or []
        )
        for event in events
    )
    material_rows = [
        item for item in protocol_rows if item.get("disposition") == "material_event"
    ]
    if any(
        item.get("content_complete") is not True
        or not item.get("item_dispositions")
        or any(
            detail.get("status") != "content_complete"
            for detail in item.get("item_dispositions") or []
            if isinstance(detail, dict)
        )
        for item in material_rows
    ):
        content_complete = False
    if not content_complete:
        failures.append("material_event_content_incomplete")
    if start_date.year != end_date.year or start_date.month != 1 or start_date.day != 1:
        failures.append("protocol_horizon_not_calendar_year")
    return {
        "verified": not failures,
        "status": "pass" if not failures else "fail",
        "blocking_failures": sorted(set(failures)),
        "source_inventory_complete": inventory_complete,
        "material_event_content_complete": content_complete,
    }


def classify_material_event_text(
    text: str,
    *,
    items: set[str] | None = None,
) -> tuple[str, str, str] | None:
    classified = classify_material_event_sections(text, items=items)
    if not classified:
        return None
    _item, event_type, headline, summary = classified[0]
    return event_type, headline, summary


def classify_material_event_sections(
    text: str,
    *,
    items: set[str] | None = None,
) -> list[tuple[str, str, str, str]]:
    compact = " ".join(str(text or "").split())
    folded = compact.casefold()
    recognized_items = sorted((items or set()).intersection(ITEM_EVENT_TYPES))
    if recognized_items:
        classified: list[tuple[str, str, str, str]] = []
        for item in recognized_items:
            section = _extract_item_section(compact, item)
            if not _item_content_complete(item, section):
                continue
            event_type, headline = ITEM_EVENT_TYPES[item]
            summary = f"SEC Form 8-K Item {item}. {_summary_sentences(section)}"
            if not _item_summary_complete(item, section, summary):
                continue
            classified.append((item, event_type, headline, summary[:1800]))
        if classified or any(item not in {"7.01", "8.01"} for item in recognized_items):
            return classified
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
        return []
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
    return [
        (item, event_type, headline, summary[:1800])
        for item in (recognized_items or [""])
    ]


def _extract_item_section(text: str, item: str) -> str:
    heading = re.compile(
        rf"\bItem\s+{re.escape(item)}\b[.\s:-]*",
        re.IGNORECASE,
    )
    match = heading.search(text)
    if not match:
        return ""
    next_item = re.search(r"\bItem\s+\d\.\d{2}\b", text[match.end() :], re.IGNORECASE)
    end = match.end() + next_item.start() if next_item else len(text)
    return " ".join(text[match.end() : end].split())


def _summary_sentences(section: str) -> str:
    protected = section
    abbreviations = (
        "Mr.",
        "Ms.",
        "Mrs.",
        "Dr.",
        "Jr.",
        "Sr.",
        "Inc.",
        "Corp.",
        "Co.",
        "N.A.",
        "U.S.",
    )
    for abbreviation in abbreviations:
        protected = protected.replace(abbreviation, abbreviation.replace(".", "\u2024"))
    protected = re.sub(
        r"\b([A-Z])\.",
        lambda match: f"{match.group(1)}\u2024",
        protected,
    )
    sentences = [
        sentence.replace("\u2024", ".").strip()
        for sentence in re.split(r"(?<=[.!?])\s+", protected)
        if len(sentence.split()) >= 4
    ]
    return " ".join(sentences[:6]) or section[:1600]


def _item_summary_complete(item: str, section: str, summary: str) -> bool:
    """Require Item 5.02 summaries to retain opening names and actions."""

    if item != "5.02":
        return True
    narrative = section[:1600]
    names = set()
    for match in re.finditer(
        r"\b(?:Mr\.|Ms\.|Mrs\.|Dr\.)\s+"
        r"((?:[A-Z][A-Za-z'’-]*\.?\s+){0,2}[A-Z][A-Za-z'’-]+)",
        narrative,
    ):
        names.add(match.group(1).split()[-1].rstrip("."))
    if names and any(name not in summary for name in names):
        return False
    action_patterns = (
        r"\bretir\w*\b",
        r"\bpromot\w*\b",
        r"\bresign\w*\b",
        r"\bappoint\w*\b",
        r"\belect\w*\b",
        r"\bdepart\w*\b",
    )
    for pattern in action_patterns:
        if re.search(pattern, narrative, re.IGNORECASE) and not re.search(
            pattern,
            summary,
            re.IGNORECASE,
        ):
            return False
    return True


def _item_content_complete(item: str, section: str) -> bool:
    folded = " ".join(section.casefold().split())
    if len(folded.split()) < 8:
        return False
    required_patterns = {
        "1.01": r"\b(?:agreement|facility|contract|amendment)\b",
        "2.02": r"\b(?:results|operations|financial condition|earnings|exhibit)\b",
        "2.03": r"\b(?:debt|obligation|credit|facility|agreement|incorporated by reference)\b",
        "5.02": r"\b(?:appoint|elect|resign|retir|promot|depart|ceased|terminate)\w*\b",
        "5.07": r"\b(?:vote|voting|shares|proposal|elected)\w*\b",
    }
    pattern = required_patterns.get(item)
    if pattern and not re.search(pattern, folded, re.IGNORECASE):
        return False
    if item == "5.02" and not re.search(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b", section):
        return False
    return True


def _at(payload: dict[str, Any], key: str, index: int) -> str:
    values = payload.get(key) or []
    return str(values[index] or "") if index < len(values) else ""
