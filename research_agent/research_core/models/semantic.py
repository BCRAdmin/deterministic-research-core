"""Canonical semantic contracts shared by source adapters and release gates."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


Direction = Literal["increase", "decrease", "neutral", "mixed", "unknown"]
Impact = Literal["positive", "adverse", "neutral", "mixed", "unknown"]
FactType = Literal[
    "instant_value",
    "period_total",
    "quarterly_rate",
    "annual_rate",
    "annualized_run_rate",
    "year_over_year_change",
    "sequential_change",
    "basis_point_change",
    "guidance_range",
    "guidance_change",
    "contribution_to_change",
    "percentage_of_total",
    "reconciliation_component",
    "per_share_rate",
    "stock_value",
    "flow_value",
    "balance_value",
]


class CanonicalTableCell(BaseModel):
    cell_id: str
    table_id: str
    row_key: str
    column_key: str
    raw_text: str
    normalized_value: Optional[float] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    scale: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    period_kind: str = "unknown"
    comparison_period_start: Optional[str] = None
    comparison_period_end: Optional[str] = None
    rate_basis: Optional[str] = None
    direction: Direction = "neutral"
    impact: Impact = "neutral"
    is_zero: bool = False
    is_not_applicable: bool = False
    is_missing: bool = False
    source_locator: str

    @model_validator(mode="after")
    def distinct_structural_states(self) -> "CanonicalTableCell":
        if self.is_not_applicable and (self.is_zero or self.normalized_value is not None):
            raise ValueError("not_applicable_zero_collision")
        if self.is_missing and self.normalized_value is not None:
            raise ValueError("missing_value_collision")
        if self.normalized_value == 0 and not self.is_not_applicable and not self.is_missing:
            self.is_zero = True
        return self


class CanonicalTable(BaseModel):
    table_id: str
    source_id: str
    source_locator: str
    title: Optional[str] = None
    subtitle: Optional[str] = None
    header_rows: list[list[str]] = Field(default_factory=list)
    row_headers: list[str] = Field(default_factory=list)
    column_headers: list[str] = Field(default_factory=list)
    row_dimension: str
    column_dimension: str
    period_axis: list[str] = Field(default_factory=list)
    metric_axis: list[str] = Field(default_factory=list)
    unit_axis: list[Optional[str]] = Field(default_factory=list)
    currency_axis: list[Optional[str]] = Field(default_factory=list)
    comparison_axis: list[Optional[str]] = Field(default_factory=list)
    value_role: list[str] = Field(default_factory=list)
    table_semantic_type: str
    cells: list[CanonicalTableCell] = Field(default_factory=list)

    @model_validator(mode="after")
    def aligned_cells(self) -> "CanonicalTable":
        if any(cell.table_id != self.table_id for cell in self.cells):
            raise ValueError("table_cell_alignment_invalid")
        if len(self.cells) != len({cell.cell_id for cell in self.cells}):
            raise ValueError("duplicate_table_cell_id")
        return self


class NumericBinding(BaseModel):
    span_id: str
    report_text: str
    fact_id: str
    evidence_id: str
    metric_id: str
    source_id: str
    source_locator: str
    derivation: Optional[dict[str, Any]] = None

