"""Conservative REIT primary-text parser for absolute reported FFO measures.

This additive REIT-v4 module is intentionally separate from the historical
REIT-v3 implementation.  It is designed for deterministic replay over captured
SEC HTML and closes the concrete R15 false-positive classes:

* positive FFO measure grammar instead of substring matching;
* hard rejection of per-share, ratio, guidance, adjustment and component rows;
* table/section-local scale authority;
* explicit value-cell -> column-header -> period binding;
* local reconciliation authority for unqualified FFO;
* complete candidate self-hash and semantic-authority validation.
"""

from __future__ import annotations

import calendar
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from lxml import html
from lxml.html import HtmlElement

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

PARSER_CONTRACT: dict[str, Any] = {
    "contract_id": "room16.reit.v4.primary_text_parser@1",
    "profile_family": "REIT",
    "profile_version": 4,
    "metric": "reit_operating_performance_measure",
    "absolute_unit": "USD",
    "positive_measure_grammar": True,
    "per_share_excluded": True,
    "component_and_adjustment_rows_excluded": True,
    "table_local_scale_required": True,
    "column_period_binding_required": True,
    "local_reconciliation_required_for_unqualified_ffo": True,
    "synthetic_ffo_prohibited": True,
    "ticker_specific_rules": False,
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


PARSER_CONTRACT_SHA256 = canonical_sha256(PARSER_CONTRACT)


def _clean_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("\xa0", " ").replace("\u200b", " ").replace("\ufeff", " ")
    return re.sub(r"\s+", " ", value).strip()


def _norm_label(value: str) -> str:
    value = _clean_text(value).lower().replace("&", " and ")
    value = re.sub(r"[–—−]", "-", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" .:;-\t")


def _parse_number(value: str) -> Decimal | None:
    text = _clean_text(value)
    if not text or text.lower() in {"-", "—", "–", "−", "nm", "n/m", "n.a.", "na"}:
        return None
    text = text.replace("$", "").replace("€", "").replace(",", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    text = re.sub(r"\s*\([a-z0-9]+\)\s*$", "", text, flags=re.I)
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return -result if negative else result


@dataclass(frozen=True)
class CellRef:
    node: HtmlElement
    row_index: int
    cell_index: int
    start_col: int
    end_col: int
    text: str


@dataclass(frozen=True)
class TableGrid:
    table: HtmlElement
    table_index: int
    rows: tuple[tuple[CellRef, ...], ...]


def _build_table_grid(table: HtmlElement, table_index: int) -> TableGrid:
    row_nodes = table.xpath("./thead/tr|./tbody/tr|./tfoot/tr|./tr")
    if not row_nodes:
        row_nodes = table.xpath(".//tr")
    rows: list[tuple[CellRef, ...]] = []
    occupied_until: dict[int, int] = {}
    for row_index, row in enumerate(row_nodes):
        refs: list[CellRef] = []
        col = 0
        for cell_index, cell in enumerate(row.xpath("./th|./td")):
            while occupied_until.get(col, -1) >= row_index:
                col += 1
            try:
                colspan = max(1, int(cell.get("colspan", "1")))
            except ValueError:
                colspan = 1
            try:
                rowspan = max(1, int(cell.get("rowspan", "1")))
            except ValueError:
                rowspan = 1
            ref = CellRef(
                node=cell,
                row_index=row_index,
                cell_index=cell_index,
                start_col=col,
                end_col=col + colspan - 1,
                text=_clean_text(" ".join(cell.itertext())),
            )
            refs.append(ref)
            if rowspan > 1:
                for occupied_col in range(ref.start_col, ref.end_col + 1):
                    occupied_until[occupied_col] = row_index + rowspan - 1
            col += colspan
        rows.append(tuple(refs))
    return TableGrid(table=table, table_index=table_index, rows=tuple(rows))


def _overlaps(left: CellRef, right: CellRef) -> bool:
    return left.start_col <= right.end_col and right.start_col <= left.end_col


_PER_SHARE_RE = re.compile(
    r"(?:\bper\b.{0,48}\b(?:share|shares|unit|units)\b|"
    r"\b(?:share|shares|unit|units)\b.{0,32}\b(?:diluted|basic)\b|"
    r"\bffo\s*/\s*(?:share|unit)\b)",
    re.I,
)
_ADJUSTED_FAMILY_RE = re.compile(
    r"\b(?:affo|adjusted\s+(?:funds\s+from\s+operations|ffo)|"
    r"core\s+(?:funds\s+from\s+operations|ffo)|"
    r"normalized\s+(?:funds\s+from\s+operations|ffo))\b",
    re.I,
)
_COMPONENT_RE = re.compile(
    r"(?:"
    r"\badjustments?\b|\bnot\s+included\s+in\s+ffo\b|"
    r"\bincluded\s+in\s+ffo\b|\bexcluded\s+from\s+ffo\b|"
    r"\bffo\s+adjustments?\b|\bfrom\s+(?:co[- ]?investments?|partially\s+owned)\b|"
    r"\bproportionate\s+share\b|\bweighted\s+average\b|"
    r"\bcoverage\b|\bmargin\b|\bpayout\b|\bguidance\b|"
    r"\brange\b|\bmidpoint\b|\bannuali[sz]ed\b|\bcalculation\b|"
    r"(?:%|\bpercent\b)\s*change|\bchange\s*(?:%|percent)\b|"
    r"\bgains?\b|\bloss(?:es)?\b|\bdepreciation\b|\bamortization\b|"
    r"\band\s+adjusted\s+(?:funds\s+from\s+operations|ffo)\b"
    r")",
    re.I,
)
_POSITIVE_FFO_RE = re.compile(
    r"^(?:total\s+)?(?:nareit\s+)?(?:ffo|funds\s+from\s+operations)"
    r"(?:\s*,?\s*(?:\(|,)?\s*as\s+defined\s+by\s+nareit\s*\)?)?"
    r"(?:\s+(?:attributable|available)\s+to\s+"
    r"(?:common\s+)?(?:stockholders?|shareholders?|unitholders?|unit\s+holders?|"
    r"controlling\s+interest|common\s+stock\s+and\s+(?:common\s+)?units?)"
    r"(?:\s+and\s+(?:stockholders?|shareholders?|unitholders?|unit\s+holders?|"
    r"(?:common\s+)?units?))?"
    r")?"
    r"(?:\s*\(\d+\))?$",
    re.I,
)


def classify_ffo_label(label: str) -> dict[str, Any]:
    """Classify a row label with stable fail-closed reason codes."""
    normalized = _norm_label(label)
    if _COMPONENT_RE.search(normalized):
        return {
            "status": "REJECT",
            "reason": "FFO_COMPONENT_OR_NON_MEASURE",
            "normalized": normalized,
        }
    if _ADJUSTED_FAMILY_RE.search(normalized):
        if _PER_SHARE_RE.search(normalized):
            return {
                "status": "REJECT",
                "reason": "PER_SHARE_NOT_ABSOLUTE_FFO",
                "normalized": normalized,
            }
        return {
            "status": "VISIBLE_NON_CORE",
            "reason": "ADJUSTED_FFO_FAMILY_GRADE_C",
            "metric_id": "reported_adjusted_ffo",
            "grade": "C",
            "normalized": normalized,
        }
    if not re.search(r"\bffo\b|\bfunds\s+from\s+operations\b", normalized):
        return {"status": "REJECT", "reason": "NOT_FFO_FAMILY", "normalized": normalized}
    if _PER_SHARE_RE.search(normalized):
        return {
            "status": "REJECT",
            "reason": "PER_SHARE_NOT_ABSOLUTE_FFO",
            "normalized": normalized,
        }
    if not _POSITIVE_FFO_RE.fullmatch(normalized):
        return {
            "status": "REJECT",
            "reason": "FFO_LABEL_OUTSIDE_POSITIVE_GRAMMAR",
            "normalized": normalized,
        }
    return {
        "status": "POTENTIAL_CORE",
        "reason": None,
        "metric_id": "reported_ffo",
        "explicit_nareit": bool(
            re.search(r"\bnareit\b|as\s+defined\s+by\s+nareit", normalized)
        ),
        "attributable": bool(re.search(r"\b(?:attributable|available)\s+to\b", normalized)),
        "normalized": normalized,
    }


_SCALE_RE = re.compile(
    r"(?P<whole>\$?\s*(?:amounts?\s+)?(?:are\s+)?(?:stated\s+)?"
    r"(?:dollars?\s+)?(?:in\s+)?(?P<scale>thousands?|millions?|billions?)"
    r"(?:\s+of\s+dollars)?(?:\s*,?\s*except\s+(?:share|per\s+share)\s+(?:amounts|data))?)",
    re.I,
)
_ACTUAL_DOLLARS_RE = re.compile(
    r"(?P<whole>(?:amounts?\s+)?(?:are\s+)?(?:stated\s+)?(?:in\s+)?dollars?"
    r"(?:\s*,?\s*except\s+(?:share|per\s+share)\s+(?:amounts|data))?)",
    re.I,
)


def _scale_declaration(text: str) -> tuple[str, str] | None:
    match = _SCALE_RE.search(text)
    if match:
        return _clean_text(match.group("whole")), match.group("scale").lower()
    match = _ACTUAL_DOLLARS_RE.search(text)
    if match:
        return _clean_text(match.group("whole")), "dollars"
    return None


def _scale_multiplier(token: str) -> Decimal:
    token = token.lower()
    if token.startswith("dollar"):
        return Decimal(1)
    if token.startswith("thousand"):
        return Decimal(1000)
    if token.startswith("million"):
        return Decimal(1_000_000)
    if token.startswith("billion"):
        return Decimal(1_000_000_000)
    raise ValueError(f"UNKNOWN_SCALE:{token}")


def _element_locator(node: HtmlElement) -> str:
    try:
        return node.getroottree().getpath(node)
    except Exception:
        return "UNAVAILABLE"


def _local_scale_authority(grid: TableGrid, target_row: int) -> dict[str, Any] | None:
    candidates: list[tuple[int, str, str, str]] = []
    for row_index in range(0, min(target_row + 1, len(grid.rows))):
        row_text = _clean_text(" ".join(ref.text for ref in grid.rows[row_index]))
        declaration = _scale_declaration(row_text)
        if declaration:
            authority_text, scale_token = declaration
            candidates.append(
                (
                    30_000 + row_index,
                    f"table:{grid.table_index}/row:{row_index}",
                    authority_text,
                    scale_token,
                )
            )
    caption = grid.table.find("caption")
    if caption is not None:
        declaration = _scale_declaration(_clean_text(" ".join(caption.itertext())))
        if declaration:
            authority_text, scale_token = declaration
            candidates.append((25_000, _element_locator(caption), authority_text, scale_token))
    preceding = grid.table.xpath(
        "preceding::*[self::p or self::div or self::span or self::h1 or self::h2 or self::h3 or self::h4][normalize-space()]"
    )
    for offset, node in enumerate(preceding[-12:]):
        text = _clean_text(" ".join(node.itertext()))
        if not text or len(text) > 1000:
            continue
        declaration = _scale_declaration(text)
        if declaration:
            authority_text, scale_token = declaration
            candidates.append(
                (10_000 + offset, _element_locator(node), authority_text, scale_token)
            )
    if not candidates:
        return None
    _, locator, authority_text, scale_token = max(candidates, key=lambda item: item[0])
    return {
        "multiplier": _scale_multiplier(scale_token),
        "scale": scale_token.upper(),
        "authority_text": authority_text,
        "authority_locator": locator,
        "authority_sha256": canonical_sha256(
            {"locator": locator, "text": authority_text, "scale": scale_token}
        ),
    }


_MONTHS = {
    name.lower(): number
    for number in range(1, 13)
    for name in (calendar.month_name[number], calendar.month_abbr[number])
}
_MONTH_PATTERN = "|".join(
    sorted((re.escape(name) for name in _MONTHS), key=len, reverse=True)
)
_DATE_RE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})\.?\s+(?P<day>\d{{1,2}})(?:,)?\s+(?P<year>20\d{{2}})\b",
    re.I,
)
_MONTH_DAY_RE = re.compile(
    rf"\b(?P<month>{_MONTH_PATTERN})\.?\s+(?P<day>\d{{1,2}})(?:,)?\b",
    re.I,
)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_QUARTER_YEAR_RE = re.compile(
    r"\b(?:q(?P<q1>[1-4])|(?P<qname>first|second|third|fourth)\s+quarter)\s+(?P<year>20\d{2})\b",
    re.I,
)
_DURATION_PATTERNS = (
    (
        re.compile(r"\b(?:for\s+the\s+)?three\s+months?\s+ended\b|\bquarter\s+ended\b", re.I),
        "STANDALONE_QUARTER",
        3,
    ),
    (re.compile(r"\b(?:for\s+the\s+)?six\s+months?\s+ended\b", re.I), "YEAR_TO_DATE", 6),
    (re.compile(r"\b(?:for\s+the\s+)?nine\s+months?\s+ended\b", re.I), "YEAR_TO_DATE", 9),
    (
        re.compile(r"\b(?:for\s+the\s+)?(?:twelve\s+months?|year)\s+ended\b", re.I),
        "ANNUAL",
        12,
    ),
)


def _header_cells_for_value(grid: TableGrid, value_ref: CellRef) -> list[CellRef]:
    results: list[CellRef] = []
    for row in grid.rows[: value_ref.row_index]:
        for ref in row:
            if not _overlaps(ref, value_ref) or not ref.text:
                continue
            if (
                _DATE_RE.search(ref.text)
                or _MONTH_DAY_RE.search(ref.text)
                or _YEAR_RE.fullmatch(ref.text.strip())
                or _QUARTER_YEAR_RE.search(ref.text)
                or any(pattern.search(ref.text) for pattern, _, _ in _DURATION_PATTERNS)
            ):
                results.append(ref)
    return results


def _quarter_end(year: int, quarter: int) -> date:
    month = quarter * 3
    return date(year, month, calendar.monthrange(year, month)[1])


def _period_binding(grid: TableGrid, value_ref: CellRef) -> dict[str, Any] | None:
    refs = _header_cells_for_value(grid, value_ref)
    if not refs:
        return None
    texts = [ref.text for ref in refs]
    combined = " | ".join(texts)
    full_date: date | None = None
    date_source: CellRef | None = None
    for ref in refs:
        matches = list(_DATE_RE.finditer(ref.text))
        if matches:
            match = matches[-1]
            month = _MONTHS[match.group("month").lower().rstrip(".")]
            full_date = date(int(match.group("year")), month, int(match.group("day")))
            date_source = ref
    if full_date is None:
        month_day: tuple[int, int, CellRef] | None = None
        year: tuple[int, CellRef] | None = None
        for ref in refs:
            md_matches = list(_MONTH_DAY_RE.finditer(ref.text))
            if md_matches:
                match = md_matches[-1]
                month_day = (
                    _MONTHS[match.group("month").lower().rstrip(".")],
                    int(match.group("day")),
                    ref,
                )
            if _YEAR_RE.fullmatch(ref.text.strip()):
                year = (int(ref.text.strip()), ref)
        if month_day and year:
            full_date = date(year[0], month_day[0], month_day[1])
            date_source = year[1]
    quarter_match = _QUARTER_YEAR_RE.search(combined)
    if full_date is None and quarter_match:
        quarter = (
            int(quarter_match.group("q1"))
            if quarter_match.group("q1")
            else {"first": 1, "second": 2, "third": 3, "fourth": 4}[
                quarter_match.group("qname").lower()
            ]
        )
        full_date = _quarter_end(int(quarter_match.group("year")), quarter)
    if full_date is None:
        return None
    basis = "UNKNOWN_DURATION"
    duration_months: int | None = None
    for ref in reversed(refs):
        for pattern, candidate_basis, months in _DURATION_PATTERNS:
            if pattern.search(ref.text):
                basis = candidate_basis
                duration_months = months
                break
        if duration_months is not None:
            break
    if duration_months is None and quarter_match:
        basis = "STANDALONE_QUARTER"
        duration_months = 3
    locators = [
        f"table:{grid.table_index}/row:{ref.row_index}/cell:{ref.cell_index}" for ref in refs
    ]
    return {
        "period_start": None,
        "period_end": full_date.isoformat(),
        "period_basis": basis,
        "duration_months": duration_months,
        "header_text": combined,
        "header_texts": texts,
        "header_locators": locators,
        "header_sha256": canonical_sha256(
            {
                "texts": texts,
                "locators": locators,
                "period_end": full_date.isoformat(),
                "basis": basis,
            }
        ),
        "date_source_locator": (
            f"table:{grid.table_index}/row:{date_source.row_index}/cell:{date_source.cell_index}"
            if date_source
            else None
        ),
    }


def _first_meaningful_cell(row: Sequence[CellRef]) -> CellRef | None:
    for ref in row:
        text = _clean_text(ref.text)
        if not text or text in {"$", "%", ")", "("}:
            continue
        if _parse_number(text) is not None:
            continue
        return ref
    return None


def _per_share_section_context(grid: TableGrid, target_row: int) -> dict[str, Any] | None:
    start = max(0, target_row - 6)
    for row_index in range(target_row - 1, start - 1, -1):
        row_text = _norm_label(" ".join(ref.text for ref in grid.rows[row_index]))
        if not row_text:
            continue
        if re.search(r"\bper\b.{0,40}\b(?:share|shares|unit|units)\b", row_text):
            locator = f"table:{grid.table_index}/row:{row_index}"
            proof = {"locator": locator, "text": row_text}
            return {**proof, "authority_sha256": canonical_sha256(proof)}
        if re.search(
            r"\b(?:reconciliation|dollars?\s+in\s+(?:thousands|millions)|net income)\b",
            row_text,
        ):
            break
    return None


def _table_reconciliation_authority(grid: TableGrid) -> dict[str, Any] | None:
    labels = [
        _norm_label(ref.text)
        for row in grid.rows
        if (ref := _first_meaningful_cell(row)) is not None
    ]
    text = " | ".join(labels)
    has_net_income = bool(
        re.search(r"\b(?:net\s+(?:\([^)]*\)\s*)?(?:income|loss)|profit\s+loss)\b", text)
    )
    has_depreciation = bool(
        re.search(r"\bdepreciation(?:\s+and\s+amortization)?\b", text)
    )
    has_ffo_measure = any(
        classify_ffo_label(label).get("status") == "POTENTIAL_CORE" for label in labels
    )
    if not (has_net_income and has_depreciation and has_ffo_measure):
        return None
    proof = {
        "locator": f"table:{grid.table_index}",
        "has_net_income_or_loss": has_net_income,
        "has_depreciation": has_depreciation,
        "has_positive_ffo_measure": has_ffo_measure,
        "label_set_sha256": canonical_sha256(labels),
    }
    return {**proof, "authority_sha256": canonical_sha256(proof)}


def _numeric_cells_after_label(
    row: Sequence[CellRef], label_ref: CellRef
) -> list[tuple[CellRef, Decimal]]:
    results: list[tuple[CellRef, Decimal]] = []
    for index, ref in enumerate(row):
        if ref.start_col <= label_ref.end_col:
            continue
        value = _parse_number(ref.text)
        if value is None and ref.text.startswith("(") and not ref.text.endswith(")"):
            if index + 1 < len(row) and row[index + 1].text == ")":
                value = _parse_number(ref.text + ")")
        if value is None:
            continue
        neighbor_text = " ".join(
            item.text for item in row[max(0, index - 1) : min(len(row), index + 2)]
        )
        if "%" in neighbor_text or re.search(r"\b(?:percent|pts?)\b", neighbor_text, re.I):
            continue
        results.append((ref, value))
    return results


def _candidate_body(
    *,
    ticker: str,
    cik: str,
    filing: Mapping[str, Any],
    grid: TableGrid,
    label_ref: CellRef,
    value_ref: CellRef,
    label_class: Mapping[str, Any],
    value: Decimal,
    scale: Mapping[str, Any],
    period: Mapping[str, Any],
    reconciliation: Mapping[str, Any] | None,
    source_artifact_sha256: str,
    source_snapshot_sha256: str,
) -> dict[str, Any]:
    explicit_nareit = bool(label_class.get("explicit_nareit"))
    grade = (
        "C"
        if label_class["status"] == "VISIBLE_NON_CORE"
        else ("A" if explicit_nareit or reconciliation is not None else "B")
    )
    multiplier = Decimal(str(scale["multiplier"]))
    body: dict[str, Any] = {
        "contract_id": "room16.reit.v4.primary_text_candidate@1",
        "contract_version": 1,
        "candidate_id": "PENDING",
        "ticker": ticker,
        "cik": cik,
        "metric_id": str(label_class.get("metric_id") or "reported_ffo"),
        "reported_label": label_ref.text,
        "normalized_label": label_class["normalized"],
        "normalized_semantic_family": "FFO_FAMILY",
        "raw_numeric_text": value_ref.text,
        "reported_numeric_value": format(value, "f"),
        "numeric_value": format(value * multiplier, "f"),
        "unit": "USD",
        "scale": scale["scale"],
        "scale_multiplier": format(multiplier, "f"),
        "scale_authority_text": scale["authority_text"],
        "scale_authority_locator": scale["authority_locator"],
        "scale_authority_sha256": scale["authority_sha256"],
        "period_start": period["period_start"],
        "period_end": period["period_end"],
        "period_basis": period["period_basis"],
        "duration_months": period["duration_months"],
        "column_header_text": period["header_text"],
        "column_header_texts": period["header_texts"],
        "column_header_locators": period["header_locators"],
        "column_header_sha256": period["header_sha256"],
        "filing_date": filing.get("filing_date"),
        "accession": filing.get("accession"),
        "form": filing.get("form"),
        "document_identity": filing.get("document_name"),
        "document_role": filing.get("document_role"),
        "source_lineage": {
            "source_artifact_sha256": source_artifact_sha256,
            "source_snapshot_sha256": source_snapshot_sha256,
        },
        "table_locator": f"table:{grid.table_index}",
        "row_locator": f"table:{grid.table_index}/row:{label_ref.row_index}",
        "label_cell_locator": (
            f"table:{grid.table_index}/row:{label_ref.row_index}/cell:{label_ref.cell_index}"
        ),
        "value_cell_locator": (
            f"table:{grid.table_index}/row:{value_ref.row_index}/cell:{value_ref.cell_index}"
        ),
        "value_grid_columns": [value_ref.start_col, value_ref.end_col],
        "reconciliation_authority": reconciliation,
        "economic_scope_grade": grade,
        "context_scope_grade": (
            "CONSOLIDATED_ATTRIBUTABLE"
            if re.search(r"\b(?:attributable|available)\s+to\b", label_class["normalized"])
            else "CONSOLIDATED_REPORTED"
        ),
        "parser_contract_sha256": PARSER_CONTRACT_SHA256,
        "synthetic": False,
        "ticker_specific_rule": False,
    }
    identity_payload = {key: val for key, val in body.items() if key != "candidate_id"}
    identity_sha = canonical_sha256(identity_payload)
    body["candidate_identity_payload_sha256"] = identity_sha
    body["candidate_id"] = f"room16.reit.v4.primary.{identity_sha}"
    body["candidate_sha256"] = canonical_sha256(body)
    return body


def validate_primary_text_candidate_v4(candidate: Mapping[str, Any]) -> str:
    if candidate.get("contract_id") != "room16.reit.v4.primary_text_candidate@1":
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_CONTRACT_INVALID")
    if candidate.get("contract_version") != 1:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_CONTRACT_VERSION_INVALID")
    supplied = str(candidate.get("candidate_sha256", ""))
    if not SHA256_RE.fullmatch(supplied):
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_HASH_INVALID")
    body = {k: v for k, v in candidate.items() if k != "candidate_sha256"}
    if canonical_sha256(body) != supplied:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_HASH_MISMATCH")
    identity_body = {
        k: v
        for k, v in body.items()
        if k not in {"candidate_id", "candidate_identity_payload_sha256"}
    }
    identity_sha = canonical_sha256(identity_body)
    if candidate.get("candidate_identity_payload_sha256") != identity_sha:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_IDENTITY_HASH_MISMATCH")
    if candidate.get("candidate_id") != f"room16.reit.v4.primary.{identity_sha}":
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_ID_MISMATCH")
    lineage = candidate.get("source_lineage")
    if not isinstance(lineage, Mapping) or any(
        not SHA256_RE.fullmatch(str(lineage.get(field, "")))
        for field in ("source_artifact_sha256", "source_snapshot_sha256")
    ):
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_LINEAGE_INVALID")
    if candidate.get("parser_contract_sha256") != PARSER_CONTRACT_SHA256:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_PARSER_AUTHORITY_MISMATCH")

    scale = str(candidate.get("scale", "")).upper()
    multiplier_by_scale = {
        "DOLLAR": Decimal(1),
        "DOLLARS": Decimal(1),
        "THOUSAND": Decimal(1000),
        "THOUSANDS": Decimal(1000),
        "MILLION": Decimal(1_000_000),
        "MILLIONS": Decimal(1_000_000),
        "BILLION": Decimal(1_000_000_000),
        "BILLIONS": Decimal(1_000_000_000),
    }
    expected_multiplier = multiplier_by_scale.get(scale)
    if expected_multiplier is None:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_SCALE_INVALID")
    try:
        reported = Decimal(str(candidate.get("reported_numeric_value")))
        multiplier = Decimal(str(candidate.get("scale_multiplier")))
        numeric = Decimal(str(candidate.get("numeric_value")))
    except InvalidOperation as exc:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_NUMERIC_INVALID") from exc
    if multiplier != expected_multiplier or reported * multiplier != numeric:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_NUMERIC_SCALE_MISMATCH")

    scale_proof = {
        "locator": candidate.get("scale_authority_locator"),
        "text": _clean_text(str(candidate.get("scale_authority_text", ""))),
        "scale": scale.lower(),
    }
    if canonical_sha256(scale_proof) != candidate.get("scale_authority_sha256"):
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_SCALE_AUTHORITY_MISMATCH")

    header_texts = candidate.get("column_header_texts")
    header_locators = candidate.get("column_header_locators")
    if not isinstance(header_texts, list) or not isinstance(header_locators, list):
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_COLUMN_AUTHORITY_MISSING")
    header_proof = {
        "texts": header_texts,
        "locators": header_locators,
        "period_end": candidate.get("period_end"),
        "basis": candidate.get("period_basis"),
    }
    if canonical_sha256(header_proof) != candidate.get("column_header_sha256"):
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_COLUMN_AUTHORITY_MISMATCH")

    reconciliation = candidate.get("reconciliation_authority")
    if reconciliation is not None:
        if not isinstance(reconciliation, Mapping):
            raise ValueError("REIT_V4_PRIMARY_CANDIDATE_RECONCILIATION_INVALID")
        claimed = reconciliation.get("authority_sha256")
        proof = {k: v for k, v in reconciliation.items() if k != "authority_sha256"}
        if canonical_sha256(proof) != claimed:
            raise ValueError("REIT_V4_PRIMARY_CANDIDATE_RECONCILIATION_AUTHORITY_MISMATCH")

    if candidate.get("economic_scope_grade") not in {"A", "B", "C"}:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_GRADE_INVALID")
    if candidate.get("period_basis") not in {
        "STANDALONE_QUARTER",
        "YEAR_TO_DATE",
        "ANNUAL",
    }:
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_PERIOD_BASIS_INVALID")
    if candidate.get("synthetic") or candidate.get("ticker_specific_rule"):
        raise ValueError("REIT_V4_PRIMARY_CANDIDATE_POLICY_INVALID")
    return supplied


def parse_primary_text_candidates_v4(
    path: Path,
    *,
    ticker: str,
    cik: str,
    filing: Mapping[str, Any],
    source_artifact_sha256: str,
    source_snapshot_sha256: str,
) -> dict[str, Any]:
    """Parse a hash-bound captured SEC HTML document into typed candidates."""
    if not path.is_file():
        raise ValueError("REIT_V4_CAPTURE_REQUIRED_BEFORE_PRIMARY_TEXT_PARSE")
    if not SHA256_RE.fullmatch(source_artifact_sha256) or not SHA256_RE.fullmatch(
        source_snapshot_sha256
    ):
        raise ValueError("REIT_V4_SOURCE_HASH_INVALID")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != source_artifact_sha256:
        raise ValueError("REIT_V4_SOURCE_ARTIFACT_HASH_MISMATCH")
    root = html.fromstring(payload)
    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for table_index, table in enumerate(root.xpath("//table")):
        grid = _build_table_grid(table, table_index)
        reconciliation = _table_reconciliation_authority(grid)
        for row in grid.rows:
            label_refs = [
                ref
                for ref in row
                if ref.text
                and re.search(r"\bffo\b|\bfunds\s+from\s+operations\b", ref.text, re.I)
            ]
            if not label_refs:
                continue
            label_ref = label_refs[0]
            label_class = classify_ffo_label(label_ref.text)
            if label_class["status"] == "REJECT":
                rejected.append(
                    {
                        "document_identity": filing.get("document_name"),
                        "row_locator": f"table:{table_index}/row:{label_ref.row_index}",
                        "reported_label": label_ref.text,
                        "reason": label_class["reason"],
                    }
                )
                continue
            per_share_context = _per_share_section_context(grid, label_ref.row_index)
            if per_share_context is not None:
                rejected.append(
                    {
                        "document_identity": filing.get("document_name"),
                        "row_locator": f"table:{table_index}/row:{label_ref.row_index}",
                        "reported_label": label_ref.text,
                        "reason": "PER_SHARE_TABLE_CONTEXT",
                        "context": per_share_context,
                    }
                )
                continue
            numeric = _numeric_cells_after_label(row, label_ref)
            if not numeric:
                rejected.append(
                    {
                        "document_identity": filing.get("document_name"),
                        "row_locator": f"table:{table_index}/row:{label_ref.row_index}",
                        "reported_label": label_ref.text,
                        "reason": "NO_ABSOLUTE_NUMERIC_VALUE",
                    }
                )
                continue
            scale = _local_scale_authority(grid, label_ref.row_index)
            if scale is None:
                rejected.append(
                    {
                        "document_identity": filing.get("document_name"),
                        "row_locator": f"table:{table_index}/row:{label_ref.row_index}",
                        "reported_label": label_ref.text,
                        "reason": "UNSUPPORTED_SCALE",
                    }
                )
                continue
            bound_any = False
            for value_ref, value in numeric:
                period = _period_binding(grid, value_ref)
                if period is None or period["period_basis"] == "UNKNOWN_DURATION":
                    continue
                bound_any = True
                candidates.append(
                    _candidate_body(
                        ticker=ticker,
                        cik=cik,
                        filing=filing,
                        grid=grid,
                        label_ref=label_ref,
                        value_ref=value_ref,
                        label_class=label_class,
                        value=value,
                        scale=scale,
                        period=period,
                        reconciliation=reconciliation,
                        source_artifact_sha256=source_artifact_sha256,
                        source_snapshot_sha256=source_snapshot_sha256,
                    )
                )
            if not bound_any:
                rejected.append(
                    {
                        "document_identity": filing.get("document_name"),
                        "row_locator": f"table:{table_index}/row:{label_ref.row_index}",
                        "reported_label": label_ref.text,
                        "reason": "UNSUPPORTED_PERIOD_BINDING",
                    }
                )
    body = {
        "contract_id": "room16.reit.v4.primary_text_parse_result@1",
        "parser_contract_sha256": PARSER_CONTRACT_SHA256,
        "source_artifact_sha256": source_artifact_sha256,
        "candidate_count": len(candidates),
        "rejected_row_count": len(rejected),
        "candidates": candidates,
        "rejected_rows": rejected,
    }
    return {**body, "parse_result_sha256": canonical_sha256(body)}


def _label_rank(candidate: Mapping[str, Any]) -> int:
    label = _norm_label(str(candidate.get("reported_label", "")))
    explicit_nareit = bool(re.search(r"\bnareit\b|as\s+defined\s+by\s+nareit", label))
    attributable = bool(re.search(r"\b(?:attributable|available)\s+to\b", label))
    if explicit_nareit and attributable:
        return 0
    if attributable:
        return 1
    if explicit_nareit:
        return 2
    if label in {"ffo", "funds from operations"}:
        return 3
    return 4


def select_reported_ffo_v4(
    candidates: Iterable[Mapping[str, Any]], *, as_of: str
) -> dict[str, Any]:
    as_of_date = date.fromisoformat(as_of)
    eligible: list[Mapping[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for candidate in candidates:
        validate_primary_text_candidate_v4(candidate)
        reason: str | None = None
        if candidate.get("metric_id") != "reported_ffo":
            reason = "NON_CORE_FFO_FAMILY"
        elif candidate.get("economic_scope_grade") != "A":
            reason = "GRADE_NOT_CORE_USABLE"
        elif candidate.get("unit") != "USD":
            reason = "UNIT_NOT_ABSOLUTE_USD"
        elif candidate.get("period_basis") not in {
            "STANDALONE_QUARTER",
            "YEAR_TO_DATE",
            "ANNUAL",
        }:
            reason = "PERIOD_BASIS_NOT_USABLE"
        else:
            try:
                period_end = date.fromisoformat(str(candidate.get("period_end")))
                filing_date = date.fromisoformat(str(candidate.get("filing_date")))
            except ValueError:
                reason = "PERIOD_OR_FILING_DATE_INVALID"
            else:
                if period_end > as_of_date:
                    reason = "PERIOD_AFTER_AS_OF"
                elif filing_date > as_of_date:
                    reason = "FILED_AFTER_AS_OF"
        if reason:
            rejected.append({"candidate_sha256": candidate["candidate_sha256"], "reason": reason})
        else:
            eligible.append(candidate)

    basis_rank = {"STANDALONE_QUARTER": 0, "YEAR_TO_DATE": 1, "ANNUAL": 2}
    eligible.sort(
        key=lambda item: (
            -int(str(item["period_end"]).replace("-", "")),
            basis_rank.get(str(item.get("period_basis")), 99),
            _label_rank(item),
            -int(str(item.get("filing_date") or "0000-00-00").replace("-", "")),
            str(item.get("accession") or ""),
            str(item["candidate_sha256"]),
        )
    )
    selected = eligible[0] if eligible else None
    rejected.extend(
        {"candidate_sha256": item["candidate_sha256"], "reason": "LOWER_DETERMINISTIC_RANK"}
        for item in eligible[1:]
    )
    selected_projection = (
        {
            key: selected.get(key)
            for key in (
                "reported_label",
                "numeric_value",
                "unit",
                "scale",
                "period_end",
                "period_basis",
                "economic_scope_grade",
                "document_identity",
                "accession",
                "row_locator",
                "value_cell_locator",
                "column_header_sha256",
                "scale_authority_sha256",
            )
        }
        if selected
        else None
    )
    receipt_body = {
        "contract_id": "room16.reit.v4.ffo_selection_receipt@1",
        "status": "SELECTED" if selected else "UNSUPPORTED",
        "counted": int(selected is not None),
        "selected_candidate_sha256": selected.get("candidate_sha256") if selected else None,
        "selected_candidate_id": selected.get("candidate_id") if selected else None,
        "selected_projection": selected_projection,
        "rejected_candidates": rejected,
        "parser_contract_sha256": PARSER_CONTRACT_SHA256,
    }
    receipt = {**receipt_body, "receipt_sha256": canonical_sha256(receipt_body)}
    return {"selected": selected, "receipt": receipt, "selected_projection": selected_projection}


__all__ = [
    "PARSER_CONTRACT",
    "PARSER_CONTRACT_SHA256",
    "canonical_sha256",
    "classify_ffo_label",
    "parse_primary_text_candidates_v4",
    "select_reported_ffo_v4",
    "validate_primary_text_candidate_v4",
]
