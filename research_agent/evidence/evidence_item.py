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
    source_scale: Optional[str] = None
    source_unit: Optional[str] = None
    source_sign: Optional[Literal[-1, 1]] = None
    currency: Optional[str] = None
    column_label: Optional[str] = None
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
            "not_applicable",
            "unknown",
        ]
    ] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    comparison_period_start: Optional[str] = None
    comparison_period_end: Optional[str] = None
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
            if self.currency or re.fullmatch(r"[A-Z]{3}", upper_unit):
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
                "not_applicable": "not_applicable",
                "unknown": "unknown",
            }[self.period_kind]
        return self
