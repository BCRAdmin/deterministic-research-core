from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable, List, Mapping, Optional, Union

from pydantic import BaseModel, Field

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.metrics_packet import MetricsPacket

OHLCV_AUTHORITY_SOURCE_TYPES = {
    "exchange_ohlcv",
    "trusted_market_data_vendor",
}


class EvidenceLedger(BaseModel):
    ticker: str
    as_of_date: str
    evidence_items: List[EvidenceItem] = Field(default_factory=list)

    def find_by_metric(self, metric_name: str) -> List[EvidenceItem]:
        aliases = _metric_aliases(metric_name)
        return [
            item
            for item in self.evidence_items
            if aliases.intersection(set(item.supports_metrics))
        ]

    def find_by_claim(self, claim_id: str) -> List[EvidenceItem]:
        return [
            item
            for item in self.evidence_items
            if claim_id in item.supports_claims
        ]

    def has_primary_evidence_for_metric(self, metric_name: str) -> bool:
        return any(item.authority_rank <= 2 for item in self.find_by_metric(metric_name))


def build_evidence_ledger_from_source_registry(
    ticker: str,
    as_of_date: str,
    source_registry: Optional[SourceRegistry],
    metrics_packet: Optional[MetricsPacket] = None,
    currency: str = "USD",
) -> EvidenceLedger:
    if source_registry is None:
        return EvidenceLedger(ticker=ticker.upper(), as_of_date=as_of_date, evidence_items=[])

    items: list[EvidenceItem] = []
    for source in source_registry.sources:
        metrics = _expand_used_for(source.used_for)
        if not metrics:
            metrics = list(source.used_for)
        for metric in metrics:
            value = _metric_value(metrics_packet, metric) if metrics_packet else None
            items.append(
                EvidenceItem(
                    evidence_id=f"{source.source_id}_{_safe_metric_id(metric)}",
                    ticker=ticker.upper(),
                    claim_type=_claim_type_for_metric(metric, source.source_type),
                    source_id=source.source_id,
                    source_type=source.source_type,
                    authority_rank=source.resolved_authority_rank()
                    if hasattr(source, "resolved_authority_rank")
                    else rank_source(source.source_type),
                    statement=f"{source.source_id} supports {metric}.",
                    value=value,
                    unit=unit_for_metric(metric, currency=currency),
                    period=None,
                    date=None,
                    url=source.url,
                    retrieved_at=source.retrieved_at,
                    supports_metrics=[metric],
                    confidence="high" if (source.authority_rank or rank_source(source.source_type)) <= 2 else "medium",
                )
            )
    return EvidenceLedger(ticker=ticker.upper(), as_of_date=as_of_date, evidence_items=items)


def build_technical_derivation_evidence(
    *,
    ticker: str,
    as_of_date: str,
    metrics_packet: MetricsPacket,
    source_registry: Optional[SourceRegistry],
    runtime_evidence: Iterable[EvidenceItem] = (),
    currency: str = "USD",
) -> list[EvidenceItem]:
    """Map calculated technical values back to one registered OHLCV source."""

    candidates: list[tuple[int, str, str, Optional[str], Optional[str]]] = []
    for item in runtime_evidence:
        if item.source_type in OHLCV_AUTHORITY_SOURCE_TYPES:
            candidates.append(
                (
                    item.authority_rank,
                    item.source_id,
                    item.source_type,
                    item.url,
                    item.retrieved_at,
                )
            )
    if source_registry is not None:
        for source in source_registry.sources:
            if source.source_type in OHLCV_AUTHORITY_SOURCE_TYPES:
                candidates.append(
                    (
                        source.resolved_authority_rank(),
                        source.source_id,
                        source.source_type,
                        source.url,
                        source.retrieved_at,
                    )
                )
    if not candidates:
        return []

    authority_rank, source_id, source_type, url, retrieved_at = sorted(
        candidates,
        key=lambda item: (item[0], item[1]),
    )[0]
    technical = metrics_packet.technical
    currency = str(currency or "USD").strip().upper()
    metric_units = {
        "close": currency,
        "sma_50": currency,
        "sma_200": currency,
        "rsi_14": "index",
        "avg_volume_20": "shares",
    }
    evidence: list[EvidenceItem] = []
    for metric_name, unit in metric_units.items():
        value = getattr(technical, metric_name, None)
        if value is None:
            continue
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_{metric_name.upper()}_"
                    f"{technical.indicator_date}"
                ),
                ticker=ticker.upper(),
                claim_type=(
                    "price_data" if metric_name == "close" else "technical_metric"
                ),
                source_id=source_id,
                source_type=source_type,
                authority_rank=authority_rank,
                statement=(
                    f"{metric_name} was calculated deterministically from the "
                    f"registered OHLCV source {source_id}."
                ),
                value=float(value),
                unit=unit,
                period="daily_history",
                date=technical.indicator_date,
                url=url,
                retrieved_at=retrieved_at,
                supports_metrics=[metric_name],
                confidence="high",
            )
        )
    return evidence


def build_fundamental_derivation_evidence(
    *,
    ticker: str,
    as_of_date: str,
    metrics_packet: MetricsPacket,
    normalized_fundamentals: dict,
    price_source_id: Optional[str] = None,
    runtime_evidence: Iterable[EvidenceItem] = (),
    currency: str = "USD",
) -> list[EvidenceItem]:
    """Keep every material TTM transformation and its operands auditable."""

    bridges = normalized_fundamentals.get("ttm_bridges")
    if not isinstance(bridges, dict):
        bridges = {}
    source_id = f"ROOM16_{ticker.upper()}_DETERMINISTIC_CALCULATIONS"
    valuation_lineage = [source_id]
    if price_source_id:
        valuation_lineage.append(price_source_id)
    evidence: list[EvidenceItem] = []
    runtime_items = list(runtime_evidence)
    currency = str(currency or "USD").strip().upper()
    for raw_metric, bridge in sorted(bridges.items()):
        if not isinstance(bridge, dict):
            continue
        metric_name = {
            "revenue": "revenue_ttm",
            "operating_income": "operating_income_ttm",
            "net_income": "net_income_ttm",
            "operating_cash_flow": "operating_cash_flow_ttm",
            "capex": "capex_ttm",
            "sbc": "sbc_ttm",
            "buybacks": "buybacks",
            "dividends_paid": "dividends_paid",
            "depreciation_and_amortization": "depreciation_and_amortization_ttm",
            "interest_expense": "interest_expense_ttm",
            "eps_diluted": "trailing_eps",
        }.get(str(raw_metric), f"{raw_metric}_ttm")
        value = _metric_value(metrics_packet, metric_name)
        if value is None:
            continue
        operands = {
            str(key): float(value)
            for key, value in (bridge.get("operands") or {}).items()
            if isinstance(value, (int, float))
        }
        formula_id = str(bridge.get("formula_id") or "unknown_ttm_formula")
        if not _bridge_value_matches(
            value=float(value),
            formula_id=formula_id,
            operands=operands,
        ) or not _bridge_operands_have_exact_evidence(
            runtime_items,
            metric_name=str(raw_metric),
            formula_id=formula_id,
            operands=operands,
            source_ids=[
                str(item)
                for item in bridge.get("source_ids") or []
                if item
            ],
        ):
            continue
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_"
                    f"{_safe_metric_id(metric_name)}_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"{metric_name}={value:g} was derived deterministically "
                    f"with {formula_id}; operands={operands}."
                ),
                value=value,
                unit=unit_for_metric(metric_name, currency=currency),
                period=(
                    f"{bridge.get('period_start') or 'unknown'}"
                    f"..{bridge.get('period_end') or as_of_date}"
                ),
                date=str(bridge.get("period_end") or as_of_date),
                supports_metrics=[metric_name, str(raw_metric)],
                confidence="high",
                formula_id=formula_id,
                formula_operands=operands,
                normalized_value=value,
                source_lineage=sorted(
                    {
                        str(source_id)
                        for source_id in bridge.get("source_ids") or []
                        if source_id
                    }
                ),
            )
        )
    fundamentals = metrics_packet.fundamentals
    distribution_period = _common_bridge_period(
        bridges,
        "buybacks",
        "dividends_paid",
    )
    distribution_period_text = (
        f"{distribution_period[0]}..{distribution_period[1]}"
        if distribution_period
        else f"TTM through {as_of_date}"
    )
    distribution_period_end = (
        distribution_period[1]
        if distribution_period
        else as_of_date
    )
    fcf_period = _common_bridge_period(
        bridges,
        "operating_cash_flow",
        "capex",
    )
    fcf_period_text = (
        f"{fcf_period[0]}..{fcf_period[1]}"
        if fcf_period
        else f"TTM through {as_of_date}"
    )
    fcf_period_end = fcf_period[1] if fcf_period else as_of_date
    growth_bridge = normalized_fundamentals.get(
        "revenue_growth_yoy_bridge"
    )
    if (
        fundamentals.revenue_growth_yoy is not None
        and isinstance(growth_bridge, Mapping)
    ):
        operands = {
            str(key): float(value)
            for key, value in (growth_bridge.get("operands") or {}).items()
            if isinstance(value, (int, float))
        }
        prior_revenue = operands.get("prior_annual_revenue")
        current_revenue = operands.get("current_annual_revenue")
        expected_growth = (
            (current_revenue - prior_revenue) / prior_revenue
            if current_revenue is not None
            and prior_revenue not in (None, 0)
            else None
        )
        if (
            expected_growth is not None
            and math.isclose(
                expected_growth,
                float(fundamentals.revenue_growth_yoy),
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and _bridge_operands_have_exact_evidence(
                runtime_items,
                metric_name="revenue",
                formula_id="annual_revenue_yoy_growth",
                operands=operands,
                source_ids=[
                    str(item)
                    for item in growth_bridge.get("source_ids") or []
                    if item
                ],
            )
        ):
            evidence.append(
                _calculation_evidence(
                    ticker=ticker,
                    as_of_date=as_of_date,
                    source_id=source_id,
                    metric_name="revenue_growth_yoy",
                    value=float(fundamentals.revenue_growth_yoy),
                    formula_id=str(
                        growth_bridge.get("formula_id")
                        or "annual_revenue_yoy_growth"
                    ),
                    operands=operands,
                    unit="fraction",
                    period=(
                        f"{growth_bridge.get('period_start') or 'unknown'}"
                        f"..{growth_bridge.get('period_end') or as_of_date}"
                    ),
                    date=str(
                        growth_bridge.get("period_end") or as_of_date
                    ),
                    evidence_items=[*runtime_items, *evidence],
                    source_lineage=_canonical_lineage_source_ids(
                        [*runtime_items, *evidence],
                        [
                            str(item)
                            for item in growth_bridge.get("source_ids") or []
                        ],
                    ),
                )
            )
    if (
        fundamentals.ebitda_ttm is not None
        and fundamentals.operating_income_ttm is not None
        and fundamentals.depreciation_and_amortization_ttm is not None
        and math.isclose(
            float(fundamentals.ebitda_ttm),
            float(fundamentals.operating_income_ttm)
            + float(fundamentals.depreciation_and_amortization_ttm),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
        and _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            {
                "operating_income_ttm": float(
                    fundamentals.operating_income_ttm
                ),
                "depreciation_and_amortization_ttm": float(
                    fundamentals.depreciation_and_amortization_ttm
                ),
            },
        )
    ):
        operands = {
            "operating_income_ttm": float(
                fundamentals.operating_income_ttm
            ),
            "depreciation_and_amortization_ttm": float(
                fundamentals.depreciation_and_amortization_ttm
            ),
        }
        evidence.append(
            _calculation_evidence(
                ticker=ticker,
                as_of_date=as_of_date,
                source_id=source_id,
                metric_name="ebitda_ttm",
                value=float(fundamentals.ebitda_ttm),
                formula_id="operating_income_plus_depreciation_and_amortization",
                operands=operands,
                unit=currency,
                period=f"TTM through {as_of_date}",
                date=as_of_date,
                evidence_items=[*runtime_items, *evidence],
            )
        )
    lease_components = {
        metric_name: float(value)
        for metric_name, value in (
            (
                "lease_liability_current",
                fundamentals.lease_liability_current,
            ),
            (
                "lease_liability_noncurrent",
                fundamentals.lease_liability_noncurrent,
            ),
        )
        if value is not None
    }
    if (
        fundamentals.total_lease_liabilities is not None
        and lease_components
        and math.isclose(
            sum(lease_components.values()),
            float(fundamentals.total_lease_liabilities),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
        and _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            lease_components,
        )
    ):
        evidence.append(
            _calculation_evidence(
                ticker=ticker,
                as_of_date=as_of_date,
                source_id=source_id,
                metric_name="total_lease_liabilities",
                value=float(fundamentals.total_lease_liabilities),
                formula_id="sum_available_lease_liability_components",
                operands=lease_components,
                unit=currency,
                period=f"as of {as_of_date}",
                date=as_of_date,
                evidence_items=[*runtime_items, *evidence],
            )
        )
    if (
        fundamentals.economic_share_count is not None
        and fundamentals.listed_share_count is not None
        and math.isclose(
            float(fundamentals.economic_share_count),
            float(fundamentals.listed_share_count),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
        and _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            {
                "listed_share_count": float(
                    fundamentals.listed_share_count
                )
            },
        )
    ):
        operands = {
            "listed_share_count": float(
                fundamentals.listed_share_count
            )
        }
        evidence.append(
            _calculation_evidence(
                ticker=ticker,
                as_of_date=as_of_date,
                source_id=source_id,
                metric_name="economic_share_count",
                value=float(fundamentals.economic_share_count),
                formula_id="point_in_time_listed_shares_alias",
                operands=operands,
                unit="shares",
                period=f"as of {as_of_date}",
                date=as_of_date,
                evidence_items=[*runtime_items, *evidence],
            )
        )
    if (
        fundamentals.diluted_share_count is not None
        and _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            {
                "shares_diluted": float(
                    fundamentals.diluted_share_count
                )
            },
        )
    ):
        operands = {
            "shares_diluted": float(fundamentals.diluted_share_count)
        }
        evidence.append(
            _calculation_evidence(
                ticker=ticker,
                as_of_date=as_of_date,
                source_id=source_id,
                metric_name="diluted_share_count",
                value=float(fundamentals.diluted_share_count),
                formula_id="latest_reported_diluted_share_count",
                operands=operands,
                unit="shares",
                period=f"latest reported period through {as_of_date}",
                date=as_of_date,
                evidence_items=[*runtime_items, *evidence],
            )
        )
    debt_components = {
        metric_name: float(value)
        for metric_name, value in (
            ("debt_current", fundamentals.debt_current),
            ("debt_noncurrent", fundamentals.debt_noncurrent),
        )
        if value is not None
    }
    if (
        fundamentals.total_debt is not None
        and debt_components
        and abs(
            sum(debt_components.values()) - float(fundamentals.total_debt)
        )
        <= max(1e-9, abs(float(fundamentals.total_debt)) * 1e-9)
        and _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            debt_components,
        )
    ):
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_TOTAL_DEBT_"
                    f"{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"total_debt={fundamentals.total_debt:g} was derived from "
                    f"the available debt components; operands={debt_components}."
                ),
                value=float(fundamentals.total_debt),
                unit=currency,
                period=f"as of {as_of_date}",
                date=as_of_date,
                supports_metrics=["total_debt"],
                confidence="high",
                formula_id="sum_available_interest_bearing_debt_components",
                formula_operands=debt_components,
                normalized_value=float(fundamentals.total_debt),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    debt_components,
                    fallback_source_id=source_id,
                ),
            )
        )
    liquid_assets = {
        metric_name: float(value)
        for metric_name, value in (
            ("cash_and_equivalents", fundamentals.cash_and_equivalents),
            ("short_term_investments", fundamentals.short_term_investments),
            ("marketable_securities", fundamentals.marketable_securities),
        )
        if value is not None
    }
    if (
        fundamentals.cash_and_investments is not None
        and liquid_assets
        and math.isclose(
            sum(liquid_assets.values()),
            float(fundamentals.cash_and_investments),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
        and _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            liquid_assets,
        )
    ):
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_"
                    f"CASH_AND_INVESTMENTS_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    "cash_and_investments="
                    f"{fundamentals.cash_and_investments:g} was derived from "
                    f"the available liquid assets; operands={liquid_assets}."
                ),
                value=float(fundamentals.cash_and_investments),
                unit=currency,
                period=f"as of {as_of_date}",
                date=as_of_date,
                supports_metrics=["cash_and_investments"],
                confidence="high",
                formula_id="sum_available_liquid_assets",
                formula_operands=liquid_assets,
                normalized_value=float(fundamentals.cash_and_investments),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    liquid_assets,
                    fallback_source_id=source_id,
                ),
            )
        )
    operands: dict[str, float] = {}
    if (
        fundamentals.net_cash is not None
        and fundamentals.total_debt is not None
        and liquid_assets
    ):
        operands = {
            **liquid_assets,
            "total_debt": float(fundamentals.total_debt),
        }
        expected_net_cash = (
            sum(liquid_assets.values()) - float(fundamentals.total_debt)
        )
        if not (
            math.isclose(
                float(fundamentals.net_cash),
                expected_net_cash,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and _operands_have_exact_evidence(
                [*runtime_items, *evidence],
                operands,
            )
        ):
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_NET_CASH_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"net_cash={fundamentals.net_cash:g} was calculated from "
                    f"liquid assets less debt; operands={operands}."
                ),
                value=float(fundamentals.net_cash),
                unit=currency,
                period=f"as of {as_of_date}",
                date=as_of_date,
                supports_metrics=["net_cash"],
                confidence="high",
                formula_id="liquid_assets_minus_total_debt",
                formula_operands=operands,
                normalized_value=float(fundamentals.net_cash),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    operands,
                    fallback_source_id=source_id,
                ),
            )
        )
    share_basis_name = None
    share_basis_value = None
    if fundamentals.economic_share_count not in (None, 0):
        share_basis_name = "economic_share_count"
        share_basis_value = fundamentals.economic_share_count
    elif fundamentals.diluted_share_count not in (None, 0):
        share_basis_name = "diluted_share_count"
        share_basis_value = fundamentals.diluted_share_count
    if (
        fundamentals.trailing_eps is not None
        and fundamentals.net_income_ttm is not None
        and share_basis_name is not None
        and not _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            {"trailing_eps": float(fundamentals.trailing_eps)},
        )
        and _division_matches(
            value=fundamentals.trailing_eps,
            numerator=fundamentals.net_income_ttm,
            denominator=share_basis_value,
        )
    ):
        operands = {
            "net_income_ttm": float(fundamentals.net_income_ttm),
            share_basis_name: float(share_basis_value),
        }
        if _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            operands,
        ):
            evidence.append(
                _calculation_evidence(
                    ticker=ticker,
                    as_of_date=as_of_date,
                    source_id=source_id,
                    metric_name="trailing_eps",
                    value=float(fundamentals.trailing_eps),
                    formula_id=(
                        f"net_income_ttm_divided_by_{share_basis_name}"
                    ),
                    operands=operands,
                    unit=f"{currency}_per_share",
                    period=f"TTM through {as_of_date}",
                    date=as_of_date,
                    evidence_items=[*runtime_items, *evidence],
                )
            )
    operands = {}
    if _division_matches(
        value=fundamentals.sbc_to_revenue,
        numerator=fundamentals.sbc_ttm,
        denominator=fundamentals.revenue_ttm,
    ):
        operands = {
            "sbc_ttm": float(fundamentals.sbc_ttm),
            "revenue_ttm": float(fundamentals.revenue_ttm),
        }
        if not _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            operands,
        ):
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_SBC_TO_REVENUE_"
                    f"{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"sbc_to_revenue={fundamentals.sbc_to_revenue:g} was "
                    f"calculated from TTM values; operands={operands}."
                ),
                value=float(fundamentals.sbc_to_revenue),
                unit="fraction",
                period=fcf_period_text,
                date=fcf_period_end,
                supports_metrics=["sbc_to_revenue"],
                confidence="high",
                formula_id="sbc_ttm_divided_by_revenue_ttm",
                formula_operands=operands,
                normalized_value=float(fundamentals.sbc_to_revenue),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    operands,
                    fallback_source_id=source_id,
                ),
            )
        )
    operands = {}
    if (
        fundamentals.free_cash_flow_ttm is not None
        and fundamentals.operating_cash_flow_ttm is not None
        and fundamentals.capex_ttm is not None
    ):
        formula_id = str(
            fundamentals.free_cash_flow_formula or "cfo_minus_capex"
        )
        operands = {
            "operating_cash_flow_ttm": float(
                fundamentals.operating_cash_flow_ttm
            ),
            "capex_ttm": float(fundamentals.capex_ttm),
        }
        fcf_matches = (
            formula_id == "cfo_minus_capex"
            and math.isclose(
                float(fundamentals.free_cash_flow_ttm),
                float(fundamentals.operating_cash_flow_ttm)
                - abs(float(fundamentals.capex_ttm)),
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and _operands_have_exact_evidence(
                [*runtime_items, *evidence],
                operands,
            )
        )
        if not fcf_matches:
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_FREE_CASH_FLOW_TTM_"
                    f"{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"free_cash_flow_ttm={fundamentals.free_cash_flow_ttm:g} "
                    f"was derived with {formula_id}; operands={operands}."
                ),
                value=float(fundamentals.free_cash_flow_ttm),
                unit=currency,
                period=fcf_period_text,
                date=fcf_period_end,
                supports_metrics=["free_cash_flow_ttm", "free_cash_flow"],
                confidence="high",
                formula_id=formula_id,
                formula_operands=operands,
                normalized_value=float(fundamentals.free_cash_flow_ttm),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    operands,
                    fallback_source_id=source_id,
                ),
            )
        )
    operands = {}
    if (
        fundamentals.shareholder_distributions_ttm is not None
        and fundamentals.buybacks is not None
        and fundamentals.dividends_paid is not None
        and distribution_period is not None
    ):
        operands = {
            "buybacks": float(fundamentals.buybacks),
            "dividends_paid": float(fundamentals.dividends_paid),
        }
        if not (
            math.isclose(
                float(fundamentals.shareholder_distributions_ttm),
                sum(operands.values()),
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and _operands_have_exact_evidence(
                [*runtime_items, *evidence],
                operands,
            )
        ):
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_"
                    f"SHAREHOLDER_DISTRIBUTIONS_TTM_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    "shareholder_distributions_ttm="
                    f"{fundamentals.shareholder_distributions_ttm:g} was "
                    "derived as buybacks plus dividends_paid."
                ),
                value=float(fundamentals.shareholder_distributions_ttm),
                unit=currency,
                period=distribution_period_text,
                date=distribution_period_end,
                supports_metrics=["shareholder_distributions_ttm"],
                confidence="high",
                formula_id="buybacks_ttm_plus_dividends_paid_ttm",
                formula_operands=operands,
                normalized_value=float(
                    fundamentals.shareholder_distributions_ttm
                ),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    operands,
                    fallback_source_id=source_id,
                ),
            )
        )
    operands = {}
    if (
        fundamentals.shareholder_distributions_minus_fcf_ttm is not None
        and fundamentals.shareholder_distributions_ttm is not None
        and fundamentals.free_cash_flow_ttm is not None
        and distribution_period is not None
        and distribution_period == fcf_period
    ):
        operands = {
            "shareholder_distributions_ttm": float(
                fundamentals.shareholder_distributions_ttm
            ),
            "free_cash_flow_ttm": float(fundamentals.free_cash_flow_ttm),
        }
        if not (
            math.isclose(
                float(
                    fundamentals.shareholder_distributions_minus_fcf_ttm
                ),
                operands["shareholder_distributions_ttm"]
                - operands["free_cash_flow_ttm"],
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and _operands_have_exact_evidence(
                [*runtime_items, *evidence],
                operands,
            )
        ):
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_"
                    f"SHAREHOLDER_DISTRIBUTIONS_MINUS_FCF_TTM_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    "shareholder_distributions_minus_fcf_ttm="
                    f"{fundamentals.shareholder_distributions_minus_fcf_ttm:g} "
                    "was derived as shareholder distributions minus FCF."
                ),
                value=float(
                    fundamentals.shareholder_distributions_minus_fcf_ttm
                ),
                unit=currency,
                period=distribution_period_text,
                date=distribution_period_end,
                supports_metrics=[
                    "shareholder_distributions_minus_fcf_ttm"
                ],
                confidence="high",
                formula_id=(
                    "shareholder_distributions_ttm_minus_free_cash_flow_ttm"
                ),
                formula_operands=operands,
                normalized_value=float(
                    fundamentals.shareholder_distributions_minus_fcf_ttm
                ),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    operands,
                    fallback_source_id=source_id,
                ),
            )
        )
    derived_ratios = (
        (
            "operating_margin_ttm",
            fundamentals.operating_margin_ttm,
            fundamentals.operating_income_ttm,
            "operating_income_ttm",
            fundamentals.revenue_ttm,
            "revenue_ttm",
            "operating_income_ttm_divided_by_revenue_ttm",
            "fraction",
            f"TTM through {as_of_date}",
        ),
        (
            "net_margin_ttm",
            fundamentals.net_margin_ttm,
            fundamentals.net_income_ttm,
            "net_income_ttm",
            fundamentals.revenue_ttm,
            "revenue_ttm",
            "net_income_ttm_divided_by_revenue_ttm",
            "fraction",
            f"TTM through {as_of_date}",
        ),
        (
            "fcf_margin_ttm",
            fundamentals.fcf_margin_ttm,
            fundamentals.free_cash_flow_ttm,
            "free_cash_flow_ttm",
            fundamentals.revenue_ttm,
            "revenue_ttm",
            "free_cash_flow_ttm_divided_by_revenue_ttm",
            "fraction",
            f"TTM through {as_of_date}",
        ),
        (
            "sbc_to_fcf",
            fundamentals.sbc_to_fcf,
            fundamentals.sbc_ttm,
            "sbc_ttm",
            fundamentals.free_cash_flow_ttm,
            "free_cash_flow_ttm",
            "sbc_ttm_divided_by_free_cash_flow_ttm",
            "fraction",
            f"TTM through {as_of_date}",
        ),
        (
            "current_ratio",
            fundamentals.current_ratio,
            fundamentals.current_assets,
            "current_assets",
            fundamentals.current_liabilities,
            "current_liabilities",
            "current_assets_divided_by_current_liabilities",
            "multiple",
            f"as of {as_of_date}",
        ),
    )
    for (
        metric_name,
        value,
        numerator,
        numerator_name,
        denominator,
        denominator_name,
        formula_id,
        unit,
        period,
    ) in derived_ratios:
        if not _division_matches(
            value=value,
            numerator=numerator,
            denominator=denominator,
        ):
            continue
        operands = {
            numerator_name: float(numerator),
            denominator_name: float(denominator),
        }
        if not _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            operands,
        ):
            continue
        evidence.append(
            _calculation_evidence(
                ticker=ticker,
                as_of_date=as_of_date,
                source_id=source_id,
                metric_name=metric_name,
                value=float(value),
                formula_id=formula_id,
                operands=operands,
                unit=unit,
                period=period,
                date=as_of_date,
                evidence_items=[*runtime_items, *evidence],
            )
        )
    operands = {}
    if _division_matches(
        value=fundamentals.free_cash_flow_conversion_ttm,
        numerator=fundamentals.free_cash_flow_ttm,
        denominator=fundamentals.net_income_ttm,
    ):
        operands = {
            "free_cash_flow_ttm": float(fundamentals.free_cash_flow_ttm),
            "net_income_ttm": float(fundamentals.net_income_ttm),
        }
        if not _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            operands,
        ):
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_"
                    f"FREE_CASH_FLOW_CONVERSION_TTM_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    "free_cash_flow_conversion_ttm="
                    f"{fundamentals.free_cash_flow_conversion_ttm:g} was "
                    "derived as free_cash_flow_ttm / net_income_ttm."
                ),
                value=float(fundamentals.free_cash_flow_conversion_ttm),
                unit="percent",
                period=f"TTM through {as_of_date}",
                date=as_of_date,
                supports_metrics=["free_cash_flow_conversion_ttm"],
                confidence="high",
                formula_id="fcf_divided_by_net_income",
                formula_operands=operands,
                normalized_value=float(
                    fundamentals.free_cash_flow_conversion_ttm
                ),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    operands,
                    fallback_source_id=source_id,
                ),
            )
        )
    coverage_metrics = (
        (
            "operating_income_interest_coverage_ttm",
            fundamentals.operating_income_interest_coverage_ttm,
            fundamentals.operating_income_ttm,
            "operating_income_ttm",
            "operating_income_divided_by_interest_expense",
        ),
        (
            "free_cash_flow_interest_coverage_ttm",
            fundamentals.free_cash_flow_interest_coverage_ttm,
            fundamentals.free_cash_flow_ttm,
            "free_cash_flow_ttm",
            "free_cash_flow_divided_by_interest_expense",
        ),
    )
    for metric_name, value, numerator, numerator_name, formula_id in coverage_metrics:
        if not _division_matches(
            value=value,
            numerator=numerator,
            denominator=fundamentals.interest_expense_ttm,
        ):
            continue
        operands = {
            numerator_name: float(numerator),
            "interest_expense_ttm": float(fundamentals.interest_expense_ttm),
        }
        if not _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            operands,
        ):
            continue
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_"
                    f"{_safe_metric_id(metric_name)}_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="financial_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"{metric_name}={value:g} was derived with {formula_id}; "
                    f"operands={operands}."
                ),
                value=float(value),
                unit="multiple",
                period=f"TTM through {as_of_date}",
                date=as_of_date,
                supports_metrics=[metric_name],
                confidence="high",
                formula_id=formula_id,
                formula_operands=operands,
                normalized_value=float(value),
                source_lineage=_operand_source_lineage(
                    [*runtime_items, *evidence],
                    operands,
                    fallback_source_id=source_id,
                ),
            )
        )
    valuation = metrics_packet.valuation
    technical = metrics_packet.technical
    operands = {}
    if (
        valuation.market_cap is not None
        and fundamentals.listed_share_count is not None
    ):
        operands = {
            "close": float(technical.close),
            "listed_share_count": float(fundamentals.listed_share_count),
        }
        market_cap_matches = (
            math.isclose(
                float(valuation.market_cap),
                operands["close"] * operands["listed_share_count"],
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and _operands_have_exact_evidence(
                [*runtime_items, *evidence],
                operands,
            )
        )
        if not market_cap_matches:
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_MARKET_CAP_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="valuation_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"market_cap={valuation.market_cap:g} was calculated from "
                    f"the as-of close and point-in-time outstanding shares."
                ),
                value=float(valuation.market_cap),
                unit=currency,
                period=f"as of {as_of_date}",
                date=as_of_date,
                supports_metrics=["market_cap", "listed_share_count"],
                confidence="high",
                formula_id="close_times_point_in_time_shares",
                formula_operands=operands,
                normalized_value=float(valuation.market_cap),
                source_lineage=list(
                    dict.fromkeys(
                        [
                            *valuation_lineage,
                            *_operand_source_lineage(
                                [*runtime_items, *evidence],
                                operands,
                                fallback_source_id=source_id,
                            ),
                        ]
                    )
                ),
            )
        )
    operands = {}
    if (
        valuation.enterprise_value is not None
        and valuation.market_cap is not None
        and fundamentals.total_debt is not None
        and fundamentals.cash_and_equivalents is not None
    ):
        operands = {
            "market_cap": float(valuation.market_cap),
            "total_debt": float(fundamentals.total_debt),
            "cash_and_equivalents": float(
                fundamentals.cash_and_equivalents
            ),
        }
        if fundamentals.short_term_investments is not None:
            operands["short_term_investments"] = float(
                fundamentals.short_term_investments
            )
        if fundamentals.marketable_securities is not None:
            operands["marketable_securities"] = float(
                fundamentals.marketable_securities
            )
        expected_enterprise_value = (
            operands["market_cap"]
            + operands["total_debt"]
            - operands["cash_and_equivalents"]
            - operands.get("short_term_investments", 0.0)
            - operands.get("marketable_securities", 0.0)
        )
        if not (
            math.isclose(
                float(valuation.enterprise_value),
                expected_enterprise_value,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and _operands_have_exact_evidence(
                [*runtime_items, *evidence],
                operands,
            )
        ):
            operands = {}
    if operands:
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_ENTERPRISE_VALUE_"
                    f"{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="valuation_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"enterprise_value={valuation.enterprise_value:g} was "
                    "calculated from market cap, debt and liquid assets."
                ),
                value=float(valuation.enterprise_value),
                unit=currency,
                period=f"as of {as_of_date}",
                date=as_of_date,
                supports_metrics=["enterprise_value"],
                confidence="high",
                formula_id="market_cap_plus_debt_minus_liquid_assets",
                formula_operands=operands,
                normalized_value=float(valuation.enterprise_value),
                source_lineage=list(
                    dict.fromkeys(
                        [
                            *valuation_lineage,
                            *_operand_source_lineage(
                                [*runtime_items, *evidence],
                                operands,
                                fallback_source_id=source_id,
                            ),
                        ]
                    )
                ),
            )
        )
    ratio_metrics = (
        (
            "ev_to_sales",
            valuation.ev_to_sales,
            valuation.enterprise_value,
            "enterprise_value",
            fundamentals.revenue_ttm,
            "revenue_ttm",
            "enterprise_value_divided_by_revenue_ttm",
            "multiple",
        ),
        (
            "price_to_fcf",
            valuation.price_to_fcf,
            valuation.market_cap,
            "market_cap",
            fundamentals.free_cash_flow_ttm,
            "free_cash_flow_ttm",
            "market_cap_divided_by_free_cash_flow_ttm",
            "multiple",
        ),
        (
            "ev_to_ebit",
            valuation.ev_to_ebit,
            valuation.enterprise_value,
            "enterprise_value",
            fundamentals.operating_income_ttm,
            "operating_income_ttm",
            "enterprise_value_divided_by_operating_income_ttm",
            "multiple",
        ),
        (
            "ev_to_ebitda",
            valuation.ev_to_ebitda,
            valuation.enterprise_value,
            "enterprise_value",
            fundamentals.ebitda_ttm,
            "ebitda_ttm",
            "enterprise_value_divided_by_ebitda_ttm",
            "multiple",
        ),
        (
            "fcf_yield",
            valuation.fcf_yield,
            fundamentals.free_cash_flow_ttm,
            "free_cash_flow_ttm",
            valuation.market_cap,
            "market_cap",
            "free_cash_flow_ttm_divided_by_market_cap",
            "fraction",
        ),
        (
            "trailing_pe",
            valuation.trailing_pe,
            technical.close,
            "close",
            fundamentals.trailing_eps,
            "trailing_eps",
            "close_divided_by_trailing_eps",
            "multiple",
        ),
    )
    for (
        metric_name,
        value,
        numerator,
        numerator_name,
        denominator,
        denominator_name,
        formula_id,
        unit,
    ) in ratio_metrics:
        if not _division_matches(
            value=value,
            numerator=numerator,
            denominator=denominator,
        ):
            continue
        operands = {
            numerator_name: float(numerator),
            denominator_name: float(denominator),
        }
        if not _operands_have_exact_evidence(
            [*runtime_items, *evidence],
            operands,
        ):
            continue
        evidence.append(
            EvidenceItem(
                evidence_id=(
                    f"{ticker.upper()}_DETERMINISTIC_"
                    f"{_safe_metric_id(metric_name)}_{as_of_date}"
                ),
                ticker=ticker.upper(),
                claim_type="valuation_metric",
                source_id=source_id,
                source_type="deterministic_calculation",
                authority_rank=1,
                statement=(
                    f"{metric_name}={value:g} was calculated with "
                    f"{formula_id}; operands={operands}."
                ),
                value=float(value),
                unit=unit,
                period=f"as of {as_of_date}",
                date=as_of_date,
                supports_metrics=[metric_name],
                confidence="high",
                formula_id=formula_id,
                formula_operands=operands,
                normalized_value=float(value),
                source_lineage=list(
                    dict.fromkeys(
                        [
                            *valuation_lineage,
                            *_operand_source_lineage(
                                [*runtime_items, *evidence],
                                operands,
                                fallback_source_id=source_id,
                            ),
                        ]
                    )
                ),
            )
        )
    return evidence


def _calculation_evidence(
    *,
    ticker: str,
    as_of_date: str,
    source_id: str,
    metric_name: str,
    value: float,
    formula_id: str,
    operands: dict[str, float],
    unit: str,
    period: str,
    date: str,
    evidence_items: Iterable[EvidenceItem],
    claim_type: str = "financial_metric",
    source_lineage: Optional[list[str]] = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=(
            f"{ticker.upper()}_DETERMINISTIC_"
            f"{_safe_metric_id(metric_name)}_{as_of_date}"
        ),
        ticker=ticker.upper(),
        claim_type=claim_type,
        source_id=source_id,
        source_type="deterministic_calculation",
        authority_rank=1,
        statement=(
            f"{metric_name}={value:g} was derived with {formula_id}; "
            f"operands={operands}."
        ),
        value=float(value),
        unit=unit,
        period=period,
        date=date,
        supports_metrics=[metric_name],
        confidence="high",
        formula_id=formula_id,
        formula_operands=operands,
        normalized_value=float(value),
        source_lineage=(
            list(dict.fromkeys(source_lineage))
            if source_lineage is not None
            else _operand_source_lineage(
                evidence_items,
                operands,
                fallback_source_id=source_id,
            )
        ),
    )


def _division_matches(
    *,
    value: Optional[float],
    numerator: Optional[float],
    denominator: Optional[float],
) -> bool:
    if value is None or numerator is None or denominator in (None, 0):
        return False
    return math.isclose(
        float(value),
        float(numerator) / float(denominator),
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def _bridge_value_matches(
    *,
    value: float,
    formula_id: str,
    operands: Mapping[str, float],
) -> bool:
    expected: Optional[float] = None
    if formula_id == "sum_four_contiguous_quarters" and operands:
        expected = sum(float(item) for item in operands.values())
    elif formula_id == "annual_minus_prior_interim_plus_current_interim":
        if {
            "annual",
            "prior_interim",
            "current_interim",
        }.issubset(operands):
            expected = (
                float(operands["annual"])
                - float(operands["prior_interim"])
                + float(operands["current_interim"])
            )
    elif formula_id == "annual_minus_q1_q2_q3_plus_post_annual_quarters":
        quarter_values = [
            float(item)
            for key, item in operands.items()
            if key not in {"annual", "derived_q4"}
        ]
        if "annual" in operands and "derived_q4" in operands:
            annual = float(operands["annual"])
            derived_q4 = float(operands["derived_q4"])
            if math.isclose(
                derived_q4,
                annual - sum(quarter_values),
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                expected = annual
    return (
        expected is not None
        and math.isclose(
            float(value),
            expected,
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
    )


def _bridge_operands_have_exact_evidence(
    evidence_items: Iterable[EvidenceItem],
    *,
    metric_name: str,
    formula_id: str,
    operands: Mapping[str, float],
    source_ids: Iterable[str],
) -> bool:
    items = list(evidence_items)
    resolved_source_ids = set(
        _canonical_lineage_source_ids(items, source_ids)
    )
    required_values = [
        float(value)
        for key, value in operands.items()
        if not (
            formula_id
            == "annual_minus_q1_q2_q3_plus_post_annual_quarters"
            and key == "derived_q4"
        )
    ]
    if not resolved_source_ids or not required_values:
        return False
    return all(
        any(
            (
                item.source_id in resolved_source_ids
                or bool(
                    resolved_source_ids.intersection(
                        _canonical_lineage_source_ids(
                            items,
                            item.source_lineage,
                        )
                    )
                )
            )
            and metric_name in item.supports_metrics
            and item.value is not None
            and math.isclose(
                float(item.value),
                operand_value,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and (
                item.raw_value is not None
                or item.normalized_value is not None
                or (item.date and item.period)
            )
            for item in items
        )
        for operand_value in required_values
    )


def _operands_have_exact_evidence(
    evidence_items: Iterable[EvidenceItem],
    operands: Mapping[str, float],
) -> bool:
    items = list(evidence_items)
    return all(
        any(
            metric_name in item.supports_metrics
            and item.value is not None
            and math.isclose(
                float(item.value),
                float(value),
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            and (
                (item.formula_id and item.formula_operands)
                or item.raw_value is not None
                or item.normalized_value is not None
                or (item.date and item.period)
            )
            for item in items
        )
        for metric_name, value in operands.items()
    )


def _operand_source_lineage(
    evidence_items: Iterable[EvidenceItem],
    operands: dict[str, float],
    *,
    fallback_source_id: str,
) -> list[str]:
    items = list(evidence_items)
    source_ids: list[str] = []
    for metric_name, value in operands.items():
        matches = [
            item
            for item in items
            if metric_name in item.supports_metrics
            and item.value is not None
            and abs(float(item.value) - value)
            <= max(1e-9, abs(value) * 1e-9)
            and (
                (item.formula_id and item.formula_operands)
                or item.raw_value is not None
                or item.normalized_value is not None
                or (item.date and item.period)
            )
        ]
        if not matches:
            continue
        best_match = sorted(
            matches,
            key=lambda item: (
                0 if item.formula_id and item.formula_operands else 1,
                0 if item.source_lineage else 1,
                0 if item.normalized_value is not None else 1,
                item.authority_rank,
                item.evidence_id,
            ),
        )[0]
        source_ids.extend(
            _canonical_lineage_source_ids(
                items,
                [best_match.source_id, *best_match.source_lineage],
            )
        )
    return list(dict.fromkeys(source_ids)) or [fallback_source_id]


def _common_bridge_period(
    bridges: Mapping[str, object],
    *metric_names: str,
) -> Optional[tuple[str, str]]:
    periods: set[tuple[str, str]] = set()
    for metric_name in metric_names:
        bridge = bridges.get(metric_name)
        if not isinstance(bridge, Mapping):
            return None
        period_start = str(bridge.get("period_start") or "").strip()
        period_end = str(bridge.get("period_end") or "").strip()
        if not period_start or not period_end:
            return None
        periods.add((period_start, period_end))
    return next(iter(periods)) if len(periods) == 1 else None


def _canonical_lineage_source_ids(
    evidence_items: Iterable[EvidenceItem],
    lineage: Iterable[str],
) -> list[str]:
    known_source_ids = {
        item.source_id
        for item in evidence_items
        if item.source_id
    }
    resolved: list[str] = []
    for raw_source_id in lineage:
        source_id = str(raw_source_id or "").strip()
        if not source_id:
            continue
        if source_id in known_source_ids:
            resolved.append(source_id)
            continue
        suffix = source_id.removeprefix("SEC_")
        suffix_matches = sorted(
            candidate
            for candidate in known_source_ids
            if suffix and candidate.endswith(suffix)
        )
        resolved.append(
            suffix_matches[0]
            if len(suffix_matches) == 1
            else source_id
        )
    return list(dict.fromkeys(resolved))


def save_evidence_ledger(ledger: EvidenceLedger, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = ledger.model_dump(mode="json") if hasattr(ledger, "model_dump") else ledger.dict()
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_evidence_ledger(path: Union[str, Path]) -> EvidenceLedger:
    return EvidenceLedger(**json.loads(Path(path).read_text(encoding="utf-8")))


def _expand_used_for(used_for: list[str]) -> list[str]:
    metrics: list[str] = []
    for raw_metric in used_for:
        metric = raw_metric.strip().lower()
        metrics.extend(sorted(_metric_aliases(metric)))
    return list(dict.fromkeys(metrics))


def _metric_aliases(metric_name: str) -> set[str]:
    normalized = metric_name.strip().lower()
    if normalized in {
        "company_guidance_eps",
        "consensus_forward_eps",
        "sbc_to_revenue",
        "sbc_to_fcf",
        "sbc_to_non_gaap_operating_income",
    }:
        return {normalized}
    if normalized == "ev_to_sales":
        return {"ev_to_sales", "revenue_ttm", "close", "price_data"}
    if normalized == "price_to_fcf":
        return {"price_to_fcf", "free_cash_flow_ttm", "close", "price_data"}
    if normalized in {"sma_50", "sma_200", "rsi_14"}:
        return {normalized, "technical_indicators"}
    aliases = {normalized}
    alias_map = {
        "revenue": {"revenue", "revenue_ttm", "sales", "umsatz"},
        "free_cash_flow": {"fcf", "free_cash_flow", "free_cash_flow_ttm", "cashflow", "free_cashflow"},
        "fcf": {"fcf", "free_cash_flow", "free_cash_flow_ttm", "cashflow", "free_cashflow"},
        "operating_income": {"operating_income", "operating_income_ttm"},
        "net_income": {"net_income", "net_income_ttm"},
        "eps": {"eps", "eps_diluted"},
        "forward_eps": {"forward_eps"},
        "guidance": {"guidance", "company_guidance_eps"},
        "consensus": {"consensus", "consensus_forward_eps", "forward_eps"},
        "sbc": {"sbc", "sbc_ttm", "sbc_to_revenue", "sbc_to_fcf"},
        "cash": {"cash", "cash_and_equivalents", "cash_and_investments", "net_cash"},
        "debt": {"debt", "total_debt", "net_debt"},
        "price": {"price", "close", "price_basis", "price_data"},
        "ohlcv": {"ohlcv", "price", "close", "price_data"},
    }
    for key, values in alias_map.items():
        if normalized == key or normalized in values:
            aliases.update(values)
    return aliases


def _metric_value(metrics_packet: Optional[MetricsPacket], metric_name: str) -> Optional[float]:
    if metrics_packet is None:
        return None
    for section_name in ["fundamentals", "technical", "valuation"]:
        section = getattr(metrics_packet, section_name)
        if hasattr(section, metric_name):
            value = getattr(section, metric_name)
            return float(value) if isinstance(value, (int, float)) else None
    return None


def _claim_type_for_metric(metric_name: str, source_type: str):
    if metric_name in {"company_guidance_eps", "guidance"}:
        return "guidance"
    if (
        metric_name in {"close", "price", "price_data", "price_basis"}
        or source_type in OHLCV_AUTHORITY_SOURCE_TYPES
    ):
        return "price_data"
    if metric_name.startswith("sma") or metric_name.startswith("ema") or metric_name in {"rsi_14", "macd_histogram"}:
        return "technical_metric"
    if metric_name in {"forward_pe_consensus", "price_to_fcf", "ev_to_sales", "peg_ratio"}:
        return "valuation_metric"
    if source_type in {"reuters", "barrons", "wsj", "marketwatch", "official_press_release"}:
        return "news"
    return "financial_metric"


def unit_for_metric(
    metric_name: str,
    *,
    currency: str = "USD",
) -> Optional[str]:
    metric_name = str(metric_name or "").strip().lower()
    currency = str(currency or "USD").strip().upper()
    if "margin" in metric_name or metric_name.startswith("sbc_to"):
        return "percent"
    if metric_name == "fcf_yield":
        return "fraction"
    if "eps" in metric_name:
        return f"{currency}_per_share"
    if metric_name in {"close", "price", "price_basis", "price_data"} or metric_name.startswith(
        ("sma_", "ema_", "bollinger_")
    ) or metric_name == "atr_14":
        return currency
    if metric_name in {
        "avg_volume_20",
        "volume",
        "listed_share_count",
        "treasury_share_count",
        "economic_share_count",
        "diluted_share_count",
    }:
        return "shares"
    if metric_name == "rsi_14":
        return "index"
    if metric_name in {
        "current_ratio",
        "debt_to_equity",
        "ev_to_ebit",
        "ev_to_ebitda",
        "ev_to_sales",
        "free_cash_flow_conversion_ttm",
        "free_cash_flow_interest_coverage_ttm",
        "forward_pe_consensus",
        "operating_income_interest_coverage_ttm",
        "peg_ratio",
        "price_to_fcf",
        "trailing_pe",
    }:
        return "multiple"
    if metric_name in {
        "cash",
        "revenue",
        "revenue_ttm",
        "gross_profit",
        "gross_profit_ttm",
        "operating_income",
        "operating_income_ttm",
        "ebitda",
        "ebitda_ttm",
        "net_income",
        "net_income_ttm",
        "operating_cash_flow",
        "operating_cash_flow_ttm",
        "capex",
        "capex_ttm",
        "free_cash_flow",
        "free_cash_flow_ttm",
        "sbc",
        "sbc_ttm",
        "buybacks",
        "dividends_paid",
        "depreciation_and_amortization",
        "depreciation_and_amortization_ttm",
        "interest_expense",
        "interest_expense_ttm",
        "shareholder_distributions_ttm",
        "shareholder_distributions_minus_fcf_ttm",
        "cash_and_equivalents",
        "cash_and_investments",
        "current_assets",
        "current_liabilities",
        "debt",
        "debt_current",
        "debt_noncurrent",
        "enterprise_value",
        "equity",
        "lease_liability_current",
        "lease_liability_noncurrent",
        "lease_liabilities_current",
        "lease_liabilities_long_term",
        "long_term_debt",
        "market_cap",
        "marketable_securities",
        "short_term_debt",
        "short_term_investments",
        "total_lease_liabilities",
        "total_debt",
        "total_assets",
        "treasury_stock_value",
        "net_cash",
    }:
        return currency
    return None


def _safe_metric_id(metric_name: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in metric_name.upper()).strip("_")
