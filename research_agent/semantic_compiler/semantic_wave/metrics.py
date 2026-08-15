"""BA6 deterministic metric binding and formula evaluation engine."""

from __future__ import annotations

import math
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.research_core.calculations.valuation import (
    _solve_implied_growth,
    equity_dcf_value,
)
from research_agent.semantic_compiler.registry_foundation.authority import SemanticRegistryAuthority
from research_agent.semantic_compiler.registry_foundation.coverage import (
    formula_instance_from_legacy,
    metric_instance_from_legacy,
)

from .contracts import FormulaEvaluationIR, MetricIR, TypedFactIR, create_hashed


class FormulaEvaluationError(ValueError):
    """Raised when a registered formula cannot be reproduced."""


def _num(operands: dict[str, Any], key: str) -> float:
    value = operands.get(key)
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise FormulaEvaluationError(f"missing_or_invalid_operand:{key}")
    return float(value)


def _divide(numerator: float, denominator: float) -> float:
    if denominator == 0:
        raise FormulaEvaluationError("zero_division")
    return numerator / denominator


def evaluate_legacy_formula(
    legacy_formula_id: str,
    operands: dict[str, Any],
    *,
    fact_context: dict[str, dict[str, Any]],
) -> float:
    values = [float(value) for value in operands.values() if isinstance(value, (int, float))]
    if not operands:
        raise FormulaEvaluationError("formula_parameter_marker_not_evaluation")
    if legacy_formula_id in {
        "reported_current_period_buybacks", "reported_current_period_dividends_paid",
        "identity_from_period_matched_issuer_fcf", "equity_dcf_sensitivity_policy_v1",
    }:
        if len(values) != 1:
            raise FormulaEvaluationError("identity_operand_count")
        return values[0]
    if legacy_formula_id in {
        "buybacks_current_period_plus_dividends_paid_current_period",
        "buybacks_ttm_plus_dividends_paid_ttm",
        "sum_available_interest_bearing_debt_components",
        "sum_period_matched_acquisition_cash_components",
    }:
        return sum(values)
    if legacy_formula_id in {
        "issuer_fcf_less_distributions_and_acquisition_cash",
        "room16_fcf_less_distributions_and_acquisition_cash",
    }:
        free_cash_flow = operands.get("issuer_defined_fcf", operands.get("room16_normalized_fcf"))
        if not isinstance(free_cash_flow, (int, float)):
            raise FormulaEvaluationError("missing_free_cash_flow_operand")
        return float(free_cash_flow) - _num(operands, "shareholder_distributions") - _num(operands, "acquisition_cash")
    if legacy_formula_id in {"matching_quarter_yoy_growth", "matching_period_diluted_share_count_yoy_change"}:
        current_key = next((key for key in operands if key.startswith("current_")), None)
        prior_key = next((key for key in operands if key.startswith("prior_")), None)
        if current_key is None or prior_key is None:
            raise FormulaEvaluationError("growth_operand_roles")
        return _divide(_num(operands, current_key) - _num(operands, prior_key), abs(_num(operands, prior_key)))
    if legacy_formula_id == "current_assets_divided_by_current_liabilities":
        return _divide(_num(operands, "current_assets"), _num(operands, "current_liabilities"))
    if legacy_formula_id in {"cfo_minus_capex", "current_period_cfo_minus_capex"}:
        cfo = operands.get("operating_cash_flow_ttm", operands.get("operating_cash_flow"))
        capex = operands.get("capex_ttm", operands.get("capex"))
        if not isinstance(cfo, (int, float)) or not isinstance(capex, (int, float)):
            raise FormulaEvaluationError("fcf_operand_roles")
        return float(cfo) - float(capex)
    if legacy_formula_id == "issuer_defined_fcf_minus_room16_normalized_fcf":
        return _num(operands, "issuer_defined_fcf") - _num(operands, "room16_normalized_fcf")
    if legacy_formula_id == "annual_minus_prior_interim_plus_current_interim":
        return _num(operands, "annual") - _num(operands, "prior_interim") + _num(operands, "current_interim")
    if legacy_formula_id == "market_cap_plus_debt_minus_liquid_assets":
        liquid = sum(float(value) for key, value in operands.items() if key in {"cash_and_equivalents", "short_term_investments", "marketable_securities"})
        return _num(operands, "market_cap") + _num(operands, "total_debt") - liquid
    if legacy_formula_id == "liquid_assets_minus_total_debt":
        liquid = sum(float(value) for key, value in operands.items() if key in {"cash_and_equivalents", "short_term_investments", "marketable_securities"})
        return liquid - _num(operands, "total_debt")
    if legacy_formula_id == "close_times_point_in_time_shares":
        share_key = next((key for key in operands if "share_count" in key), None)
        if share_key is None:
            raise FormulaEvaluationError("share_basis_operand_missing")
        return _num(operands, "close") * _num(operands, share_key)
    ratios = {
        "close_divided_by_trailing_eps": ("close", "trailing_eps"),
        "enterprise_value_divided_by_revenue_ttm": ("enterprise_value", "revenue_ttm"),
        "market_cap_divided_by_free_cash_flow_ttm": ("market_cap", "free_cash_flow_ttm"),
        "sbc_ttm_divided_by_free_cash_flow_ttm": ("sbc_ttm", "free_cash_flow_ttm"),
        "sbc_ttm_divided_by_revenue_ttm": ("sbc_ttm", "revenue_ttm"),
        "free_cash_flow_interest_coverage": ("free_cash_flow_ttm", "interest_expense_ttm"),
        "operating_income_interest_coverage": ("operating_income_ttm", "interest_expense_ttm"),
    }
    if legacy_formula_id in ratios:
        numerator, denominator = ratios[legacy_formula_id]
        return _divide(_num(operands, numerator), _num(operands, denominator))
    if legacy_formula_id in {
        "shareholder_distributions_current_period_minus_free_cash_flow_current_period",
        "shareholder_distributions_ttm_minus_free_cash_flow_ttm",
    }:
        distribution_key = next(key for key in operands if key.startswith("shareholder_distributions"))
        fcf_key = next(key for key in operands if key.startswith("free_cash_flow"))
        return _num(operands, distribution_key) - _num(operands, fcf_key)
    if legacy_formula_id in {"equity_dcf_sensitivity_v1", "equity_dcf_sensitivity_policy_v1"}:
        _, _, total = equity_dcf_value(
            starting_free_cash_flow=_num(operands, "starting_free_cash_flow"),
            free_cash_flow_growth_rate=_num(operands, "free_cash_flow_growth_rate"),
            discount_rate=_num(operands, "discount_rate"),
            terminal_growth_rate=_num(operands, "terminal_growth_rate"),
            forecast_years=int(_num(operands, "forecast_years")),
        )
        return total
    if legacy_formula_id == "dcf_terminal_value_share_v1":
        return _divide(_num(operands, "present_value_terminal_value"), _num(operands, "equity_value"))
    if legacy_formula_id == "reverse_equity_dcf_growth_solver_v1":
        result = _solve_implied_growth(
            starting_free_cash_flow=_num(operands, "starting_free_cash_flow"),
            target_equity_value=_num(operands, "target_equity_value"),
            discount_rate=_num(operands, "discount_rate"),
            terminal_growth_rate=_num(operands, "terminal_growth_rate"),
        )
        if result is None:
            raise FormulaEvaluationError("reverse_dcf_outside_solver_range")
        return result
    if legacy_formula_id == "issuer_financial_risk_coverage_v1":
        weights = {"capital_allocation": 0.15, "cash_flow_durability": 0.30, "dilution": 0.20, "financial_resilience": 0.35}
        return sum(_num(operands, key) * weights[key] for key in weights)
    if legacy_formula_id == "issuer_financial_risk_v1":
        coverage_operands = fact_context.get("financial_risk_coverage", {}).get("formula_operands") or {}
        weights = {"capital_allocation": 0.15, "cash_flow_durability": 0.30, "dilution": 0.20, "financial_resilience": 0.35}
        effective = {key: weights[key] * float(coverage_operands.get(key, 0.0)) for key in weights}
        measured = sum(effective.values())
        return round(sum(_num(operands, key) * effective[key] for key in weights) / measured, 2)
    raise FormulaEvaluationError(f"formula_not_implemented:{legacy_formula_id}")


def build_metrics_and_evaluations(
    facts: list[dict[str, Any]],
    typed_facts: tuple[TypedFactIR, ...],
    *,
    authority: SemanticRegistryAuthority | None = None,
) -> tuple[tuple[MetricIR, ...], tuple[FormulaEvaluationIR, ...], tuple[dict[str, Any], ...]]:
    authority = authority or SemanticRegistryAuthority.load()
    typed_by_id = {item.fact_id: item for item in typed_facts}
    metrics: list[MetricIR] = []
    evaluations: list[FormulaEvaluationIR] = []
    markers: list[dict[str, Any]] = []
    context = {str(item["metric"]): item for item in facts}
    for fact in sorted(facts, key=lambda item: str(item["fact_id"])):
        typed = typed_by_id[str(fact["fact_id"])]
        binding = metric_instance_from_legacy(fact, authority)
        metrics.append(create_hashed(
            MetricIR,
            metric_instance_id=f"metric.instance.{str(fact['fact_id']).lower()}",
            metric_definition_id=binding.canonical_definition_id,
            result_fact_id=typed.fact_id,
            value=typed.value,
            dimension=typed.dimension,
            unit=typed.unit,
            period_kind=typed.period_kind,
            binding_sha256=binding.binding_sha256,
        ))
        if not fact.get("formula_id"):
            continue
        if not fact.get("formula_operands"):
            markers.append({
                "result_fact_id": typed.fact_id,
                "legacy_formula_id": str(fact["formula_id"]),
                "formula_definition_id": authority.bind_formula(str(fact["formula_id"])),
                "status": "diagnostic_only",
                "reason": "formula_parameter_marker_not_evaluation",
            })
            continue
        instance = formula_instance_from_legacy(fact, authority)
        evaluated = evaluate_legacy_formula(
            str(fact["formula_id"]),
            dict(fact["formula_operands"]),
            fact_context=context,
        )
        expected = float(fact["value"])
        if not math.isclose(evaluated, expected, rel_tol=1e-10, abs_tol=1e-8):
            raise FormulaEvaluationError(
                f"formula_result_mismatch:{fact['metric']}:{evaluated}:{expected}"
            )
        definition = authority.formula_definitions[instance.formula_definition_id]
        evaluation_hash = sha256_json({
            "formula_instance": instance.model_dump(mode="json"),
            "expected_value": expected,
            "evaluated_value": evaluated,
            "result_fact_id": typed.fact_id,
        })
        evaluations.append(create_hashed(
            FormulaEvaluationIR,
            formula_instance_id=instance.formula_instance_id,
            formula_definition_id=instance.formula_definition_id,
            operand_fact_ids=instance.operand_fact_ids,
            result_fact_id=typed.fact_id,
            expected_value=expected,
            evaluated_value=evaluated,
            result_dimension=definition.result_dimension,
            rounding_policy=definition.rounding_policy,
            evaluation_status="verified",
            evaluation_hash=evaluation_hash,
        ))
    return tuple(metrics), tuple(evaluations), tuple(markers)
