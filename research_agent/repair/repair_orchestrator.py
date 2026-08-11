from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from research_agent.audit.audit_report import AuditReport
from research_agent.audit.report_linter import audit_markdown_report
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.repair.repair_policy import MAX_REPAIR_ATTEMPTS, requires_repair
from research_agent.repair.repair_result import RepairChange, RepairResult
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport


class RepairAttempt(BaseModel):
    attempt: int
    repair_result: RepairResult
    audit_report: AuditReport


class AutoRepairRunResult(BaseModel):
    success: bool
    final_markdown: str
    attempts: list[RepairAttempt] = Field(default_factory=list)
    final_audit_report: AuditReport


class DeterministicRepairClient:
    """Rule-based repair client used for deterministic regression tests."""

    def repair_report(
        self,
        draft: str,
        data_packet: DataPacket,
        metrics_packet: MetricsPacket,
        validation_report: ValidationReport,
        audit_report: AuditReport,
        decision_packet: DecisionPacket,
        source_registry: Optional[SourceRegistry],
        attempt: int,
    ) -> RepairResult:
        repaired = draft
        changes: list[RepairChange] = []

        for issue in audit_report.issues:
            if not requires_repair(issue.code):
                continue
            before = repaired
            repaired = self._repair_issue(repaired, issue, metrics_packet, decision_packet)
            if repaired != before:
                changes.append(
                    RepairChange(
                        issue_code=issue.code,
                        original_text=before,
                        repaired_text=repaired,
                        explanation=f"Applied deterministic repair for {issue.code}.",
                    )
                )

        new_audit = audit_markdown_report(
            markdown=repaired,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            source_registry=source_registry,
            ticker=data_packet.ticker,
            decision_packet=decision_packet,
        )
        return RepairResult(
            ticker=data_packet.ticker,
            attempt=attempt,
            success=not new_audit.has_blocking_errors,
            repaired_markdown=repaired,
            changes=changes,
            remaining_blocking_errors=[
                issue.code for issue in new_audit.issues if requires_repair(issue.code)
            ],
        )

    def _repair_issue(
        self,
        markdown: str,
        issue,
        metrics_packet: MetricsPacket,
        decision_packet: DecisionPacket,
    ) -> str:
        if issue.code == "NUMERIC_MISMATCH" and issue.metric:
            return _replace_line_for_metric(markdown, issue, metrics_packet)
        if issue.code == "PERIOD_MISMATCH" and issue.metric == "operating_margin":
            value = metrics_packet.fundamentals.operating_margin_ttm
            if value is None:
                return _remove_line(markdown, issue.line_number)
            return _replace_line(markdown, issue.line_number, f"Operating Margin TTM: {value:.1%}.")
        if issue.code == "INVALID_TRADE_LEVEL":
            return _repair_trade_levels(markdown, metrics_packet)
        if issue.code in {"RATING_TOO_HARSH_FOR_ACTION", "RATING_ACTION_MISMATCH", "RATING_BLOCKED_BY_DECISION_PACKET"}:
            permission = decision_packet.rating_permission
            if permission.permission_type == "safety_fallback" or not permission.allowed_ratings:
                return _remove_rating_and_action_language(markdown)
            preferred = decision_packet.rating_permission.preferred_rating.value
            return _replace_rating(markdown, preferred)
        if issue.code in {"OVERSTATED_CAUSALITY", "WEAK_NEWS_CAUSALITY"}:
            return _soften_causality(markdown)
        if issue.code == "NO_NEWS_WITH_AVAILABLE_SOURCES":
            return _replace_no_news(markdown)
        if issue.code == "UNVERIFIED_HARD_METRIC":
            return _remove_line(markdown, issue.line_number)
        if issue.code == "MISSING_EVIDENCE_FOR_HARD_CLAIM":
            return _remove_line(markdown, issue.line_number)
        return markdown


def run_auto_repair(
    draft_markdown: str,
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    validation_report: ValidationReport,
    audit_report: AuditReport,
    decision_packet: DecisionPacket,
    source_registry: Optional[SourceRegistry],
    llm_client: Optional[Any] = None,
    max_attempts: int = MAX_REPAIR_ATTEMPTS,
) -> AutoRepairRunResult:
    current_draft = draft_markdown
    attempts: list[RepairAttempt] = []
    current_audit = audit_report
    repair_client = llm_client or DeterministicRepairClient()

    for attempt in range(1, max_attempts + 1):
        if not current_audit.has_blocking_errors:
            return AutoRepairRunResult(
                success=True,
                final_markdown=current_draft,
                attempts=attempts,
                final_audit_report=current_audit,
            )

        repaired = repair_client.repair_report(
            draft=current_draft,
            data_packet=data_packet,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            audit_report=current_audit,
            decision_packet=decision_packet,
            source_registry=source_registry,
            attempt=attempt,
        )
        current_draft = repaired.repaired_markdown
        current_audit = audit_markdown_report(
            markdown=current_draft,
            metrics_packet=metrics_packet,
            validation_report=validation_report,
            source_registry=source_registry,
            ticker=data_packet.ticker,
            decision_packet=decision_packet,
        )
        attempts.append(
            RepairAttempt(
                attempt=attempt,
                repair_result=repaired,
                audit_report=current_audit,
            )
        )

    return AutoRepairRunResult(
        success=not current_audit.has_blocking_errors,
        final_markdown=current_draft,
        attempts=attempts,
        final_audit_report=current_audit,
    )


def _replace_line_for_metric(markdown: str, issue, metrics_packet: MetricsPacket) -> str:
    metric = issue.metric
    if metric == "free_cash_flow_ttm":
        value = metrics_packet.fundamentals.free_cash_flow_ttm
        return _replace_line(markdown, issue.line_number, f"FCF TTM: {_format_usd(value)}.")
    if metric == "forward_pe_consensus":
        value = metrics_packet.valuation.forward_pe_consensus
        return _replace_line(markdown, issue.line_number, f"Forward KGV: {value:.1f}x.")
    if metric == "operating_margin_ttm":
        value = metrics_packet.fundamentals.operating_margin_ttm
        return _replace_line(markdown, issue.line_number, f"Operating Margin TTM: {value:.1%}.")
    return markdown


def _repair_trade_levels(markdown: str, metrics_packet: MetricsPacket) -> str:
    entry_match = re.search(r"(Entry\s*\$?\s*)([0-9]+(?:[.,][0-9]+)?)", markdown, re.IGNORECASE)
    stop_match = re.search(r"(Stop-Loss\s*\$?\s*)([0-9]+(?:[.,][0-9]+)?)", markdown, re.IGNORECASE)
    if not entry_match or not stop_match:
        return markdown
    entry = float(entry_match.group(2).replace(",", "."))
    stop_reference = metrics_packet.technical.sma_50 or metrics_packet.technical.bollinger_lower
    if stop_reference is None or stop_reference >= entry:
        stop_reference = entry * 0.92
    replacement = f"{stop_match.group(1)}{stop_reference:.2f}"
    return markdown[: stop_match.start()] + replacement + markdown[stop_match.end() :]


def _replace_rating(markdown: str, preferred_rating: str) -> str:
    rating_re = re.compile(r"(Rating\s*[:\-]\s*)([A-Za-z ]+)", re.IGNORECASE)
    if rating_re.search(markdown):
        return rating_re.sub(rf"\1{preferred_rating}", markdown, count=1)
    return f"Rating: {preferred_rating}\n\n{markdown}"


def _remove_rating_and_action_language(markdown: str) -> str:
    """Remove recommendations when the decision packet permits no rating.

    A safety fallback is an explicit abstention, not a weak Hold.  Replacing a
    prohibited rating with another rating would make the prose contradict the
    machine-readable decision state.
    """

    prohibited_prefix = re.compile(
        r"^\s*(?:[-*]\s*)?(?:rating|operative\s+action|action\s+plan|action)\s*[:\-]",
        re.IGNORECASE,
    )
    return "\n".join(
        line for line in markdown.splitlines() if not prohibited_prefix.search(line)
    )


def _soften_causality(markdown: str) -> str:
    softened = re.sub(r"\bbecause of\b", "in the context of", markdown, flags=re.IGNORECASE)
    softened = re.sub(r"\bdue to\b", "alongside", softened, flags=re.IGNORECASE)
    softened = re.sub(r"\bcaused by\b", "temporally near", softened, flags=re.IGNORECASE)
    softened = re.sub(r"\btriggered by\b", "temporally near", softened, flags=re.IGNORECASE)
    softened = re.sub(r"\baufgrund\b", "im Kontext von", softened, flags=re.IGNORECASE)
    softened = re.sub(r"\bwegen\b", "im Umfeld von", softened, flags=re.IGNORECASE)
    softened = softened.replace("proving distribution", "without proving direct causality")
    return softened


def _replace_no_news(markdown: str) -> str:
    return re.sub(
        r"No company-specific news found in the period\.|No news found\.|No relevant news\.",
        "SourceRegistry contains relevant company/news sources; the report should discuss sourced events rather than claiming no news.",
        markdown,
        flags=re.IGNORECASE,
    )


def _remove_line(markdown: str, line_number: Optional[int]) -> str:
    if line_number is None:
        return markdown
    lines = markdown.splitlines()
    index = line_number - 1
    if 0 <= index < len(lines):
        lines.pop(index)
    return "\n".join(lines)


def _replace_line(markdown: str, line_number: Optional[int], replacement: str) -> str:
    if line_number is None:
        return markdown
    lines = markdown.splitlines()
    index = line_number - 1
    if 0 <= index < len(lines):
        lines[index] = replacement
    return "\n".join(lines)


def _format_usd(value: Optional[float]) -> str:
    if value is None:
        return "Metric unavailable in validated packet"
    magnitude = abs(value)
    sign = "-" if value < 0 else ""
    if magnitude >= 1_000_000_000:
        return f"{sign}${magnitude / 1_000_000_000:.3f}B"
    if magnitude >= 1_000_000:
        return f"{sign}${magnitude / 1_000_000:.1f}M"
    return f"{sign}${magnitude:,.0f}"
