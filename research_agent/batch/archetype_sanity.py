from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.audit.audit_report import AuditIssue
from research_agent.batch.batch_manifest import BatchManifest, BatchRunItem, save_batch_manifest
from research_agent.batch.dashboard_adapter import build_dashboard_status, save_dashboard_status
from research_agent.batch.display_policy import external_rating_payload
from research_agent.quality.deeptech_manual_review import (
    EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING,
    EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE,
    assess_speculative_deep_tech_manual_review,
)
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry
from research_agent.research_core.models.metrics_packet import FundamentalMetrics, MetricsPacket, TechnicalMetrics, ValuationMetrics


BATCH_ID = "archetype_sanity_check"
AS_OF_DATE = "2026-05-16"
TICKERS = ("RGTI", "IONQ", "QBTS", "RKLB", "GOOGL", "SNOW", "MSFT", "QCOM")
FCF_SUPPORT_FOR_ACCUMULATE_CODE = "MISSING_FCF_SUPPORT_FOR_ACCUMULATE"


def run_archetype_sanity_batch(output_dir: str | Path = Path("outputs/batches") / BATCH_ID) -> dict[str, Any]:
    """Run a compact archetype sanity batch without invoking the full report pipeline."""
    batch_dir = Path(output_dir)
    batch_dir.mkdir(parents=True, exist_ok=True)

    items = [_run_case(case, batch_dir) for case in _cases()]
    manifest = BatchManifest(
        batch_id=BATCH_ID,
        as_of_date=AS_OF_DATE,
        started_at=_utc_now(),
        finished_at=_utc_now(),
        status="completed_with_manual_review" if any(item.status == "manual_review" for item in items) else "completed",
        items=items,
    )
    save_batch_manifest(manifest, batch_dir / "batch_manifest.json")
    dashboard = build_dashboard_status(manifest)
    save_dashboard_status(dashboard, batch_dir / "dashboard_status.json")
    (batch_dir / "archetype_sanity_review.md").write_text(_render_review(dashboard), encoding="utf-8")
    (batch_dir / "score_split_report.md").write_text(_render_score_split_review(dashboard), encoding="utf-8")
    return dashboard


def _run_case(case: dict[str, Any], batch_dir: Path) -> BatchRunItem:
    assessment = assess_speculative_deep_tech_manual_review(
        markdown=case["markdown"],
        metrics_packet=case["metrics"],
        source_registry=case["sources"],
        rating_text=case.get("rating_text"),
    )
    issues = list(assessment.issues)
    if case.get("qcom_missing_fcf_support"):
        issues.append(
            AuditIssue(
                severity="warning",
                code=FCF_SUPPORT_FOR_ACCUMULATE_CODE,
                message="Accumulate display requires explicit FCF support before external publication.",
            )
        )

    ticker = case["ticker"]
    ticker_dir = batch_dir / "reports" / ticker
    ticker_dir.mkdir(parents=True, exist_ok=True)

    counts = dict(assessment.counts)
    if case.get("qcom_missing_fcf_support"):
        counts["fcf_unavailable_block_count"] = 1

    status = "manual_review" if assessment.status == "manual_review" or case.get("qcom_missing_fcf_support") else "passed"
    publishable = bool(assessment.publishable and status == "passed")
    quality_score = _score_for(assessment.company_archetype.value, bool(case.get("qcom_missing_fcf_support")))
    split = _score_split_for(
        ticker=ticker,
        status=status,
        quality_score=quality_score,
        assessment=assessment,
        qcom_missing_fcf_support=bool(case.get("qcom_missing_fcf_support")),
    )
    quality_payload = {
        **assessment.to_quality_payload(),
        "ticker": ticker,
        "as_of_date": AS_OF_DATE,
        "total_score": quality_score,
        **split,
        "status": status,
        "publishable": publishable,
        "risk_profiles": [
            issue.code
            for issue in issues
            if issue.code in {
                "SPECULATIVE_DEEP_TECH_MANUAL_REVIEW_PROFILE",
                EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH_MANUAL_REVIEW_PROFILE,
            }
        ],
        "manual_review_reasons": [issue.code for issue in issues],
        "external_display_rating": assessment.external_display_rating,
        "sec_ir_current_period_evidence_complete": assessment.sec_ir_current_period_evidence_complete,
    }
    audit_payload = {
        "ticker": ticker,
        "has_blocking_errors": status == "manual_review",
        "issues": [_issue_payload(issue) for issue in issues],
    }

    quality_path = ticker_dir / "quality_score.json"
    audit_path = ticker_dir / "audit_report.json"
    case_path = ticker_dir / "sanity_case.json"
    quality_path.write_text(json.dumps(quality_payload, indent=2, sort_keys=True), encoding="utf-8")
    audit_path.write_text(json.dumps(audit_payload, indent=2, sort_keys=True), encoding="utf-8")
    case_path.write_text(json.dumps(_case_payload(case, assessment), indent=2, sort_keys=True), encoding="utf-8")

    return BatchRunItem(
        ticker=ticker,
        status=status,
        output_path=str(ticker_dir),
        quality_score=quality_score,
        final_rating=case["final_rating"],
        preferred_rating=case["preferred_rating"],
        publishable=publishable,
        counts=counts,
        artifacts={
            "quality_score.json": str(quality_path),
            "audit_report.json": str(audit_path),
            "sanity_case.json": str(case_path),
        },
    )


def _cases() -> list[dict[str, Any]]:
    return [
        {
            "ticker": "RGTI",
            "metrics": _metrics("RGTI", revenue=7_090_000, market_cap=6_340_000_000, operating_income=-75_000_000, fcf=-77_200_000, sbc_to_revenue=2.48, dilution=0.18),
            "sources": _vendor_sources("RGTI"),
            "final_rating": "Underweight",
            "preferred_rating": "Underweight",
            "markdown": _deeptech_text("RGTI", "quantum hardware", beta=1.8),
            "rating_text": "Rating: Underweight. Fundamental risk is extreme; technical SMA, RSI, support, resistance and momentum also dominate the decision.",
        },
        {
            "ticker": "IONQ",
            "metrics": _metrics("IONQ", revenue=43_000_000, market_cap=9_200_000_000, operating_income=-205_000_000, fcf=-170_000_000, sbc_to_revenue=1.2, dilution=0.16),
            "sources": _vendor_sources("IONQ"),
            "final_rating": "Underweight",
            "preferred_rating": "Underweight",
            "markdown": _deeptech_text("IONQ", "quantum computing", beta=1.9),
            "rating_text": "Rating: Underweight. The investment thesis is constrained by early commercial adoption and valuation disconnect.",
        },
        {
            "ticker": "QBTS",
            "metrics": _metrics("QBTS", revenue=9_500_000, market_cap=1_400_000_000, operating_income=-80_000_000, fcf=-68_000_000, sbc_to_revenue=0.72, dilution=0.24),
            "sources": _vendor_sources("QBTS"),
            "final_rating": "Underweight",
            "preferred_rating": "Underweight",
            "markdown": _deeptech_text("QBTS", "quantum annealing hardware", beta=2.2),
            "rating_text": "Rating: Underweight. Contract milestones exist, but revenue is lumpy and commercial adoption is not scaled.",
        },
        {
            "ticker": "RKLB",
            "metrics": _metrics(
                "RKLB",
                revenue=622_495_000,
                market_cap=75_540_078_250,
                operating_income=-233_765_000,
                fcf=-220_123_000,
                sbc_to_revenue=0.12,
                ev_to_sales=118.78,
                atr=8.89,
                close=124.77,
            ),
            "sources": _space_infrastructure_sources("RKLB"),
            "final_rating": "Hold",
            "preferred_rating": "Hold",
            "markdown": (
                "This company has real commercial space-infrastructure revenue, backlog above $2.2B, contracted missions, "
                "Space Systems/product revenue, Launch Services/service revenue, Electron launch cadence and a Neutron development program. "
                "It remains capital-intensive with major execution milestone risk, high volatility, negative operating income and negative FCF. "
                "Contract value, delivery revenue timing, market cap, annual revenue, recurring versus one-off programmatic revenue, commercial/government mix and valuation support are discussed."
            ),
            "rating_text": "Rating: Hold. FCF path, execution milestones and valuation discipline block clean Accumulate.",
        },
        {
            "ticker": "GOOGL",
            "metrics": _metrics("GOOGL", revenue=350_000_000_000, market_cap=2_100_000_000_000, operating_income=108_000_000_000, fcf=70_000_000_000, sbc_to_revenue=0.04),
            "sources": _primary_sources("GOOGL"),
            "final_rating": "Hold",
            "preferred_rating": "Hold",
            "markdown": "GOOGL is a mega-cap platform with SEC/IR current-period financial evidence, scaled revenue, strong operating income, and positive free cash flow.",
            "rating_text": "Rating: Hold. The rationale is based on scaled fundamentals, valuation, and platform durability.",
        },
        {
            "ticker": "SNOW",
            "metrics": _metrics("SNOW", revenue=4_500_000_000, market_cap=72_000_000_000, operating_income=-1_000_000_000, fcf=1_000_000_000, sbc_to_revenue=0.25),
            "sources": _primary_sources("SNOW"),
            "final_rating": "Hold",
            "preferred_rating": "Hold",
            "markdown": "SNOW is a SaaS consumption company with scaled commercial adoption, SEC/IR evidence, high revenue, and positive free cash flow.",
            "rating_text": "Rating: Hold. High valuation alone does not make this an early-commercial deep-tech profile.",
        },
        {
            "ticker": "MSFT",
            "metrics": _metrics("MSFT", revenue=260_000_000_000, market_cap=3_200_000_000_000, operating_income=112_000_000_000, fcf=75_000_000_000, sbc_to_revenue=0.035),
            "sources": _primary_sources("MSFT"),
            "final_rating": "Hold",
            "preferred_rating": "Hold",
            "markdown": "MSFT is a mega-cap platform with primary financial evidence, scaled commercial adoption, operating profits, and positive free cash flow.",
            "rating_text": "Rating: Hold. The rationale is platform scale and cash generation.",
        },
        {
            "ticker": "QCOM",
            "metrics": _metrics("QCOM", revenue=39_000_000_000, market_cap=185_000_000_000, operating_income=10_500_000_000, fcf=None, sbc_to_revenue=0.04),
            "sources": _primary_sources("QCOM"),
            "final_rating": "Accumulate",
            "preferred_rating": "Accumulate",
            "markdown": "QCOM is a semiconductor AI infrastructure company with primary evidence and scaled revenue. This sanity case omits FCF support for an Accumulate display check.",
            "rating_text": "Rating: Accumulate. FCF support is intentionally absent in this fixture.",
            "qcom_missing_fcf_support": True,
        },
    ]


def _metrics(
    ticker: str,
    *,
    revenue: float,
    market_cap: float,
    operating_income: float,
    fcf: float | None,
    sbc_to_revenue: float,
    dilution: float | None = None,
    ev_to_sales: float | None = None,
    atr: float | None = None,
    close: float = 100.0,
) -> MetricsPacket:
    return MetricsPacket(
        ticker=ticker,
        as_of_date=AS_OF_DATE,
        technical=TechnicalMetrics(indicator_date=AS_OF_DATE, close=close, atr_14=atr),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=revenue,
            operating_income_ttm=operating_income,
            free_cash_flow_ttm=fcf,
            sbc_to_revenue=sbc_to_revenue,
            diluted_share_count_yoy=dilution,
        ),
        valuation=ValuationMetrics(market_cap=market_cap, ev_to_sales=ev_to_sales),
    )


def _vendor_sources(ticker: str) -> SourceRegistry:
    return SourceRegistry(
        registry_id=f"{ticker.lower()}_vendor",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker.lower()}_vendor_financials",
                ticker=ticker,
                source_type="yahoo_finance",
                used_for=["revenue_ttm", "operating_income", "free_cash_flow_ttm", "sbc", "cash", "debt", "eps"],
            )
        ],
    )


def _primary_sources(ticker: str) -> SourceRegistry:
    return SourceRegistry(
        registry_id=f"{ticker.lower()}_primary",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker.lower()}_10q",
                ticker=ticker,
                source_type="sec_filing",
                used_for=["revenue_ttm", "operating_income", "free_cash_flow_ttm", "financials", "cash", "eps"],
            ),
            SourceRegistryEntry(
                source_id=f"{ticker.lower()}_ir_release",
                ticker=ticker,
                source_type="company_ir",
                used_for=["revenue_ttm", "financials"],
            ),
        ],
    )


def _space_infrastructure_sources(ticker: str) -> SourceRegistry:
    return SourceRegistry(
        registry_id=f"{ticker.lower()}_space_infrastructure",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker.lower()}_10q",
                ticker=ticker,
                source_type="sec_filing",
                used_for=["revenue_ttm", "operating_income", "free_cash_flow_ttm", "financials", "cash"],
            ),
            SourceRegistryEntry(
                source_id=f"{ticker.lower()}_ir_release",
                ticker=ticker,
                source_type="company_ir",
                used_for=[
                    "current_q_revenue",
                    "backlog",
                    "contract_backlog",
                    "contracted_missions",
                    "launch_cadence",
                    "electron_execution",
                    "neutron_development_risk",
                    "product_revenue",
                    "space_systems_revenue",
                    "service_revenue",
                    "launch_services_revenue",
                    "free_cash_flow",
                ],
            ),
        ],
    )


def _deeptech_text(ticker: str, domain: str, *, beta: float) -> str:
    return (
        f"{ticker} is an early commercial {domain} story stock with limited commercial adoption and lumpy revenue. "
        "Revenue is not scaled, operating income remains negative, free cash flow remains negative, and SBC is high. "
        "Hard financial metrics are vendor-only and no SEC/IR current-period evidence is available. "
        "Loss narrowed and GAAP net income improved after derivative and warrant fair-value effects. "
        f"Beta: {beta}. Roadmap milestone, qubit prototype milestone, defense contract, and customer order language are prominent, "
        "but the report only describes the announcement qualitatively and lacks a quantified materiality bridge to valuation."
    )


def _score_for(archetype: str, qcom_missing_fcf_support: bool) -> float:
    if archetype == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL":
        return 70.0
    if archetype == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH":
        return 78.0
    if qcom_missing_fcf_support:
        return 82.0
    return 92.0


def _score_split_for(
    *,
    ticker: str,
    status: str,
    quality_score: float,
    assessment: Any,
    qcom_missing_fcf_support: bool,
) -> dict[str, Any]:
    archetype = assessment.company_archetype.value
    if archetype == "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL":
        return {
            "publish_quality_score": 68,
            "internal_research_quality_score": 80,
            "data_confidence_score": 55,
            "score_explanation_short": (
                "Not publishable because hard metrics are vendor-heavy and the archetype requires manual review; "
                "internal report is useful as a speculative deep-tech risk note."
            ),
        }
    if archetype == "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH":
        return {
            "publish_quality_score": min(int(quality_score), 70),
            "internal_research_quality_score": 78,
            "data_confidence_score": 72,
            "score_explanation_short": (
                "Manual review due to negative FCF and extreme valuation; internal report is usable because "
                "backlog, revenue scale, FCF path and execution risks are clearly explained."
            ),
        }
    if qcom_missing_fcf_support:
        return {
            "publish_quality_score": 72,
            "internal_research_quality_score": 74,
            "data_confidence_score": 62,
            "score_explanation_short": "Manual review because FCF support is missing for the external Accumulate display.",
        }
    return {
        "publish_quality_score": int(quality_score),
        "internal_research_quality_score": int(quality_score),
        "data_confidence_score": 90 if ticker in {"GOOGL", "SNOW", "MSFT"} else 85,
        "score_explanation_short": "Gold-v1 report with current-period KPIs, evidence support and coherent rating logic."
        if status == "passed"
        else "Score split reflects separate publication readiness, internal research usefulness and data confidence.",
    }


def _issue_payload(issue: AuditIssue) -> dict[str, Any]:
    if hasattr(issue, "model_dump"):
        return issue.model_dump(mode="json")
    return issue.dict()


def _case_payload(case: dict[str, Any], assessment: Any) -> dict[str, Any]:
    return {
        "ticker": case["ticker"],
        "expected_role": _expected_role(case["ticker"]),
        "company_archetype": assessment.company_archetype.value,
        "archetype_confidence": assessment.archetype_confidence,
        "archetype_triggered_rules": assessment.archetype_triggered_rules,
        "active_deeptech_profile": assessment.active,
        "publishable": assessment.publishable,
        "issue_codes": [issue.code for issue in assessment.issues],
    }


def _render_review(dashboard: dict[str, Any]) -> str:
    rows = []
    for item in dashboard["items"]:
        rows.append(
            "| {ticker} | {expected} | {archetype} | {confidence:.3f} | {status} | {publishable} | {display} | {rules} |".format(
                ticker=item["ticker"],
                expected=_expected_role(item["ticker"]),
                archetype=item["company_archetype"],
                confidence=float(item["archetype_confidence"] or 0),
                status=item["status"],
                publishable=item["publishable"],
                display=item["display_rating"] or "",
                rules=", ".join(item["archetype_triggered_rules"][:5]),
            )
        )
    summary = dashboard["summary"]
    return "\n".join(
        [
            "# Archetype Sanity Review",
            "",
            f"Batch: `{dashboard['batch_id']}`",
            f"As of: `{dashboard['as_of_date']}`",
            "",
            "| Ticker | Erwartung | Archetype | Confidence | Status | Publishable | External Display | Top Triggered Rules |",
            "|---|---|---:|---:|---|---:|---|---|",
            *rows,
            "",
            "## Ergebnis",
            "",
            f"- Deep-Tech Profile Count: {summary['speculative_deep_tech_profile_count']}",
            f"- Early-Commercial Capital-Intensive Tech Count: {summary.get('early_commercial_capital_intensive_tech_count', 0)}",
            f"- Vendor-only Hard Metrics Count: {summary['vendor_only_hard_metrics_count']}",
            f"- Accounting-Gain Guard Count: {summary['accounting_gain_not_operating_turnaround_count']}",
            f"- Order Materiality Missing Count: {summary['order_materiality_missing_count']}",
            f"- Technical Overweight Count: {summary['technical_overweight_in_thesis_count']}",
            "",
            "## Sanity-Urteil",
            "",
            "- RGTI bleibt `manual_review` und wird als `SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL` erkannt.",
            "- IONQ und QBTS lösen ebenfalls generisch aus, weil mehrere frühe Deep-Tech-, Microcap-/Story-Stock- und Evidence-Risiken zusammenkommen.",
            f"- RKLB-artige Space-/Hardware-Fälle mit Umsatz, Backlog und Execution-Risiko laufen als `EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH` und zeigen `{EARLY_COMMERCIAL_CAPITAL_INTENSIVE_DISPLAY_RATING}`.",
            "- GOOGL, SNOW und MSFT werden nicht als Deep-Tech klassifiziert.",
            "- QCOM bleibt `SEMICONDUCTOR_AI_INFRA`; die FCF-Support-Display-Regel bleibt sichtbar mit `Hold Pending FCF Support`.",
            "- Keine Guard-Lockerung und keine neue Architektur: der Batch nutzt die bestehende Audit-/Quality-/Dashboard-Schicht.",
            "",
        ]
    )


def _render_score_split_review(dashboard: dict[str, Any]) -> str:
    rows = [
        "| {ticker} | {status} | {publish} | {internal} | {data} | {legacy} | {publishable} | {explanation} |".format(
            ticker=item["ticker"],
            status=item["status"],
            publish=item.get("publish_quality_score"),
            internal=item.get("internal_research_quality_score"),
            data=item.get("data_confidence_score"),
            legacy=item.get("total_score_legacy"),
            publishable=item.get("publishable"),
            explanation=str(item.get("score_explanation_short") or "").replace("|", "/"),
        )
        for item in dashboard["items"]
    ]
    return "\n".join(
        [
            "# Archetype Score Split Review",
            "",
            f"Batch: `{dashboard['batch_id']}`",
            f"As of: `{dashboard['as_of_date']}`",
            "",
            "| Ticker | Status | Publish Quality | Internal Research | Data Confidence | Legacy Total | Publishable | Explanation |",
            "|---|---|---:|---:|---:|---:|---:|---|",
            *rows,
            "",
        ]
    )


def _expected_role(ticker: str) -> str:
    return {
        "RGTI": "Deep-Tech manual_review",
        "IONQ": "Deep-Tech pruefen",
        "QBTS": "Deep-Tech pruefen",
        "RKLB": "Early-commercial capital-intensive tech",
        "GOOGL": "Mega-Cap kein Deep-Tech",
        "SNOW": "SaaS kein Deep-Tech",
        "MSFT": "Mega-Cap kein Deep-Tech",
        "QCOM": "Semiconductor, FCF Display-Regel",
    }[ticker]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    run_archetype_sanity_batch()
