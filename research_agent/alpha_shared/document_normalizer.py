"""Deterministic neutral HTML/text normalization and observation discovery."""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import NamedTuple

from pydantic import Field

from research_agent.compiler_foundation.canonical import sha256_bytes, sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

from .contracts import DocumentObservationIR
from .reit_total_row_grammar import is_plain_reported_ffo_total_label

SPACE = re.compile(r"\s+")
NUMBER = re.compile(r"(?<![A-Za-z0-9])[-+]?\$?\d[\d,]*(?:\.\d+)?%?(?![A-Za-z0-9])")
PUNCTUATION = re.compile(r"[^\w%$.-]+", re.UNICODE)
HEADER_SIGNAL = re.compile(
    r"(?:\b(?:19|20)\d{2}\b|\bq[1-4]\b|\b(?:current|prior|year|quarter|month|week|day)\b|"
    r"\b(?:ended|ending|as of|percent|percentage|usd|dollars?|millions?|billions?)\b|[%$])",
    re.IGNORECASE,
)
TEMPORAL_FRAGMENT = re.compile(
    r"^(?:(?:Three|Six|Nine|Twelve) Months Ended(?: [A-Za-z]+ \d{1,2},?)?|"
    r"As of(?: [A-Za-z]+ \d{1,2},?)?|[A-Za-z]+ \d{1,2},?|(?:19|20)\d{2}|"
    r"Q[1-4](?: (?:19|20)\d{2})?|Current|Prior|Current Year|Prior Year)$",
    re.IGNORECASE,
)
COMPLETE_TEMPORAL_HEADER = re.compile(
    r"^(?:(?:Three|Six|Nine|Twelve) Months Ended [A-Za-z]+ \d{1,2},? (?:19|20)\d{2}|"
    r"As of [A-Za-z]+ \d{1,2},? (?:19|20)\d{2}|Q[1-4] (?:19|20)\d{2}|"
    r"Current|Prior|Current Year|Prior Year)$",
    re.IGNORECASE,
)
ZERO_WIDTH = re.compile(r"[\u200b\u200c\u200d\ufeff]")
CURRENCY_OR_UNIT_MARKER = re.compile(r"^(?:[$€£¥]|US\$|USD|EUR|GBP|JPY)$", re.IGNORECASE)


def _clean(value: str) -> str:
    return SPACE.sub(" ", value).strip()


def _semantic_cell(value: str) -> str:
    """Treat presentation-only zero-width characters as empty for table semantics."""

    return _clean(ZERO_WIDTH.sub("", value))


def _normalized_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return _clean(PUNCTUATION.sub(" ", normalized))


def _contains_alias(value: str, alias: str) -> bool:
    haystack = f" {_normalized_phrase(value)} "
    needle = _normalized_phrase(alias)
    return bool(needle) and f" {needle} " in haystack


def classify_numeric_role(*, context: str, token: str, label: str) -> str:
    """Classify a nearby number before any trust decision."""

    escaped = re.escape(token)
    normalized = _normalized_phrase(context)
    if re.search(rf"\(\s*{escaped}\s*\)", context):
        return "FOOTNOTE_MARKER"
    if re.search(rf"\bnote\s+{escaped}\b", context, re.IGNORECASE):
        return "NOTE_REFERENCE"
    if re.search(rf"\b(?:section|item|page)\s+{escaped}\b", context, re.IGNORECASE):
        return "SECTION_REFERENCE"
    if re.search(
        rf"\b{escaped}\s+(?:months?|years?|quarters?|weeks?|days?)\b", context, re.IGNORECASE
    ):
        return "PERIOD_VALUE"
    bare = token.replace("$", "").replace(",", "").rstrip("%")
    if re.fullmatch(r"(?:19|20)\d{2}", bare) or re.search(
        rf"\b{escaped}[-/]\d{{1,2}}[-/]\d{{1,4}}\b", context
    ):
        return "DATE_VALUE"
    if re.search(rf"\b(?:first|second|third|number|count)\s+{escaped}\b", context, re.IGNORECASE):
        return "ORDINAL_OR_COUNT"
    if token.endswith("%") and not _contains_alias(normalized, label):
        return "AMBIGUOUS"
    return "AMBIGUOUS"


class NormalizedTable(StrictModel):
    table_index: int = Field(ge=0)
    rows: tuple[tuple[str, ...], ...]
    context_blocks: tuple[str, ...] = ()
    column_origins: tuple[tuple[int, ...], ...] = ()


class TemporalHeaderBinding(NamedTuple):
    value: str
    target_value_column: int
    header_row_index: int
    temporal_anchor_column: int
    binding_reason: str
    origin_cell_coordinates: tuple[int, int]


def bind_temporal_header_fragment(
    *,
    table: NormalizedTable,
    header_row_index: int,
    target_value_column: int,
    numeric_value_columns: frozenset[int],
    label_column: int,
) -> TemporalHeaderBinding | None:
    """Bind one temporal header row to a numeric column using only table structure."""

    if header_row_index >= len(table.rows):
        return None
    row = table.rows[header_row_index]
    origins = (
        table.column_origins[header_row_index]
        if header_row_index < len(table.column_origins)
        else tuple(range(len(row)))
    )

    def candidate(column: int) -> tuple[str, int]:
        origin = origins[column] if column < len(origins) else column
        value = _semantic_cell(row[origin]) if origin < len(row) else ""
        return value, origin

    direct, direct_origin = candidate(target_value_column)
    if direct and TEMPORAL_FRAGMENT.fullmatch(direct):
        return TemporalHeaderBinding(
            value=direct,
            target_value_column=target_value_column,
            header_row_index=header_row_index,
            temporal_anchor_column=direct_origin,
            binding_reason="COLUMN_ORIGIN",
            origin_cell_coordinates=(header_row_index, direct_origin),
        )
    if direct and not CURRENCY_OR_UNIT_MARKER.fullmatch(direct):
        return None

    visited_origins = {direct_origin}
    for column in range(target_value_column - 1, label_column, -1):
        if column in numeric_value_columns:
            break
        value, origin = candidate(column)
        if origin in visited_origins:
            continue
        visited_origins.add(origin)
        if not value or CURRENCY_OR_UNIT_MARKER.fullmatch(value):
            continue
        if TEMPORAL_FRAGMENT.fullmatch(value):
            return TemporalHeaderBinding(
                value=value,
                target_value_column=target_value_column,
                header_row_index=header_row_index,
                temporal_anchor_column=origin,
                binding_reason="NEAREST_LEFT_WITHIN_MEASURE_GROUP",
                origin_cell_coordinates=(header_row_index, origin),
            )
        break
    return None


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
        self.table_column_origins: list[list[list[int]]] = []
        self.table_contexts: list[tuple[str, ...]] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._row_origins: list[int] | None = None
        self._cell: list[str] | None = None
        self._cell_colspan = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._flush()
            self._table = []
            self.table_column_origins.append([])
            self.table_contexts.append(tuple(self.blocks[-4:]))
        elif tag == "tr" and self._table is not None:
            self._row = []
            self._row_origins = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []
            attributes = {key.casefold(): value for key, value in attrs}
            try:
                self._cell_colspan = max(1, min(50, int(attributes.get("colspan") or "1")))
            except ValueError:
                self._cell_colspan = 1
        elif tag in {"p", "div", "li", "br", "h1", "h2", "h3", "h4"}:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None and self._row is not None:
            value = _clean(" ".join(self._cell))
            origin = len(self._row)
            self._row.extend([value, *("" for _ in range(self._cell_colspan - 1))])
            if self._row_origins is not None:
                self._row_origins.extend([origin] * self._cell_colspan)
            self._cell = None
            self._cell_colspan = 1
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(self._row):
                self._table.append(self._row)
                self.table_column_origins[-1].append(
                    self._row_origins or list(range(len(self._row)))
                )
            self._row = None
            self._row_origins = None
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
            NormalizedTable(
                table_index=index,
                rows=tuple(tuple(row) for row in rows),
                context_blocks=(
                    parser.table_contexts[index] if index < len(parser.table_contexts) else ()
                ),
                column_origins=(
                    tuple(tuple(row) for row in parser.table_column_origins[index])
                    if index < len(parser.table_column_origins)
                    else ()
                ),
            )
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
        "normalizer_version": 2,
    }
    return NormalizedDocument(**body, normalizer_sha256=sha256_json(body))


def discover_observations(
    document: NormalizedDocument,
    label_profiles: dict[str, tuple[str, ...]],
) -> tuple[DocumentObservationIR, ...]:
    """Find evidence-bound label contexts; never guess among numeric candidates."""

    observations: list[DocumentObservationIR] = []
    for metric_id, aliases in sorted(label_profiles.items()):
        for block_index, context in enumerate(document.normalized_text_blocks):
            matched = next((alias for alias in aliases if _contains_alias(context, alias)), None)
            if matched is None:
                continue
            tokens = NUMBER.findall(context)
            ambiguity = ("TEXT_SPAN_UNTRUSTED_BY_DEFAULT",)
            if len(tokens) != 1:
                ambiguity += ("NUMERIC_CARDINALITY_NOT_ONE",)
            token = tokens[0] if len(tokens) == 1 else ""
            observations.append(
                DocumentObservationIR.create(
                    source_document_sha256=document.source_document_sha256,
                    locator_type="text_span",
                    locator=f"block:{block_index}",
                    reported_label=matched,
                    raw_value_text=" | ".join(tokens),
                    parsed_numeric_value_or_null=token or None,
                    reported_unit_text_or_null="percent" if token.endswith("%") else None,
                    reported_period_text_or_null=None,
                    reported_basis_text_or_null=metric_id,
                    context_text=context[:2000],
                    numeric_role=classify_numeric_role(context=context, token=token, label=matched)
                    if token
                    else "AMBIGUOUS",
                    ambiguity_codes=ambiguity,
                    trusted_numeric=False,
                )
            )

        for table in document.normalized_tables:
            for row_index, row in enumerate(table.rows[1:], start=1):
                for label_column, label_cell in enumerate(row):
                    matched = next(
                        (alias for alias in aliases if _contains_alias(label_cell, alias)), None
                    )
                    if (
                        matched is None
                        and metric_id == "reported_ffo"
                        and is_plain_reported_ffo_total_label(label_cell)
                    ):
                        matched = "funds from operations"
                    if matched is None:
                        continue
                    for value_column, value_cell in enumerate(row):
                        if value_column == label_column:
                            continue
                        tokens = NUMBER.findall(value_cell)
                        if not tokens:
                            continue
                        numeric_value_columns = frozenset(
                            column
                            for column, cell in enumerate(row)
                            if NUMBER.findall(cell)
                        )
                        header_values: list[str] = []
                        header_row_limit = row_index
                        for possible_data_index, possible_data_row in enumerate(
                            table.rows[:row_index]
                        ):
                            later_cells = possible_data_row[1:]
                            first_cell = (
                                _semantic_cell(possible_data_row[0])
                                if possible_data_row
                                else ""
                            )
                            if (
                                possible_data_row
                                and first_cell
                                and not TEMPORAL_FRAGMENT.fullmatch(first_cell)
                                and any(
                                    NUMBER.fullmatch(_semantic_cell(cell))
                                    and not TEMPORAL_FRAGMENT.fullmatch(_semantic_cell(cell))
                                    for cell in later_cells
                                )
                            ):
                                header_row_limit = possible_data_index
                                break
                        for prior_index, _prior in enumerate(table.rows[:header_row_limit]):
                            binding = bind_temporal_header_fragment(
                                table=table,
                                header_row_index=prior_index,
                                target_value_column=value_column,
                                numeric_value_columns=numeric_value_columns,
                                label_column=label_column,
                            )
                            value = binding.value if binding else ""
                            if (
                                value
                                and TEMPORAL_FRAGMENT.fullmatch(value)
                                and value not in header_values
                            ):
                                header_values.append(value)
                        header = " ".join(header_values)
                        unambiguous = len(tokens) == 1 and bool(
                            COMPLETE_TEMPORAL_HEADER.fullmatch(header)
                        )
                        ambiguity = () if unambiguous else ("TABLE_CELL_VALUE_AMBIGUOUS",)
                        token = tokens[0] if len(tokens) == 1 else ""
                        table_context = " | ".join(
                            (
                                *table.context_blocks,
                                *(" | ".join(item) for item in table.rows[:row_index]),
                            )
                        )
                        row_context = " | ".join(row)
                        currency = (
                            "$" in row[:value_column]
                            or "$" in table_context
                            or bool(
                                re.search(r"\b(?:usd|dollars?)\b", table_context, re.IGNORECASE)
                            )
                        )
                        reported_unit = (
                            "percent"
                            if token.endswith("%")
                            else "USD"
                            if currency
                            else "shares"
                            if re.search(
                                r"\b(?:diluted|weighted-average) shares\b",
                                label_cell,
                                re.IGNORECASE,
                            )
                            else None
                        )
                        if re.search(
                            r"\battributable to common stockholders\b", label_cell, re.IGNORECASE
                        ):
                            basis = "attributable_to_common_stockholders"
                        elif re.search(r"\bcompany share\b", label_cell, re.IGNORECASE):
                            basis = "company_share"
                        elif re.fullmatch(
                            r"\s*(?:funds from operations\s*\(ffo\)|ffo|core ffo|affo)\s*",
                            label_cell,
                            re.IGNORECASE,
                        ):
                            basis = "issuer_reported_total"
                        else:
                            basis = metric_id
                        observations.append(
                            DocumentObservationIR.create(
                                source_document_sha256=document.source_document_sha256,
                                locator_type="table_cell",
                                locator=f"table:{table.table_index}:row:{row_index}:column:{value_column}",
                                row_index_or_null=row_index,
                                column_index_or_null=value_column,
                                header_path=tuple(header_values),
                                reported_label=matched,
                                raw_value_text=" | ".join(tokens),
                                parsed_numeric_value_or_null=token or None,
                                reported_unit_text_or_null=reported_unit,
                                reported_period_text_or_null=header,
                                reported_basis_text_or_null=basis,
                                context_text=f"{table_context} || ROW: {row_context}"[-4000:],
                                numeric_role="MEASURE_VALUE" if unambiguous else "AMBIGUOUS",
                                ambiguity_codes=ambiguity,
                                trusted_numeric=unambiguous,
                            )
                        )
    return tuple(sorted(observations, key=lambda item: item.observation_id))
