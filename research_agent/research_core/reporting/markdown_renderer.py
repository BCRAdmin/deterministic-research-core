from __future__ import annotations

from pathlib import Path


def save_report(ticker: str, as_of_date: str, report: str, output_dir: str = "research_agent/data/outputs") -> Path:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{ticker.upper()}_{as_of_date}_report.md"
    target.write_text(report, encoding="utf-8")
    return target

