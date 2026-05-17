from __future__ import annotations

from pathlib import Path

from research_agent.e2e.e2e_result import E2EResult


def render_acceptance_report(result: E2EResult) -> str:
    lines = [
        f"# E2E Acceptance Report - {result.case_id}",
        "",
        f"- Ticker: `{result.ticker}`",
        f"- Passed: `{result.passed}`",
        f"- Repaired: `{result.repaired}`",
        f"- Final status: `{result.final_status}`",
        f"- Quality score: `{result.quality_score.total_score}`",
        f"- Preferred rating: `{result.decision_packet.rating_permission.preferred_rating.value}`",
        "",
        "## Failures",
    ]
    if result.failure_reasons:
        lines.extend(f"- {reason}" for reason in result.failure_reasons)
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"


def save_acceptance_report(result: E2EResult, output_dir: str | Path) -> Path:
    target = Path(output_dir) / result.case_id / "acceptance_report.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_acceptance_report(result), encoding="utf-8")
    return target
