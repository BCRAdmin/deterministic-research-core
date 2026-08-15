#!/usr/bin/env python3
"""Generate the RFC-0001 Registry Foundation 1.1.0 and Product mirror."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_bytes, sha256_json

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = (
    ROOT
    / "research_agent/semantic_compiler/registry_foundation/config/registry_foundation_v1_1.json"
)
FOUNDATION_V1_HASH = "3cbaea421c51e6a3f1b5dad14fc619fd66d1b5420322b619b76455ac9416a239"


def _operand_contract(
    required: list[str], patterns: list[str], minimum: int, maximum: int
) -> dict[str, object]:
    return {
        "required_roles": sorted(required),
        "allowed_role_patterns": sorted(patterns),
        "min_operands": minimum,
        "max_operands": maximum,
    }


LEGACY_OPERAND_CONTRACTS = {
    "annual_minus_prior_interim_plus_current_interim": _operand_contract(["annual", "current_interim", "prior_interim"], [r"^(annual|current_interim|prior_interim)$"], 3, 3),
    "buybacks_current_period_plus_dividends_paid_current_period": _operand_contract(["buybacks_current_period", "dividends_paid_current_period"], [r"^(buybacks_current_period|dividends_paid_current_period)$"], 2, 2),
    "buybacks_ttm_plus_dividends_paid_ttm": _operand_contract(["buybacks", "dividends_paid"], [r"^(buybacks|dividends_paid)$"], 2, 2),
    "cfo_minus_capex": _operand_contract(["capex_ttm", "operating_cash_flow_ttm"], [r"^(capex_ttm|operating_cash_flow_ttm)$"], 2, 2),
    "close_divided_by_trailing_eps": _operand_contract(["close", "trailing_eps"], [r"^(close|trailing_eps)$"], 2, 2),
    "close_times_point_in_time_shares": _operand_contract(["close"], [r"^close$", r"^.*share_count$"], 2, 2),
    "current_assets_divided_by_current_liabilities": _operand_contract(["current_assets", "current_liabilities"], [r"^(current_assets|current_liabilities)$"], 2, 2),
    "current_period_cfo_minus_capex": _operand_contract(["capex", "operating_cash_flow"], [r"^(capex|operating_cash_flow)$"], 2, 2),
    "dcf_terminal_value_share_v1": _operand_contract(["equity_value", "present_value_terminal_value"], [r"^(equity_value|present_value_terminal_value)$"], 2, 2),
    "enterprise_value_divided_by_revenue_ttm": _operand_contract(["enterprise_value", "revenue_ttm"], [r"^(enterprise_value|revenue_ttm)$"], 2, 2),
    "equity_dcf_sensitivity_policy_v1": _operand_contract([], [r"^dcf_base_(discount_rate|terminal_growth_rate)$"], 1, 1),
    "equity_dcf_sensitivity_v1": _operand_contract(["discount_rate", "forecast_years", "free_cash_flow_growth_rate", "starting_free_cash_flow", "terminal_growth_rate"], [r"^(discount_rate|forecast_years|free_cash_flow_growth_rate|starting_free_cash_flow|terminal_growth_rate)$"], 5, 5),
    "free_cash_flow_interest_coverage": _operand_contract(["free_cash_flow_ttm", "interest_expense_ttm"], [r"^(free_cash_flow_ttm|interest_expense_ttm)$"], 2, 2),
    "identity_from_period_matched_issuer_fcf": _operand_contract(["issuer_defined_fcf"], [r"^issuer_defined_fcf$"], 1, 1),
    "issuer_defined_fcf_minus_room16_normalized_fcf": _operand_contract(["issuer_defined_fcf", "room16_normalized_fcf"], [r"^(issuer_defined_fcf|room16_normalized_fcf)$"], 2, 2),
    "issuer_fcf_less_distributions_and_acquisition_cash": _operand_contract(["acquisition_cash", "issuer_defined_fcf", "shareholder_distributions"], [r"^(acquisition_cash|issuer_defined_fcf|shareholder_distributions)$"], 3, 3),
    "issuer_financial_risk_coverage_v1": _operand_contract(["capital_allocation", "cash_flow_durability", "dilution", "financial_resilience"], [r"^(capital_allocation|cash_flow_durability|dilution|financial_resilience)$"], 4, 4),
    "issuer_financial_risk_v1": _operand_contract(["capital_allocation", "cash_flow_durability", "dilution", "financial_resilience"], [r"^(capital_allocation|cash_flow_durability|dilution|financial_resilience)$"], 4, 4),
    "liquid_assets_minus_total_debt": _operand_contract(["total_debt"], [r"^(cash_and_equivalents|marketable_securities|short_term_investments|total_debt)$"], 2, 4),
    "market_cap_divided_by_free_cash_flow_ttm": _operand_contract(["free_cash_flow_ttm", "market_cap"], [r"^(free_cash_flow_ttm|market_cap)$"], 2, 2),
    "market_cap_plus_debt_minus_liquid_assets": _operand_contract(["market_cap", "total_debt"], [r"^(cash_and_equivalents|market_cap|marketable_securities|short_term_investments|total_debt)$"], 3, 5),
    "matching_period_diluted_share_count_yoy_change": _operand_contract(["current_diluted_share_count", "prior_diluted_share_count"], [r"^(current_diluted_share_count|prior_diluted_share_count)$"], 2, 2),
    "matching_quarter_yoy_growth": _operand_contract([], [r"^current_[a-z0-9_]+$", r"^prior_[a-z0-9_]+$"], 2, 2),
    "operating_income_interest_coverage": _operand_contract(["interest_expense_ttm", "operating_income_ttm"], [r"^(interest_expense_ttm|operating_income_ttm)$"], 2, 2),
    "reported_current_period_buybacks": _operand_contract(["buybacks"], [r"^buybacks$"], 1, 1),
    "reported_current_period_dividends_paid": _operand_contract(["dividends_paid"], [r"^dividends_paid$"], 1, 1),
    "reverse_equity_dcf_growth_solver_v1": _operand_contract(["discount_rate", "forecast_years", "starting_free_cash_flow", "target_equity_value", "terminal_growth_rate"], [r"^(discount_rate|forecast_years|starting_free_cash_flow|target_equity_value|terminal_growth_rate)$"], 5, 5),
    "room16_fcf_less_distributions_and_acquisition_cash": _operand_contract(["acquisition_cash", "room16_normalized_fcf", "shareholder_distributions"], [r"^(acquisition_cash|room16_normalized_fcf|shareholder_distributions)$"], 3, 3),
    "sbc_ttm_divided_by_free_cash_flow_ttm": _operand_contract(["free_cash_flow_ttm", "sbc_ttm"], [r"^(free_cash_flow_ttm|sbc_ttm)$"], 2, 2),
    "sbc_ttm_divided_by_revenue_ttm": _operand_contract(["revenue_ttm", "sbc_ttm"], [r"^(revenue_ttm|sbc_ttm)$"], 2, 2),
    "shareholder_distributions_current_period_minus_free_cash_flow_current_period": _operand_contract(["free_cash_flow_current_period", "shareholder_distributions_current_period"], [r"^(free_cash_flow_current_period|shareholder_distributions_current_period)$"], 2, 2),
    "shareholder_distributions_ttm_minus_free_cash_flow_ttm": _operand_contract(["free_cash_flow_ttm", "shareholder_distributions_ttm"], [r"^(free_cash_flow_ttm|shareholder_distributions_ttm)$"], 2, 2),
    "sum_available_interest_bearing_debt_components": _operand_contract([], [r"^debt_[a-z0-9_]+$"], 1, 16),
    "sum_period_matched_acquisition_cash_components": _operand_contract([], [r"^[A-Za-z0-9_.:-]+$"], 1, 32),
}


def _metric(
    definition_id: str,
    description: str,
    dimensions: list[str],
    patterns: list[str],
) -> dict[str, object]:
    return {
        "definition_id": definition_id,
        "definition_version": 1,
        "semantic_description": description,
        "dimensions": sorted(set(dimensions) | {"basis_points", "count", "currency", "index", "multiple", "per_share", "percent", "text"}),
        "allowed_fact_types": sorted([
            "annual_cap", "annual_rate", "annualized_run_rate", "basis_point_change",
            "contribution_to_change", "flow_value", "guidance_component", "guidance_range",
            "instant_value", "per_share_rate", "percentage_of_total", "period_total",
            "policy_value", "quarterly_rate", "reconciliation_component", "stock_value",
            "year_over_year_change",
        ]),
        "allowed_units": sorted(["CAD", "USD", "USD/share", "USD_per_share", "basis_points", "count", "index", "multiple", "percent", "ratio", "score_0_100", "shares", "text"]),
        "allowed_period_kinds": sorted(["comparison", "duration", "guidance", "instant", "rate", "trailing_twelve_months"]),
        "allowed_scales": sorted(["base", "basis_points", "billion", "million", "none", "percent", "thousand"]),
        "allowed_currencies": sorted(["CAD", "USD", "none"]),
        "instance_patterns": sorted(patterns),
        "compatibility": "additive_v1",
    }


def _formula(
    definition_id: str,
    expression: str,
    roles: list[str],
    dimensions: list[str],
    result_dimension: str,
    aliases: list[str],
    *,
    zero_division: str = "fail_closed",
) -> dict[str, object]:
    return {
        "formula_definition_id": definition_id,
        "formula_version": 1,
        "expression_contract": expression,
        "operand_roles": sorted(roles),
        "operand_dimensions": dimensions,
        "result_dimension": result_dimension,
        "rounding_policy": "preserve_binary64_then_renderer_rounds",
        "missing_operand_policy": "fail_closed",
        "zero_division_policy": zero_division,
        "provenance_policy": "all_operands_required",
        "determinism_contract": "pure_same_input_same_output",
        "legacy_aliases": sorted(aliases),
        "legacy_operand_contracts": {
            alias: LEGACY_OPERAND_CONTRACTS[alias] for alias in sorted(aliases)
        },
    }


def build_payload() -> dict[str, object]:
    metric_definitions = [
        _metric("metric.capital_allocation", "Capital-allocation flow, residual or reconciliation metric.", ["currency", "percent"], [r"^(buybacks_current_period|capital_allocation_.*|dividends_paid_current_period|fcf_definition_difference_current_period|free_cash_flow_current_period|issuer_defined_fcf_current_period|shareholder_distributions.*)$"]),
        _metric("metric.core_financial", "Reported or deterministically normalized core financial metric.", ["count", "currency", "multiple", "percent", "per_share"], [r"^(capex|current_period_.*|current_ratio|diluted_share_count_yoy|free_cash_flow_ttm|lease_liability_noncurrent|net_cash|net_income|net_income_ttm|operating_cash_flow|operating_income|revenue|revenue_ttm|sbc_to_fcf|sbc_to_revenue|total_debt)$"]),
        _metric("metric.filing_numeric", "Numeric disclosure instance extracted from a filing topic.", ["currency", "percent", "per_share"], [r"^filing_.*$"]),
        _metric("metric.guidance", "Issuer guidance range or guidance component.", ["currency", "percent", "per_share"], [r"^guidance_.*$"]),
        _metric("metric.operating_kpi", "Issuer operating KPI instance with period and optional segment parameters.", ["basis_points", "count", "currency", "percent", "text"], [r"^operating_kpi_.*$"]),
        _metric("metric.risk", "Deterministic issuer-risk score or coverage measurement.", ["index", "percent"], [r"^financial_risk_.*$"]),
        _metric("metric.scenario", "Illustrative valuation scenario input or result excluded from rating logic unless separately permitted.", ["currency", "percent"], [r"^(dcf_.*|reverse_dcf_.*)$"]),
        _metric("metric.technical", "Deterministic market or technical observation.", ["currency", "index"], [r"^(close|rsi_14|sma_50|sma_200)$"]),
        _metric("metric.valuation", "Point-in-time valuation measurement.", ["currency", "multiple"], [r"^(enterprise_value|ev_to_sales|market_cap|price_to_fcf|trailing_pe)$"]),
    ]
    formula_definitions = [
        _formula("formula.add_components", "sum(all component operands)", ["component_a", "component_b"], ["same"], "same", ["buybacks_current_period_plus_dividends_paid_current_period", "buybacks_ttm_plus_dividends_paid_ttm"]),
        _formula("formula.capital_residual", "free_cash_flow - shareholder_distributions - acquisition_cash", ["acquisition_cash", "free_cash_flow", "shareholder_distributions"], ["currency", "currency", "currency"], "currency", ["issuer_fcf_less_distributions_and_acquisition_cash", "room16_fcf_less_distributions_and_acquisition_cash"]),
        _formula("formula.current_ratio", "current_assets / current_liabilities", ["current_assets", "current_liabilities"], ["currency", "currency"], "multiple", ["current_assets_divided_by_current_liabilities"], zero_division="not_applicable"),
        _formula("formula.dcf_policy_parameter", "identity binding for one registered DCF policy parameter", ["policy_parameter"], ["same"], "same", ["equity_dcf_sensitivity_policy_v1"]),
        _formula("formula.dcf_sensitivity", "discounted explicit cash flows plus discounted terminal value", ["discount_rate", "forecast_years", "free_cash_flow_growth_rate", "starting_free_cash_flow", "terminal_growth_rate"], ["percent", "count", "percent", "currency", "percent"], "currency", ["equity_dcf_sensitivity_v1"]),
        _formula("formula.dcf_terminal_share", "present_value_terminal_value / equity_value", ["equity_value", "present_value_terminal_value"], ["currency", "currency"], "percent", ["dcf_terminal_value_share_v1"], zero_division="not_applicable"),
        _formula("formula.enterprise_value", "market_cap + debt - liquid_assets", ["debt", "liquid_assets", "market_cap"], ["currency", "currency", "currency"], "currency", ["market_cap_plus_debt_minus_liquid_assets"]),
        _formula("formula.fcf", "operating_cash_flow - capital_expenditure", ["capital_expenditure", "operating_cash_flow"], ["currency", "currency"], "currency", ["cfo_minus_capex", "current_period_cfo_minus_capex"]),
        _formula("formula.fcf_definition_difference", "issuer_defined_fcf - room16_normalized_fcf", ["issuer_defined_fcf", "room16_normalized_fcf"], ["currency", "currency"], "currency", ["issuer_defined_fcf_minus_room16_normalized_fcf"]),
        _formula("formula.growth", "(current - prior) / abs(prior)", ["current", "prior"], ["same", "same"], "percent", ["matching_period_diluted_share_count_yoy_change", "matching_quarter_yoy_growth"], zero_division="not_applicable"),
        _formula("formula.identity", "reported operand without arithmetic transformation", ["reported_value"], ["same"], "same", ["identity_from_period_matched_issuer_fcf", "reported_current_period_buybacks", "reported_current_period_dividends_paid"]),
        _formula("formula.interest_coverage", "earnings_measure / interest_expense", ["earnings_measure", "interest_expense"], ["currency", "currency"], "multiple", ["free_cash_flow_interest_coverage", "operating_income_interest_coverage"], zero_division="not_applicable"),
        _formula("formula.market_cap", "close * point_in_time_shares", ["close", "point_in_time_shares"], ["currency_per_share", "shares"], "currency", ["close_times_point_in_time_shares"]),
        _formula("formula.net_cash", "liquid_assets - total_debt", ["liquid_assets", "total_debt"], ["currency", "currency"], "currency", ["liquid_assets_minus_total_debt"]),
        _formula("formula.ratio_multiple", "numerator / denominator", ["denominator", "numerator"], ["same"], "multiple", ["close_divided_by_trailing_eps", "enterprise_value_divided_by_revenue_ttm", "market_cap_divided_by_free_cash_flow_ttm"], zero_division="not_applicable"),
        _formula("formula.ratio_percent", "numerator / denominator", ["denominator", "numerator"], ["same"], "percent", ["sbc_ttm_divided_by_free_cash_flow_ttm", "sbc_ttm_divided_by_revenue_ttm"], zero_division="not_applicable"),
        _formula("formula.reverse_dcf", "solve growth where discounted equity value equals target equity value", ["discount_rate", "forecast_years", "starting_free_cash_flow", "target_equity_value", "terminal_growth_rate"], ["percent", "count", "currency", "currency", "percent"], "percent", ["reverse_equity_dcf_growth_solver_v1"]),
        _formula("formula.risk_coverage", "measured risk weight / total risk weight", ["capital_allocation", "cash_flow_durability", "dilution", "financial_resilience"], ["index"], "percent", ["issuer_financial_risk_coverage_v1"], zero_division="not_applicable"),
        _formula("formula.risk_score", "weighted measured risk components", ["capital_allocation", "cash_flow_durability", "dilution", "financial_resilience"], ["index"], "index", ["issuer_financial_risk_v1"]),
        _formula("formula.subtract_components", "left - right", ["left", "right"], ["same"], "same", ["shareholder_distributions_current_period_minus_free_cash_flow_current_period", "shareholder_distributions_ttm_minus_free_cash_flow_ttm"]),
        _formula("formula.sum_debt", "sum available interest-bearing debt components", ["component"], ["currency"], "currency", ["sum_available_interest_bearing_debt_components"]),
        _formula("formula.sum_period_components", "sum period-matched acquisition cash components", ["component"], ["currency"], "currency", ["sum_period_matched_acquisition_cash_components"]),
        _formula("formula.ttm_bridge", "annual - prior_interim + current_interim", ["annual", "current_interim", "prior_interim"], ["same"], "same", ["annual_minus_prior_interim_plus_current_interim"]),
    ]
    claim_kinds = []
    for claim_kind, required, decision in [
        ("financial_metric", ["numeric_fact"], "eligible"),
        ("guidance", ["guidance_fact"], "eligible_with_uncertainty"),
        ("news", [], "context_only"),
        ("rating", ["permission_corridor"], "decision_output"),
        ("risk", ["risk_fact"], "eligible"),
        ("technical_metric", ["market_fact"], "timing_only"),
        ("valuation_metric", ["valuation_fact"], "eligible_if_measured"),
    ]:
        claim_kinds.append({
            "claim_kind_id": f"claim.{claim_kind}",
            "required_fact_roles": sorted(required),
            "optional_fact_roles": sorted(["counterevidence", "uncertainty"]),
            "allowed_evidence_edges": sorted(["derived_from", "supported_by"]),
            "materiality_contract": "explicit_or_inherited_from_bound_facts",
            "rendering_eligibility": "requires_complete_citation_lineage",
            "decision_eligibility": decision,
            "citation_requirements": "every_numeric_binding_and_material_assertion",
            "quarantine_behavior": "fail_closed",
        })
    decision_ids = {
        "decision.counterevidence": "Evidence that constrains or opposes a decision input.",
        "decision.input.operating_signal": "Operating KPI input with score-inclusion state.",
        "decision.input.risk": "Current issuer-risk input with calibration boundary.",
        "decision.non_advice_boundary": "Boundary preventing personalized action language.",
        "decision.permission_corridor": "Allowed and blocked rating corridor.",
        "decision.rating_permission": "Exact legacy rating permission state.",
        "decision.rationale": "Reason or risk contributing to the conclusion.",
        "decision.rule": "Generic deterministic decision rule instance.",
        "decision.score_contribution": "Named score component and inclusion state.",
        "decision.timing_state": "Timing overlay isolated from fundamental judgment.",
    }
    decision_definitions = [{
        "decision_node_definition_id": key,
        "node_semantics": value,
        "allowed_input_kinds": sorted(["current_risk", "financial_metric", "operating_kpi", "policy", "score", "text"]),
        "required_lineage": sorted(["legacy_decision_packet"]),
        "compatibility": "additive_v1",
    } for key, value in sorted(decision_ids.items())]
    payload: dict[str, object] = {
        "contract_id": "room16.compiler.registry_foundation",
        "contract_version": 1,
        "version": "1.1.0",
        "compatibility": "additive_successor_of_1.0.0",
        "parent_foundation_version": "1.0.0",
        "parent_registry_authority_sha256": FOUNDATION_V1_HASH,
        "owner": "research",
        "product_role": "hash_verified_consumer_only",
        "authority_bundle_version": 3,
        "authority_bundle_changed": False,
        "metric_definitions": sorted(metric_definitions, key=lambda item: str(item["definition_id"])),
        "formula_definitions": sorted(formula_definitions, key=lambda item: str(item["formula_definition_id"])),
        "claim_kind_definitions": sorted(claim_kinds, key=lambda item: str(item["claim_kind_id"])),
        "decision_node_definitions": decision_definitions,
        "risk_definitions": [{
            "risk_definition_id": "risk.current_issuer_risk",
            "semantic_description": "Current issuer risk separated from data and review limitations.",
            "score_eligibility": "calibrated_only",
            "counterevidence_required": True,
        }],
        "permission_corridor_definitions": [{
            "permission_corridor_definition_id": "permission.rating_corridor",
            "allowed_rating_contract": "allowed_ratings_subset_with_preferred_rating",
            "publication_contract": "legacy_publication_permission_preserved",
            "non_advice_boundary_required": True,
        }],
        "identifier_policies": {
            "blocked_executable_prefixes": ["event_", "positional_", "unknown_", "unmapped_"],
            "definition_instance_separation_required": True,
            "single_definition_binding_required": True,
            "ticker_specific_definitions_allowed": False,
            "unknown_executable_ids_allowed": False,
        },
    }
    payload["authority_sha256"] = sha256_json(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-repo", type=Path, default=ROOT.parent / "company-dossier-lab")
    args = parser.parse_args()
    payload = build_payload()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    OUTPUT.write_text(rendered, encoding="utf-8")
    product = args.product_repo.resolve()
    mirror = product / "config/room16_semantic_registry_mirror_v1_1.json"
    lock = product / "config/room16_semantic_registry_mirror_v1_1.lock.json"
    mirror.write_text(rendered, encoding="utf-8")
    pass_contract_path = (
        ROOT
        / "research_agent/semantic_compiler/semantic_wave/config/semantic_wave_pass_contracts.json"
    )
    pass_contracts = json.loads(pass_contract_path.read_text(encoding="utf-8"))
    lock_payload = {
        "contract_id": "room16.compiler.product_semantic_registry_mirror_lock",
        "contract_version": 1,
        "registry_foundation_version": "1.1.0",
        "authority_owner": "research",
        "mirror_mode": "hash_verified_read_only",
        "authority_sha256": payload["authority_sha256"],
        "canonical_document_sha256": sha256_bytes(canonical_bytes(payload)),
        "parent_foundation_version": "1.0.0",
        "authority_bundle_version": 3,
        "semantic_wave_pass_contracts_sha256": sha256_bytes(
            canonical_bytes(pass_contracts)
        ),
        "product_may_edit_semantics": False,
        "product_may_add_registry_entries": False,
    }
    lock.write_text(json.dumps(lock_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "pass",
        "registry_foundation_version": "1.1.0",
        "authority_sha256": payload["authority_sha256"],
        "canonical_document_sha256": lock_payload["canonical_document_sha256"],
        "research_authority": str(OUTPUT),
        "product_mirror": str(mirror),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
