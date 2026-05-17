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


class CompanyFactsParser:
    def __init__(self, ticker: str, cik: str, companyfacts_json: Dict[str, Any]):
        self.ticker = ticker.upper()
        self.cik = str(cik).zfill(10)
        self.data = companyfacts_json

    def _get_us_gaap_facts(self, concept: str) -> list[dict]:
        facts = (
            self.data
            .get("facts", {})
            .get("us-gaap", {})
            .get(concept, {})
            .get("units", {})
        )
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
                parsed.append(
                    ParsedFact(
                        metric_name=metric_name,
                        value=float(row["val"]),
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
                    )
                )
        return parsed

    def _period_label(self, row: dict) -> str:
        fy = row.get("fy")
        fp = row.get("fp")
        if fy and fp:
            return f"FY{fy}_{fp}"
        return row.get("form") or "unknown"

    def latest_annual_fact(self, metric_name: str) -> Optional[ParsedFact]:
        facts = [
            fact for fact in self.get_facts_for_metric(metric_name)
            if fact.form == "10-K" and fact.fp in {"FY", "CY"}
        ]
        if not facts:
            facts = [
                fact for fact in self.get_facts_for_metric(metric_name)
                if fact.form == "10-K"
            ]
        if not facts:
            return None
        return sorted(facts, key=lambda fact: (fact.filed or "", fact.end or ""))[-1]

    def latest_quarterly_facts(self, metric_name: str, n: int = 4) -> List[ParsedFact]:
        facts = [
            fact for fact in self.get_facts_for_metric(metric_name)
            if fact.form in {"10-Q", "10-K"} and fact.fp not in {"FY", "CY"}
        ]
        facts = sorted(facts, key=lambda fact: (fact.end or "", fact.filed or ""))
        return facts[-n:]

    def to_evidence_item(self, fact: ParsedFact) -> EvidenceItem:
        return EvidenceItem(
            evidence_id=f"{self.ticker}_SEC_{fact.metric_name}_{fact.period}_{fact.accession or fact.filed}",
            ticker=self.ticker,
            claim_type="financial_metric",
            source_id=f"SEC_{self.cik}_{fact.accession or fact.filed}",
            source_type="sec_filing",
            authority_rank=rank_source("sec_filing"),
            statement=f"{self.ticker} reported {fact.metric_name} of {fact.value} {fact.unit} for {fact.period}.",
            value=fact.value,
            unit=fact.unit,
            period=fact.period,
            date=fact.end,
            supports_metrics=[fact.metric_name, _metrics_packet_name(fact.metric_name)],
            confidence="high",
        )


def _metrics_packet_name(metric_name: str) -> str:
    if metric_name in {"revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "capex", "sbc"}:
        return f"{metric_name}_ttm"
    return metric_name
