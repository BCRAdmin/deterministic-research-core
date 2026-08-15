"""BA4 deterministic source parsers and table discovery."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json

from .contracts import (
    CanonicalCellIR,
    CanonicalTableIR,
    ParsedDocumentIR,
    ParsedRecordIR,
    SourceLocatorIR,
    create_hashed,
)


class ParserError(ValueError):
    """Fail-closed parser error."""


def _safe(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "." for char in value)
    return ".".join(part for part in cleaned.split(".") if part) or "root"


def _records(value: Any, pointer: str = "$") -> list[ParsedRecordIR]:
    kind = "object" if isinstance(value, dict) else "array" if isinstance(value, list) else "scalar"
    payload = (
        {"keys": sorted(map(str, value))}
        if isinstance(value, dict)
        else {"length": len(value)}
        if isinstance(value, list)
        else value
    )
    records = [ParsedRecordIR(record_id=f"record.{_safe(pointer)}", record_kind=kind, pointer=pointer, payload=payload)]
    if isinstance(value, dict):
        for key in sorted(value):
            records.extend(_records(value[key], f"{pointer}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            records.extend(_records(item, f"{pointer}[{index}]"))
    return records


def _value_state(value: Any) -> str:
    if value is None:
        return "missing"
    if isinstance(value, str) and value.strip().lower() in {"—", "-", "–"}:
        return "dash"
    if isinstance(value, str) and value.strip().lower() in {"n/a", "na", "not applicable"}:
        return "not_applicable"
    if value == 0:
        return "zero"
    return "value"


def _table_from_rows(
    *,
    table_id: str,
    title: str,
    rows: list[dict[str, Any]],
    snapshot_id: str,
    source_sha256: str,
    artifact_path: str,
    pointer: str,
) -> CanonicalTableIR:
    columns = tuple(sorted({str(key) for row in rows for key in row}))
    row_keys = tuple(f"row.{index:06d}" for index in range(len(rows)))
    cells: list[CanonicalCellIR] = []
    for index, row in enumerate(rows):
        row_key = row_keys[index]
        for column in columns:
            value = row.get(column)
            cell_id = f"{table_id}.cell.{index:06d}.{_safe(column)}"
            cells.append(CanonicalCellIR(
                cell_id=cell_id,
                row_key=row_key,
                column_key=column,
                value_state=_value_state(value),
                raw_value=value,
                normalized_value=value if isinstance(value, (int, float, str, bool)) else None,
                locator=SourceLocatorIR(
                    snapshot_id=snapshot_id,
                    source_sha256=source_sha256,
                    artifact_path=artifact_path,
                    pointer=f"{pointer}[{index}].{column}",
                    table_id=table_id,
                    cell_id=cell_id,
                ),
            ))
    return create_hashed(
        CanonicalTableIR,
        table_id=table_id,
        table_definition_id="source_register",
        title=title,
        row_keys=row_keys,
        column_keys=columns,
        cells=tuple(cells),
    )


def _discover_json_tables(
    value: Any,
    *,
    snapshot_id: str,
    source_sha256: str,
    artifact_path: str,
    pointer: str = "$",
) -> list[CanonicalTableIR]:
    tables: list[CanonicalTableIR] = []
    if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
        table_id = f"table.{_safe(snapshot_id)}.{hashlib.sha256(pointer.encode()).hexdigest()[:12]}"
        tables.append(_table_from_rows(
            table_id=table_id,
            title=pointer,
            rows=value,
            snapshot_id=snapshot_id,
            source_sha256=source_sha256,
            artifact_path=artifact_path,
            pointer=pointer,
        ))
        return tables
    if isinstance(value, dict):
        for key in sorted(value):
            tables.extend(_discover_json_tables(
                value[key], snapshot_id=snapshot_id, source_sha256=source_sha256,
                artifact_path=artifact_path, pointer=f"{pointer}.{key}",
            ))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            tables.extend(_discover_json_tables(
                item, snapshot_id=snapshot_id, source_sha256=source_sha256,
                artifact_path=artifact_path, pointer=f"{pointer}[{index}]",
            ))
    return tables


def parse_artifact(
    *,
    source_snapshot_sha256: str,
    snapshot_id: str,
    artifact_path: str,
    source_sha256: str,
    media_type: str,
    payload: bytes,
) -> tuple[ParsedDocumentIR, tuple[CanonicalTableIR, ...]]:
    if hashlib.sha256(payload).hexdigest() != source_sha256:
        raise ParserError("source_payload_hash_mismatch")
    parser_id: str
    records: list[ParsedRecordIR]
    tables: list[CanonicalTableIR]
    if media_type.endswith("json") or artifact_path.endswith(".json"):
        parser_id = "parser.json.v1"
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ParserError("malformed_json") from exc
        records = _records(value)
        tables = _discover_json_tables(
            value,
            snapshot_id=snapshot_id,
            source_sha256=source_sha256,
            artifact_path=artifact_path,
        )
    elif media_type in {"text/csv", "application/csv"} or artifact_path.endswith(".csv"):
        parser_id = "parser.csv.v1"
        try:
            rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8"))))
        except UnicodeDecodeError as exc:
            raise ParserError("malformed_csv_encoding") from exc
        if not rows:
            raise ParserError("empty_csv")
        records = [
            ParsedRecordIR(
                record_id=f"record.csv.{index:06d}",
                record_kind="csv_row",
                pointer=f"$[{index}]",
                payload=row,
            )
            for index, row in enumerate(rows)
        ]
        tables = [_table_from_rows(
            table_id=f"table.{_safe(snapshot_id)}.csv",
            title=artifact_path,
            rows=rows,
            snapshot_id=snapshot_id,
            source_sha256=source_sha256,
            artifact_path=artifact_path,
            pointer="$",
        )]
    else:
        parser_id = "parser.text.v1"
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParserError("malformed_text_encoding") from exc
        records = [ParsedRecordIR(record_id="record.text", record_kind="text", pointer="$", payload=text)]
        tables = []
    document = create_hashed(
        ParsedDocumentIR,
        source_snapshot_sha256=source_snapshot_sha256,
        document_id=f"document.{_safe(snapshot_id)}",
        snapshot_id=snapshot_id,
        source_sha256=source_sha256,
        media_type=media_type,
        parser_id=parser_id,
        records=tuple(records),
    )
    return document, tuple(sorted(tables, key=lambda item: item.table_id))


def bridge_legacy_table_facts(
    facts: list[dict[str, Any]],
    *,
    snapshot_id: str,
    source_sha256: str,
    artifact_path: str,
) -> tuple[CanonicalTableIR, ...]:
    """Materialize already accepted table-cell lineage for shadow parity."""

    grouped: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        if fact.get("table_id") and fact.get("cell_id"):
            grouped.setdefault(str(fact["table_id"]), []).append(fact)
    tables: list[CanonicalTableIR] = []
    for table_id, rows in sorted(grouped.items()):
        cells = []
        row_keys = []
        column_keys = []
        for index, fact in enumerate(sorted(rows, key=lambda item: str(item["cell_id"]))):
            row_key = str(fact.get("row_metric") or f"row.{index:06d}")
            column_key = str(fact.get("column_metric") or fact["metric"])
            row_keys.append(row_key)
            column_keys.append(column_key)
            cells.append(CanonicalCellIR(
                cell_id=str(fact["cell_id"]),
                row_key=row_key,
                column_key=column_key,
                value_state="zero" if fact.get("is_zero") else "value",
                raw_value=fact.get("source_value"),
                normalized_value=fact.get("value"),
                locator=SourceLocatorIR(
                    snapshot_id=snapshot_id,
                    source_sha256=source_sha256,
                    artifact_path=artifact_path,
                    pointer=str(fact.get("source_locator") or fact["cell_id"]),
                    table_id=table_id,
                    cell_id=str(fact["cell_id"]),
                ),
            ))
        kind = "operating_kpi" if any(str(item["metric"]).startswith("operating_kpi_") for item in rows) else "financial_statement"
        tables.append(create_hashed(
            CanonicalTableIR,
            table_id=table_id,
            table_definition_id=kind,
            title=table_id,
            row_keys=tuple(sorted(set(row_keys))),
            column_keys=tuple(sorted(set(column_keys))),
            cells=tuple(cells),
        ))
    return tuple(tables)
