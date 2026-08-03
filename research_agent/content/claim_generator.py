from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional

from research_agent.decision.decision_packet import DecisionPacket
from research_agent.decision.signal_scores import classify_technical_trend
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger, unit_for_metric
from research_agent.reconciliation.canonical_financials import CanonicalFinancials
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket, MaterialNewsEvent
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.research_core.calculations.fundamentals import (
    current_operating_profit_decline_metrics,
    current_profit_growth_divergence_metrics,
)


_BUSINESS_CONTEXT_SECTIONS = {
    "Business & Segment Context",
    "Business Model Reality",
    "Revenue Scale and Backlog",
    "Contract / Backlog Materiality",
    "Segment Mix",
    "Execution Milestones",
}
_BUSINESS_CONTEXT_EVENT_TYPES = {"business_context", "business_model"}
_CATALYST_EVENT_TYPES = {
    "acquisition",
    "divestiture",
    "leadership",
    "partnership",
    "product_strategy",
    "strategy",
}


def generate_research_claims(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    evidence_ledger: EvidenceLedger,
    decision_packet: DecisionPacket,
    validation_report: Optional[ValidationReport] = None,
    canonical_financials: Optional[CanonicalFinancials] = None,
) -> list[ResearchClaim]:
    """Create deterministic evidence-grounded analyst claims.

    This layer intentionally does not calculate new metrics. It chooses from
    validated packet fields and maps every emitted claim to existing evidence.
    Claims that cannot be evidence-mapped are dropped before reporting.
    """

    builder = _ClaimBuilder(
        data_packet=data_packet,
        metrics_packet=metrics_packet,
        evidence_ledger=evidence_ledger,
        decision_packet=decision_packet,
        validation_report=validation_report,
        canonical_financials=canonical_financials,
    )
    return [claim for claim in builder.build_candidates() if claim.evidence_ids]


def claim_quality_metrics(claims: Iterable[ResearchClaim]) -> dict[str, float | int]:
    claim_list = list(claims)
    total = len(claim_list)
    mapped = sum(1 for claim in claim_list if claim.evidence_ids)
    hard = [
        claim for claim in claim_list
        if (claim.claim_type or "") in {"financial_metric", "valuation_metric", "technical_metric", "price_data"}
    ]
    hard_mapped = sum(1 for claim in hard if claim.evidence_ids)
    data_limitations = [claim for claim in claim_list if _is_data_limitation_claim(claim)]
    substantive = [claim for claim in claim_list if _is_substantive_claim(claim)]
    generic = [claim for claim in claim_list if _is_generic_meta_claim(claim)]
    current_period_kpis = [claim for claim in claim_list if _is_current_period_kpi_claim(claim)]
    current_period_metrics = {
        metric
        for claim in current_period_kpis
        for metric in claim.metric_refs
    }
    company_specific = [
        claim
        for claim in claim_list
        if _is_company_specific_claim(claim)
    ]
    valuation_specific = [
        claim for claim in claim_list
        if not _is_generic_meta_claim(claim)
        and (claim.section or "") == "Valuation / Multiples"
        and _has_validated_number(claim)
    ]
    technical_specific = [
        claim for claim in claim_list
        if not _is_generic_meta_claim(claim)
        and (claim.section or "") == "Technical Setup"
        and _has_validated_number(claim)
    ]
    rating_rationale = [
        claim for claim in claim_list
        if (claim.section or "") == "Final Rating & Action Plan" and _has_rating_implication(claim)
    ]
    risk_specific = [
        claim
        for claim in claim_list
        if (claim.section or "") == "Key Risks"
        and bool(claim.evidence_ids)
        and (
            (claim.claim_type or "") == "risk"
            or bool(claim.metric_refs or claim.evidence_metrics)
        )
        and not _is_generic_meta_claim(claim)
        and not _is_data_limitation_claim(claim)
    ]
    generic_count = len(generic)
    ticker_kpi_count = sum(1 for claim in claim_list if _has_ticker_specific_kpi(claim))
    substantive_ratio = (len(substantive) / total) if total else 0.0
    return {
        "analyst_claim_count": total,
        "evidence_mapped_claim_ratio": (mapped / total) if total else 0.0,
        "hard_claim_evidence_ratio": (hard_mapped / len(hard)) if hard else 1.0,
        "substantive_analyst_claim_count": len(substantive),
        "substantive_claim_count": len(substantive),
        "substantive_claim_ratio": substantive_ratio,
        "generic_claim_count": generic_count,
        "data_limitation_claim_count": len(data_limitations),
        "current_period_kpi_claim_count": len(current_period_kpis),
        "current_period_kpi_metric_count": len(current_period_metrics),
        "ticker_specific_kpi_claim_count": ticker_kpi_count,
        "final_rating_rationale_quality": _final_rating_rationale_quality(claim_list),
        "mechanical_rating_language_count": sum(1 for claim in claim_list if _has_mechanical_rating_language(claim)),
        "generic_claim_ratio": (generic_count / total) if total else 0.0,
        "company_specific_claim_count": len(company_specific),
        "valuation_specific_claim_count": len(valuation_specific),
        "technical_specific_claim_count": len(technical_specific),
        "rating_rationale_claim_count": len(rating_rationale),
        "risk_specific_claim_count": len(risk_specific),
    }


def claim_coverage_gaps(metrics: Mapping[str, object]) -> list[str]:
    """Return missing content dimensions without rewarding padded claim totals."""

    total = int(metrics.get("analyst_claim_count") or 0)
    gaps: list[str] = []
    if total == 0:
        gaps.append("no_evidence_mapped_claims")
    if float(metrics.get("evidence_mapped_claim_ratio") or 0.0) < 1.0:
        gaps.append("incomplete_claim_evidence")
    if float(metrics.get("hard_claim_evidence_ratio") or 0.0) < 1.0:
        gaps.append("incomplete_hard_claim_evidence")
    if int(metrics.get("current_period_kpi_metric_count") or 0) < 3:
        gaps.append("missing_current_period_context")
    if int(metrics.get("company_specific_claim_count") or 0) < 1:
        gaps.append("missing_company_specific_analysis")
    if int(metrics.get("valuation_specific_claim_count") or 0) < 1:
        gaps.append("missing_valuation_analysis")
    if int(metrics.get("technical_specific_claim_count") or 0) < 1:
        gaps.append("missing_technical_analysis")
    if int(metrics.get("rating_rationale_claim_count") or 0) < 1:
        gaps.append("missing_rating_rationale")
    if (
        "risk_specific_claim_count" in metrics
        and int(metrics.get("risk_specific_claim_count") or 0) < 1
    ):
        gaps.append("missing_risk_analysis")
    if int(metrics.get("final_rating_rationale_quality") or 0) < 50:
        gaps.append("weak_rating_rationale")
    if float(metrics.get("generic_claim_ratio") or 0.0) > 0.50:
        gaps.append("excessive_generic_content")
    if total and (
        int(metrics.get("data_limitation_claim_count") or 0) / total > 0.25
    ):
        gaps.append("excessive_data_limitation_content")
    return gaps


class _ClaimBuilder:
    def __init__(
        self,
        data_packet: DataPacket,
        metrics_packet: MetricsPacket,
        evidence_ledger: EvidenceLedger,
        decision_packet: DecisionPacket,
        validation_report: Optional[ValidationReport],
        canonical_financials: Optional[CanonicalFinancials],
    ) -> None:
        self.data_packet = data_packet
        self.metrics = metrics_packet
        self.ledger = evidence_ledger
        self.decision = decision_packet
        self.validation = validation_report
        self.canonical = canonical_financials
        self.claims: list[ResearchClaim] = []
        self.counter = 0
        self.evidence_id_counts: dict[str, int] = {}
        for item in evidence_ledger.evidence_items:
            self.evidence_id_counts[item.evidence_id] = (
                self.evidence_id_counts.get(item.evidence_id, 0) + 1
            )

    def build_candidates(self) -> list[ResearchClaim]:
        ticker = self.data_packet.ticker.upper()
        preferred = self.decision.rating_permission.preferred_rating.value
        core_rating_metrics = _core_rating_metric_refs(self.metrics)

        self.add(
            "Executive Summary",
            "summary",
            "rating",
            (
                f"{ticker} enters the report at a frozen close of "
                f"{_money(self.metrics.technical.close, self.data_packet.price_basis.currency)} "
                f"with a {preferred} stance. The available evidence anchors are "
                f"{_core_rating_evidence_text(self.metrics, self.data_packet.price_basis.currency)}; "
                f"the technical evidence indicates {_technical_interpretation(self.metrics)}. "
                f"Valuation status is {self.decision.signal_scores.valuation_status}."
            ),
            core_rating_metrics,
            "high",
            "high",
            implication=f"The action language should stay consistent with the {preferred} stance.",
        )

        current_claim_specs = _current_period_claim_specs(
            ticker,
            self.metrics,
            self.canonical,
            currency=self.data_packet.price_basis.currency,
        )
        for current_claim in current_claim_specs:
            self.add(
                current_claim["section"],
                current_claim["kind"],
                current_claim["evidence_type"],
                current_claim["text"],
                current_claim["metrics"],
                "high",
                "high",
                counterargument=current_claim.get("counterargument"),
                implication=current_claim.get("implication"),
            )

        for event in self.data_packet.news_coverage.material_events:
            if event.event_type in _BUSINESS_CONTEXT_EVENT_TYPES:
                self.add_event(event, section="Business & Segment Context")
            elif event.event_type in _CATALYST_EVENT_TYPES:
                self.add_event(event, section="Catalysts & Triggers")

        for index, risk_evidence in enumerate(
            self._selected_risk_evidence(limit=4)
        ):
            self.add_risk(risk_evidence, explain_disclosure=index == 0)

        fcf_claim_metrics = ["free_cash_flow_ttm"]
        if _negative_fcf_is_capex_funding_gap(self.metrics):
            fcf_claim_metrics.extend(
                ["capex_ttm", "operating_cash_flow_ttm"]
            )
        self.add(
            "Fundamental Analysis",
            "fundamental",
            "financial_metric",
            _fundamental_fcf_claim_text(
                ticker,
                self.metrics,
                self.data_packet.price_basis.currency,
            ),
            fcf_claim_metrics,
            "high",
            "high",
            counterargument="FCF may be company-defined or period-sensitive and can require reconciliation review.",
            implication=(
                "Treat FCF as a rating input only after its source, period and "
                "formula have passed validation."
            ),
        )
        if (
            self.metrics.fundamentals.shareholder_distributions_ttm
            is not None
            and (
                self.metrics.fundamentals
                .shareholder_distributions_minus_fcf_ttm
                is not None
            )
        ):
            distribution_difference = (
                self.metrics.fundamentals.shareholder_distributions_minus_fcf_ttm
            )
            if distribution_difference > 0:
                distribution_comparison = (
                    "shareholder distributions exceed FCF; the signed "
                    "distributions-minus-FCF comparison is "
                    f"{self._money(distribution_difference)}."
                )
                distribution_counterargument = (
                    "The excess does not by itself prove that distributions were "
                    "debt-funded or cash-funded."
                )
            elif distribution_difference < 0:
                distribution_comparison = (
                    "FCF exceeds shareholder distributions; the signed "
                    "distributions-minus-FCF comparison is "
                    f"-{self._money(abs(distribution_difference))}."
                )
                distribution_counterargument = (
                    "This period surplus does not prove that every distribution "
                    "was funded from FCF or that the relationship is durable."
                )
            else:
                distribution_comparison = (
                    "shareholder distributions equal FCF; the signed "
                    "distributions-minus-FCF comparison is zero."
                )
                distribution_counterargument = (
                    "Equality in one period does not establish a durable funding "
                    "relationship."
                )
            self.add(
                "Fundamental Analysis",
                "fundamental",
                "financial_metric",
                (
                    "TTM shareholder distributions are "
                    f"{self._money(self.metrics.fundamentals.shareholder_distributions_ttm)}; "
                    f"{distribution_comparison} "
                    "This is an arithmetic comparison and does not identify a "
                    "funding source."
                ),
                [
                    "shareholder_distributions_ttm",
                    "shareholder_distributions_minus_fcf_ttm",
                ],
                "high",
                "high",
                counterargument=distribution_counterargument,
                implication=(
                    "Capital-return sustainability should be discussed without "
                    "inventing a financing bridge."
                ),
            )
        self.add(
            "Fundamental Analysis",
            "fundamental",
            "financial_metric",
            (
                "SBC/Revenue is "
                f"{_pct(self.metrics.fundamentals.sbc_to_revenue)}. Without a "
                "share-count trend and a sector or lifecycle benchmark, this "
                "is a dilution input rather than evidence that SBC is high or low."
            ),
            ["sbc_to_revenue"],
            "medium",
            "medium",
            counterargument="Sector and lifecycle matter, but persistent dilution can still reduce equity quality.",
            implication="Treat SBC as a risk modifier rather than an automatic rating override.",
        )
        net_cash = self.metrics.fundamentals.net_cash
        total_debt = self.metrics.fundamentals.total_debt
        balance_sheet_metrics = [
            metric
            for metric, value in (
                ("net_cash", net_cash),
                ("total_debt", total_debt),
            )
            if value is not None
        ]
        if net_cash is None:
            balance_sheet_claim = (
                f"Total debt is {self._money(total_debt)}, while the signed net "
                "cash or net debt position is unavailable."
            )
        elif net_cash < 0:
            debt_context = (
                f"total debt of {self._money(total_debt)}"
                if total_debt is not None
                else "an unavailable total-debt figure"
            )
            balance_sheet_claim = (
                "The balance-sheet position includes net debt of "
                f"{self._money(abs(net_cash))} and {debt_context}. "
                "This is a leverage input, not "
                "evidence of financial flexibility."
            )
        else:
            debt_context = (
                f"total debt of {self._money(total_debt)}"
                if total_debt is not None
                else "an unavailable total-debt figure"
            )
            balance_sheet_claim = (
                "The balance-sheet position includes net cash of "
                f"{self._money(net_cash)} and {debt_context}. "
                "This is a liquidity input, not a "
                "standalone rating signal."
            )
        self.add(
            "Fundamental Analysis",
            "fundamental",
            "financial_metric",
            balance_sheet_claim,
            balance_sheet_metrics,
            "medium",
            "medium",
            implication=(
                "Interpret liquidity or leverage only from the signed net position "
                "and its underlying debt evidence."
            ),
        )
        equity = self.metrics.fundamentals.equity
        current_ratio = self.metrics.fundamentals.current_ratio
        lease_liabilities = self.metrics.fundamentals.total_lease_liabilities
        lease_context = None
        lease_metric = None
        if lease_liabilities is not None:
            lease_context = (
                "separate lease liabilities total "
                f"{self._money(lease_liabilities)}"
            )
            lease_metric = "total_lease_liabilities"
        elif self.metrics.fundamentals.lease_liability_current is not None:
            lease_context = (
                "available current lease liabilities are "
                f"{self._money(self.metrics.fundamentals.lease_liability_current)}; "
                "a complete lease-liability total is unavailable"
            )
            lease_metric = "lease_liability_current"
        elif self.metrics.fundamentals.lease_liability_noncurrent is not None:
            lease_context = (
                "available noncurrent lease liabilities are "
                f"{self._money(self.metrics.fundamentals.lease_liability_noncurrent)}; "
                "a complete lease-liability total is unavailable"
            )
            lease_metric = "lease_liability_noncurrent"
        if equity is not None and equity <= 0:
            constraint_parts = [
                f"Book equity is {self._money(equity)}, so debt/equity is not a "
                "meaningful leverage ratio"
            ]
            constraint_metrics = ["equity"]
            if current_ratio is not None:
                constraint_parts.append(
                    f"the current ratio is {_multiple(current_ratio)}"
                )
                constraint_metrics.append("current_ratio")
            if lease_context and lease_metric:
                constraint_parts.append(lease_context)
                constraint_metrics.append(lease_metric)
            self.add(
                "Fundamental Analysis",
                "balance_sheet_constraint",
                "financial_metric",
                (
                    f"{'; '.join(constraint_parts)}. Non-positive book equity is a "
                    "material balance-sheet constraint, but does not by itself "
                    "establish insolvency or its cause."
                ),
                constraint_metrics,
                "high",
                "high",
                counterargument=(
                    "Book equity can reflect accumulated distributions, losses, "
                    "accounting charges or a combination of factors."
                ),
                implication=(
                    "Assess leverage from debt, cash, liquidity, lease obligations "
                    "and cash-flow coverage instead of a debt/equity multiple."
                ),
            )
        elif current_ratio is not None and current_ratio < 1.0:
            constraint_parts = [
                f"The current ratio is {_multiple(current_ratio)}"
            ]
            constraint_metrics = ["current_ratio"]
            if lease_context and lease_metric:
                constraint_parts.append(lease_context)
                constraint_metrics.append(lease_metric)
            self.add(
                "Fundamental Analysis",
                "balance_sheet_constraint",
                "financial_metric",
                (
                    f"{'; '.join(constraint_parts)}. A current ratio below 1.0x "
                    "is material liquidity context, but does not by itself establish "
                    "an inability to meet obligations."
                ),
                constraint_metrics,
                "high",
                "high",
                counterargument=(
                    "Business models with recurring receipts or rapid working-capital "
                    "turnover can operate with current liabilities above current assets."
                ),
                implication=(
                    "Assess the working-capital model, cash conversion, debt maturities "
                    "and lease obligations together."
                ),
            )
        elif lease_context and lease_metric:
            self.add(
                "Fundamental Analysis",
                "lease_obligations",
                "financial_metric",
                (
                    f"In addition to reported debt, {lease_context}. The lease "
                    "figure remains separately labeled and is not silently merged "
                    "into total debt."
                ),
                [lease_metric],
                "medium",
                "medium",
                counterargument=(
                    "Lease obligations can support normal operations and are not "
                    "identical to unsecured borrowing."
                ),
                implication=(
                    "Assess debt, lease obligations, liquidity and cash-flow "
                    "coverage together."
                ),
            )

        self.add(
            "Valuation / Multiples",
            "valuation",
            "valuation_metric",
            (
                "EV/Sales is "
                f"{_multiple(self.metrics.valuation.ev_to_sales)}, derived from "
                "enterprise value and TTM revenue. Without a validated peer, "
                "history or cycle benchmark, this records a multiple level but "
                "does not label the company cheap or expensive."
            ),
            ["ev_to_sales", "enterprise_value", "revenue_ttm"],
            "medium",
            "high",
            counterargument=(
                "A benchmark can change the interpretation, but must be present "
                "in the authority packet before it affects the rating."
            ),
            implication="Treat EV/Sales as an observation until comparison evidence exists.",
        )
        price_to_fcf = self.metrics.valuation.price_to_fcf
        price_to_fcf_context = (
            " This is an extreme positive-FCF multiple under the validation "
            "rule, which means the market capitalization is highly sensitive "
            "to the durability and growth of cash flow and requires explicit "
            "manual review before publication."
            if price_to_fcf is not None and price_to_fcf > 100
            else (
                " This records the cash-flow valuation level without labeling "
                "it cheap or expensive."
            )
        )
        self.add(
            "Valuation / Multiples",
            "valuation",
            "valuation_metric",
            (
                f"For {ticker}, P/FCF is "
                f"{_multiple(price_to_fcf)}, derived from market capitalization "
                f"and TTM FCF.{price_to_fcf_context}"
            ),
            ["price_to_fcf", "market_cap", "free_cash_flow_ttm"],
            "medium",
            "medium",
            implication=(
                "A valuation conclusion requires sector comparison and "
                "cash-flow durability evidence."
            ),
        )
        if (
            self.metrics.valuation.ev_to_sales is None
            and self.metrics.valuation.price_to_fcf is None
            and self.metrics.valuation.trailing_pe is not None
        ):
            self.add(
                "Valuation / Multiples",
                "valuation",
                "valuation_metric",
                (
                    f"For {ticker}, trailing P/E is "
                    f"{_multiple(self.metrics.valuation.trailing_pe)}, derived "
                    "from the frozen close and trailing diluted EPS. Without a "
                    "validated peer, history or cycle benchmark, this records "
                    "a multiple level but does not label the company cheap or "
                    "expensive."
                ),
                ["trailing_pe", "close", "trailing_eps"],
                "medium",
                "high",
                implication=(
                    "Treat trailing P/E as an observation until comparison "
                    "evidence exists."
                ),
            )

        self.add(
            "Technical Setup",
            "technical",
            "technical_metric",
            (
                "The technical setup uses close "
                f"{self._money(self.metrics.technical.close)}, 50-SMA "
                f"{self._money(self.metrics.technical.sma_50)}, 200-SMA "
                f"{self._money(self.metrics.technical.sma_200)} and RSI "
                f"{_number(self.metrics.technical.rsi_14)}. The combined "
                "long-term trend state is "
                f"{classify_technical_trend(self.metrics)}."
            ),
            ["close", "sma_50", "sma_200", "rsi_14"],
            "high",
            "high",
            implication="Timing language should follow the validated technical trend state.",
        )
        self.add(
            "Technical Setup",
            "technical",
            "technical_metric",
            (
                f"{ticker}'s close of {self._money(self.metrics.technical.close)} "
                "and moving-average position imply "
                f"{_technical_interpretation(self.metrics)}; this remains "
                "timing evidence and does not prescribe an entry, trim or "
                "position size."
            ),
            ["close", "sma_50", "sma_200", "rsi_14"],
            "medium",
            "medium",
            counterargument="Technical weakness can be temporary if fundamentals and catalysts improve.",
            implication="Treat technical and fundamental divergence as a review condition, not as a personal trade instruction.",
        )

        growth_metrics = [
            metric
            for claim in current_claim_specs
            for metric in claim["metrics"]
            if str(metric).startswith("current_period_")
            and str(metric).endswith("_growth_yoy")
        ]
        growth_metrics = list(dict.fromkeys(str(metric) for metric in growth_metrics))
        current_period_loss_metrics = _current_period_loss_metrics(self.canonical)
        current_period_loss_phrase = _current_period_loss_phrase(
            current_period_loss_metrics
        )
        if growth_metrics:
            growth_values = {
                metric: self._metric_value(metric) for metric in growth_metrics
            }
            growth_text = ", ".join(
                _growth_metric_phrase(metric, growth_values[metric])
                for metric in growth_metrics
            )
            growth_declines = any(
                value is not None and value < 0
                for value in growth_values.values()
            )
            growth_increases = any(
                value is not None and value > 0
                for value in growth_values.values()
            )
            comparison_periods = {
                str(claim.get("comparison_period") or "")
                for claim in current_claim_specs
                if any(metric in claim["metrics"] for metric in growth_metrics)
            }
            if comparison_periods == {"fiscal_year"}:
                comparison_label = "Matching-fiscal-year"
            elif comparison_periods == {"quarter"}:
                comparison_label = "Matching-quarter"
            else:
                comparison_label = "Matching-period"
            fcf_value = self.metrics.fundamentals.free_cash_flow_ttm
            growth_divergence = current_profit_growth_divergence_metrics(
                self.metrics.fundamentals
            )
            if growth_divergence:
                divergence_text = " and ".join(
                    _growth_metric_phrase(metric, growth_values[metric])
                    for metric in growth_divergence
                )
                divergence_subject = (
                    f"The extreme {divergence_text}"
                    if len(growth_divergence) == 1
                    else f"The extreme profit comparisons ({divergence_text})"
                )
                guarded_reference = (
                    "that comparison"
                    if len(growth_divergence) == 1
                    else "those comparisons"
                )
                operating_declines = current_operating_profit_decline_metrics(
                    self.metrics.fundamentals
                )
                separate_operating_direction = ""
                if operating_declines:
                    operating_decline_text = " and ".join(
                        _growth_metric_phrase(metric, growth_values[metric])
                        for metric in operating_declines
                    )
                    separate_operating_direction = (
                        f" Separately, {operating_decline_text} remains measured "
                        "current-period downside evidence."
                    )
                if fcf_value is not None and fcf_value < 0:
                    cash_context = (
                        "Revenue TTM establishes scale, while negative FCF remains "
                        "evidence of weak cash conversion."
                    )
                elif fcf_value == 0:
                    cash_context = (
                        "Revenue TTM establishes scale, while zero FCF does not "
                        "establish positive cash conversion."
                    )
                elif fcf_value is not None:
                    cash_context = (
                        "Revenue TTM and positive FCF establish scale and cash "
                        "generation, not the cause or durability of the guarded "
                        "profit comparison."
                    )
                else:
                    cash_context = (
                        "Revenue TTM establishes scale, while unavailable FCF cannot "
                        "support a cash-conversion conclusion."
                    )
                bull_text = (
                    f"{comparison_label} evidence reports {growth_text}. "
                    f"{divergence_subject} diverges from revenue growth and requires "
                    "base-effect or one-off review; without causal filing evidence "
                    f"in the current packet, {guarded_reference} does not establish "
                    "operating business "
                    f"direction.{separate_operating_direction} "
                    f"Revenue TTM is {self._money(self.metrics.fundamentals.revenue_ttm)} "
                    f"and FCF TTM is {self._money(fcf_value)}. {cash_context} A more "
                    "constructive rating still requires persistence and stronger "
                    "technical or benchmarked valuation support."
                )
            elif growth_declines:
                comparison_summary = (
                    "The current-period comparisons are mixed"
                    if growth_increases
                    else "All available current-period comparisons decline"
                )
                if fcf_value is not None and fcf_value < 0:
                    cash_context = (
                        "negative FCF remains separate evidence of weak cash "
                        "conversion"
                    )
                elif fcf_value == 0:
                    cash_context = (
                        "zero FCF does not establish positive cash conversion"
                    )
                elif fcf_value is not None:
                    cash_context = (
                        "positive FCF establishes cash generation, but does not turn "
                        "mixed comparisons into broad-based operating improvement"
                    )
                else:
                    cash_context = (
                        "FCF is unavailable and cannot support a cash-conversion "
                        "conclusion"
                    )
                scale_and_cash = (
                    "Revenue TTM is "
                    f"{self._money(self.metrics.fundamentals.revenue_ttm)}"
                )
                if fcf_value is not None:
                    scale_and_cash += f" and FCF TTM is {self._money(fcf_value)}"
                bull_text = (
                    f"{comparison_label} evidence reports {growth_text}. "
                    f"{comparison_summary}; segment, margin or one-off context is "
                    "needed before treating them as business direction. "
                    f"{scale_and_cash}; {cash_context}. A more "
                    "constructive rating requires revenue and profit measures to "
                    "improve together, plus stronger technical or benchmarked "
                    "valuation support."
                )
            elif current_period_loss_metrics:
                if fcf_value is not None and fcf_value < 0:
                    cash_context = (
                        "the latest reported period still contains "
                        f"{current_period_loss_phrase}, and negative FCF remains "
                        "evidence of weak cash conversion. These figures show "
                        "reported top-line direction and scale; they do not establish "
                        "operating improvement. A more constructive rating still requires "
                        "profitability and cash conversion to improve, plus stronger "
                        "technical or benchmarked valuation support."
                    )
                else:
                    cash_context = (
                        "the latest reported period still contains "
                        f"{current_period_loss_phrase}. Revenue and FCF therefore do "
                        "not establish operating improvement. A more constructive "
                        "rating still requires profitability to improve and stronger "
                        "technical or benchmarked valuation support."
                    )
            elif fcf_value is not None and fcf_value < 0:
                if _negative_fcf_is_capex_funding_gap(self.metrics):
                    cash_context = (
                        "this records aligned current-period direction and scale, but "
                        "does not establish durability or cause. Negative FCF reflects "
                        "capital expenditure exceeding positive operating cash flow; "
                        "without a maintenance-versus-growth split, it identifies a "
                        "funding requirement rather than proving weak operations. A more "
                        "constructive rating still requires those comparisons to persist, "
                        "the investment funding path to remain supportable and stronger "
                        "technical or benchmarked valuation support."
                    )
                else:
                    cash_context = (
                        "this records aligned current-period direction and scale, but does "
                        "not establish durability or cause; negative FCF remains evidence "
                        "of weak cash conversion. A more "
                        "constructive rating still requires those comparisons to persist, "
                        "cash conversion to improve and stronger technical or benchmarked "
                        "valuation support."
                    )
            elif fcf_value == 0:
                cash_context = (
                    "this records aligned current-period direction and scale, but does "
                    "not establish durability, cause or positive cash conversion. A more "
                    "constructive rating "
                    "still requires those comparisons to persist, cash conversion to "
                    "improve and stronger technical or benchmarked valuation support."
                )
            elif fcf_value is not None:
                cash_context = (
                    "this records aligned current-period direction, scale and positive "
                    "cash generation, but does not establish durability or cause. A more "
                    "constructive rating still requires those "
                    "comparisons to persist and stronger technical or benchmarked "
                    "valuation support."
                )
            else:
                cash_context = (
                    "this records aligned current-period direction and scale, but does "
                    "not establish durability or cause; FCF is unavailable and cannot "
                    "support a cash-conversion conclusion. "
                    "A more constructive rating still requires those comparisons to "
                    "persist, cash-conversion evidence and stronger technical or "
                    "benchmarked valuation support."
                )
            if not growth_divergence and not growth_declines:
                scale_and_cash = (
                    "revenue TTM of "
                    f"{self._money(self.metrics.fundamentals.revenue_ttm)}"
                )
                if fcf_value is not None:
                    scale_and_cash += f" and FCF TTM of {self._money(fcf_value)}"
                bull_text = (
                    f"{comparison_label} evidence shows {growth_text}. Together with "
                    f"{scale_and_cash}, {cash_context}"
                )
        else:
            fcf_value = self.metrics.fundamentals.free_cash_flow_ttm
            if current_period_loss_metrics:
                cash_context = (
                    "The revenue total establishes scale, but the latest reported "
                    f"period still contains {current_period_loss_phrase}; these totals "
                    "do not establish operating improvement"
                )
            elif fcf_value is not None and fcf_value < 0:
                if _negative_fcf_is_capex_funding_gap(self.metrics):
                    cash_context = (
                        "The revenue total establishes scale, while negative FCF "
                        "reflects capital expenditure exceeding positive operating "
                        "cash flow. Without a maintenance-versus-growth split, this "
                        "identifies a funding requirement rather than proving weak "
                        "operations"
                    )
                else:
                    cash_context = (
                        "The revenue total establishes scale, while negative FCF is a "
                        "cash-conversion constraint rather than bull-case support"
                    )
            elif fcf_value == 0:
                cash_context = (
                    "The revenue total establishes scale, while zero FCF does not "
                    "establish positive cash conversion"
                )
            elif fcf_value is not None:
                cash_context = (
                    "These totals establish scale and positive cash generation, not growth"
                )
            else:
                cash_context = (
                    "The revenue total establishes scale, while unavailable FCF cannot "
                    "support a cash-conversion conclusion"
                )
            if fcf_value is None:
                bull_text = (
                    "The bull case uses revenue of "
                    f"{self._money(self.metrics.fundamentals.revenue_ttm)} as scale "
                    f"evidence. {cash_context}; a more constructive rating requires "
                    "comparable current-period evidence or technical confirmation."
                )
            else:
                bull_text = (
                    "The bull case combines revenue of "
                    f"{self._money(self.metrics.fundamentals.revenue_ttm)} with FCF of "
                    f"{self._money(fcf_value)}. {cash_context}; a more constructive "
                    "rating requires comparable current-period evidence or technical "
                    "confirmation."
                )
        bull_metrics = ["revenue_ttm"]
        if self.metrics.fundamentals.free_cash_flow_ttm is not None:
            bull_metrics.append("free_cash_flow_ttm")
        bull_metrics.extend(growth_metrics)
        bull_metrics.extend(current_period_loss_metrics)
        self.add(
            "Bull Case",
            "bull",
            "financial_metric",
            bull_text,
            bull_metrics,
            "medium",
            "medium",
            counterargument=(
                "Reported comparisons and scale do not by themselves prove durable cash "
                "conversion or justify an unbenchmarked valuation."
            ),
            implication="The bull case remains a research scenario, not an action plan.",
        )
        self.add(
            "Bull Case",
            "bull",
            "technical_metric",
            f"A constructive technical bull path for {ticker} requires confirmation beyond the current RSI of {_number(self.metrics.technical.rsi_14)} and moving-average setup.",
            ["rsi_14", "sma_50", "sma_200", "close"],
            "medium",
            "medium",
            implication="A more constructive research stance should require confirmation when the preferred rating is not Buy.",
        )

        bear_metrics = []
        if self.metrics.fundamentals.free_cash_flow_ttm is not None:
            bear_metrics.append("free_cash_flow_ttm")
        bear_metrics.extend(
            current_operating_profit_decline_metrics(
                self.metrics.fundamentals
            )
        )
        if bear_metrics:
            bear_metrics.extend(
                metric
                for metric, value in (
                    ("close", self.metrics.technical.close),
                    ("sma_50", self.metrics.technical.sma_50),
                    ("sma_200", self.metrics.technical.sma_200),
                    ("rsi_14", self.metrics.technical.rsi_14),
                )
                if value is not None
            )
            self.add(
                "Bear Case",
                "bear",
                "financial_metric",
                _bear_case_claim_text(
                    ticker,
                    self.metrics,
                    self.data_packet.price_basis.currency,
                ),
                bear_metrics,
                "medium",
                "high",
                implication=(
                    "Treat the bear case as evidence to monitor, not as proof of "
                    "permanent business deterioration."
                ),
            )
        self.add(
            "Catalysts & Triggers",
            "catalyst",
            "technical_metric",
            (
                "The validated technical reference levels are 50-SMA "
                f"{self._money(self.metrics.technical.sma_50)} and 200-SMA "
                f"{self._money(self.metrics.technical.sma_200)}. No separate "
                "evidence-backed price target is present in the packet."
            ),
            ["sma_50", "sma_200"],
            "medium",
            "medium",
            implication=(
                "Treat these moving averages as reference levels, not as "
                "standalone price targets."
            ),
        )

        self.add(
            "Final Rating & Action Plan",
            "rating",
            "rating",
            _final_rating_claim_text(
                ticker,
                preferred,
                self.metrics,
                self.data_packet.price_basis.currency,
                self.decision,
            ),
            core_rating_metrics,
            "high",
            "high",
            counterargument=_final_rating_counterargument(preferred, self.metrics),
            implication=_final_rating_implication(ticker, preferred, self.metrics),
        )
        return self.claims

    def add_event(self, event: MaterialNewsEvent, *, section: str) -> None:
        statement = str(event.summary or event.headline).strip()
        if not statement or any(character.isdigit() for character in statement):
            return
        evidence = [
            item
            for item in self.ledger.evidence_items
            if item.source_id == event.source_id
            and item.claim_type in {"event", "guidance", "news", "management_quote"}
            and item.authority_rank <= 2
            and item.date == event.date
            and item.statement.strip() == statement
            and self.evidence_id_counts.get(item.evidence_id) == 1
        ]
        if not evidence:
            return
        claim_statement = (
            f"Issuer-filed business context: {statement}"
            if event.event_type in _BUSINESS_CONTEXT_EVENT_TYPES
            else statement
        )
        self.counter += 1
        claim_id = f"{self.data_packet.ticker}_CLAIM_{self.counter:03d}"
        counterargument = None
        implication = None
        if event.event_type in _CATALYST_EVENT_TYPES:
            counterargument = (
                "An announced strategy is forward-looking intent; execution and "
                "financial contribution remain unproven."
            )
            implication = (
                "Reassess only when subsequent reported evidence shows whether "
                "the stated objectives are being achieved."
            )
        self.claims.append(
            ResearchClaim(
                claim_id=claim_id,
                section=section,
                claim_type="news",
                agent="deterministic_content_generator",
                claim=claim_statement,
                claim_text=claim_statement,
                evidence_metrics=[],
                metric_refs=[],
                metric_values={},
                evidence_ids=[item.evidence_id for item in evidence],
                source_ids=list(dict.fromkeys(item.source_id for item in evidence)),
                confidence="high",
                importance="high",
                counterargument=counterargument,
                investment_implication=implication,
            )
        )

    def add_risk(
        self,
        evidence: EvidenceItem,
        *,
        explain_disclosure: bool,
    ) -> None:
        self.counter += 1
        claim_id = f"{self.data_packet.ticker}_CLAIM_{self.counter:03d}"
        statement = evidence.statement.strip()
        if statement and statement[-1] not in ".!?":
            statement = f"{statement}."
        text = f"Issuer-disclosed risk: {statement}"
        if explain_disclosure:
            text += (
                " This identifies an exposure; it does not establish that the "
                "adverse outcome has occurred."
            )
        self.claims.append(
            ResearchClaim(
                claim_id=claim_id,
                section="Key Risks",
                claim_type="risk",
                agent="deterministic_content_generator",
                claim=text,
                claim_text=text,
                evidence_metrics=[],
                metric_refs=[],
                metric_values={},
                evidence_ids=[evidence.evidence_id],
                source_ids=[evidence.source_id],
                confidence=evidence.confidence,
                importance="high",
            )
        )

    def _selected_risk_evidence(self, *, limit: int) -> list[EvidenceItem]:
        candidates = [
            item
            for item in self.ledger.evidence_items
            if item.claim_type == "risk"
            and item.source_type in {"sec_filing", "company_ir", "official_press_release"}
            and item.authority_rank <= 2
            and self.evidence_id_counts.get(item.evidence_id) == 1
            and item.statement.strip()
        ]
        candidates = list({item.evidence_id: item for item in candidates}.values())
        if len(candidates) <= limit:
            return candidates
        positions = {
            round(index * (len(candidates) - 1) / (limit - 1))
            for index in range(limit)
        }
        return [candidates[index] for index in sorted(positions)]

    def add(
        self,
        section: str,
        claim_type: str,
        evidence_type: str,
        text: str,
        metrics: list[str],
        confidence: str,
        importance: str,
        counterargument: Optional[str] = None,
        implication: Optional[str] = None,
    ) -> None:
        if any(self._metric_value(metric) is None for metric in metrics):
            return
        evidence = self._evidence_for(metrics)
        if not evidence:
            return
        self.counter += 1
        claim_id = f"{self.data_packet.ticker}_CLAIM_{self.counter:03d}"
        self.claims.append(
            ResearchClaim(
                claim_id=claim_id,
                section=section,
                claim_type=evidence_type,
                agent="deterministic_content_generator",
                claim=text,
                claim_text=text,
                evidence_metrics=metrics,
                metric_refs=metrics,
                metric_values={
                    metric: value
                    for metric in metrics
                    if (value := self._metric_value(metric)) is not None
                },
                evidence_ids=[item.evidence_id for item in evidence],
                source_ids=list(dict.fromkeys(item.source_id for item in evidence)),
                confidence=confidence,
                importance=importance,
                counterargument=counterargument,
                investment_implication=implication,
            )
        )

    def _metric_value(self, metric_name: str) -> Optional[float]:
        for section_name in ("fundamentals", "technical", "valuation"):
            section = getattr(self.metrics, section_name)
            if hasattr(section, metric_name):
                value = getattr(section, metric_name)
                if isinstance(value, (int, float)):
                    return float(value)
        return _canonical_value(self.canonical, metric_name)

    def _money(self, value: Optional[float]) -> str:
        return _money(value, currency=self.data_packet.price_basis.currency)

    def _evidence_for(self, metrics: list[str]) -> list[EvidenceItem]:
        matched: list[EvidenceItem] = []
        for metric in metrics:
            metric_evidence = self._compatible_evidence_for_metric(metric)
            if not metric_evidence:
                return []
            matched.extend(metric_evidence)
        deduped: dict[str, EvidenceItem] = {}
        for item in matched:
            deduped.setdefault(item.evidence_id, item)
        return list(deduped.values())

    def _compatible_evidence_for_metric(
        self,
        metric_name: str,
    ) -> list[EvidenceItem]:
        expected_value = self._metric_value(metric_name)
        if expected_value is None:
            return []
        expected_unit = unit_for_metric(
            metric_name,
            currency=self.data_packet.price_basis.currency,
        )
        candidates = [
            item
            for item in self.ledger.find_by_metric(metric_name)
            if self.evidence_id_counts.get(item.evidence_id) == 1
            and _evidence_value_is_compatible(item, expected_value)
            and _evidence_provenance_is_compatible(item)
            and _evidence_date_is_compatible(
                item,
                metric_name,
                self.data_packet,
                self.metrics,
            )
            and _evidence_period_is_compatible(item, metric_name)
            and _evidence_unit_is_compatible(item.unit, expected_unit)
        ]
        with_explicit_unit = [item for item in candidates if item.unit]
        candidates = with_explicit_unit or candidates
        if not candidates:
            return []

        canonical_ids = self._canonical_evidence_ids(metric_name, expected_value)
        canonical_matches = [
            item for item in candidates if item.evidence_id in canonical_ids
        ]
        if canonical_matches and not metric_name.endswith("_ttm"):
            return _latest_evidence(canonical_matches)

        formula_backed = [
            item
            for item in candidates
            if item.formula_id and item.formula_operands
        ]
        if formula_backed:
            return _latest_evidence(formula_backed)
        if canonical_matches:
            return _latest_evidence(canonical_matches)

        raw_candidates = [item for item in candidates if item.raw_value is not None]
        return _latest_evidence(raw_candidates or candidates)

    def _canonical_evidence_ids(
        self,
        metric_name: str,
        expected_value: float,
    ) -> set[str]:
        if self.canonical is None:
            return set()
        matching_metrics = [
            metric
            for metric in self.canonical.metrics_for(metric_name)
            if math.isclose(
                float(metric.value),
                expected_value,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        ]
        if not matching_metrics:
            return set()
        latest_end_date = max(metric.end_date or "" for metric in matching_metrics)
        latest_metrics = [
            metric
            for metric in matching_metrics
            if (metric.end_date or "") == latest_end_date
        ]
        return {
            evidence_id
            for metric in latest_metrics
            for evidence_id in metric.evidence_ids
        }


def _evidence_value(item: EvidenceItem) -> Optional[float]:
    value = (
        item.normalized_value
        if item.normalized_value is not None
        else item.value
    )
    return float(value) if isinstance(value, (int, float)) else None


def _latest_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    latest_date = max((item.date or "") for item in items)
    latest = [item for item in items if (item.date or "") == latest_date]
    best_rank = min(item.authority_rank for item in latest)
    return [item for item in latest if item.authority_rank == best_rank]


def _evidence_value_is_compatible(
    item: EvidenceItem,
    expected_value: float,
) -> bool:
    actual_value = _evidence_value(item)
    if actual_value is None:
        return False
    return math.isclose(
        actual_value,
        expected_value,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def _evidence_unit_is_compatible(
    actual_unit: Optional[str],
    expected_unit: Optional[str],
) -> bool:
    if expected_unit is None or not actual_unit:
        return True
    return _normalize_unit(actual_unit) == _normalize_unit(expected_unit)


def _evidence_provenance_is_compatible(item: EvidenceItem) -> bool:
    return bool(
        (
            item.formula_id
            and item.formula_operands
        )
        or item.raw_value is not None
        or item.normalized_value is not None
        or (item.date and item.period)
    )


def _normalize_unit(unit: str) -> str:
    normalized = str(unit).strip().lower().replace("/", "_per_")
    return "_".join(normalized.replace("-", "_").split())


def _evidence_date_is_compatible(
    item: EvidenceItem,
    metric_name: str,
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
) -> bool:
    technical_metrics = {
        "close",
        "sma_10",
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_10",
        "ema_20",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "bollinger_upper",
        "bollinger_mid",
        "bollinger_lower",
        "atr_14",
        "avg_volume_20",
    }
    if metric_name not in technical_metrics or not item.date:
        return True
    expected_date = (
        data_packet.price_basis.date
        if metric_name == "close"
        else metrics_packet.technical.indicator_date
    )
    return item.date == expected_date


def _evidence_period_is_compatible(
    item: EvidenceItem,
    metric_name: str,
) -> bool:
    if not metric_name.endswith("_ttm"):
        return True
    if item.duration_days is not None and not 300 <= item.duration_days <= 430:
        return False
    period = str(item.period or "").strip().lower()
    if not period or "ttm" in period or ".." in period:
        return True
    return not any(token in period for token in ("q1", "q2", "q3", "q4"))


def _money(value: Optional[float], currency: str = "USD") -> str:
    if value is None:
        return "not available in evidence set"
    currency = str(currency or "USD").strip().upper()
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:
        amount = f"{magnitude / 1_000_000_000:.2f}B"
    elif magnitude >= 1_000_000:
        amount = f"{magnitude / 1_000_000:.1f}M"
    else:
        amount = f"{magnitude:.2f}"
    sign = "-" if value < 0 else ""
    return (
        f"{sign}${amount}"
        if currency == "USD"
        else f"{sign}{amount} {currency}"
    )


def _pct(value: Optional[float]) -> str:
    if value is None:
        return "not available in evidence set"
    return f"{value:.1%}"


def _multiple(value: Optional[float]) -> str:
    if value is None:
        return "not available in evidence set"
    return f"{value:.2f}x"


def _number(value: Optional[float]) -> str:
    if value is None:
        return "not available in evidence set"
    return f"{value:.2f}"


def _plain_number(value: Optional[float]) -> str:
    if value is None:
        return "not available in evidence set"
    return f"{value:.2f}"


def _growth_metric_label(metric_name: str) -> str:
    return {
        "current_period_revenue_growth_yoy": "revenue growth",
        "current_period_operating_income_growth_yoy": "operating-income growth",
        "current_period_net_income_growth_yoy": "net-income growth",
    }.get(metric_name, metric_name.replace("_", " "))


def _growth_metric_phrase(metric_name: str, value: Optional[float]) -> str:
    label = _growth_metric_label(metric_name)
    if value is None:
        return f"{label} not available"
    if value < 0:
        return f"{label.replace(' growth', ' decline')} {_pct(abs(value))}"
    if value == 0:
        return f"{label.replace(' growth', '')} unchanged"
    return f"{label} {_pct(value)}"


def _yoy_change_phrase(label: str, value: float) -> str:
    if value < 0:
        return f"{label} declined by {_pct(abs(value))}"
    if value > 0:
        return f"{label} increased by {_pct(value)}"
    return f"{label} was unchanged"


def _technical_interpretation(metrics: MetricsPacket) -> str:
    trend_state = classify_technical_trend(metrics)
    if trend_state == "bullish":
        return "a bullish long-term trend state"
    if trend_state == "bearish":
        return "a bearish long-term trend state"
    if trend_state == "mixed":
        return "a mixed long-term trend state"
    return "an unavailable long-term trend state"


def _negative_fcf_is_capex_funding_gap(metrics: MetricsPacket) -> bool:
    fundamentals = metrics.fundamentals
    return (
        fundamentals.free_cash_flow_ttm is not None
        and fundamentals.free_cash_flow_ttm < 0
        and fundamentals.operating_cash_flow_ttm is not None
        and fundamentals.operating_cash_flow_ttm > 0
        and fundamentals.capex_ttm is not None
        and fundamentals.capex_ttm > fundamentals.operating_cash_flow_ttm
    )


def _fundamental_fcf_claim_text(
    ticker: str,
    metrics: MetricsPacket,
    currency: str,
) -> str:
    fundamentals = metrics.fundamentals
    fcf = _money(fundamentals.free_cash_flow_ttm, currency)
    if _negative_fcf_is_capex_funding_gap(metrics):
        return (
            f"FCF TTM is {fcf} because capital expenditure of "
            f"{_money(fundamentals.capex_ttm, currency)} exceeds positive operating "
            f"cash flow of {_money(fundamentals.operating_cash_flow_ttm, currency)}. "
            "This measures an investment funding gap; without a validated "
            "maintenance-versus-growth split, it does not by itself establish weak "
            f"operations at {ticker}."
        )
    return (
        f"FCF TTM is {fcf}, making cash conversion a direct rating input for "
        f"{ticker}."
    )


def _bear_case_claim_text(
    ticker: str,
    metrics: MetricsPacket,
    currency: str,
) -> str:
    trend_state = classify_technical_trend(metrics)
    fcf_value = metrics.fundamentals.free_cash_flow_ttm
    fcf = _money(fcf_value, currency)
    if fcf_value is not None and fcf_value < 0:
        if _negative_fcf_is_capex_funding_gap(metrics):
            return (
                f"The technical picture for {ticker} is "
                f"{_technical_interpretation(metrics)} and remains timing evidence. "
                f"Negative FCF TTM of {fcf} reflects capital expenditure exceeding "
                "positive operating cash flow. This is a capital-intensity and "
                "funding risk, but without a maintenance-versus-growth split it does "
                "not by itself establish weak operations."
            )
        if trend_state == "bearish":
            return (
                f"{ticker}'s bearish long-term trend state and negative FCF TTM "
                f"of {fcf} are current downside evidence. They do not by "
                "themselves explain the cause or durability of the weakness, but "
                "the current packet contains both technical and cash-conversion "
                "support for a bear case."
            )
        if trend_state == "bullish":
            return (
                f"{ticker}'s bullish long-term trend state is counterevidence to "
                f"the bear case, while negative FCF TTM of {fcf} is current "
                "fundamental downside evidence. The bear case therefore rests on "
                "weak cash conversion; the technical trend offsets but does not "
                "erase that risk."
            )
        if trend_state == "mixed":
            return (
                f"{ticker}'s mixed long-term trend state neither confirms nor "
                f"refutes the bear case, while negative FCF TTM of {fcf} is "
                "current fundamental downside evidence. The current bear case "
                "rests on weak cash conversion without technical confirmation."
            )
        return (
            f"{ticker}'s long-term technical trend is not fully measured, while "
            f"negative FCF TTM of {fcf} is current fundamental downside "
            "evidence. The bear case rests on weak cash conversion without a "
            "measured technical confirmation or offset."
        )
    profit_declines = [
        {
            "current_period_operating_income_growth_yoy": "operating-income",
            "current_period_net_income_growth_yoy": "net-income",
        }[metric_name]
        for metric_name in current_operating_profit_decline_metrics(
            metrics.fundamentals
        )
    ]
    if profit_declines and fcf_value is None:
        decline_text = " and ".join(profit_declines)
        decline_subject = (
            f"{decline_text} decline"
            if len(profit_declines) == 1
            else f"{decline_text} declines"
        )
        trend_context = {
            "bullish": (
                "The bullish long-term trend state is counterevidence, but does "
                "not erase the reported weakness."
            ),
            "bearish": (
                "The bearish long-term trend state adds technical confirmation, "
                "but does not establish the cause or durability of the weakness."
            ),
            "mixed": (
                "The mixed long-term trend state neither confirms nor offsets "
                "the reported weakness."
            ),
        }.get(
            trend_state,
            "The long-term technical trend is unavailable and adds no confirmation.",
        )
        return (
            f"{ticker}'s current-period {decline_subject} "
            f"{'is' if len(profit_declines) == 1 else 'are'} current downside "
            f"evidence. FCF is unavailable, so the current packet cannot confirm "
            f"or offset that weakness through cash conversion. {trend_context} "
            "Persistence and cause still require separate confirmation."
        )
    if profit_declines and fcf_value is not None and fcf_value > 0:
        decline_text = " and ".join(profit_declines)
        if trend_state == "bullish":
            return (
                f"{ticker}'s current-period {decline_text} declines are current "
                f"downside evidence. Positive FCF TTM of {fcf} and the bullish "
                "long-term trend state are counterevidence, but do not erase the "
                "declines. A durable bear case requires the profit weakness to "
                "persist or be confirmed by weaker cash conversion; the current "
                "packet does not establish its cause."
            )
        if trend_state == "bearish":
            return (
                f"{ticker}'s current-period {decline_text} declines and bearish "
                "long-term trend state are current downside evidence. Positive FCF "
                f"TTM of {fcf} is counterevidence; persistence and cause still need "
                "separate confirmation."
            )
        return (
            f"{ticker}'s current-period {decline_text} declines are current downside "
            f"evidence. Positive FCF TTM of {fcf} is counterevidence, while the "
            f"{trend_state} technical state does not establish the cause or "
            "durability of the profit weakness."
        )
    if trend_state == "bearish":
        return (
            f"{ticker}'s bearish long-term trend state is current downside "
            f"evidence. FCF TTM of {fcf} is the counterweight; without "
            "separate operating evidence, the technical state alone does not "
            "establish company-specific deterioration."
        )
    if trend_state == "bullish":
        return (
            f"{ticker}'s bullish long-term trend state is not current downside "
            f"evidence. FCF TTM of {fcf} is also counterevidence. A bear case "
            "requires a future technical reversal or separate evidence of "
            "weaker cash generation; neither is established by the current "
            "packet."
        )
    if trend_state == "mixed":
        return (
            f"{ticker}'s mixed long-term trend state is inconclusive rather than "
            f"current downside evidence. FCF TTM of {fcf} is the counterweight. "
            "A bear case requires downside confirmation or separate evidence "
            "of weaker cash generation."
        )
    return (
        f"{ticker}'s long-term technical trend is not fully measured and therefore "
        f"is not current downside evidence. FCF TTM of {fcf} is the available "
        "counterweight; a bear case requires separate evidence of weaker cash "
        "generation."
    )


def _claim_text(claim: ResearchClaim) -> str:
    return " ".join(
        part
        for part in [
            claim.claim_text or claim.claim or "",
            claim.counterargument or "",
            claim.investment_implication or "",
        ]
        if part
    ).lower()


def _has_validated_number(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    if _is_data_limitation_claim(claim):
        return False
    return any(char.isdigit() for char in text)


def _has_company_specific_driver(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    drivers = {
        "qct", "qtl", "handset", "automotive", "iot", "cloud", "search", "youtube",
        "ai data cloud", "rpo", "nrr", "agentforce", "data cloud", "observability",
        "large-customer", "datacenter", "reality labs", "buyback", "product revenue",
        "remaining performance obligations", "capex", "free cash flow", "fcf",
        "google cloud", "services revenue", "family of apps", "vmware", "infrastructure software",
        "adjusted free cash flow", "free cash flow margin",
        "balance-sheet", "net cash", "debt evidence", "ev/sales", "p/fcf",
        "technical setup", "moving-average", "source disagreement", "current-period mismatch",
        "earnings", "trigger language",
    }
    return any(driver in text for driver in drivers)


def _is_company_specific_claim(claim: ResearchClaim) -> bool:
    if (
        not claim.evidence_ids
        or _is_generic_meta_claim(claim)
        or _is_data_limitation_claim(claim)
    ):
        return False
    section = claim.section or ""
    claim_type = claim.claim_type or ""
    if section in _BUSINESS_CONTEXT_SECTIONS:
        return claim_type in {"event", "guidance", "management_quote", "news"} or (
            _has_ticker_specific_kpi(claim)
        )
    return section == "Catalysts & Triggers" and claim_type in {
        "event",
        "guidance",
        "management_quote",
        "news",
    }


def _has_sector_specific_interpretation(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    lenses = {
        "semiconductor", "saas", "consumption", "ads/cloud", "mega-cap", "enterprise saas",
        "inventory", "gross margin", "sbc", "capex", "regulatory", "cycle",
        "rsi", "sma", "moving-average", "trend", "earnings",
    }
    if (claim.section or "") == "Technical Setup" and any(term in text for term in {"rsi", "sma", "moving-average", "trend", "levels"}):
        return True
    return any(lens in text for lens in lenses)


def _has_rating_implication(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    return any(term in text for term in {"rating", "action", "accumulate", "hold", "trim", "underweight", "buy", "sell", "conviction"})


def _has_counterargument_or_risk_implication(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    terms = {
        "risk", "counterargument", "bear", "pressure", "overbought", "unavailable",
        "manual review", "drawdown", "low-confidence", "missing", "valuation risk",
        "confirmation", "blocking data issue",
    }
    return any(term in text for term in terms)


def _is_generic_meta_claim(claim: ResearchClaim) -> bool:
    text = (claim.claim_text or claim.claim or "").lower()
    generic_phrases = {
        "is available in the validated packet",
        "should anchor business-quality discussion",
        "not from manually recomputed",
        "rather than narrative",
        "use validated",
        "business discussion should focus",
        "should be read against",
        "should not be translated into a blocked rating",
        "validation and audit issues are part of",
        "blocking data issue should override",
        "source disagreement or current-period mismatch can reduce conviction",
        "should be limited to confirmed packet inputs",
        "trigger language should use",
    }
    return any(phrase in text for phrase in generic_phrases)


def _is_data_limitation_claim(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    return any(
        phrase in text
        for phrase in {
            "not available in validated packet",
            "fcf unavailable",
            "free cash flow is unavailable",
            "metric unavailable",
            "missing company guidance",
            "earnings date unavailable",
        }
    )


def _has_ticker_specific_kpi(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    terms = {
        "google cloud", "search", "youtube", "capex", "ai capex", "other income",
        "product revenue", "rpo", "remaining performance obligations", "nrr",
        "net revenue retention", "customers above $1m", "adjusted free cash flow",
        "family of apps", "reality labs", "azure", "intelligent cloud", "vmware",
        "infrastructure software", "ai semiconductor", "free cash flow margin",
        "observability", "ai monitoring", "gpu observability", "cash and marketable securities",
        "agentforce", "data cloud", "subscription growth", "capital return",
        "backlog", "contract backlog", "contracted missions", "launch manifest",
        "electron", "haste", "launch cadence", "neutron", "space systems",
        "launch services", "service revenue", "execution milestone", "capital intensity",
        "latest reported period", "operating income", "net income",
    }
    return any(term in text for term in terms)


def _is_current_period_kpi_claim(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    if (claim.section or "") not in {
        "Business & Segment Context",
        "Fundamental Analysis",
        "Catalysts & Triggers",
        "Key Risks",
        "Business Model Reality",
        "Revenue Scale and Backlog",
        "Contract / Backlog Materiality",
        "Segment Mix",
        "Execution Milestones",
        "FCF Path",
        "Capital Intensity",
        "Valuation vs Revenue/Backlog",
    }:
        return False
    return _has_ticker_specific_kpi(claim) and _has_validated_number(claim) and any(
        term in text
        for term in {
            "q1", "q2", "q3", "q4", "latest-quarter", "current-period", "fy2025", "fy2026",
            "fy2027", "quarter", "guide", "guidance", "revenue of", "fcf of",
        }
    )


def _has_mechanical_rating_language(claim: ResearchClaim) -> bool:
    text = _claim_text(claim)
    return any(
        phrase in text
        for phrase in {
            "decisionpacket permissions connect",
            "rating corridor suggests",
            "score indicates",
            "allowed rating corridor",
            "because decisionpacket",
        }
    )


def _final_rating_rationale_quality(claims: list[ResearchClaim]) -> int:
    rating_claims = [claim for claim in claims if (claim.section or "") == "Final Rating & Action Plan"]
    if not rating_claims:
        return 0
    score = 0
    for claim in rating_claims:
        if _has_mechanical_rating_language(claim):
            continue
        if _has_validated_number(claim):
            score += 25
        if _has_company_specific_driver(claim):
            score += 25
        if _has_sector_specific_interpretation(claim):
            score += 20
        if _has_counterargument_or_risk_implication(claim):
            score += 15
        if _has_rating_implication(claim):
            score += 15
    return min(100, score)


def _is_substantive_claim(claim: ResearchClaim) -> bool:
    if _is_data_limitation_claim(claim):
        return False
    if _is_generic_meta_claim(claim):
        return False
    elements = [
        _has_validated_number(claim),
        _has_company_specific_driver(claim),
        _has_sector_specific_interpretation(claim),
        _has_rating_implication(claim),
        _has_counterargument_or_risk_implication(claim),
    ]
    return _has_validated_number(claim) and _has_company_specific_driver(claim) and (
        _has_rating_implication(claim) or _has_counterargument_or_risk_implication(claim)
    ) and sum(1 for element in elements if element) >= 3


def _canonical_value(
    canonical_financials: Optional[CanonicalFinancials],
    metric_name: str,
) -> Optional[float]:
    if canonical_financials is None:
        return None
    metric_aliases = {
        "current_q_revenue": ["current_q_revenue", "revenue"],
        "current_q_free_cash_flow": ["current_q_free_cash_flow", "free_cash_flow"],
        "operating_cash_flow": ["operating_cash_flow", "cash_flow_from_operations"],
        "backlog": ["backlog", "contract_backlog", "remaining_performance_obligations"],
        "space_systems_revenue": ["space_systems_revenue", "product_revenue"],
        "launch_services_revenue": ["launch_services_revenue", "service_revenue"],
        "launch_cadence": ["launch_cadence", "electron_execution", "electron_haste_new_contracts", "launch_manifest_contracts"],
        "electron_haste_new_contracts": ["electron_haste_new_contracts", "electron_execution"],
        "neutron_new_contracts": ["neutron_new_contracts", "neutron_development_risk"],
        "launch_manifest_contracts": ["launch_manifest_contracts", "launch_cadence"],
        "operating_loss": ["operating_loss", "operating_income"],
        "cash_and_marketable_securities": ["cash_and_marketable_securities", "cash_and_investments", "cash"],
    }
    aliases = metric_aliases.get(metric_name, [metric_name])
    candidates = [
        metric
        for alias in aliases
        for metric in canonical_financials.metrics_for(alias)
    ]
    if metric_name.startswith("current_q_"):
        current_candidates = [
            metric for metric in candidates
            if _is_current_period_metric(metric.period, metric.source_ids)
        ]
        if current_candidates:
            candidates = current_candidates
    if not candidates:
        return None
    candidates = sorted(
        candidates,
        key=lambda metric: (
            metric.end_date or "",
            _reported_period_priority(metric),
            {"high": 3, "medium": 2, "low": 1}.get(metric.confidence, 0),
        ),
        reverse=True,
    )
    return candidates[0].value


def _latest_current_period_metric(
    canonical_financials: CanonicalFinancials,
    metric_name: str,
):
    candidates = [
        metric
        for metric in canonical_financials.metrics_for(metric_name)
        if metric.basis == "gaap"
        and metric.period_bucket in {"annual", "quarterly"}
        and metric.start_date
        and metric.end_date
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda metric: (
            metric.end_date or "",
            1 if metric.period_bucket == "annual" else 0,
            {"high": 3, "medium": 2, "low": 1}.get(metric.confidence, 0),
        ),
    )


def _current_period_loss_metrics(
    canonical_financials: Optional[CanonicalFinancials],
) -> list[str]:
    if canonical_financials is None:
        return []
    anchor = _latest_current_period_metric(canonical_financials, "revenue")
    if anchor is None:
        return []
    return [
        metric_name
        for metric_name in ("operating_income", "net_income")
        if (
            metric := _metric_for_same_reported_period(
                canonical_financials,
                metric_name,
                anchor,
            )
        )
        is not None
        and metric.value < 0
    ]


def _current_period_loss_phrase(metric_names: list[str]) -> str:
    labels = {
        "operating_income": "an operating loss",
        "net_income": "a net loss",
    }
    phrases = [labels[name] for name in metric_names if name in labels]
    if len(phrases) <= 1:
        return phrases[0] if phrases else "a loss"
    return f"{phrases[0]} and {phrases[1]}"


def _metric_for_same_reported_period(
    canonical_financials: CanonicalFinancials,
    metric_name: str,
    anchor_metric: object,
):
    start_date = getattr(anchor_metric, "start_date", None)
    end_date = getattr(anchor_metric, "end_date", None)
    if not start_date or not end_date:
        return canonical_financials.get_metric(
            metric_name,
            period=getattr(anchor_metric, "period", None),
        )
    candidates = [
        metric
        for metric in canonical_financials.metrics_for(metric_name)
        if metric.start_date == start_date
        and metric.end_date == end_date
        and metric.period_bucket == getattr(anchor_metric, "period_bucket", None)
        and (
            getattr(anchor_metric, "fiscal_year", None) is None
            or metric.fiscal_year == getattr(anchor_metric, "fiscal_year", None)
        )
        and (
            getattr(anchor_metric, "fiscal_period", None) is None
            or metric.fiscal_period == getattr(anchor_metric, "fiscal_period", None)
        )
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda metric: {
            "high": 3,
            "medium": 2,
            "low": 1,
        }.get(metric.confidence, 0),
    )


def _display_period(metric: object) -> str:
    fiscal_year = getattr(metric, "fiscal_year", None)
    fiscal_period = str(getattr(metric, "fiscal_period", "") or "").upper()
    if fiscal_year is not None and fiscal_period in {"Q1", "Q2", "Q3", "Q4"}:
        return f"FY{fiscal_year}_{fiscal_period}"
    if fiscal_year is not None and fiscal_period == "FY":
        return f"FY{fiscal_year}"
    return str(getattr(metric, "period", "") or "current period")


def _reported_period_priority(metric: object) -> int:
    return {
        "quarterly": 3,
        "ytd": 2,
        "annual": 1,
    }.get(str(getattr(metric, "period_bucket", "") or "").lower(), 0)


def _is_current_period_metric(period: str, source_ids: list[str]) -> bool:
    period_lower = (period or "").lower()
    source_lower = " ".join(source_ids).lower()
    return (
        "q1_2026" in period_lower
        or "q2_2026" in period_lower
        or "q3_2026" in period_lower
        or "q4_2026" in period_lower
        or "2026q1" in period_lower
        or "2026q2" in period_lower
        or "2026_q1" in period_lower
        or "2026_q2" in period_lower
        or "2026_q3" in period_lower
        or "2026_q4" in period_lower
        or "_ir_" in source_lower
        or "release" in source_lower
    )


def _per_share(value: Optional[float]) -> str:
    if value is None:
        return "not available in evidence set"
    return f"${value:.2f}"


def _final_rating_claim_text(
    ticker: str,
    preferred: str,
    metrics: MetricsPacket,
    currency: str,
    decision: DecisionPacket,
) -> str:
    evidence_anchor = _core_rating_evidence_text(metrics, currency)
    reason = (
        decision.analytical_rating_reason
        or decision.rating_permission.reason
    )
    valuation_status = decision.signal_scores.valuation_status
    valuation_note = (
        "Valuation multiples are unbenchmarked and therefore add neither a "
        "positive nor a negative rating signal."
        if valuation_status == "unbenchmarked"
        else "No benchmarked valuation signal is present."
    )
    current_profit_declines = [
        {
            "current_period_operating_income_growth_yoy": "operating-income",
            "current_period_net_income_growth_yoy": "net-income",
        }[metric_name]
        for metric_name in current_operating_profit_decline_metrics(
            metrics.fundamentals
        )
    ]
    if current_profit_declines:
        decline_text = " and ".join(current_profit_declines)
        if metrics.fundamentals.free_cash_flow_ttm is None:
            fundamental_note = (
                "The measured fundamental picture is pressured but incomplete: "
                f"current-period {decline_text} declines are measured while FCF "
                "is unavailable."
            )
        elif metrics.fundamentals.free_cash_flow_ttm > 0:
            fundamental_note = (
                "The measured fundamental picture is mixed: positive FCF does "
                f"not erase current-period {decline_text} declines."
            )
        else:
            fundamental_note = (
                "The measured fundamental picture is cautious: current-period "
                f"{decline_text} declines lack positive FCF counterevidence."
            )
    elif decision.signal_scores.fundamental_score < 0:
        fundamental_note = (
            "The measured fundamental signal is cautious and remains part of the "
            "rating rationale."
        )
    elif decision.signal_scores.fundamental_score > 0:
        fundamental_note = "The measured fundamental signal is constructive."
    else:
        fundamental_note = "The measured fundamental signal is neutral."
    return (
        f"We rate {ticker} {preferred} at the validated close of "
        f"{_money(metrics.technical.close, currency)}. {reason} The factual "
        f"anchors are {evidence_anchor}; the technical evidence indicates "
        f"{_technical_interpretation(metrics)}. {fundamental_note} "
        f"{valuation_note}"
    )


def _core_rating_metric_refs(metrics: MetricsPacket) -> list[str]:
    metric_refs = ["close"]
    for metric_name, value in (
        ("revenue_ttm", metrics.fundamentals.revenue_ttm),
        ("free_cash_flow_ttm", metrics.fundamentals.free_cash_flow_ttm),
        ("ev_to_sales", metrics.valuation.ev_to_sales),
        ("sma_50", metrics.technical.sma_50),
        ("sma_200", metrics.technical.sma_200),
        ("rsi_14", metrics.technical.rsi_14),
        (
            "current_period_operating_income_growth_yoy",
            metrics.fundamentals.current_period_operating_income_growth_yoy,
        ),
        (
            "current_period_net_income_growth_yoy",
            metrics.fundamentals.current_period_net_income_growth_yoy,
        ),
    ):
        if value is not None:
            metric_refs.append(metric_name)
    if (
        metrics.valuation.ev_to_sales is None
        and metrics.valuation.trailing_pe is not None
    ):
        metric_refs.append("trailing_pe")
    return metric_refs


def _core_rating_evidence_text(metrics: MetricsPacket, currency: str) -> str:
    anchors = []
    if metrics.fundamentals.revenue_ttm is not None:
        anchors.append(
            f"revenue TTM of {_money(metrics.fundamentals.revenue_ttm, currency)}"
        )
    if metrics.fundamentals.free_cash_flow_ttm is not None:
        anchors.append(
            f"FCF TTM of {_money(metrics.fundamentals.free_cash_flow_ttm, currency)}"
        )
    if metrics.valuation.ev_to_sales is not None:
        anchors.append(f"EV/Sales of {_multiple(metrics.valuation.ev_to_sales)}")
    elif metrics.valuation.trailing_pe is not None:
        anchors.append(f"trailing P/E of {_multiple(metrics.valuation.trailing_pe)}")
    return ", ".join(anchors) if anchors else "the available validated metrics"


def _final_rating_counterargument(preferred: str, metrics: MetricsPacket) -> str:
    if preferred in {"Accumulate", "Buy"}:
        return "A more bearish rating would require evidence that cash generation or technical confirmation has deteriorated."
    if preferred in {"Tactical Trim", "Tactical Underweight", "Underweight"}:
        return "A more bullish rating would require current-period KPI acceleration, technical confirmation and benchmarked valuation evidence."
    return "A more bullish rating needs current-period or technical confirmation and benchmarked valuation evidence; a more bearish rating needs deteriorating fundamentals or unresolved data errors."


def _final_rating_implication(ticker: str, preferred: str, metrics: MetricsPacket) -> str:
    if preferred == "Accumulate":
        return f"An Accumulate research stance for {ticker} requires confirmed KPI and technical evidence."
    if preferred in {"Tactical Trim", "Tactical Underweight"}:
        return f"The tactical-risk stance for {ticker} remains until trend or current-period KPI evidence changes."
    return f"The Hold research stance for {ticker} remains until technical or current-period KPI evidence changes."


def _claim_metric_available(
    metrics: MetricsPacket,
    canonical_financials: CanonicalFinancials,
    metric_name: str,
) -> bool:
    for section_name in ("fundamentals", "technical", "valuation"):
        section = getattr(metrics, section_name)
        if hasattr(section, metric_name) and isinstance(
            getattr(section, metric_name), (int, float)
        ):
            return True
    return _canonical_value(canonical_financials, metric_name) is not None


def _current_period_claim_specs(
    ticker: str,
    metrics: MetricsPacket,
    canonical_financials: Optional[CanonicalFinancials],
    currency: str = "USD",
) -> list[dict[str, object]]:
    fundamentals = metrics.fundamentals
    specs: list[dict[str, object]] = []
    if canonical_financials is None:
        return specs
    specs.extend(_early_commercial_capital_intensive_specs(ticker, metrics, canonical_financials))
    if ticker == "GOOGL":
        q1_revenue = _canonical_value(canonical_financials, "current_q_revenue")
        cloud_revenue = _canonical_value(canonical_financials, "google_cloud_revenue")
        cloud_growth = _canonical_value(canonical_financials, "google_cloud_growth")
        op_margin = _canonical_value(canonical_financials, "operating_margin")
        capex = _canonical_value(canonical_financials, "capex")
        other_income = _canonical_value(canonical_financials, "other_income_gain")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"GOOGL Q1 revenue of {_money(q1_revenue)} and Google Cloud revenue of {_money(cloud_revenue)} at {_pct(cloud_growth)} growth show the current-period growth engine is real, "
                    "but Cloud and Search strength still need to be balanced against AI capex and valuation before moving beyond Hold."
                ),
                "metrics": ["current_q_revenue", "google_cloud_revenue", "google_cloud_growth"],
                "counterargument": "Cloud acceleration can be offset by depreciation and AI infrastructure spending.",
                "implication": "Require Cloud plus FCF/capex context before publishing a bullish upgrade.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"GOOGL's Q1 operating margin of {_pct(op_margin)}, Q1 capex of {_money(capex)} and TTM FCF of {_money(fundamentals.free_cash_flow_ttm)} make AI capex the main cash-conversion debate, "
                    "so Hold is more disciplined than adding aggressively into an overbought chart."
                ),
                "metrics": ["operating_margin", "capex", "free_cash_flow_ttm"],
                "counterargument": "One-off gains or investment income should not be treated as recurring operating quality.",
                "implication": "Hold remains more disciplined than Buy until FCF conversion and capex pressure are clearer.",
            },
            {
                "section": "Key Risks",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"GOOGL's Other Income gain of {_money(other_income)} is a current-period quality caveat: it can lift reported earnings, but it should not be capitalized as recurring Search or Cloud economics."
                ),
                "metrics": ["other_income_gain"],
                "counterargument": "Investment gains can support balance-sheet flexibility, but they are not operating margin.",
                "implication": "Keep rating language anchored in operating cash generation and capex, not one-off gains.",
            },
        ])
    elif ticker == "SNOW":
        product_revenue = _canonical_value(canonical_financials, "product_revenue")
        nrr = _canonical_value(canonical_financials, "net_revenue_retention")
        rpo = _canonical_value(canonical_financials, "remaining_performance_obligations")
        customers = _canonical_value(canonical_financials, "customers_gt_1m")
        adjusted_fcf = _canonical_value(canonical_financials, "adjusted_free_cash_flow")
        fy_guide = _canonical_value(canonical_financials, "fy2027_product_revenue_guidance")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"SNOW's product revenue of {_money(product_revenue)}, NRR of {_pct(nrr)} and RPO of {_money(rpo)} are the current-period proof points for AI Data Cloud demand; "
                    "they support the growth story but do not eliminate valuation and technical-trend risk."
                ),
                "metrics": ["product_revenue", "net_revenue_retention", "remaining_performance_obligations"],
                "counterargument": "Consumption revenue can slow quickly if customer optimization returns.",
                "implication": "Hold language should depend on product-revenue durability, RPO conversion and whether the underweight bias is still warranted.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"SNOW's FY2026 {_plain_number(customers)} customers above $1M product revenue and adjusted FCF of {_money(adjusted_fcf)} show enterprise depth and cash conversion, "
                    "but SBC and GAAP/non-GAAP gaps still justify a cautious Hold with an underweight bias rather than an upgrade."
                ),
                "metrics": ["customers_gt_1m", "adjusted_free_cash_flow", "sbc_to_revenue"],
                "counterargument": "High FCF can coexist with GAAP losses and elevated SBC.",
                "implication": "Do not upgrade without NRR/RPO/product-revenue confirmation.",
            },
            {
                "section": "Catalysts & Triggers",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"SNOW's FY2027 product revenue guide of {_money(fy_guide)} is the key catalyst yardstick: upside requires sustained RPO conversion and stable NRR, while downside appears if consumption weakens."
                ),
                "metrics": ["fy2027_product_revenue_guidance", "remaining_performance_obligations"],
                "counterargument": "Guidance can be revised if consumption trends change.",
                "implication": "Re-rate only if product revenue and RPO conversion improve against this guide.",
            },
        ])
    elif ticker == "META":
        q_revenue = _canonical_value(canonical_financials, "current_q_revenue")
        op_margin = _canonical_value(canonical_financials, "operating_margin")
        q_fcf = _canonical_value(canonical_financials, "current_q_free_cash_flow")
        capex_low = _canonical_value(canonical_financials, "capex_guidance_low")
        capex_high = _canonical_value(canonical_financials, "capex_guidance_high")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"META's Q1 revenue of {_money(q_revenue)} shows that the ad platform still has substantial current-period growth power."
                ),
                "metrics": ["current_q_revenue"],
                "counterargument": "Ad strength can be offset by AI infrastructure spending and Reality Labs losses.",
                "implication": "Revenue quality supports Hold, not a more bearish stance.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"META's Q1 operating margin of {_pct(op_margin)} and Q1 FCF of {_money(q_fcf)} show strong ad-platform economics and cash generation."
                ),
                "metrics": ["operating_margin", "current_q_free_cash_flow"],
                "counterargument": "Margins may compress if AI capex and infrastructure depreciation accelerate.",
                "implication": "Cash generation keeps the rating from moving to Sell despite capex risk.",
            },
            {
                "section": "Key Risks",
                "kind": "current_period",
                "evidence_type": "guidance",
                "text": (
                    f"META's FY2026 capex guidance range of {_money(capex_low)}-{_money(capex_high)} keeps AI infrastructure ROI risk central to the Hold rating."
                ),
                "metrics": ["capex_guidance_low", "capex_guidance_high"],
                "counterargument": "AI spend can strengthen ads ranking and engagement if monetization follows.",
                "implication": "Hold remains appropriate until capex intensity translates into durable earnings growth.",
            },
        ])
    elif ticker == "MSFT":
        q_revenue = _canonical_value(canonical_financials, "current_q_revenue")
        cloud = _canonical_value(canonical_financials, "microsoft_cloud_revenue")
        cloud_growth = _canonical_value(canonical_financials, "microsoft_cloud_growth")
        azure_growth = _canonical_value(canonical_financials, "azure_growth")
        ai_run_rate = _canonical_value(canonical_financials, "ai_run_rate")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"MSFT's Q3 revenue of {_money(q_revenue)} and Microsoft Cloud revenue of {_money(cloud)} show that cloud scale remains the core business driver."
                ),
                "metrics": ["current_q_revenue", "microsoft_cloud_revenue"],
                "counterargument": "Large cloud scale does not automatically solve AI capacity cost.",
                "implication": "Cloud scale supports Hold rather than a bearish rating.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"Microsoft Cloud growth of {_pct(cloud_growth)} and Azure growth of {_pct(azure_growth)} show current-period demand strength."
                ),
                "metrics": ["microsoft_cloud_growth", "azure_growth"],
                "counterargument": "Growth can still be offset by capex and margin pressure.",
                "implication": "A more bullish rating needs cloud growth to convert into cleaner FCF expansion.",
            },
            {
                "section": "Catalysts & Triggers",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"MSFT's AI business annual revenue run-rate above {_money(ai_run_rate)} is the key catalyst yardstick for whether AI demand is becoming material enough to offset infrastructure spend."
                ),
                "metrics": ["ai_run_rate"],
                "counterargument": "Run-rate disclosures can outpace realized margin contribution.",
                "implication": "Upgrade requires AI revenue to scale with durable margin and FCF support.",
            },
        ])
    elif ticker == "AVGO":
        q_revenue = _canonical_value(canonical_financials, "current_q_revenue")
        ai_revenue = _canonical_value(canonical_financials, "ai_revenue")
        q2_guide = _canonical_value(canonical_financials, "q2_revenue_guidance")
        q_fcf = _canonical_value(canonical_financials, "current_q_free_cash_flow")
        ai_guide = _canonical_value(canonical_financials, "q2_ai_semiconductor_revenue_guidance")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"AVGO's Q1 revenue of {_money(q_revenue)} and AI revenue of {_money(ai_revenue)} show that AI infrastructure is the central current-period growth driver."
                ),
                "metrics": ["current_q_revenue", "ai_revenue"],
                "counterargument": "AI acceleration can still be offset by valuation risk.",
                "implication": "Hold requires explicit AI revenue support in the main report.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"AVGO's Q1 FCF of {_money(q_fcf)} provides current-period cash-flow support for the AI and VMware/software mix thesis."
                ),
                "metrics": ["current_q_free_cash_flow"],
                "counterargument": "Strong FCF does not eliminate multiple compression risk.",
                "implication": "FCF context is required before AVGO can be considered publishable.",
            },
            {
                "section": "Catalysts & Triggers",
                "kind": "current_period",
                "evidence_type": "guidance",
                "text": (
                    f"AVGO's Q2 revenue guide of {_money(q2_guide)} and AI semiconductor guide of {_money(ai_guide)} are the forward catalysts that must support the Hold rating."
                ),
                "metrics": ["q2_revenue_guidance", "q2_ai_semiconductor_revenue_guidance"],
                "counterargument": "Guidance can disappoint if AI order timing or VMware integration economics weaken.",
                "implication": "A more bullish stance requires Q2 guidance to convert into reported revenue and FCF.",
            },
        ])
    elif ticker == "DDOG":
        revenue = _canonical_value(canonical_financials, "revenue")
        ocf = _canonical_value(canonical_financials, "operating_cash_flow")
        fcf = _canonical_value(canonical_financials, "free_cash_flow")
        fcf_metric = "free_cash_flow"
        fcf_label = "company-defined FCF"
        if fcf is None:
            fcf = fundamentals.free_cash_flow_ttm
            fcf_metric = "free_cash_flow_ttm"
            fcf_label = "TTM FCF"
        sbc = _canonical_value(canonical_financials, "sbc")
        cash = _canonical_value(canonical_financials, "cash_and_equivalents")
        securities = _canonical_value(canonical_financials, "marketable_securities")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"DDOG's FY2025 revenue of {_money(revenue)} anchors the observability-platform demand story; "
                    "the platform case is credible only if usage growth and AI monitoring demand convert into durable cash generation."
                ),
                "metrics": ["revenue"],
                "counterargument": "Usage-based observability revenue can slow if cloud optimization pressure returns.",
                "implication": "A more constructive stance needs revenue durability rather than generic software multiple language.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"DDOG reported operating cash flow of {_money(ocf)} and company-defined free cash flow of {_money(fcf)}, "
                    "which makes FCF conversion the core support for any Hold-to-Accumulate path."
                ),
                "metrics": ["operating_cash_flow", "free_cash_flow"],
                "counterargument": "Company-defined FCF still has to be weighed against SBC and reinvestment needs.",
                "implication": "Do not upgrade without clean IR reconciliation and sustained FCF conversion.",
            },
            {
                "section": "Key Risks",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"DDOG's FY2025 SBC of {_money(sbc)}, cash of {_money(cash)} and marketable securities of {_money(securities)} define the equity-quality tradeoff: "
                    "liquidity is strong, but compensation intensity still matters for shareholders."
                ),
                "metrics": ["sbc", "cash_and_equivalents", "marketable_securities"],
                "counterargument": "High liquidity can fund innovation, but it does not erase dilution risk.",
                "implication": "Keep the rating disciplined unless growth, FCF and dilution improve together.",
            },
        ])
    elif ticker == "CRM":
        revenue = _canonical_value(canonical_financials, "revenue")
        ocf = _canonical_value(canonical_financials, "operating_cash_flow")
        fcf = _canonical_value(canonical_financials, "free_cash_flow")
        fcf_metric = "free_cash_flow"
        fcf_label = "company-defined FCF"
        if fcf is None:
            fcf = fundamentals.free_cash_flow_ttm
            fcf_metric = "free_cash_flow_ttm"
            fcf_label = "TTM FCF"
        sbc = _canonical_value(canonical_financials, "sbc")
        cash = _canonical_value(canonical_financials, "cash_and_equivalents")
        securities = _canonical_value(canonical_financials, "marketable_securities")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"CRM's FY2026 revenue of {_money(revenue)} gives the enterprise-SaaS base enough scale for Agentforce and Data Cloud to matter, "
                    "but the rating still depends on whether AI adoption can reaccelerate durable subscription growth."
                ),
                "metrics": ["revenue"],
                "counterargument": "Large revenue scale can coexist with slower organic growth or AI adoption disappointment.",
                "implication": "A stronger stance needs evidence that Data Cloud and Agentforce are improving growth quality.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"CRM reported operating cash flow of {_money(ocf)} and {fcf_label} of {_money(fcf)}, "
                    "so FCF durability and capital return are the main reasons not to take a more bearish view."
                ),
                "metrics": ["operating_cash_flow", fcf_metric],
                "counterargument": "FCF strength needs clean reconciliation and should not mask slowing subscription demand.",
                "implication": "Hold can improve only if FCF durability comes with better growth evidence.",
            },
            {
                "section": "Catalysts & Triggers",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"CRM's FY2026 SBC of {_money(sbc)}, cash of {_money(cash)} and marketable securities of {_money(securities)} frame the capital-return debate: "
                    "shareholder returns are more compelling if AI/product execution improves without higher dilution."
                ),
                "metrics": ["sbc", "cash_and_equivalents", "marketable_securities"],
                "counterargument": "Buybacks or cash balances do not solve weak growth if AI products disappoint.",
                "implication": "Upgrade requires cleaner growth plus FCF, not capital return alone.",
            },
        ])
    elif ticker == "AAPL":
        q_revenue = _canonical_value(canonical_financials, "current_q_revenue")
        eps = _canonical_value(canonical_financials, "current_q_eps")
        ocf = _canonical_value(canonical_financials, "current_q_operating_cash_flow")
        buyback = _canonical_value(canonical_financials, "buyback_authorization")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"AAPL's latest-quarter revenue of {_money(q_revenue)} and EPS of {_per_share(eps)} support the ecosystem-quality thesis."
                ),
                "metrics": ["current_q_revenue", "current_q_eps"],
                "counterargument": "Revenue and EPS strength still depend on iPhone cycle, Services mix and regulatory pressure.",
                "implication": "Accumulate should be staged rather than valuation-insensitive.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"AAPL generated operating cash flow above {_money(ocf)} in the latest quarter, reinforcing the capital-return quality of the franchise."
                ),
                "metrics": ["current_q_operating_cash_flow"],
                "counterargument": "OCF strength cannot fully offset product-cycle risk if growth slows.",
                "implication": "Cash generation supports Accumulate on pullbacks, not aggressive chasing.",
            },
            {
                "section": "Catalysts & Triggers",
                "kind": "current_period",
                "evidence_type": "guidance",
                "text": (
                    f"AAPL's additional buyback authorization of {_money(buyback)} is a shareholder-return catalyst that can support EPS resilience."
                ),
                "metrics": ["buyback_authorization"],
                "counterargument": "Buybacks do not solve AI positioning or regulatory platform risk.",
                "implication": "A stronger rating needs capital returns plus clearer product and AI momentum.",
            },
        ])
    elif ticker == "NFLX":
        q_revenue = _canonical_value(canonical_financials, "current_q_revenue")
        op_income = _canonical_value(canonical_financials, "operating_income")
        op_margin = _canonical_value(canonical_financials, "operating_margin")
        q_fcf = _canonical_value(canonical_financials, "current_q_free_cash_flow")
        specs.extend([
            {
                "section": "Business & Segment Context",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"NFLX's Q1 revenue of {_money(q_revenue)} shows that the streaming scale and monetization base remain strong."
                ),
                "metrics": ["current_q_revenue"],
                "counterargument": "Revenue scale can be offset if engagement weakens or content costs rise.",
                "implication": "Revenue quality supports Hold rather than a bearish rating.",
            },
            {
                "section": "Fundamental Analysis",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"NFLX's Q1 operating income of {_money(op_income)} and operating margin of {_pct(op_margin)} show strong current-period profitability."
                ),
                "metrics": ["operating_income", "operating_margin"],
                "counterargument": "Margin strength can fade if content spend or competition accelerates.",
                "implication": "A more bullish stance needs sustained margin durability, not just one strong quarter.",
            },
            {
                "section": "Catalysts & Triggers",
                "kind": "current_period",
                "evidence_type": "financial_metric",
                "text": (
                    f"NFLX's Q1 FCF of {_money(q_fcf)} is the key cash-flow proof point for whether operating leverage is translating into shareholder value."
                ),
                "metrics": ["current_q_free_cash_flow"],
                "counterargument": "FCF can be period-sensitive if content cash timing changes.",
                "implication": "Hold remains appropriate until FCF durability and ad-tier execution are clearer.",
            },
        ])
    specs = [
        spec
        for spec in specs
        if all(
            _claim_metric_available(metrics, canonical_financials, metric_name)
            for metric_name in spec.get("metrics", [])
        )
    ]
    if not specs:
        current_revenue = _latest_current_period_metric(
            canonical_financials,
            "revenue",
        )
        if current_revenue is not None:
            available_metrics = {
                metric_name: _metric_for_same_reported_period(
                    canonical_financials,
                    metric_name,
                    current_revenue,
                )
                for metric_name in (
                    "operating_income",
                    "gross_profit",
                    "net_income",
                    "eps_diluted",
                )
            }
            if (
                available_metrics["operating_income"] is not None
                and available_metrics["net_income"] is not None
            ):
                candidate_names = ("operating_income", "net_income")
            else:
                candidate_names = (
                    "gross_profit",
                    "net_income",
                    "operating_income",
                    "eps_diluted",
                )
            period_metrics = [("revenue", current_revenue)]
            for metric_name in candidate_names:
                metric = available_metrics[metric_name]
                if metric is not None:
                    period_metrics.append((metric_name, metric))
                if len(period_metrics) == 3:
                    break
            if len(period_metrics) == 3:
                metric_names = [metric_name for metric_name, _ in period_metrics]
                metric_labels = {
                    "revenue": "revenue",
                    "operating_income": "operating income",
                    "gross_profit": "gross profit",
                    "net_income": "net income",
                    "eps_diluted": "diluted EPS",
                }
                metric_phrases = [
                    f"{metric_labels[metric_name]} of "
                    f"{_money(metric.value, currency)}"
                    for metric_name, metric in period_metrics
                ]
                period_result_text = (
                    ", ".join(metric_phrases[:-1])
                    + f" and {metric_phrases[-1]}"
                )
                growth_candidates = [
                    (
                        "revenue",
                        "current_period_revenue_growth_yoy",
                        "revenue",
                        metrics.fundamentals.current_period_revenue_growth_yoy,
                    ),
                    (
                        "operating_income",
                        "current_period_operating_income_growth_yoy",
                        "operating income",
                        metrics.fundamentals.current_period_operating_income_growth_yoy,
                    ),
                    (
                        "net_income",
                        "current_period_net_income_growth_yoy",
                        "net income",
                        metrics.fundamentals.current_period_net_income_growth_yoy,
                    ),
                ]
                available_growth = [
                    (growth_metric, label, value)
                    for source_metric, growth_metric, label, value in growth_candidates
                    if source_metric in metric_names and value is not None
                ]
                if available_growth:
                    comparison_period = (
                        "fiscal year"
                        if current_revenue.period_bucket == "annual"
                        else "quarter"
                    )
                    growth_phrases = [
                        _yoy_change_phrase(label, value)
                        for _, label, value in available_growth
                    ]
                    if len(growth_phrases) == 1:
                        growth_text = growth_phrases[0]
                    else:
                        growth_text = (
                            ", ".join(growth_phrases[:-1])
                            + f" and {growth_phrases[-1]}"
                        )
                    comparison_text = (
                        f" Against the matching prior-year {comparison_period}, "
                        f"{growth_text}. These are arithmetic "
                        "year-over-year comparisons, not causal conclusions."
                    )
                    claim_metrics = [
                        *metric_names,
                        *(growth_metric for growth_metric, _, _ in available_growth),
                    ]
                    comparison_counterargument = (
                        "One year-over-year comparison does not establish a "
                        "durable multi-period trend."
                    )
                else:
                    comparison_period = (
                        "fiscal year"
                        if current_revenue.period_bucket == "annual"
                        else "quarter"
                    )
                    comparison_text = (
                        " These are current-period results; they do not by "
                        "themselves establish growth without a matching "
                        f"prior-year {comparison_period}."
                    )
                    claim_metrics = metric_names
                    comparison_counterargument = (
                        "A single reported period does not establish a durable "
                        "trend."
                    )
                specs.append(
                    {
                        "section": "Fundamental Analysis",
                        "kind": "current_period",
                        "evidence_type": "financial_metric",
                        "text": (
                            f"{ticker}'s latest reported period "
                            f"{_display_period(current_revenue)} includes "
                            f"{period_result_text}."
                            f"{comparison_text}"
                        ),
                        "metrics": claim_metrics,
                        "comparison_period": (
                            "fiscal_year"
                            if current_revenue.period_bucket == "annual"
                            else "quarter"
                        ),
                        "counterargument": comparison_counterargument,
                        "implication": (
                            "Use the latest period as current context, not as "
                            "standalone evidence for an upgrade or downgrade."
                        ),
                    }
                )
    return specs


def _early_commercial_capital_intensive_specs(
    ticker: str,
    metrics: MetricsPacket,
    canonical_financials: CanonicalFinancials,
) -> list[dict[str, object]]:
    q_revenue = _canonical_value(canonical_financials, "current_q_revenue")
    backlog = _canonical_value(canonical_financials, "backlog")
    product_revenue = _canonical_value(canonical_financials, "space_systems_revenue")
    service_revenue = _canonical_value(canonical_financials, "launch_services_revenue")
    electron_contracts = _canonical_value(canonical_financials, "electron_haste_new_contracts")
    neutron_contracts = _canonical_value(canonical_financials, "neutron_new_contracts")
    launch_manifest = _canonical_value(canonical_financials, "launch_manifest_contracts")
    q_fcf = _canonical_value(canonical_financials, "current_q_free_cash_flow")
    operating_loss = _canonical_value(canonical_financials, "operating_loss")
    revenue_growth = _canonical_value(canonical_financials, "full_year_revenue_growth")
    cash = _canonical_value(canonical_financials, "cash_and_marketable_securities")
    f = metrics.fundamentals
    v = metrics.valuation
    growth_clause = (
        f"company current-period evidence reports full-year revenue growth of {_pct(revenue_growth)} year over year; "
        if revenue_growth is not None
        else ""
    )

    if not (
        q_revenue is not None
        and backlog is not None
        and f.revenue_ttm is not None
        and f.free_cash_flow_ttm is not None
        and f.free_cash_flow_ttm < 0
        and v.ev_to_sales is not None
        and v.ev_to_sales > 20
    ):
        return []

    specs: list[dict[str, object]] = [
        {
            "section": "Business Model Reality",
            "kind": "current_period",
            "evidence_type": "financial_metric",
            "text": (
                f"{ticker} is an early-commercial capital-intensive technology company: latest quarterly revenue of {_money(q_revenue)} "
                f"and TTM revenue of {_money(f.revenue_ttm)} show real commercial scale, while FCF of {_money(f.free_cash_flow_ttm)} keeps the report in manual-review territory."
            ),
            "metrics": ["current_q_revenue", "revenue_ttm", "free_cash_flow_ttm"],
            "counterargument": "Revenue scale and backlog do not prove durable margins or valuation support.",
            "implication": "Do not treat this as a pre-commercial story, but do not publish a clean bullish view without FCF proof.",
        },
        {
            "section": "Revenue Scale and Backlog",
            "kind": "current_period",
            "evidence_type": "financial_metric",
            "text": (
                f"{ticker} has TTM revenue of {_money(f.revenue_ttm)}, latest quarterly revenue of {_money(q_revenue)}, "
                f"and backlog above {_money(backlog)}; backlog is material relative to the current revenue base."
            ),
            "metrics": ["revenue_ttm", "current_q_revenue", "backlog"],
            "counterargument": "Backlog still has timing, conversion and program-risk uncertainty.",
            "implication": "Backlog is material commercial evidence, not automatic valuation support.",
        },
        {
            "section": "Contract / Backlog Materiality",
            "kind": "current_period",
            "evidence_type": "financial_metric",
            "text": (
                f"Contract value/backlog materiality is central: backlog of {_money(backlog)} must be judged against annual revenue / TTM revenue of {_money(f.revenue_ttm)}, "
                "market cap, delivery revenue timing, recurring versus one-off programmatic revenue, and commercial versus government or prototype mix."
            ),
            "metrics": ["backlog", "revenue_ttm", "close"],
            "counterargument": "A large backlog can still convert slowly or carry program-specific margin risk.",
            "implication": "Classify backlog as real evidence, while requiring conversion and timing proof before rating upside.",
        },
        {
            "section": "Segment Mix",
            "kind": "current_period",
            "evidence_type": "financial_metric",
            "text": (
                f"Segment mix shows platform scaling rather than a single prototype story: Space Systems/product revenue was {_money(product_revenue)} "
                f"and Launch Services/service revenue was {_money(service_revenue)} in the latest quarter."
            ),
            "metrics": ["product_revenue", "service_revenue"],
            "counterargument": "Segment revenue mix still needs margin and repeatability evidence.",
            "implication": "Use segment mix to separate commercial execution from pure milestone narrative.",
        },
        {
            "section": "Execution Milestones",
            "kind": "current_period",
            "evidence_type": "financial_metric",
            "text": (
                f"Execution milestones remain decisive: {_plain_number(electron_contracts)} Electron/HASTE contracts, "
                f"{_plain_number(launch_manifest)} contracted launch-manifest missions and {_plain_number(neutron_contracts)} Neutron contracts show cadence, "
                "but Neutron development and timing risk still block a clean Buy/Accumulate view."
            ),
            "metrics": ["electron_haste_new_contracts", "launch_manifest_contracts", "neutron_new_contracts"],
            "counterargument": "Contract wins do not remove development, launch or delivery risk.",
            "implication": "Treat technical execution as gating evidence, not as standalone upside.",
        },
        {
            "section": "FCF Path",
            "kind": "current_period",
            "evidence_type": "financial_metric",
            "text": (
                f"The FCF path is still negative: TTM FCF is {_money(f.free_cash_flow_ttm)}, latest-quarter FCF is {_money(q_fcf)}, "
                f"and operating loss is {_money(operating_loss)}."
            ),
            "metrics": ["free_cash_flow_ttm", "current_q_free_cash_flow", "operating_loss"],
            "counterargument": "Investment-phase losses can be acceptable if backlog converts into profitable revenue.",
            "implication": "Keep external display at Hold Pending FCF and Execution Evidence until cash conversion improves.",
        },
        {
            "section": "Capital Intensity",
            "kind": "current_period",
            "evidence_type": "financial_metric",
            "text": (
                f"Capital intensity is visible in negative current-quarter FCF of {_money(q_fcf)} despite cash and marketable securities of {_money(cash)}; "
                "major development programs can extend the time needed to prove durable FCF."
            ),
            "metrics": ["current_q_free_cash_flow", "cash_and_marketable_securities"],
            "counterargument": "Liquidity can fund development, but it does not by itself validate equity valuation.",
            "implication": "Cash runway reduces distress risk but does not remove execution risk.",
        },
        {
            "section": "Valuation vs Revenue/Backlog",
            "kind": "current_period",
            "evidence_type": "valuation_metric",
            "text": (
                f"Valuation is stretched versus current scale: EV/Sales is {_multiple(v.ev_to_sales)}, while backlog of {_money(backlog)} is not enough by itself to offset market-cap expectations."
            ),
            "metrics": ["ev_to_sales", "enterprise_value", "revenue_ttm", "backlog"],
            "counterargument": "High EV/Sales can persist if growth and execution exceed expectations.",
            "implication": "High valuation blocks clean Buy/Accumulate unless backlog conversion and FCF path improve.",
        },
        {
            "section": "Technical Setup only as timing",
            "kind": "current_period",
            "evidence_type": "technical_metric",
            "text": (
                f"Technical setup is timing evidence only: close {_plain_number(metrics.technical.close)}, RSI {_number(metrics.technical.rsi_14)} "
                "and high volatility should not dominate the fundamental classification."
            ),
            "metrics": ["close", "rsi_14"],
            "counterargument": "Momentum can support position timing, not business-quality proof.",
            "implication": "Technical claims must stay secondary to FCF, backlog conversion and execution evidence.",
        },
        {
            "section": "Final Internal View",
            "kind": "current_period",
            "evidence_type": "rating",
            "text": (
                f"Final internal view for {ticker} should remain Hold/manual review: {growth_clause}backlog and contracts are real, "
                "but negative FCF, execution milestones and valuation intensity require more evidence before external publication."
            ),
            "metrics": ["full_year_revenue_growth", "backlog", "free_cash_flow_ttm", "close"],
            "counterargument": "A more bearish published stance would need evidence that commercial execution is failing, not just that valuation is high.",
            "implication": "Use Manual Review / Hold Pending FCF and Execution Evidence rather than a reflexively bearish display.",
        },
    ]
    return specs
