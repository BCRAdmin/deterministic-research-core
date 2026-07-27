from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.source_ranker import rank_source
from research_agent.sources.sec.xbrl_concepts import US_GAAP_CONCEPTS


@dataclass
class ParsedFact:
    metric_name: str
    value: float
    unit: str
    period: str
    fy: Optional[int]
    fp: Optional[str]
    form: Optional[str]
    filed: Optional[str]
    start: Optional[str]
    end: Optional[str]
    accession: Optional[str]
    source_type: str = "sec_filing"
    frame: Optional[str] = None
    concept: Optional[str] = None
    raw_value: Optional[float] = None
    normalization_note: Optional[str] = None


class CompanyFactsParser:
    def __init__(self, ticker: str, cik: str, companyfacts_json: Dict[str, Any]):
        self.ticker = ticker.upper()
        self.cik = str(cik).zfill(10)
        self.data = companyfacts_json

    def _get_us_gaap_facts(self, concept: str) -> list[dict]:
        facts = self.data.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {})
        all_facts = []
        for unit, rows in facts.items():
            for row in rows:
                normalized = dict(row)
                normalized["_unit"] = unit
                normalized["_concept"] = concept
                all_facts.append(normalized)
        return all_facts

    def get_facts_for_metric(self, metric_name: str) -> List[ParsedFact]:
        concepts = US_GAAP_CONCEPTS.get(metric_name, [])
        parsed: List[ParsedFact] = []
        for concept in concepts:
            for row in self._get_us_gaap_facts(concept):
                if "val" not in row:
                    continue
                raw_value = float(row["val"])
                value, normalization_note = self._normalize_metric_value(
                    metric_name,
                    row,
                    raw_value,
                )
                parsed.append(
                    ParsedFact(
                        metric_name=metric_name,
                        value=value,
                        unit=row.get("_unit", "unknown"),
                        period=self._period_label(row),
                        fy=row.get("fy"),
                        fp=row.get("fp"),
                        form=row.get("form"),
                        filed=row.get("filed"),
                        start=row.get("start"),
                        end=row.get("end"),
                        accession=row.get("accn"),
                        frame=row.get("frame"),
                        concept=row.get("_concept"),
                        raw_value=raw_value,
                        normalization_note=normalization_note,
                    )
                )
        return parsed

    def _normalize_metric_value(
        self,
        metric_name: str,
        row: dict,
        raw_value: float,
    ) -> tuple[float, Optional[str]]:
        if metric_name != "shares_diluted" or raw_value <= 0:
            return raw_value, None

        net_income = self._matching_fact_value("NetIncomeLoss", row)
        diluted_eps = self._matching_fact_value("EarningsPerShareDiluted", row)
        if net_income is None or diluted_eps in (None, 0):
            return raw_value, None
        if net_income * diluted_eps <= 0:
            return raw_value, None

        implied_shares = abs(net_income / diluted_eps)
        scales = (1.0, 1_000.0, 1_000_000.0, 1_000_000_000.0)
        scale = min(
            scales,
            key=lambda candidate: abs((raw_value * candidate) - implied_shares) / implied_shares,
        )
        relative_error = abs((raw_value * scale) - implied_shares) / implied_shares
        if scale == 1.0 or relative_error > 0.15:
            return raw_value, None

        normalized = raw_value * scale
        return normalized, (
            "Normalized SEC diluted-share scale by "
            f"{scale:g} after reconciling same-period net income and diluted EPS "
            f"(raw={raw_value:g}, implied_shares={implied_shares:g}, "
            f"relative_error={relative_error:.4f})."
        )

    def _matching_fact_value(self, concept: str, target: dict) -> Optional[float]:
        candidates = [
            row
            for row in self._get_us_gaap_facts(concept)
            if row.get("start") == target.get("start")
            and row.get("end") == target.get("end")
            and row.get("accn") == target.get("accn")
            and "val" in row
        ]
        if not candidates:
            candidates = [
                row
                for row in self._get_us_gaap_facts(concept)
                if row.get("start") == target.get("start")
                and row.get("end") == target.get("end")
                and row.get("form") == target.get("form")
                and "val" in row
            ]
        if not candidates:
            return None
        return float(candidates[-1]["val"])

    def _period_label(self, row: dict) -> str:
        fy = row.get("fy")
        fp = row.get("fp")
        if fy and fp:
            return f"FY{fy}_{fp}"
        return row.get("form") or "unknown"

    def latest_annual_fact(self, metric_name: str) -> Optional[ParsedFact]:
        facts = [
            fact
            for fact in self.get_facts_for_metric(metric_name)
            if fact.form == "10-K" and fact.fp in {"FY", "CY"}
        ]
        if not facts:
            facts = [fact for fact in self.get_facts_for_metric(metric_name) if fact.form == "10-K"]
        if not facts:
            return None
        return sorted(facts, key=lambda fact: (fact.filed or "", fact.end or ""))[-1]

    def latest_quarterly_facts(self, metric_name: str, n: int = 4) -> List[ParsedFact]:
        facts = [
            fact
            for fact in self.get_facts_for_metric(metric_name)
            if fact.form in {"10-Q", "10-K"} and fact.fp not in {"FY", "CY"}
        ]
        facts = sorted(facts, key=lambda fact: (fact.end or "", fact.filed or ""))
        return facts[-n:]

    def to_evidence_item(self, fact: ParsedFact) -> EvidenceItem:
        normalization_suffix = f" {fact.normalization_note}" if fact.normalization_note else ""
        return EvidenceItem(
            evidence_id=f"{self.ticker}_SEC_{fact.metric_name}_{fact.period}_{fact.accession or fact.filed}",
            ticker=self.ticker,
            claim_type="financial_metric",
            source_id=f"SEC_{self.cik}_{fact.accession or fact.filed}",
            source_type="sec_filing",
            authority_rank=rank_source("sec_filing"),
            statement=(
                f"{self.ticker} reported {fact.metric_name} of {fact.value} "
                f"{fact.unit} for {fact.period}.{normalization_suffix}"
            ),
            value=fact.value,
            unit=fact.unit,
            period=fact.period,
            date=fact.end,
            supports_metrics=[fact.metric_name, _metrics_packet_name(fact.metric_name)],
            confidence="high",
        )


def _metrics_packet_name(metric_name: str) -> str:
    if metric_name in {
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capex",
        "sbc",
    }:
        return f"{metric_name}_ttm"
    return metric_name
