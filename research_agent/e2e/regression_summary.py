from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from research_agent.e2e.e2e_result import E2EResult


class RegressionSummary(BaseModel):
    run_id: str
    cases_total: int
    cases_passed: int
    cases_failed: int
    avg_quality_score: float
    repair_rate: float
    manual_review_count: int
    failures: list[dict] = Field(default_factory=list)


def build_regression_summary(results: Iterable[E2EResult], run_id: str = "e2e_latest") -> RegressionSummary:
    results = list(results)
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    repaired = sum(1 for result in results if result.repaired)
    manual_review = sum(1 for result in results if result.final_status == "manual_review")
    avg_quality = (
        sum(result.quality_score.total_score for result in results) / total
        if total
        else 0.0
    )
    failures = [
        {
            "case_id": result.case_id,
            "ticker": result.ticker,
            "failure_reasons": result.failure_reasons,
        }
        for result in results
        if not result.passed
    ]
    return RegressionSummary(
        run_id=run_id,
        cases_total=total,
        cases_passed=passed,
        cases_failed=total - passed,
        avg_quality_score=avg_quality,
        repair_rate=repaired / total if total else 0.0,
        manual_review_count=manual_review,
        failures=failures,
    )


def render_regression_summary_markdown(results: Iterable[E2EResult], summary: RegressionSummary) -> str:
    lines = [
        "# E2E Regression Summary",
        "",
        f"- Run ID: `{summary.run_id}`",
        f"- Cases: `{summary.cases_passed}/{summary.cases_total}` passed",
        f"- Average quality score: `{summary.avg_quality_score:.1f}`",
        f"- Repair rate: `{summary.repair_rate:.1%}`",
        "",
        "| Case | Ticker | Passed | Repaired | Quality | Final Rating |",
        "|---|---|---:|---:|---:|---|",
    ]
    for result in results:
        lines.append(
            "| {case} | {ticker} | {passed} | {repaired} | {quality:.0f} | {rating} |".format(
                case=result.case_id,
                ticker=result.ticker,
                passed="yes" if result.passed else "no",
                repaired="yes" if result.repaired else "no",
                quality=result.quality_score.total_score,
                rating=result.decision_packet.rating_permission.preferred_rating.value,
            )
        )
    return "\n".join(lines) + "\n"


def save_regression_summary(results: list[E2EResult], output_dir: str | Path, run_id: str = "e2e_latest") -> RegressionSummary:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    summary = build_regression_summary(results, run_id=run_id)
    payload = summary.model_dump(mode="json") if hasattr(summary, "model_dump") else summary.dict()
    (target_dir / "e2e_summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (target_dir / "e2e_summary.md").write_text(
        render_regression_summary_markdown(results, summary),
        encoding="utf-8",
    )
    return summary
