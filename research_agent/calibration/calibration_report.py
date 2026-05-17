from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, Union

from research_agent.calibration.rule_weight_engine import RuleCalibrationStats


def render_calibration_report(
    stats: Iterable[RuleCalibrationStats],
    report_date: str | None = None,
    live_engine_version: str = "v1",
    shadow_engine_version: str = "v2_shadow",
    min_outcome_window: str = "60D",
) -> str:
    stats = list(stats)
    report_date = report_date or date.today().isoformat()
    sample_size = max((stat.sample_size for stat in stats), default=0)
    useful = [stat for stat in stats if stat.recommendation in {"increase", "decrease", "keep"}]
    weak = [stat for stat in stats if stat.recommendation in {"disable", "shadow_only"}]
    lines = [
        f"# Calibration Report - {report_date}",
        "",
        f"Sample size: {sample_size} reports",
        f"Minimum outcome window: {min_outcome_window}",
        f"Live engine version: {live_engine_version}",
        f"Shadow engine version: {shadow_engine_version}",
        "",
        "## Top Useful Rules",
        "",
        "| Rule | Sample | Avg 60D Excess | Hit Rate Positive | Recommendation |",
        "|---|---:|---:|---:|---|",
    ]
    for stat in useful:
        lines.append(
            "| {rule} | {sample} | {excess} | {hit_rate} | {recommendation} |".format(
                rule=stat.rule_id,
                sample=stat.sample_size,
                excess=_pct(stat.avg_60d_excess_return),
                hit_rate=_pct(stat.hit_rate_positive_excess_60d),
                recommendation=stat.recommendation,
            )
        )
    lines.extend([
        "",
        "## Rules to Keep in Shadow",
        "",
        "| Rule | Reason |",
        "|---|---|",
    ])
    for stat in weak:
        reason = "Insufficient sample size" if stat.sample_size < 30 else stat.recommendation
        lines.append(f"| {stat.rule_id} | {reason} |")
    lines.extend([
        "",
        "## Recommendation",
        "",
        "Keep calibrated weights in shadow mode until sample size and confidence thresholds are met.",
    ])
    return "\n".join(lines) + "\n"


def save_calibration_report(markdown: str, path: Union[str, Path]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return target


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"
