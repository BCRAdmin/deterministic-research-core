from __future__ import annotations

import re
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


ClaimType = Literal[
    "financial_metric",
    "technical_metric",
    "valuation_metric",
    "guidance",
    "event",
    "news",
    "analyst_opinion",
    "price_data",
    "risk",
    "management_quote",
]


class EvidenceItem(BaseModel):
    evidence_id: str
    ticker: str
    claim_type: ClaimType
    source_id: str
    source_type: str
    authority_rank: int
    statement: str
    value: Optional[float] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    date: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    url: Optional[str] = None
    retrieved_at: Optional[str] = None
    supports_metrics: List[str] = Field(default_factory=list)
    # ``supports_claims`` is retained as a wire-compatible alias during the
    # contract migration.  It may contain claim IDs only; semantic buckets
    # such as ``company_risk_analysis`` belong in ``supports_categories``.
    supports_claims: List[str] = Field(default_factory=list)
    supports_claim_ids: List[str] = Field(default_factory=list)
    supports_categories: List[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    formula_id: Optional[str] = None
    formula_operands: Dict[str, float] = Field(default_factory=dict)
    raw_value: Optional[float] = None
    normalized_value: Optional[float] = None
    fact_type: Optional[str] = None
    raw_text: Optional[str] = None
    normalized_magnitude: Optional[float] = None
    signed_value: Optional[float] = None
    direction: str = "neutral"
    impact: str = "neutral"
    rate_basis: Optional[str] = None
    source_scale: Optional[str] = None
    source_unit: Optional[str] = None
    source_sign: Optional[Literal[-1, 1]] = None
    currency: Optional[str] = None
    column_label: Optional[str] = None
    row_metric: Optional[str] = None
    column_metric: Optional[str] = None
    segment: Optional[str] = None
    source_cell_status: Optional[str] = None
    table_id: Optional[str] = None
    cell_id: Optional[str] = None
    row_key: Optional[str] = None
    column_key: Optional[str] = None
    source_locator: Optional[str] = None
    is_zero: bool = False
    is_not_applicable: bool = False
    is_missing: bool = False
    source_accession_number: Optional[str] = None
    source_document: Optional[str] = None
    source_document_role: Optional[str] = None
    source_snapshot_path: Optional[str] = None
    source_content_sha256: Optional[str] = None
    source_content_bytes: Optional[int] = None
    source_lineage: List[str] = Field(default_factory=list)
    duration_days: Optional[int] = None
    audited: Optional[bool] = None
    amendment_status: Optional[str] = None
    dimension: Optional[
        Literal[
            "currency",
            "percent",
            "basis_points",
            "multiple",
            "ratio",
            "count",
            "shares",
            "per_share",
            "index",
            "date",
            "text",
            "unknown",
        ]
    ] = None
    display_unit: Optional[str] = None
    period_kind: Optional[
        Literal[
            "instant",
            "duration",
            "comparison",
            "trailing_twelve_months",
            "guidance",
            "rate",
            "not_applicable",
            "unknown",
        ]
    ] = None
    presentation_basis: Optional[
        Literal[
            "point_in_time",
            "period_total",
            "period_average",
            "period_over_period_comparison",
            "trailing_twelve_months",
            "guidance_range",
            "effective_rate",
            "annualized_run_rate",
            "not_applicable",
            "unknown",
        ]
    ] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    comparison_period_start: Optional[str] = None
    comparison_period_end: Optional[str] = None
    effective_asof_dates: List[str] = Field(default_factory=list)
    provenance_class: Optional[
        Literal[
            "primary_source",
            "market_source",
            "derived_calculation",
            "secondary_source",
            "unknown",
        ]
    ] = None

    @model_validator(mode="after")
    def normalize_typed_contract(self) -> "EvidenceItem":
        """Populate the typed evidence contract without inventing facts.

        Only properties already encoded in the source fields are derived here.
        Ambiguous values remain ``unknown`` and are rejected later when a
        material numeric fact is promoted into the fact ledger.
        """

        legacy_claims = list(dict.fromkeys(self.supports_claims))
        explicit_claims = list(dict.fromkeys([*self.supports_claim_ids, *legacy_claims]))
        self.supports_claim_ids = list(dict.fromkeys(explicit_claims))
        self.supports_claims = list(self.supports_claim_ids)

        unit = str(self.unit or self.source_unit or "").strip()
        upper_unit = unit.upper()
        if self.dimension is None:
            per_share_currency = re.fullmatch(
                r"([A-Z]{3})(?:_PER_SHARE|/SHARE)",
                upper_unit,
            )
            if per_share_currency:
                self.dimension = "per_share"
                self.currency = self.currency or per_share_currency.group(1)
            elif self.currency or re.fullmatch(r"[A-Z]{3}", upper_unit):
                self.dimension = "currency"
            elif upper_unit in {"PERCENT", "%", "FRACTION (1.0 = 100%)"}:
                self.dimension = "percent"
            elif upper_unit in {"BASIS_POINTS", "BASIS POINTS", "BPS"}:
                self.dimension = "basis_points"
            elif upper_unit in {"MULTIPLE", "X"}:
                self.dimension = "multiple"
            elif upper_unit == "RATIO":
                self.dimension = "ratio"
            elif upper_unit in {"SHARE", "SHARES"}:
                self.dimension = "shares"
            elif upper_unit in {"INDEX", "SCORE", "SCORE_0_100"}:
                self.dimension = "index"
            elif upper_unit in {"COUNT", "NUMBER"}:
                self.dimension = "count"
            else:
                self.dimension = "unknown" if self.value is not None else "text"
        if self.dimension == "currency":
            if self.currency is None and re.fullmatch(r"[A-Z]{3}", upper_unit):
                self.currency = upper_unit
            self.display_unit = self.display_unit or self.currency or upper_unit or None
        elif self.dimension == "per_share":
            self.display_unit = self.display_unit or unit or (
                f"{self.currency}/share" if self.currency else "per_share"
            )
        else:
            self.display_unit = self.display_unit or unit or None

        if self.provenance_class is None:
            if self.source_type in {"deterministic_calculation", "derived_calculation"}:
                self.provenance_class = "derived_calculation"
            elif self.source_type in {"sec_filing", "company_ir", "official_press_release"}:
                self.provenance_class = "primary_source"
            elif self.source_type in {"exchange_ohlcv", "trusted_market_data_vendor"}:
                self.provenance_class = "market_source"
            elif self.source_type:
                self.provenance_class = "secondary_source"
            else:
                self.provenance_class = "unknown"

        if self.period_kind is None:
            lowered = str(self.period or "").casefold()
            if self.current_period_start or self.comparison_period_start:
                self.period_kind = "comparison"
            elif "guidance" in self.supports_metrics or self.claim_type == "guidance":
                self.period_kind = "guidance"
            elif "ttm" in lowered or "trailing twelve" in lowered:
                self.period_kind = "trailing_twelve_months"
            elif self.period_start or self.duration_days is not None:
                self.period_kind = "duration"
            elif self.date or self.period_end:
                self.period_kind = "instant"
            elif self.value is None:
                self.period_kind = "not_applicable"
            else:
                self.period_kind = "unknown"
        if self.presentation_basis is None:
            self.presentation_basis = {
                "instant": "point_in_time",
                "duration": "period_total",
                "comparison": "period_over_period_comparison",
                "trailing_twelve_months": "trailing_twelve_months",
                "guidance": "guidance_range",
                "rate": (
                    "annualized_run_rate"
                    if self.fact_type == "annualized_run_rate"
                    else "effective_rate"
                ),
                "not_applicable": "not_applicable",
                "unknown": "unknown",
            }[self.period_kind]
        if self.normalized_magnitude is None and self.value is not None:
            self.normalized_magnitude = abs(float(self.value))
        if self.signed_value is None and self.value is not None:
            self.signed_value = float(self.value)
        if self.raw_text is None:
            self.raw_text = self.statement
        if self.source_cell_status == "not_applicable_dash":
            self.is_not_applicable = True
        if self.is_not_applicable:
            if any(value is not None for value in (self.value, self.raw_value, self.normalized_value, self.normalized_magnitude, self.signed_value)):
                raise ValueError("not_applicable_zero_collision")
            self.is_zero = False
        elif self.value == 0:
            self.is_zero = True
        return self
