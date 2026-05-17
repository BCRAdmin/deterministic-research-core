from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Union

from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.evidence.evidence_validator import validate_ledger
from research_agent.research_core.models.claims import ResearchClaim


def render_evidence_report(
    ledger: EvidenceLedger,
    required_metrics: Optional[list[str]] = None,
    claims: Optional[Iterable[ResearchClaim]] = None,
) -> str:
    claims = list(claims or [])
    issues = validate_ledger(ledger, required_metrics=required_metrics, claims=claims)
    lines = [
        f"# Evidence Report - {ledger.ticker}",
        "",
        "## Hard Metrics",
        "",
        "| Metric | Value | Period | Basis | Source Type | Source ID | Evidence ID | Confidence | Status |",
        "|---|---:|---|---|---|---|---|---|---|",
    ]
    metrics = required_metrics or _metrics_from_ledger(ledger)
    for metric in metrics:
        items = ledger.find_by_metric(metric)
        if not items:
            lines.append(f"| {metric} | n/a | n/a | n/a | Missing |")
            continue
        best = sorted(items, key=lambda item: (item.value is None, item.authority_rank, _source_display_priority(item)))[0]
        status = "OK" if best.authority_rank <= 2 else "Warning"
        value = _fmt_value(best.value, best.unit)
        basis = _basis_for_item(best)
        lines.append(
            f"| {metric} | {value} | {best.period or 'n/a'} | {basis} | {best.source_type} | "
            f"{best.source_id} | {best.evidence_id} | {best.confidence} | {status} |"
        )

    if issues:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{issue['code']}`: {issue['message']}" for issue in issues)
    else:
        lines.extend(["", "## Warnings", "", "- No evidence warnings."])
    return "\n".join(lines) + "\n"


def save_evidence_report(markdown: str, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return target


def _metrics_from_ledger(ledger: EvidenceLedger) -> list[str]:
    metrics: list[str] = []
    for item in ledger.evidence_items:
        metrics.extend(item.supports_metrics)
    return list(dict.fromkeys(metrics))


def _fmt_value(value: Optional[float], unit: Optional[str]) -> str:
    if value is None:
        return "n/a"
    if unit == "percent":
        return f"{value:.1%}"
    if unit in {"usd", "usd_per_share"}:
        return f"{value:,.2f}"
    return f"{value:,.2f}"


def _basis_for_item(item) -> str:
    if item.claim_type == "guidance":
        return "company-defined"
    if item.source_type in {"market_data_provider", "finviz", "stockanalysis"}:
        return "consensus"
    if "non-gaap" in item.statement.lower():
        return "non-GAAP"
    if "derived" in item.evidence_id.lower() or "derived" in item.statement.lower():
        return "GAAP-derived"
    return "GAAP" if item.source_type == "sec_filing" else "company-defined"


def _source_display_priority(item) -> int:
    if item.source_type in {"earnings_release", "company_ir", "official_press_release"}:
        return 0
    if item.source_type == "sec_filing":
        return 1
    return 2
