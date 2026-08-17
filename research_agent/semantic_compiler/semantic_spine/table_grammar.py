"""BA4 table grammar for JSON, CSV, HTML and Markdown source artifacts."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import ProvenanceRef

from .contracts import (
    ParsedPayloadIR,
    SemanticCellIR,
    SemanticTableIR,
    SourceInputIR,
    TableAxisIR,
    TableDiscoveryIR,
    TableDispositionIR,
    create_hashed,
)


class TableGrammarError(ValueError):
    """Fail-closed parse or table grammar error."""


def _safe(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "." for char in value)
    return ".".join(part for part in cleaned.split(".") if part) or "root"


def _state(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        return "missing"
    if isinstance(value, str) and value.strip().casefold() in {"—", "–", "-"}:
        return "dash"
    if isinstance(value, str) and value.strip().casefold() in {"n/a", "na", "n.m.", "not applicable"}:
        return "not_applicable"
    if value == 0 or (isinstance(value, str) and value.strip() in {"0", "0.0", "0.00"}):
        return "zero"
    return "value"


def _normalize(value: Any) -> int | float | str | bool | None:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = str(value).strip()
    if not text:
        return None
    candidate = text.replace("\u00a0", " ").replace(",", "").replace("$", "").replace("€", "")
    percent = candidate.endswith("%")
    if percent:
        candidate = candidate[:-1].strip()
    negative = candidate.startswith("(") and candidate.endswith(")")
    if negative:
        candidate = candidate[1:-1]
    try:
        number = float(candidate)
        number = -number if negative else number
        number = number / 100 if percent else number
        return int(number) if number.is_integer() and not percent else number
    except ValueError:
        return text


@dataclass(frozen=True)
class _RawCell:
    text: str
    header: bool = False
    rowspan: int = 1
    colspan: int = 1


@dataclass(frozen=True)
class _Candidate:
    locator: str
    title: str
    rows: tuple[tuple[_RawCell, ...], ...]
    merged: bool = False


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.tables: list[_Candidate] = []
        self.rows: list[list[_RawCell]] = []
        self.row: list[_RawCell] | None = None
        self.cell_tag: str | None = None
        self.cell_text: list[str] = []
        self.cell_rowspan = 1
        self.cell_colspan = 1
        self.caption: list[str] = []
        self.in_caption = False
        self.table_index = 0
        self.merged = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.rows = []
                self.caption = []
                self.merged = False
            return
        if self.depth != 1:
            return
        if tag == "caption":
            self.in_caption = True
        elif tag == "tr":
            self.row = []
        elif tag in {"th", "td"} and self.row is not None:
            self.cell_tag = tag
            self.cell_text = []
            try:
                self.cell_rowspan = max(1, int(attrs_dict.get("rowspan") or 1))
                self.cell_colspan = max(1, int(attrs_dict.get("colspan") or 1))
            except ValueError:
                self.cell_rowspan = self.cell_colspan = 1
            self.merged = self.merged or self.cell_rowspan > 1 or self.cell_colspan > 1

    def handle_data(self, data: str) -> None:
        if self.depth != 1:
            return
        if self.cell_tag:
            self.cell_text.append(data)
        elif self.in_caption:
            self.caption.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self.depth == 1:
                title = " ".join(" ".join(self.caption).split()) or f"HTML table {self.table_index + 1}"
                self.tables.append(_Candidate(
                    locator=f"html/table[{self.table_index}]",
                    title=title,
                    rows=tuple(tuple(row) for row in self.rows),
                    merged=self.merged,
                ))
                self.table_index += 1
            self.depth = max(0, self.depth - 1)
            return
        if self.depth != 1:
            return
        if tag in {"th", "td"} and self.cell_tag:
            text = " ".join("".join(self.cell_text).split())
            assert self.row is not None
            self.row.append(_RawCell(text, self.cell_tag == "th", self.cell_rowspan, self.cell_colspan))
            self.cell_tag = None
            self.cell_text = []
        elif tag == "tr" and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None
        elif tag == "caption":
            self.in_caption = False


def _expand(candidate: _Candidate) -> tuple[list[list[_RawCell | None]], bool]:
    grid: list[list[_RawCell | None]] = []
    occupied: dict[tuple[int, int], _RawCell] = {}
    for row_index, raw_row in enumerate(candidate.rows):
        row: list[_RawCell | None] = []
        column = 0
        for cell in raw_row:
            while (row_index, column) in occupied:
                while len(row) <= column:
                    row.append(None)
                row[column] = occupied[(row_index, column)]
                column += 1
            for row_offset in range(cell.rowspan):
                for column_offset in range(cell.colspan):
                    occupied[(row_index + row_offset, column + column_offset)] = cell
            for _ in range(cell.colspan):
                while len(row) <= column:
                    row.append(None)
                row[column] = cell
                column += 1
        while (row_index, column) in occupied:
            row.append(occupied[(row_index, column)])
            column += 1
        grid.append(row)
    width = max((len(row) for row in grid), default=0)
    for row in grid:
        row.extend([None] * (width - len(row)))
    return grid, candidate.merged


def _json_candidates(value: Any, pointer: str = "$") -> list[_Candidate]:
    found: list[_Candidate] = []
    if isinstance(value, list) and value:
        if all(isinstance(item, dict) for item in value):
            columns = sorted({str(key) for item in value for key in item})
            rows = [tuple(_RawCell(column, True) for column in columns)]
            rows.extend(tuple(_RawCell(str(item.get(column, ""))) for column in columns) for item in value)
            found.append(_Candidate(pointer, pointer, tuple(rows)))
            return found
        if all(isinstance(item, list) for item in value):
            found.append(_Candidate(pointer, pointer, tuple(tuple(_RawCell(str(cell)) for cell in row) for row in value)))
            return found
    if isinstance(value, dict):
        headers = value.get("headers") or value.get("columns")
        rows_value = value.get("rows") or value.get("data")
        if isinstance(headers, list) and isinstance(rows_value, list) and all(isinstance(row, list) for row in rows_value):
            rows = [tuple(_RawCell(str(cell), True) for cell in headers)]
            rows.extend(tuple(_RawCell(str(cell)) for cell in row) for row in rows_value)
            found.append(_Candidate(pointer, str(value.get("title") or pointer), tuple(rows)))
            return found
        for key in sorted(value):
            found.extend(_json_candidates(value[key], f"{pointer}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_json_candidates(item, f"{pointer}[{index}]"))
    return found


def _markdown_candidates(text: str) -> list[_Candidate]:
    lines = text.splitlines()
    found: list[_Candidate] = []
    index = 0
    while index + 1 < len(lines):
        if "|" in lines[index] and re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
            start = index
            block = [lines[index]]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                block.append(lines[index]); index += 1
            rows = []
            for row_index, line in enumerate(block):
                values = [part.strip() for part in line.strip().strip("|").split("|")]
                rows.append(tuple(_RawCell(value, row_index == 0) for value in values))
            found.append(_Candidate(f"markdown/line[{start + 1}]", f"Markdown table line {start + 1}", tuple(rows)))
            continue
        index += 1
    return found


def parse_payload(source: SourceInputIR, payload: bytes) -> tuple[ParsedPayloadIR, list[_Candidate]]:
    import hashlib

    if hashlib.sha256(payload).hexdigest() != source.payload_sha256:
        raise TableGrammarError("source_payload_hash_mismatch")
    path = source.member_path.casefold()
    media = source.media_type.casefold()
    candidates: list[_Candidate] = []
    if media.endswith("json") or path.endswith(".json"):
        try:
            parsed = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TableGrammarError("malformed_json") from exc
        kind = "json"
        candidates = _json_candidates(parsed)
    elif "csv" in media or path.endswith(".csv"):
        try:
            rows = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise TableGrammarError("malformed_csv") from exc
        parsed = rows
        kind = "csv"
        candidates = [_Candidate("csv/table[0]", source.member_path, tuple(
            tuple(_RawCell(str(cell), row_index == 0) for cell in row)
            for row_index, row in enumerate(rows)
        ))]
    elif "html" in media or path.endswith((".htm", ".html")):
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            text = payload.decode("latin-1")
        parser = _HTMLTableParser()
        parser.feed(text)
        parsed = {"text_sha256": sha256_json(text), "length": len(text)}
        kind = "html"
        candidates = parser.tables
    else:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TableGrammarError("malformed_text") from exc
        parsed = text if source.input_kind == "legacy_compatibility" else {"text_sha256": sha256_json(text), "length": len(text)}
        kind = "markdown" if "markdown" in media or path.endswith(".md") else "text"
        candidates = _markdown_candidates(text) if kind == "markdown" else []
    document = create_hashed(
        ParsedPayloadIR,
        parsed_payload_id=f"parsed.{_safe(source.source_input_id)}",
        source_input_sha256=source.ir_sha256,
        parser_id=f"room16.semantic_table_grammar.{kind}@2",
        payload_kind=kind,
        payload=parsed,
        compatibility_adapter_id=source.compatibility_adapter_id,
    )
    return document, candidates


def _table_kind(title: str, grid: list[list[_RawCell | None]]) -> str:
    text = " ".join([title, *[cell.text for row in grid[:4] for cell in row if cell]]).casefold()
    if any(word in text for word in ("balance sheet", "income statement", "cash flow", "statement of")):
        return "financial_statement"
    if "guidance" in text or "outlook" in text:
        return "guidance"
    if any(word in text for word in ("valuation", "multiple", "discount rate", "terminal value")):
        return "valuation"
    if any(word in text for word in ("member", "volume", "renewal", "subscriber", "kpi")):
        return "operating_kpi"
    if any(word in text for word in ("source", "url", "accession")):
        return "source_register"
    return "generic"


def _orientation(grid: list[list[_RawCell | None]]) -> str:
    if len(grid) < 2 or len(grid[0]) < 2:
        return "row_major"
    first_row = [cell.text.casefold() if cell else "" for cell in grid[0]]
    first_col = [row[0].text.casefold() if row and row[0] else "" for row in grid[1:]]
    period = re.compile(r"(?:19|20)\d{2}|q[1-4]|fy\d{2,4}")
    metric_words = re.compile(r"revenue|income|margin|cash|shares|rate|volume|member")
    if sum(bool(metric_words.search(value)) for value in first_row[1:]) >= 2 and sum(bool(period.search(value)) for value in first_col) >= 1:
        return "transposed"
    return "row_major"


def discover_tables(source: SourceInputIR, candidates: list[_Candidate]) -> TableDiscoveryIR:
    tables: list[SemanticTableIR] = []
    dispositions: list[TableDispositionIR] = []
    for index, candidate in enumerate(candidates):
        detected_id = f"detected.{_safe(source.source_input_id)}.{index:06d}"
        grid, merged = _expand(candidate)
        height = len(grid)
        width = max((len(row) for row in grid), default=0)
        if height < 2 or width < 2:
            dispositions.append(TableDispositionIR(
                detected_table_id=detected_id,
                source_input_sha256=source.ir_sha256,
                locator=candidate.locator,
                disposition="excluded",
                exclusion_code="TABLE_TOO_SMALL",
            ))
            continue
        header_depth = 0
        for row in grid:
            populated = [cell for cell in row if cell is not None]
            if populated and all(cell.header for cell in populated):
                header_depth += 1
            else:
                break
        header_depth = max(1, header_depth)
        row_header_depth = 1 if any(row and row[0] and (row[0].header or isinstance(_normalize(row[0].text), str)) for row in grid[header_depth:]) else 0
        column_labels = []
        for column in range(width):
            label_parts = [grid[row][column].text for row in range(min(header_depth, height)) if grid[row][column] and grid[row][column].text]
            column_labels.append(" / ".join(dict.fromkeys(label_parts)) or f"column_{column}")
        cells: list[SemanticCellIR] = []
        missing = 0
        for row_index, row in enumerate(grid):
            row_label = row[0].text if row and row[0] and row[0].text else f"row_{row_index}"
            for column_index in range(width):
                raw_cell = row[column_index] if column_index < len(row) else None
                raw = raw_cell.text if raw_cell else None
                state = _state(raw)
                missing += state == "missing"
                cell_id = f"{detected_id}.cell.{row_index:05d}.{column_index:05d}"
                locator_text = f"{candidate.locator}/row[{row_index}]/cell[{column_index}]"
                cells.append(SemanticCellIR(
                    cell_id=cell_id,
                    row_index=row_index,
                    column_index=column_index,
                    row_key=row_label,
                    column_key=column_labels[column_index],
                    value_state=state,
                    raw_value=raw,
                    normalized_value=_normalize(raw),
                    locator=ProvenanceRef(
                        source_id=source.source_input_id,
                        artifact_path=source.member_path,
                        sha256=source.payload_sha256,
                        locator=locator_text,
                    ),
                ))
        flat_labels = tuple(column_labels)
        period_indices = tuple(i for i, label in enumerate(flat_labels) if re.search(r"(?:19|20)\d{2}|q[1-4]|fy\d{2,4}", label, re.I))
        unit_indices = tuple(i for i, label in enumerate(flat_labels) if re.search(r"usd|eur|%|share|unit", label, re.I))
        scale_indices = tuple(i for i, label in enumerate(flat_labels) if re.search(r"thousand|million|billion|000", label, re.I))
        axes = [
            TableAxisIR(axis_id=f"{detected_id}.axis.row", axis_kind="row", labels=tuple(cell.row_key for cell in cells[::width]), source_indices=tuple(range(height))),
            TableAxisIR(axis_id=f"{detected_id}.axis.column", axis_kind="column", labels=flat_labels, source_indices=tuple(range(width))),
        ]
        if period_indices:
            axes.append(TableAxisIR(axis_id=f"{detected_id}.axis.period", axis_kind="period", labels=tuple(flat_labels[i] for i in period_indices), source_indices=period_indices))
        if unit_indices:
            axes.append(TableAxisIR(axis_id=f"{detected_id}.axis.unit", axis_kind="unit", labels=tuple(flat_labels[i] for i in unit_indices), source_indices=unit_indices))
        if scale_indices:
            axes.append(TableAxisIR(axis_id=f"{detected_id}.axis.scale", axis_kind="scale", labels=tuple(flat_labels[i] for i in scale_indices), source_indices=scale_indices))
        table = create_hashed(
            SemanticTableIR,
            table_id=detected_id.replace("detected.", "table.", 1),
            source_input_sha256=source.ir_sha256,
            table_kind=_table_kind(candidate.title, grid),
            title=candidate.title,
            orientation=_orientation(grid),
            header_depth=header_depth,
            row_header_depth=row_header_depth,
            sparse=missing > 0,
            merged_cells_expanded=merged,
            axes=tuple(axes),
            cells=tuple(cells),
        )
        tables.append(table)
        dispositions.append(TableDispositionIR(
            detected_table_id=detected_id,
            source_input_sha256=source.ir_sha256,
            locator=candidate.locator,
            disposition="registered",
            registered_table_sha256=table.ir_sha256,
        ))
    return create_hashed(
        TableDiscoveryIR,
        source_input_sha256=source.ir_sha256,
        tables=tuple(tables),
        dispositions=tuple(dispositions),
        detected_count=len(dispositions),
        registered_count=len(tables),
        excluded_count=sum(item.disposition == "excluded" for item in dispositions),
    )
