"""Explicit, hash-bound metric semantics for the shared Alpha compiler.

Semantics in this module are keyed by exact metric id.  Deliberately no
fallback exists: an unknown metric is unsupported rather than receiving a
unit or period type guessed from its name.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from research_agent.alpha_bank.projection import CORE_ORDER as BANK_ORDER
from research_agent.alpha_bank.projection import MAPPING_REGISTRY as BANK_MAPPING
from research_agent.alpha_energy.projection import CORE_ORDER as ENERGY_ORDER
from research_agent.alpha_energy.projection import MAPPING_REGISTRY as ENERGY_MAPPING
from research_agent.alpha_reit.projection import CORE_ORDER as REIT_ORDER
from research_agent.alpha_reit.projection import MAPPING_REGISTRY as REIT_MAPPING
from research_agent.alpha_saas.projection import CORE_ORDER as SAAS_ORDER
from research_agent.alpha_saas.projection import MAPPING_REGISTRY as SAAS_MAPPING
from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256 = r"^[0-9a-f]{64}$"
PeriodType = Literal["INSTANT", "DURATION"]


class MetricSemanticsIR(StrictModel):
    contract_id: Literal["room16.fixed24.metric_semantics_ir"] = (
        "room16.fixed24.metric_semantics_ir"
    )
    contract_version: Literal[1] = 1
    metric_id: str
    archetype_profile_ids: tuple[str, ...]
    semantic_definition: str
    period_type: PeriodType
    allowed_units: tuple[str, ...]
    canonical_unit_or_null: str | None
    scale_policy: Literal["PURE", "EXPLICIT_SOURCE_SCALE_ONLY"]
    approved_concepts: tuple[str, ...]
    source_precedence: tuple[str, ...]
    formula_eligibility: tuple[str, ...]
    required_core: bool
    semantics_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "MetricSemanticsIR":
        body = {
            "contract_id": "room16.fixed24.metric_semantics_ir",
            "contract_version": 1,
            **values,
        }
        return cls(**body, semantics_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_hash(self) -> "MetricSemanticsIR":
        body = self.model_dump(mode="json", exclude={"semantics_sha256"})
        if sha256_json(body) != self.semantics_sha256:
            raise ValueError("metric semantics self-hash mismatch")
        return self


_MAPPINGS = {
    "saas": SAAS_MAPPING["metrics"],
    "reit": REIT_MAPPING["metrics"],
    "bank": BANK_MAPPING["metrics"],
    "energy": ENERGY_MAPPING["metrics"],
}
_PROFILE_ORDERS = {
    "saas": SAAS_ORDER,
    "reit": REIT_ORDER,
    "bank": BANK_ORDER,
    "energy": ENERGY_ORDER,
}
_REQUIRED_CORE = {
    metric_id
    for order in _PROFILE_ORDERS.values()
    for metric_id in order[:5]
}

# Exact semantic categories.  Membership is intentionally enumerated rather
# than inferred from substrings such as "share", "rate", or "margin".
_INSTANT = {
    "allowance_for_credit_losses",
    "cash",
    "cash_and_due_from_banks",
    "cet1_capital",
    "common_shares",
    "current_contract_liability",
    "current_debt",
    "debt_maturity_12m",
    "debt_maturity_after_y5",
    "debt_maturity_y2",
    "debt_maturity_y3",
    "debt_maturity_y4",
    "debt_maturity_y5",
    "deposits",
    "gross_loans_or_financing_receivables",
    "investment_securities",
    "latest_market_price",
    "long_term_debt",
    "long_term_debt_and_leases",
    "net_debt",
    "rpo",
    "risk_weighted_assets",
    "shares_outstanding",
    "total_assets",
    "total_debt",
}

_PER_SHARE = {
    "common_dividend_per_share",
    "diluted_eps",
    "dividend_per_share_paid",
}

_SHARES = {
    "common_shares",
    "diluted_weighted_average_shares",
    "shares_outstanding",
}

_PURE = {
    "allowance_to_loans",
    "cet1_ratio_advanced",
    "cet1_ratio_standardized",
    "operating_margin",
    "period_end_loans_to_deposits",
    "reported_occupancy",
    "reported_rent_growth",
    "supplementary_leverage_ratio",
    "tier1_capital_ratio",
    "tier1_leverage_ratio",
    "total_capital_ratio",
    "weighted_average_interest_rate",
}

_COUNTS = {"reportable_segment_count"}

_DERIVED = {
    "allowance_to_loans",
    "free_cash_flow",
    "net_debt",
    "operating_margin",
    "period_end_loans_to_deposits",
}

_SUPPLEMENTAL_NON_GAAP = {
    "reported_affo",
    "reported_core_ffo",
    "reported_development_pipeline",
    "reported_dispositions",
    "reported_ffo",
    "reported_noi",
    "reported_occupancy",
    "reported_rent_growth",
    "reported_same_store_noi",
}


def _profiles_for(metric_id: str) -> tuple[str, ...]:
    return tuple(
        sorted(profile for profile, values in _PROFILE_ORDERS.items() if metric_id in values)
    )


def _concepts_for(metric_id: str) -> tuple[str, ...]:
    values = {
        str(concept)
        for mappings in _MAPPINGS.values()
        for concept in mappings.get(metric_id, ())
    }
    return tuple(sorted(values))


def _units(metric_id: str) -> tuple[str, ...]:
    if metric_id in _PER_SHARE:
        return ("USD / shares", "USD/shares")
    if metric_id in _SHARES:
        return ("shares",)
    if metric_id in _PURE or metric_id in _COUNTS:
        return ("pure", "ratio") if metric_id in _PURE else ("pure",)
    return ("USD",)


def _definition(metric_id: str) -> str:
    definitions = {
        "diluted_eps": "diluted earnings attributable per weighted-average diluted share",
        "rpo": "total remaining performance obligation measured at the reporting instant",
        "current_contract_liability": "current contract liability; distinct from RPO and cRPO",
        "common_stock_repurchases": "cash paid to repurchase common stock",
        "share_repurchases": "cash paid for share repurchases",
        "shares_outstanding": "common shares outstanding at the reporting instant",
        "reported_ffo": "issuer-reported total funds from operations",
        "reported_core_ffo": "issuer-reported total Core FFO",
        "reported_affo": "issuer-reported total AFFO with an explicit AFFO title",
    }
    return definitions.get(metric_id, f"explicit shared semantic metric: {metric_id}")


_ALL_METRICS = tuple(
    sorted(
        {metric for values in _PROFILE_ORDERS.values() for metric in values}
        | _DERIVED
        | _SUPPLEMENTAL_NON_GAAP
    )
)


def _build_registry() -> dict[str, MetricSemanticsIR]:
    values: dict[str, MetricSemanticsIR] = {}
    for metric_id in _ALL_METRICS:
        profiles = set(_profiles_for(metric_id))
        if metric_id in _SUPPLEMENTAL_NON_GAAP:
            profiles.add("reit")
        units = _units(metric_id)
        values[metric_id] = MetricSemanticsIR.create(
            metric_id=metric_id,
            archetype_profile_ids=tuple(sorted(profiles)),
            semantic_definition=_definition(metric_id),
            period_type="INSTANT" if metric_id in _INSTANT else "DURATION",
            allowed_units=units,
            canonical_unit_or_null=units[0] if len(units) == 1 else None,
            scale_policy="PURE" if metric_id in _PURE or metric_id in _COUNTS else "EXPLICIT_SOURCE_SCALE_ONLY",
            approved_concepts=_concepts_for(metric_id),
            source_precedence=(
                "exact_current_base_xbrl_direct",
                "exact_current_supplemental_direct",
                "safe_approved_formula",
            ),
            formula_eligibility=("approved_formula_output",) if metric_id in _DERIVED else (),
            required_core=metric_id in _REQUIRED_CORE,
        )
    return values


METRIC_SEMANTICS = _build_registry()
_REGISTRY_BODY = {
    "contract_id": "room16.fixed24.metric_semantics_registry",
    "contract_version": 1,
    "ticker_specific_rules": False,
    "unknown_metric_policy": "UNSUPPORTED_NO_GUESS",
    "metrics": {
        key: value.model_dump(mode="json") for key, value in sorted(METRIC_SEMANTICS.items())
    },
}
METRIC_SEMANTICS_REGISTRY = {
    **_REGISTRY_BODY,
    "registry_sha256": sha256_json(_REGISTRY_BODY),
}
METRIC_SEMANTICS_REGISTRY_SHA256 = METRIC_SEMANTICS_REGISTRY["registry_sha256"]


def metric_semantics(metric_id: str) -> MetricSemanticsIR | None:
    """Return exact semantics, or ``None`` when the metric is unknown."""

    return METRIC_SEMANTICS.get(metric_id)
