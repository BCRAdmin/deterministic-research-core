"""Deterministic neutral HTML/text normalization and observation discovery."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from pydantic import Field

from research_agent.compiler_foundation.canonical import sha256_bytes, sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

from .contracts import DocumentObservationIR

SPACE = re.compile(r"\s+")
NUMBER = re.compile(r"(?<![A-Za-z0-9])[-+]?\$?\d[\d,]*(?:\.\d+)?%?(?![A-Za-z0-9])")


def _clean(value: str) -> str:
    return SPACE.sub(" ", value).strip()


class NormalizedTable(StrictModel):
    table_index: int = Field(ge=0)
    rows: tuple[tuple[str, ...], ...]


class NormalizedDocument(StrictModel):
    contract_id: str = "room16.rfc0011.normalized_document"
    contract_version: int = 1
    source_document_sha256: str
    document_id: str
    accession_number: str
    report_date: str | None
    filing_date: str
    document_name: str
    media_type: str
    normalized_text_blocks: tuple[str, ...]
    normalized_tables: tuple[NormalizedTable, ...]
    normalizer_version: int = 1
    normalizer_sha256: str


class _NeutralHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._buffer: list[str] = []
        self.tables: list[list[list[str]]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._flush()
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
        elif tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self.tables.append(self._table)
            self._table = None
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4"}:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        else:
            self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        value = _clean(" ".join(self._buffer))
        if value:
            self.blocks.append(value)
        self._buffer.clear()


def normalize_document(
    payload: bytes,
    *,
    document_id: str,
    accession_number: str,
    report_date: str | None,
    filing_date: str,
    document_name: str,
    media_type: str,
) -> NormalizedDocument:
    text = payload.decode("utf-8", errors="replace")
    if media_type in {"text/html", "application/xhtml+xml"} or "<html" in text[:1000].lower():
        parser = _NeutralHTMLParser()
        parser.feed(text)
        parser.close()
        blocks = tuple(parser.blocks)
        tables = tuple(
            NormalizedTable(table_index=index, rows=tuple(tuple(row) for row in rows))
            for index, rows in enumerate(parser.tables)
        )
    else:
        blocks = tuple(value for line in text.splitlines() if (value := _clean(line)))
        tables = ()
    body = {
        "source_document_sha256": sha256_bytes(payload),
        "document_id": document_id,
        "accession_number": accession_number,
        "report_date": report_date,
        "filing_date": filing_date,
        "document_name": document_name,
        "media_type": media_type,
        "normalized_text_blocks": blocks,
        "normalized_tables": [table.model_dump(mode="json") for table in tables],
        "normalizer_version": 1,
    }
    return NormalizedDocument(**body, normalizer_sha256=sha256_json(body))


def discover_observations(
    document: NormalizedDocument,
    label_profiles: dict[str, tuple[str, ...]],
) -> tuple[DocumentObservationIR, ...]:
    """Find evidence-bound label contexts; never guess among numeric candidates."""

    contexts: list[tuple[str, str, str]] = []
    contexts.extend(("text_span", f"block:{index}", block) for index, block in enumerate(document.normalized_text_blocks))
    for table in document.normalized_tables:
        for row_index, row in enumerate(table.rows):
            contexts.append(("table_row", f"table:{table.table_index}:row:{row_index}", " | ".join(row)))
    observations: list[DocumentObservationIR] = []
    for metric_id, aliases in sorted(label_profiles.items()):
        for locator_type, locator, context in contexts:
            lowered = context.casefold()
            matched = next((alias for alias in aliases if alias.casefold() in lowered), None)
            if matched is None:
                continue
            tokens = NUMBER.findall(context)
            ambiguity = () if len(tokens) == 1 else ("NUMERIC_CARDINALITY_NOT_ONE",)
            observations.append(
                DocumentObservationIR.create(
                    source_document_sha256=document.source_document_sha256,
                    locator_type=locator_type,
                    locator=locator,
                    reported_label=matched,
                    raw_value_text=" | ".join(tokens),
                    parsed_numeric_value_or_null=tokens[0] if len(tokens) == 1 else None,
                    reported_unit_text_or_null="percent" if len(tokens) == 1 and tokens[0].endswith("%") else None,
                    reported_period_text_or_null=None,
                    reported_basis_text_or_null=metric_id,
                    context_text=context[:2000],
                    ambiguity_codes=ambiguity,
                    trusted_numeric=len(tokens) == 1,
                )
            )
    return tuple(sorted(observations, key=lambda item: item.observation_id))
