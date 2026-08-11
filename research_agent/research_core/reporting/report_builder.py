from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional

from research_agent.audit.report_linter import audit_markdown_report
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.decision.rating_permission import enforce_rating_permission
from research_agent.evidence.claim_evidence_mapper import map_claim_to_evidence
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.evidence.evidence_validator import validate_claim_has_evidence, validate_metric_evidence
from research_agent.quality.quality_score import calculate_quality_score, save_quality_report
from research_agent.repair.repair_orchestrator import run_auto_repair
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import (
    ValidationReport,
    describe_blocking_validation_errors,
)


def render_metric_table(metrics: MetricsPacket, currency: str = "USD") -> str:
    return f"""
| Metric | Value |
|---|---:|
| Close | {_fmt_currency(metrics.technical.close, 2, currency)} |
| 50 SMA | {_fmt_number(metrics.technical.sma_50, 2)} |
| 200 SMA | {_fmt_number(metrics.technical.sma_200, 2)} |
| RSI 14 | {_fmt_number(metrics.technical.rsi_14, 2)} |
| FCF TTM | {_fmt_currency(metrics.fundamentals.free_cash_flow_ttm, 0, currency)} |
| SBC / Revenue | {_fmt_pct(metrics.fundamentals.sbc_to_revenue)} |
| EV / Sales | {_fmt_number(metrics.valuation.ev_to_sales, 2)} |
| P / FCF | {_fmt_number(metrics.valuation.price_to_fcf, 2)} |
""".strip()


def render_markdown_report(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    validation_report: ValidationReport,
    claims: Optional[Iterable[ResearchClaim]] = None,
    red_team_findings: Optional[Iterable[str]] = None,
    final_decision: Optional[str] = None,
    source_registry: Optional[SourceRegistry] = None,
    evidence_ledger: Optional[EvidenceLedger] = None,
    decision_packet: Optional[DecisionPacket] = None,
    run_audit: bool = False,
    audit_output_dir: Optional[str] = None,
    enable_auto_repair: bool = False,
    repair_client=None,
) -> str:
    if validation_report.has_blocking_errors:
        raise RuntimeError(
            "Blocking validation errors. Final report generation stopped. "
            + describe_blocking_validation_errors(validation_report)
        )
    claims = list(claims or [])
    if evidence_ledger is not None:
        _enforce_evidence_grounding(evidence_ledger, claims, metrics_packet)

    sections = [
        f"# {data_packet.ticker} Research Report",
        _render_data_basis(data_packet),
        "## Validated Metric Table",
        render_metric_table(metrics_packet, data_packet.price_basis.currency),
        "## Validation Status",
        _render_validation_summary(validation_report),
        "## Analyst Interpretation",
        _render_claims(claims, evidence_ledger),
    ]
    if red_team_findings:
        sections.extend(["## Red-Team Findings", "\n".join(f"- {item}" for item in red_team_findings)])
    if decision_packet:
        sections.extend(["## Rating Permission", _render_rating_permission(decision_packet)])
    if final_decision:
        if decision_packet:
            enforce_rating_permission(final_decision, decision_packet.rating_permission)
        sections.extend(["## Investment Committee", final_decision])
    if source_registry:
        sections.extend(["## Source Quality", _render_source_quality(source_registry)])
    report = "\n\n".join(section for section in sections if section)

    if run_audit:
        audit = audit_markdown_report(
            markdown=report,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            source_registry=source_registry,
            decision_packet=decision_packet,
            evidence_ledger=evidence_ledger,
            ticker=data_packet.ticker,
        )
        if audit.has_blocking_errors:
            if enable_auto_repair and decision_packet:
                repair_run = run_auto_repair(
                    draft_markdown=report,
                    data_packet=data_packet,
                    metrics_packet=metrics_packet,
                    validation_report=validation_report,
                    audit_report=audit,
                    decision_packet=decision_packet,
                    source_registry=source_registry,
                    llm_client=repair_client,
                )
                report = repair_run.final_markdown
                audit = repair_run.final_audit_report
                if audit_output_dir:
                    _save_repair_artifacts(repair_run, audit_output_dir)
                if not repair_run.success:
                    if audit_output_dir:
                        _save_manual_review_required(report, audit, audit_output_dir)
                    raise RuntimeError("Auto-repair could not clear blocking Markdown audit errors.")
            else:
                if audit_output_dir:
                    _save_failed_audit_draft(report, audit, audit_output_dir)
                raise RuntimeError("Blocking Markdown audit errors. Final report generation stopped.")

        if decision_packet:
            quality = calculate_quality_score(
                validation_report=validation_report,
                audit_report=audit,
                decision_packet=decision_packet,
                final_markdown=report,
            )
            if audit_output_dir:
                save_quality_report(quality, Path(audit_output_dir) / "quality_score.json")
                if quality.publishable:
                    (Path(audit_output_dir) / "final_report.md").write_text(report, encoding="utf-8")
            if not quality.publishable:
                if audit_output_dir:
                    _save_manual_review_required(report, audit, audit_output_dir)
                raise RuntimeError("Quality gate failed. Final report generation stopped.")

    return report


def _render_data_basis(data_packet: DataPacket) -> str:
    lines = [
        "## Data Basis",
        f"- Report as-of date: `{data_packet.as_of_date}`",
        f"- Price basis: `{data_packet.price_basis.close:.2f} {data_packet.price_basis.currency}` close from `{data_packet.price_basis.date}` via `{data_packet.price_basis.source}`",
        f"- Source registry: `{data_packet.source_registry_id}`",
    ]
    if data_packet.as_of_date != data_packet.price_basis.date:
        lines.append(
            f"- Technical indicators are based on the closing price from `{data_packet.price_basis.date}`, not on the report creation date `{data_packet.as_of_date}`."
        )
    if not data_packet.next_events.next_earnings_date:
        lines.append("- Next earnings date: metric unavailable in validated packet.")
    elif not data_packet.next_events.confirmed:
        lines.append(f"- Next earnings date `{data_packet.next_events.next_earnings_date}` is unconfirmed.")
    else:
        lines.append(f"- Next earnings date: `{data_packet.next_events.next_earnings_date}`.")
    return "\n".join(lines)


def _render_validation_summary(validation_report: ValidationReport) -> str:
    if not validation_report.issues:
        return "No validation issues."
    return "\n".join(
        f"- `{issue.severity}` `{issue.code}`: {issue.message}"
        for issue in validation_report.issues
    )


def _render_claims(
    claims: Iterable[ResearchClaim],
    evidence_ledger: Optional[EvidenceLedger] = None,
) -> str:
    claim_list = list(claims)
    if not claim_list:
        return "No LLM claims attached. Use validated packets before adding interpretation."
    lines = []
    for claim in claim_list:
        evidence_ids = []
        if evidence_ledger is not None:
            mapping = map_claim_to_evidence(claim, evidence_ledger)
            evidence_ids = mapping["evidence_ids"]
        evidence_suffix = (
            f" Evidence IDs: `{', '.join(evidence_ids)}`."
            if evidence_ids
            else ""
        )
        claim_id_suffix = (
            f" Claim ID: `{claim.claim_id}`."
            if claim.claim_id
            else ""
        )
        lines.append(
            f"- {claim.claim}{claim_id_suffix} Evidence metrics: `{', '.join(claim.evidence_metrics)}`.{evidence_suffix} Confidence: `{claim.confidence}`."
        )
    return "\n".join(lines)


def _render_source_quality(source_registry: SourceRegistry) -> str:
    if not source_registry.sources:
        return "No sources registered."
    return "\n".join(
        f"- `{source.source_id}` `{source.source_type}` rank `{source.resolved_authority_rank()}` used for `{', '.join(source.used_for)}`"
        for source in source_registry.sources
    )


def _render_rating_permission(decision_packet: DecisionPacket) -> str:
    permission = decision_packet.rating_permission
    return "\n".join(
        [
            f"- Analytical display rating: `{permission.display_rating or permission.preferred_rating.value}`",
            f"- Internal fallback rating: `{permission.preferred_rating.value}`",
            f"- Permission type: `{permission.permission_type}`",
            f"- Allowed ratings: `{', '.join(rating.value for rating in permission.allowed_ratings)}`",
            f"- Blocked ratings: `{', '.join(rating.value for rating in permission.blocked_ratings)}`",
            f"- Reason: {permission.reason}",
        ]
    )


def _fmt_number(value: Optional[float], digits: int) -> str:
    if value is None:
        return "Metric unavailable in validated packet."
    return f"{value:,.{digits}f}"


def _fmt_currency(value: Optional[float], digits: int, currency: str) -> str:
    if value is None:
        return "Metric unavailable in validated packet."
    normalized_currency = str(currency or "USD").strip().upper()
    return f"{value:,.{digits}f} {normalized_currency}"


def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "Metric unavailable in validated packet."
    return f"{value:.1%}"


def _enforce_evidence_grounding(
    evidence_ledger: EvidenceLedger,
    claims: list[ResearchClaim],
    metrics_packet: MetricsPacket,
) -> None:
    required_metrics = ["close"]
    if metrics_packet.fundamentals.free_cash_flow_ttm is not None:
        required_metrics.append("free_cash_flow_ttm")
    if metrics_packet.fundamentals.sbc_to_revenue is not None:
        required_metrics.append("sbc_to_revenue")
    blocking = []
    for metric in required_metrics:
        issue = validate_metric_evidence(metric, evidence_ledger)
        if issue and issue["severity"] == "error":
            blocking.append(issue)
    for claim in claims:
        issue = validate_claim_has_evidence(claim, evidence_ledger)
        if issue:
            blocking.append(issue)
    if blocking:
        codes = ", ".join(issue["code"] for issue in blocking)
        raise RuntimeError(f"Evidence grounding failed. Blocking issues: {codes}.")


def _save_failed_audit_draft(report: str, audit, audit_output_dir: str) -> None:
    target_dir = Path(audit_output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "draft_failed_audit.md").write_text(report, encoding="utf-8")
    payload = _model_to_json_dict(audit)
    (target_dir / "audit_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _save_repair_artifacts(repair_run, audit_output_dir: str) -> None:
    target_dir = Path(audit_output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "repaired_report.md").write_text(repair_run.final_markdown, encoding="utf-8")
    payload = _model_to_json_dict(repair_run)
    (target_dir / "repair_result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    audit_payload = _model_to_json_dict(repair_run.final_audit_report)
    (target_dir / "audit_report.json").write_text(
        json.dumps(audit_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _save_manual_review_required(report: str, audit, audit_output_dir: str) -> None:
    target_dir = Path(audit_output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "manual_review_required.md").write_text(report, encoding="utf-8")
    (target_dir / "draft_failed_audit.md").write_text(report, encoding="utf-8")
    payload = _model_to_json_dict(audit)
    (target_dir / "audit_report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _model_to_json_dict(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()
