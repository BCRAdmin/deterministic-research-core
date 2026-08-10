from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional, Union

from research_agent.reconciliation.canonical_financials import CanonicalFinancials
from research_agent.research_core.models.metrics_packet import MetricsPacket


def deduplicate_reconciliation_warnings(warnings: list[dict]) -> list[dict]:
    """Keep one copy of each exact warning while preserving source order."""

    unique: list[dict] = []
    seen: set[str] = set()
    for warning in warnings:
        identity = json.dumps(warning, sort_keys=True, separators=(",", ":"))
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(warning)
    return unique


def render_reconciliation_report(canonical: CanonicalFinancials, warnings: Optional[list[dict]] = None) -> str:
    warnings = warnings or []
    lines = [
        f"# Reconciliation Report - {canonical.ticker}",
        "",
        "## Reconciliation Stats",
        "",
        f"- Canonical metrics created: `{len(canonical.metrics)}`",
    ]
    if warnings:
        counts = Counter(warning["code"] for warning in warnings)
        lines.extend(f"- `{code}`: `{count}`" for code, count in counts.most_common())
    else:
        lines.append("- Warnings: `0`")
    lines.extend([
        "",
        "## Canonical Metrics",
        "",
        "| Metric | Period | Value | Basis | Source | Confidence |",
        "|---|---|---:|---|---|---|",
    ])
    for metric in canonical.metrics:
        lines.append(
            f"| {metric.metric_name} | {metric.period} | {_fmt(metric.value, metric.unit)} | "
            f"{metric.basis} | {', '.join(metric.source_ids)} | {metric.confidence} |"
        )
    lines.extend(["", "## Top Unresolved Disagreements", ""])
    true_disagreements = [
        warning for warning in warnings
        if warning.get("code") == "TRUE_SOURCE_VALUE_DISAGREEMENT"
    ]
    if true_disagreements:
        lines.extend(
            f"- `{warning['code']}` `{warning.get('metric')}`: {warning['message']}"
            for warning in true_disagreements[:20]
        )
    else:
        lines.append("- No true unresolved source disagreements.")

    lines.extend(["", "## Ignored Frame / Period Variants", ""])
    ignored = [
        warning for warning in warnings
        if warning.get("code") in {"SOURCE_FRAME_VARIANT_IGNORED", "PERIOD_TYPE_MISMATCH_IGNORED"}
    ]
    if ignored:
        ignored_counts = Counter(warning["code"] for warning in ignored)
        lines.extend(f"- `{code}`: `{count}`" for code, count in ignored_counts.most_common())
    else:
        lines.append("- No ignored frame or period variants.")

    lines.extend(["", "## Warnings", ""])
    if warnings:
        lines.extend(f"- `{warning['code']}`: {warning['message']}" for warning in warnings)
    else:
        lines.append("- No reconciliation warnings.")
    return "\n".join(lines) + "\n"


def save_reconciliation_report(markdown: str, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return target


def save_reconciliation_warnings(warnings: list[dict], path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(warnings, indent=2, sort_keys=True), encoding="utf-8")
    return target


def render_current_period_reconciliation_summary(
    canonical: CanonicalFinancials,
    metrics_packet: MetricsPacket,
    warnings: Optional[list[dict]] = None,
) -> str:
    warnings = warnings or []
    ignored_count = sum(
        int(warning.get("count") or 1)
        for warning in warnings
        if warning.get("code") in {"SOURCE_FRAME_VARIANT_IGNORED", "PERIOD_TYPE_MISMATCH_IGNORED"}
    )
    true_disagreements = [
        warning for warning in warnings if warning.get("code") == "TRUE_SOURCE_VALUE_DISAGREEMENT"
    ]
    metric_rows = [
        ("revenue_ttm", metrics_packet.fundamentals.revenue_ttm, "usd", "revenue"),
        ("free_cash_flow_ttm", metrics_packet.fundamentals.free_cash_flow_ttm, "usd", "free_cash_flow"),
        ("sbc_to_revenue", metrics_packet.fundamentals.sbc_to_revenue, "percent", "sbc"),
        ("operating_income_ttm", metrics_packet.fundamentals.operating_income_ttm, "usd", "operating_income"),
        ("net_income_ttm", metrics_packet.fundamentals.net_income_ttm, "usd", "net_income"),
        ("ev_to_sales", metrics_packet.valuation.ev_to_sales, "multiple", None),
        ("price_to_fcf", metrics_packet.valuation.price_to_fcf, "multiple", None),
    ]
    lines = [
        f"# Current Period Reconciliation Summary - {canonical.ticker}",
        "",
        f"- As-of date: `{canonical.as_of_date}`",
        f"- True unresolved disagreements: `{len(true_disagreements)}`",
        f"- Ignored frame / period variants: `{ignored_count}`",
        "",
        "## Final Metrics Used",
        "",
        "| Metric | Value | Period | Basis | Source | Confidence |",
        "|---|---:|---|---|---|---|",
    ]
    for metric_name, value, unit, canonical_name in metric_rows:
        source_metric = _best_current_metric(canonical, canonical_name) if canonical_name else None
        lines.append(
            f"| {metric_name} | {_fmt_optional(value, unit)} | "
            f"{source_metric.period if source_metric else 'MetricsPacket'} | "
            f"{source_metric.basis if source_metric else 'derived'} | "
            f"{', '.join(source_metric.source_ids) if source_metric else 'metrics_packet'} | "
            f"{source_metric.confidence if source_metric else 'medium'} |"
        )
    lines.extend(["", "## Top Unresolved Disagreements", ""])
    if true_disagreements:
        lines.extend(
            f"- `{warning.get('metric')}` `{warning.get('period_type')}`: {warning.get('message')}"
            for warning in true_disagreements[:20]
        )
    else:
        lines.append("- No true unresolved source disagreements.")
    return "\n".join(lines) + "\n"


def save_current_period_reconciliation_summary(markdown: str, path: Union[str, Path]) -> Path:
    return save_reconciliation_report(markdown, path)


def _fmt(value: float, unit: str) -> str:
    if unit == "percent":
        return f"{value:.1%}"
    return f"{value:,.2f} {unit}"


def _fmt_optional(value: Optional[float], unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "percent":
        return f"{value:.1%}"
    if unit == "multiple":
        return f"{value:,.2f}x"
    return f"{value:,.2f}"


def _best_current_metric(canonical: CanonicalFinancials, metric_name: Optional[str]):
    if metric_name is None:
        return None
    candidates = [
        metric for metric in canonical.metrics_for(metric_name)
        if metric.period_bucket in {"quarterly", "annual", "ttm", "instant"}
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda metric: (
            metric.end_date or "",
            {"high": 3, "medium": 2, "low": 1}.get(metric.confidence, 0),
            1 if any("IR" in source_id.upper() or "EARNINGS" in source_id.upper() for source_id in metric.source_ids) else 0,
        ),
        reverse=True,
    )[0]
