from __future__ import annotations

from typing import Iterable, Optional

from research_agent.decision.decision_packet import DecisionPacket
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.reconciliation.canonical_financials import CanonicalFinancials
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


MIN_ANALYST_CLAIMS = 15


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
    company_specific = [
        claim
        for claim in claim_list
        if not _is_generic_meta_claim(claim) and _has_company_specific_driver(claim)
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
        "ticker_specific_kpi_claim_count": ticker_kpi_count,
        "final_rating_rationale_quality": _final_rating_rationale_quality(claim_list),
        "mechanical_rating_language_count": sum(1 for claim in claim_list if _has_mechanical_rating_language(claim)),
        "generic_claim_ratio": (generic_count / total) if total else 0.0,
        "company_specific_claim_count": len(company_specific),
        "valuation_specific_claim_count": len(valuation_specific),
        "technical_specific_claim_count": len(technical_specific),
        "rating_rationale_claim_count": len(rating_rationale),
    }


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

    def build_candidates(self) -> list[ResearchClaim]:
        ticker = self.data_packet.ticker.upper()
        profile = _company_profile(ticker)
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
                "source quality and the technical setup remain separate constraints."
            ),
            core_rating_metrics,
            "high",
            "high",
            implication=f"The action language should stay consistent with the {preferred} stance.",
        )

        for current_claim in _current_period_claim_specs(
            ticker,
            self.metrics,
            self.canonical,
            currency=self.data_packet.price_basis.currency,
        ):
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

        self.add(
            "Fundamental Analysis",
            "fundamental",
            "financial_metric",
            f"{ticker} has revenue TTM of {self._money(self.metrics.fundamentals.revenue_ttm)}, so the business discussion should focus on {profile['business_driver']} rather than generic scale language.",
            ["revenue_ttm"],
            "high",
            "high",
            counterargument="Revenue scale alone does not prove attractive returns or valuation discipline.",
            implication="Use revenue evidence as context, not as a standalone buy signal.",
        )
        self.add(
            "Fundamental Analysis",
            "fundamental",
            "financial_metric",
            f"FCF TTM is {self._money(self.metrics.fundamentals.free_cash_flow_ttm)}, making cash conversion a direct rating input for {ticker}.",
            ["free_cash_flow_ttm"],
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
            self.add(
                "Fundamental Analysis",
                "fundamental",
                "financial_metric",
                (
                    "TTM shareholder distributions are "
                    f"{self._money(self.metrics.fundamentals.shareholder_distributions_ttm)}; "
                    "distributions minus FCF are "
                    f"{self._money(self.metrics.fundamentals.shareholder_distributions_minus_fcf_ttm)}. "
                    "This is an arithmetic comparison and does not identify a "
                    "funding source."
                ),
                [
                    "shareholder_distributions_ttm",
                    "shareholder_distributions_minus_fcf_ttm",
                ],
                "high",
                "high",
                counterargument=(
                    "A positive difference does not by itself prove debt-funded "
                    "or cash-funded distributions."
                ),
                implication=(
                    "Capital-return sustainability should be discussed without "
                    "inventing a financing bridge."
                ),
            )
        self.add(
            "Fundamental Analysis",
            "fundamental",
            "financial_metric",
            f"SBC/Revenue is {_pct(self.metrics.fundamentals.sbc_to_revenue)}, which should be interpreted through {profile['sector_lens']} rather than a one-size-fits-all compensation lens.",
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

        self.add(
            "Valuation / Multiples",
            "valuation",
            "valuation_metric",
            f"Valuation is framed by EV/Sales of {_multiple(self.metrics.valuation.ev_to_sales)}; this directly limits how aggressive the {preferred} stance should be.",
            ["ev_to_sales", "enterprise_value", "revenue_ttm"],
            "medium",
            "high",
            counterargument="Packet-derived valuation can still be blocked by sanity guards when source reconciliation is suspect.",
            implication="Do not upgrade rating solely from valuation language if audit has financial-sanity errors.",
        )
        self.add(
            "Valuation / Multiples",
            "valuation",
            "valuation_metric",
            f"For {ticker}, P/FCF is {_multiple(self.metrics.valuation.price_to_fcf)} and should be read against {profile['valuation_lens']}; missing or extreme cash-flow multiples should reduce conviction rather than invite a stronger rating.",
            ["price_to_fcf", "market_cap", "free_cash_flow_ttm"],
            "medium",
            "medium",
            implication="The rating should stay conservative when multiples are expensive, missing or flagged.",
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
                f"{_number(self.metrics.technical.rsi_14)}, creating timing "
                "risk if price cannot reclaim trend support."
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

        self.add(
            "Bull Case",
            "bull",
            "financial_metric",
            (
                "The bull case combines revenue of "
                f"{self._money(self.metrics.fundamentals.revenue_ttm)} with "
                "available FCF evidence. A more constructive rating requires "
                "both inputs to remain validated and valuation or technical "
                "constraints to improve."
            ),
            ["revenue_ttm", "free_cash_flow_ttm"],
            "medium",
            "medium",
            counterargument="Strong scale does not resolve valuation or reconciliation anomalies.",
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

        if self.metrics.fundamentals.free_cash_flow_ttm is not None:
            sbc_to_revenue = self.metrics.fundamentals.sbc_to_revenue
            if sbc_to_revenue is None:
                sbc_context = (
                    "SBC/Revenue is unavailable and therefore cannot support "
                    "the risk case."
                )
                bear_metrics = ["free_cash_flow_ttm"]
            else:
                sbc_context = (
                    f"SBC/Revenue of {_pct(sbc_to_revenue)} is a separate "
                    "dilution input, not proof of deterioration."
                )
                bear_metrics = ["free_cash_flow_ttm", "sbc_to_revenue"]
            self.add(
                "Bear Case",
                "bear",
                "financial_metric",
                (
                    f"The bear case is that {profile['bear_driver']} could "
                    f"outweigh the available FCF evidence. {sbc_context}"
                ),
                bear_metrics,
                "medium",
                "high",
                implication=(
                    "Manual review remains appropriate when financial-sanity "
                    "guards fire."
                ),
            )
        self.add(
            "Bear Case",
            "bear",
            "valuation_metric",
            f"Valuation risk for {ticker} is a discipline constraint; expensive or missing EV/Sales and P/FCF context should not be translated into a blocked rating.",
            ["revenue_ttm", "free_cash_flow_ttm"],
            "medium",
            "medium",
            implication="Avoid a more bearish research label when the evidence supports only a Hold or tactical-risk stance.",
        )

        self.add(
            "Key Risks",
            "risk",
            "risk",
            f"Validation and audit issues are part of the {ticker} research view; any blocking data issue should override a superficially complete report.",
            ["close"],
            "high",
            "high",
            implication="Blocking audit errors should keep the report in manual review.",
        )
        self.add(
            "Key Risks",
            "risk",
            "financial_metric",
            f"Source disagreement or current-period mismatch can reduce conviction for {ticker}, especially where revenue {self._money(self.metrics.fundamentals.revenue_ttm)} is a key valuation denominator.",
            ["revenue_ttm", "free_cash_flow_ttm"],
            "medium",
            "medium",
            implication="Source-quality limitations belong in the final action plan.",
        )

        self.add(
            "Catalysts & Triggers",
            "catalyst",
            "price_data",
            (
                f"Catalysts for {ticker} at the validated close of "
                f"{self._money(self.metrics.technical.close)} should be limited "
                "to confirmed packet inputs; missing earnings or forward "
                "company data should be stated as unavailable rather than "
                "converted into event-risk claims."
            ),
            ["close"],
            "high",
            "medium",
            implication="If earnings are unavailable, the report should state that limitation rather than inventing timing.",
        )
        self.add(
            "Catalysts & Triggers",
            "catalyst",
            "technical_metric",
            (
                "Trigger language should use evidence-backed levels such as "
                f"50-SMA {self._money(self.metrics.technical.sma_50)} and "
                f"200-SMA {self._money(self.metrics.technical.sma_200)}, not "
                "unvalidated price targets."
            ),
            ["sma_50", "sma_200"],
            "medium",
            "medium",
            implication="Use confirmation language instead of hard price targets unless risk/reward levels are validated.",
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
            ),
            core_rating_metrics,
            "high",
            "high",
            counterargument=_final_rating_counterargument(preferred, self.metrics),
            implication=_final_rating_implication(ticker, preferred, self.metrics),
        )
        return self.claims

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
            matched.extend(self.ledger.find_by_metric(metric))
        deduped: dict[str, EvidenceItem] = {}
        for item in matched:
            deduped.setdefault(item.evidence_id, item)
        return list(deduped.values())


def _company_profile(ticker: str) -> dict[str, str]:
    profiles = {
        "QCOM": {
            "business_driver": "QCT/QTL mix, handset cyclicality, automotive/IoT diversification and management forecast quality",
            "sector_lens": "semiconductor-cycle, segment-mix and buyback context",
            "valuation_lens": "semiconductor cyclicality and earnings/FCF support",
            "bull_driver": "QCT recovery, QTL resilience, automotive/IoT diversification and disciplined capital returns",
            "bear_driver": "handset cyclicality, margin pressure, inventory risk or weak management forecast",
        },
        "NVDA": {
            "business_driver": "accelerated-computing demand, datacenter mix, supply constraints and AI capex durability",
            "sector_lens": "semiconductor margin, supply-chain and AI infrastructure context",
            "valuation_lens": "AI-infrastructure growth durability and cycle risk",
            "bull_driver": "datacenter AI demand and operating leverage",
            "bear_driver": "AI capex digestion, export limits, supply risk or multiple compression",
        },
        "GOOGL": {
            "business_driver": "Search, YouTube, Google Cloud growth, AI monetization and capex intensity",
            "sector_lens": "mega-cap ads/cloud margin and regulatory context",
            "valuation_lens": "ads/cloud growth, AI capex burden and cash-flow durability",
            "bull_driver": "Search monetization, Cloud growth and AI product integration",
            "bear_driver": "AI capex intensity, regulatory pressure or ad-growth slowdown",
        },
        "SNOW": {
            "business_driver": "product revenue, NRR, RPO, AI Data Cloud adoption and consumption growth",
            "sector_lens": "SaaS consumption, RPO/NRR, SBC and GAAP-vs-non-GAAP context",
            "valuation_lens": "consumption growth, FCF quality and SBC dilution",
            "bull_driver": "AI Data Cloud adoption, product revenue growth and RPO conversion",
            "bear_driver": "consumption slowdown, GAAP losses, SBC dilution or weak FY plan",
        },
        "DDOG": {
            "business_driver": "observability platform expansion, large-customer growth, AI monitoring and usage-based demand",
            "sector_lens": "SaaS usage growth, ARR/customer expansion, SBC and cash-conversion context",
            "valuation_lens": "growth durability versus high FCF multiple",
            "bull_driver": "observability consolidation, AI monitoring demand and large-customer expansion",
            "bear_driver": "usage slowdown, valuation compression, SBC dilution or weaker company forecast",
        },
        "CRM": {
            "business_driver": "Agentforce, Data Cloud, RPO/cRPO, margin discipline, buybacks and FY plan",
            "sector_lens": "enterprise SaaS margin, RPO, AI product adoption and capital-return context",
            "valuation_lens": "enterprise SaaS FCF durability, growth reacceleration and capital returns",
            "bull_driver": "Agentforce/Data Cloud adoption, RPO conversion and operating-margin discipline",
            "bear_driver": "AI adoption disappointment, integration risk, weak cRPO or FCF reconciliation gaps",
        },
    }
    if ticker in profiles:
        return profiles[ticker]
    if ticker in {"AAPL", "MSFT", "AMZN", "META", "NFLX"}:
        return {
            "business_driver": "mega-cap platform growth, AI/cloud investment, margin durability and regulatory risk",
            "sector_lens": "mega-cap platform, capex and capital-return context",
            "valuation_lens": "platform growth, FCF durability and capex intensity",
            "bull_driver": "platform scale, ecosystem monetization and operating leverage",
            "bear_driver": "regulatory pressure, capex intensity, growth deceleration or multiple compression",
        }
    if ticker in {"AMD", "AVGO", "INTC", "MU", "MRVL"}:
        return {
            "business_driver": "semiconductor cycle, product mix, inventory, gross margin and management forecast quality",
            "sector_lens": "semiconductor-cycle, segment-mix and balance-sheet context",
            "valuation_lens": "cycle-adjusted earnings and FCF support",
            "bull_driver": "cycle recovery, AI/datacenter mix and margin leverage",
            "bear_driver": "inventory correction, gross-margin pressure or weak management forecast",
        }
    return {
        "business_driver": "available revenue, cash-flow and source-quality evidence",
        "sector_lens": "sector-specific quality and valuation context",
        "valuation_lens": "revenue scale, cash-flow evidence and risk context",
        "bull_driver": "revenue scale and available cash-flow evidence",
        "bear_driver": "source-quality issues, valuation risk or technical weakness",
    }


def _money(value: Optional[float], currency: str = "USD") -> str:
    if value is None:
        return "not available in evidence set"
    currency = str(currency or "USD").strip().upper()
    if abs(value) >= 1_000_000_000:
        amount = f"{value / 1_000_000_000:.2f}B"
    elif abs(value) >= 1_000_000:
        amount = f"{value / 1_000_000:.1f}M"
    else:
        amount = f"{value:.2f}"
    return f"${amount}" if currency == "USD" else f"{amount} {currency}"


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


def _technical_interpretation(metrics: MetricsPacket) -> str:
    technical = metrics.technical
    if technical.rsi_14 is not None and technical.rsi_14 > 75:
        return "an overbought setup that favors patience or tactical trimming over immediate full accumulation"
    if technical.close and technical.sma_200 and technical.close < technical.sma_200:
        return "a damaged trend that lacks confirmation of recovery"
    if technical.close and technical.sma_50 and technical.close > technical.sma_50:
        return "constructive momentum but still requires valuation and risk discipline"
    return "a mixed setup that should not override validated fundamentals"


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
        if _is_current_period_metric(metric.period, metric.source_ids)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda metric: (
            metric.end_date or "",
            {"high": 3, "medium": 2, "low": 1}.get(metric.confidence, 0),
        ),
    )


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
) -> str:
    evidence_anchor = _core_rating_evidence_text(metrics, currency)
    return (
        f"We rate {ticker} {preferred} at the validated close of "
        f"{_money(metrics.technical.close, currency)}. The evidence anchors are "
        f"{evidence_anchor}; source quality, valuation and technical risk limit "
        "the case for a more bullish rating."
    )


def _core_rating_metric_refs(metrics: MetricsPacket) -> list[str]:
    metric_refs = ["close"]
    for metric_name, value in (
        ("revenue_ttm", metrics.fundamentals.revenue_ttm),
        ("free_cash_flow_ttm", metrics.fundamentals.free_cash_flow_ttm),
        ("ev_to_sales", metrics.valuation.ev_to_sales),
    ):
        if value is not None:
            metric_refs.append(metric_name)
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
    return ", ".join(anchors) if anchors else "the available validated metrics"


def _final_rating_counterargument(preferred: str, metrics: MetricsPacket) -> str:
    if preferred in {"Accumulate", "Buy"}:
        return "A more bearish rating would require evidence that cash generation, technical confirmation or source quality has broken down."
    if preferred in {"Tactical Trim", "Tactical Underweight", "Underweight"}:
        return "A more bullish rating would require current-period KPI acceleration plus valuation or technical confirmation."
    return "A more bullish rating needs cleaner valuation and technical confirmation; a more bearish rating needs evidence of deteriorating fundamentals or unresolved data errors."


def _final_rating_implication(ticker: str, preferred: str, metrics: MetricsPacket) -> str:
    if preferred == "Accumulate":
        return f"An Accumulate research stance for {ticker} requires confirmed KPI acceleration and valuation discipline."
    if preferred in {"Tactical Trim", "Tactical Underweight"}:
        return f"The tactical-risk stance for {ticker} remains until valuation, trend or current-period KPIs improve."
    return f"The Hold research stance for {ticker} remains until valuation, technical setup or current-period KPI evidence changes."


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
    if not specs:
        current_revenue = _latest_current_period_metric(
            canonical_financials,
            "revenue",
        )
        if current_revenue is not None:
            operating_income = canonical_financials.get_metric(
                "operating_income",
                period=current_revenue.period,
            )
            net_income = canonical_financials.get_metric(
                "net_income",
                period=current_revenue.period,
            )
            if operating_income is not None and net_income is not None:
                specs.append(
                    {
                        "section": "Fundamental Analysis",
                        "kind": "current_period",
                        "evidence_type": "financial_metric",
                        "text": (
                            f"{ticker}'s latest reported period "
                            f"{current_revenue.period} includes revenue of "
                            f"{_money(current_revenue.value, currency)}, "
                            "operating income of "
                            f"{_money(operating_income.value, currency)} and "
                            f"net income of {_money(net_income.value, currency)}. "
                            "These are current-period results; they do not by "
                            "themselves establish growth without a comparable "
                            "prior period."
                        ),
                        "metrics": [
                            "current_q_revenue",
                            "operating_income",
                            "net_income",
                        ],
                        "counterargument": (
                            "A single reported period does not establish a "
                            "durable trend."
                        ),
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
