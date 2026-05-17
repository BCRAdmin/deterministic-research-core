from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from research_agent.audit.rating_action_extractor import extract_action_lines, infer_report_action_class
from research_agent.audit.report_linter import audit_markdown_report
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.e2e.acceptance_report import save_acceptance_report
from research_agent.e2e.e2e_case import E2ECase
from research_agent.e2e.e2e_result import E2EResult
from research_agent.e2e.fixture_loader import load_cases_from_path, load_packets
from research_agent.e2e.regression_summary import save_regression_summary
from research_agent.e2e.report_diff import unified_report_diff
from research_agent.evidence.evidence_report import render_evidence_report, save_evidence_report
from research_agent.quality.quality_score import calculate_quality_score, save_quality_report
from research_agent.repair.repair_orchestrator import run_auto_repair


class E2ERunner:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_case(self, case: E2ECase) -> E2EResult:
        original_report = Path(case.original_report_path).read_text(encoding="utf-8")
        packets = load_packets(case)

        initial_audit = audit_markdown_report(
            markdown=original_report,
            metrics_packet=packets["metrics_packet"],
            validation_report=packets["validation_report"],
            source_registry=packets.get("source_registry"),
            evidence_ledger=packets.get("evidence_ledger"),
            decision_packet=packets.get("decision_packet"),
            ticker=case.ticker,
        )

        decision_packet = packets.get("decision_packet") or build_decision_packet(
            metrics_packet=packets["metrics_packet"],
            validation_report=packets["validation_report"],
            action_class=_action_class(original_report),
        )

        if initial_audit.has_blocking_errors:
            repair_result = run_auto_repair(
                draft_markdown=original_report,
                data_packet=packets["data_packet"],
                metrics_packet=packets["metrics_packet"],
                validation_report=packets["validation_report"],
                audit_report=initial_audit,
                decision_packet=decision_packet,
                source_registry=packets.get("source_registry"),
            )
            final_markdown = repair_result.final_markdown
            repaired = True
        else:
            final_markdown = original_report
            repaired = False

        final_audit = audit_markdown_report(
            markdown=final_markdown,
            metrics_packet=packets["metrics_packet"],
            validation_report=packets["validation_report"],
            source_registry=packets.get("source_registry"),
            evidence_ledger=packets.get("evidence_ledger"),
            decision_packet=decision_packet,
            ticker=case.ticker,
        )
        quality = calculate_quality_score(
            validation_report=packets["validation_report"],
            audit_report=final_audit,
            decision_packet=decision_packet,
            final_markdown=final_markdown,
        )
        final_status = _final_status(repaired, final_audit.has_blocking_errors, quality.publishable)
        failure_reasons = self._evaluate_expectations(
            case=case,
            initial_audit=initial_audit,
            final_audit=final_audit,
            decision_packet=decision_packet,
            quality=quality,
            final_status=final_status,
            final_markdown=final_markdown,
        )
        result = E2EResult(
            case_id=case.case_id,
            ticker=case.ticker,
            initial_audit=initial_audit,
            final_audit=final_audit,
            decision_packet=decision_packet,
            quality_score=quality,
            repaired=repaired,
            final_markdown=final_markdown,
            passed=not failure_reasons,
            final_status=final_status,
            failure_reasons=failure_reasons,
        )
        self._save_case_artifacts(case, result, original_report, packets)
        return result

    def run_cases(self, cases: list[E2ECase], run_id: str = "e2e_latest") -> list[E2EResult]:
        results = [self.run_case(case) for case in cases]
        save_regression_summary(results, self.output_dir, run_id=run_id)
        return results

    def _evaluate_expectations(
        self,
        case: E2ECase,
        initial_audit,
        final_audit,
        decision_packet,
        quality,
        final_status: str,
        final_markdown: str,
    ) -> list[str]:
        failures: list[str] = []
        for expected in case.expected_issues:
            found = initial_audit.has_issue(expected.code, metric=expected.metric)
            if expected.must_find and not found:
                failures.append(f"Expected initial issue {expected.code} was not found.")
            if expected.severity:
                severities = [issue.severity for issue in initial_audit.issues if issue.code == expected.code]
                if expected.severity not in severities:
                    failures.append(f"Expected issue {expected.code} severity {expected.severity} was not found.")

        permission = decision_packet.rating_permission
        if case.expected_rating.preferred_rating and permission.preferred_rating.value != case.expected_rating.preferred_rating:
            failures.append(
                f"Expected preferred rating {case.expected_rating.preferred_rating}, got {permission.preferred_rating.value}."
            )
        blocked = {rating.value for rating in permission.blocked_ratings}
        for rating in case.expected_rating.blocked_ratings:
            if rating not in blocked:
                failures.append(f"Expected blocked rating {rating}.")
            if rating.lower() in final_markdown.lower():
                failures.append(f"Final markdown still contains blocked rating text {rating}.")

        if case.expected_final_status in {"publishable", "repaired_publishable"}:
            if final_audit.has_blocking_errors:
                failures.append("Final audit still has blocking errors.")
            if quality.total_score < case.minimum_quality_score:
                failures.append(f"Quality score {quality.total_score} below minimum {case.minimum_quality_score}.")
            if not quality.publishable:
                failures.append("Quality gate is not publishable.")
        if case.expected_final_status == "repaired_publishable" and not final_status == "repaired_publishable":
            failures.append(f"Expected repaired_publishable final status, got {final_status}.")
        if case.expected_final_status == "manual_review" and final_status != "manual_review":
            failures.append(f"Expected manual_review final status, got {final_status}.")
        return failures

    def _save_case_artifacts(self, case: E2ECase, result: E2EResult, original_report: str, packets: dict) -> None:
        target_dir = self.output_dir / case.case_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "final_repaired_report.md").write_text(result.final_markdown, encoding="utf-8")
        (target_dir / "report_diff.patch").write_text(unified_report_diff(original_report, result.final_markdown), encoding="utf-8")
        _save_model(result.initial_audit, target_dir / "initial_audit_report.json")
        _save_model(result.final_audit, target_dir / "audit_report.json")
        _save_model(result.decision_packet, target_dir / "decision_packet.json")
        save_quality_report(result.quality_score, target_dir / "quality_score.json")
        evidence_ledger = packets.get("evidence_ledger")
        if evidence_ledger is not None:
            markdown = render_evidence_report(evidence_ledger)
            save_evidence_report(markdown, target_dir / "evidence_report.md")
        _save_model(result, target_dir / "e2e_result.json")
        save_acceptance_report(result, self.output_dir)


def _action_class(markdown: str) -> Optional[str]:
    action_class = infer_report_action_class(extract_action_lines(markdown))
    return action_class if action_class != "unknown" else None


def _final_status(repaired: bool, has_blocking_errors: bool, publishable: bool) -> str:
    if has_blocking_errors or not publishable:
        return "manual_review"
    return "repaired_publishable" if repaired else "publishable"


def _save_model(model, path: Path) -> None:
    payload = model.model_dump(mode="json") if hasattr(model, "model_dump") else model.dict()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run E2E regression cases for research reports.")
    parser.add_argument("--cases", required=True, help="Directory or JSON case file.")
    parser.add_argument("--output", required=True, help="Output directory for E2E artifacts.")
    parser.add_argument("--run-id", default="e2e_latest")
    args = parser.parse_args(argv)

    cases = load_cases_from_path(args.cases)
    runner = E2ERunner(args.output)
    results = runner.run_cases(cases, run_id=args.run_id)
    return 0 if all(result.passed for result in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
