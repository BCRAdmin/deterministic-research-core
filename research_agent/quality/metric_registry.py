"""Stable semantic metric registry for source adapters and release gates."""

from __future__ import annotations

import re
from typing import Any


def _entry(
    metric_id: str,
    label: str,
    aliases: list[str],
    dimension: str,
    units: list[str],
    currencies: list[str],
    period_kinds: list[str],
    rate_basis: list[str],
    directions: list[str],
    aggregation: str,
    patterns: list[str],
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "canonical_label": label,
        "aliases": aliases,
        "dimension": dimension,
        "allowed_units": units,
        "allowed_currencies": currencies,
        "allowed_period_kinds": period_kinds,
        "allowed_rate_basis": rate_basis,
        "allowed_directions": directions,
        "aggregation_behavior": aggregation,
        "company_archetype": "general_corporate",
        "source_table_patterns": patterns,
    }


METRIC_REGISTRY = {
    item["metric_id"]: item
    for item in (
        _entry("collection_disposal_revenue_growth_pct", "Collection and disposal revenue growth", ["collection and disposal revenue growth"], "percent", ["percent"], [], ["comparison"], [], ["increase", "decrease", "neutral"], "non_additive_change", [r"collection.*disposal.*revenue.*growth"]),
        _entry("collection_disposal_core_price_pct", "Collection and disposal core price", ["core price"], "percent", ["percent"], [], ["comparison"], [], ["increase", "decrease", "neutral"], "non_additive_change", [r"collection.*disposal.*core price"]),
        _entry("collection_disposal_yield_pct", "Collection and disposal yield", ["collection and disposal yield", "average yield"], "percent", ["percent"], [], ["comparison", "duration"], [], ["increase", "decrease", "neutral"], "non_additive_change", [r"(?:total )?average yield"]),
        _entry("total_average_yield_change_usd", "Total average yield change", ["total average yield amount"], "currency", ["currency"], ["USD"], ["comparison"], [], ["increase", "decrease", "neutral"], "additive_change", [r"total average yield"]),
        _entry("total_average_yield_share_of_company_pct", "Total average yield share of company", ["yield percent of total company"], "percent", ["percent"], [], ["duration"], [], ["neutral"], "non_additive_share", [r"total average yield.*% of total"]),
        _entry("dividends_paid_usd", "Dividends paid", ["cash dividends paid", "dividend payments"], "currency", ["currency"], ["USD"], ["duration"], [], ["neutral"], "additive_flow", [r"cash dividends"]),
        _entry("quarterly_dividend_per_share_usd", "Quarterly dividend per share", ["quarterly per share dividend"], "per_share", ["currency_per_share"], ["USD"], ["rate"], ["per_share_per_quarter"], ["increase", "decrease", "neutral"], "effective_rate", [r"quarterly.*per share dividend"]),
        _entry("landfill_depletable_tons", "Landfill depletable tons", ["depletable tons"], "count", ["count"], [], ["duration"], [], ["increase", "decrease", "neutral"], "additive_flow", [r"landfill depletable tons"]),
        _entry("internalization_rate_pct", "Internalization rate", ["internalization of waste"], "percent", ["percent"], [], ["duration", "comparison"], [], ["increase", "decrease", "neutral"], "non_additive_rate", [r"internalization"]),
        _entry("acquired_annualized_revenue_usd", "Acquired annualized revenue", ["gross annualized revenue acquired"], "currency", ["currency"], ["USD"], ["rate"], ["annualized_at_acquisition_window"], ["neutral"], "annualized_run_rate", [r"annualized revenue acquired"]),
        _entry("revenue_guidance_change_pct", "Revenue guidance change", ["revenue outlook reduction"], "percent", ["percent"], [], ["guidance"], [], ["increase", "decrease"], "non_additive_change", [r"revenue.*(?:guidance|outlook).*(?:reduction|increase)"]),
        _entry("operating_ebitda_headwind_bps", "Operating EBITDA headwind", ["basis point headwind"], "basis_points", ["basis_points"], [], ["duration", "comparison"], [], ["decrease"], "contribution_to_change", [r"operating ebitda.*headwind"]),
    )
}


POSITIONAL_RE = re.compile(r"(?:^|_)(?:event|value)_?\d+(?:_|$)", re.IGNORECASE)


def resolve_metric_definition(metric_id: str, *, source_text: str = "") -> dict[str, Any]:
    """Resolve a metric to a stable definition or return an unresolved result."""

    candidate = str(metric_id or "").strip()
    if not candidate or POSITIONAL_RE.search(candidate) or "unmapped" in candidate:
        return {"metric_id": candidate, "mapping_status": "unresolved", "definition": None}
    if candidate in METRIC_REGISTRY:
        return {"metric_id": candidate, "mapping_status": "mapped", "definition": METRIC_REGISTRY[candidate]}
    normalized = source_text.casefold()
    matches = [
        definition
        for definition in METRIC_REGISTRY.values()
        if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in definition["source_table_patterns"])
    ]
    if len(matches) == 1:
        return {"metric_id": matches[0]["metric_id"], "mapping_status": "mapped", "definition": matches[0]}
    # Existing deterministic packet metrics are accepted when their identity
    # is semantic and non-positional; the exact instance ID remains intact.
    if re.fullmatch(r"[a-z][a-z0-9_]*", candidate):
        return {"metric_id": candidate, "mapping_status": "mapped", "definition": None}
    return {"metric_id": candidate, "mapping_status": "unresolved", "definition": None}


def registry_manifest() -> dict[str, Any]:
    return {
        "contract_id": "room16.metric_registry",
        "contract_version": 1,
        "metrics": [METRIC_REGISTRY[key] for key in sorted(METRIC_REGISTRY)],
    }

