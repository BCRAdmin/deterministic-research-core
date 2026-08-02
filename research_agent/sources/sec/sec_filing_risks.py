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
_ITEM_HEADING = re.compile(r"^item\s+\d+[a-z]?[.\s]", re.IGNORECASE)
_RISK_LANGUAGE = re.compile(
    r"\b(could|may|might|failure|fail|unable|adverse|adversely|competition|"
    r"volatility|subject to|subjects us to|presents a number of risks)\b",
    re.IGNORECASE,
)
_GENERIC_PREFIXES = (
    "our business results are subject",
    "the risks described below",
    "risk factors should be read",
    "for a discussion of risk factors",
)


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
        if tag in {"b", "strong"} or "font-weight:700" in style or "font-weight:bold" in style:
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
    blocks = parser.finish()
    starts = [
        index
        for index, (block, _) in enumerate(blocks)
        if _compact_heading(block) in {"riskfactors", "item1ariskfactors"}
    ]
    best: list[str] = []
    for start in starts:
        end = next(
            (
                index
                for index in range(start + 1, len(blocks))
                if _is_later_item_heading(blocks[index][0])
            ),
            len(blocks),
        )
        candidates: list[tuple[str, bool]] = []
        seen: set[str] = set()
        for block, emphasized in blocks[start + 1 : end]:
            if not _is_risk_heading(block):
                continue
            key = block.casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append((block, emphasized))
        emphasized = [block for block, is_emphasized in candidates if is_emphasized]
        section_risks = emphasized or [block for block, _ in candidates]
        if len(section_risks) > len(best):
            best = section_risks
    return best[:30]


def build_sec_risk_evidence(
    *,
    ticker: str,
    filing: SecFilingReference,
    html: str,
    retrieved_at: str,
) -> list[EvidenceItem]:
    symbol = ticker.strip().upper()
    period = (
        f"{filing.form} period ended {filing.report_date}"
        if filing.report_date
        else filing.form
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
            supports_claims=["company_risk_analysis"],
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
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "filing": filing.to_dict(),
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
        item.ticker != symbol
        or item.claim_type != "risk"
        or item.source_type != "sec_filing"
        for item in items
    ):
        raise ValueError("SEC risk evidence identity or authority mismatch")
    return items


def _array_value(payload: dict[str, Any], key: str, index: int) -> str:
    values = payload.get(key) or []
    if index >= len(values):
        return ""
    return str(values[index] or "").strip()


def _normalized_heading(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def _compact_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _is_later_item_heading(text: str) -> bool:
    normalized = _normalized_heading(text)
    return bool(_ITEM_HEADING.match(normalized)) and not normalized.startswith(
        "item 1a"
    )


def _is_risk_heading(text: str) -> bool:
    stripped = text.strip()
    lowered = stripped.lower()
    if not 40 <= len(stripped) <= 320:
        return False
    if stripped.startswith(("•", "●", "▪", "-")) or not stripped.endswith("."):
        return False
    if stripped.isupper() or lowered.startswith(_GENERIC_PREFIXES):
        return False
    if stripped.count(". ") > 1:
        return False
    return bool(_RISK_LANGUAGE.search(stripped))
